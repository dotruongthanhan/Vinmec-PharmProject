"""Kiểm giới hạn đồng thời và vòng đời kết nối chỉ đọc."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest.mock import MagicMock, Mock

import psycopg
import pytest
from psycopg.pq import TransactionStatus

from app.db import read_pool


def idle_connection() -> MagicMock:
    connection = MagicMock()
    connection.closed = False
    connection.info.transaction_status = TransactionStatus.IDLE
    return connection


def test_pool_reuses_idle_connection_and_discards_query_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = idle_connection(), idle_connection()
    connect = Mock(side_effect=[first, second])
    monkeypatch.setattr(psycopg, "connect", connect)
    pool = read_pool.ReadPool()
    with pool.connection("local-mock") as connection:
        assert connection is first
    with pytest.raises(psycopg.errors.QueryCanceled), pool.connection("local-mock") as connection:
        assert connection is first
        raise psycopg.errors.QueryCanceled()
    assert first.transaction.call_count == 2
    assert first.execute.call_count == 2
    assert connect.call_args.kwargs["prepare_threshold"] is None
    first.close.assert_called_once()
    with pool.connection("local-mock") as connection:
        assert connection is second
    assert connect.call_count == 2
    pool.close()
    second.close.assert_called_once()


@pytest.mark.parametrize("fail_on_begin", [False, True])
def test_pool_replaces_idle_connection_when_transaction_setup_fails(
    monkeypatch: pytest.MonkeyPatch, fail_on_begin: bool
) -> None:
    idle, replacement = idle_connection(), idle_connection()
    connect = Mock(side_effect=[idle, replacement])
    monkeypatch.setattr(psycopg, "connect", connect)
    pool = read_pool.ReadPool()
    with pool.connection("local-mock") as connection:
        assert connection is idle

    failure = psycopg.OperationalError("Kết nối giả lập đã bị ngắt.")
    if fail_on_begin:
        idle.transaction.return_value.__enter__.side_effect = failure
    else:
        idle.execute.side_effect = failure

    with pool.connection("local-mock") as connection:
        assert connection is replacement
        idle.close.assert_called_once()
        replacement.execute.assert_called_once_with("SET LOCAL statement_timeout = 8000")
    assert connect.call_count == 2
    with pool.connection("local-mock") as connection:
        assert connection is replacement
    assert connect.call_count == 2
    pool.close()


def test_pool_does_not_retry_if_replacement_setup_also_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    idle, replacement = idle_connection(), idle_connection()
    connect = Mock(side_effect=[idle, replacement])
    monkeypatch.setattr(psycopg, "connect", connect)
    pool = read_pool.ReadPool()
    with pool.connection("local-mock"):
        pass

    idle.execute.side_effect = psycopg.OperationalError("Kết nối rảnh lỗi.")
    replacement.execute.side_effect = psycopg.OperationalError("Kết nối mới lỗi.")
    with (
        pytest.raises(psycopg.OperationalError, match="Kết nối mới lỗi"),
        pool.connection("local-mock"),
    ):
        pytest.fail("Không được cấp kết nối khi SET LOCAL thất bại.")
    assert connect.call_count == 2
    idle.close.assert_called_once()
    replacement.close.assert_called_once()


def test_pool_does_not_retry_operational_error_in_caller_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    idle = idle_connection()
    connect = Mock(return_value=idle)
    monkeypatch.setattr(psycopg, "connect", connect)
    pool = read_pool.ReadPool()
    with pool.connection("local-mock"):
        pass

    failure = psycopg.OperationalError("Truy vấn của bên gọi lỗi.")
    with pytest.raises(psycopg.OperationalError) as caught, pool.connection("local-mock"):
        raise failure
    assert caught.value is failure
    connect.assert_called_once()
    idle.close.assert_called_once()


def test_pool_limits_concurrent_checkouts_and_closes_on_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connections = [idle_connection() for _ in range(3)]
    connect = Mock(side_effect=connections)
    monkeypatch.setattr(psycopg, "connect", connect)
    monkeypatch.setattr(read_pool, "_WAIT_SECONDS", 0)
    pool = read_pool.ReadPool()
    ready = Barrier(4)
    release = Event()

    def read() -> None:
        with pool.connection("local-mock"):
            ready.wait(timeout=5)
            assert release.wait(timeout=5)

    with ThreadPoolExecutor(max_workers=3) as workers:
        pending = [workers.submit(read) for _ in connections]
        try:
            ready.wait(timeout=5)
            with pytest.raises(psycopg.OperationalError, match="Hết thời gian chờ"):
                with pool.connection("local-mock"):
                    pytest.fail("Không được cấp kết nối thứ tư.")
            assert connect.call_count == 3
            pool.close()
            for connection in connections:
                connection.close.assert_not_called()
        finally:
            release.set()
        for task in pending:
            task.result(timeout=5)
    for connection in connections:
        connection.close.assert_called_once()
