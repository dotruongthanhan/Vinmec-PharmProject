"""Chuẩn bị sáu bảng và nạp một phiên bản trong cùng giao dịch."""

from pathlib import Path
from typing import get_args

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from app.config.settings import get_secret
from app.core.errors import ConfigError
from app.kb.dictionary.accept import Ranking, candidate_path
from app.kb.dictionary.axis import MatchMethod
from app.kb.dictionary.review import queue
from app.kb.dictionary.rules_extra import load_rules
from app.kb.dictionary.storage import Row, read_jsonl

TABLES = {
    "tu_dien_hoat_chat": "hoat_chat",
    "tu_dien_dong_nghia": "dong_nghia",
    "tu_dien_thuoc": "thuoc",
    "tu_dien_thanh_phan": "thuoc_thanh_phan",
    "tu_dien_anh_xa": "anh_xa",
    "tu_dien_hang_duyet": "cho_duyet",
}


def _snapshot(root: Path) -> tuple[str, dict[str, list[Row]]]:
    folder = root / "kb_curated/tu_dien"
    tables = {table: read_jsonl(folder / f"{path}.jsonl") for table, path in TABLES.items()}
    versions = {row.get("phien_ban") for rows in tables.values() for row in rows}
    if (
        len(versions) != 1
        or not (version := next(iter(versions)))
        or not version.startswith("T52-")
    ):
        raise ValueError("Can mot bo tu dien T52 dung xong, cung phien ban")
    grouped = queue(root, rows=tables["tu_dien_hang_duyet"])
    scores = candidate_path(root, "that")
    rankings = (
        {row["khoa_chuan_hoa"]: Ranking.model_validate(row) for row in read_jsonl(scores)}
        if scores.is_file()
        else {}
    )
    tables["tu_dien_hang_duyet"] = [
        {
            **group,
            "phien_ban": version,
            "ung_vien": [pick.model_dump() for pick in rankings[key].ung_vien]
            if key in rankings
            else [],
        }
        for key, group in sorted(grouped.items())
    ]

    axes = {row["hoat_chat_id"] for row in tables["tu_dien_hoat_chat"]}
    products = {row["thuoc_id"] for row in tables["tu_dien_thuoc"]}
    allowed = set(get_args(MatchMethod))
    if not load_rules().tu_nhan_ngu_nghia:
        allowed.remove("ngu_nghia_tu_nhan")
    for name, rows in tables.items():
        for number, row in enumerate(rows, 1):
            if not row["nguon_ban_ghi_ids"]:
                raise ValueError(f"{name}: thieu nguon neo")
            if "hoat_chat_id" in row and row["hoat_chat_id"] not in axes:
                raise ValueError(f"{name}: hoat chat mo coi")
            if "thuoc_id" in row and row["thuoc_id"] not in products:
                raise ValueError(f"{name}: che pham mo coi")
            if "cach_khop" in row and row["cach_khop"] not in allowed:
                raise ValueError(f"{name}: cach khop khong duoc xuat ban")
            if name in {"tu_dien_anh_xa", "tu_dien_thanh_phan", "tu_dien_dong_nghia"}:
                row["stt"] = number
    return version, tables


def publish(root: Path, *, yes: bool = False) -> Row:
    """Mặc định đọc dữ liệu và in mẫu, chỉ đọc URL khi có --yes."""
    version, tables = _snapshot(root)
    summary = {
        "phien_ban": version,
        "so_dong": {table: len(rows) for table, rows in tables.items()},
    }
    if not yes:
        return {
            **summary,
            "dry_run": True,
            "mau": {table: rows[:3] for table, rows in tables.items()},
        }
    try:
        url = get_secret("DATABASE_URL")
    except ConfigError:
        raise ValueError("Thieu bien moi truong DATABASE_URL") from None
    try:
        with psycopg.connect(url) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext('tri_thuc.tu_dien'))")
            for table in reversed(tables):
                target = sql.Identifier("tri_thuc", table)
                cursor.execute(
                    sql.SQL("DELETE FROM {} WHERE phien_ban = %s").format(target), (version,)
                )
            for table, rows in tables.items():
                target = sql.Identifier("tri_thuc", table)
                query = sql.SQL(
                    "INSERT INTO {table} SELECT * FROM jsonb_populate_recordset(NULL::{table}, %s)"
                ).format(table=target)
                for start in range(0, len(rows), 1000):
                    cursor.execute(query, (Jsonb(rows[start : start + 1000]),))
    except psycopg.Error as exc:
        state = exc.sqlstate or "khong_ro"
        raise ValueError(f"Nap tu dien that bai, giao dich da huy (SQLSTATE {state})") from None
    return {**summary, "dry_run": False}
