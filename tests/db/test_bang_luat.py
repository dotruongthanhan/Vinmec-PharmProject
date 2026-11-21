"""Kiểm thử chuyển 12 bảng luật/danh mục D1-D7 lên PostgreSQL và đọc lại lúc chạy."""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from threading import Event, Thread
from typing import Any
from unittest.mock import patch

import psycopg
import pytest

from app import container as container_mod
from app.api import service as service_mod
from app.api.service import CaseService
from app.config.settings import load_settings
from app.core.errors import ConfigError
from app.db import bang_luat, bang_luat_store, cli
from app.db.bang_luat import (
    RULE_DOCUMENTS,
    RULE_TABLES,
    clear_all_caches,
    expected_table_counts,
    load_bang_luat,
    load_document,
    prepare_document,
)
from app.domain.loader import load_case
from app.kb import names as names_mod
from app.kb.names import DrugNameIndex
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.orchestration.ask import CaseAsker
from app.pipeline import run_case
from app.providers.bm25_index import Bm25Index
from app.providers.fakes import FakeLLM, HashEmbedder, NoopReranker
from app.providers.memory_store import InMemoryVectorStore
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.query_builder import QueryBuilder
from app.rules import (
    allergy,
    allergy_config,
    d4_config,
    d5_config,
    d6_config,
    d7_config,
    drug_disease,
    duplicate,
    duplicate_config,
    hepatic,
    lab_threshold,
    max_dose,
    renal_dose,
    route,
    stewardship,
    toxicity,
)
from app.rules.registry import RuleContext

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _reset_rule_caches() -> Iterator[None]:
    """Xoá bộ nhớ đệm bảng luật trước và sau mỗi test để không nhiễm trạng thái."""
    clear_all_caches()
    yield
    clear_all_caches()


def _env_secret(name: str) -> str:
    """Đọc biến môi trường giả lập trong test mà không kích hoạt load_dotenv."""
    value = os.getenv(name)
    if not value:
        raise ConfigError(name)
    return value


def test_bang_luat_store_is_isolated_from_rules_and_uses_single_connection_point() -> None:
    source = (ROOT / "app/db/bang_luat_store.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(("app.rules", "app.kb", "app.db.sources"))
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            assert not node.module.startswith(("app.rules", "app.kb", "app.db.sources"))
    assert source.count("read_pool.connection") == 1
    assert "psycopg.connect" not in source


def _sqlite_schema_for_bang_luat() -> str:
    """Chuyển DDL các bảng bảng-luật trong db/schema.sql sang cú pháp SQLite kiểm thử."""
    sql_text = (ROOT / "db/schema.sql").read_text(encoding="utf-8")
    blocks = dict(
        re.findall(r"CREATE TABLE IF NOT EXISTS (\w+\.\w+) \(\n(.*?)\n\);", sql_text, re.S)
    )
    stmts: list[str] = []
    for full_name in RULE_TABLES:
        body = blocks[full_name]
        short = full_name.split(".", 1)[1]
        lines: list[str] = []
        for raw_line in body.splitlines():
            line = raw_line
            line = line.replace("id bigserial PRIMARY KEY", "id INTEGER PRIMARY KEY AUTOINCREMENT")
            line = line.replace("double precision", "REAL")
            line = line.replace("timestamptz", "TEXT")
            line = line.replace("boolean", "INTEGER")
            line = line.replace("jsonb NOT NULL DEFAULT '{}'::jsonb", "TEXT NOT NULL DEFAULT '{}'")
            line = line.replace("jsonb NOT NULL DEFAULT '[]'::jsonb", "TEXT NOT NULL DEFAULT '[]'")
            line = line.replace("DEFAULT now()", "DEFAULT CURRENT_TIMESTAMP")
            line = line.replace("jsonb", "TEXT")
            line = line.replace("REFERENCES tri_thuc.", "REFERENCES ")
            line = re.sub(r"\s+text\b", " TEXT", line)
            line = re.sub(r"\s+integer\b", " INTEGER", line)
            lines.append(line)
        joined = "\n".join(lines)
        stmts.append(f"CREATE TABLE {short} (\n{joined}\n);")
    return "\n".join(stmts)


class FakeBangLuatCursor:
    """Con trỏ giả trả tuple hoặc dict giống psycopg 3."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def fetchall(self) -> list[Any]:
        return list(self._rows)

    def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    def __iter__(self) -> Iterator[Any]:
        return iter(self._rows)


class FakeBangLuatConnection:
    """Kết nối SQLite trong bộ nhớ mô phỏng 24 bảng quy tắc tri_thuc.*."""

    def __init__(self, *, as_dicts: bool = False) -> None:
        self._db = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
        self._db.executescript(_sqlite_schema_for_bang_luat())
        self.as_dicts = as_dicts
        self.committed = False
        self.rolled_back = False
        self.statements: list[str] = []

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> FakeBangLuatConnection:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self._db.execute("BEGIN")
        try:
            yield
        except Exception:
            self._db.rollback()
            self.rolled_back = True
            raise
        else:
            self._db.commit()
            self.committed = True

    def _convert_param(self, value: Any) -> Any:
        if hasattr(value, "obj"):
            return json.dumps(value.obj, ensure_ascii=False)
        return value

    def execute(self, query: str, params: Any = None) -> FakeBangLuatCursor:
        self.statements.append(query)
        if query.startswith("TRUNCATE "):
            for table_name in re.findall(r"tri_thuc\.(\w+)", query):
                self._db.execute(f'DELETE FROM "{table_name}"')
            return FakeBangLuatCursor([])
        sql_text = query.replace("tri_thuc.", "").replace("%s", "?")
        bound = tuple(self._convert_param(item) for item in (params or ()))
        cur = self._db.execute(sql_text, bound)
        columns = [desc[0] for desc in cur.description or ()]
        raw_rows = cur.fetchall()
        if not columns:
            return FakeBangLuatCursor([])
        if not self.as_dicts:
            return FakeBangLuatCursor(raw_rows)
        return FakeBangLuatCursor([dict(zip(columns, row, strict=True)) for row in raw_rows])

    def executemany(self, query: str, rows: list[tuple[Any, ...]]) -> None:
        self.statements.append(query)
        sql_text = query.replace("tri_thuc.", "").replace("%s", "?")
        converted = [tuple(self._convert_param(item) for item in row) for row in rows]
        self._db.executemany(sql_text, converted)


def test_schema_contains_all_bang_luat_tables_indexes_and_rls() -> None:
    schema = (ROOT / "db/schema.sql").read_text(encoding="utf-8")
    blocks = dict(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+\.\w+) \(\n(.*?)\n\);", schema, re.S))
    revoke_match = re.search(
        r"REVOKE ALL ON\s+tri_thuc\.bang_luat_meta,(.*?)FROM PUBLIC;",
        schema,
        flags=re.S,
    )
    assert revoke_match is not None
    revoke_block = revoke_match.group(0)
    do_blocks = re.findall(r"DO \$\$.*?END\s*\$\$;", schema, flags=re.S)
    rule_do = [block for block in do_blocks if "tri_thuc.bang_luat_meta" in block]
    assert len(rule_do) == 1

    for table in RULE_TABLES:
        assert table in blocks, table
        assert table in revoke_block, table
        assert table in rule_do[0], table
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in schema, table

    assert "hoat_chat_id text" in blocks["tri_thuc.quy_tac_lieu_than_v2"]
    assert "USING gin (hoat_chat_ids)" in schema
    assert "ON tri_thuc.nguong_xet_nghiem (xet_nghiem);" in schema
    assert "ON tri_thuc.tuong_tac_benh (hoat_chat_id);" in schema
    assert "ON tri_thuc.canh_bao_doc_tinh (hoat_chat_id, loai);" in schema


def test_all_real_rule_documents_roundtrip_without_postgres() -> None:
    prepared = [prepare_document(spec, ROOT) for spec in RULE_DOCUMENTS]
    counts = expected_table_counts(prepared)
    assert counts["tri_thuc.bang_luat_meta"] == 12
    for table, count in counts.items():
        assert count > 0, table


@pytest.mark.parametrize("as_dicts", [False, True])
def test_load_bang_luat_and_load_document_preserve_order_and_data(
    as_dicts: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    with closing(FakeBangLuatConnection(as_dicts=as_dicts)) as conn:
        counts = load_bang_luat(conn, ROOT)
        assert conn.committed is True
        assert counts["tri_thuc.bang_luat_meta"] == 12
        out = capsys.readouterr().out
        for table in RULE_TABLES:
            assert f"{table}: {counts[table]}" in out

        for spec in RULE_DOCUMENTS:
            prepared = prepare_document(spec, ROOT)
            loaded = load_document(conn, spec.ma)
            assert loaded == prepared.raw, spec.ma


def test_cli_load_bang_luat_dry_run_rollback_and_reject_corrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with (
        patch("app.db.cli.get_secret", side_effect=AssertionError("Không được đọc bí mật")),
        patch("psycopg.connect", side_effect=AssertionError("Không được kết nối DB")),
    ):
        assert cli.main(["load", "bang-luat", "--dry-run"]) == 0
    dry_out = capsys.readouterr().out
    assert "tri_thuc.bang_luat_meta: 12" in dry_out
    assert "DRY-RUN" in dry_out

    # Bản sao kho giả để kiểm tra tệp hỏng bị từ chối trước khi kết nối DB.
    for spec in RULE_DOCUMENTS:
        target = tmp_path / spec.tep
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / spec.tep, target)
    shutil.copytree(ROOT / "config", tmp_path / "config", dirs_exist_ok=True)
    bad_file = tmp_path / "data/kb/quy_tac_gan.json"
    bad_payload = json.loads(bad_file.read_text(encoding="utf-8"))
    bad_payload["quy_tac"][0]["hanh_dong_nhan"] = "gia_tri_sai_enum"
    bad_file.write_text(json.dumps(bad_payload), encoding="utf-8")

    monkeypatch.setattr(cli, "ROOT", tmp_path)
    with (
        patch("app.db.cli.get_secret", side_effect=AssertionError("Không được đọc bí mật")),
        patch("psycopg.connect", side_effect=AssertionError("Không được kết nối DB")),
    ):
        code = cli.main(["load", "bang-luat"])
    assert code != 0
    capsys.readouterr()

    # Khôi phục tệp hợp lệ và kiểm tra rollback khi đối chiếu DB trả sai khác.
    shutil.copyfile(ROOT / "data/kb/quy_tac_gan.json", bad_file)
    bad_conn = FakeBangLuatConnection(as_dicts=True)
    real_load_document = bang_luat.load_document

    def skewed_load_document(conn: Any, ma: str) -> dict[str, Any]:
        doc = real_load_document(conn, ma)
        if ma == "atc_bo_sung":
            doc["nguon"] = "DA_BI_SUA_SAI"
        return doc

    monkeypatch.setattr(cli, "get_secret", lambda _name: "postgresql://fake@localhost/db")
    monkeypatch.setattr(cli.psycopg, "connect", lambda *args, **kwargs: bad_conn)
    monkeypatch.setattr(bang_luat, "load_document", skewed_load_document)
    mismatch_code = cli.main(["load", "bang-luat"])
    assert mismatch_code != 0
    assert bad_conn.rolled_back is True
    assert bad_conn.committed is False


def test_runtime_loaders_db_and_auto_match_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_all_caches()
    monkeypatch.setenv("KB_SOURCE", "file")
    expected_renal = renal_dose.load_renal_rules()
    expected_hepatic = d4_config.load_hepatic_config()
    expected_lab = d4_config.load_lab_threshold_config()
    expected_dd = d4_config.load_drug_disease_config()
    expected_route = d5_config.load_route_config()
    expected_max = d5_config.load_max_dose_config()
    expected_tox = d6_config.load_toxicity_config()
    expected_stew = d7_config.load_stewardship_config()
    expected_allergy = allergy_config.load_allergy_config()
    expected_names = DrugNameIndex.load()
    expected_dup = duplicate_config.load_duplicate_config()

    with closing(FakeBangLuatConnection(as_dicts=True)) as conn:
        load_bang_luat(conn, ROOT)
        db_queries = 0

        @contextmanager
        def fake_pool(url: str) -> Iterator[FakeBangLuatConnection]:
            nonlocal db_queries
            assert url == "postgresql://demo:secret@db.invalid/prod"
            db_queries += 1
            yield conn

        monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/prod")
        monkeypatch.setattr(bang_luat_store, "get_secret", _env_secret)
        monkeypatch.setattr(bang_luat_store, "open_read_connection", fake_pool)

        clear_all_caches()
        monkeypatch.setenv("KB_SOURCE", "db")
        assert renal_dose.load_renal_rules() == expected_renal
        assert d4_config.try_load_default_hepatic_config() == expected_hepatic
        assert d4_config.try_load_default_lab_threshold_config() == expected_lab
        assert d4_config.try_load_default_drug_disease_config() == expected_dd
        assert d5_config.try_load_default_route_config() == expected_route
        assert d5_config.try_load_default_max_dose_config() == expected_max
        assert d6_config.try_load_default_toxicity_config() == expected_tox
        assert d7_config.try_load_default_stewardship_config() == expected_stew
        assert allergy_config.try_load_default_allergy_config() == expected_allergy
        db_names = DrugNameIndex.load()
        assert db_names._entries == expected_names._entries
        assert db_names._labels == expected_names._labels
        assert db_names.resolve("Paracetamol") == expected_names.resolve("Paracetamol")
        label = "amoxicillin_and_clavulanate_potassium"
        assert db_names.ids_for_label(label) == expected_names.ids_for_label(label)
        assert duplicate_config.load_duplicate_config() == expected_dup

        assert db_queries == 1
        # Gọi lại không truy vấn DB thêm lần nào (nạp một lần mỗi tiến trình).
        assert d4_config.try_load_default_hepatic_config() == expected_hepatic
        assert d5_config.try_load_default_route_config() == expected_route
        assert DrugNameIndex.load()._entries == expected_names._entries
        assert renal_dose.load_renal_rules() == expected_renal
        assert duplicate_config.load_duplicate_config() == expected_dup
        assert db_queries == 1

        # Chế độ auto khi vắng tệp cục bộ sẽ đọc từ DB.
        clear_all_caches()
        monkeypatch.setenv("KB_SOURCE", "auto")
        monkeypatch.setattr(d4_config, "_DEFAULT_HEPATIC_PATH", tmp_path / "missing_gan.json")
        monkeypatch.setattr(names_mod, "_DEFAULT_HOAT_CHAT_PATH", tmp_path / "missing_hc.json")
        monkeypatch.setattr(renal_dose, "DEFAULT_RENAL_RULES_PATH", tmp_path / "missing_renal.json")
        assert d4_config.try_load_default_hepatic_config() == expected_hepatic
        assert DrugNameIndex.load().resolve("Paracetamol") == ["acetaminophen"]
        assert renal_dose.load_renal_rules() == expected_renal
        assert db_queries == 2
    clear_all_caches()


def test_db_failure_returns_safe_fallback_and_logs_single_warning_without_dsn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret_dsn = "postgresql://demo:mat-khau-tuyet-mat@db.invalid/prod"
    monkeypatch.setenv("KB_SOURCE", "db")
    monkeypatch.setenv("DATABASE_URL", secret_dsn)

    @contextmanager
    def broken_pool(url: str) -> Iterator[Any]:
        raise psycopg.OperationalError(url)
        yield  # pragma: no cover

    monkeypatch.setattr(bang_luat_store, "get_secret", _env_secret)
    monkeypatch.setattr(bang_luat_store, "open_read_connection", broken_pool)
    clear_all_caches()

    case = load_case(ROOT / "data/mock/demo/DEMO-01.json")

    class _MinimalResolver:
        def resolve_line(self, _ca: Any, _line: Any) -> KetQuaPhanGiai:
            return KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[
                    ThanhPhanPhanGiai(
                        hoat_chat_id="meropenem",
                        ten_inn="Meropenem",
                        ten_viet=None,
                        ma_atc=["J01DH02"],
                        ddinter_id=None,
                        loai="thuoc",
                    )
                ],
            )

    resolver: Any = _MinimalResolver()
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            assert d4_config.try_load_default_hepatic_config() is None
            assert d4_config.try_load_default_lab_threshold_config() is None
            assert d4_config.try_load_default_drug_disease_config() is None
            assert d5_config.try_load_default_route_config() is None
            assert d5_config.try_load_default_max_dose_config() is None
            assert d6_config.try_load_default_toxicity_config() is None
            assert d7_config.try_load_default_stewardship_config() is None
            assert allergy_config.try_load_default_allergy_config() is None
            assert renal_dose.try_load_default_renal_rules() is None
            assert duplicate_config.try_load_default_duplicate_config() is None
            names = DrugNameIndex.load()
            assert names.resolve("Paracetamol") == []

        assert len(caplog.records) == 12  # 12 bảng luật, mỗi bảng chỉ log cảnh báo đúng 1 lần.
        assert "mat-khau-tuyet-mat" not in caplog.text

        # Bộ nạp không được làm sập app hay các luật đang chạy.
        renal_book = renal_dose.load_renal_rules()
        assert run_case(case, renal_book, resolver=resolver).phat_hien
        allergy.check(case, resolver)
        duplicate.check(case, resolver)
        route.check(case, resolver)
        max_dose.check(case, resolver)
        toxicity.check(case, resolver)
        hepatic.check(case, resolver)
        lab_threshold.check(case, resolver)
        drug_disease.check(case, resolver)
        stewardship.check(case, resolver)
        assert len(caplog.records) == 12

    # Bảng DB trống khi KB_SOURCE=auto và thiếu tệp cũng không làm sập app.
    with closing(FakeBangLuatConnection(as_dicts=True)) as empty_conn:

        @contextmanager
        def empty_pool(_url: str) -> Iterator[FakeBangLuatConnection]:
            yield empty_conn

        clear_all_caches()
        monkeypatch.setenv("KB_SOURCE", "auto")
        monkeypatch.setattr(d4_config, "_DEFAULT_HEPATIC_PATH", tmp_path / "missing_gan.json")
        monkeypatch.setattr(renal_dose, "DEFAULT_RENAL_RULES_PATH", tmp_path / "missing_renal.json")
        monkeypatch.setattr(bang_luat_store, "open_read_connection", empty_pool)
        assert d4_config.try_load_default_hepatic_config() is None
        assert renal_dose.load_renal_rules().quy_tac == []

    clear_all_caches()


@pytest.mark.luong_cu_cung
def test_container_service_asker_use_db_without_local_kb_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_all_caches()
    with closing(FakeBangLuatConnection(as_dicts=True)) as conn:
        load_bang_luat(conn, ROOT)

        @contextmanager
        def fake_pool(url: str) -> Iterator[FakeBangLuatConnection]:
            yield conn

        monkeypatch.setenv("KB_SOURCE", "db")
        monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/prod")
        monkeypatch.setenv("CASE_SOURCE", "file")
        monkeypatch.setenv("CDSS_AI", "off")
        monkeypatch.setattr(bang_luat_store, "get_secret", _env_secret)
        monkeypatch.setattr(service_mod, "get_secret", _env_secret)
        monkeypatch.setattr(bang_luat_store, "open_read_connection", fake_pool)
        monkeypatch.setattr(renal_dose, "DEFAULT_RENAL_RULES_PATH", tmp_path / "missing_renal.json")
        monkeypatch.setattr(names_mod, "_DEFAULT_HOAT_CHAT_PATH", tmp_path / "missing_hc.json")
        monkeypatch.setattr(container_mod, "_ROOT", tmp_path)
        monkeypatch.setattr(container_mod, "_SHARED_RULE_CONTEXT", None)

        settings = load_settings("test")
        container = container_mod.Container(settings)
        assert container.renal_rules.quy_tac
        monkeypatch.setattr(
            container_mod,
            "get_rule_context",
            lambda: RuleContext(container.renal_rules, None, None),
        )

        asker = CaseAsker(
            llm=FakeLLM([]),
            retriever=HybridRetriever(
                HashEmbedder(8),
                NoopReranker(),
                InMemoryVectorStore(),
                Bm25Index(),
                60,
                0.0,
            ),
            query_builder=QueryBuilder(settings.retrieval),
            resolve_name=DrugNameIndex.load().resolve,
            prompt_path=ROOT / "config/prompts/hoi_them.v1.md",
            case_settings=settings.case_context,
            evidence_max_chars=settings.evidence.max_chars,
        )
        assert asker._get_renal_rules() == container.renal_rules

        service = CaseService(ROOT / "data/mock/demo", None, tmp_path / "fb.jsonl")
        try:
            assert service.list_cases().cases
        finally:
            service.shutdown()
    clear_all_caches()


def test_schema_and_tu_dien_table_names_are_disjoint() -> None:
    """Tên bảng giữa db/schema.sql và db/tu_dien.sql không được trùng nhau."""
    pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][a-zA-Z0-9_.]*)",
        re.IGNORECASE,
    )
    schema_sql = (ROOT / "db/schema.sql").read_text(encoding="utf-8")
    tu_dien_sql = (ROOT / "db/tu_dien.sql").read_text(encoding="utf-8")
    schema_tables = {m.lower() for m in pattern.findall(schema_sql)}
    tu_dien_tables = {m.lower() for m in pattern.findall(tu_dien_sql)}

    assert schema_tables
    assert tu_dien_tables
    assert schema_tables & tu_dien_tables == set()
    assert "tri_thuc.danh_muc_hoat_chat_demo" in schema_tables
    assert "tri_thuc.danh_muc_hoat_chat_demo_nhan" in schema_tables
    assert "tri_thuc.tu_dien_hoat_chat" in tu_dien_tables


def test_bang_luat_loads_all_docs_in_one_connection_and_blocks_concurrent_callers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nạp đồng thời các bảng luật chỉ mở đúng 1 kết nối DB và mỗi bảng 1 truy vấn."""
    clear_all_caches()
    with closing(FakeBangLuatConnection(as_dicts=True)) as conn:
        load_bang_luat(conn, ROOT)
        conn.statements.clear()
        open_count = 0
        entered = Event()
        proceed = Event()

        @contextmanager
        def gated_pool(_url: str) -> Iterator[FakeBangLuatConnection]:
            nonlocal open_count
            open_count += 1
            entered.set()
            assert proceed.wait(timeout=5.0)
            yield conn

        monkeypatch.setenv("KB_SOURCE", "db")
        monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/prod")
        monkeypatch.setattr(bang_luat_store, "get_secret", _env_secret)
        monkeypatch.setattr(bang_luat_store, "open_read_connection", gated_pool)

        results: dict[str, Any] = {}
        errors: list[BaseException] = []

        def worker(name: str, fn: Any) -> None:
            try:
                results[name] = fn()
            except BaseException as exc:
                errors.append(exc)

        t1 = Thread(target=worker, args=("renal", renal_dose.load_renal_rules))
        t1.start()
        assert entered.wait(timeout=5.0)
        t2 = Thread(target=worker, args=("hepatic", d4_config.try_load_default_hepatic_config))
        t2.start()
        proceed.set()
        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        assert not errors
        assert results["renal"].quy_tac
        assert results["hepatic"] is not None and results["hepatic"].quy_tac
        assert d4_config.try_load_default_lab_threshold_config() is not None
        assert d4_config.try_load_default_drug_disease_config() is not None
        assert d5_config.try_load_default_route_config() is not None
        assert d5_config.try_load_default_max_dose_config() is not None
        assert d6_config.try_load_default_toxicity_config() is not None
        assert d7_config.try_load_default_stewardship_config() is not None
        assert allergy_config.try_load_default_allergy_config() is not None
        assert duplicate_config.try_load_default_duplicate_config() is not None
        assert DrugNameIndex.load().resolve("Paracetamol") == ["acetaminophen"]

        assert open_count == 1
        meta_queries = [stmt for stmt in conn.statements if "tri_thuc.bang_luat_meta" in stmt]
        assert len(meta_queries) == 1
        assert len(conn.statements) == len(RULE_TABLES)
    clear_all_caches()
