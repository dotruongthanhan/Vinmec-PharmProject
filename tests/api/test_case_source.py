"""Kiểm nguồn ca, đường lui tệp và lỗi DB qua đúng hợp đồng HTTP."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from logging import WARNING
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.api import schemas
from app.api.service import AiRunner, CaseService
from app.config.settings import load_case_cache_ttl, load_case_source
from app.core.errors import ConfigError
from app.db import administrative, medical_record, reader
from app.db.sources import prepare_cases
from app.domain.models import CaBenh
from app.orchestration.ai_review import AiRunResult
from app.pipeline import KetQuaThamDinh
from app.ui.services import PipelineReviewService
from tests.api.test_ai_routes import _FakeAiRunner, _poll_ai_until_done

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def disable_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CDSS_AI", "off")
    monkeypatch.setenv("ACCESS_LOG", "off")


def make_service(tmp_path: Path, ai_runner: AiRunner | None = None) -> CaseService:
    return CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
        ai_runner=ai_runner,
    )


def test_db_reads_do_not_hold_case_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASE_SOURCE", "db")
    service = make_service(tmp_path)
    rows = prepare_cases(ROOT).rows

    def lock_is_free() -> bool:
        if not service._lock.acquire(blocking=False):
            return False
        service._lock.release()
        return True

    def read_cases() -> reader.Rows:
        assert other_thread.submit(lock_is_free).result(timeout=2)
        return rows

    def read_admin(ids: list[str]) -> dict[str, schemas.AdministrativeRecord]:
        assert other_thread.submit(lock_is_free).result(timeout=2)
        return {}

    def read_record(pid: str, cid: str) -> schemas.MedicalRecord:
        assert other_thread.submit(lock_is_free).result(timeout=2)
        return medical_record.build_medical_record(rows, pid, cid)

    monkeypatch.setattr(reader, "read_case_rows", read_cases)
    monkeypatch.setattr(administrative, "read_administrative", read_admin)
    monkeypatch.setattr(medical_record, "read_medical_record", read_record)
    try:
        with ThreadPoolExecutor(max_workers=1) as other_thread:
            assert service.list_cases().cases
            assert service.get_case("HS-022").danh_sach_y_lenh
    finally:
        service.shutdown()


@pytest.mark.parametrize("running", [True, False])
def test_db_ttl_refresh_preserves_unchanged_ai_and_evicts_changed_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, running: bool
) -> None:
    from app.api.main import create_app

    monkeypatch.setenv("CASE_SOURCE", "db")
    monkeypatch.setenv("CASE_CACHE_TTL_SECONDS", "10")
    monotonic = Mock(return_value=0)
    monkeypatch.setattr("app.api.service.time", SimpleNamespace(monotonic=monotonic))
    rows = prepare_cases(ROOT).rows
    query = Mock(return_value=rows)
    monkeypatch.setattr(reader, "read_case_rows", query)
    monkeypatch.setattr(administrative, "read_administrative", lambda ids: {})
    monkeypatch.setattr(
        medical_record,
        "read_medical_record",
        lambda pid, cid: medical_record.build_medical_record(query.return_value, pid, cid),
    )
    runner = _FakeAiRunner()
    release = Event()
    if not running:
        release.set()

    def run(ca: CaBenh, result: KetQuaThamDinh) -> AiRunResult:
        assert release.wait(timeout=5)
        return runner.run(ca, result)

    service = make_service(tmp_path, SimpleNamespace(run=run))
    with TestClient(create_app(service)) as client:
        try:
            first = client.get("/api/cases").json()
            assert client.post("/api/cases/DEMO-02/ai").json()["trang_thai"] == "dang_chay"
            if not running:
                completed = _poll_ai_until_done(client, "DEMO-02")
                assert completed["trang_thai"] == "xong"
            unchanged_rules = service._results["DEMO-02"]
            changed_rules = service._results["DEMO-01"]
            query.return_value = {
                **rows,
                "nghiep_vu.y_lenh": [
                    {
                        **order,
                        "mo_ta_ngan": "Ca mô phỏng đã cập nhật.",
                    }
                    if order["ca_id"] == "DEMO-01"
                    else {**order, "ca_id": "DEMO-MOI"}
                    if order["ca_id"] == "DEMO-03"
                    else order
                    for order in rows["nghiep_vu.y_lenh"]
                ],
            }
            monotonic.return_value = 9
            assert client.get("/api/cases").json()["lam_moi_luc"] == first["lam_moi_luc"]
            query.assert_called_once()

            monotonic.return_value = 10
            removed = client.get("/api/cases/DEMO-03")
            assert removed.status_code == 404
            assert removed.json()["loi"]["ma"] == "khong_tim_thay"
            assert "DEMO-01" not in service._results and "DEMO-03" not in service._results
            refreshed = client.get("/api/cases").json()
            assert refreshed["lam_moi_luc"] != first["lam_moi_luc"]
            assert any(row["ca_id"] == "DEMO-MOI" for row in refreshed["cases"])
            assert service._results["DEMO-02"] is unchanged_rules
            assert service._results["DEMO-01"] is not changed_rules
            assert query.call_count == 2
            after_refresh = client.get("/api/cases/DEMO-02/ai").json()
            if running:
                assert after_refresh["trang_thai"] == "dang_chay"
                release.set()
                assert _poll_ai_until_done(client, "DEMO-02")["trang_thai"] == "xong"
            else:
                assert after_refresh == completed
            assert runner.calls == 1
        finally:
            release.set()


@pytest.mark.parametrize("empty", [False, True])
def test_db_refresh_error_keeps_cached_response_and_retries_after_15_seconds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, empty: bool
) -> None:
    from app.api.main import create_app

    monkeypatch.setenv("CASE_SOURCE", "db")
    monkeypatch.setenv("CASE_CACHE_TTL_SECONDS", "60")
    monotonic = Mock(return_value=0)
    monkeypatch.setattr("app.api.service.time", SimpleNamespace(monotonic=monotonic))
    cases, errors = reader.build_cases(prepare_cases(ROOT).rows)
    marker = "chi-tiet-loi-gia-lap"
    first_load = ([] if empty else cases, errors)
    cases = cases[:1] if empty else []
    loader = Mock(side_effect=[first_load, reader.DatabaseReadError(marker), (cases, [])])
    service = make_service(tmp_path)
    monkeypatch.setattr(service._loader, "list_cases", loader)
    monkeypatch.setattr(administrative, "read_administrative", lambda ids: {})

    with TestClient(create_app(service)) as client:
        first = client.get("/api/cases")
        assert first.status_code == 200
        assert bool(first.json()["cases"]) is not empty
        load_time = first.json()["lam_moi_luc"]
        results = service._results.copy()

        monotonic.return_value = 60
        with caplog.at_level(WARNING, logger="app.api.service"):
            stale = client.get("/api/cases")
        assert stale.status_code == 200
        assert stale.json() == first.json()
        assert service._results.keys() == results.keys()
        assert all(service._results[case_id] is result for case_id, result in results.items())
        assert any(record.name == "app.api.service" for record in caplog.records)
        assert marker not in caplog.text

        monotonic.return_value = 74.999
        assert client.get("/api/cases").json() == first.json()
        assert loader.call_count == 2

        monotonic.return_value = 75
        refreshed = client.get("/api/cases")
        assert refreshed.status_code == 200
        assert len(refreshed.json()["cases"]) == len(cases)
        assert refreshed.json()["lam_moi_luc"] != load_time
        assert loader.call_count == 3


def test_db_failed_first_load_returns_503_and_can_retry_immediately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.main import create_app

    monkeypatch.setenv("CASE_SOURCE", "db")
    monkeypatch.setattr("app.api.service.time", SimpleNamespace(monotonic=lambda: 0))
    query = Mock(
        side_effect=[reader.DatabaseReadError("Lỗi đọc giả lập."), prepare_cases(ROOT).rows]
    )
    monkeypatch.setattr(reader, "read_case_rows", query)
    monkeypatch.setattr(administrative, "read_administrative", lambda ids: {})

    with TestClient(create_app(make_service(tmp_path))) as client:
        assert client.get("/api/cases").status_code == 503
        recovered = client.get("/api/cases")
        assert recovered.status_code == 200
        assert recovered.json()["cases"]
        assert query.call_count == 2


def test_db_detail_returns_while_another_request_refreshes_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.main import create_app

    monkeypatch.setenv("CASE_SOURCE", "db")
    monkeypatch.setenv("CASE_CACHE_TTL_SECONDS", "10")
    monotonic = Mock(return_value=0)
    monkeypatch.setattr("app.api.service.time", SimpleNamespace(monotonic=monotonic))
    rows = prepare_cases(ROOT).rows
    started = Event()
    release = Event()

    def refresh_rows() -> reader.Rows:
        started.set()
        assert release.wait(timeout=10)
        return rows

    query = Mock(return_value=rows)
    monkeypatch.setattr(reader, "read_case_rows", query)
    monkeypatch.setattr(administrative, "read_administrative", lambda ids: {})
    monkeypatch.setattr(
        medical_record,
        "read_medical_record",
        lambda pid, cid: medical_record.build_medical_record(rows, pid, cid),
    )

    with TestClient(create_app(make_service(tmp_path))) as client, ThreadPoolExecutor(2) as workers:
        assert client.get("/api/cases").status_code == 200
        query.side_effect = refresh_rows
        monotonic.return_value = 10
        refreshing = workers.submit(client.get, "/api/cases")
        try:
            assert started.wait(timeout=5)
            detail = workers.submit(client.get, "/api/cases/HS-022").result(timeout=5)
            assert detail.status_code == 200
            assert detail.json()["ca_id"] == "HS-022"
            assert not refreshing.done()
        finally:
            release.set()
        assert refreshing.result(timeout=5).status_code == 200
        assert query.call_count == 2


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
        assert "lam_moi_luc" not in body
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
        assert datetime.fromisoformat(response.json()["lam_moi_luc"]).utcoffset() == timedelta(
            hours=7
        )
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


@pytest.mark.parametrize(
    ("value", "expected"), [(None, 60), ("abc", 60), (" 45 ", 45), ("1", 10), ("900", 600)]
)
def test_case_cache_ttl_default_and_bounds(
    monkeypatch: pytest.MonkeyPatch, value: str | None, expected: int
) -> None:
    if value is None:
        monkeypatch.delenv("CASE_CACHE_TTL_SECONDS", raising=False)
    else:
        monkeypatch.setenv("CASE_CACHE_TTL_SECONDS", value)
    assert load_case_cache_ttl() == expected
