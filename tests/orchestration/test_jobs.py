"""Kiểm thử AiJobManager: chống chạy trùng đồng thời, chạy lại và bắt lỗi."""

import threading
import time

from app.orchestration.jobs import AiJobManager


def _wait_until_done(manager: AiJobManager, ca_id: str, timeout: float = 2.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = manager.get(ca_id)
        if state is not None and state.trang_thai != "dang_chay":
            return state.trang_thai
        time.sleep(0.01)
    raise AssertionError("Quá thời gian chờ tác vụ nền")


def test_job_manager_dedupes_concurrent_starts_and_supports_restart() -> None:
    manager = AiJobManager(max_workers=2)
    try:
        release = threading.Event()
        entered = threading.Event()
        calls = 0
        count_lock = threading.Lock()

        def job() -> dict[str, object]:
            nonlocal calls
            with count_lock:
                calls += 1
            entered.set()
            release.wait(timeout=2.0)
            return {"lan": calls}

        results = []
        barrier = threading.Barrier(2)

        def starter() -> None:
            barrier.wait(timeout=2.0)
            results.append(manager.start("DEMO-02", job))

        t1 = threading.Thread(target=starter)
        t2 = threading.Thread(target=starter)
        t1.start()
        t2.start()
        t1.join(timeout=2.0)
        t2.join(timeout=2.0)

        assert entered.wait(timeout=2.0)
        assert all(item.trang_thai == "dang_chay" for item in results)
        release.set()

        assert _wait_until_done(manager, "DEMO-02") == "xong"
        assert calls == 1

        # Gọi lại khi đã xong mà restart=False không kích hoạt lần chạy mới.
        existing = manager.start("DEMO-02", job, restart=False)
        assert existing.trang_thai == "xong"
        assert calls == 1

        # restart=True chạy lại lần mới.
        restarted = manager.start("DEMO-02", job, restart=True)
        assert restarted.trang_thai == "dang_chay"
        assert _wait_until_done(manager, "DEMO-02") == "xong"
        assert calls == 2
    finally:
        manager.shutdown()


def test_job_manager_restart_ignores_stale_previous_run() -> None:
    manager = AiJobManager(max_workers=2)
    try:
        unblock_first = threading.Event()
        first_started = threading.Event()
        first_finished = threading.Event()

        def slow_first() -> str:
            first_started.set()
            try:
                unblock_first.wait(timeout=2.0)
                return "cu"
            finally:
                first_finished.set()

        manager.start("DEMO-02", slow_first)
        assert first_started.wait(timeout=2.0)

        manager.start("DEMO-02", lambda: "moi", restart=True)
        assert _wait_until_done(manager, "DEMO-02") == "xong"
        assert manager.get("DEMO-02").ket_qua == "moi"

        unblock_first.set()
        assert first_finished.wait(timeout=2.0)
        # Chờ nhẹ để đảm bảo nhánh cập nhật của job cũ đã chạy qua.
        time.sleep(0.02)
        assert manager.get("DEMO-02").ket_qua == "moi"
    finally:
        manager.shutdown()


def test_job_manager_records_exception_as_loi_and_get_missing_returns_none() -> None:
    manager = AiJobManager(max_workers=2)
    try:
        assert manager.get("KHONG-CO") is None

        def failing() -> None:
            raise ValueError("nội dung bí mật")

        manager.start("DEMO-02", failing)
        assert _wait_until_done(manager, "DEMO-02") == "loi"
        state = manager.get("DEMO-02")
        assert state is not None
        assert state.ket_qua is None
        assert state.canh_bao == ["Bước AI gặp lỗi không mong muốn (ValueError)"]
        assert "bí mật" not in " ".join(state.canh_bao)
    finally:
        manager.shutdown()
