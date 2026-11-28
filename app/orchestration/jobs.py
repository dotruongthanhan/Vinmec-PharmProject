"""Quản lý tác vụ chạy nền phân tích AI và bộ đệm trạng thái theo ca."""

import statistics
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.progress import TienTrinh, tien_trinh_hien_tai


class AiQueueFullError(RuntimeError):
    """Hàng đợi phân tích AI nền đã đạt trần số việc chưa hoàn tất."""


class AiJobState(BaseModel):
    """Trạng thái hiện tại của tác vụ phân tích AI cho một ca bệnh."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    ca_id: str
    trang_thai: Literal["dang_chay", "xong", "loi"]
    ket_qua: Any = None
    canh_bao: list[str] = Field(default_factory=list)
    tien_trinh: Any = None
    bat_dau: float | None = None
    ket_thuc: float | None = None


class AiJobManager:
    """Chạy nền tối đa 2 ca đồng thời, chống chạy trùng và giới hạn hàng đợi."""

    def __init__(self, max_workers: int = 2, max_pending: int = 6) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = RLock()
        self._jobs: dict[str, AiJobState] = {}
        self._generations: dict[str, int] = {}
        self._durations_ms: deque[float] = deque(maxlen=20)
        self._max_pending = max_pending

    @property
    def max_pending(self) -> int:
        """Trần số việc chưa hoàn tất (đang chạy và đang chờ)."""
        return self._max_pending

    def pending_count(self) -> int:
        """Đếm số việc đang chạy hoặc đang chờ hoàn tất."""
        with self._lock:
            return sum(1 for state in self._jobs.values() if state.trang_thai == "dang_chay")

    def thuong_le_ms(self) -> float | None:
        """Trung vị thời lượng của tối đa 20 lượt xong gần nhất; None nếu dưới 3 mẫu."""
        with self._lock:
            if len(self._durations_ms) < 3:
                return None
            return float(statistics.median(self._durations_ms))

    def start(
        self,
        ca_id: str,
        fn: Callable[[], Any],
        restart: bool = False,
    ) -> AiJobState:
        """Nộp việc nếu chưa chạy hoặc đã xong/lỗi với restart=True; đang chạy luôn giữ nguyên."""
        with self._lock:
            current = self._jobs.get(ca_id)
            if current is not None and (current.trang_thai == "dang_chay" or not restart):
                return current
            if self.pending_count() >= self._max_pending:
                raise AiQueueFullError(
                    f"Hàng đợi phân tích AI đã đạt giới hạn {self._max_pending} việc."
                )
            generation = self._generations.get(ca_id, 0) + 1
            self._generations[ca_id] = generation
            progress = TienTrinh()
            progress.dang_ky("thu_thap_nguon", "Lấy nguồn")
            progress.dang_ky("tong_hop_1", "Tổng hợp nhận định")
            progress.dang_ky("kiem_chung_1", "Kiểm chứng trích dẫn")
            state = AiJobState(
                ca_id=ca_id,
                trang_thai="dang_chay",
                tien_trinh=progress,
                bat_dau=progress.thoi_diem_bat_dau,
            )
            self._jobs[ca_id] = state
            try:
                self._executor.submit(self._run_job, ca_id, generation, fn, progress)
            except Exception:
                if current is None:
                    self._jobs.pop(ca_id, None)
                else:
                    self._jobs[ca_id] = current
                raise
            return state

    def get(self, ca_id: str) -> AiJobState | None:
        """Trả trạng thái hiện tại của ca hoặc None nếu chưa từng khởi động."""
        with self._lock:
            return self._jobs.get(ca_id)

    def _run_job(
        self,
        ca_id: str,
        generation: int,
        fn: Callable[[], Any],
        progress: TienTrinh,
    ) -> None:
        """Chạy tác vụ trong luồng nền và cập nhật kết quả nếu vẫn đúng thế hệ."""
        token = tien_trinh_hien_tai.set(progress)
        succeeded = False
        try:
            try:
                result = fn()
            except Exception as exc:
                progress.chot(False)
                finished_at = progress.thoi_diem_ket_thuc or time.perf_counter()
                next_state = AiJobState(
                    ca_id=ca_id,
                    trang_thai="loi",
                    ket_qua=None,
                    canh_bao=[f"Bước AI gặp lỗi không mong muốn ({type(exc).__name__})"],
                    tien_trinh=progress,
                    bat_dau=progress.thoi_diem_bat_dau,
                    ket_thuc=finished_at,
                )
            else:
                llm_status = getattr(getattr(result, "llm", None), "trang_thai", None)
                succeeded = llm_status != "loi_llm"
                progress.chot(succeeded)
                finished_at = progress.thoi_diem_ket_thuc or time.perf_counter()
                raw_warnings = getattr(result, "canh_bao", [])
                warnings = [str(w) for w in raw_warnings] if isinstance(raw_warnings, list) else []
                next_state = AiJobState(
                    ca_id=ca_id,
                    trang_thai="xong",
                    ket_qua=result,
                    canh_bao=warnings,
                    tien_trinh=progress,
                    bat_dau=progress.thoi_diem_bat_dau,
                    ket_thuc=finished_at,
                )
        finally:
            tien_trinh_hien_tai.reset(token)
        with self._lock:
            if self._generations.get(ca_id) == generation:
                self._jobs[ca_id] = next_state
                if succeeded:
                    self._durations_ms.append(progress.tong_ms(finished_at))

    def shutdown(self, wait: bool = True) -> None:
        """Đóng nhóm luồng nền khi ứng dụng dừng hoặc kết thúc kiểm thử."""
        self._executor.shutdown(wait=wait)
