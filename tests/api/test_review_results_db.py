"""Kiểm thử ghi kết quả thẩm định vào DB, bộ đệm, API lịch sử và chế độ tệp."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.schemas import MedicalRecord
from app.api.service import CaseService
from app.db.bang_luat import prepare_document
from app.db.bang_luat_store import RULE_DOCUMENTS
from app.db.reader import DbReviewService
from app.domain.loader import load_case
from app.rules import renal_dose as renal_dose_mod
from app.storage import feedback_chat as fc_mod
from app.storage import review_results as rr_mod
from app.storage.review_results import (
    DbReviewResultStore,
    NoopReviewResultStore,
    compute_rule_version,
)

ROOT = Path(__file__).resolve().parents[2]

_FAKE_REVIEW_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE y_lenh (
    y_lenh_id TEXT PRIMARY KEY,
    ca_id TEXT UNIQUE
);
CREATE TABLE phan_hoi (
    thoi_diem TEXT NOT NULL,
    ca_id TEXT NOT NULL,
    ma_luat TEXT NOT NULL,
    yeu_to INTEGER NOT NULL,
    chi_tiet_y_lenh_id TEXT NOT NULL,
    phan_hoi TEXT NOT NULL,
    nhom_ly_do TEXT,
    ly_do TEXT,
    nguoi_dung_id TEXT,
    PRIMARY KEY (ca_id, ma_luat, thoi_diem)
);
CREATE TABLE bang_luat_meta (
    ma TEXT PRIMARY KEY,
    ten TEXT,
    phien_ban TEXT,
    ngay TEXT,
    trang_thai TEXT,
    ghi_chu TEXT,
    nguon TEXT,
    phan_khac TEXT NOT NULL DEFAULT '{}',
    sha256_tep TEXT NOT NULL
);
CREATE TABLE ket_qua_tham_dinh (
    ket_qua_id TEXT PRIMARY KEY,
    ca_id TEXT NOT NULL REFERENCES y_lenh(ca_id),
    thoi_diem TEXT NOT NULL,
    phien_ban_luat TEXT NOT NULL,
    so_luat_da_chay INTEGER NOT NULL,
    che_do TEXT NOT NULL,
    tom_tat TEXT NOT NULL
);
CREATE TABLE ket_qua_nhan_dinh (
    ket_qua_id TEXT NOT NULL REFERENCES ket_qua_tham_dinh(ket_qua_id) ON DELETE CASCADE,
    thu_tu INTEGER NOT NULL,
    nhom TEXT NOT NULL,
    nhan_dinh_id TEXT NOT NULL,
    thuoc TEXT NOT NULL,
    ma_luat TEXT,
    yeu_to INTEGER NOT NULL,
    yeu_to_nhan TEXT NOT NULL,
    ket_luan TEXT NOT NULL,
    ket_luan_nhan TEXT NOT NULL,
    muc_do TEXT,
    muc_do_nhan TEXT,
    nguon_goc_ma TEXT NOT NULL,
    nguon_goc_nhan TEXT NOT NULL,
    chi_tiet_y_lenh_id TEXT NOT NULL,
    nhan_xet TEXT NOT NULL,
    can_cu TEXT NOT NULL,
    du_lieu_thieu TEXT NOT NULL,
    PRIMARY KEY (ket_qua_id, thu_tu)
);
"""


class FakeCursor:
    """Con trỏ giả lập trả dict hoặc tuple tương thích psycopg 3."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def fetchall(self) -> list[Any]:
        return list(self._rows)

    def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None


class FakeReviewPgConnection:
    """Kết nối SQLite trong bộ nhớ giả lập bảng kết quả thẩm định và siêu dữ liệu."""

    def __init__(self, *, as_dicts: bool = True) -> None:
        self._db = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
        self._db.executescript(_FAKE_REVIEW_SCHEMA)
        self.as_dicts = as_dicts
        self.statements: list[str] = []
        self.fail_insert_findings = False

    def close(self) -> None:
        self._db.close()

    def seed_case(self, ca_id: str) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO y_lenh (y_lenh_id, ca_id) VALUES (?, ?)",
            (f"YL-{ca_id}", ca_id),
        )

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self._db.execute("BEGIN")
        try:
            yield
        except Exception:
            self._db.rollback()
            raise
        else:
            self._db.commit()

    def _convert_param(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat()
        if hasattr(value, "obj"):
            return json.dumps(value.obj, ensure_ascii=False)
        return value

    def _translate_sql(self, query: str) -> str:
        return query.replace("nghiep_vu.", "").replace("tri_thuc.", "").replace("%s", "?")

    def execute(self, query: str, params: Any = None) -> FakeCursor:
        self.statements.append(query)
        sql_text = self._translate_sql(query)
        bound = tuple(self._convert_param(item) for item in (params or ()))
        cur = self._db.execute(sql_text, bound)
        columns = [desc[0] for desc in cur.description or ()]
        raw_rows = cur.fetchall()
        if not columns:
            return FakeCursor([])
        parsed: list[Any] = []
        for row in raw_rows:
            converted = [
                datetime.fromisoformat(val) if col == "thoi_diem" and isinstance(val, str) else val
                for col, val in zip(columns, row, strict=True)
            ]
            if self.as_dicts:
                parsed.append(dict(zip(columns, converted, strict=True)))
            else:
                parsed.append(tuple(converted))
        return FakeCursor(parsed)

    def executemany(self, query: str, rows: list[tuple[Any, ...]]) -> None:
        self.statements.append(query)
        if self.fail_insert_findings and "ket_qua_nhan_dinh" in query:
            raise psycopg.OperationalError("Lỗi ghi nhận định giả lập")
        sql_text = self._translate_sql(query)
        converted = [tuple(self._convert_param(item) for item in row) for row in rows]
        self._db.executemany(sql_text, converted)


def _patch_db_case_service(
    monkeypatch: pytest.MonkeyPatch,
    cases_ref: list[Any],
    conn: FakeReviewPgConnection,
) -> tuple[list[str], list[str]]:
    read_calls: list[str] = []
    write_calls: list[str] = []

    @contextmanager
    def fake_read_pool(_url: str) -> Iterator[FakeReviewPgConnection]:
        read_calls.append("read")
        yield conn

    @contextmanager
    def fake_write_conn(_url: str) -> Iterator[FakeReviewPgConnection]:
        write_calls.append("write")
        yield conn

    monkeypatch.setenv("CASE_SOURCE", "db")
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("ACCESS_LOG", "off")
    monkeypatch.setenv("CDSS_AI", "off")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/prod")
    monkeypatch.setattr(DbReviewService, "list_cases", lambda self: (list(cases_ref), []))
    monkeypatch.setattr(CaseService, "_administrative", lambda self, cases: {})
    monkeypatch.setattr(CaseService, "_read_medical_record", lambda self, case: MedicalRecord())
    monkeypatch.setattr(fc_mod.read_pool, "connection", fake_read_pool)
    monkeypatch.setattr(fc_mod, "_open_write_connection", fake_write_conn)
    return read_calls, write_calls


def test_schema_has_review_result_tables_and_gold_note() -> None:
    sql_text = (ROOT / "db/schema.sql").read_text(encoding="utf-8")
    blocks = dict(
        re.findall(r"CREATE TABLE IF NOT EXISTS (\w+\.\w+) \(\n(.*?)\n\);", sql_text, re.S)
    )

    assert "nghiep_vu.ket_qua_tham_dinh" in blocks
    assert "nghiep_vu.ket_qua_nhan_dinh" in blocks
    header_body = blocks["nghiep_vu.ket_qua_tham_dinh"]
    for col in (
        "ket_qua_id",
        "ca_id",
        "thoi_diem",
        "phien_ban_luat",
        "so_luat_da_chay",
        "che_do",
        "tom_tat",
    ):
        assert col in header_body
    assert "REFERENCES nghiep_vu.y_lenh(ca_id)" in header_body
    assert "CHECK (che_do IN ('file', 'db'))" in header_body

    finding_body = blocks["nghiep_vu.ket_qua_nhan_dinh"]
    for col in (
        "ket_qua_id",
        "thu_tu",
        "nhom",
        "nhan_dinh_id",
        "thuoc",
        "ma_luat",
        "yeu_to",
        "yeu_to_nhan",
        "ket_luan",
        "ket_luan_nhan",
        "muc_do",
        "muc_do_nhan",
        "nguon_goc_ma",
        "nguon_goc_nhan",
        "chi_tiet_y_lenh_id",
        "nhan_xet",
        "can_cu",
        "du_lieu_thieu",
    ):
        assert col in finding_body
    assert "REFERENCES nghiep_vu.ket_qua_tham_dinh(ket_qua_id)" in finding_body
    revoke_sql = (
        "REVOKE ALL ON nghiep_vu.ket_qua_tham_dinh, nghiep_vu.ket_qua_nhan_dinh FROM PUBLIC;"
    )
    assert revoke_sql in sql_text
    assert "ALTER TABLE nghiep_vu.ket_qua_tham_dinh ENABLE ROW LEVEL SECURITY;" in sql_text
    assert "ALTER TABLE nghiep_vu.ket_qua_nhan_dinh ENABLE ROW LEVEL SECURITY;" in sql_text
    assert "đáp án mẫu (gold)" in sql_text


@pytest.mark.parametrize("as_dicts", [True, False])
def test_db_mode_persists_once_per_evaluation_and_matches_api_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    as_dicts: bool,
) -> None:
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    cases_ref = [case]
    with closing(FakeReviewPgConnection(as_dicts=as_dicts)) as conn:
        conn.seed_case("DEMO-02")
        read_calls, write_calls = _patch_db_case_service(monkeypatch, cases_ref, conn)
        service = CaseService(
            ROOT / "data/mock/demo",
            ROOT / "data/kb/quy_tac_lieu_than.json",
            tmp_path / "feedback.jsonl",
            ai_runner=None,
        )
        assert isinstance(service._review_store, DbReviewResultStore)

        with TestClient(create_app(service)) as client:
            # Tải hàng đợi trước rồi mở ca bệnh giống luồng web thực tế.
            assert client.get("/api/cases").status_code == 200
            service.flush_persist()
            assert len(write_calls) == 0

            first = client.get("/api/cases/DEMO-02")
            assert first.status_code == 200
            detail = first.json()
            service.flush_persist()
            assert len(write_calls) == 1

            # Lần gọi thứ hai trong thời gian bộ đệm không ghi lại.
            second = client.get("/api/cases/DEMO-02")
            assert second.status_code == 200
            service.flush_persist()
            assert len(write_calls) == 1
            assert conn._db.execute("SELECT count(*) FROM ket_qua_tham_dinh").fetchone()[0] == 1

            # Đối chiếu bảng ket_qua_tham_dinh và ket_qua_nhan_dinh với phản hồi API.
            header = conn._db.execute(
                "SELECT ket_qua_id, ca_id, phien_ban_luat, so_luat_da_chay, che_do, tom_tat "
                "FROM ket_qua_tham_dinh"
            ).fetchone()
            assert header is not None
            ket_qua_id, ca_id, phien_ban_luat, so_luat_da_chay, che_do, raw_tom_tat = header
            assert ca_id == "DEMO-02"
            assert len(phien_ban_luat) == 64
            assert so_luat_da_chay == detail["nhan_dinh"]["so_luat_da_chay"]
            assert che_do == "file"
            tom_tat = json.loads(raw_tom_tat)
            assert tom_tat["dem"] == detail["dinh_danh"]["dem"]

            api_findings = [
                *detail["nhan_dinh"]["can_chu_y"],
                *detail["nhan_dinh"]["dat"],
            ]
            assert tom_tat["tong_nhan_dinh"] == len(api_findings)
            stored_rows = conn._db.execute(
                "SELECT thu_tu, nhom, nhan_dinh_id, thuoc, ma_luat, yeu_to, yeu_to_nhan, "
                "ket_luan, ket_luan_nhan, muc_do, muc_do_nhan, nguon_goc_ma, nguon_goc_nhan, "
                "chi_tiet_y_lenh_id, nhan_xet, can_cu, du_lieu_thieu "
                "FROM ket_qua_nhan_dinh WHERE ket_qua_id = ? ORDER BY thu_tu ASC",
                (ket_qua_id,),
            ).fetchall()
            assert len(stored_rows) == len(api_findings)
            attention_count = len(detail["nhan_dinh"]["can_chu_y"])
            for idx, (db_row, api_row) in enumerate(zip(stored_rows, api_findings, strict=True)):
                expected_group = "can_chu_y" if idx < attention_count else "dat"
                assert db_row[0] == idx
                assert db_row[1] == expected_group
                assert db_row[2] == api_row["nhan_dinh_id"]
                assert db_row[3] == api_row["thuoc"]
                assert db_row[4] == api_row["ma_luat"]
                assert db_row[5] == int(api_row["yeu_to"].split(".", 1)[0])
                assert db_row[6] == api_row["yeu_to"]
                assert db_row[7] == api_row["ket_luan_ma"]
                assert db_row[8] == api_row["ket_luan_nhan"]
                assert db_row[9] == api_row["muc_do_ma"]
                assert db_row[10] == api_row["muc_do_nhan"]
                assert db_row[11] == api_row["nguon_goc_ma"]
                assert db_row[12] == api_row["nguon_goc_nhan"]
                assert json.loads(db_row[13]) == api_row["chi_tiet_y_lenh_id"]
                assert db_row[14] == api_row["nhan_xet"]
                assert json.loads(db_row[15]) == api_row["can_cu"]
                assert json.loads(db_row[16]) == api_row["thong_tin_con_thieu"]

            # Không bao giờ ghi vào các bảng đáp án mẫu (gold).
            gold_tables = (
                "lan_tham_dinh",
                "nhan_dinh_thuoc",
                "nghiep_vu.nhan_dinh",
                "nghiep_vu.can_cu",
            )
            for gold_table in gold_tables:
                assert not any(gold_table in stmt for stmt in conn.statements)

            # Xoá bộ đệm kết quả → chạy luật thật lại → ghi lần thứ hai.
            service._results.clear()
            assert client.get("/api/cases/DEMO-02").status_code == 200
            service.flush_persist()
            assert len(write_calls) == 2
            assert conn._db.execute("SELECT count(*) FROM ket_qua_tham_dinh").fetchone()[0] == 2

            # Hết hạn TTL và dữ liệu ca thay đổi → chạy luật thật lại → ghi lần thứ ba.
            cases_ref[0] = case.model_copy(update={"mo_ta_ngan": "Hồ sơ cập nhật sau TTL"})
            service._next_case_refresh_at = 0.0
            assert client.get("/api/cases/DEMO-02").status_code == 200
            service.flush_persist()
            assert len(write_calls) == 3
            assert conn._db.execute("SELECT count(*) FROM ket_qua_tham_dinh").fetchone()[0] == 3

            # Đọc lịch sử qua API mới (dùng read_pool, mới nhất trước).
            read_before = len(read_calls)
            hist_resp = client.get("/api/cases/DEMO-02/lich-su-tham-dinh")
            assert hist_resp.status_code == 200
            assert hist_resp.headers["cache-control"] == "private, no-store"
            assert len(read_calls) == read_before + 1
            hist_body = hist_resp.json()
            assert hist_body["ca_id"] == "DEMO-02"
            assert len(hist_body["lich_su"]) == 3
            assert len({item["ket_qua_id"] for item in hist_body["lich_su"]}) == 3
            timestamps = [
                datetime.fromisoformat(item["thoi_diem"]) for item in hist_body["lich_su"]
            ]
            assert timestamps == sorted(timestamps, reverse=True)
            assert hist_body["lich_su"][0]["tom_tat"]["tong_nhan_dinh"] == len(api_findings)

            missing_resp = client.get("/api/cases/KHONG-CO/lich-su-tham-dinh")
            assert missing_resp.status_code == 404


def test_write_error_and_rollback_do_not_break_api_or_leak_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    secret_dsn = "postgresql://demo:mat-khau-tuyet-mat@db.invalid/prod"
    monkeypatch.setenv("CASE_SOURCE", "db")
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("ACCESS_LOG", "off")
    monkeypatch.setenv("CDSS_AI", "off")
    monkeypatch.setenv("DATABASE_URL", secret_dsn)
    monkeypatch.setattr(DbReviewService, "list_cases", lambda self: ([case], []))
    monkeypatch.setattr(CaseService, "_administrative", lambda self, cases: {})
    monkeypatch.setattr(CaseService, "_read_medical_record", lambda self, case: MedicalRecord())

    with closing(FakeReviewPgConnection(as_dicts=True)) as read_conn:

        @contextmanager
        def fake_read_pool(_url: str) -> Iterator[FakeReviewPgConnection]:
            yield read_conn

        @contextmanager
        def broken_write(url: str) -> Iterator[Any]:
            raise psycopg.OperationalError(url)
            yield  # pragma: no cover

        monkeypatch.setattr(fc_mod.read_pool, "connection", fake_read_pool)
        monkeypatch.setattr(fc_mod, "_open_write_connection", broken_write)

        service = CaseService(
            ROOT / "data/mock/demo",
            ROOT / "data/kb/quy_tac_lieu_than.json",
            tmp_path / "feedback.jsonl",
            ai_runner=None,
        )
        with caplog.at_level("WARNING", logger="app.storage.review_results"):
            with TestClient(create_app(service)) as client:
                resp = client.get("/api/cases/DEMO-02")
                assert resp.status_code == 200
                assert resp.json()["nhan_dinh"]["can_chu_y"]
        assert "Không lưu được kết quả thẩm định" in caplog.text
        assert "mat-khau-tuyet-mat" not in caplog.text

    # Kiểm tra rollback toàn giao dịch nếu chèn bảng con ket_qua_nhan_dinh thất bại.
    with closing(FakeReviewPgConnection(as_dicts=True)) as tx_conn:
        tx_conn.seed_case("DEMO-02")
        tx_conn.fail_insert_findings = True
        _patch_db_case_service(monkeypatch, [case], tx_conn)
        tx_service = CaseService(
            ROOT / "data/mock/demo",
            ROOT / "data/kb/quy_tac_lieu_than.json",
            tmp_path / "feedback2.jsonl",
            ai_runner=None,
        )
        with TestClient(create_app(tx_service)) as client:
            resp = client.get("/api/cases/DEMO-02")
            assert resp.status_code == 200
        assert tx_conn._db.execute("SELECT count(*) FROM ket_qua_tham_dinh").fetchone()[0] == 0
        assert tx_conn._db.execute("SELECT count(*) FROM ket_qua_nhan_dinh").fetchone()[0] == 0


def test_history_read_error_is_sanitized_to_503(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    secret_dsn = "postgresql://demo:bi-mat-khong-duoc-lo@db.invalid/prod"
    monkeypatch.setenv("CASE_SOURCE", "db")
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("ACCESS_LOG", "off")
    monkeypatch.setenv("CDSS_AI", "off")
    monkeypatch.setenv("DATABASE_URL", secret_dsn)
    monkeypatch.setattr(DbReviewService, "list_cases", lambda self: ([case], []))

    @contextmanager
    def broken_read(url: str) -> Iterator[Any]:
        raise psycopg.OperationalError(url)
        yield  # pragma: no cover

    store = DbReviewResultStore(read_connection=broken_read, write_connection=broken_read)
    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "feedback.jsonl",
        ai_runner=None,
        review_store=store,
    )
    with TestClient(create_app(service), raise_server_exceptions=False) as client:
        resp = client.get("/api/cases/DEMO-02/lich-su-tham-dinh")
    assert resp.status_code == 503
    assert "bi-mat-khong-duoc-lo" not in resp.text


def test_file_mode_never_writes_to_db_and_returns_empty_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CASE_SOURCE", "file")
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("ACCESS_LOG", "off")
    monkeypatch.setenv("CDSS_AI", "off")

    def forbid_db(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("Chế độ tệp không được chạm DB")

    monkeypatch.setattr(rr_mod.read_pool, "connection", forbid_db)
    monkeypatch.setattr(fc_mod, "_open_write_connection", forbid_db)
    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "feedback.jsonl",
        ai_runner=None,
    )
    assert isinstance(service._review_store, NoopReviewResultStore)
    with TestClient(create_app(service)) as client:
        assert client.get("/api/cases/DEMO-02").status_code == 200
        hist = client.get("/api/cases/DEMO-02/lich-su-tham-dinh")
        assert hist.status_code == 200
        assert hist.json() == {"ca_id": "DEMO-02", "lich_su": []}


def test_rule_version_matches_between_file_and_db_meta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rules_path = renal_dose_mod.DEFAULT_RENAL_RULES_PATH
    rules = renal_dose_mod.load_renal_rules(rules_path)
    monkeypatch.setenv("KB_SOURCE", "file")
    file_mode, file_hash = compute_rule_version(rules_path, rules, root=ROOT)
    assert file_mode == "file"
    assert len(file_hash) == 64

    with closing(FakeReviewPgConnection(as_dicts=True)) as conn:
        for spec in RULE_DOCUMENTS:
            prepared = prepare_document(spec, ROOT)
            meta = prepared.meta_row
            conn._db.execute(
                "INSERT INTO bang_luat_meta (ma, phien_ban, sha256_tep) VALUES (?, ?, ?)",
                (meta["ma"], meta["phien_ban"], meta["sha256_tep"]),
            )

        @contextmanager
        def fake_read() -> Iterator[FakeReviewPgConnection]:
            yield conn

        monkeypatch.setenv("KB_SOURCE", "db")
        db_mode, db_hash = compute_rule_version(
            rules_path,
            rules,
            read_conn_factory=fake_read,
            root=ROOT,
        )
        assert db_mode == "db"
        assert db_hash == file_hash


@pytest.mark.skipif(
    not (os.getenv("CDSS_TEST_PG_INTEGRATION") == "1" and os.getenv("DATABASE_URL")),
    reason="Bỏ qua kiểm tích hợp PostgreSQL khi không bật CDSS_TEST_PG_INTEGRATION=1",
)
def test_postgres_real_db_review_results_optional() -> None:
    store = DbReviewResultStore()
    assert isinstance(store.list_history("__khong_ton_tai__"), list)
    t1 = datetime.now(UTC) - timedelta(seconds=1)
    assert t1.tzinfo is not None
