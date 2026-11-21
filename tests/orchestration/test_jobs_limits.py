"""Kiểm thử giới hạn hàng đợi và quy tắc khởi động lại của AiJobManager (T88)."""

import threading
import time

import pytest

from app.orchestration.jobs import AiJobManager, AiQueueFullError


def _wait_until_status(
    manager: AiJobManager,
    ca_id: str,
    expected: tuple[str, ...],
    timeout: float = 2.0,
) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = manager.get(ca_id)
        if state is not None and state.trang_thai in expected:
            return state.trang_thai
        time.sleep(0.005)
    raise AssertionError(f"Quá thời gian chờ ca {ca_id} đạt trạng thái {expected}")


def test_start_restart_ignored_50_times_while_running() -> None:
    """Test 1: gọi start(restart=True) 50 lần khi đang chạy chỉ chạy hàm giả đúng 1 lần."""
    manager = AiJobManager(max_workers=2)
    entered = threading.Event()
    release = threading.Event()
    calls = 0
    count_lock = threading.Lock()
    try:

        def job() -> str:
            nonlocal calls
            with count_lock:
                calls += 1
            entered.set()
            assert release.wait(timeout=2.0)
            return "xong-1"

        first = manager.start("DEMO-02", job, restart=True)
        assert first.trang_thai == "dang_chay"
        assert entered.wait(timeout=2.0)

        for _ in range(50):
            current = manager.start("DEMO-02", job, restart=True)
            assert current.trang_thai == "dang_chay"

        assert calls == 1
        release.set()
        assert _wait_until_status(manager, "DEMO-02", ("xong", "loi")) == "xong"
        assert calls == 1
    finally:
        release.set()
        manager.shutdown()


def test_start_restart_runs_again_after_done_or_error() -> None:
    """Test 2: sau khi xong hoặc lỗi, restart=True chạy lại lần 2."""
    manager = AiJobManager(max_workers=2)
    calls = 0
    count_lock = threading.Lock()
    try:

        def ok_job() -> str:
            nonlocal calls
            with count_lock:
                calls += 1
            return f"lan-{calls}"

        first = manager.start("DEMO-02", ok_job)
        assert first.trang_thai == "dang_chay"
        assert _wait_until_status(manager, "DEMO-02", ("xong",)) == "xong"
        assert calls == 1

        second = manager.start("DEMO-02", ok_job, restart=True)
        assert second.trang_thai == "dang_chay"
        assert _wait_until_status(manager, "DEMO-02", ("xong",)) == "xong"
        assert calls == 2
        state2 = manager.get("DEMO-02")
        assert state2 is not None
        assert state2.ket_qua == "lan-2"

        def failing_job() -> str:
            raise ValueError("lỗi giả lập")

        manager.start("DEMO-03", failing_job)
        assert _wait_until_status(manager, "DEMO-03", ("loi",)) == "loi"
        recovered = manager.start("DEMO-03", ok_job, restart=True)
        assert recovered.trang_thai == "dang_chay"
        assert _wait_until_status(manager, "DEMO-03", ("xong",)) == "xong"
        assert calls == 3
    finally:
        manager.shutdown()


def test_queue_limit_raises_ai_queue_full_error_on_seventh_case() -> None:
    """Test 3: 7 ca khác nhau với max_pending=6 -> ca thứ 7 ném AiQueueFullError."""
    manager = AiJobManager(max_workers=2, max_pending=6)
    release = threading.Event()
    started_two = threading.Event()
    running = 0
    count_lock = threading.Lock()
    try:

        def slow_job() -> str:
            nonlocal running
            with count_lock:
                running += 1
                if running >= 2:
                    started_two.set()
            assert release.wait(timeout=2.0)
            return "ok"

        for idx in range(1, 7):
            state = manager.start(f"CA-{idx}", slow_job)
            assert state.trang_thai == "dang_chay"

        assert started_two.wait(timeout=2.0)
        assert manager.pending_count() == 6

        # Ca đang chạy gọi restart=True vẫn giữ nguyên, không bị chặn bởi trần hàng đợi.
        same = manager.start("CA-1", slow_job, restart=True)
        assert same.trang_thai == "dang_chay"

        with pytest.raises(AiQueueFullError):
            manager.start("CA-7", slow_job)

        assert manager.get("CA-7") is None

        release.set()
        for idx in range(1, 7):
            assert _wait_until_status(manager, f"CA-{idx}", ("xong",)) == "xong"
        assert manager.pending_count() == 0

        seventh = manager.start("CA-7", lambda: "ok-7")
        assert seventh.trang_thai == "dang_chay"
        assert _wait_until_status(manager, "CA-7", ("xong",)) == "xong"
    finally:
        release.set()
        manager.shutdown()
