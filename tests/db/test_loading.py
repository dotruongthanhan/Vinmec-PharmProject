"""Các giao dịch, COPY và bộ đệm được thử hoàn toàn cục bộ."""

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest

from app.db.engine import load_batch, load_embeddings, upsert_statement, verify
from app.db.mapping import TABLES
from app.db.sources import Batch, Embeddings, SourceError, prepare, read_embeddings

ROOT = Path(__file__).resolve().parents[2]


class RecordingConnection:
    """Ghi lại ranh giới SQL và rollback để không cần PostgreSQL."""

    def __init__(self, fail_at: str = "") -> None:
        self.statements: list[tuple[str, Any]] = []
        self.committed: list[tuple[str, Any]] = []
        self.fail_at = fail_at
        self.rowcount = 0
        self.copy_rows: list[tuple[Any, ...]] = []
        self.answer: tuple[Any, ...] = (0,)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
        except Exception:
            self.committed.clear()
            raise
        else:
            self.committed.extend(self.statements)

    @contextmanager
    def cursor(self) -> Iterator["RecordingConnection"]:
        yield self

    def execute(self, query: Any, params: Any = None) -> "RecordingConnection":
        text = query if isinstance(query, str) else query.as_string()
        self.statements.append((text, params))
        if self.fail_at and self.fail_at in text:
            raise RuntimeError("lỗi giữa lượt")
        if "to_regclass" in text:
            self.answer = tuple(params)
        elif "FILTER" in text:
            self.answer = (0, 0)
        else:
            self.answer = (0,)
        return self

    def fetchone(self) -> tuple[Any, ...]:
        return self.answer

    def executemany(self, query: Any, rows: Any) -> None:
        for row in rows:
            self.execute(query, row)
        self.rowcount = 0

    @contextmanager
    def copy(self, query: Any) -> Iterator["RecordingConnection"]:
        self.execute(query)
        yield self

    def write_row(self, row: tuple[Any, ...]) -> None:
        self.copy_rows.append(row)


def test_load_rolls_back_if_child_insert_fails() -> None:
    batch = prepare("cases", ROOT)
    connection = RecordingConnection('INSERT INTO "nghiep_vu"."chan_doan"')
    with pytest.raises(RuntimeError, match="giữa lượt"):
        load_batch(connection, batch, "cases", replace=True)
    assert not connection.committed
    assert any("DELETE" in text for text, _ in connection.statements)
    assert not any("CASCADE" in text for text, _ in connection.statements)
    assert not any('DELETE FROM "tri_thuc"' in text for text, _ in connection.statements)


def test_ddinter_counts_copy_and_upsert() -> None:
    batch = prepare("ddinter", ROOT)
    name = "tri_thuc.tuong_tac_sang_loc"
    assert batch.source_counts[name] == 507655
    assert len(batch.rows[name]) == 234981
    assert not batch.rejected
    small = Batch((name,))
    small.rows[name] = batch.rows[name][:2]
    connection = RecordingConnection()
    load_batch(connection, small, "ddinter", replace=True)
    assert len(connection.copy_rows) == 2
    statements = [text for text, _ in connection.statements]
    assert any(text.startswith("COPY") for text in statements)
    assert any("INSERT INTO" in text and "ON CONFLICT" in text for text in statements)
    assert all(row["ddinter_id_a"] < row["ddinter_id_b"] for row in batch.rows[name])


def test_kb_upsert_only_preserves_embedding_when_text_is_unchanged() -> None:
    sql = upsert_statement(TABLES["tri_thuc.doan_trich"]).as_string()
    insert, update = sql.split("ON CONFLICT", 1)
    assert "embedding" not in insert
    assert 'IS NOT DISTINCT FROM EXCLUDED."noi_dung_nhung"' in update
    assert 'THEN "tri_thuc"."doan_trich"."embedding" ELSE NULL END' in update


def test_bad_catalog_row_is_logged_without_aborting_below_limit(tmp_path: Path) -> None:
    from app.db.sources import read_json

    path = ROOT / "data/kb/hoat_chat.json"
    original = read_json(path)
    catalog = json.loads(json.dumps(original))
    del catalog["hoat_chat"][0]["hoat_chat_id"]

    def source(candidate: Path) -> Any:
        return catalog if candidate == path else read_json(candidate)

    with patch("app.db.sources.read_json", side_effect=source):
        batch = prepare("kb", ROOT)
    assert any(error.bang == "tri_thuc.hoat_chat" for error in batch.rejected)
    batch.finish(tmp_path / "nap_loi.jsonl")
    assert "hoat_chat_id" in (tmp_path / "nap_loi.jsonl").read_text(encoding="utf-8")


def test_embeddings_reads_exact_model_doc_key_and_leaves_cache_unchanged(tmp_path: Path) -> None:
    cache = tmp_path / "embeddings.sqlite"
    vector = np.ones(2048, dtype=np.float32)
    with sqlite3.connect(cache) as connection:
        connection.execute("CREATE TABLE embeddings (key TEXT PRIMARY KEY, dims INTEGER, vec BLOB)")
        for model, kind, text in (
            ("model", "doc", "first"),
            ("other", "doc", "second"),
            ("model", "query", "third"),
        ):
            key = hashlib.sha256(f"{model}\n{kind}\n{text}".encode()).hexdigest()
            connection.execute(
                "INSERT INTO embeddings VALUES (?, ?, ?)", (key, 2048, vector.tobytes())
            )
    before = cache.read_bytes()
    chunks = [
        {"doan_trich_id": str(i), "noi_dung_nhung": text}
        for i, text in enumerate(("first", "second", "third"))
    ]
    result = read_embeddings(chunks, cache, "model")
    assert list(result.vectors) == ["0"]
    assert result.missing == 2
    assert cache.read_bytes() == before


def test_missing_cache_is_not_created(tmp_path: Path) -> None:
    path = tmp_path / "absent.sqlite"
    result = read_embeddings([{"doan_trich_id": "one", "noi_dung_nhung": "text"}], path, "model")
    assert result.missing == 1 and not result.vectors
    assert not path.exists()


def test_bad_cached_vector_is_rejected_and_logged_at_five_percent(tmp_path: Path) -> None:
    cache = tmp_path / "invalid.sqlite"
    key = hashlib.sha256(b"model\ndoc\ntext-0").hexdigest()
    with sqlite3.connect(cache) as connection:
        connection.execute("CREATE TABLE embeddings (key TEXT PRIMARY KEY, dims INTEGER, vec BLOB)")
        connection.execute("INSERT INTO embeddings VALUES (?, ?, ?)", (key, 2048, b"bad"))
    chunks = [{"doan_trich_id": str(i), "noi_dung_nhung": f"text-{i}"} for i in range(20)]
    result = read_embeddings(chunks, cache, "model")
    assert not result.vectors
    assert result.missing == 20
    assert len(result.rejected) == 1
    result.finish(tmp_path / "nap_loi.jsonl")
    assert "embedding" in (tmp_path / "nap_loi.jsonl").read_text(encoding="utf-8")


def test_embedding_replace_rolls_back_when_chunk_absent() -> None:
    connection = RecordingConnection()
    with pytest.raises(SourceError, match="thiếu doan_trich_id"):
        load_embeddings(connection, Embeddings(vectors={"missing": "[1]"}), replace=True)
    assert not connection.committed


def test_verify_fails_on_count_discrepancy_and_never_writes() -> None:
    connection = RecordingConnection()
    assert not verify(connection, {"nghiep_vu.nguoi_benh": 1}, Embeddings())
    assert all(
        not any(
            token in statement.upper() for token in ("INSERT", "UPDATE", "DELETE", "DROP", "CREATE")
        )
        for statement, _ in connection.statements
    )


def test_missing_allergy_status_is_rejected() -> None:
    batch = Batch()
    batch.add("nghiep_vu.nguoi_benh", {"nguoi_benh_id": "NB-DEMO-01"}, "demo.json")
    assert batch.rejected
    assert "tinh_trang_di_ung" in batch.rejected[0].ly_do


def test_verify_checks_view_and_composite_order_reference() -> None:
    from app.db.mapping import ACTIVE_DRUG_VIEW

    connection = RecordingConnection()
    assert verify(connection, {ACTIVE_DRUG_VIEW: 0}, Embeddings())
    statements = [text for text, _ in connection.statements]
    assert any('SELECT count(*) FROM "nghiep_vu"."v_thuoc_dang_dung"' == q for q in statements)
    assert any('c."y_lenh_id" = p."y_lenh_id" AND c."ca_id" = p."ca_id"' in q for q in statements)
    assert any('c."thay_the_y_lenh_id" = p."y_lenh_id"' in q for q in statements)
    assert any("EXCEPT SELECT * FROM expected" in q for q in statements)
    assert any("GROUP BY ca_id HAVING count(*) > 1" in q for q in statements)


@pytest.mark.parametrize("query_fragment", ["v_thuoc_dang_dung", "GROUP BY ca_id", 'c."ca_id"'])
def test_verify_reports_new_view_or_case_constraint_discrepancy(query_fragment: str) -> None:
    class InconsistentConnection(RecordingConnection):
        def execute(self, query: Any, params: Any = None) -> "InconsistentConnection":
            super().execute(query, params)
            statement = self.statements[-1][0]
            if "to_regclass" not in statement and query_fragment in statement:
                self.answer = (1,)
            return self

    assert not verify(InconsistentConnection(), {"nghiep_vu.v_thuoc_dang_dung": 0}, Embeddings())
