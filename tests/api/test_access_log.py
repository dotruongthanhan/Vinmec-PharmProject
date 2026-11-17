"""Kiểm tra nhật ký truy cập tối giản với xác thực giả và thư mục tạm."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.auth.dependencies import require_role
from app.auth.principal import Principal
from tests.auth.support import AuthHarness

FIELDS = {
    "thoi_diem",
    "nguoi_dung_id",
    "phien_id",
    "vai_tro",
    "phuong_thuc",
    "duong_dan",
    "ma_trang_thai",
    "ma_loi",
    "thoi_gian_ms",
}
NOW = datetime(2026, 11, 18, 23, 59, tzinfo=UTC)


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AuthHarness:
    """Mặc định bật nhật ký, mọi HTTP xác thực đều được giả lập."""
    monkeypatch.delenv("ACCESS_LOG", raising=False)
    return AuthHarness(tmp_path, monkeypatch)


def read_entries(directory: Path) -> list[dict[str, Any]]:
    """Chỉ đọc nhật ký truy cập trong thư mục thử."""
    return [
        json.loads(line)
        for path in sorted(directory.glob("nhat_ky_truy_cap-*.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def test_success_has_exact_fields_and_identity(harness: AuthHarness, tmp_path: Path) -> None:
    assert harness.client.get("/api/cases", headers=harness.headers()).status_code == 200
    entries = read_entries(tmp_path)
    assert len(entries) == 1
    entry = entries[0]
    assert set(entry) == FIELDS
    assert entry["nguoi_dung_id"] == "simulated-user-a"
    assert entry["phien_id"] == "simulated-session-a"
    assert entry["vai_tro"] == "duoc_si_ls"
    assert entry["phuong_thuc"] == "GET"
    assert entry["duong_dan"] == "/api/cases"
    assert entry["ma_trang_thai"] == 200
    assert entry["ma_loi"] is None
    assert type(entry["thoi_gian_ms"]) is int
    assert entry["thoi_gian_ms"] >= 0
    assert datetime.fromisoformat(entry["thoi_diem"]).utcoffset() == timedelta(0)


@pytest.mark.parametrize("invalid_token", [False, True])
def test_unauthenticated_has_no_identity(
    harness: AuthHarness, tmp_path: Path, invalid_token: bool
) -> None:
    headers = harness.headers(exp=1) if invalid_token else {}
    response = harness.client.get("/api/cases", headers=headers)
    assert response.status_code == 401
    entry = read_entries(tmp_path)[0]
    assert entry["ma_loi"] == response.json()["loi"]["ma"]
    if not invalid_token:
        assert entry["ma_loi"] == "chua_dang_nhap"
    assert entry["ma_trang_thai"] == 401
    assert all(entry[key] is None for key in ("nguoi_dung_id", "phien_id", "vai_tro"))


def test_wrong_role_preserves_authenticated_identity(harness: AuthHarness, tmp_path: Path) -> None:
    @harness.app.get("/api/test-admin")
    def admin_only(
        principal: Annotated[Principal, Depends(require_role("admin"))],
    ) -> dict[str, bool]:
        return {"ok": True}

    harness.app.router.routes.insert(0, harness.app.router.routes.pop())
    response = harness.client.get("/api/test-admin", headers=harness.headers())
    assert response.status_code == 403
    entry = read_entries(tmp_path)[0]
    assert entry["nguoi_dung_id"] == "simulated-user-a"
    assert entry["phien_id"] == "simulated-session-a"
    assert entry["vai_tro"] == "duoc_si_ls"
    assert entry["ma_loi"] == "khong_co_quyen"


@pytest.mark.parametrize("online_status", [401, 503])
def test_online_check_failure_identity(
    harness: AuthHarness, tmp_path: Path, online_status: int
) -> None:
    harness.online_status = online_status
    response = harness.client.post(
        "/api/cases/DEMO-02/feedback", json={}, headers=harness.headers()
    )
    assert response.status_code == online_status
    entry = read_entries(tmp_path)[0]
    assert entry["ma_loi"] == response.json()["loi"]["ma"]
    expected = None if online_status == 401 else "simulated-user-a"
    assert entry["nguoi_dung_id"] == expected
    if online_status == 401:
        assert entry["phien_id"] is None and entry["vai_tro"] is None


def test_secrets_query_and_bodies_are_absent(harness: AuthHarness, tmp_path: Path) -> None:
    headers = harness.headers()
    headers.update({"Cookie": "private-cookie-marker", "User-Agent": "private-agent-marker"})
    question = "cau-hoi-gia-lap-bi-mat-khong-duoc-ghi"
    response = harness.client.post("/api/ask?x=bi-mat", json={"cau_hoi": question}, headers=headers)
    assert response.status_code == 200
    entry = read_entries(tmp_path)[0]
    assert set(entry) == FIELDS
    assert entry["duong_dan"] == "/api/ask"
    raw = next(tmp_path.glob("nhat_ky_truy_cap-*.jsonl")).read_text(encoding="utf-8")
    for secret in (
        headers["Authorization"],
        headers["Authorization"].split()[1],
        "Bearer",
        "Authorization",
        "Cookie",
        "private-cookie-marker",
        "private-agent-marker",
        "?x=",
        "bi-mat",
        question,
        response.json()["noi_dung"],
    ):
        assert secret not in raw


def test_health_get_is_excluded(harness: AuthHarness, tmp_path: Path) -> None:
    assert harness.client.get("/api/health?x=bi-mat").status_code == 200
    assert read_entries(tmp_path) == []
    response = harness.client.post("/api/health")
    assert len(read_entries(tmp_path)) == 1
    assert read_entries(tmp_path)[0]["ma_trang_thai"] == response.status_code


@pytest.mark.parametrize("authenticated", [False, True])
def test_unwritable_directory_keeps_response(
    harness: AuthHarness, tmp_path: Path, authenticated: bool
) -> None:
    blocked = tmp_path / "regular-file"
    blocked.write_text("giu-nguyen", encoding="utf-8")
    app = create_app(harness.service, harness.verifier, access_log_dir=blocked)
    with TestClient(app) as client:
        headers = harness.headers() if authenticated else {}
        response = client.get("/api/cases", headers=headers)
        assert response.status_code == (200 if authenticated else 401)
    assert blocked.read_text(encoding="utf-8") == "giu-nguyen"


def test_unexpected_write_error_is_swallowed(
    harness: AuthHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("noi-dung-gia-lap-khong-duoc-log")

    monkeypatch.setattr(Path, "mkdir", fail)
    response = harness.client.get("/api/me", headers=harness.headers())
    assert response.status_code == 200


def test_startup_cleanup_uses_filename_and_keeps_boundary(
    harness: AuthHarness, tmp_path: Path
) -> None:
    old = "nhat_ky_truy_cap-2026-08-19.jsonl"
    kept = {
        "nhat_ky_truy_cap-2026-08-20.jsonl",  # Đúng 90 ngày, vẫn giữ.
        "nhat_ky_truy_cap-2026-11-18.jsonl",
        "nhat_ky_truy_cap-2026-12-01.jsonl",
        "nhat_ky_truy_cap-2026-02-30.jsonl",
        "nhat_ky_truy_cap-2026-1-1.jsonl",
        "nhat_ky_truy_cap-2020-01-01.jsonl.bak",
        "hoi_thoai.jsonl",
    }
    for name in {old} | kept:
        (tmp_path / name).write_text("giu-nguyen", encoding="utf-8")
    directory = tmp_path / "nhat_ky_truy_cap-2020-01-01.jsonl"
    directory.mkdir()
    app = create_app(harness.service, harness.verifier, access_log_clock=lambda: NOW)
    with TestClient(app):
        assert not (tmp_path / old).exists()
        assert directory.is_dir()
        for name in kept:
            assert (tmp_path / name).read_text(encoding="utf-8") == "giu-nguyen"


def test_cleanup_error_does_not_prevent_requests(
    harness: AuthHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = tmp_path / "nhat_ky_truy_cap-2020-01-01.jsonl"
    old.touch()

    def fail(*args: Any, **kwargs: Any) -> None:
        raise OSError("Lỗi xoá giả lập")

    monkeypatch.setattr(Path, "unlink", fail)
    app = create_app(harness.service, harness.verifier, access_log_clock=lambda: NOW)
    with TestClient(app) as client:
        assert client.get("/api/cases", headers=harness.headers()).status_code == 200
    assert old.exists()
    assert (tmp_path / "nhat_ky_truy_cap-2026-11-18.jsonl").exists()


def test_disabled_log_neither_writes_nor_cleans(
    harness: AuthHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ACCESS_LOG", "off")
    old = tmp_path / "nhat_ky_truy_cap-2020-01-01.jsonl"
    old.write_text("giu-nguyen", encoding="utf-8")
    app = create_app(harness.service, harness.verifier)
    with TestClient(app) as client:
        assert client.get("/api/cases", headers=harness.headers()).status_code == 200
    assert list(tmp_path.glob("nhat_ky_truy_cap-*.jsonl")) == [old]
    assert old.read_text(encoding="utf-8") == "giu-nguyen"


@pytest.mark.parametrize("setting", [None, "on"])
def test_injected_clock_uses_utc_day(
    harness: AuthHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, setting: str | None
) -> None:
    if setting is not None:
        monkeypatch.setenv("ACCESS_LOG", setting)
    local = datetime(2026, 11, 19, 6, 59, tzinfo=timezone(timedelta(hours=7)))
    moments = iter([local, local + timedelta(minutes=2)])
    folder = tmp_path / "injected-runtime"
    app = create_app(
        harness.service,
        harness.verifier,
        access_log_dir=folder,
        access_log_clock=lambda: next(moments),
    )
    client = TestClient(app)
    for _ in range(2):
        assert client.get("/api/me", headers=harness.headers()).status_code == 200
    assert {p.name for p in folder.iterdir()} == {
        "nhat_ky_truy_cap-2026-11-18.jsonl",
        "nhat_ky_truy_cap-2026-11-19.jsonl",
    }
    assert datetime.fromisoformat(read_entries(folder)[0]["thoi_diem"]) == NOW


@pytest.mark.parametrize("status", [404, 422, 500])
def test_api_error_code_is_recorded_without_body(
    harness: AuthHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    if status == 500:

        def fail() -> None:
            raise RuntimeError("noi-dung-gia-lap-bi-mat")

        monkeypatch.setattr(harness.service, "list_cases", fail)
    path = "/api/cases/khong-co" if status == 404 else "/api/cases"
    if status == 422:
        response = harness.client.post("/api/ask", json={}, headers=harness.headers())
    else:
        response = harness.client.get(path, headers=harness.headers())
    assert response.status_code == status
    entries = read_entries(tmp_path)
    assert len(entries) == 1
    assert entries[0]["ma_trang_thai"] == status
    assert entries[0]["ma_loi"] == response.json()["loi"]["ma"]
    assert entries[0]["nguoi_dung_id"] == "simulated-user-a"


def test_concurrent_requests_keep_complete_json_lines(harness: AuthHarness, tmp_path: Path) -> None:
    headers = harness.headers()

    def call(index: int) -> int:
        return harness.client.get(f"/api/me?i={index}", headers=headers).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(call, range(20))) == [200] * 20
    entries = read_entries(tmp_path)
    assert len(entries) == 20
    assert all(set(entry) == FIELDS and entry["duong_dan"] == "/api/me" for entry in entries)
