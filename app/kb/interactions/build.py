"""Dựng SQLite xác định từ các tệp DDInter cục bộ, không gọi mạng."""

import json
import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import closing
from itertools import groupby
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from app.kb.interactions.models import SEVERITIES

INDEX_PATH = Path("data/kb_curated/tuong_tac/ddinter.sqlite")
SOURCE_DIR = Path("data/kb_staging/ddinter")
REPORT_PATH = Path("data/kb_reports/T55_bang_tuong_tac.json")
_SCHEMA = """
CREATE TABLE cap(
    ddinter_id_a TEXT NOT NULL, ddinter_id_b TEXT NOT NULL,
    muc_do TEXT NOT NULL, muc_do_so INTEGER NOT NULL, co_che_json TEXT NOT NULL,
    co_lech_muc INTEGER NOT NULL, cac_muc_nguon_json TEXT NOT NULL,
    ma_trang_cap_json TEXT NOT NULL, hau_qua TEXT, xu_tri TEXT,
    tai_lieu_json TEXT NOT NULL, url_goc TEXT,
    PRIMARY KEY(ddinter_id_a, ddinter_id_b), CHECK(ddinter_id_a < ddinter_id_b)
) WITHOUT ROWID;
CREATE TABLE thuoc(ddinter_id TEXT PRIMARY KEY, ten TEXT NOT NULL, da_cao_du INTEGER NOT NULL);
CREATE TABLE thuc_an(
    ddinter_id TEXT NOT NULL, thuc_an TEXT NOT NULL, muc_do TEXT NOT NULL,
    mo_ta TEXT, xu_tri TEXT, co_che_json TEXT NOT NULL
);
CREATE TEMP TABLE raw(
    a TEXT, b TEXT, muc TEXT, so INTEGER, co TEXT, trang INTEGER
);
"""
SourceRow = dict[str, Any]


def _rows(path: Path) -> Iterator[SourceRow]:
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _text(value: str | None) -> str | None:
    return None if value is None or value.strip().casefold() in {"", "-", "none", "n/a"} else value


def _fill(db: sqlite3.Connection, source: Path) -> dict[str, object]:
    counts: Counter[str] = Counter()
    self_rows = 0

    def observations() -> Iterator[tuple[object, ...]]:
        nonlocal self_rows
        for row in _rows(source / "tuong_tac_thuoc.jsonl"):
            a, b = sorted((row["ddinter_id_a"], row["ddinter_id_b"]))
            if row["muc_do"] not in SEVERITIES:
                raise ValueError("Cặp DDInter không hợp lệ")
            counts[row["tu_trang_cua"]] += 1
            if a == b:
                self_rows += 1
                continue
            yield a, b, row["muc_do"], row["muc_do_so"], _json(row["co_che"]), row["ma_trang_cap"]

    db.executemany("INSERT INTO raw VALUES (?, ?, ?, ?, ?, ?)", observations())
    details = {row["ma_trang_cap"]: row for row in _rows(source / "tuong_tac_chi_tiet.jsonl")}
    levels: Counter[str] = Counter(dict.fromkeys(SEVERITIES, 0))
    conflicts = detailed = 0
    cursor = db.execute("SELECT * FROM raw ORDER BY a, b, muc, trang, co")
    for (a, b), values in groupby(cursor, key=lambda row: (row[0], row[1])):
        rows = list(values)
        levels_found = sorted({row[2] for row in rows}, key=SEVERITIES.index)
        severity = levels_found[0]
        pages = sorted({row[5] for row in rows if row[5] is not None})
        mechanisms = sorted({item for row in rows for item in json.loads(row[4])})
        candidates = [
            details[page]
            for page in pages
            if page in details
            and sorted((details[page]["ddinter_id_a"], details[page]["ddinter_id_b"])) == [a, b]
        ]
        candidates.sort(key=lambda row: (row["muc_do"] != severity, row["ma_trang_cap"]))
        detail = candidates[0] if candidates else {}
        selected_pages = sorted(
            {row[5] for row in rows if row[2] == severity and row[5] is not None}
        )
        source_page = detail.get("ma_trang_cap") or (selected_pages[0] if selected_pages else None)
        url = detail.get("url_goc") or (
            f"https://ddinter2.scbdd.com/server/interact/{source_page}/" if source_page else None
        )
        db.execute(
            "INSERT INTO cap VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                a,
                b,
                severity,
                max(row[3] for row in rows if row[2] == severity),
                _json(mechanisms),
                len(levels_found) > 1,
                _json(levels_found),
                _json(pages),
                _text(detail.get("hau_qua")),
                _text(detail.get("xu_tri")),
                _json(detail.get("tai_lieu", [])),
                url,
            ),
        )
        levels[severity] += 1
        conflicts += len(levels_found) > 1
        detailed += bool(detail)
    complete = 0
    for row in sorted(_rows(source / "thuoc.jsonl"), key=lambda row: row["ddinter_id"]):
        total = row.get("tong_tuong_tac_tren_trang", {}).get("tuong_tac_thuoc")
        done = total is not None and counts[row["ddinter_id"]] == total
        db.execute("INSERT INTO thuoc VALUES (?, ?, ?)", (row["ddinter_id"], row["ten"], done))
        complete += done
    foods = sorted(_rows(source / "tuong_tac_thuc_an.jsonl"), key=_json)
    for row in foods:
        db.execute(
            "INSERT INTO thuc_an VALUES (?, ?, ?, ?, ?, ?)",
            (
                row["ddinter_id"],
                row["thuc_an"],
                row["muc_do"],
                _text(row.get("mo_ta")),
                _text(row.get("xu_tri")),
                _json(row.get("co_che", [])),
            ),
        )
    return {
        "so_cap": sum(levels.values()),
        "so_cap_theo_muc": dict(levels),
        "so_cap_lech_muc": conflicts,
        "so_cap_co_chi_tiet": detailed,
        "so_thuoc_da_cao_du": complete,
        "so_tuong_tac_thuc_an": len(foods),
        "so_dong_tu_than_bo_qua": self_rows,
    }


def build_index(root: Path = Path(".")) -> dict[str, object]:
    """Ghi tệp mới, chỉ thay nguyên tử sau khi hoàn tất và kiểm toàn vẹn."""
    destination = root / INDEX_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = root / SOURCE_DIR
    paths = [
        source / f"{name}.jsonl"
        for name in ("thuoc", "tuong_tac_thuoc", "tuong_tac_chi_tiet", "tuong_tac_thuc_an")
    ]
    versions = {path: (path.stat().st_size, path.stat().st_mtime_ns) for path in paths}
    with NamedTemporaryFile(dir=destination.parent, suffix=".sqlite", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with closing(sqlite3.connect(temporary)) as db:
            db.executescript(_SCHEMA)
            report = _fill(db, source)
            db.commit()
            if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError("Bảng tương tác không toàn vẹn")
        if any(
            (path.stat().st_size, path.stat().st_mtime_ns) != value
            for path, value in versions.items()
        ):
            raise RuntimeError("Nguồn DDInter thay đổi trong khi dựng; hãy chạy lại")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    report_path = root / REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report
