"""Dùng chung tối đa ba kết nối đọc PostgreSQL trong mỗi tiến trình."""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from threading import BoundedSemaphore, Lock
from typing import Any

import psycopg
from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from app.config.settings import load_settings

_OPTIONS = "-c default_transaction_read_only=on -c statement_timeout=8000"
_WAIT_SECONDS = 10
_LOGGER = logging.getLogger(__name__)


class ReadPool:
    """Cấp riêng một kết nối cho mỗi giao dịch và chỉ giữ kết nối ở trạng thái rảnh."""

    def __init__(self) -> None:
        self._slots = BoundedSemaphore(3)
        self._lock = Lock()
        self._idle: list[psycopg.Connection[dict[str, Any]]] = []
        self._url: str | None = None
        self._generation = 0
        self._connect_lock = Lock()
        self._unavailable_url: str | None = None
        self._retry_at = 0.0

    def _connect(self, url: str) -> psycopg.Connection[dict[str, Any]]:
        """Chỉ thử lại một kết nối sau thời gian ngắt."""
        with self._connect_lock:
            if self._unavailable_url == url and time.monotonic() < self._retry_at:
                raise psycopg.OperationalError("Kết nối đọc DB tạm thời không sẵn sàng.")
            settings = load_settings().db
            try:
                connection = psycopg.connect(
                    url,
                    options=_OPTIONS,
                    row_factory=dict_row,
                    connect_timeout=settings.thoi_han_ket_noi_giay,
                    prepare_threshold=None,
                )
            except (psycopg.OperationalError, OSError):
                if self._unavailable_url != url:
                    _LOGGER.warning("Cầu dao kết nối đọc DB đã bật.")
                self._unavailable_url = url
                self._retry_at = time.monotonic() + settings.cau_dao_giay
                raise
            if self._unavailable_url == url:
                _LOGGER.warning("Cầu dao kết nối đọc DB đã đóng.")
                self._unavailable_url = None
                self._retry_at = 0.0
            return connection

    def close(self) -> None:
        """Đóng kết nối rảnh; kết nối đang dùng sẽ đóng khi trả về."""
        with self._lock:
            self._close_idle()

    def _close_idle(self) -> None:
        self._generation += 1
        for connection in self._idle:
            connection.close()
        self._idle.clear()
        self._url = None

    @contextmanager
    def connection(self, url: str) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        """Mở một ảnh chụp chỉ đọc, kể cả khi pooler bỏ qua tùy chọn kết nối."""
        with self._connect_lock:
            retry_connection = self._unavailable_url == url
            if retry_connection and time.monotonic() < self._retry_at:
                raise psycopg.OperationalError("Kết nối đọc DB tạm thời không sẵn sàng.")
        if not self._slots.acquire(timeout=_WAIT_SECONDS):
            raise psycopg.OperationalError("Hết thời gian chờ kết nối đọc.")
        connection = None
        reusable = False
        try:
            with self._lock:
                if url != self._url:
                    self._close_idle()
                    self._url = url
                generation = self._generation
                if self._idle and not retry_connection:
                    connection = self._idle.pop()
            while True:
                if connection is None or connection.closed:
                    connection = self._connect(url)
                    connection.isolation_level = IsolationLevel.REPEATABLE_READ
                    connection.read_only = True
                    retry_setup = False
                else:
                    retry_setup = True
                try:
                    with connection.transaction():
                        connection.execute("SET LOCAL statement_timeout = 8000")
                        retry_setup = False
                        yield connection
                except psycopg.OperationalError:
                    if not retry_setup:
                        raise
                    connection.close()
                    connection = None
                else:
                    break
            reusable = not connection.closed and connection.info.transaction_status == (
                TransactionStatus.IDLE
            )
        finally:
            try:
                if connection is not None:
                    with self._lock:
                        if reusable and generation == self._generation:
                            self._idle.append(connection)
                        else:
                            connection.close()
            finally:
                self._slots.release()


read_pool = ReadPool()
