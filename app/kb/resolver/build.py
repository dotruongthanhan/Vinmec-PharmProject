"""Dựng chỉ mục tra cứu và báo cáo ánh xạ từ các tệp cục bộ."""

import csv
import hashlib
import json
import os
import sqlite3
from collections import defaultdict
from collections.abc import Iterable, Iterator
from contextlib import closing
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from app.domain.models import CaBenh
from app.kb.resolver.matching import CaseMatch, IngredientNames, product_key

INDEX_PATH = Path("data/kb_curated/tra_cuu/tra_cuu.sqlite")
REPORT_DIR = Path("data/kb_reports")
CASE_CSV = "T53_chuyen_ma_ca.csv"
DDINTER_CSV = "T53_ddinter_chua_noi.csv"
DICTIONARY_DIR = Path("data/kb_curated/tu_dien")
DDINTER_PATH = Path("data/kb_staging/ddinter/thuoc.jsonl")
_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE hoat_chat(
    hoat_chat_id TEXT PRIMARY KEY, ten_inn TEXT NOT NULL, ten_viet TEXT, rxcui TEXT,
    ma_atc_json TEXT NOT NULL, loai TEXT NOT NULL, ddinter_id TEXT UNIQUE, ddinter_cach_khop TEXT
);
CREATE TABLE dong_nghia(
    khoa_chuan_hoa TEXT NOT NULL, hoat_chat_id TEXT NOT NULL REFERENCES hoat_chat,
    loai TEXT NOT NULL, cach_khop TEXT NOT NULL,
    PRIMARY KEY(khoa_chuan_hoa, hoat_chat_id, loai, cach_khop)
) WITHOUT ROWID;
CREATE TABLE thuoc(
    khoa_ten_thuoc TEXT NOT NULL, thuoc_id TEXT PRIMARY KEY, ten_thuoc TEXT NOT NULL,
    so_dang_ky TEXT, dang_bao_che TEXT
);
CREATE INDEX thuoc_khoa_ten ON thuoc(khoa_ten_thuoc, thuoc_id);
CREATE TABLE thuoc_thanh_phan(
    thuoc_id TEXT NOT NULL REFERENCES thuoc, hoat_chat_id TEXT NOT NULL REFERENCES hoat_chat,
    ham_luong REAL, don_vi TEXT, PRIMARY KEY(thuoc_id, hoat_chat_id)
) WITHOUT ROWID;
CREATE TABLE chuyen_ma_ca(
    ma_ca TEXT PRIMARY KEY, hoat_chat_id TEXT NOT NULL REFERENCES hoat_chat, cach_khop TEXT NOT NULL
);
CREATE TABLE meta(phien_ban TEXT, ngay_dung TEXT, nguon_tep_json TEXT, sha256_json TEXT);
"""

SourceRow = dict[str, Any]
CsvRow = dict[str, str]


class SourceFiles:
    """Gộp đọc JSONL và băm tệp trong một lượt."""

    def __init__(self, root: Path, paths: list[Path]) -> None:
        self._root = root
        self._versions = {path: self._version(path) for path in paths}
        self.checksums: dict[str, str] = {}
        self.dates: set[str] = set()

    def _version(self, path: Path) -> tuple[int, int, int]:
        stat = (self._root / path).stat()
        return stat.st_ino, stat.st_size, stat.st_mtime_ns

    def rows(self, path: Path) -> Iterator[SourceRow]:
        digest = hashlib.sha256()
        with (self._root / path).open("rb") as stream:
            for line in stream:
                digest.update(line)
                if line.strip():
                    row = json.loads(line)
                    if row.get("ngay_dung"):
                        self.dates.add(row["ngay_dung"])
                    yield row
        self.checksums[path.as_posix()] = digest.hexdigest()

    def hash_cases(self, paths: Iterable[Path]) -> None:
        for path in paths:
            with (self._root / path).open("rb") as stream:
                self.checksums[path.as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()

    def check_unchanged(self) -> None:
        for path, version in self._versions.items():
            if self._version(path) != version:
                raise RuntimeError(f"Nguồn thay đổi khi dựng chỉ mục: {path}. Hãy chạy lại.")


def _case_paths(root: Path) -> list[Path]:
    return sorted(
        path.relative_to(root)
        for folder in ("demo", "hoso_gia_lap")
        for path in (root / "data/mock" / folder).glob("*.json")
        if not path.name.startswith("_")
    )


def _load_cases(root: Path) -> list[CaBenh]:
    from app.db.reader import load_source_cases

    return load_source_cases(root)


def _insert_dictionary(
    db: sqlite3.Connection, sources: SourceFiles
) -> tuple[dict[str, SourceRow], IngredientNames]:
    axis = {row["hoat_chat_id"]: row for row in sources.rows(DICTIONARY_DIR / "hoat_chat.jsonl")}
    db.executemany(
        "INSERT INTO hoat_chat VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        (
            (
                identifier,
                row["ten_inn"],
                row.get("ten_viet"),
                row.get("rxcui"),
                json.dumps(row["ma_atc"]),
                row["loai"],
            )
            for identifier, row in sorted(axis.items())
        ),
    )
    db.executemany(
        "INSERT OR IGNORE INTO dong_nghia VALUES (?, ?, ?, ?)",
        (
            (row["khoa_chuan_hoa"], row["hoat_chat_id"], row["loai"], row["cach_khop"])
            for row in sources.rows(DICTIONARY_DIR / "dong_nghia.jsonl")
        ),
    )
    db.executemany(
        "INSERT INTO thuoc VALUES (?, ?, ?, ?, ?)",
        (
            (
                product_key(row["ten_thuoc"]),
                row["thuoc_id"],
                row["ten_thuoc"],
                row.get("so_dang_ky"),
                row.get("dang_bao_che"),
            )
            for row in sources.rows(DICTIONARY_DIR / "thuoc.jsonl")
        ),
    )
    db.executemany(
        """
        INSERT INTO thuoc_thanh_phan VALUES (?, ?, ?, ?)
        ON CONFLICT(thuoc_id, hoat_chat_id) DO UPDATE SET ham_luong=NULL, don_vi=NULL
        WHERE ham_luong IS NOT excluded.ham_luong OR don_vi IS NOT excluded.don_vi
        """,
        (
            (row["thuoc_id"], row["hoat_chat_id"], row.get("ham_luong"), row.get("don_vi"))
            for row in sources.rows(DICTIONARY_DIR / "thuoc_thanh_phan.jsonl")
        ),
    )
    names = IngredientNames(
        {identifier: row["ten_inn"] for identifier, row in axis.items()},
        db.execute("SELECT khoa_chuan_hoa, hoat_chat_id, loai FROM dong_nghia"),
    )
    return axis, names


def _atc_index(rows: dict[str, SourceRow]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    for identifier, row in rows.items():
        for code in row["ma_atc"]:
            index[code[:5]].add(identifier)
    return index


def _atc_suggestions(row: SourceRow, index: dict[str, set[str]]) -> str:
    candidates = {identifier for code in row["ma_atc"] for identifier in index[code[:5]]}
    return " | ".join(sorted(candidates))


def _link_ddinter(
    db: sqlite3.Connection, axis: dict[str, SourceRow], names: IngredientNames, sources: SourceFiles
) -> tuple[int, list[CsvRow]]:
    ddinter = {row["ddinter_id"]: row for row in sources.rows(DDINTER_PATH)}
    axis_by_dd = {identifier: names.ddinter_ids(row["ten"]) for identifier, row in ddinter.items()}
    dd_by_axis: dict[str, set[str]] = defaultdict(set)
    for identifier, matches in axis_by_dd.items():
        for match in matches:
            dd_by_axis[match].add(identifier)

    links = {}
    for identifier, matches in sorted(axis_by_dd.items()):
        if len(matches) == 1:
            match = next(iter(matches))
            if len(dd_by_axis[match]) == 1:
                links[identifier] = match
    db.executemany(
        "UPDATE hoat_chat SET ddinter_id = ?, ddinter_cach_khop = 'ten_chinh_xac' "
        "WHERE hoat_chat_id = ?",
        links.items(),
    )

    axis_atc = _atc_index(axis)
    dd_atc = _atc_index(ddinter)
    rows = []
    for identifier, row in sorted(ddinter.items()):
        if identifier not in links:
            matches = axis_by_dd[identifier]
            rows.append(
                {
                    "phia": "ddinter",
                    "ddinter_id": identifier,
                    "ten": row["ten"],
                    "ma_atc": " | ".join(row["ma_atc"]),
                    "ly_do": (
                        "Xung đột nối tên" if matches else "Chưa khớp INN hoặc đồng nghĩa INN/muối"
                    ),
                    "ung_vien_xung_dot": " | ".join(sorted(matches)),
                    "goi_y_atc": _atc_suggestions(row, axis_atc),
                }
            )
    linked_axis = set(links.values())
    for identifier, row in sorted(axis.items()):
        if identifier not in linked_axis:
            matches = dd_by_axis.get(identifier, set())
            rows.append(
                {
                    "phia": "truc",
                    "hoat_chat_id": identifier,
                    "ten": row["ten_inn"],
                    "ma_atc": " | ".join(row["ma_atc"]),
                    "ly_do": (
                        "Xung đột nối tên"
                        if matches
                        else "Chưa có tên DDInter khớp INN/đồng nghĩa INN/muối"
                    ),
                    "ung_vien_xung_dot": " | ".join(sorted(matches)),
                    "goi_y_atc": _atc_suggestions(row, dd_atc),
                }
            )
    return len(links), rows


def _case_mapping(
    db: sqlite3.Connection, cases: list[CaBenh], names: IngredientNames
) -> list[CsvRow]:
    observed: dict[str, set[CaseMatch]] = defaultdict(set)
    salt_codes = set()
    for case in cases:
        matches = {
            row.hoat_chat_id: names.match_case(row)
            for row in case.danh_muc_hoat_chat
            if row.hoat_chat_id.startswith("HC-")
        }
        for code, match in matches.items():
            observed[code].add(match)
        for drug in case.danh_muc_thuoc:
            if len(drug.thanh_phan) == 1:
                code = drug.thanh_phan[0].hoat_chat_id
                match = matches.get(code)
                if (
                    match
                    and match.hoat_chat_id
                    and names.is_salt(product_key(drug.ten_thuoc), match.hoat_chat_id)
                ):
                    salt_codes.add(code)

    rows = []
    for code, matches in sorted(observed.items()):
        identifiers = {match.hoat_chat_id for match in matches if match.hoat_chat_id}
        errors = sorted({match.ly_do for match in matches if match.ly_do})
        if len(identifiers) > 1:
            errors.append(f"Cùng mã ca khớp nhiều hoạt chất: {', '.join(sorted(identifiers))}")
        if len(identifiers) == 1 and not errors:
            identifier = next(iter(identifiers))
            methods = {match.cach_khop for match in matches}
            method = next(
                label
                for label in ("dang_muoi", "ten_quoc_te", "dong_nghia", "ten_viet")
                if label in methods or (label == "dang_muoi" and code in salt_codes)
            )
            db.execute("INSERT INTO chuyen_ma_ca VALUES (?, ?, ?)", (code, identifier, method))
            rows.append({"ma_ca": code, "hoat_chat_id": identifier, "cach_khop": method})
        else:
            rows.append({"ma_ca": code, "ly_do": " / ".join(errors)})
    return rows


def _write_csv(path: Path, fields: list[str], rows: list[CsvRow]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_index(root: Path) -> dict[str, int]:
    """Tạo SQLite tạm cùng thư mục rồi thay thế nguyên tử khi hoàn tất."""
    index = root / INDEX_PATH
    reports = root / REPORT_DIR
    index.parent.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    case_paths = _case_paths(root)
    paths = [
        DICTIONARY_DIR / f"{name}.jsonl"
        for name in ("hoat_chat", "dong_nghia", "thuoc", "thuoc_thanh_phan")
    ]
    sources = SourceFiles(root, [*paths, DDINTER_PATH, *case_paths])
    with NamedTemporaryFile(
        dir=index.parent, prefix=".tra_cuu-", suffix=".sqlite", delete=False
    ) as file:
        temporary = Path(file.name)
    try:
        with closing(sqlite3.connect(temporary)) as db, db:
            db.executescript(_SCHEMA)
            axis, names = _insert_dictionary(db, sources)
            linked, dd_rows = _link_ddinter(db, axis, names, sources)
            case_rows = _case_mapping(db, _load_cases(root), names)
            sources.hash_cases(case_paths)
            db.execute(
                "INSERT INTO meta VALUES (?, ?, ?, ?)",
                (
                    "T53-v1",
                    max(sources.dates, default=None),
                    json.dumps(sorted(sources.checksums)),
                    json.dumps(sources.checksums, sort_keys=True),
                ),
            )
        sources.check_unchanged()
        os.replace(temporary, index)
    finally:
        temporary.unlink(missing_ok=True)
    _write_csv(
        reports / DDINTER_CSV,
        [
            "phia",
            "ddinter_id",
            "hoat_chat_id",
            "ten",
            "ma_atc",
            "ly_do",
            "ung_vien_xung_dot",
            "goi_y_atc",
        ],
        dd_rows,
    )
    _write_csv(reports / CASE_CSV, ["ma_ca", "hoat_chat_id", "cach_khop", "ly_do"], case_rows)
    return {
        "so_hoat_chat": len(axis),
        "so_hoat_chat_co_ddinter": linked,
        "so_ma_ca": len(case_rows),
        "so_ma_ca_chua_chuyen": sum(not row.get("hoat_chat_id") for row in case_rows),
        "dung_luong_sqlite_byte": index.stat().st_size,
    }
