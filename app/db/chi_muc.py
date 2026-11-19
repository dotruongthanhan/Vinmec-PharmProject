"""Nạp và đối chiếu toàn bộ bảng của hai chỉ mục SQLite sang PostgreSQL."""

from __future__ import annotations

import sqlite3
from contextlib import ExitStack, closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import psycopg
from psycopg import sql

from app.db.engine import identifier
from app.db.sources import SourceError

BATCH_SIZE = 5000


@dataclass(frozen=True)
class IndexTableSpec:
    """Ánh xạ một bảng SQLite chỉ mục sang bảng PostgreSQL tương ứng."""

    source_kind: Literal["tuong_tac", "tra_cuu"]
    sqlite_table: str
    pg_table: str
    columns: tuple[str, ...]


# Thứ tự giữ bảng cha trước bảng con để bảo toàn khoá ngoại khi nạp.
INDEX_TABLES: tuple[IndexTableSpec, ...] = (
    IndexTableSpec(
        "tuong_tac",
        "cap",
        "tri_thuc.ddinter_cap",
        (
            "ddinter_id_a",
            "ddinter_id_b",
            "muc_do",
            "muc_do_so",
            "co_che_json",
            "co_lech_muc",
            "cac_muc_nguon_json",
            "ma_trang_cap_json",
            "hau_qua",
            "xu_tri",
            "tai_lieu_json",
            "url_goc",
        ),
    ),
    IndexTableSpec(
        "tuong_tac",
        "thuoc",
        "tri_thuc.ddinter_thuoc",
        ("ddinter_id", "ten", "da_cao_du"),
    ),
    IndexTableSpec(
        "tuong_tac",
        "thuc_an",
        "tri_thuc.ddinter_thuc_an",
        ("ddinter_id", "thuc_an", "muc_do", "mo_ta", "xu_tri", "co_che_json"),
    ),
    IndexTableSpec(
        "tra_cuu",
        "hoat_chat",
        "tri_thuc.tra_cuu_hoat_chat",
        (
            "hoat_chat_id",
            "ten_inn",
            "ten_viet",
            "rxcui",
            "ma_atc_json",
            "loai",
            "ddinter_id",
            "ddinter_cach_khop",
        ),
    ),
    IndexTableSpec(
        "tra_cuu",
        "dong_nghia",
        "tri_thuc.tra_cuu_dong_nghia",
        ("khoa_chuan_hoa", "hoat_chat_id", "loai", "cach_khop"),
    ),
    IndexTableSpec(
        "tra_cuu",
        "thuoc",
        "tri_thuc.tra_cuu_thuoc",
        ("khoa_ten_thuoc", "thuoc_id", "ten_thuoc", "so_dang_ky", "dang_bao_che"),
    ),
    IndexTableSpec(
        "tra_cuu",
        "thuoc_thanh_phan",
        "tri_thuc.tra_cuu_thuoc_thanh_phan",
        ("thuoc_id", "hoat_chat_id", "ham_luong", "don_vi"),
    ),
    IndexTableSpec(
        "tra_cuu",
        "chuyen_ma_ca",
        "tri_thuc.tra_cuu_chuyen_ma_ca",
        ("ma_ca", "hoat_chat_id", "cach_khop"),
    ),
    IndexTableSpec(
        "tra_cuu",
        "meta",
        "tri_thuc.tra_cuu_meta",
        ("phien_ban", "ngay_dung", "nguon_tep_json", "sha256_json"),
    ),
)


def _open_sqlite_readonly(path: Path) -> sqlite3.Connection:
    """Mở tệp SQLite ở chế độ chỉ đọc; báo SourceError nếu thiếu hoặc lỗi."""
    if not path.is_file():
        raise SourceError(f"Thiếu tệp chỉ mục: {path}")
    try:
        return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    except (OSError, sqlite3.Error) as exc:
        msg = f"Không mở được tệp chỉ mục {path.name}: {type(exc).__name__}"
        raise SourceError(msg) from None


def _read_sqlite_counts(dbs: dict[str, sqlite3.Connection]) -> dict[str, int]:
    """Đếm số dòng hiện có trong từng bảng SQLite nguồn."""
    counts: dict[str, int] = {}
    for spec in INDEX_TABLES:
        db = dbs[spec.source_kind]
        try:
            row = db.execute(f'SELECT count(*) FROM "{spec.sqlite_table}"').fetchone()
        except sqlite3.Error as exc:
            raise SourceError(
                f"Lỗi đọc bảng {spec.sqlite_table} từ SQLite: {type(exc).__name__}"
            ) from None
        counts[spec.pg_table] = int(row[0]) if row is not None else 0
    return counts


def inspect_sqlite_counts(tra_cuu_path: Path, tuong_tac_path: Path) -> dict[str, int]:
    """Mở chỉ đọc hai tệp SQLite và trả số dòng từng bảng đích."""
    with ExitStack() as stack:
        dbs = {
            "tra_cuu": stack.enter_context(closing(_open_sqlite_readonly(tra_cuu_path))),
            "tuong_tac": stack.enter_context(closing(_open_sqlite_readonly(tuong_tac_path))),
        }
        return _read_sqlite_counts(dbs)


def load_chi_muc(
    connection: psycopg.Connection[Any],
    tra_cuu_path: Path,
    tuong_tac_path: Path,
    batch_size: int = BATCH_SIZE,
) -> dict[str, tuple[int, int]]:
    """Chép toàn bộ bảng chỉ mục SQLite sang PostgreSQL trong một giao dịch."""
    with ExitStack() as stack:
        dbs = {
            "tra_cuu": stack.enter_context(closing(_open_sqlite_readonly(tra_cuu_path))),
            "tuong_tac": stack.enter_context(closing(_open_sqlite_readonly(tuong_tac_path))),
        }
        source_counts = _read_sqlite_counts(dbs)
        results: dict[str, tuple[int, int]] = {}
        with connection.transaction(), connection.cursor() as pg_cursor:
            pg_cursor.execute(
                sql.SQL("TRUNCATE {} RESTART IDENTITY").format(
                    sql.SQL(", ").join(identifier(spec.pg_table) for spec in INDEX_TABLES)
                )
            )
            for spec in INDEX_TABLES:
                src_db = dbs[spec.source_kind]
                col_sql = ", ".join(f'"{col}"' for col in spec.columns)
                src_cursor = src_db.execute(f'SELECT {col_sql} FROM "{spec.sqlite_table}"')
                command = sql.SQL("COPY {} ({}) FROM STDIN").format(
                    identifier(spec.pg_table),
                    sql.SQL(", ").join(map(sql.Identifier, spec.columns)),
                )
                copied = 0
                with pg_cursor.copy(command) as copy:
                    while batch := src_cursor.fetchmany(batch_size):
                        for row in batch:
                            copy.write_row(row)
                            copied += 1
                if copied != source_counts[spec.pg_table]:
                    raise SourceError(
                        f"{spec.pg_table}: số dòng chép ({copied}) khác SQLite "
                        f"({source_counts[spec.pg_table]})"
                    )
            mismatched: list[str] = []
            for spec in INDEX_TABLES:
                src_count = source_counts[spec.pg_table]
                row = pg_cursor.execute(
                    sql.SQL("SELECT count(*) FROM {}").format(identifier(spec.pg_table))
                ).fetchone()
                dst_count = int(row[0]) if row is not None else 0
                results[spec.pg_table] = (src_count, dst_count)
                status = "KHỚP" if dst_count == src_count else "LỆCH"
                print(f"{spec.pg_table}: nguồn={src_count}, CSDL={dst_count}, {status}")
                if dst_count != src_count:
                    mismatched.append(spec.pg_table)
            if mismatched:
                joined = ", ".join(mismatched)
                raise SourceError(f"Lệch số dòng chỉ mục, đã rollback: {joined}")
        return results


def verify_chi_muc(
    connection: psycopg.Connection[Any],
    tra_cuu_path: Path,
    tuong_tac_path: Path,
) -> bool:
    """Đối chiếu số dòng 9 bảng chỉ mục giữa SQLite cục bộ và PostgreSQL (chỉ đọc)."""
    source_counts = inspect_sqlite_counts(tra_cuu_path, tuong_tac_path)
    matched = True
    with connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
        for spec in INDEX_TABLES:
            src_count = source_counts[spec.pg_table]
            reg_cur = connection.execute("SELECT to_regclass(%s)", (spec.pg_table,))
            exists = reg_cur.fetchone()
            if exists is None or exists[0] is None:
                print(f"{spec.pg_table}: nguồn={src_count}, CSDL=thiếu bảng, LỆCH")
                matched = False
                continue
            count_row = connection.execute(
                sql.SQL("SELECT count(*) FROM {}").format(identifier(spec.pg_table))
            ).fetchone()
            dst_count = int(count_row[0]) if count_row is not None else 0
            ok = dst_count == src_count
            status = "KHỚP" if ok else "LỆCH"
            print(f"{spec.pg_table}: nguồn={src_count}, CSDL={dst_count}, {status}")
            matched = matched and ok
    return matched
