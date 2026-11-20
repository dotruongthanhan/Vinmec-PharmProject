"""Kiểm tĩnh db/roles.sql khớp thao tác ghi đường chạy API và nguyên tắc quyền tối thiểu."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLES_SQL = ROOT / "db/roles.sql"

# Các mô-đun thuộc đường chạy API (trực tiếp hoặc được API gọi để đọc/ghi DB).
API_PATH_MODULES: tuple[str, ...] = (
    "app/api/main.py",
    "app/api/routes.py",
    "app/api/service.py",
    "app/api/lookup.py",
    "app/api/formulas.py",
    "app/feedback.py",
    "app/storage/feedback_chat.py",
    "app/storage/review_results.py",
    "app/db/reader.py",
    "app/db/administrative.py",
    "app/db/medical_record.py",
    "app/db/bang_luat_store.py",
    "app/retrieval/corpus.py",
    "app/orchestration/evidence.py",
    "app/container.py",
)

_WRITE_OPS = {"INSERT", "UPDATE", "DELETE", "TRUNCATE"}


def _strip_sql_comments(sql_text: str) -> str:
    """Loại chú thích -- và /* */ trước khi phân tích câu lệnh GRANT/REVOKE."""
    without_block = re.sub(r"/\*.*?\*/", "", sql_text, flags=re.S)
    return re.sub(r"--[^\n]*", "", without_block)


def _extract_api_writes() -> set[tuple[str, str]]:
    """Quét mã đường chạy API tìm mọi cặp (thao tác, nghiep_vu.<bảng>)."""
    found: set[tuple[str, str]] = set()
    insert_stmt_re = re.compile(
        r"INSERT\s+INTO\s+nghiep_vu\.([a-z0-9_]+)\b(.*?)(?:[\"']{3}|$)",
        re.I | re.S,
    )
    update_re = re.compile(r"\bUPDATE\s+nghiep_vu\.([a-z0-9_]+)\b", re.I)
    delete_re = re.compile(r"\bDELETE\s+FROM\s+nghiep_vu\.([a-z0-9_]+)\b", re.I)

    for rel in API_PATH_MODULES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for match in insert_stmt_re.finditer(text):
            table = f"nghiep_vu.{match.group(1).lower()}"
            found.add(("INSERT", table))
            if re.search(r"\bON\s+CONFLICT\b.*?\bDO\s+UPDATE\b", match.group(2), re.I | re.S):
                found.add(("UPDATE", table))
        for match in update_re.finditer(text):
            found.add(("UPDATE", f"nghiep_vu.{match.group(1).lower()}"))
        for match in delete_re.finditer(text):
            found.add(("DELETE", f"nghiep_vu.{match.group(1).lower()}"))
    return found


def _extract_app_grants(sql_no_comments: str) -> dict[str, set[str]]:
    """Trích các quyền GRANT trực tiếp cho bvienx_app theo đối tượng (chữ thường)."""
    grants: dict[str, set[str]] = {}
    grant_re = re.compile(
        r"\bGRANT\s+([^;]+?)\s+ON\s+"
        r"(?:TABLE\s+|SEQUENCE\s+|SCHEMA\s+|ALL\s+TABLES\s+IN\s+SCHEMA\s+)?"
        r"([^;]+?)\s+TO\s+([^;]+?);",
        re.I | re.S,
    )
    for match in grant_re.finditer(sql_no_comments):
        privileges_raw, targets_raw, grantees_raw = match.groups()
        grantees = {item.strip().lower() for item in grantees_raw.split(",")}
        if "bvienx_app" not in grantees:
            continue
        privileges = {item.strip().upper() for item in privileges_raw.split(",")}
        for target in targets_raw.split(","):
            cleaned = target.strip().lower()
            grants.setdefault(cleaned, set()).update(privileges)
    return grants


def test_roles_sql_covers_every_api_write_and_sequence() -> None:
    sql_raw = ROLES_SQL.read_text(encoding="utf-8")
    sql_clean = _strip_sql_comments(sql_raw)
    grants = _extract_app_grants(sql_clean)

    api_writes = _extract_api_writes()
    assert ("INSERT", "nghiep_vu.phan_hoi") in api_writes
    assert ("UPDATE", "nghiep_vu.phan_hoi") in api_writes
    assert ("INSERT", "nghiep_vu.hoi_thoai") in api_writes
    assert ("DELETE", "nghiep_vu.hoi_thoai") in api_writes
    assert ("INSERT", "nghiep_vu.ket_qua_tham_dinh") in api_writes
    assert ("INSERT", "nghiep_vu.ket_qua_nhan_dinh") in api_writes

    for op, table in sorted(api_writes):
        assert op in grants.get(table, set()), f"Thiếu GRANT {op} ON {table} TO bvienx_app"

    # Không có truy vấn ghi trực tiếp vào tri_thuc từ đường chạy API.
    for rel in API_PATH_MODULES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert not re.search(
            r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|TRUNCATE)\s+tri_thuc\.",
            text,
            re.I,
        ), rel

    # Bảng có bigserial/serial mà API INSERT phải có USAGE, SELECT trên sequence.
    assert {"USAGE", "SELECT"} <= grants.get("nghiep_vu.hoi_thoai_id_seq", set())


def test_roles_sql_enforces_least_privilege_and_no_secrets() -> None:
    sql_raw = ROLES_SQL.read_text(encoding="utf-8")
    sql_clean = _strip_sql_comments(sql_raw)
    grants = _extract_app_grants(sql_clean)

    assert not re.search(r"\bGRANT\s+ALL\b", sql_raw, re.I)
    assert not re.search(r"\bPASSWORD\s*'", sql_raw, re.I)

    # bvienx_app không được có CREATE ở bất kỳ đâu và không được ghi vào tri_thuc.
    for target, privs in grants.items():
        assert "CREATE" not in privs, f"bvienx_app không được nhận CREATE trên {target}"
        if target.startswith("tri_thuc") or target == "tri_thuc":
            assert not (_WRITE_OPS & privs), f"bvienx_app không được ghi {target}: {privs}"

    assert "NOCREATEDB" in sql_clean
    assert "NOCREATEROLE" in sql_clean
    assert "NOSUPERUSER" in sql_clean
    assert "NOINHERIT" in sql_clean
    assert "REVOKE CREATE ON SCHEMA public FROM PUBLIC;" in sql_clean
    assert (
        "REVOKE CREATE ON SCHEMA tri_thuc, nghiep_vu FROM bvienx_app, bvienx_loader;" in sql_clean
    )
    assert "statement_timeout = '15s'" in sql_clean
    assert "idle_in_transaction_session_timeout = '30s'" in sql_clean
    assert "\\password bvienx_app" in sql_raw


def _extract_loader_nghiep_vu_grant_tables(sql_no_comments: str) -> set[str]:
    """Trích danh sách bảng nghiep_vu.* được cấp quyền ghi cho bvienx_loader."""
    tables: set[str] = set()
    grant_re = re.compile(
        r"\bGRANT\s+([^;]+?)\s+ON\s+(?:TABLE\s+)?([^;]+?)\s+TO\s+([^;]+?);",
        re.I | re.S,
    )
    for match in grant_re.finditer(sql_no_comments):
        privileges_raw, targets_raw, grantees_raw = match.groups()
        grantees = {item.strip().lower() for item in grantees_raw.split(",")}
        privileges = {item.strip().upper() for item in privileges_raw.split(",")}
        if "bvienx_loader" not in grantees or not (_WRITE_OPS & privileges):
            continue
        for target in targets_raw.split(","):
            cleaned = target.strip().lower()
            if cleaned.startswith("nghiep_vu."):
                tables.add(cleaned.removeprefix("nghiep_vu."))
    return tables


def _extract_direct_policies(sql_no_comments: str) -> dict[tuple[str, str], tuple[str, str, str]]:
    """Trích các cặp DROP POLICY IF EXISTS + CREATE POLICY trực tiếp ngoài khối DO $$."""
    direct_re = re.compile(
        r"DROP\s+POLICY\s+IF\s+EXISTS\s+([a-z0-9_]+)\s+ON\s+([a-z0-9_]+\.[a-z0-9_]+)\s*;\s*"
        r"CREATE\s+POLICY\s+([a-z0-9_]+)\s+ON\s+([a-z0-9_]+\.[a-z0-9_]+)\s+"
        r"FOR\s+(SELECT|INSERT|UPDATE|DELETE|ALL)\s+TO\s+([a-z0-9_,\s]+?)\s+"
        r"((?:USING|WITH\s+CHECK)\b[^;]*);",
        re.I | re.S,
    )
    policies: dict[tuple[str, str], tuple[str, str, str]] = {}
    for match in direct_re.finditer(sql_no_comments):
        drop_name, drop_table, name, table, op, roles_raw, clause = match.groups()
        assert drop_name.lower() == name.lower()
        assert drop_table.lower() == table.lower()
        policies[(op.upper(), table.lower())] = (
            name.lower(),
            roles_raw.strip().lower(),
            " ".join(clause.split()).lower(),
        )
    return policies


def test_roles_sql_has_rls_policies_matching_grants() -> None:
    sql_raw = ROLES_SQL.read_text(encoding="utf-8")
    sql_clean = _strip_sql_comments(sql_raw)
    grants = _extract_app_grants(sql_clean)

    # Không tắt RLS, không cấp BYPASSRLS, không tạo policy cho public/anon/authenticated.
    assert not re.search(r"\bBYPASSRLS\b", sql_clean, re.I)
    assert not re.search(r"\bDISABLE\s+ROW\s+LEVEL\s+SECURITY\b", sql_clean, re.I)
    assert not re.search(
        r"\bCREATE\s+POLICY\b[^;'\"]*?\bTO\s+"
        r"(?:[a-z0-9_]+\s*,\s*)*(?:PUBLIC|anon|authenticated)\b",
        sql_clean,
        re.I | re.S,
    )

    any_policy_re = re.compile(
        r"\bCREATE\s+POLICY\s+([a-z0-9_]+)\s+ON\s+([^\s]+)\s+"
        r"FOR\s+(SELECT|INSERT|UPDATE|DELETE|ALL)\s+TO\s+([a-z0-9_,\s]+?)\s+"
        r"(?:USING|WITH\s+CHECK)\b",
        re.I | re.S,
    )
    all_policies = list(any_policy_re.finditer(sql_clean))
    assert all_policies
    for match in all_policies:
        policy_name = match.group(1).lower()
        roles = {item.strip().lower() for item in match.group(4).split(",")}
        assert not (roles & {"public", "anon", "authenticated"}), match.group(0)
        assert roles <= {"bvienx_app", "bvienx_loader"}, match.group(0)
        if "bvienx_app" in roles:
            assert policy_name.startswith("bvienx_app_"), policy_name
        if "bvienx_loader" in roles:
            assert policy_name.startswith("bvienx_loader_"), policy_name

    # Kiểm mọi policy trực tiếp đều có DROP POLICY IF EXISTS đi trước và khớp GRANT ghi của app.
    non_dynamic = [m for m in all_policies if not m.group(2).startswith("%")]
    direct_policies = _extract_direct_policies(sql_clean)
    assert len(direct_policies) == len(non_dynamic)

    app_write_grants = {
        (op, target) for target, privs in grants.items() for op in privs if op in _WRITE_OPS
    }
    assert app_write_grants == _extract_api_writes()
    assert set(direct_policies) == app_write_grants

    for (op, table), (policy_name, roles_raw, clause) in direct_policies.items():
        assert roles_raw == "bvienx_app"
        assert policy_name.startswith("bvienx_app_")
        if op == "INSERT":
            assert clause == "with check (true)", f"{table}: {clause}"
        elif op == "UPDATE":
            assert clause == "using (true) with check (true)", f"{table}: {clause}"
        elif op == "DELETE":
            assert clause == "using (true)", f"{table}: {clause}"

    # Kiểm khối DO $$ duyệt pg_tables tạo SELECT cho bvienx_app và FOR ALL cho bvienx_loader.
    normalized = " ".join(sql_clean.split())
    assert "FROM pg_tables WHERE schemaname IN ('tri_thuc', 'nghiep_vu')" in normalized
    assert "'DROP POLICY IF EXISTS bvienx_app_doc ON %I.%I'" in normalized
    app_select_policy = (
        "'CREATE POLICY bvienx_app_doc ON %I.%I FOR SELECT TO bvienx_app USING (true)'"
    )
    assert app_select_policy in normalized
    assert "'DROP POLICY IF EXISTS bvienx_loader_nap ON %I.%I'" in normalized
    loader_all_policy = (
        "'CREATE POLICY bvienx_loader_nap ON %I.%I "
        "FOR ALL TO bvienx_loader USING (true) WITH CHECK (true)'"
    )
    assert loader_all_policy in normalized
    assert re.search(
        r"IF\s+tbl\.schemaname\s*=\s*'tri_thuc'\s+OR\s*\(\s*"
        r"tbl\.schemaname\s*=\s*'nghiep_vu'\s+AND\s+"
        r"tbl\.tablename(?:::text)?\s*=\s*ANY\s*\(\s*loader_nghiep_vu_tables\s*\)\s*\)\s+THEN",
        sql_clean,
        re.I,
    )

    array_match = re.search(
        r"loader_nghiep_vu_tables\s+text\[\]\s*:=\s*ARRAY\s*\[(.*?)\]\s*;",
        sql_clean,
        re.I | re.S,
    )
    assert array_match is not None
    loader_policy_tables = set(re.findall(r"'([a-z0-9_]+)'", array_match.group(1)))
    assert loader_policy_tables == _extract_loader_nghiep_vu_grant_tables(sql_clean)
