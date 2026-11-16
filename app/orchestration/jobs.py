"""Quản lý tác vụ chạy nền phân tích AI và bộ đệm trạng thái theo ca."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AiJobState(BaseModel):
    """Trạng thái hiện tại của tác vụ phân tích AI cho một ca bệnh."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    ca_id: str
    trang_thai: Literal["dang_chay", "xong", "loi"]
    ket_qua: Any = None
    canh_bao: list[str] = Field(default_factory=list)


class AiJobManager:
    """Chạy nền tối đa 2 ca đồng thời, chống chạy trùng và lưu kết quả theo ca_id."""

    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = RLock()
        self._jobs: dict[str, AiJobState] = {}
        self._generations: dict[str, int] = {}

    def start(
        self,
        ca_id: str,
        fn: Callable[[], Any],
        restart: bool = False,
    ) -> AiJobState:
        """Đặt dang_chay và nộp việc nếu chưa có hoặc restart=True; ngược lại giữ nguyên."""
        with self._lock:
            current = self._jobs.get(ca_id)
            if current is not None and not restart:
                return current
            generation = self._generations.get(ca_id, 0) + 1
            self._generations[ca_id] = generation
            state = AiJobState(ca_id=ca_id, trang_thai="dang_chay")
            self._jobs[ca_id] = state
            self._executor.submit(self._run_job, ca_id, generation, fn)
            return state

    def get(self, ca_id: str) -> AiJobState | None:
        """Trả trạng thái hiện tại của ca hoặc None nếu chưa từng khởi động."""
        with self._lock:
            return self._jobs.get(ca_id)

    def _run_job(self, ca_id: str, generation: int, fn: Callable[[], Any]) -> None:
        """Chạy tác vụ trong luồng nền và cập nhật kết quả nếu vẫn đúng thế hệ."""
        try:
            result = fn()
        except Exception as exc:
            next_state = AiJobState(
                ca_id=ca_id,
                trang_thai="loi",
                ket_qua=None,
                canh_bao=[f"Bước AI gặp lỗi không mong muốn ({type(exc).__name__})"],
            )
        else:
            raw_warnings = getattr(result, "canh_bao", [])
            warnings = [str(w) for w in raw_warnings] if isinstance(raw_warnings, list) else []
            next_state = AiJobState(
                ca_id=ca_id,
                trang_thai="xong",
                ket_qua=result,
                canh_bao=warnings,
            )
        with self._lock:
            if self._generations.get(ca_id) == generation:
                self._jobs[ca_id] = next_state

    def shutdown(self, wait: bool = True) -> None:
        """Đóng nhóm luồng nền khi ứng dụng dừng hoặc kết thúc kiểm thử."""
        self._executor.shutdown(wait=wait)
