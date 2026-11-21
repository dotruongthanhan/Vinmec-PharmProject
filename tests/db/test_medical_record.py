"""Đọc đủ lịch sử, tách khỏi CaBenh và kiểm truy vấn gộp chỉ đọc."""

import copy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import psycopg
import pytest

from app.db import reader
from app.db.sources import Batch, prepare_cases

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def batch() -> Batch:
    return prepare_cases(ROOT)


def test_record_has_every_encounter_without_building_case(batch: Batch) -> None:
    from app.db import medical_record

    before = copy.deepcopy(batch.rows)
    with patch.object(reader, "build_case", side_effect=AssertionError("Không dựng CaBenh")):
        record = medical_record.build_medical_record(batch.rows, "NB-HS-022", "HS-022")
    assert len(record.danh_sach_y_lenh) == 7
    assert {order.thu_tu_dot for order in record.danh_sach_y_lenh} == {1, 2}
    assert [order.y_lenh_id for order in record.danh_sach_y_lenh if order.la_trong_tam] == [
        "YL-HS-022-05"
    ]
    expected = sum(
        1
        for sheet in batch.rows["nghiep_vu.phieu_dieu_tri"]
        if sheet["dot_dieu_tri_id"] in {order.dot_dieu_tri_id for order in record.danh_sach_y_lenh}
    )
    assert len(record.phieu_dieu_tri) == expected > 0
    assert all(order.dong and "Lịch dùng" in order.dong[0] for order in record.danh_sach_y_lenh)
    assert batch.rows == before
    shuffled = {key: list(reversed(rows)) for key, rows in batch.rows.items()}
    assert medical_record.build_medical_record(shuffled, "NB-HS-022", "HS-022") == record
    for sheet in record.phieu_dieu_tri:
        assert set(sheet.y_lenh_trong_ngay) <= {
            order.y_lenh_id
            for order in record.danh_sach_y_lenh
            if order.dot_dieu_tri_id == sheet.dot_dieu_tri_id
        }


def test_all_records_match_source_counts(batch: Batch) -> None:
    from app.db.medical_record import build_medical_record

    total = 0
    for patient in batch.rows["nghiep_vu.nguoi_benh"]:
        pid = patient["nguoi_benh_id"]
        ids = {
            row["dot_dieu_tri_id"]
            for row in batch.rows["nghiep_vu.dot_dieu_tri"]
            if row["nguoi_benh_id"] == pid
        }
        focus = next(
            row
            for row in batch.rows["nghiep_vu.y_lenh"]
            if row["dot_dieu_tri_id"] in ids and row["ca_id"]
        )
        record = build_medical_record(batch.rows, pid, focus["ca_id"])
        assert len(record.danh_sach_y_lenh) == sum(
            row["dot_dieu_tri_id"] in ids for row in batch.rows["nghiep_vu.y_lenh"]
        )
        total += len(record.phieu_dieu_tri)
    assert total == 333


def test_grouped_reader_is_readonly_and_filters_to_patient(
    batch: Batch, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.db import medical_record

    connection = MagicMock()
    statements: list[tuple[str, object]] = []

    def execute(query: object, params: object = None) -> Mock:
        statement = query if isinstance(query, str) else query.as_string()
        if statement.startswith("SET LOCAL"):
            assert statement == "SET LOCAL statement_timeout = 8000"
            return Mock()
        statements.append((statement, params))
        table = next(name for name in batch.rows if name in statement.replace('"', ""))
        rows = copy.deepcopy(batch.rows[table])
        if table == "nghiep_vu.dot_dieu_tri":
            for row in rows:
                row["thoi_diem_bat_dau"] = datetime.fromisoformat(
                    row["thoi_diem_bat_dau"]
                ).astimezone(UTC)
        return Mock(fetchall=lambda: rows)

    connection.execute.side_effect = execute
    connect = Mock(return_value=connection)
    monkeypatch.setattr(medical_record.psycopg, "connect", connect)
    monkeypatch.setattr(medical_record, "get_secret", lambda key: "test-dsn")
    record = medical_record.read_medical_record("NB-HS-022", "HS-022")
    assert len(record.danh_sach_y_lenh) == 7
    assert connection.read_only is True
    assert connection.isolation_level == psycopg.IsolationLevel.REPEATABLE_READ
    assert "default_transaction_read_only=on" in connect.call_args.kwargs["options"]
    assert len(statements) == 7
    assert all(
        statement.startswith("SELECT") and "ANY(%s)" in statement for statement, _ in statements
    )
    rows = medical_record.read_medical_record_rows()
    assert rows["nghiep_vu.dot_dieu_tri"][0]["thoi_diem_bat_dau"].utcoffset() == timedelta(hours=7)


def test_reader_sanitizes_database_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.db import medical_record

    monkeypatch.setattr(medical_record, "get_secret", lambda key: "test-dsn")
    monkeypatch.setattr(
        medical_record.psycopg, "connect", Mock(side_effect=psycopg.OperationalError("SECRET"))
    )
    with pytest.raises(reader.DatabaseReadError) as exc:
        medical_record.read_medical_record("NB-HS-022", "HS-022")
    assert "SECRET" not in str(exc.value)


def test_verify_ho_so_matches_all_rows_and_detects_missing_orders(
    batch: Batch, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.db import medical_record

    monkeypatch.setattr(medical_record, "read_medical_record_rows", lambda: batch.rows)
    assert medical_record.verify_ho_so() == 0
    output = capsys.readouterr().out
    assert "HS-022: y_lệnh=7/7" in output
    assert output.count("KHỚP") == 66
    missing = copy.deepcopy(batch.rows)
    missing["nghiep_vu.y_lenh"] = [
        row for row in missing["nghiep_vu.y_lenh"] if row["y_lenh_id"] != "YL-HS-022-01"
    ]
    monkeypatch.setattr(medical_record, "read_medical_record_rows", lambda: missing)
    assert medical_record.verify_ho_so() == 1
    assert "HS-022: y_lệnh=6/7" in capsys.readouterr().out
    monkeypatch.setattr(medical_record, "read_medical_record_rows", lambda: batch.rows)
    original = medical_record.build_medical_record

    def omit_order(rows: reader.Rows, pid: str, cid: str) -> object:
        result = original(rows, pid, cid)
        result.danh_sach_y_lenh.pop()
        return result

    monkeypatch.setattr(medical_record, "build_medical_record", omit_order)
    assert medical_record.verify_ho_so() == 1
    assert "LỆCH" in capsys.readouterr().out
