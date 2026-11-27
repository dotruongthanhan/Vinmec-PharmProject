"""Ghi vết PostgreSQL theo lô trên luồng nền riêng."""

from __future__ import annotations

import json
import logging
import queue
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from threading import Event, Lock, Thread
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.config.settings import get_secret, load_settings
from app.core.errors import ConfigError
from app.tracing.models import MAX_ATTRIBUTES_BYTES, VetChay
from app.tracing.sink import vn_now

_LOGGER = logging.getLogger(__name__)
_INSERT_TRACE = """
INSERT INTO nghiep_vu.vet_chay (ma_vet, bat_dau, ket_thuc, thoi_gian_ms, loai, engine,
 nguoi_dung_id, vai_tro, phien_id, ca_bam, phien_ban, trang_thai_cuoi, tong_token_vao,
 tong_token_ra, chi_phi_uoc_tinh, so_tool, so_bi_chan, ma_loi, muc_noi_dung, vet_bi_cat,
 so_khoa_la_bi_bo) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
 %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (ma_vet) DO NOTHING
"""
_INSERT_SPAN = """
INSERT INTO nghiep_vu.vet_buoc (ma_vet, ma_buoc, ma_buoc_cha, loai, ten, bat_dau,
 thoi_gian_ms, trang_thai, thuoc_tinh, noi_dung) VALUES (%s, %s, %s, %s, %s,
 %s, %s, %s, %s, %s) ON CONFLICT (ma_vet, ma_buoc) DO NOTHING
"""
_DELETE = """
DELETE FROM nghiep_vu.vet_chay WHERE ma_vet IN
 (SELECT ma_vet FROM nghiep_vu.vet_chay WHERE bat_dau < %s ORDER BY bat_dau LIMIT 5000)
"""
_TIMEOUT = "SET LOCAL statement_timeout = 5000"


def don_vet_db_qua_han(so_ngay: int, *, dong_ho: Callable[[], datetime] | None = None) -> int:
    """Xoá vết cũ theo lô tối đa 5000, dùng kết nối ghi riêng."""
    if so_ngay < 0:
        return 0
    settings = load_settings()
    url = get_secret(settings.database.url_env)
    return _don_vet_db(so_ngay, url, settings.db.thoi_han_ket_noi_giay, dong_ho=dong_ho)


def _don_vet_db(
    so_ngay: int, url: str, connect_timeout: int, *, dong_ho: Callable[[], datetime] | None = None
) -> int:
    """Dọn bằng cấu hình kết nối của tracer đang chạy."""
    cutoff = (dong_ho or vn_now)() - timedelta(days=so_ngay)
    total = 0
    with psycopg.connect(url, connect_timeout=connect_timeout) as conn:
        while True:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(_TIMEOUT)
                    cur.execute(_DELETE, (cutoff,))
                    count = cur.rowcount
            total += count
            if count == 0:
                return total


class PostgresTraceSink:
    """Đích ghi không chặn, bỏ lô lỗi và thử lại sau thời gian cầu dao."""

    def __init__(
        self,
        *,
        url_env: str = "DATABASE_URL",
        url: str | None = None,
        hang_doi_toi_da: int = 1000,
        thoi_han_ket_noi_giay: int = 3,
        cau_dao_giay: int = 60,
        connect: Callable[..., Any] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        auto_start: bool = True,
    ) -> None:
        try:
            self._url = (url if url is not None else get_secret(url_env)).strip()
        except ConfigError:
            self._url = ""
        if not self._url:
            _LOGGER.warning("Thiếu URL DB; tắt đích ghi vết DB.")
        self._connect = connect or psycopg.connect
        self._connect_timeout = thoi_han_ket_noi_giay
        self._breaker_seconds = cau_dao_giay
        self._clock = monotonic
        self._retry_at = 0.0
        self._queue: queue.Queue[VetChay] = queue.Queue(maxsize=max(1, hang_doi_toi_da))
        self._lock = Lock()
        self._dropped = 0
        self._warnings: set[type[Exception]] = set()
        self._stop = Event()
        self._flush_requested = Event()
        self._stop_deadline: float | None = None
        self._closed = False
        self._thread: Thread | None = None
        if auto_start and self._url:
            self._thread = Thread(target=self._worker, name="tracer-db-writer", daemon=True)
            self._thread.start()

    @property
    def so_vet_bo_db(self) -> int:
        with self._lock:
            return self._dropped

    def don_qua_han(self, so_ngay: int, *, dong_ho: Callable[[], datetime]) -> int:
        """Dọn bằng cùng URL với đích ghi; bỏ qua nếu đích đã tắt."""
        if not self._url:
            return 0
        return _don_vet_db(so_ngay, self._url, self._connect_timeout, dong_ho=dong_ho)

    @property
    def so_vet_bi_bo(self) -> int:
        return self.so_vet_bo_db

    def _drop(self, count: int) -> None:
        with self._lock:
            self._dropped += count

    def gui(self, vet: VetChay) -> bool:
        with self._lock:
            if self._closed or not self._url:
                return False
            try:
                self._queue.put_nowait(vet)
                return True
            except queue.Full:
                self._dropped += 1
                return False

    def _write_batch(self, batch: list[VetChay]) -> None:
        if self._clock() < self._retry_at:
            self._drop(len(batch))
            return
        try:
            traces = []
            spans = []
            for v in batch:
                traces.append(
                    (
                        v.ma_vet,
                        v.bat_dau,
                        v.ket_thuc,
                        v.thoi_gian_ms,
                        v.loai,
                        v.engine,
                        v.nguoi_dung_id,
                        v.vai_tro,
                        v.phien_id,
                        v.ca_bam,
                        Jsonb(v.phien_ban),
                        v.trang_thai_cuoi,
                        v.tong_token_vao,
                        v.tong_token_ra,
                        v.chi_phi_uoc_tinh,
                        v.so_tool,
                        v.so_bi_chan,
                        v.ma_loi,
                        v.muc_noi_dung,
                        v.vet_bi_cat,
                        v.so_khoa_la_bi_bo,
                    )
                )
                for s in v.cac_buoc:
                    attrs = json.dumps(s.thuoc_tinh, ensure_ascii=False).encode("utf-8")
                    if len(attrs) > MAX_ATTRIBUTES_BYTES:
                        raise ValueError("Thuộc tính span vượt giới hạn")
                    content = (
                        None
                        if v.muc_noi_dung == "sieu_du_lieu" or s.noi_dung is None
                        else json.dumps(s.noi_dung, ensure_ascii=False)
                    )
                    spans.append(
                        (
                            v.ma_vet,
                            s.ma_buoc,
                            s.ma_buoc_cha,
                            s.loai,
                            s.ten,
                            s.bat_dau,
                            s.thoi_gian_ms,
                            s.trang_thai,
                            Jsonb(s.thuoc_tinh),
                            content,
                        )
                    )
            with self._connect(self._url, connect_timeout=self._connect_timeout) as conn:
                with conn.cursor() as cur:
                    cur.execute(_TIMEOUT)
                    cur.executemany(_INSERT_TRACE, traces)
                    if spans:
                        cur.executemany(_INSERT_SPAN, spans)
            self._retry_at = 0.0
        except Exception as exc:
            self._drop(len(batch))
            self._retry_at = self._clock() + self._breaker_seconds
            if type(exc) not in self._warnings:
                self._warnings.add(type(exc))
                _LOGGER.warning("Không ghi được lô vết DB (%s).", type(exc).__name__)

    def _worker(self) -> None:
        while not self._stop.is_set() or not self._queue.empty():
            if self._stop_deadline is not None and time.monotonic() >= self._stop_deadline:
                while True:
                    try:
                        self._queue.get_nowait()
                    except queue.Empty:
                        return
                    self._drop(1)
                    self._queue.task_done()
            try:
                first = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            batch = [first]
            deadline = time.monotonic() + 2
            while len(batch) < 50:
                if self._stop.is_set() or self._flush_requested.is_set():
                    wait = 0
                else:
                    wait = min(0.1, max(0.0, deadline - time.monotonic()))
                try:
                    batch.append(self._queue.get(timeout=wait))
                except queue.Empty:
                    if (
                        self._stop.is_set()
                        or self._flush_requested.is_set()
                        or time.monotonic() >= deadline
                    ):
                        break
            self._write_batch(batch)
            for _ in batch:
                self._queue.task_done()
            if self._queue.empty():
                self._flush_requested.clear()

    def flush(self, timeout: float = 2.0) -> bool:
        self._flush_requested.set()
        deadline = time.monotonic() + timeout
        while self._queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.01)
        return self._queue.unfinished_tasks == 0

    def close(self, timeout: float = 3.0) -> None:
        with self._lock:
            self._closed = True
            self._stop_deadline = time.monotonic() + max(0.0, min(timeout, 3.0))
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=min(timeout, 3.0))
