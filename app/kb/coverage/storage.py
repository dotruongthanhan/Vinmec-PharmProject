"""Nạp nguồn cục bộ chỉ đọc và ghi hai tệp báo cáo độ phủ."""

import csv
import json
import sqlite3
from collections import Counter
from collections.abc import Iterator, Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

from app.kb.coverage.models import (
    DEFAULT_REQUIRED,
    AxisIngredient,
    CoverageData,
    CoverageRow,
    CoverageSummary,
    LabelChunk,
)
from app.kb.coverage.report import calculate_coverage, validate_required_sources
from app.kb.names import normalize_key

Row = dict[str, Any]


def _read_jsonl(path: Path) -> Iterator[Row]:
    """Đọc lần lượt để không giữ bảng tương tác lớn trong bộ nhớ."""
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _read_catalog(path: Path) -> set[str] | None:
    """Giữ trạng thái chưa có nguồn khi thiếu tệp mục lục."""
    if not path.is_file():
        return None
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = {normalize_key(field): field for field in reader.fieldnames or []}
        column = next(
            (
                headers[key]
                for key in (
                    "ten inn",
                    "ten hoat chat",
                    "hoat chat",
                    "ten thuoc",
                    "ten",
                    "drug name",
                    "name",
                    "drug",
                    "title",
                )
                if key in headers
            ),
            None,
        )
        if column is None:
            raise ValueError(f"Thieu cot ten hoat chat trong {path}")
        return {row[column].strip() for row in reader if row.get(column, "").strip()}


def _read_ndc(folder: Path) -> set[str]:
    """Đọc tên thành phần ở dữ liệu NDC gốc và bản đệm đã rút gọn."""
    names: set[str] = set()
    for path in sorted(folder.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        products = (
            payload
            if isinstance(payload, list)
            else payload.get("results", payload.get("san_pham", [payload]))
        )
        for product in products:
            for ingredient in product.get("active_ingredients", []):
                if ingredient.get("name"):
                    names.add(ingredient["name"])
            for ingredient in product.get("ham_luong", []):
                if ingredient.get("hoat_chat"):
                    names.add(ingredient["hoat_chat"])
    return names


def load_sources(root: Path) -> CoverageData:
    """Mở SQLite ở chế độ chỉ đọc; không dựng lại bất kỳ nguồn nào."""
    data = root / "data"
    path = data / "kb_curated/tra_cuu/tra_cuu.sqlite"
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        records = db.execute("""
            SELECT h.*, COALESCE(p.so_che_pham, 0) AS so_che_pham_dav,
                EXISTS(SELECT 1 FROM chuyen_ma_ca c
                    WHERE c.hoat_chat_id = h.hoat_chat_id) AS trong_ca_gia_lap
            FROM hoat_chat h LEFT JOIN (
                SELECT hoat_chat_id, COUNT(DISTINCT thuoc_id) AS so_che_pham
                FROM thuoc_thanh_phan GROUP BY hoat_chat_id
            ) p ON p.hoat_chat_id = h.hoat_chat_id
            ORDER BY h.hoat_chat_id
        """).fetchall()
    axis = [
        AxisIngredient.model_validate({**dict(row), "ma_atc": json.loads(row["ma_atc_json"])})
        for row in records
    ]
    staging = data / "kb_staging/ddinter"
    totals = {
        row["ddinter_id"]: row.get("tong_tuong_tac_tren_trang", {}).get("tuong_tac_thuoc")
        for row in _read_jsonl(staging / "thuoc.jsonl")
    }
    counts = Counter(row["tu_trang_cua"] for row in _read_jsonl(staging / "tuong_tac_thuoc.jsonl"))
    chunks = [
        LabelChunk.model_validate(row)
        for row in _read_jsonl(data / "kb_curated/chunks.jsonl")
        if row.get("nguon") == "openfda"
    ]
    return CoverageData(
        hoat_chat=axis,
        doan_nhan=chunks,
        tong_ddinter=totals,
        so_dong_ddinter=dict(counts),
        ten_ndc=_read_ndc(data / "kb_sources/openfda_ndc"),
        ten_livertox=_read_catalog(data / "kb_sources/livertox/muc_luc.csv"),
        ten_lactmed=_read_catalog(data / "kb_sources/lactmed/muc_luc.csv"),
    )


def report(root: Path, *, required_sources: Sequence[str] = DEFAULT_REQUIRED) -> CoverageSummary:
    """Ghi ma trận CSV có BOM và tóm tắt JSON, trả tóm tắt cho CLI."""
    required = validate_required_sources(required_sources)
    rows, summary = calculate_coverage(load_sources(root), required_sources=required)
    folder = root / "data/kb_reports"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "do_phu_da_nguon.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CoverageRow.model_fields))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: ";".join(value) if isinstance(value, list) else value
                    for key, value in row.model_dump().items()
                }
            )
    (folder / "do_phu_da_nguon.json").write_text(
        summary.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return summary
