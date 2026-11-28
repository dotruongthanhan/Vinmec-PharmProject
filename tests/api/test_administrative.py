"""Kiểm hợp đồng hành chính và ranh giới dữ liệu gửi AI."""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.api.service import CaseService
from app.config.settings import CaseContextSettings
from app.db import administrative, reader
from app.db.sources import prepare_cases
from app.domain.loader import load_case
from app.llm.case_context import build_case_context
from app.pipeline import run_case
from app.rules import load_renal_rules

ROOT = Path(__file__).resolve().parents[2]


def test_administrative_view_has_all_encounters_and_stays_outside_ai() -> None:
    rows = prepare_cases(ROOT).rows
    cases, errors = reader.build_cases(rows)
    assert not errors
    case = next(item for item in cases if item.ca_id == "HS-022")
    view = administrative.build_administrative(rows, [case.nguoi_benh.nguoi_benh_id])
    record = view[case.nguoi_benh.nguoi_benh_id]
    assert record.dinh_danh_day_du.ho_ten == "Nguyễn Văn 22"
    assert len(record.lich_su_vao_vien) == len(
        [
            r
            for r in rows["nghiep_vu.dot_dieu_tri"]
            if r["nguoi_benh_id"] == case.nguoi_benh.nguoi_benh_id
        ]
    )
    result = run_case(case, load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json"))
    context, _ = build_case_context(
        case, result, CaseContextSettings(max_chars=30000, notes_latest_n=5)
    )
    for key in ("ho_ten", "ngay_sinh", "dia_chi", "dien_thoai"):
        assert key not in case.model_dump_json()
        assert key not in context.van_ban_ca
    assert record.dinh_danh_day_du.ho_ten not in context.van_ban_ca


def test_demo_loader_discards_only_administrative_extensions(tmp_path: Path) -> None:
    raw = json.loads((ROOT / "data/mock/_goc_truoc_T45/DEMO-01.json").read_text("utf-8"))
    raw["hanh_chinh"] = {"ho_ten": "TEN_GIA_LAP_BI_MAT"}
    raw["dot_dieu_tri"]["quan_ly"] = {"so_giuong": "G-01"}
    path = tmp_path / "case.json"
    path.write_text(json.dumps(raw), "utf-8")
    case = load_case(path)
    assert "TEN_GIA_LAP_BI_MAT" not in case.model_dump_json()


def test_file_mode_has_empty_admin_without_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CASE_SOURCE", "file")
    query = Mock(side_effect=AssertionError("Không đọc DB"))
    monkeypatch.setattr(administrative, "read_administrative", query)
    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "feedback.jsonl",
        ai_runner=None,
    )
    try:
        detail = service.get_case("DEMO-01")
        assert detail.dinh_danh_day_du is None
        assert detail.quan_ly_nguoi_benh is None
        assert detail.lich_su_vao_vien == []
        query.assert_not_called()
    finally:
        service.shutdown()


def test_reader_uses_only_scoped_selects_in_read_only_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = prepare_cases(ROOT).rows
    patients = [row["nguoi_benh_id"] for row in rows["nghiep_vu.nguoi_benh"]]
    connection = MagicMock()
    connection.__enter__.return_value = connection
    statements = []

    def execute(query: object, params: tuple | None = None) -> MagicMock:
        statement = query if isinstance(query, str) else query.as_string()
        if statement.startswith("SET LOCAL"):
            assert statement == "SET LOCAL statement_timeout = 8000"
            return MagicMock()
        statements.append((statement, params))
        assert statement.startswith("SELECT ")
        if "thuoc_text" in statement:
            result = [
                {
                    "y_lenh_id": rows["nghiep_vu.y_lenh"][0]["y_lenh_id"],
                    "thuoc_text": "Thuốc giả lập 5 mg",
                }
            ]
        else:
            table = next(name for name in rows if f'"{name.split(".")[1]}"' in statement)
            result = rows[table]
        cursor = MagicMock()
        cursor.fetchall.return_value = result
        return cursor

    connection.execute.side_effect = execute
    connect = Mock(return_value=connection)
    monkeypatch.setattr(administrative.psycopg, "connect", connect)
    monkeypatch.setattr(administrative, "get_secret", lambda key: "test-dsn")
    result = administrative.read_administrative(patients)
    assert len(result) == 66
    assert sum(len(record.lich_su_vao_vien) for record in result.values()) == 93
    assert connection.read_only is True
    assert connection.isolation_level == psycopg.IsolationLevel.REPEATABLE_READ
    assert "default_transaction_read_only=on" in connect.call_args.kwargs["options"]
    assert all("ANY(%s)" in statement and params[0] for statement, params in statements)
    assert any(
        '"chan_doan"' in statement and statement.endswith("ORDER BY chan_doan_id")
        for statement, _ in statements
    )
    assert any(
        entry.phieu_dieu_tri for record in result.values() for entry in record.lich_su_vao_vien
    )


def test_http_admin_is_uncached_and_never_logged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app.api.main import create_app

    monkeypatch.setenv("CASE_SOURCE", "db")
    monkeypatch.setenv("CDSS_AI", "off")
    monkeypatch.setenv("ACCESS_LOG", "on")
    rows = prepare_cases(ROOT).rows
    monkeypatch.setattr(reader, "read_case_rows", lambda: rows)
    from app.db import medical_record

    monkeypatch.setattr(
        medical_record,
        "read_medical_record",
        lambda pid, cid: medical_record.build_medical_record(rows, pid, cid),
    )
    records = administrative.build_administrative(rows, ["NB-HS-022"])
    identity = records["NB-HS-022"].dinh_danh_day_du
    identity.ho_ten = "TEN_GIA_LAP_KHONG_GHI_LOG"
    query = Mock(return_value=records)
    monkeypatch.setattr(administrative, "read_administrative", query)
    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "feedback.jsonl",
        ai_runner=None,
    )
    with TestClient(create_app(service, access_log_dir=tmp_path)) as client:
        response = client.get("/api/cases/HS-022")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["dinh_danh_day_du"]["ho_ten"] == identity.ho_ten
        identity.ho_ten = "TEN_MOI_KHONG_CACHE"
        assert (
            client.get("/api/cases/HS-022").json()["dinh_danh_day_du"]["ho_ten"] == identity.ho_ten
        )
        assert query.call_count == 2
        assert client.get("/api/cases").headers["cache-control"] == "private, no-store"
    logs = "".join(p.read_text("utf-8") for p in tmp_path.glob("nhat_ky_truy_cap-*.jsonl"))
    assert logs
    for marker in (
        "TEN_GIA_LAP_KHONG_GHI_LOG",
        "TEN_MOI_KHONG_CACHE",
        "ho_ten",
        "ngay_sinh",
        "dia_chi",
        "dien_thoai",
    ):
        assert marker not in logs + caplog.text
        assert marker not in repr(service._cases) + repr(service._results)


def test_reader_error_hides_personal_data(monkeypatch: pytest.MonkeyPatch) -> None:
    marker = "TEN_NGAY_SINH_DIA_CHI_DIEN_THOAI_GIA_LAP"
    monkeypatch.setattr(administrative, "get_secret", lambda key: "test-dsn")
    monkeypatch.setattr(administrative.psycopg, "connect", Mock(side_effect=psycopg.Error(marker)))
    with pytest.raises(reader.DatabaseReadError) as exc:
        administrative.read_administrative(["NB-HS-022"])
    assert marker not in str(exc.value)
