"""Ghi nhật ký truy cập tối giản và dọn tệp theo ngày UTC."""

import logging
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import Lock
from time import perf_counter

from pydantic import BaseModel
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.auth.principal import Principal

_LOGGER = logging.getLogger(__name__)
_WRITE_LOCK = Lock()
_FILENAME = re.compile(r"nhat_ky_truy_cap-(\d{4}-\d{2}-\d{2})\.jsonl", re.ASCII)


def utc_now() -> datetime:
    """Lấy thời điểm UTC, có thể thay bằng đồng hồ thử."""
    return datetime.now(UTC)


class AccessLogEntry(BaseModel):
    """Chỉ chứa các trường được phép ghi theo hợp đồng."""

    thoi_diem: datetime
    nguoi_dung_id: str | None
    phien_id: str | None
    vai_tro: str | None
    phuong_thuc: str
    duong_dan: str
    ma_trang_thai: int
    ma_loi: str | None
    thoi_gian_ms: int


class AccessLogger:
    """Ghi và dọn nhật ký; lỗi lưu trữ không ảnh hưởng yêu cầu."""

    def __init__(
        self, directory: Path, *, enabled: bool, clock: Callable[[], datetime] = utc_now
    ) -> None:
        self.directory = directory
        self.enabled = enabled
        self.clock = clock

    def write(self, scope: Scope, status: int, elapsed_ms: int) -> None:
        """Ghi một dòng, không truy cập tiêu đề, query hay thân HTTP."""
        if not self.enabled:
            return
        try:
            now = self.clock().astimezone(UTC)
            state = scope.get("state", {})
            principal: Principal | None = state.get("principal") if status != 401 else None
            entry = AccessLogEntry(
                thoi_diem=now,
                nguoi_dung_id=principal.nguoi_dung_id if principal is not None else None,
                phien_id=principal.phien_id if principal is not None else None,
                vai_tro=principal.vai_tro if principal is not None else None,
                phuong_thuc=scope["method"],
                duong_dan=scope["path"],
                ma_trang_thai=status,
                ma_loi=state.get("ma_loi"),
                thoi_gian_ms=elapsed_ms,
            )
            line = entry.model_dump_json() + "\n"
            with _WRITE_LOCK:
                self.directory.mkdir(parents=True, exist_ok=True)
                path = self.directory / f"nhat_ky_truy_cap-{now.date().isoformat()}.jsonl"
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(line)
        except Exception as exc:
            _LOGGER.debug("Không ghi được nhật ký truy cập (%s)", type(exc).__name__)

    def cleanup(self) -> None:
        """Chỉ xoá tệp đúng mẫu có ngày cũ hơn 90 ngày, bỏ qua lỗi."""
        if not self.enabled:
            return
        try:
            cutoff = self.clock().astimezone(UTC).date() - timedelta(days=90)
            with _WRITE_LOCK:
                for path in self.directory.glob("nhat_ky_truy_cap-*.jsonl"):
                    try:
                        match = _FILENAME.fullmatch(path.name)
                        if match is None or path.is_symlink() or not path.is_file():
                            continue
                        if date.fromisoformat(match[1]) < cutoff:
                            path.unlink()
                    except Exception as exc:
                        _LOGGER.debug("Bỏ qua tệp nhật ký lỗi (%s)", type(exc).__name__)
        except Exception as exc:
            _LOGGER.debug("Không dọn được nhật ký truy cập (%s)", type(exc).__name__)


class AccessLogMiddleware:
    """Bọc ngoài xử lý lỗi để thấy cả phản hồi 500 mà không đọc thân."""

    def __init__(self, app: ASGIApp, logger: AccessLogger) -> None:
        self.app = app
        self.logger = logger

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Chỉ lấy mã HTTP từ thông điệp bắt đầu phản hồi."""
        if (
            scope["type"] != "http"
            or not self.logger.enabled
            or (scope["method"] == "GET" and scope["path"] == "/api/health")
        ):
            await self.app(scope, receive, send)
            return
        started = perf_counter()
        status = 500

        async def capture_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            self.logger.write(scope, status, int((perf_counter() - started) * 1000))
