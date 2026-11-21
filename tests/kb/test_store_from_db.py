"""Kiểm tra nạp chỉ mục tra cứu, DDInter và kho đoạn từ PostgreSQL và cấu hình kb_source."""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import psycopg
import pytest

from app import container as container_mod
from app.config import settings as settings_mod
from app.config.settings import load_kb_source, load_settings
from app.container import Container
from app.core.errors import ConfigError, RetrievalError
from app.core.types import Chunk
from app.db import chi_muc, cli
from app.domain.models import CaBenh
from app.kb.interactions import InteractionStore
from app.kb.interactions import build as ddinter_build
from app.kb.resolver import DrugResolver
from app.kb.resolver import build as resolver_build
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.orchestration import evidence as evidence_mod
from app.orchestration.evidence import LazyRetrieverFactory
from app.retrieval.corpus import load_corpus, load_corpus_from_db
from app.rules.interaction import check_with_matrix
from tests.core.test_types import make_chunk
from tests.kb.test_interactions import write_sources

ROOT = Path(__file__).resolve().parents[2]
RESOLVER_FIXTURE = Path(__file__).parent / "fixtures/resolver"

_FAKE_PG_SCHEMA = """
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
CREATE TABLE tra_cuu_hoat_chat (
    hoat_chat_id TEXT PRIMARY KEY,
    ten_inn TEXT NOT NULL,
    ten_viet TEXT,
    rxcui TEXT,
    ma_atc_json TEXT NOT NULL,
    loai TEXT NOT NULL,
    ddinter_id TEXT UNIQUE,
    ddinter_cach_khop TEXT
);
CREATE TABLE tra_cuu_dong_nghia (
    khoa_chuan_hoa TEXT NOT NULL,
    hoat_chat_id TEXT NOT NULL,
    loai TEXT NOT NULL,
    cach_khop TEXT NOT NULL,
    PRIMARY KEY (khoa_chuan_hoa, hoat_chat_id, loai, cach_khop)
);
CREATE TABLE tra_cuu_thuoc (
    khoa_ten_thuoc TEXT NOT NULL,
    thuoc_id TEXT PRIMARY KEY,
    ten_thuoc TEXT NOT NULL,
    so_dang_ky TEXT,
    dang_bao_che TEXT
);
CREATE TABLE tra_cuu_thuoc_thanh_phan (
    thuoc_id TEXT NOT NULL,
    hoat_chat_id TEXT NOT NULL,
    ham_luong REAL,
    don_vi TEXT,
    PRIMARY KEY (thuoc_id, hoat_chat_id)
);
CREATE TABLE tra_cuu_chuyen_ma_ca (
    ma_ca TEXT PRIMARY KEY,
    hoat_chat_id TEXT NOT NULL,
    cach_khop TEXT NOT NULL
);
CREATE TABLE tra_cuu_meta (
    phien_ban TEXT,
    ngay_dung TEXT,
    nguon_tep_json TEXT,
    sha256_json TEXT
);
CREATE TABLE doan_trich (
    doan_trich_id TEXT PRIMARY KEY,
    tai_lieu_id TEXT NOT NULL,
    muc_cha_id TEXT,
    nhom_nguon TEXT NOT NULL,
    nguon TEXT NOT NULL,
    tang_tin_cay INTEGER NOT NULL,
    hoat_chat_ids TEXT NOT NULL,
    muc TEXT NOT NULL,
    duong_dan_muc TEXT NOT NULL,
    loai_noi_dung TEXT NOT NULL,
    ngon_ngu TEXT NOT NULL,
    phien_ban_nguon TEXT,
    url_goc TEXT,
    noi_dung_goc TEXT NOT NULL,
    noi_dung_nhung TEXT NOT NULL,
    embedding TEXT,
    tu_khoa TEXT,
    nap_luc TEXT,
    nguon_tep TEXT
);
"""


class FakePsycopgCursor:
    """Con trỏ giả trả hàng tuple hoặc dict như psycopg 3."""

    def __init__(self, rows: list[Any], *, single_row: tuple[Any, ...] | None = None) -> None:
        self._rows = rows
        self._single_row = single_row

    def fetchall(self) -> list[Any]:
        return list(self._rows)

    def fetchone(self) -> tuple[Any, ...] | None:
        if self._single_row is not None:
            return self._single_row
        return self._rows[0] if self._rows else None

    def __iter__(self) -> Iterator[Any]:
        return iter(self._rows)


class FakeCopySession:
    """Bối cảnh COPY giả ghi trực tiếp vào bảng SQLite đích."""

    def __init__(self, db: sqlite3.Connection, table: str, columns: list[str]) -> None:
        self._db = db
        self._table = table
        self._columns = columns
        self.rows_written = 0

    def write_row(self, row: tuple[Any, ...]) -> None:
        placeholders = ", ".join("?" for _ in self._columns)
        col_list = ", ".join(f'"{col}"' for col in self._columns)
        self._db.execute(
            f'INSERT INTO "{self._table}" ({col_list}) VALUES ({placeholders})',
            row,
        )
        self.rows_written += 1


class FakePsycopgConnection:
    """Kết nối giả dùng SQLite trong bộ nhớ để mô phỏng bảng PostgreSQL tri_thuc.*."""

    def __init__(self, *, as_dicts: bool = False, skip_table_copy: str | None = None) -> None:
        self._db = sqlite3.connect(":memory:", isolation_level=None)
        self._db.executescript(_FAKE_PG_SCHEMA)

        def _has_any(raw_json: str, ids_json: str) -> int:
            return int(bool(set(json.loads(raw_json)) & set(json.loads(ids_json))))

        self._db.create_function("pg_jsonb_has_any", 2, _has_any)
        self.as_dicts = as_dicts
        self.skip_table_copy = skip_table_copy
        self.committed = False
        self.rolled_back = False
        self.statements: list[str] = []

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> FakePsycopgConnection:
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

    @contextmanager
    def cursor(self) -> Iterator[FakePsycopgConnection]:
        yield self

    def _to_sqlite_sql(self, text: str) -> str:
        return text.replace('"tri_thuc".', "").replace("tri_thuc.", "")

    def execute(self, query: Any, params: Any = None) -> FakePsycopgCursor:
        text = query if isinstance(query, str) else query.as_string()
        self.statements.append(text)
        if text.startswith("SET TRANSACTION"):
            return FakePsycopgCursor([])
        if text.startswith("TRUNCATE "):
            for table in re.findall(r'"tri_thuc"\."(\w+)"', text):
                self._db.execute(f'DELETE FROM "{table}"')
            return FakePsycopgCursor([])
        if "SELECT to_regclass" in text:
            table_name = str(params[0]).removeprefix("tri_thuc.")
            found = self._db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()
            return FakePsycopgCursor([], single_row=(found[0],) if found else (None,))
        sqlite_sql = self._to_sqlite_sql(text)
        exec_params: Any = params or ()
        if "hoat_chat_ids ?| %s" in sqlite_sql:
            sqlite_sql = sqlite_sql.replace(
                "hoat_chat_ids ?| %s",
                "pg_jsonb_has_any(hoat_chat_ids, %s)",
            )
            param_list = list(exec_params)
            param_list[0] = json.dumps(list(param_list[0]))
            exec_params = tuple(param_list)
        if "WHERE (ddinter_id_a, ddinter_id_b) IN ((" in sqlite_sql:
            sqlite_sql = sqlite_sql.replace(
                "WHERE (ddinter_id_a, ddinter_id_b) IN (",
                "WHERE (ddinter_id_a, ddinter_id_b) IN (VALUES ",
            )
        sqlite_sql = sqlite_sql.replace("%s", "?")
        cur = self._db.execute(sqlite_sql, exec_params)
        columns = [desc[0] for desc in cur.description or ()]
        raw_rows = cur.fetchall()
        if not self.as_dicts or "count(*)" in text.lower():
            return FakePsycopgCursor(raw_rows)
        dict_rows: list[dict[str, Any]] = []
        for row in raw_rows:
            mapped = dict(zip(columns, row, strict=True))
            if "hoat_chat_ids" in mapped and isinstance(mapped["hoat_chat_ids"], str):
                mapped["hoat_chat_ids"] = json.loads(mapped["hoat_chat_ids"])
            dict_rows.append(mapped)
        return FakePsycopgCursor(dict_rows)

    @contextmanager
    def copy(self, query: Any) -> Iterator[FakeCopySession]:
        text = query if isinstance(query, str) else query.as_string()
        self.statements.append(text)
        match = re.match(r'^COPY "tri_thuc"\."(\w+)" \(([^)]+)\) FROM STDIN$', text)
        assert match is not None, f"Câu COPY không khớp mẫu: {text}"
        table = match.group(1)
        columns = [col.strip().strip('"') for col in match.group(2).split(",")]
        session = FakeCopySession(self._db, table, columns)
        yield session
        if self.skip_table_copy == f"tri_thuc.{table}":
            self._db.execute(
                f'DELETE FROM "{table}" WHERE rowid = (SELECT max(rowid) FROM "{table}")'
            )


def _build_small_resolver_sqlite(root: Path) -> Path:
    (root / resolver_build.DICTIONARY_DIR).mkdir(parents=True)
    for name in ("hoat_chat", "dong_nghia", "thuoc", "thuoc_thanh_phan"):
        src = RESOLVER_FIXTURE / f"{name}.jsonl"
        shutil.copyfile(src, root / resolver_build.DICTIONARY_DIR / f"{name}.jsonl")
    (root / resolver_build.DDINTER_PATH.parent).mkdir(parents=True)
    shutil.copyfile(RESOLVER_FIXTURE / "ddinter.jsonl", root / resolver_build.DDINTER_PATH)
    for folder in ("demo", "hoso_gia_lap"):
        dest = root / "data/mock" / folder
        dest.mkdir(parents=True)
        data = json.loads((RESOLVER_FIXTURE / "ca.json").read_text(encoding="utf-8"))
        data["ca_id"] += f"-{folder}"
        (dest / "ca.json").write_text(json.dumps(data), encoding="utf-8")
    resolver_build.build_index(root)
    return root / resolver_build.INDEX_PATH


def _build_small_ddinter_sqlite(root: Path) -> Path:
    write_sources(root)
    ddinter_build.build_index(root)
    return root / ddinter_build.INDEX_PATH


_INSERT_CHUNK_SQL = f"INSERT INTO doan_trich VALUES ({', '.join('?' for _ in range(19))})"


def _seed_chunks_in_fake_pg(
    conn: FakePsycopgConnection,
    chunks: list[Chunk],
    *,
    embeddings: Mapping[str, str | None] | None = None,
) -> None:
    default_vec = json.dumps([0.01] * 2048)
    for chunk in chunks:
        vec_value = (
            embeddings[chunk.doan_trich_id]
            if embeddings is not None and chunk.doan_trich_id in embeddings
            else default_vec
        )
        conn._db.execute(
            _INSERT_CHUNK_SQL,
            (
                chunk.doan_trich_id,
                chunk.tai_lieu_id,
                chunk.muc_cha_id,
                chunk.nhom_nguon,
                chunk.nguon,
                chunk.tang_tin_cay,
                json.dumps(chunk.hoat_chat_ids),
                chunk.muc,
                chunk.duong_dan_muc,
                chunk.loai_noi_dung,
                chunk.ngon_ngu,
                chunk.phien_ban_nguon,
                chunk.url_goc,
                chunk.noi_dung_goc,
                chunk.noi_dung_nhung,
                vec_value,
                "tu khoa gia",
                "2026-11-19T00:00:00Z",
                "data/kb_curated/chunks.jsonl",
            ),
        )


@pytest.mark.parametrize("as_dicts", [False, True])
def test_interaction_store_and_resolver_from_db_match_sqlite(
    tmp_path: Path, as_dicts: bool
) -> None:
    tra_cuu_path = _build_small_resolver_sqlite(tmp_path / "res")
    ddinter_path = _build_small_ddinter_sqlite(tmp_path / "dd")
    with closing(FakePsycopgConnection(as_dicts=as_dicts)) as conn:
        results = chi_muc.load_chi_muc(conn, tra_cuu_path, ddinter_path)
        assert conn.committed
        assert all(src == dst for src, dst in results.values())

        file_store = InteractionStore.from_path(ddinter_path)
        conn.statements.clear()
        db_store = InteractionStore.from_db(conn)
        assert not any("ddinter_cap" in stmt for stmt in conn.statements)

        assert db_store.pair("A", "B") == file_store.pair("A", "B")
        after_first_pair = len(conn.statements)
        assert db_store.pair("B", "A") == file_store.pair("B", "A")
        assert db_store.pair("A", "B") == file_store.pair("A", "B")
        assert len(conn.statements) == after_first_pair

        assert db_store.pair("A", "D") is None and file_store.pair("A", "D") is None
        after_missing_pair = len(conn.statements)
        assert db_store.pair("D", "A") is None
        assert db_store.pair("E", "E") is None and file_store.pair("E", "E") is None
        assert len(conn.statements) == after_missing_pair

        batch_store = InteractionStore.from_db(conn)
        conn.statements.clear()
        batched = batch_store.pairs([("A", "B"), ("A", "D"), ("E", "E")])
        assert len(conn.statements) == 1
        assert batched == {("A", "B"): file_store.pair("A", "B")}
        assert batch_store.pair("A", "B") == file_store.pair("A", "B")
        assert batch_store.pair("A", "D") is None
        assert len(conn.statements) == 1

        for code in ("A", "B", "C", "D", "E", "missing"):
            assert db_store.drug_complete(code) is file_store.drug_complete(code)
            assert db_store.foods(code) == file_store.foods(code)

        file_resolver = DrugResolver.from_index(tra_cuu_path)
        db_resolver = DrugResolver.from_db(conn)
        for name in (
            "Augmentin",
            "Amoxicilin + acid clavulanic 875 mg/125 mg",
            "Natri clorid 0,9% 500 mL",
            "Amoxicilinn 10 mg",
            "Tên trùng công thức 10 mg",
        ):
            assert db_resolver.resolve_name(name) == file_resolver.resolve_name(name)
        case = CaBenh.model_validate_json((RESOLVER_FIXTURE / "ca.json").read_bytes())
        line = case.y_lenh_cho_duyet.chi_tiet[0]
        assert db_resolver.resolve_line(case, line) == file_resolver.resolve_line(case, line)

        file_check = check_with_matrix(case, file_resolver, file_store)
        db_check = check_with_matrix(case, db_resolver, InteractionStore.from_db(conn))
        assert db_check == file_check


def test_interaction_rule_uses_single_batch_query_on_db_store(tmp_path: Path) -> None:
    ddinter_path = _build_small_ddinter_sqlite(tmp_path / "dd")
    case = CaBenh.model_validate_json((RESOLVER_FIXTURE / "ca.json").read_bytes())
    base_line = case.y_lenh_cho_duyet.chi_tiet[0]
    case.y_lenh_cho_duyet.chi_tiet = [
        base_line.model_copy(
            update={"chi_tiet_y_lenh_id": f"CT-{code}", "thuoc_id": None, "ten_tu_do": code}
        )
        for code in ("A", "B", "D")
    ]

    class _StubResolver:
        def resolve_line(self, _ca: CaBenh, line: Any) -> KetQuaPhanGiai:
            code = line.ten_tu_do
            return KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                nguon_khop="dong_nghia",
                thanh_phan=[
                    ThanhPhanPhanGiai(
                        hoat_chat_id=f"hc_{code.lower()}",
                        ten_inn=f"Drug {code}",
                        ten_viet=None,
                        ma_atc=[],
                        ddinter_id=code,
                        loai="thuoc",
                    )
                ],
            )

    with closing(FakePsycopgConnection(as_dicts=True)) as conn:
        for spec in chi_muc.INDEX_TABLES:
            if spec.source_kind == "tuong_tac":
                with closing(sqlite3.connect(ddinter_path)) as src:
                    col_sql = ", ".join(f'"{c}"' for c in spec.columns)
                    rows = src.execute(f'SELECT {col_sql} FROM "{spec.sqlite_table}"').fetchall()
                placeholders = ", ".join("?" for _ in spec.columns)
                table = spec.pg_table.split(".", 1)[1]
                conn._db.executemany(
                    f'INSERT INTO "{table}" ({col_sql}) VALUES ({placeholders})', rows
                )

        file_store = InteractionStore.from_path(ddinter_path)
        db_store = InteractionStore.from_db(conn)
        conn.statements.clear()
        stub_resolver: Any = _StubResolver()
        db_result = check_with_matrix(case, stub_resolver, db_store)
        file_result = check_with_matrix(case, stub_resolver, file_store)
        assert db_result == file_result
        cap_queries = [stmt for stmt in conn.statements if "ddinter_cap" in stmt]
        assert len(cap_queries) == 1

        conn.statements.clear()
        assert check_with_matrix(case, stub_resolver, db_store) == file_result
        assert not [stmt for stmt in conn.statements if "ddinter_cap" in stmt]


def test_interaction_store_batch_sql_has_no_braces_and_exact_placeholders() -> None:
    with closing(FakePsycopgConnection(as_dicts=True)) as conn:
        store = InteractionStore.from_db(conn)
        conn.statements.clear()
        store.pairs([("A", "B"), ("C", "D")])
        assert len(conn.statements) == 1
        sql_text = conn.statements[0]
        assert "{" not in sql_text
        assert "}" not in sql_text
        assert sql_text.count("%s") == 4
        assert "WHERE (ddinter_id_a, ddinter_id_b) IN ((%s, %s), (%s, %s))" in sql_text


def test_interaction_store_pairs_splits_queries_into_batches_of_1000() -> None:
    with closing(FakePsycopgConnection(as_dicts=True)) as conn:
        row_1 = (
            "D0000",
            "D0001",
            "Major",
            3,
            '["ức chế"]',
            0,
            '["Major"]',
            "[1]",
            None,
            None,
            "[]",
            None,
        )
        row_2 = (
            "D2004",
            "D2005",
            "Minor",
            1,
            '["nhẹ"]',
            0,
            '["Minor"]',
            "[2]",
            None,
            None,
            "[]",
            None,
        )
        insert_sql = "INSERT INTO ddinter_cap VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        conn._db.execute(insert_sql, row_1)
        conn._db.execute(insert_sql, row_2)
        store = InteractionStore.from_db(conn)
        conn.statements.clear()
        many_pairs = [(f"D{i:04d}", f"D{i + 1:04d}") for i in range(2005)]
        found = store.pairs(many_pairs)
        assert len(conn.statements) == 3
        assert conn.statements[0].count("(%s, %s)") == 1000
        assert conn.statements[1].count("(%s, %s)") == 1000
        assert conn.statements[2].count("(%s, %s)") == 5
        assert set(found) == {("D0000", "D0001"), ("D2004", "D2005")}


@pytest.mark.parametrize("as_dicts", [False, True])
def test_load_corpus_from_db_matches_file_and_ignores_extra_columns(
    tmp_path: Path, as_dicts: bool
) -> None:
    chunks = [
        make_chunk("C-02", "Đoạn thứ hai", drug="vancomycin"),
        make_chunk("C-01", "Đoạn thứ nhất", drug="meropenem", muc="lieu_than"),
    ]
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text("\n".join(c.model_dump_json() for c in chunks) + "\n", encoding="utf-8")

    with closing(FakePsycopgConnection(as_dicts=as_dicts)) as conn:
        _seed_chunks_in_fake_pg(conn, chunks)
        from_db = load_corpus_from_db(conn)
        from_file = sorted(load_corpus(chunks_path), key=lambda item: item.doan_trich_id)
        assert from_db == from_file
        select_sql = conn.statements[-1]
        assert "ORDER BY doan_trich_id" in select_sql
        for ignored in ("embedding", "tu_khoa", "nap_luc", "nguon_tep"):
            assert ignored not in select_sql


def test_load_corpus_from_db_rejects_invalid_chunk() -> None:
    with closing(FakePsycopgConnection(as_dicts=True)) as conn:
        conn._db.execute(
            _INSERT_CHUNK_SQL,
            (
                "BAD-1",
                "doc1",
                None,
                "nhan_thuoc",
                "openfda",
                99,
                "[]",
                "lieu",
                "Duong",
                "van_ban",
                "en",
                None,
                None,
                "goc",
                "nhung",
                None,
                None,
                None,
                None,
            ),
        )
        with pytest.raises(RetrievalError, match="Đoạn không hợp lệ"):
            load_corpus_from_db(conn)


def test_lazy_retriever_factory_loads_from_db_once_and_sanitizes_errors(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    chunks = [
        make_chunk("M-1", "meropenem renal", drug="meropenem", muc="lieu_than"),
        make_chunk("W-1", "warfarin interaction", drug="warfarin", muc="tuong_tac"),
    ]
    conn = FakePsycopgConnection(as_dicts=True)
    _seed_chunks_in_fake_pg(conn, chunks)

    calls = 0

    @contextmanager
    def fake_pool_connection(url: str) -> Iterator[FakePsycopgConnection]:
        assert url == "postgresql://demo:secret@db.invalid/test"
        yield conn

    original_load_db = evidence_mod.load_corpus_for_ingredients_from_db

    def counted_load_db(connection: Any, ids: Any, **kwargs: Any) -> list[Any]:
        nonlocal calls
        calls += 1
        return original_load_db(connection, ids, **kwargs)

    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/test")
    monkeypatch.setattr(evidence_mod.read_pool, "connection", fake_pool_connection)
    monkeypatch.setattr(evidence_mod, "load_corpus_for_ingredients_from_db", counted_load_db)
    settings = load_settings("test")
    app_cfg = settings.app.model_copy(update={"kb_source": "db"})
    settings = settings.model_copy(update={"app": app_cfg})
    factory = LazyRetrieverFactory(Container(settings))

    mero = factory.for_ingredients({"meropenem"})
    assert mero.vector_store.count() == 1
    assert factory.for_ingredients({"meropenem"}) is mero
    assert calls == 1
    warfarin = factory.for_ingredients({"warfarin"})
    assert warfarin.vector_store.count() == 1
    assert calls == 2

    conn.close()

    @contextmanager
    def failing_pool(url: str) -> Iterator[Any]:
        raise psycopg.OperationalError(url)
        yield  # pragma: no cover

    monkeypatch.setattr(evidence_mod.read_pool, "connection", failing_pool)
    failing_factory = LazyRetrieverFactory(Container(settings), use_db=True)
    with caplog.at_level("WARNING", logger="app.orchestration.evidence"):
        with pytest.raises(RetrievalError, match="cơ sở dữ liệu"):
            failing_factory.for_ingredients({"meropenem"})
    assert "secret" not in caplog.text


def test_kb_source_settings_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KB_SOURCE", raising=False)
    assert load_kb_source() == "auto"
    assert load_settings("test").app.kb_source == "auto"

    for raw, expected in (("file", "file"), (" DB ", "db"), ("Auto", "auto")):
        monkeypatch.setenv("KB_SOURCE", raw)
        assert load_kb_source() == expected
        assert load_settings("test").app.kb_source == expected

    monkeypatch.setenv("KB_SOURCE", "invalid")
    with pytest.raises(ConfigError, match="KB_SOURCE"):
        load_kb_source()
    with pytest.raises(ConfigError, match="KB_SOURCE"):
        load_settings("test")


def _prepare_container_root(tmp_path: Path) -> Path:
    kb_dir = tmp_path / "data/kb"
    kb_dir.mkdir(parents=True)
    for name in ("quy_tac_lieu_than.json", "hoat_chat.json"):
        shutil.copyfile(ROOT / "data/kb" / name, kb_dir / name)
    return tmp_path


def test_container_auto_selects_file_when_present_and_db_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    root = _prepare_container_root(tmp_path)
    tra_cuu_path = _build_small_resolver_sqlite(root / "src_res")
    ddinter_path = _build_small_ddinter_sqlite(root / "src_dd")

    with closing(FakePsycopgConnection(as_dicts=True)) as conn:
        chi_muc.load_chi_muc(conn, tra_cuu_path, ddinter_path)
        _seed_chunks_in_fake_pg(conn, [make_chunk("C-1", "meropenem", drug="meropenem")])

        monkeypatch.setattr(container_mod, "_ROOT", root)
        monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/test")
        monkeypatch.setattr(settings_mod, "load_dotenv", lambda **kw: False)

        @contextmanager
        def fake_pool_connection(url: str) -> Iterator[FakePsycopgConnection]:
            yield conn

        monkeypatch.setattr(container_mod.read_pool, "connection", fake_pool_connection)
        monkeypatch.setattr(evidence_mod.read_pool, "connection", fake_pool_connection)

        # 1. auto + tệp có sẵn -> đọc tệp, không gọi DB.
        base_settings = load_settings("test")
        present_settings = base_settings.model_copy(
            update={
                "app": base_settings.app.model_copy(
                    update={
                        "tra_cuu": str(tra_cuu_path),
                        "tuong_tac": str(ddinter_path),
                        "kb_source": "auto",
                    }
                )
            }
        )
        chunks_file = root / "data/kb_curated/chunks.jsonl"
        chunks_file.parent.mkdir(parents=True)
        sample_chunk = make_chunk("F-1", "meropenem").model_dump_json()
        chunks_file.write_text(sample_chunk, encoding="utf-8")

        with (
            patch.object(DrugResolver, "from_db", side_effect=AssertionError("Không được đọc DB")),
            patch.object(
                InteractionStore, "from_db", side_effect=AssertionError("Không được đọc DB")
            ),
        ):
            file_container = Container(present_settings)
            assert file_container.drug_resolver is not None
            assert file_container.interaction_store is not None
            assert file_container.case_asker._retriever is not None
            assert file_container.case_asker._retriever._should_use_db() is False

        # 2. auto + tệp vắng + có DATABASE_URL -> đọc DB, không cảnh báo yếu tố 4.
        chunks_file.unlink()
        absent_settings = base_settings.model_copy(
            update={
                "app": base_settings.app.model_copy(
                    update={
                        "tra_cuu": str(root / "absent_tra_cuu.sqlite"),
                        "tuong_tac": str(root / "absent_ddinter.sqlite"),
                        "kb_source": "auto",
                    }
                )
            }
        )
        caplog.clear()
        with caplog.at_level("WARNING", logger="app.container"):
            db_container = Container(absent_settings)
            ctx = db_container.rule_context
            assert ctx.resolver is not None
            assert ctx.interactions is not None
            assert ctx.interactions.pair("A", "B") is not None
            assert ctx.resolver.resolve_name("Augmentin").trang_thai == "da_phan_giai"
            asker = db_container.case_asker
            assert isinstance(asker._retriever, LazyRetrieverFactory)
            assert asker._retriever._should_use_db() is True
            assert asker._retriever.for_ingredients({"meropenem"}).vector_store.count() == 1
        assert "Không chạy yếu tố 4" not in caplog.text


def test_container_kb_source_db_failure_returns_none_and_warns_without_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    root = _prepare_container_root(tmp_path)
    tra_cuu_path = _build_small_resolver_sqlite(root / "src_res")
    ddinter_path = _build_small_ddinter_sqlite(root / "src_dd")
    monkeypatch.setattr(container_mod, "_ROOT", root)
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:mat-khau-bi-mat@db.invalid/prod")

    @contextmanager
    def broken_pool(url: str) -> Iterator[Any]:
        raise psycopg.OperationalError(url)
        yield  # pragma: no cover

    monkeypatch.setattr(container_mod.read_pool, "connection", broken_pool)
    base_settings = load_settings("test")
    db_settings = base_settings.model_copy(
        update={
            "app": base_settings.app.model_copy(
                update={
                    "tra_cuu": str(tra_cuu_path),
                    "tuong_tac": str(ddinter_path),
                    "kb_source": "db",
                }
            )
        }
    )
    caplog.clear()
    with caplog.at_level("WARNING", logger="app.container"):
        container = Container(db_settings)
        ctx = container.rule_context
        assert ctx.resolver is None
        assert ctx.interactions is None
    assert len(caplog.records) == 1
    assert "Không chạy yếu tố 4" in caplog.text
    assert "tri_thuc.tra_cuu_*" in caplog.text
    assert "tri_thuc.ddinter_*" in caplog.text
    assert "mat-khau-bi-mat" not in caplog.text


def test_schema_contains_chi_muc_tables_index_and_rls() -> None:
    schema = (ROOT / "db/schema.sql").read_text(encoding="utf-8")
    expected_tables = (
        "tri_thuc.ddinter_cap",
        "tri_thuc.ddinter_thuoc",
        "tri_thuc.ddinter_thuc_an",
        "tri_thuc.tra_cuu_hoat_chat",
        "tri_thuc.tra_cuu_dong_nghia",
        "tri_thuc.tra_cuu_thuoc",
        "tri_thuc.tra_cuu_thuoc_thanh_phan",
        "tri_thuc.tra_cuu_chuyen_ma_ca",
        "tri_thuc.tra_cuu_meta",
    )
    blocks = dict(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+\.\w+) \(\n(.*?)\n\);", schema, re.S))
    revoke_pattern = r"REVOKE ALL ON\s+tri_thuc\.ddinter_cap,(.*?)FROM PUBLIC;"
    revoke_match = re.search(revoke_pattern, schema, flags=re.S)
    assert revoke_match is not None
    revoke_block = revoke_match.group(0)
    for table in expected_tables:
        assert table in blocks
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in schema
        assert table in revoke_block
    assert "id bigserial PRIMARY KEY" in blocks["tri_thuc.ddinter_thuc_an"]
    assert "ham_luong double precision" in blocks["tri_thuc.tra_cuu_thuoc_thanh_phan"]
    assert "ON tri_thuc.tra_cuu_thuoc (khoa_ten_thuoc, thuoc_id);" in schema
    assert "FROM PUBLIC;" in schema
    do_blocks = re.findall(r"DO \$\$.*?END\s*\$\$;", schema, flags=re.S)
    assert any("tri_thuc.ddinter_cap" in block and "anon" in block for block in do_blocks)
    assert any("tri_thuc.ddinter_cap" in block and "authenticated" in block for block in do_blocks)


def test_chi_muc_cli_dry_run_rollback_verify_and_all_help(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tra_cuu_path = _build_small_resolver_sqlite(tmp_path / "res")
    ddinter_path = _build_small_ddinter_sqlite(tmp_path / "dd")

    with (
        patch("app.db.cli.get_secret", side_effect=AssertionError("Không được đọc bí mật")),
        patch("psycopg.connect", side_effect=AssertionError("Không được kết nối DB")),
    ):
        code = cli.main(
            [
                "load",
                "chi-muc",
                "--dry-run",
                "--tra-cuu",
                str(tra_cuu_path),
                "--tuong-tac",
                str(ddinter_path),
            ]
        )
        assert code == 0
    dry_out = capsys.readouterr().out
    assert "tri_thuc.ddinter_cap: 1" in dry_out
    assert "tri_thuc.tra_cuu_hoat_chat:" in dry_out

    # Kiểm tra rollback khi lệch số dòng đích so với nguồn.
    bad_conn = FakePsycopgConnection(skip_table_copy="tri_thuc.ddinter_thuoc")
    monkeypatch.setattr(cli, "get_secret", lambda _name: "postgresql://fake@localhost/db")
    monkeypatch.setattr(cli.psycopg, "connect", lambda *args, **kwargs: bad_conn)
    mismatch_code = cli.main(
        [
            "load",
            "chi-muc",
            "--tra-cuu",
            str(tra_cuu_path),
            "--tuong-tac",
            str(ddinter_path),
        ]
    )
    assert mismatch_code != 0
    assert bad_conn.rolled_back is True
    assert bad_conn.committed is False
    mismatch_out = capsys.readouterr().out
    assert "tri_thuc.ddinter_thuoc: nguồn=5, CSDL=4, LỆCH" in mismatch_out

    # Kiểm tra verify chi-muc khớp khi đã nạp đủ và lệch khi thiếu dữ liệu.
    good_conn = FakePsycopgConnection()
    chi_muc.load_chi_muc(good_conn, tra_cuu_path, ddinter_path)
    capsys.readouterr()

    @contextmanager
    def keep_open_connect(*args: Any, **kwargs: Any) -> Iterator[FakePsycopgConnection]:
        assert "default_transaction_read_only=on" in kwargs["options"]
        yield good_conn

    monkeypatch.setattr(cli.psycopg, "connect", keep_open_connect)
    verify_args = [
        "verify",
        "chi-muc",
        "--tra-cuu",
        str(tra_cuu_path),
        "--tuong-tac",
        str(ddinter_path),
    ]
    assert cli.main(verify_args) == 0
    verify_out = capsys.readouterr().out
    assert "tri_thuc.ddinter_cap: nguồn=1, CSDL=1, KHỚP" in verify_out

    flag_args = [
        "verify",
        "--chi-muc",
        "--tra-cuu",
        str(tra_cuu_path),
        "--tuong-tac",
        str(ddinter_path),
    ]
    assert cli.main(flag_args) == 0
    capsys.readouterr()

    good_conn._db.execute("DELETE FROM ddinter_thuoc WHERE ddinter_id = 'A'")
    assert cli.main(verify_args) != 0
    assert "tri_thuc.ddinter_thuoc: nguồn=5, CSDL=4, LỆCH" in capsys.readouterr().out
    good_conn.close()

    help_text = cli.parser().format_help()
    assert "chi-muc" in help_text
    assert "all" in help_text
    all_help = next(
        action.choices["all"].format_help()
        for action in cli.parser()._actions
        if getattr(action, "choices", None) and "all" in action.choices
    )
    assert "chi-muc" in all_help
