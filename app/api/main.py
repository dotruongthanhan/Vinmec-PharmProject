"""Lắp ứng dụng FastAPI, lỗi thống nhất và bản web đóng gói nếu có."""

import logging
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from threading import Thread

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import container as container_mod
from app.api import lookup
from app.api.access_log import AccessLogger, AccessLogMiddleware, utc_now
from app.api.routes import router
from app.api.service import CaseService
from app.auth.errors import AuthError
from app.auth.revocation import RevocationList
from app.auth.verifier import Authenticator, JwtVerifier
from app.config.settings import (
    AuthSettings,
    assert_auth_mode_allowed,
    database_url_warnings,
    get_secret,
    load_access_log_enabled,
    load_auth_settings,
    load_env_file,
    load_kb_source,
    load_settings,
)
from app.core.errors import ConfigError
from app.db.read_pool import read_pool
from app.db.reader import DatabaseReadError
from app.kb.names import DrugNameIndex
from app.rules import (
    allergy_config,
    d4_config,
    d5_config,
    d6_config,
    d7_config,
    duplicate_config,
    renal_dose,
)

_ROOT = Path(__file__).resolve().parents[2]
# Chạy local (uvicorn app.api.main:app) cần SUPABASE_URL, SUPABASE_ANON_KEY... từ .env gốc.
# Biến đã có trong môi trường (Docker, CI, test) được ưu tiên, nên EC2 không đổi hành vi.
load_env_file()


class WebFiles(StaticFiles):
    """Phục vụ tệp web và trả trang gốc cho đường dẫn phía trình duyệt."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Giữ lỗi API ngoài cơ chế trả trang gốc của web."""
        if path.lstrip("/").startswith("api"):
            raise HTTPException(404)
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


def _error(
    request: Request,
    status: int,
    code: str,
    message: str,
    *,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Tạo thân lỗi đúng hợp đồng, không đính kèm dữ liệu đầu vào."""
    request.state.ma_loi = code
    return JSONResponse(
        status_code=status,
        content={"loi": {"ma": code, "thong_bao": message}},
        headers=dict(headers) if headers else None,
    )


_MAX_API_BODY_BYTES = 262_144
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})
_TOO_LARGE_MESSAGE = "Nội dung yêu cầu vượt quá giới hạn cho phép."


def _parse_content_length(headers: list[tuple[bytes, bytes]]) -> int | None:
    """Đọc Content-Length; trả None nếu thiếu và -1 nếu sai định dạng hoặc trùng lệch."""
    parsed: set[int] = set()
    for key, val in headers:
        if key.lower() != b"content-length":
            continue
        raw = val.decode("latin-1").strip()
        if not (raw.isascii() and raw.isdigit()):
            return -1
        parsed.add(int(raw))
    if not parsed:
        return None
    if len(parsed) != 1:
        return -1
    return next(iter(parsed))


def _has_bearer_header(headers: list[tuple[bytes, bytes]]) -> bool:
    """Kiểm tra có đúng một tiêu đề Authorization dạng Bearer <token> không rỗng."""
    values: list[str] = []
    for key, val in headers:
        if key.lower() == b"authorization":
            values.append(val.decode("latin-1"))
    if len(values) != 1:
        return False
    parts = values[0].split()
    return len(parts) == 2 and parts[0].lower() == "bearer"


def _has_chunked_encoding(headers: list[tuple[bytes, bytes]]) -> bool:
    """Kiểm tra tiêu đề Transfer-Encoding có chứa chunked hay không."""
    for key, val in headers:
        if key.lower() == b"transfer-encoding" and b"chunked" in val.lower():
            return True
    return False


async def _send_api_error(
    scope: Scope,
    receive: Receive,
    send: Send,
    status: int,
    code: str,
    message: str,
) -> None:
    """Trả thân lỗi API chuẩn và gắn mã lỗi vào scope cho nhật ký truy cập."""
    scope.setdefault("state", {})["ma_loi"] = code
    response = JSONResponse(
        status_code=status,
        content={"loi": {"ma": code, "thong_bao": message}},
    )
    await response(scope, receive, send)


async def _send_auth_error(scope: Scope, receive: Receive, send: Send, code: str) -> None:
    """Trả lỗi xác thực theo đúng mã và thông báo cố định trong app.auth.errors."""
    err = AuthError(code)
    if isinstance(err.detail, dict):
        err_code = str(err.detail.get("ma", code))
        err_msg = str(err.detail.get("thong_bao", "Bạn cần đăng nhập để tiếp tục."))
    else:
        err_code = code
        err_msg = "Bạn cần đăng nhập để tiếp tục."
    await _send_api_error(scope, receive, send, err.status_code, err_code, err_msg)


async def _read_bounded_body(receive: Receive, limit: int) -> bytes | None:
    """Đọc thân yêu cầu tối đa `limit` byte; vượt ngưỡng thì dừng và trả None."""
    chunks: list[bytes] = []
    total = 0
    more_body = True
    while more_body:
        message = await receive()
        msg_type = message.get("type")
        if msg_type == "http.disconnect":
            break
        if msg_type != "http.request":
            continue
        chunk = message.get("body", b"")
        if chunk:
            total += len(chunk)
            if total > limit:
                return None
            chunks.append(chunk)
        more_body = bool(message.get("more_body", False))
    return b"".join(chunks)


class _ApiGuardMiddleware:
    """Chặn thân quá lớn và yêu cầu thiếu Bearer trước khi định tuyến API."""

    def __init__(self, app: ASGIApp, *, default_auth_settings: AuthSettings) -> None:
        self.app = app
        self._default_auth_settings = default_auth_settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Kiểm trần kích thước và tiêu đề Bearer cho /api/* (trừ GET /api/health, OPTIONS)."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = str(scope.get("method", "")).upper()
        path = str(scope.get("path", ""))
        is_api = path == "/api" or path.startswith("/api/")
        if not is_api or method == "OPTIONS" or (method == "GET" and path == "/api/health"):
            await self.app(scope, receive, send)
            return

        headers: list[tuple[bytes, bytes]] = list(scope.get("headers", []))
        content_length = _parse_content_length(headers)
        if content_length == -1:
            await _send_api_error(
                scope,
                receive,
                send,
                400,
                "du_lieu_khong_hop_le",
                "Dữ liệu không hợp lệ.",
            )
            return
        if content_length is not None and content_length > _MAX_API_BODY_BYTES:
            await _send_api_error(scope, receive, send, 413, "than_qua_lon", _TOO_LARGE_MESSAGE)
            return

        state_app = scope.get("app")
        auth_settings = getattr(
            getattr(state_app, "state", None),
            "auth_settings",
            self._default_auth_settings,
        )
        if auth_settings.auth_mode != "off":
            if not auth_settings.supabase_url:
                await _send_auth_error(scope, receive, send, "xac_thuc_khong_san_sang")
                return
            if not _has_bearer_header(headers):
                await _send_auth_error(scope, receive, send, "chua_dang_nhap")
                return

        if _has_chunked_encoding(headers) or (content_length is None and method in _BODY_METHODS):
            buffered = await _read_bounded_body(receive, _MAX_API_BODY_BYTES)
            if buffered is None:
                await _send_api_error(scope, receive, send, 413, "than_qua_lon", _TOO_LARGE_MESSAGE)
                return
            body_sent = False

            async def replay_receive() -> Message:
                nonlocal body_sent
                if not body_sent:
                    body_sent = True
                    return {"type": "http.request", "body": buffered, "more_body": False}
                return await receive()

            await self.app(scope, replay_receive, send)
            return

        await self.app(scope, receive, send)


def _should_warmup_db() -> bool:
    """Chỉ làm nóng nền khi KB_SOURCE được cấu hình đọc từ DB."""
    try:
        return load_kb_source() == "db"
    except ConfigError:
        return False


def _warmup_db_knowledge() -> None:
    """Nạp trước chỉ mục tra cứu, DDInter và toàn bộ bảng luật ở luồng nền."""
    logger = logging.getLogger(__name__)
    try:
        container_mod.get_rule_context()
    except Exception as exc:
        logger.warning("Lỗi làm nóng ngữ cảnh luật từ DB (%s)", type(exc).__name__)
    loaders: tuple[Callable[[], object], ...] = (
        renal_dose.load_renal_rules,
        d4_config.try_load_default_hepatic_config,
        d4_config.try_load_default_lab_threshold_config,
        d4_config.try_load_default_drug_disease_config,
        d5_config.try_load_default_route_config,
        d5_config.try_load_default_max_dose_config,
        d6_config.try_load_default_toxicity_config,
        d7_config.try_load_default_stewardship_config,
        allergy_config.try_load_default_allergy_config,
        duplicate_config.try_load_default_duplicate_config,
        DrugNameIndex.load,
        lookup.warm_suggest_index,
    )
    for loader in loaders:
        try:
            loader()
        except Exception as exc:
            name = getattr(loader, "__qualname__", getattr(loader, "__name__", "loader"))
            logger.warning("Lỗi làm nóng bảng luật %s từ DB (%s)", name, type(exc).__name__)


@asynccontextmanager
async def _lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Làm nóng tri thức nền khi dùng DB, dọn nhật ký và đóng tài nguyên khi tắt."""
    application.state.access_log.cleanup()
    if application.state.auth_settings.auth_mode == "off":
        logging.getLogger(__name__).warning(
            "AUTH_MODE=off: xác thực đã tắt; chỉ dùng cho phát triển cục bộ."
        )
    try:
        db_url = get_secret("DATABASE_URL")
    except ConfigError:
        db_url = ""
    if db_url:
        app_logger = logging.getLogger(__name__)
        for warning in database_url_warnings(db_url):
            app_logger.warning("%s", warning)
    warmup_thread: Thread | None = None
    if _should_warmup_db():
        warmup_thread = Thread(
            target=_warmup_db_knowledge,
            name="kb-warmup",
            daemon=True,
        )
        warmup_thread.start()
    application.state.warmup_thread = warmup_thread
    try:
        yield
    finally:
        if warmup_thread is not None and warmup_thread.is_alive():
            warmup_thread.join(timeout=2.0)
        shutdown = getattr(application.state.service, "shutdown", None)
        try:
            if callable(shutdown):
                shutdown()
        finally:
            read_pool.close()


def create_app(
    service: CaseService | None = None,
    auth: Authenticator | None = None,
    *,
    access_log_dir: Path | None = None,
    access_log_clock: Callable[[], datetime] = utc_now,
) -> FastAPI:
    """Dựng ứng dụng với dịch vụ được tiêm hoặc cấu hình công khai của kho."""
    assert_auth_mode_allowed()
    application = FastAPI(openapi_url=None, docs_url=None, redoc_url=None, lifespan=_lifespan)
    auth_settings = load_auth_settings()
    application.state.auth_settings = auth_settings
    application.state.auth = auth if auth is not None else JwtVerifier(auth_settings)
    application.state.revocations = RevocationList()
    if service is None:
        settings = load_settings()
        service = CaseService(
            _ROOT / settings.app.case_dir,
            None,
            _ROOT / "data/runtime/phan_hoi.jsonl",
        )
    application.state.service = service
    access_log = AccessLogger(
        access_log_dir if access_log_dir is not None else service._feedback_path.parent,
        enabled=load_access_log_enabled(),
        clock=access_log_clock,
    )
    application.state.access_log = access_log
    # Thêm guard trước CORS trong user_middleware để CORS vẫn bọc ngoài khi dựng stack.
    application.add_middleware(_ApiGuardMiddleware, default_auth_settings=auth_settings)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(auth_settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        """Thay cả lỗi định tuyến mặc định bằng thân lỗi API, giữ tiêu đề phản hồi."""
        headers = exc.headers
        if isinstance(exc.detail, dict) and "ma" in exc.detail and "thong_bao" in exc.detail:
            return _error(
                request,
                exc.status_code,
                str(exc.detail["ma"]),
                str(exc.detail["thong_bao"]),
                headers=headers,
            )
        if exc.status_code == 404:
            return _error(
                request,
                404,
                "khong_tim_thay",
                "Không tìm thấy tài nguyên.",
                headers=headers,
            )
        if exc.status_code >= 500:
            return _error(
                request,
                exc.status_code,
                "loi_he_thong",
                "Đã xảy ra lỗi hệ thống.",
                headers=headers,
            )
        return _error(
            request,
            exc.status_code,
            "du_lieu_khong_hop_le",
            "Dữ liệu không hợp lệ.",
            headers=headers,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Không phản chiếu thân yêu cầu trong thông báo kiểm tra dữ liệu."""
        return _error(request, 422, "du_lieu_khong_hop_le", "Dữ liệu không hợp lệ.")

    @application.exception_handler(DatabaseReadError)
    async def database_error(request: Request, exc: DatabaseReadError) -> JSONResponse:
        """Giữ thân lỗi thống nhất, chỉ dùng thông báo DB đã được làm sạch."""
        return _error(request, 503, "loi_he_thong", str(exc))

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """Ẩn nội dung ngoại lệ và dấu vết ngăn xếp khỏi người gọi."""
        return _error(request, 500, "loi_he_thong", "Đã xảy ra lỗi hệ thống.")

    application.include_router(router)
    dist = _ROOT / "web/dist"
    if (dist / "index.html").is_file():
        application.mount("/", WebFiles(directory=dist), name="web")
    # Bọc cả ServerErrorMiddleware để mã lỗi 500 đã được gắn trước khi ghi.
    application.middleware_stack = AccessLogMiddleware(
        application.build_middleware_stack(), access_log
    )
    return application


app = create_app()
