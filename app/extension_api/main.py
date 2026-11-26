"""Ứng dụng FastAPI độc lập cho Chrome Extension (cổng 8001, Zero-Retention)."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import container as container_mod
from app.api.access_log import AccessLogger, AccessLogMiddleware, utc_now
from app.auth.errors import AuthError
from app.auth.revocation import RevocationList
from app.auth.verifier import Authenticator, JwtVerifier
from app.config.extension import (
    ExtensionSettings,
    load_extension_cors_origins,
    load_extension_cors_regex,
    load_extension_settings,
)
from app.config.settings import (
    AuthSettings,
    assert_auth_mode_allowed,
    load_access_log_enabled,
    load_auth_settings,
    load_kb_source,
)
from app.extension_api.routes import router
from app.extension_api.service import ExtensionService

_LOGGER = logging.getLogger(__name__)
_ROOT = Path(__file__).resolve().parents[2]
_ACCESS_LOG_DIR = _ROOT / "data/runtime/access_logs_extension"
_PUBLIC_PATHS = frozenset({"/api/extension/health"})


class _ExtensionBodyTooLargeError(Exception):
    """Báo thân HTTP vượt quá giới hạn cho phép."""


def _error_payload(code: str, message: str) -> dict[str, str]:
    return {"ma": code, "thong_bao": message}


def _header_value(scope: Scope, name: bytes) -> str | None:
    lowered = name.lower()
    for raw_name, raw_value in scope.get("headers", ()):
        if raw_name.lower() == lowered:
            return raw_value.decode("latin-1")
    return None


def _bearer_token(scope: Scope) -> str | None:
    """Trả token Bearer duy nhất từ tiêu đề HTTP, trả None nếu thiếu hoặc trùng lặp."""
    matches: list[str] = []
    for raw_name, raw_value in scope.get("headers", ()):
        if raw_name.lower() == b"authorization":
            matches.append(raw_value.decode("latin-1"))
    if len(matches) != 1:
        return None
    parts = matches[0].split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return None
    return parts[1].strip()


async def _send_auth_error(
    scope: Scope,
    receive: Receive,
    send: Send,
    code: str,
) -> None:
    err = AuthError(code)
    status = err.status_code
    detail = err.detail if isinstance(err.detail, dict) else _error_payload(code, "Chưa đăng nhập.")
    response = JSONResponse(
        detail,
        status_code=status,
        headers={"WWW-Authenticate": "Bearer"} if status == 401 else None,
    )
    await response(scope, receive, send)


class _ExtensionGuardMiddleware:
    """Chặn xác thực trước khi đọc ảnh 8 MB và áp giới hạn kích thước thân theo tuyến."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        auth_settings: AuthSettings,
        authenticator: Authenticator,
        max_json_bytes: int,
        max_multipart_bytes: int,
    ) -> None:
        self.app = app
        self._auth_settings = auth_settings
        self._authenticator = authenticator
        self._max_json_bytes = max_json_bytes
        self._max_multipart_bytes = max_multipart_bytes

    def _limit_for(self, scope: Scope) -> int:
        if scope["method"] == "POST" and scope["path"] == "/api/extension/extract-and-review":
            return self._max_multipart_bytes
        return self._max_json_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]
        limit = self._limit_for(scope)

        # Kiểm tra JWT trước khi nạp tải trọng ảnh (lên tới 8 MB) vào bộ nhớ.
        if (
            method != "OPTIONS"
            and path not in _PUBLIC_PATHS
            and self._auth_settings.auth_mode != "off"
        ):
            if not self._auth_settings.supabase_url:
                await _send_auth_error(scope, receive, send, "xac_thuc_khong_san_sang")
                return
            token = _bearer_token(scope)
            if token is None:
                await _send_auth_error(scope, receive, send, "chua_dang_nhap")
                return
            try:
                self._authenticator.verify(token)
            except AuthError as exc:
                detail = exc.detail if isinstance(exc.detail, dict) else {}
                await _send_auth_error(
                    scope,
                    receive,
                    send,
                    str(detail.get("ma") or "chua_dang_nhap"),
                )
                return

        content_length = _header_value(scope, b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > limit:
                    response = JSONResponse(
                        _error_payload(
                            "vuot_gioi_han_than", "Tải trọng yêu cầu vượt giới hạn cho phép."
                        ),
                        status_code=413,
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                response = JSONResponse(
                    _error_payload("yeu_cau_khong_hop_le", "Header Content-Length không hợp lệ."),
                    status_code=400,
                )
                await response(scope, receive, send)
                return

        received_bytes = 0

        async def guarded_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                received_bytes += len(chunk)
                if received_bytes > limit:
                    raise _ExtensionBodyTooLargeError()
            return message

        async def add_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", ()))
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"x-frame-options", b"DENY"))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, guarded_receive, add_security_headers)
        except _ExtensionBodyTooLargeError:
            response = JSONResponse(
                _error_payload("vuot_gioi_han_than", "Tải trọng yêu cầu vượt giới hạn cho phép."),
                status_code=413,
            )
            await response(scope, receive, send)


def _warmup_readonly_knowledge() -> None:
    """Làm ấm chỉ mục tri thức công khai (`tri_thuc`), tuyệt đối không đụng `nghiep_vu`."""
    try:
        container_mod.get_rule_context()
        kb_source = load_kb_source()
        if kb_source != "file":
            return
    except Exception as exc:
        _LOGGER.debug("Bỏ qua làm ấm tri thức (%s)", type(exc).__name__)


def _detail_error(exc: StarletteHTTPException) -> tuple[str, str]:
    detail: Any = exc.detail
    if (
        isinstance(detail, dict)
        and isinstance(detail.get("ma"), str)
        and isinstance(detail.get("thong_bao"), str)
    ):
        return detail["ma"], detail["thong_bao"]
    if isinstance(detail, str) and detail:
        return f"http_{exc.status_code}", detail
    return f"http_{exc.status_code}", "Yêu cầu không thể xử lý."


def create_extension_app(
    extension_service: ExtensionService | None = None,
    *,
    settings: ExtensionSettings | None = None,
    auth_settings: AuthSettings | None = None,
    auth: Authenticator | None = None,
    access_logger: AccessLogger | None = None,
) -> FastAPI:
    """Tạo ứng dụng FastAPI độc lập cho Extension, tách biệt hoàn toàn với app/api/main.py."""
    ext_settings = settings or (
        extension_service.settings if extension_service is not None else load_extension_settings()
    )
    resolved_auth = auth_settings or (
        extension_service.auth_settings if extension_service is not None else load_auth_settings()
    )
    if auth_settings is None:
        assert_auth_mode_allowed()
    resolved_authenticator: Authenticator = auth if auth is not None else JwtVerifier(resolved_auth)
    resolved_service = extension_service or ExtensionService(
        settings=ext_settings,
        auth_settings=resolved_auth,
    )
    logger = access_logger or AccessLogger(
        _ACCESS_LOG_DIR,
        enabled=load_access_log_enabled(),
        clock=utc_now,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            await asyncio.to_thread(_warmup_readonly_knowledge)
            yield
        finally:
            resolved_service.shutdown()

    app = FastAPI(
        title="CDSS Extension API (Zero-Retention)",
        version="1.10.0-extension",
        lifespan=lifespan,
    )
    app.state.extension_service = resolved_service
    app.state.auth_settings = resolved_auth
    app.state.auth = resolved_authenticator
    app.state.revocations = RevocationList()

    app.add_middleware(
        _ExtensionGuardMiddleware,
        auth_settings=resolved_auth,
        authenticator=resolved_authenticator,
        max_json_bytes=ext_settings.server.max_json_body_bytes,
        max_multipart_bytes=ext_settings.server.max_multipart_body_bytes,
    )
    app.add_middleware(AccessLogMiddleware, logger=logger)

    cors_origins = load_extension_cors_origins()
    cors_regex = load_extension_cors_regex()
    if cors_origins or cors_regex:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_origin_regex=cors_regex,
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Extension-Version"],
        )

    app.include_router(router)

    @app.exception_handler(StarletteHTTPException)
    def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _detail_error(exc)
        request.state.ma_loi = code
        return JSONResponse(
            _error_payload(code, message),
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(HTTPException)
    def handle_fastapi_error(request: Request, exc: HTTPException) -> JSONResponse:
        code, message = _detail_error(exc)
        request.state.ma_loi = code
        return JSONResponse(
            _error_payload(code, message),
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    def handle_validation_error(request: Request, _exc: RequestValidationError) -> JSONResponse:
        request.state.ma_loi = "du_lieu_khong_hop_le"
        return JSONResponse(
            _error_payload("du_lieu_khong_hop_le", "Dữ liệu đầu vào không hợp lệ."),
            status_code=422,
        )

    @app.exception_handler(Exception)
    def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        _LOGGER.exception("Lỗi không xử lý ở Extension API (%s)", type(exc).__name__)
        request.state.ma_loi = "loi_he_thong"
        return JSONResponse(
            _error_payload("loi_he_thong", "Hệ thống gặp lỗi nội bộ, vui lòng thử lại."),
            status_code=500,
        )

    return app


app = create_extension_app()
