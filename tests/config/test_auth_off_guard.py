"""Kiểm thử chặn AUTH_MODE=off khi chạy trong container (T4)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.service import CaseService
from app.config.settings import assert_auth_mode_allowed
from app.core.errors import ConfigError

ROOT = Path(__file__).resolve().parents[2]


def _make_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CaseService:
    monkeypatch.setenv("CASE_SOURCE", "file")
    return CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
        ai_runner=None,
    )


@pytest.mark.parametrize("runtime", ["container", "CONTAINER", " container "])
def test_auth_mode_off_in_container_raises_config_error(
    monkeypatch: pytest.MonkeyPatch, runtime: str
) -> None:
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("CDSS_RUNTIME", runtime)

    with pytest.raises(ConfigError, match="AUTH_MODE=off bị cấm khi chạy trong container"):
        assert_auth_mode_allowed()

    with pytest.raises(ConfigError, match="AUTH_MODE=off bị cấm khi chạy trong container"):
        create_app()


def test_auth_mode_off_without_container_runtime_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.delenv("CDSS_RUNTIME", raising=False)
    service = _make_service(tmp_path, monkeypatch)

    with TestClient(create_app(service)) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["xac_thuc"] == "off"


@pytest.mark.parametrize("auth_mode", ["required", None])
def test_auth_mode_required_in_container_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, auth_mode: str | None
) -> None:
    if auth_mode is None:
        monkeypatch.delenv("AUTH_MODE", raising=False)
    else:
        monkeypatch.setenv("AUTH_MODE", auth_mode)
    monkeypatch.setenv("CDSS_RUNTIME", "container")
    service = _make_service(tmp_path, monkeypatch)

    with TestClient(create_app(service)) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["xac_thuc"] == "required"
