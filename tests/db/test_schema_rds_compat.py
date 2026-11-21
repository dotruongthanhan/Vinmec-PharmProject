"""Kiểm tra lược đồ SQL tương thích PostgreSQL thường (AWS RDS) và không BOM."""

import re
import tempfile
from pathlib import Path

from app.db.engine import apply_schema
from tests.db.test_loading import RecordingConnection

ROOT = Path(__file__).resolve().parents[2]


def test_schema_revokes_supabase_roles_only_conditionally() -> None:
    sql_text = (ROOT / "db/schema.sql").read_text(encoding="utf-8")
    outside_do = re.sub(r"DO \$\$.*?END\s*\$\$;", "", sql_text, flags=re.S)

    assert not re.search(r"REVOKE\b[^;]*\b(?:anon|authenticated)\b", outside_do, re.I)
    revoked_tables = "REVOKE ALL ON nghiep_vu.phieu_dieu_tri, nghiep_vu.phieu_y_lenh FROM PUBLIC;"
    assert revoked_tables in outside_do
    assert "REVOKE ALL ON nghiep_vu.v_thuoc_dang_dung FROM PUBLIC;" in outside_do

    do_blocks = re.findall(r"DO \$\$.*?END\s*\$\$;", sql_text, flags=re.S)
    assert len(do_blocks) == 6
    assert any("nghiep_vu.hoi_thoai" in block for block in do_blocks)
    assert any("nghiep_vu.ket_qua_tham_dinh" in block for block in do_blocks)
    assert any("nghiep_vu.ket_qua_nhan_dinh" in block for block in do_blocks)
    assert any("tri_thuc.bang_luat_meta" in block for block in do_blocks)
    for block in do_blocks:
        assert "SELECT 1 FROM pg_roles WHERE rolname = 'anon'" in block
        assert "SELECT 1 FROM pg_roles WHERE rolname = 'authenticated'" in block


def test_tu_dien_sql_has_no_utf8_bom() -> None:
    raw = (ROOT / "db/tu_dien.sql").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8")
    assert text.startswith("-- DDL")


def test_apply_schema_tolerates_utf8_bom() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        schema_dir = root / "db"
        schema_dir.mkdir(parents=True)
        (schema_dir / "schema.sql").write_bytes(b"\xef\xbb\xbfSELECT 1;\n")

        connection = RecordingConnection()
        apply_schema(connection, root)  # type: ignore[arg-type]

    assert len(connection.committed) == 1
    executed_sql = connection.committed[0][0]
    assert executed_sql == "SELECT 1;\n"
    assert not executed_sql.startswith("﻿")
