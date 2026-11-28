"""Kiểm thử cảnh báo chuỗi kết nối DB, ưu tiên DATABASE_URL_LOADER và che bí mật."""

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.service import CaseService
from app.config import settings as settings_mod
from app.config.settings import database_url_warnings, loader_database_url
from app.core.errors import ConfigError

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("url", "expected_owner", "expected_ssl"),
    [
        (
            "postgresql://bvienx_app:mk-bi-mat@rds.example.invalid:5432/bvienx"
            "?sslmode=verify-full&sslrootcert=/srv/certs/rds-global-bundle.pem",
            False,
            False,
        ),
        (
            "postgresql://bvienx_admin:mk-bi-mat@127.0.0.1:5433/bvienx?sslmode=require",
            True,
            False,
        ),
        (
            "postgresql://postgres:mk-bi-mat@localhost:5432/bvienx",
            True,
            False,
        ),
        (
            "postgresql://bvienx_app:mk-bi-mat@[::1]:5433/bvienx",
            False,
            False,
        ),
        (
            "postgresql://bvienx_app:mk-bi-mat@rds.example.invalid:5432/bvienx?sslmode=require",
            False,
            True,
        ),
        (
            "postgresql://bvienx_admin:mk-bi-mat@rds.example.invalid:5432/bvienx",
            True,
            True,
        ),
        (
            "postgresql://bvienx_admin:mk-bi-mat@127.0.0.1:5433/bvienx?sslmode=require",
            True,
            False,
        ),
        (
            "postgresql://bvienx_app:mk-bi-mat@rds.example.invalid:5432/bvienx?sslmode=require",
            False,
            True,
        ),
    ],
)
def test_database_url_warnings_checks_owner_and_sslmode(
    url: str, expected_owner: bool, expected_ssl: bool
) -> None:
    warnings = database_url_warnings(url)
    joined = "\n".join(warnings)
    assert ("API đang dùng tài khoản chủ DB" in warnings) is expected_owner
    assert ("sslmode=verify-full" in joined) is expected_ssl
    assert "mk-bi-mat" not in joined
    assert "rds.example.invalid" not in joined
    assert url not in joined


@pytest.mark.parametrize(
    ("bad_url", "secret"),
    [
        ("", "khong-co"),
        ("   ", "khong-co"),
        ("mysql://bvienx_admin:p@ss#1!@rds.example.invalid/db", "p@ss#1!"),
        ("postgresql://bvienx_admin:p@ss:abc@rds.example.invalid:badport/db", "p@ss:abc"),
        ("khong-phai-url-co-mat-khau-bi-mat", "mat-khau-bi-mat"),
        ("postgresql://bvienx_app:secret@[::1/db", "secret"),
    ],
)
def test_database_url_warnings_handles_unparseable_and_special_passwords(
    bad_url: str, secret: str
) -> None:
    warnings = database_url_warnings(bad_url)
    assert len(warnings) == 1
    assert "không phân tích được" in warnings[0].lower()
    assert secret not in warnings[0]
    if bad_url.strip():
        assert bad_url.strip() not in warnings[0]


def test_database_url_warnings_never_leaks_encoded_special_password() -> None:
    secret_raw = "p@ss!#%:word"
    url = (
        "postgresql://bvienx_admin:p%40ss%21%23%25%3Aword"
        "@rds.example.invalid:5432/bvienx?sslmode=require"
    )
    warnings = database_url_warnings(url)
    assert len(warnings) == 2
    for item in warnings:
        assert secret_raw not in item
        assert "p%40ss" not in item
        assert "rds.example.invalid" not in item
        assert "postgresql://" not in item


def test_loader_database_url_prefers_loader_env_and_warns_once(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setattr(settings_mod, "_warned_missing_loader_url", False)

    loader_dsn = "postgresql://bvienx_loader:mk-loader-123@db.invalid:5432/bvienx"
    app_dsn = "postgresql://bvienx_app:mk-app-456@db.invalid:5432/bvienx"

    monkeypatch.setenv("DATABASE_URL_LOADER", loader_dsn)
    monkeypatch.setenv("DATABASE_URL", app_dsn)
    with caplog.at_level(logging.WARNING, logger="app.config.settings"):
        assert loader_database_url() == loader_dsn
    assert caplog.records == []

    monkeypatch.delenv("DATABASE_URL_LOADER", raising=False)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="app.config.settings"):
        assert loader_database_url() == app_dsn
        assert loader_database_url() == app_dsn
    assert len(caplog.records) == 1
    assert "DATABASE_URL_LOADER" in caplog.records[0].message
    assert "mk-app-456" not in caplog.text
    assert app_dsn not in caplog.text

    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ConfigError, match="DATABASE_URL"):
        loader_database_url()


def test_app_lifespan_logs_url_warnings_without_blocking_or_leaking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("CASE_SOURCE", "file")
    monkeypatch.setenv("KB_SOURCE", "file")
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("ACCESS_LOG", "off")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://bvienx_admin:mat-khau-lifespan@rds.example.invalid:5432/bvienx"
        "?sslmode=require",
    )
    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
        ai_runner=None,
    )
    with caplog.at_level(logging.WARNING, logger="app.api.main"):
        with TestClient(create_app(service)) as client:
            assert client.get("/api/health").status_code == 200
    assert "API đang dùng tài khoản chủ DB" in caplog.text
    assert "sslmode=verify-full" in caplog.text
    assert "mat-khau-lifespan" not in caplog.text
    assert "rds.example.invalid" not in caplog.text
