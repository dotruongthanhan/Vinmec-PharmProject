"""SQL tham số hoá, giao dịch nạp và kiểm tra chỉ đọc."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from app.db.mapping import SCHEMAS, TABLES, Table
from app.db.sources import Batch, Embeddings, SourceError


def identifier(name: str) -> sql.Identifier:
    return sql.Identifier(*name.split("."))


def upsert_statement(table: Table, staging: str | None = None) -> sql.Composed:
    """Chỉ tên bảng/cột từ ánh xạ được ghép; giá trị dùng tham số."""
    columns = table.column_names
    # Chỉ giữ véc-tơ đã có khi văn bản nhúng không đổi.
    if table.name == "tri_thuc.doan_trich":
        columns = tuple(col for col in columns if col != "embedding")
    names = sql.SQL(", ").join(map(sql.Identifier, columns))
    values = (
        sql.SQL("SELECT {} FROM {} WHERE true").format(names, identifier(staging))
        if staging
        else sql.SQL("VALUES ({})").format(sql.SQL(", ").join(sql.Placeholder() for _ in columns))
    )
    assignments = [
        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(col), sql.Identifier(col))
        for col in columns
        if col not in table.primary_key
    ]
    if table.name == "tri_thuc.doan_trich":
        assignments.append(
            sql.SQL(
                '"embedding" = CASE WHEN {}."noi_dung_nhung" '
                'IS NOT DISTINCT FROM EXCLUDED."noi_dung_nhung" '
                'THEN {}."embedding" ELSE NULL END'
            ).format(identifier(table.name), identifier(table.name))
        )
    updates = sql.SQL(", ").join(assignments)
    return sql.SQL("INSERT INTO {} ({}) {} ON CONFLICT ({}) DO UPDATE SET {}").format(
        identifier(table.name),
        names,
        values,
        sql.SQL(", ").join(map(sql.Identifier, table.primary_key)),
        updates,
    )


def row_values(table: Table, row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(
        Jsonb(row[col]) if col in table.json_columns and row[col] is not None else row[col]
        for col in table.column_names
        if not (table.name == "tri_thuc.doan_trich" and col == "embedding")
    )


def apply_schema(connection: psycopg.Connection[Any], root: Path, reset: bool = False) -> None:
    """Dựng nguyên tử; reset chỉ dùng hai tên lược đồ cố định."""
    with connection.transaction():
        if reset:
            for schema in SCHEMAS:
                connection.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
                )
        connection.execute((root / "db/schema.sql").read_text(encoding="utf-8"))


def replace_group(cursor: psycopg.Cursor[Any], batch: Batch, group: str) -> None:
    """Xoá theo thứ tự con → cha, không CASCADE sang nhóm khác."""
    for name in reversed(TABLES):
        if name in batch.tables and name != "tri_thuc.hoat_chat":
            cursor.execute(sql.SQL("DELETE FROM {}").format(identifier(name)))
    if group == "kb":
        # Danh mục dùng chung với ca: giữ các khoá còn trong nguồn để không xoá dây chuyền ca.
        keys = [row["hoat_chat_id"] for row in batch.rows["tri_thuc.hoat_chat"]]
        cursor.execute("DELETE FROM tri_thuc.hoat_chat WHERE NOT (hoat_chat_id = ANY(%s))", (keys,))


def load_batch(
    connection: psycopg.Connection[Any], batch: Batch, group: str, replace: bool = False
) -> None:
    """Mỗi nhóm một giao dịch; DDInter dùng COPY vào bảng tạm rồi upsert."""
    with connection.transaction(), connection.cursor() as cursor:
        if replace:
            replace_group(cursor, batch, group)
        for name, table in TABLES.items():
            if name not in batch.tables or not batch.rows[name]:
                continue
            if group == "ddinter":
                staging = "stage_tuong_tac_sang_loc"
                cursor.execute(
                    sql.SQL(
                        "CREATE TEMP TABLE {} (LIKE {} INCLUDING DEFAULTS) ON COMMIT DROP"
                    ).format(identifier(staging), identifier(name))
                )
                command = sql.SQL("COPY {} ({}) FROM STDIN").format(
                    identifier(staging), sql.SQL(", ").join(map(sql.Identifier, table.column_names))
                )
                with cursor.copy(command) as copy:
                    for row in batch.rows[name]:
                        copy.write_row(row_values(table, row))
                cursor.execute(upsert_statement(table, staging))
            else:
                cursor.executemany(
                    upsert_statement(table), (row_values(table, row) for row in batch.rows[name])
                )


def load_embeddings(
    connection: psycopg.Connection[Any], embeddings: Embeddings, replace: bool = False
) -> None:
    """Chỉ cập nhật đoạn đã có; thiếu đoạn làm hoàn tác cả nhóm."""
    with connection.transaction(), connection.cursor() as cursor:
        if replace:
            cursor.execute("UPDATE tri_thuc.doan_trich SET embedding = NULL")
        if embeddings.vectors:
            cursor.executemany(
                "UPDATE tri_thuc.doan_trich SET embedding = %s WHERE doan_trich_id = %s",
                ((vector, chunk_id) for chunk_id, vector in embeddings.vectors.items()),
            )
            if cursor.rowcount != len(embeddings.vectors):
                raise SourceError("thiếu doan_trich_id trong cơ sở dữ liệu; chạy load kb trước")


def check(connection: psycopg.Connection[Any]) -> None:
    """Chỉ SELECT; kết nối được bảo vệ chỉ đọc ngay từ khi mở."""
    with connection.transaction():
        print("PostgreSQL:", connection.execute("SELECT version()").fetchone()[0])
        row = connection.execute(
            "SELECT extversion FROM pg_extension WHERE extname = %s", ("vector",)
        ).fetchone()
        print("vector:", row[0] if row else "chưa có")
        for schema in SCHEMAS:
            row = connection.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = %s)", (schema,)
            ).fetchone()
            print(f"{schema}: {'có' if row[0] else 'chưa có'}")


def expected_counts(batches: Iterable[Batch]) -> dict[str, int]:
    keys: dict[str, set[tuple[Any, ...]]] = {name: set() for name in TABLES}
    for batch in batches:
        for name in batch.tables:
            for row in batch.rows[name]:
                keys[name].add(tuple(row[col] for col in TABLES[name].primary_key))
    return {name: len(values) for name, values in keys.items()}


def verify(
    connection: psycopg.Connection[Any], counts: dict[str, int], embeddings: Embeddings
) -> bool:
    """Đối chiếu số dòng duy nhất, khoá ngoại và độ phủ bộ đệm."""
    matched = True
    with connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
        for name, count in counts.items():
            exists = connection.execute("SELECT to_regclass(%s)", (name,)).fetchone()[0]
            if exists is None:
                print(f"{name}: nguồn={count}, CSDL=thiếu bảng, LỆCH")
                matched = False
                continue
            actual = connection.execute(
                sql.SQL("SELECT count(*) FROM {}").format(identifier(name))
            ).fetchone()[0]
            ok = actual == count
            print(f"{name}: nguồn={count}, CSDL={actual}, {'KHỚP' if ok else 'LỆCH'}")
            matched = matched and ok
        orphan_total = 0
        for name, table in TABLES.items():
            for reference in table.foreign_keys:
                exists = connection.execute(
                    "SELECT to_regclass(%s), to_regclass(%s)", (name, reference.table)
                ).fetchone()
                if None in exists:
                    continue
                present = sql.SQL(" AND ").join(
                    sql.SQL("c.{} IS NOT NULL").format(sql.Identifier(c)) for c in reference.columns
                )
                join = sql.SQL(" AND ").join(
                    sql.SQL("c.{} = p.{}").format(sql.Identifier(c), sql.Identifier(p))
                    for c, p in zip(reference.columns, reference.target, strict=True)
                )
                query = sql.SQL(
                    "SELECT count(*) FROM {} c WHERE {} "
                    "AND NOT EXISTS (SELECT 1 FROM {} p WHERE {})"
                ).format(identifier(name), present, identifier(reference.table), join)
                orphan_total += connection.execute(query).fetchone()[0]
        print(f"Khoá ngoại mồ côi: {orphan_total}")
        matched = matched and orphan_total == 0
        if connection.execute("SELECT to_regclass(%s)", ("tri_thuc.doan_trich",)).fetchone()[0]:
            missing, available = connection.execute(
                "SELECT count(*) FILTER (WHERE embedding IS NULL), "
                "count(*) FILTER (WHERE embedding IS NOT NULL) FROM tri_thuc.doan_trich"
            ).fetchone()
            print(
                f"Embedding: có={available}, thiếu={missing}, "
                f"có trong bộ đệm={len(embeddings.vectors)}"
            )
            matched = (
                matched and available == len(embeddings.vectors) and missing == embeddings.missing
            )
    return matched
