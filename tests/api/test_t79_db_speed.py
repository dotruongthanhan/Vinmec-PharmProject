"""Kiểm thử tối ưu tốc độ đọc/ghi DB của T79 (làm nóng, gom lô, nền, song song)."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from threading import Barrier, Event, Thread
from typing import Any, Literal

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import container as container_mod
from app.api import schemas as s
from app.api.main import create_app
from app.api.service import CaseService
from app.config.settings import load_settings
from app.core.errors import ConfigError
from app.db import administrative, bang_luat_store, medical_record, reader
from app.db.bang_luat import RULE_TABLES, clear_all_caches, load_bang_luat
from app.db.read_pool import read_pool
from app.db.reader import DbReviewService
from app.db.sources import prepare_cases
from app.domain.loader import ingredients_of, load_case
from app.domain.models import CaBenh
from app.kb.interactions import InteractionStore
from app.kb.names import DrugNameIndex
from app.kb.resolver import DrugResolver
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.pipeline import run_case
from app.rules import (
    allergy_config,
    d4_config,
    d5_config,
    d6_config,
    d7_config,
    duplicate_config,
    renal_dose,
)
from app.rules.types import effective_lines
from tests.db.test_bang_luat import FakeBangLuatConnection

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _isolate_t79_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Cô lập bộ nhớ đệm bảng luật, ngữ cảnh dùng chung và kết nối rảnh giữa các test."""
    clear_all_caches()
    monkeypatch.setattr(container_mod, "_SHARED_RULE_CONTEXT", None)
    yield
    clear_all_caches()
    read_pool.close()


def _env_secret(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigError(name)
    return value


class _FakeDdinterCursor:
    """Con trỏ giả lập dict_row cho bảng DDInter."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self._rows)


class _FakeDdinterPgConnection:
    """Kết nối SQLite giả lập 3 bảng tri_thuc.ddinter_* để đếm truy vấn list_cases."""

    def __init__(self) -> None:
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.executescript(
            """
            CREATE TABLE ddinter_cap (
                ddinter_id_a TEXT NOT NULL,
                ddinter_id_b TEXT NOT NULL,
                muc_do TEXT NOT NULL,
                muc_do_so INTEGER NOT NULL,
                co_che_json TEXT NOT NULL,
                co_lech_muc INTEGER NOT NULL,
                cac_muc_nguon_json TEXT NOT NULL,
                ma_trang_cap_json TEXT NOT NULL,
                hau_qua TEXT,
                xu_tri TEXT,
                tai_lieu_json TEXT NOT NULL,
                url_goc TEXT,
                PRIMARY KEY (ddinter_id_a, ddinter_id_b)
            );
            CREATE TABLE ddinter_thuoc (
                ddinter_id TEXT PRIMARY KEY,
                ten TEXT NOT NULL,
                da_cao_du INTEGER NOT NULL
            );
            CREATE TABLE ddinter_thuc_an (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ddinter_id TEXT NOT NULL,
                thuc_an TEXT NOT NULL,
                muc_do TEXT NOT NULL,
                mo_ta TEXT,
                xu_tri TEXT,
                co_che_json TEXT NOT NULL
            );
            """
        )
        self.statements: list[str] = []

    def close(self) -> None:
        self._db.close()

    def execute(self, query: str, params: Any = None) -> _FakeDdinterCursor:
        self.statements.append(query)
        sql_text = query.replace("tri_thuc.", "").replace("%s", "?")
        if "WHERE (ddinter_id_a, ddinter_id_b) IN ((" in sql_text:
            sql_text = sql_text.replace(
                "WHERE (ddinter_id_a, ddinter_id_b) IN (",
                "WHERE (ddinter_id_a, ddinter_id_b) IN (VALUES ",
            )
        cur = self._db.execute(sql_text, tuple(params or ()))
        columns = [desc[0] for desc in cur.description or ()]
        rows = [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]
        return _FakeDdinterCursor(rows)


def test_lifespan_warms_db_knowledge_without_blocking_and_deduplicates_concurrent_requests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KB_SOURCE", "db")
    monkeypatch.setenv("CASE_SOURCE", "file")
    monkeypatch.setenv("CDSS_AI", "off")
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("ACCESS_LOG", "off")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/prod")
    monkeypatch.setattr(container_mod, "get_secret", _env_secret)
    monkeypatch.setattr(bang_luat_store, "get_secret", _env_secret)

    with closing(FakeBangLuatConnection(as_dicts=True)) as rule_conn:
        load_bang_luat(rule_conn, ROOT)
        rule_conn.statements.clear()
        bang_luat_opens = 0

        @contextmanager
        def fake_bang_luat_pool(_url: str) -> Iterator[FakeBangLuatConnection]:
            nonlocal bang_luat_opens
            bang_luat_opens += 1
            yield rule_conn

        @contextmanager
        def fake_container_pool(_url: str) -> Iterator[object]:
            yield object()

        resolver_started = Event()
        allow_resolver = Event()
        resolver_calls = 0
        interaction_calls = 0
        stub_resolver = object()
        stub_interactions = object()

        def fake_resolver_from_db(_cls: Any, _conn: Any) -> Any:
            nonlocal resolver_calls
            resolver_calls += 1
            resolver_started.set()
            assert allow_resolver.wait(timeout=5.0)
            return stub_resolver

        def fake_interactions_from_db(
            _cls: Any,
            _conn: Any,
            *,
            db_url: str | None = None,
        ) -> Any:
            nonlocal interaction_calls
            del db_url
            interaction_calls += 1
            return stub_interactions

        monkeypatch.setattr(bang_luat_store, "open_read_connection", fake_bang_luat_pool)
        monkeypatch.setattr(container_mod.read_pool, "connection", fake_container_pool)
        monkeypatch.setattr(DrugResolver, "from_db", classmethod(fake_resolver_from_db))
        monkeypatch.setattr(InteractionStore, "from_db", classmethod(fake_interactions_from_db))

        service = CaseService(
            ROOT / "data/mock/demo",
            None,
            tmp_path / "feedback.jsonl",
            ai_runner=None,
        )
        with TestClient(create_app(service)) as client:
            health = client.get("/api/health")
            assert health.status_code == 200
            assert resolver_started.wait(timeout=5.0)

            concurrent_ctxs: list[Any] = []
            concurrent_errors: list[BaseException] = []

            def concurrent_caller() -> None:
                try:
                    concurrent_ctxs.append(container_mod.get_rule_context())
                except BaseException as exc:
                    concurrent_errors.append(exc)

            req_thread = Thread(target=concurrent_caller)
            req_thread.start()
            allow_resolver.set()
            req_thread.join(timeout=5.0)

            warmup = client.app.state.warmup_thread
            assert warmup is not None
            warmup.join(timeout=5.0)

            assert not concurrent_errors
            assert resolver_calls == 1
            assert interaction_calls == 1
            assert bang_luat_opens == 1
            assert len(rule_conn.statements) == len(RULE_TABLES)
            assert len(concurrent_ctxs) == 1
            assert concurrent_ctxs[0].resolver is stub_resolver
            assert concurrent_ctxs[0].interactions is stub_interactions
            assert concurrent_ctxs[0] is container_mod.get_rule_context()

            assert d4_config.try_load_default_hepatic_config() is not None
            assert d4_config.try_load_default_lab_threshold_config() is not None
            assert d4_config.try_load_default_drug_disease_config() is not None
            assert d5_config.try_load_default_route_config() is not None
            assert d5_config.try_load_default_max_dose_config() is not None
            assert d6_config.try_load_default_toxicity_config() is not None
            assert d7_config.try_load_default_stewardship_config() is not None
            assert allergy_config.try_load_default_allergy_config() is not None
            assert duplicate_config.try_load_default_duplicate_config() is not None
            assert DrugNameIndex.load().resolve("Paracetamol") == ["acetaminophen"]
            assert renal_dose.load_renal_rules().quy_tac
            assert bang_luat_opens == 1


def test_lifespan_warmup_skips_file_mode_and_logs_warning_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("CASE_SOURCE", "file")
    monkeypatch.setenv("CDSS_AI", "off")
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("ACCESS_LOG", "off")

    monkeypatch.setenv("KB_SOURCE", "file")
    file_service = CaseService(
        ROOT / "data/mock/demo",
        None,
        tmp_path / "fb_file.jsonl",
        ai_runner=None,
    )
    with TestClient(create_app(file_service)) as client:
        assert client.app.state.warmup_thread is None
        assert client.get("/api/health").status_code == 200

    clear_all_caches()
    monkeypatch.setattr(container_mod, "_SHARED_RULE_CONTEXT", None)
    secret_dsn = "postgresql://demo:mat-khau-bi-mat@db.invalid/prod"
    monkeypatch.setenv("KB_SOURCE", "db")
    monkeypatch.setenv("DATABASE_URL", secret_dsn)
    monkeypatch.setattr(container_mod, "get_secret", _env_secret)
    monkeypatch.setattr(bang_luat_store, "get_secret", _env_secret)

    @contextmanager
    def broken_pool(url: str) -> Iterator[Any]:
        raise psycopg.OperationalError(url)
        yield  # pragma: no cover

    monkeypatch.setattr(bang_luat_store, "open_read_connection", broken_pool)
    monkeypatch.setattr(container_mod.read_pool, "connection", broken_pool)

    db_service = CaseService(
        ROOT / "data/mock/demo",
        None,
        tmp_path / "fb_db.jsonl",
        ai_runner=None,
    )
    with caplog.at_level(logging.WARNING):
        with TestClient(create_app(db_service)) as client:
            assert client.get("/api/health").status_code == 200
            warmup = client.app.state.warmup_thread
            assert warmup is not None
            warmup.join(timeout=5.0)
    assert caplog.records
    assert "mat-khau-bi-mat" not in caplog.text


def test_container_concurrent_cached_property_loads_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KB_SOURCE", "db")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/prod")
    monkeypatch.setattr(container_mod, "get_secret", _env_secret)

    @contextmanager
    def fake_pool(_url: str) -> Iterator[object]:
        yield object()

    resolver_calls = 0
    interaction_calls = 0
    stub_resolver = object()
    stub_interactions = object()

    def counted_resolver(_cls: Any, _conn: Any) -> Any:
        nonlocal resolver_calls
        time.sleep(0.03)
        resolver_calls += 1
        return stub_resolver

    def counted_interactions(_cls: Any, _conn: Any, *, db_url: str | None = None) -> Any:
        nonlocal interaction_calls
        del db_url
        time.sleep(0.03)
        interaction_calls += 1
        return stub_interactions

    monkeypatch.setattr(container_mod.read_pool, "connection", fake_pool)
    monkeypatch.setattr(DrugResolver, "from_db", classmethod(counted_resolver))
    monkeypatch.setattr(InteractionStore, "from_db", classmethod(counted_interactions))

    container = container_mod.Container(load_settings("test"))
    start_barrier = Barrier(4, timeout=5.0)
    got_resolvers: list[Any] = []
    got_stores: list[Any] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            start_barrier.wait()
            got_resolvers.append(container.drug_resolver)
            got_stores.append(container.interaction_store)
        except BaseException as exc:
            errors.append(exc)

    threads = [Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5.0)

    assert not errors
    assert resolver_calls == 1
    assert interaction_calls == 1
    assert len(got_resolvers) == 4 and all(item is stub_resolver for item in got_resolvers)
    assert len(got_stores) == 4 and all(item is stub_interactions for item in got_stores)


def test_list_cases_67_cases_queries_ddinter_cap_once_and_matches_file_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = prepare_cases(ROOT).rows
    base_cases, errors = reader.build_cases(rows)
    assert not errors and len(base_cases) == 66
    hs024 = next(case for case in base_cases if case.ca_id == "HS-024")
    cases_67 = [*base_cases, hs024.model_copy(update={"ca_id": "HS-061"})]
    assert len(cases_67) == 67

    ingredient_to_ddinter: dict[str, tuple[str, str]] = {}
    for case in cases_67:
        for line in (*case.y_lenh_cho_duyet.chi_tiet, *case.thuoc_dang_dung):
            for hc in ingredients_of(case, line):
                if hc.hoat_chat_id not in ingredient_to_ddinter:
                    idx = len(ingredient_to_ddinter) + 1
                    ingredient_to_ddinter[hc.hoat_chat_id] = (
                        f"DD{idx:04d}",
                        hc.ten_quoc_te or hc.ten_hoat_chat,
                    )

    class _BatchStubResolver:
        def resolve_line(self, ca: CaBenh, line: Any) -> KetQuaPhanGiai:
            components = []
            for hc in ingredients_of(ca, line):
                dd_id, inn = ingredient_to_ddinter[hc.hoat_chat_id]
                components.append(
                    ThanhPhanPhanGiai(
                        hoat_chat_id=hc.hoat_chat_id,
                        ten_inn=inn,
                        ten_viet=hc.ten_hoat_chat,
                        ma_atc=[hc.ma_atc] if hc.ma_atc else [],
                        ddinter_id=dd_id,
                        loai="thuoc",
                    )
                )
            if not components:
                return KetQuaPhanGiai(trang_thai="khong_nhan_dien", ly_do="Không có thành phần")
            return KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                nguon_khop="danh_muc_ca",
                thanh_phan=components,
            )

    stub_resolver: Any = _BatchStubResolver()
    with closing(_FakeDdinterPgConnection()) as conn:
        drug_rows = []
        for dd_id, inn in ingredient_to_ddinter.values():
            conn._db.execute(
                "INSERT INTO ddinter_thuoc VALUES (?, ?, ?)",
                (dd_id, inn, 1),
            )
            drug_rows.append((dd_id, 1))

        # Cặp thuốc thực tế của HS-024 (và HS-061) để kiểm đối chiếu nhận định mức nặng.
        hs024_ids = sorted(
            {
                ingredient_to_ddinter[hc.hoat_chat_id][0]
                for line in effective_lines(hs024)
                for hc in ingredients_of(hs024, line)
            }
        )
        assert len(hs024_ids) >= 2
        sample_pairs = [
            (
                hs024_ids[0],
                hs024_ids[1],
                "Major",
                3,
                json.dumps(["Tăng nguy cơ độc tính"]),
                0,
                json.dumps(["Major"]),
                json.dumps(["1"]),
                "Hậu quả giả lập",
                "Xử trí giả lập",
                json.dumps(["DDInter test"]),
                "https://ddinter.invalid/1",
            ),
        ]
        if len(hs024_ids) >= 3:
            a, b = sorted((hs024_ids[0], hs024_ids[2]))
            sample_pairs.append(
                (
                    a,
                    b,
                    "Moderate",
                    2,
                    json.dumps(["Theo dõi"]),
                    0,
                    json.dumps(["Moderate"]),
                    json.dumps(["2"]),
                    "Hậu quả trung bình",
                    "Theo dõi thêm",
                    json.dumps(["DDInter test"]),
                    "https://ddinter.invalid/2",
                )
            )
        for pair_row in sample_pairs:
            conn._db.execute(
                "INSERT INTO ddinter_cap VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                pair_row,
            )

        file_store = InteractionStore._build(sample_pairs, drug_rows, ())
        db_store = InteractionStore.from_db(conn)
        conn.statements.clear()

        renal_rules = renal_dose.load_renal_rules()
        expected = {
            case.ca_id: run_case(
                case,
                renal_rules,
                resolver=stub_resolver,
                interactions=file_store,
            )
            for case in cases_67
        }

        monkeypatch.setenv("CASE_SOURCE", "db")
        monkeypatch.setenv("KB_SOURCE", "file")
        monkeypatch.setenv("CDSS_AI", "off")
        monkeypatch.setattr(DbReviewService, "list_cases", lambda self: (list(cases_67), []))
        monkeypatch.setattr(CaseService, "_administrative", lambda self, cases: {})
        monkeypatch.setattr(
            container_mod,
            "get_rule_context",
            lambda: container_mod.RuleContext(renal_rules, stub_resolver, db_store),
        )

        service = CaseService(
            ROOT / "data/mock/demo",
            None,
            tmp_path / "feedback.jsonl",
            ai_runner=None,
        )
        try:
            queue = service.list_cases()
            assert len(queue.cases) == 67
            cap_queries = [stmt for stmt in conn.statements if "ddinter_cap" in stmt]
            assert len(cap_queries) == 1

            for case in cases_67:
                assert service._results[case.ca_id].phat_hien == expected[case.ca_id].phat_hien

            # Gọi lại lần 2 không truy vấn ddinter_cap thêm.
            assert len(service.list_cases().cases) == 67
            assert len([stmt for stmt in conn.statements if "ddinter_cap" in stmt]) == 1
        finally:
            service.shutdown()


def test_get_case_returns_before_slow_save_review_finishes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    monkeypatch.setenv("CASE_SOURCE", "db")
    monkeypatch.setenv("KB_SOURCE", "file")
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("ACCESS_LOG", "off")
    monkeypatch.setenv("CDSS_AI", "off")
    monkeypatch.setattr(DbReviewService, "list_cases", lambda self: ([case], []))
    monkeypatch.setattr(CaseService, "_administrative", lambda self, cases: {})
    monkeypatch.setattr(CaseService, "_read_medical_record", lambda self, c: s.MedicalRecord())

    save_started = Event()
    allow_finish = Event()
    saved_ids: list[str] = []

    class _SlowReviewStore:
        def save_review(
            self,
            *,
            ca_id: str,
            detail: s.ChiTietCa,
            phien_ban_luat: str,
            che_do: Literal["file", "db"],
            thoi_diem: datetime | None = None,
        ) -> str | None:
            del detail, phien_ban_luat, che_do, thoi_diem
            save_started.set()
            assert allow_finish.wait(timeout=5.0)
            saved_ids.append(ca_id)
            return "kq-slow-1"

        def list_history(self, ca_id: str) -> list[s.LanThamDinhLichSu]:
            del ca_id
            return []

    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "feedback.jsonl",
        ai_runner=None,
        review_store=_SlowReviewStore(),
    )
    with TestClient(create_app(service)) as client:
        first = client.get("/api/cases/DEMO-02")
        assert first.status_code == 200
        assert not allow_finish.is_set()
        assert saved_ids == []
        assert save_started.wait(timeout=2.0)

        # Gọi lại trong lúc lần ghi đầu đang chạy không xếp hàng ghi trùng.
        second = client.get("/api/cases/DEMO-02")
        assert second.status_code == 200
        allow_finish.set()
        service.flush_persist(timeout=5.0)
        assert saved_ids == ["DEMO-02"]

    # Lỗi bất ngờ ở tác vụ nền chỉ log cảnh báo, không làm hỏng API.
    class _FailingReviewStore:
        def save_review(self, **_kwargs: Any) -> str | None:
            raise RuntimeError("postgresql://demo:bi-mat-nen@db.invalid/prod")

        def list_history(self, ca_id: str) -> list[s.LanThamDinhLichSu]:
            del ca_id
            return []

    failing_service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "feedback_fail.jsonl",
        ai_runner=None,
        review_store=_FailingReviewStore(),
    )
    with caplog.at_level(logging.WARNING):
        with TestClient(create_app(failing_service)) as client:
            resp = client.get("/api/cases/DEMO-02")
            assert resp.status_code == 200
            failing_service.flush_persist(timeout=5.0)
    assert "Không lưu được kết quả thẩm định ở luồng nền" in caplog.text
    assert "bi-mat-nen" not in caplog.text


def test_get_case_reads_administrative_and_medical_record_in_parallel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = prepare_cases(ROOT).rows
    cases, errors = reader.build_cases(rows)
    assert not errors
    hs022 = next(case for case in cases if case.ca_id == "HS-022")

    monkeypatch.setenv("CASE_SOURCE", "db")
    monkeypatch.setenv("KB_SOURCE", "file")
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("ACCESS_LOG", "off")
    monkeypatch.setenv("CDSS_AI", "off")
    monkeypatch.setattr(DbReviewService, "list_cases", lambda self: ([hs022], []))

    barrier = Barrier(2, timeout=2.0)

    def parallel_admin(patient_ids: list[str]) -> dict[str, s.AdministrativeRecord]:
        barrier.wait()
        return administrative.build_administrative(rows, patient_ids)

    def parallel_medical(patient_id: str, case_id: str) -> s.MedicalRecord:
        barrier.wait()
        return medical_record.build_medical_record(rows, patient_id, case_id)

    monkeypatch.setattr(administrative, "read_administrative", parallel_admin)
    monkeypatch.setattr(medical_record, "read_medical_record", parallel_medical)

    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "feedback.jsonl",
        ai_runner=None,
    )
    with TestClient(create_app(service)) as client:
        resp = client.get("/api/cases/HS-022")
        assert resp.status_code == 200
        body = resp.json()
        assert body["dinh_danh_day_du"]["ho_ten"] == "Nguyễn Văn 22"
        assert len(body["danh_sach_y_lenh"]) == 7
