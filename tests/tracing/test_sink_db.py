from datetime import UTC, datetime
from uuid import uuid4

from app.tracing.models import VetChay
from app.tracing.sink_db import PostgresTraceSink


def test_batch_uses_parameters_and_commits() -> None:
    calls = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            calls.append((sql, params))

        def executemany(self, sql, params):
            calls.append((sql, list(params)))

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return Cursor()

    sink = PostgresTraceSink(url="fake", connect=lambda *a, **kw: Connection(), auto_start=False)
    now = datetime.now(UTC)
    record = VetChay(
        ma_vet=str(uuid4()),
        bat_dau=now,
        ket_thuc=now,
        thoi_gian_ms=1,
        loai="hoi_dap",
        engine="canary-engine",
    )
    sink._write_batch([record])
    assert len(calls) == 2
    assert "ON CONFLICT (ma_vet) DO NOTHING" in calls[1][0]
    assert "canary-engine" not in calls[1][0]
    assert calls[1][1][0][5] == "canary-engine"


def test_batches_and_metadata_content() -> None:
    from threading import Thread

    from app.tracing.models import SpanBanGhi

    transactions = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            pass

        def executemany(self, sql, params):
            transactions[-1].append((sql, list(params)))

    class Connection:
        def __enter__(self):
            transactions.append([])
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return Cursor()

    now = datetime.now(UTC)
    sink = PostgresTraceSink(url="fake", connect=lambda *a, **kw: Connection(), auto_start=False)
    for _ in range(120):
        ident = str(uuid4())
        span = SpanBanGhi(
            ma_vet=ident,
            ma_buoc="span",
            loai="tool",
            ten="tool",
            bat_dau=now,
            thoi_gian_ms=0,
            noi_dung={"text": "canary"},
        )
        record = VetChay(
            ma_vet=ident,
            bat_dau=now,
            ket_thuc=now,
            thoi_gian_ms=1,
            loai="hoi_dap",
            engine="agentic",
            cac_buoc=[span],
        )
        assert sink.gui(record)
    sink._stop.set()
    thread = Thread(target=sink._worker)
    thread.start()
    thread.join(3)
    assert not thread.is_alive()
    assert [len(tx[0][1]) for tx in transactions] == [50, 50, 20]
    assert all(row[-1] is None for tx in transactions for row in tx[1][1])
    assert all("canary" not in sql for tx in transactions for sql, _ in tx)


def test_breaker_and_full_queue() -> None:
    import psycopg

    attempts = []
    now = datetime.now(UTC)
    record = VetChay(
        ma_vet=str(uuid4()),
        bat_dau=now,
        ket_thuc=now,
        thoi_gian_ms=0,
        loai="hoi_dap",
        engine="agentic",
    )

    def fail(*args, **kwargs):
        attempts.append(1)
        raise psycopg.OperationalError("secret connection string")

    sink = PostgresTraceSink(
        url="fake", connect=fail, auto_start=False, hang_doi_toi_da=1, monotonic=lambda: 100.0
    )
    assert sink.gui(record)
    assert not sink.gui(record)
    sink._write_batch([record])
    sink._write_batch([record])
    assert len(attempts) == 1
    assert sink.so_vet_bo_db == 3


def test_invalid_destination() -> None:
    import pytest
    from pydantic import ValidationError

    from app.config.settings import TracerSettings

    with pytest.raises(ValidationError):
        TracerSettings(dich=["xyz"])


def test_cleanup_batches(monkeypatch) -> None:
    from datetime import timedelta

    from app.tracing import sink_db

    now = datetime(2026, 11, 27, tzinfo=UTC)
    calls = []
    counts = iter([5000, 10, 0])

    class Cursor:
        rowcount = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            if params:
                calls.append((sql, params))
                self.rowcount = next(counts)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def transaction(self):
            return self

        def cursor(self):
            return Cursor()

    monkeypatch.setattr(sink_db, "get_secret", lambda name: "fake")
    monkeypatch.setattr(sink_db.psycopg, "connect", lambda *args, **kwargs: Connection())
    assert sink_db.don_vet_db_qua_han(30, dong_ho=lambda: now) == 5010
    assert len(calls) == 3
    assert all(params == (now - timedelta(days=30),) for _, params in calls)
    assert all("LIMIT 5000" in sql for sql, _ in calls)


def test_canary_reaches_no_database_parameters(tmp_path, monkeypatch) -> None:
    import json
    import time

    from app.agent.tools.base import ToolContext
    from app.config.settings import TracerSettings
    from app.core.types import ChatMessage
    from app.tracing import Tracer, goi_llm_co_vet
    from tests.agent.test_gateway import _setup
    from tests.tracing.test_tracing import _FakeLLM

    captured = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            captured.append((sql, params))

        def executemany(self, sql, params):
            captured.append((sql, list(params)))

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return Cursor()

    db_sink = PostgresTraceSink(url="fake", connect=lambda *a, **kw: Connection(), auto_start=False)
    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path), muc_noi_dung="noi_dung_da_che"))
    tracer._sinks.append(db_sink)
    question = "Giả Lập Sáu Ba HN998877 0912345678 012345678901 sk-test-canary-123"
    _, gateway = _setup()
    ctx = ToolContext(
        vai_tro="duoc_si_ls", che_do="ca", han_chot=time.monotonic() + 30, cau_hoi_goc=question
    )
    with tracer.bat_dau_vet("hoi_dap", "agentic"):
        goi_llm_co_vet(_FakeLLM(), [ChatMessage(role="user", content=question)], {})
        gateway.goi("cong_cu_thu", {"cau_truy_van": question}, ctx)
    record = db_sink._queue.get_nowait()
    db_sink._write_batch([record])
    db_sink._queue.task_done()
    assert len(captured) == 3
    sql = " ".join(command for command, _ in captured)
    raw = json.dumps(captured, default=lambda x: getattr(x, "obj", str(x)), ensure_ascii=False)
    for canary in (
        "Giả Lập Sáu Ba",
        "HN998877",
        "0912345678",
        "012345678901",
        "sk-test-canary-123",
    ):
        assert canary not in raw
        assert canary not in sql
    assert len(captured[2][1]) == len(record.cac_buoc)
    tracer.close()


def test_db_full_does_not_stop_jsonl(tmp_path) -> None:
    from app.config.settings import TracerSettings
    from app.tracing import Tracer

    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path)))
    db = PostgresTraceSink(url="fake", hang_doi_toi_da=1, auto_start=False)
    tracer._sinks.append(db)
    for _ in range(2):
        with tracer.bat_dau_vet("hoi_dap", "co_dinh"):
            pass
    assert db.so_vet_bo_db == 1
    assert tracer.sink.flush()
    assert len(next(tmp_path.glob("vet-*.jsonl")).read_text(encoding="utf-8").splitlines()) == 2
    tracer.close()


def test_missing_url_does_not_start_worker(monkeypatch) -> None:
    from app.core.errors import ConfigError
    from app.tracing import sink_db

    def missing(name):
        raise ConfigError(name)

    monkeypatch.setattr(sink_db, "get_secret", missing)
    sink = PostgresTraceSink()
    assert sink._thread is None
    sink.close()
    blank_sink = PostgresTraceSink(url="  ")
    assert blank_sink._thread is None
    blank_sink.close()


def test_sql_definitions_and_grants() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    sql = (root / "db/vet.sql").read_text(encoding="utf-8")
    roles = (root / "db/roles.sql").read_text(encoding="utf-8")
    for statement in sql.split(";"):
        if statement.strip():
            assert "IF NOT EXISTS" in statement
    for line in roles.splitlines():
        if "GRANT" in line and ("vet_chay" in line or "vet_buoc" in line):
            assert "UPDATE" not in line


def test_timeout_does_not_delay_trace_requests() -> None:
    import time
    from pathlib import Path
    from threading import Event

    import psycopg

    from app.config.settings import TracerSettings
    from app.domain.loader import load_case
    from app.providers.fakes import FakeLLM
    from app.tracing import Tracer
    from tests.agent.test_asker import _make_asker

    connected = Event()

    def slow_connection(*args, **kwargs):
        connected.set()
        time.sleep(1)
        raise psycopg.OperationalError("timeout")

    sink = PostgresTraceSink(url="fake", connect=slow_connection, hang_doi_toi_da=100)
    tracer = Tracer(TracerSettings(dich=[], bat=True))
    tracer._sinks.append(sink)
    disabled = Tracer(TracerSettings(bat=False))
    response = {"hanh_dong": "tra_loi", "tra_loi": {"pham_vi": "trong", "tra_loi": "ok"}}
    asker = _make_asker(FakeLLM([response] * 100))
    case = load_case(Path(__file__).resolve().parents[2] / "data/mock/demo/DEMO-02.json")

    def samples(target):
        timings = []
        for _ in range(50):
            start = time.perf_counter()
            with target.bat_dau_vet("hoi_dap", "agentic"):
                asker.ask(case, "Có nguồn không?")
            timings.append((time.perf_counter() - start) * 1000)
        return sorted(timings)[47]

    baseline = samples(disabled)
    with tracer.bat_dau_vet("hoi_dap", "agentic"):
        pass
    sink._flush_requested.set()
    assert connected.wait(3)
    active = samples(tracer)
    tracer.close()
    disabled.close()
    assert active - baseline < 20


def test_cleanup_uses_one_scheduler(tmp_path, monkeypatch) -> None:
    from threading import Event

    from app.config.settings import TracerSettings
    from app.tracing import context

    called = Event()
    paths = []

    def cleanup(days, *, thu_muc, dong_ho):
        paths.append(thu_muc)
        if len(paths) >= 2:
            called.set()
        return 0

    monkeypatch.setattr(context, "don_vet_qua_han", cleanup)
    first = context.Tracer(TracerSettings(thu_muc=str(tmp_path / "a")), auto_cleanup=True)
    second = context.Tracer(TracerSettings(thu_muc=str(tmp_path / "b")), auto_cleanup=True)
    try:
        assert called.wait(3)
        with context._CLEANUP_LOCK:
            assert first in context._CLEANUP_JOBS
            assert second in context._CLEANUP_JOBS
            assert context._CLEANUP_THREAD is not None
            assert context._CLEANUP_THREAD.is_alive()
    finally:
        first.close()
        second.close()


def test_database_error_logs_only_type_once(caplog) -> None:
    import psycopg

    calls = []
    clock = [0.0]

    def fail(*args, **kwargs):
        calls.append(True)
        raise psycopg.OperationalError("postgresql://secret-host/secret")

    sink = PostgresTraceSink(
        url="fake", connect=fail, auto_start=False, monotonic=lambda: clock[0], cau_dao_giay=1
    )
    now = datetime.now(UTC)
    record = VetChay(
        ma_vet=str(uuid4()),
        bat_dau=now,
        ket_thuc=now,
        thoi_gian_ms=0,
        loai="hoi_dap",
        engine="agentic",
    )
    sink._write_batch([record])
    clock[0] = 2
    sink._write_batch([record])
    assert len(calls) == 2
    assert sink.so_vet_bo_db == 2
    assert sum("OperationalError" in r.message for r in caplog.records) == 1
    assert "secret-host" not in caplog.text
