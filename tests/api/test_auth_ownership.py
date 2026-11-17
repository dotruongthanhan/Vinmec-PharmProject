"""Đủ tám tình huống quyền và sở hữu theo mục 7.3."""

import json
from pathlib import Path
from typing import Annotated, Any

import pytest
from fastapi import Depends

from app.auth.dependencies import require_role
from app.auth.principal import Principal
from app.feedback import load_feedback
from tests.auth.support import AuthHarness


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AuthHarness:
    return AuthHarness(tmp_path, monkeypatch)


def ask(harness: AuthHarness, user: str = "simulated-user-a", scope: str = "DEMO-02") -> None:
    path = "/api/ask" if scope == "__global__" else f"/api/cases/{scope}/ask"
    response = harness.client.post(
        path, json={"cau_hoi": "Câu hỏi giả lập"}, headers=harness.headers(sub=user)
    )
    assert response.status_code == 200


def legacy_line(harness: AuthHarness) -> None:
    item = {
        "ca_id": "DEMO-02",
        "cau_hoi": "Câu hỏi cũ",
        "tra_loi": {"noi_dung": "Cũ"},
        "thoi_diem": "2026-01-01",
    }
    with harness.chat_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item) + "\n")


@pytest.mark.parametrize("scope", ["DEMO-02", "__global__"])
def test_ownership_01_chat_records_user_and_session(harness: AuthHarness, scope: str) -> None:
    ask(harness, scope=scope)
    item = json.loads(harness.chat_path.read_text(encoding="utf-8"))
    assert item["nguoi_dung_id"] == "simulated-user-a"
    assert item["phien_id"] == "simulated-session-a"
    assert item["ca_id"] == scope


def test_ownership_02_other_user_cannot_read(harness: AuthHarness) -> None:
    ask(harness)
    assert (
        harness.client.get(
            "/api/conversations", headers=harness.headers(sub="simulated-user-b")
        ).json()
        == {}
    )
    own = harness.client.get("/api/conversations", headers=harness.headers()).json()
    assert set(own) == {"DEMO-02"}
    assert set(own["DEMO-02"][0]) == {"cau_hoi", "tra_loi", "thoi_diem"}


def test_ownership_03_other_user_cannot_clear(harness: AuthHarness) -> None:
    ask(harness)
    before = harness.chat_path.read_text(encoding="utf-8")
    response = harness.client.post(
        "/api/conversations/DEMO-02/clear", headers=harness.headers(sub="simulated-user-b")
    )
    assert response.json() == {"ok": True}
    assert harness.chat_path.read_text(encoding="utf-8") == before
    harness.client.post("/api/conversations/DEMO-02/clear", headers=harness.headers())
    assert harness.chat_path.read_text() == ""


def test_ownership_04_admin_own_and_legacy_only(harness: AuthHarness) -> None:
    ask(harness)
    ask(harness, user="simulated-admin")
    legacy_line(harness)
    headers = harness.headers(sub="simulated-admin", app_metadata={"role": "admin"})
    items = harness.client.get("/api/conversations", headers=headers).json()["DEMO-02"]
    assert len(items) == 2
    assert items[-1]["cau_hoi"] == "Câu hỏi cũ"
    harness.client.post("/api/conversations/DEMO-02/clear", headers=headers)
    remaining = [
        json.loads(line) for line in harness.chat_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(remaining) == 1
    assert remaining[0]["nguoi_dung_id"] == "simulated-user-a"


def test_ownership_05_pharmacist_cannot_see_or_clear_legacy(harness: AuthHarness) -> None:
    legacy_line(harness)
    assert harness.client.get("/api/conversations", headers=harness.headers()).json() == {}
    before = harness.chat_path.read_text(encoding="utf-8")
    harness.client.post("/api/conversations/DEMO-02/clear", headers=harness.headers())
    assert harness.chat_path.read_text(encoding="utf-8") == before


def test_ownership_06_feedback_records_user_and_session(harness: AuthHarness) -> None:
    response = harness.client.post(
        "/api/cases/DEMO-02/feedback", json=harness.feedback_body(), headers=harness.headers()
    )
    assert response.status_code == 200
    item = load_feedback(harness.path)[0]
    assert item.nguoi_dung_id == "simulated-user-a"
    assert item.phien_id == "simulated-session-a"
    assert harness.online_calls == 1


def test_ownership_07_legacy_feedback_and_chat_readable(harness: AuthHarness) -> None:
    legacy_line(harness)
    item: dict[str, Any] = {
        "thoi_diem": "2026-01-01T00:00:00Z",
        "ca_id": "DEMO-02",
        "ma_luat": "test",
        "yeu_to": 6,
        "chi_tiet_y_lenh_id": [],
        "phan_hoi": "dong_y",
    }
    harness.path.write_text(json.dumps(item) + "\n", encoding="utf-8")
    loaded = load_feedback(harness.path)
    assert loaded[0].nguoi_dung_id is None and loaded[0].phien_id is None
    headers = harness.headers(app_metadata={"role": "admin"})
    assert len(harness.client.get("/api/conversations", headers=headers).json()["DEMO-02"]) == 1


def test_ownership_08_admin_only_test_route(harness: AuthHarness) -> None:
    @harness.app.get("/api/test-admin")
    def admin_only(
        principal: Annotated[Principal, Depends(require_role("admin"))],
    ) -> dict[str, bool]:
        return {"ok": True}

    harness.app.router.routes.insert(0, harness.app.router.routes.pop())

    denied = harness.client.get("/api/test-admin", headers=harness.headers())
    assert denied.status_code == 403
    assert denied.json()["loi"]["ma"] == "khong_co_quyen"
    assert (
        harness.client.get(
            "/api/test-admin", headers=harness.headers(app_metadata={"role": "admin"})
        ).status_code
        == 200
    )
