"""Lắp ứng dụng FastAPI, lỗi thống nhất và bản web đóng gói nếu có."""

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app.api.access_log import AccessLogger, AccessLogMiddleware, utc_now
from app.api.routes import router
from app.api.service import CaseService
from app.auth.revocation import RevocationList
from app.auth.verifier import Authenticator, JwtVerifier
from app.config.settings import load_access_log_enabled, load_auth_settings, load_settings

_ROOT = Path(__file__).resolve().parents[2]


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


def _error(request: Request, status: int, code: str, message: str) -> JSONResponse:
    """Tạo thân lỗi đúng hợp đồng, không đính kèm dữ liệu đầu vào."""
    request.state.ma_loi = code
    return JSONResponse(status_code=status, content={"loi": {"ma": code, "thong_bao": message}})


@asynccontextmanager
async def _lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Đóng bộ chạy nền AI và kết nối HTTP khi ứng dụng kết thúc."""
    application.state.access_log.cleanup()
    if application.state.auth_settings.auth_mode == "off":
        logging.getLogger(__name__).warning(
            "AUTH_MODE=off: xác thực đã tắt; chỉ dùng cho phát triển cục bộ."
        )
    try:
        yield
    finally:
        shutdown = getattr(application.state.service, "shutdown", None)
        if callable(shutdown):
            shutdown()


def create_app(
    service: CaseService | None = None,
    auth: Authenticator | None = None,
    *,
    access_log_dir: Path | None = None,
    access_log_clock: Callable[[], datetime] = utc_now,
) -> FastAPI:
    """Dựng ứng dụng với dịch vụ được tiêm hoặc cấu hình công khai của kho."""
    application = FastAPI(openapi_url=None, docs_url=None, redoc_url=None, lifespan=_lifespan)
    auth_settings = load_auth_settings()
    application.state.auth_settings = auth_settings
    application.state.auth = auth if auth is not None else JwtVerifier(auth_settings)
    application.state.revocations = RevocationList()
    if service is None:
        settings = load_settings()
        service = CaseService(
            _ROOT / settings.app.case_dir,
            _ROOT / "data/kb/quy_tac_lieu_than.json",
            _ROOT / "data/runtime/phan_hoi.jsonl",
        )
    application.state.service = service
    access_log = AccessLogger(
        access_log_dir if access_log_dir is not None else service._feedback_path.parent,
        enabled=load_access_log_enabled(),
        clock=access_log_clock,
    )
    application.state.access_log = access_log
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(auth_settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        """Thay cả lỗi định tuyến mặc định bằng thân lỗi API."""
        if isinstance(exc.detail, dict) and "ma" in exc.detail and "thong_bao" in exc.detail:
            return _error(
                request, exc.status_code, str(exc.detail["ma"]), str(exc.detail["thong_bao"])
            )
        if exc.status_code == 404:
            return _error(request, 404, "khong_tim_thay", "Không tìm thấy tài nguyên.")
        if exc.status_code >= 500:
            return _error(request, exc.status_code, "loi_he_thong", "Đã xảy ra lỗi hệ thống.")
        return _error(request, exc.status_code, "du_lieu_khong_hop_le", "Dữ liệu không hợp lệ.")

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Không phản chiếu thân yêu cầu trong thông báo kiểm tra dữ liệu."""
        return _error(request, 422, "du_lieu_khong_hop_le", "Dữ liệu không hợp lệ.")

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
