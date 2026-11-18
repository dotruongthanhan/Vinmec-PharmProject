"""Kiểm tra ánh xạ và chuyển dữ liệu nguồn, không dùng PostgreSQL."""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_mapping_matches_schema_and_rls() -> None:
    from app.db.mapping import TABLES

    sql = (ROOT / "db/schema.sql").read_text(encoding="utf-8")
    blocks = dict(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+\.\w+) \(\n(.*?)\n\);", sql, re.S))
    assert set(blocks) == set(TABLES)
    for name, table in TABLES.items():
        columns = set(
            re.findall(
                r"^    (\w+) (?:text|integer|double|boolean|timestamptz|jsonb|halfvec|tsvector)",
                blocks[name],
                re.M,
            )
        )
        additions = re.search(rf"ALTER TABLE {re.escape(name)}\n(.*?);", sql, re.S)
        if additions:
            columns.update(re.findall(r"ADD COLUMN IF NOT EXISTS (\w+) ", additions.group(1)))
        assert columns == set(table.column_names) | set(table.generated_columns), name
        assert f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY;" in sql
    assert "CREATE POLICY" not in sql
    assert "halfvec(2048)" in sql
    assert "halfvec_cosine_ops" in sql
    assert "USING gin" in sql


def test_six_cases_preserve_source_counts_and_foreign_keys() -> None:
    from unittest.mock import patch

    from app.db.sources import prepare, read_cases

    demo = [(path, case) for path, case in read_cases(ROOT) if path.parent.name == "demo"]
    with patch("app.db.sources.read_cases", return_value=demo):
        batch = prepare("cases", ROOT)
    cases = [
        json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "data/mock/demo").glob("*.json")
    ]
    expected = {
        "nguoi_benh": 6,
        "dot_dieu_tri": 6,
        "di_ung": 1,
        "chan_doan": 6,
        "sinh_hieu": 13,
        "ket_qua_xet_nghiem": 9,
        "vi_sinh": 1,
        "dien_bien": 6,
        "y_lenh": 6,
        "chi_tiet_y_lenh": 6,
        "lich_dung": 13,
        "lan_tham_dinh": 6,
        "nhan_dinh": 5,
        "can_cu": 0,
        "phan_hoi": 0,
    }
    for table, count in expected.items():
        assert len(batch.rows[f"nghiep_vu.{table}"]) == count, table
    for source, table in (
        ("sinh_hieu", "sinh_hieu"),
        ("xet_nghiem", "ket_qua_xet_nghiem"),
        ("vi_sinh", "vi_sinh"),
    ):
        assert len(batch.rows[f"nghiep_vu.{table}"]) == sum(len(c[source]) for c in cases)
    assert not batch.rejected
    assert batch.orphans() == []
    assert batch.rows["nghiep_vu.nguoi_benh"][0]["tinh_trang_di_ung"]["trang_thai"]


def test_load_order_respects_foreign_keys() -> None:
    from app.db.mapping import TABLES

    positions = {name: i for i, name in enumerate(TABLES)}
    for name, table in TABLES.items():
        for reference in table.foreign_keys:
            if reference.table != name:
                assert positions[reference.table] < positions[name]


def test_invalid_row_names_missing_field_and_rejection_threshold(tmp_path: Path) -> None:
    from app.db.sources import Batch, RejectionLimitError

    batch = Batch()
    for index in range(19):
        batch.add(
            "nghiep_vu.nguoi_benh",
            {"nguoi_benh_id": str(index), "tinh_trang_di_ung": {"trang_thai": "chua_co_thong_tin"}},
            "demo.json",
        )
    batch.add("nghiep_vu.nguoi_benh", {"tuoi": 30}, "demo.json")
    assert len(batch.rows["nghiep_vu.nguoi_benh"]) == 19
    assert "nguoi_benh_id" in batch.rejected[0].ly_do
    batch.finish(tmp_path / "nap_loi.jsonl")
    assert "nguoi_benh_id" in (tmp_path / "nap_loi.jsonl").read_text(encoding="utf-8")
    batch.add("nghiep_vu.nguoi_benh", {"nguoi_benh_id": "bad", "tuoi": "sai"}, "demo.json")
    with pytest.raises(RejectionLimitError, match="5%"):
        batch.finish(tmp_path / "nap_loi.jsonl")


def test_kb_preserves_every_chunk_field_and_renal_values() -> None:
    from app.db.sources import prepare

    batch = prepare("kb", ROOT)
    chunks = [
        json.loads(line)
        for line in (ROOT / "data/kb_curated/chunks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    raw = chunks[0]
    first = batch.rows["tri_thuc.doan_trich"][0]
    assert {key: first[key] for key in raw} == raw
    assert len(batch.rows["tri_thuc.tai_lieu"]) == len({row["tai_lieu_id"] for row in chunks})
    assert len(batch.rows["tri_thuc.doan_trich"]) == len(chunks)
    assert Counter(row["crcl_tu"] for row in batch.rows["tri_thuc.quy_tac_lieu_than"]) == Counter(
        [50, 26, 10, None]
    )
    assert not batch.rejected
    assert batch.orphans() == []
