"""Kiểm tra cầu dao kết nối đọc bằng đồng hồ và DB giả."""

import logging
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import psycopg
import pytest

from app.config.settings import ReadDatabaseSettings
from app.db import read_pool


def test_connection_failure_opens_and_closes_breaker(monkeypatch, caplog):
    now = [100.0]
    monkeypatch.setattr(read_pool.time, "monotonic", lambda: now[0])
    settings = Mock(db=ReadDatabaseSettings(thoi_han_ket_noi_giay=5, cau_dao_giay=60))
    monkeypatch.setattr(read_pool, "load_settings", lambda: settings)
    connect = Mock(side_effect=[psycopg.OperationalError("giả lập"), Mock()])
    monkeypatch.setattr(psycopg, "connect", connect)
    pool = read_pool.ReadPool()
    with caplog.at_level(logging.WARNING):
        with pytest.raises(psycopg.OperationalError):
            pool._connect("mock")
        with ThreadPoolExecutor(max_workers=3) as workers:
            futures = [workers.submit(pool._connect, "mock") for _ in range(3)]
            for future in futures:
                with pytest.raises(psycopg.OperationalError):
                    future.result()
        assert connect.call_count == 1
        assert connect.call_args.kwargs["connect_timeout"] == 5
        now[0] += 60
        pool._connect("mock")
    assert connect.call_count == 2
    assert sum("đã bật" in record.message for record in caplog.records) == 1
    assert sum("đã đóng" in record.message for record in caplog.records) == 1


def test_query_failure_does_not_open_breaker(monkeypatch):
    connection = Mock()
    connection.closed = False
    connection.transaction.return_value.__enter__ = Mock()
    connection.transaction.return_value.__exit__ = Mock(return_value=False)
    connect = Mock(return_value=connection)
    monkeypatch.setattr(psycopg, "connect", connect)
    pool = read_pool.ReadPool()
    with pytest.raises(psycopg.OperationalError), pool.connection("mock"):
        raise psycopg.OperationalError("lỗi truy vấn giả")
    with pool.connection("mock"):
        pass
    assert connect.call_count == 2


def test_open_breaker_blocks_idle_connection(monkeypatch):
    pool = read_pool.ReadPool()
    pool._url = "mock"
    pool._idle.append(Mock())
    pool._unavailable_url = "mock"
    pool._retry_at = 200.0
    monkeypatch.setattr(read_pool.time, "monotonic", lambda: 100.0)
    with pytest.raises(psycopg.OperationalError), pool.connection("mock"):
        pytest.fail("Không được dùng kết nối khi cầu dao đang bật.")


def test_read_config_defaults_and_yaml():
    from app.config.settings import load_settings

    assert ReadDatabaseSettings().thoi_han_ket_noi_giay == 3
    assert load_settings().db.cau_dao_giay == 60
    assert load_settings().db.thoi_han_ket_noi_giay == 3
