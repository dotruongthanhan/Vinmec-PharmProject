"""Đích ghi vết JSONL theo ngày giờ Việt Nam qua hàng đợi có trần và luồng nền."""

from __future__ import annotations

import json
import logging
import queue
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Protocol

from app.db.timezone import VN_TZ
from app.tracing.models import MAX_TRACE_BYTES, VetChay

_LOGGER = logging.getLogger(__name__)
_ROOT = Path(__file__).resolve().parents[2]
_TRACE_FILENAME_RE = re.compile(r"vet-(\d{4}-\d{2}-\d{2})\.jsonl", re.ASCII)

DEFAULT_QUEUE_SIZE = 1000
DEFAULT_MAX_FILE_BYTES = 200 * 1024 * 1024
DEFAULT_TRACE_DIR = _ROOT / "data/runtime/vet"


class TraceSink(Protocol):
    """Giao diện chung cho đích ghi vết."""

    def gui(self, vet: VetChay) -> bool: ...

    def flush(self, timeout: float = 2.0) -> bool: ...

    def close(self, timeout: float = 2.0) -> None: ...


def vn_now() -> datetime:
    """Thời điểm hiện tại theo múi giờ Việt Nam (+07:00)."""
    return datetime.now(VN_TZ)


def _serialize_trace_line(vet: VetChay) -> str:
    """Tuần tự hoá vết qua json.dumps thành đúng một dòng, cắt span cuối nếu vượt 256 KB."""

    def _dump(record: VetChay) -> str:
        raw = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
        return raw.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")

    line = _dump(vet)
    if len(line.encode("utf-8")) <= MAX_TRACE_BYTES:
        return line

    spans = list(vet.cac_buoc)
    current = vet.model_copy(update={"vet_bi_cat": True, "cac_buoc": spans})
    line = _dump(current)
    while spans and len(line.encode("utf-8")) > MAX_TRACE_BYTES:
        spans.pop()
        current = current.model_copy(update={"cac_buoc": spans})
        line = _dump(current)
    return line


def don_vet_qua_han(
    so_ngay: int = 30,
    *,
    thu_muc: Path | None = None,
    dong_ho: Callable[[], datetime] | None = None,
) -> int:
    """Xoá các tệp vet-YYYY-MM-DD.jsonl cũ hơn so_ngay (theo giờ Việt Nam), bỏ qua lỗi."""
    directory = Path(thu_muc) if thu_muc is not None else DEFAULT_TRACE_DIR
    if so_ngay < 0 or not directory.is_dir():
        return 0
    clock = dong_ho if dong_ho is not None else vn_now
    cutoff = clock().astimezone(VN_TZ).date() - timedelta(days=so_ngay)
    deleted = 0
    try:
        candidates = list(directory.glob("vet-*.jsonl"))
    except OSError as exc:
        _LOGGER.debug("Không duyệt được thư mục vết (%s)", type(exc).__name__)
        return 0

    for path in candidates:
        try:
            match = _TRACE_FILENAME_RE.fullmatch(path.name)
            if match is None or path.is_symlink() or not path.is_file():
                continue
            file_date = date.fromisoformat(match.group(1))
            if file_date < cutoff:
                path.unlink()
                deleted += 1
        except (OSError, ValueError) as exc:
            _LOGGER.debug("Bỏ qua tệp vết lỗi khi dọn (%s)", type(exc).__name__)
    return deleted


@dataclass(frozen=True)
class _FlushMarker:
    """Dấu hiệu nội bộ để chờ luồng nền xử lý xong các dòng đang xếp hàng."""

    done: Event


class JsonlTraceSink:
    """Ghi một dòng một vết vào vet-YYYY-MM-DD.jsonl qua hàng đợi có trần và luồng nền."""

    def __init__(
        self,
        thu_muc: Path,
        *,
        hang_doi_toi_da: int = DEFAULT_QUEUE_SIZE,
        kich_thuoc_tep_toi_da: int = DEFAULT_MAX_FILE_BYTES,
        dong_ho: Callable[[], datetime] = vn_now,
        auto_start: bool = True,
    ) -> None:
        self._thu_muc = Path(thu_muc)
        self._hang_doi_toi_da = max(1, hang_doi_toi_da)
        self._kich_thuoc_tep_toi_da = max(1, kich_thuoc_tep_toi_da)
        self._dong_ho = dong_ho
        self._queue: queue.Queue[VetChay | _FlushMarker | None] = queue.Queue(
            maxsize=self._hang_doi_toi_da
        )
        self._lock = Lock()
        self._so_vet_bi_bo = 0
        self._so_loi_ghi = 0
        self._da_canh_bao_day = False
        self._da_canh_bao_loi = False
        self._ngay_vuot_tran: set[str] = set()
        self._closed = False
        self._thread: Thread | None = None
        if auto_start:
            self._start_worker()

    def _start_worker(self) -> None:
        """Khởi chạy luồng nền daemon xử lý hàng đợi ghi tệp."""
        self._thread = Thread(
            target=self._worker_loop,
            name="tracer-jsonl-writer",
            daemon=True,
        )
        self._thread.start()

    @property
    def thu_muc(self) -> Path:
        """Thư mục đích chứa các tệp vet-YYYY-MM-DD.jsonl."""
        return self._thu_muc

    @property
    def so_vet_bi_bo(self) -> int:
        """Tổng số vết bị bỏ do hàng đợi đầy hoặc tệp vượt ngưỡng ngày."""
        with self._lock:
            return self._so_vet_bi_bo

    @property
    def so_loi_ghi(self) -> int:
        """Tổng số lần gặp lỗi I/O khi ghi vết."""
        with self._lock:
            return self._so_loi_ghi

    def gui(self, vet: VetChay) -> bool:
        """Đưa vết vào hàng đợi không chặn; đầy hoặc lỗi thì bỏ, tăng bộ đếm và trả False."""
        with self._lock:
            if self._closed:
                return False
        try:
            self._queue.put_nowait(vet)
            return True
        except queue.Full:
            with self._lock:
                self._so_vet_bi_bo += 1
                if not self._da_canh_bao_day:
                    self._da_canh_bao_day = True
                    _LOGGER.warning(
                        "Hàng đợi ghi vết đã đầy (%d); bỏ bớt vết mới để không chặn lượt chạy.",
                        self._hang_doi_toi_da,
                    )
            return False

    def _worker_loop(self) -> None:
        """Đọc tuần tự từ hàng đợi và ghi ra tệp theo ngày."""
        while True:
            item = self._queue.get()
            try:
                if item is None:
                    return
                if isinstance(item, _FlushMarker):
                    item.done.set()
                    continue
                try:
                    self._write_line(_serialize_trace_line(item))
                except Exception as exc:
                    with self._lock:
                        self._so_loi_ghi += 1
                        if not self._da_canh_bao_loi:
                            self._da_canh_bao_loi = True
                            _LOGGER.warning("Không tuần tự hoá được vết (%s)", type(exc).__name__)
            finally:
                self._queue.task_done()

    def _write_line(self, line: str) -> None:
        """Ghi đúng một dòng JSONL vào tệp ngày giờ Việt Nam; quá 200 MB thì dừng ngày đó."""
        try:
            day = self._dong_ho().astimezone(VN_TZ).date().isoformat()
            with self._lock:
                if day in self._ngay_vuot_tran:
                    self._so_vet_bi_bo += 1
                    return

            self._thu_muc.mkdir(parents=True, exist_ok=True)
            path = self._thu_muc / f"vet-{day}.jsonl"
            payload = (line + "\n").encode("utf-8")
            current_size = path.stat().st_size if path.is_file() else 0
            if current_size + len(payload) > self._kich_thuoc_tep_toi_da:
                with self._lock:
                    if day not in self._ngay_vuot_tran:
                        self._ngay_vuot_tran.add(day)
                        _LOGGER.warning(
                            "Tệp vết ngày %s vượt giới hạn %d byte; ngừng ghi trong ngày.",
                            day,
                            self._kich_thuoc_tep_toi_da,
                        )
                    self._so_vet_bi_bo += 1
                return

            with path.open("ab") as handle:
                handle.write(payload)
        except Exception as exc:
            with self._lock:
                self._so_loi_ghi += 1
                if not self._da_canh_bao_loi:
                    self._da_canh_bao_loi = True
                    _LOGGER.warning("Không ghi được tệp vết JSONL (%s)", type(exc).__name__)

    def flush(self, timeout: float = 2.0) -> bool:
        """Chờ luồng nền ghi xong mọi mục đã xếp trước thời điểm gọi."""
        if self._thread is None or not self._thread.is_alive():
            return self._queue.empty()
        marker = _FlushMarker(done=Event())
        try:
            self._queue.put(marker, timeout=timeout)
        except queue.Full:
            return False
        return marker.done.wait(timeout=timeout)

    def close(self, timeout: float = 2.0) -> None:
        """Xả hàng đợi và dừng luồng nền gọn gàng."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        if self._thread is None or not self._thread.is_alive():
            return
        try:
            self._queue.put(None, timeout=timeout)
        except queue.Full:
            _LOGGER.debug("Không gửi được tín hiệu dừng khi hàng đợi vết đang đầy.")
            return
        self._thread.join(timeout=timeout)
