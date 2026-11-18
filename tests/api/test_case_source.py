"""Kiểm nguồn ca, đường lui tệp và lỗi DB qua đúng hợp đồng HTTP."""

from pathlib import Path
from unittest.mock import Mock

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.api import schemas
from app.api.service import CaseService
from app.config.settings import load_case_source
from app.core.errors import ConfigError
from app.db import administrative, medical_record, reader
from app.db.sources import prepare_cases
from app.ui.services import PipelineReviewService

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def disable_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CDSS_AI", "off")
    monkeypatch.setenv("ACCESS_LOG", "off")


def make_service(tmp_path: Path) -> CaseService:
    return CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
        ai_runner=None,
    )


@pytest.mark.parametrize("source", [None, "file"])
def test_file_source_preserves_six_demo_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str | None
) -> None:
    from app.api.main import create_app

    if source is None:
        monkeypatch.delenv("CASE_SOURCE", raising=False)
    else:
        monkeypatch.setenv("CASE_SOURCE", source)
    monkeypatch.setattr(reader, "read_case_rows", Mock(side_effect=AssertionError("Không đọc DB")))
    service = make_service(tmp_path)
    assert isinstance(service._loader, PipelineReviewService)
    assert load_case_source() == "file"
    with TestClient(create_app(service)) as client:
        body = client.get("/api/cases").json()
        assert len(body["cases"]) == 6
        assert body["loi_nap"] == []
        assert client.get("/api/cases/HS-022").status_code == 404


def test_db_source_returns_66_and_hs022_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.main import create_app

    monkeypatch.setenv("CASE_SOURCE", "db")
    query = Mock(return_value=prepare_cases(ROOT).rows)
    monkeypatch.setattr(
        medical_record,
        "read_medical_record",
        lambda pid, cid: medical_record.build_medical_record(query.return_value, pid, cid),
    )
    monkeypatch.setattr(reader, "read_case_rows", query)
    monkeypatch.setattr(
        administrative,
        "read_administrative",
        lambda ids: administrative.build_administrative(prepare_cases(ROOT).rows, ids),
    )
    service = make_service(tmp_path)
    assert isinstance(service._loader, reader.DbReviewService)
    assert query.call_count == 0
    with TestClient(create_app(service)) as client:
        assert client.get("/api/health").status_code == 200
        query.assert_not_called()
        response = client.get("/api/cases")
        assert response.status_code == 200
        queue = schemas.DanhSachCa.model_validate(response.json())
        assert len(queue.cases) == 66 and not queue.loi_nap
        response = client.get("/api/cases/HS-022")
        assert response.status_code == 200
        detail = schemas.ChiTietCa.model_validate(response.json())
        assert detail.dinh_danh.ca_id == "HS-022"
        assert detail.tom_tat.chan_doan
        assert detail.chi_tiet.xet_nghiem
        assert detail.chi_tiet.y_lenh
        client.get("/api/cases")
        query.assert_called_once()


@pytest.mark.parametrize("failure", ["missing", "connection"])
def test_db_failure_keeps_health_and_hides_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    from app.api.main import create_app

    monkeypatch.setenv("CASE_SOURCE", "db")
    marker = "SECRET_CONNEXION_FACTICE"
    if failure == "missing":
        monkeypatch.setattr(reader, "get_secret", Mock(side_effect=ConfigError("DATABASE_URL")))
    else:
        monkeypatch.setattr(reader, "get_secret", Mock(return_value=marker))
        monkeypatch.setattr(
            reader.psycopg, "connect", Mock(side_effect=psycopg.OperationalError(marker))
        )
    with TestClient(create_app(make_service(tmp_path)), raise_server_exceptions=False) as client:
        assert client.get("/api/health").status_code == 200
        bodies = []
        for path in (
            "/api/cases",
            "/api/cases/HS-022",
            "/api/cases/HS-022/records/test",
            "/api/cases/HS-022/ai",
            "/api/cases/HS-022/sources/test",
        ):
            response = client.get(path)
            assert response.status_code == 503
            body = response.json()
            assert set(body) == {"loi"}
            assert body["loi"]["ma"] == "loi_he_thong"
            assert marker not in response.text
            bodies.append(body)
        assert all(body == bodies[0] for body in bodies)
        assert (
            "DATABASE_URL" in bodies[0]["loi"]["thong_bao"]
            if failure == "missing"
            else ("Không thể đọc ca bệnh" in bodies[0]["loi"]["thong_bao"])
        )


def test_create_app_selects_db_without_connecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.main import create_app

    monkeypatch.setenv("CASE_SOURCE", "db")
    query = Mock(side_effect=AssertionError("Không đọc DB lúc khởi tạo"))
    monkeypatch.setattr(reader, "read_case_rows", query)
    application = create_app(access_log_dir=tmp_path)
    assert isinstance(application.state.service._loader, reader.DbReviewService)
    application.state.service.shutdown()
    query.assert_not_called()


def test_invalid_source_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASE_SOURCE", "invalide")
    with pytest.raises(ConfigError, match="CASE_SOURCE phải là db hoặc file"):
        load_case_source()
