"""Hợp đồng hồ sơ, fallback file và bảo vệ route hiện có."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.service import CaseService
from app.db import administrative, medical_record, reader
from app.db.sources import prepare_cases

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CDSS_AI", "off")
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("ACCESS_LOG", "off")
    monkeypatch.setattr(
        medical_record.psycopg, "connect", Mock(side_effect=AssertionError("Không kết nối DB thật"))
    )


def make_service(tmp_path: Path) -> CaseService:
    return CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "feedback.jsonl",
        ai_runner=None,
    )


def test_file_detail_has_inferred_orders_and_no_sheets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CASE_SOURCE", "file")
    monkeypatch.setattr(
        medical_record, "read_medical_record", Mock(side_effect=AssertionError("File không đọc DB"))
    )
    with TestClient(create_app(make_service(tmp_path))) as client:
        response = client.get("/api/cases/DEMO-01")
    assert response.status_code == 200
    detail = response.json()
    assert detail["phieu_dieu_tri"] == []
    assert len(detail["danh_sach_y_lenh"]) == 1
    focus = [order for order in detail["danh_sach_y_lenh"] if order["la_trong_tam"]]
    assert len(focus) == 1
    assert focus[0]["dong"] == detail["chi_tiet"]["y_lenh"]["cho_duyet"]["dong"]
    assert response.headers["cache-control"] == "private, no-store"


def test_db_detail_adds_every_order_and_sheet_without_changing_old_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CASE_SOURCE", "db")
    rows = prepare_cases(ROOT).rows
    monkeypatch.setattr(reader, "read_case_rows", lambda: rows)
    monkeypatch.setattr(
        administrative,
        "read_administrative",
        lambda ids: administrative.build_administrative(rows, ids),
    )
    monkeypatch.setattr(
        medical_record,
        "read_medical_record",
        lambda pid, cid: medical_record.build_medical_record(rows, pid, cid),
    )
    with TestClient(create_app(make_service(tmp_path))) as client:
        response = client.get("/api/cases/HS-022")
    assert response.status_code == 200
    detail = response.json()
    assert len(detail["danh_sach_y_lenh"]) == 7
    assert detail["phieu_dieu_tri"]
    assert len(detail["lich_su_vao_vien"]) == 2
    assert detail["dinh_danh_day_du"] and detail["quan_ly_nguoi_benh"]
    assert detail["chi_tiet"]["y_lenh"]["cho_duyet"]["dong"]


def test_db_record_errors_are_sanitized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASE_SOURCE", "db")
    monkeypatch.setattr(reader, "read_case_rows", lambda: prepare_cases(ROOT).rows)
    monkeypatch.setattr(administrative, "read_administrative", lambda ids: {})
    monkeypatch.setattr(
        medical_record, "read_medical_record", Mock(side_effect=reader.DatabaseReadError("SECRET"))
    )
    with TestClient(create_app(make_service(tmp_path)), raise_server_exceptions=False) as client:
        response = client.get("/api/cases/HS-022")
    assert response.status_code == 503
    assert "SECRET" not in response.text


def test_file_background_order_is_inferred_from_active_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CASE_SOURCE", "file")
    service = make_service(tmp_path)
    case = service._get_case("DEMO-01")
    active = case.y_lenh_cho_duyet.chi_tiet[0].model_copy(
        update={"chi_tiet_y_lenh_id": "CT-NEN-GIA-LAP", "trang_thai_dong": "active"}
    )
    case = case.model_copy(update={"thuoc_dang_dung": [active]})
    monkeypatch.setattr(service, "_get_case", lambda cid: case)
    with TestClient(create_app(service)) as client:
        response = client.get("/api/cases/DEMO-01")
    assert response.status_code == 200
    detail = response.json()
    background = next(order for order in detail["danh_sach_y_lenh"] if not order["la_trong_tam"])
    assert background["y_lenh_id"] == "YL-DEMO-01-NEN"
    assert background["trang_thai"] == "dang_thuc_hien"
    assert background["dong"] == detail["chi_tiet"]["y_lenh"]["dang_dung"]["dong"]
    assert detail["phieu_dieu_tri"] == []
