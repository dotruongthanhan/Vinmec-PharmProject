"""Kiểm phiên và vai trò sống với Supabase giả."""

import json
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from time import time
from typing import Annotated, Any

import httpx
import pytest
from fastapi import Depends

from app.auth.dependencies import require_role
from app.auth.principal import Principal
from app.config.settings import load_auth_settings
from tests.auth.support import AuthHarness


class SessionHarness(AuthHarness):
    """Tách vai trò sống khỏi vai trò đã ký trong JWT."""

    payload: Any = {"app_metadata": {"role": "duoc_si_ls"}}
    malformed = False
    timeout = False

    def respond(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("jwks.json"):
            return super().respond(request)
        self.online_calls += 1
        if self.timeout:
            raise httpx.ReadTimeout("Lỗi giả lập " + request.headers["authorization"])
        if self.malformed:
            return httpx.Response(200, content=b"not-json")
        return httpx.Response(self.online_status, json=self.payload)


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SessionHarness:
    return SessionHarness(tmp_path, monkeypatch)


@pytest.mark.parametrize("session", [None, "simulated-session-a"])
def test_logout_blocks_replay_before_online_check(
    harness: SessionHarness, session: str | None
) -> None:
    headers = harness.headers(session_id=session)
    harness.online_status = 503
    response = harness.client.post("/api/dang-xuat", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert harness.online_calls == 0
    for path in ("/api/me", "/api/cases"):
        response = harness.client.get(path, headers=headers)
        assert response.status_code == 401
        assert response.json()["loi"]["ma"] == "chua_dang_nhap"
    assert harness.online_calls == 0


def test_logout_blocks_other_token_in_same_session(harness: SessionHarness) -> None:
    assert harness.client.post("/api/dang-xuat", headers=harness.headers()).status_code == 200
    response = harness.client.get("/api/me", headers=harness.headers(exp=int(time()) + 7200))
    assert response.status_code == 401


def test_logout_requires_token_and_valid_role(harness: SessionHarness) -> None:
    assert harness.client.post("/api/dang-xuat").status_code == 401
    response = harness.client.post("/api/dang-xuat", headers=harness.headers(app_metadata={}))
    assert response.status_code == 403


@pytest.mark.parametrize("status", [401, 403, 404])
def test_read_rejects_revoked_remote_identity(harness: SessionHarness, status: int) -> None:
    harness.online_status = status
    response = harness.client.get("/api/cases", headers=harness.headers())
    assert response.status_code == 401
    assert response.json()["loi"]["ma"] == "chua_dang_nhap"


@pytest.mark.parametrize("failure", ["503", "timeout", "malformed"])
def test_outage_allows_reads_but_rejects_writes(
    harness: SessionHarness, caplog: pytest.LogCaptureFixture, failure: str
) -> None:
    harness.online_status = 503 if failure == "503" else 200
    harness.timeout = failure == "timeout"
    harness.malformed = failure == "malformed"
    headers = harness.headers(app_metadata={"role": "admin"})
    assert harness.client.get("/api/cases", headers=headers).status_code == 200
    assert harness.client.get("/api/me", headers=headers).json()["vai_tro"] == "admin"
    assert caplog.records
    for path in (
        "/api/ask",
        "/api/cases/DEMO-02/ask",
        "/api/cases/DEMO-02/ai",
        "/api/cases/DEMO-02/feedback",
        "/api/conversations/DEMO-02/clear",
    ):
        response = harness.client.post(path, json={}, headers=headers)
        assert response.status_code == 503
        assert response.json()["loi"]["ma"] == "xac_thuc_khong_san_sang"
    token = headers["Authorization"].split()[1]
    assert token not in caplog.text
    assert token not in response.text
    assert token not in "".join(p.read_text() for p in harness.path.parent.glob("nhat_ky*.jsonl"))


def test_outage_is_remembered_briefly_to_avoid_serial_timeouts(harness: SessionHarness) -> None:
    harness.online_status = 503
    headers = harness.headers(app_metadata={"role": "admin"})
    for _ in range(3):
        assert harness.client.get("/api/cases", headers=headers).status_code == 200
    assert harness.online_calls == 1


def test_live_role_downgrades_admin_and_me(harness: SessionHarness) -> None:
    @harness.app.get("/api/test-admin")
    def admin_only(
        principal: Annotated[Principal, Depends(require_role("admin"))],
    ) -> dict[str, bool]:
        return {"ok": True}

    harness.app.router.routes.insert(0, harness.app.router.routes.pop())
    headers = harness.headers(app_metadata={"role": "admin"})
    assert harness.client.get("/api/test-admin", headers=headers).status_code == 403
    assert harness.client.get("/api/me", headers=headers).json()["vai_tro"] == "duoc_si_ls"
    harness.now += 60
    harness.payload = {"app_metadata": {"role": "admin"}}
    assert harness.client.get("/api/test-admin", headers=headers).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"app_metadata": {}},
        {"app_metadata": {"role": "unknown"}},
        {"app_metadata": {"role": []}},
    ],
)
def test_invalid_live_role_denied(harness: SessionHarness, payload: Any) -> None:
    harness.payload = payload
    response = harness.client.get("/api/me", headers=harness.headers())
    assert response.status_code == 403
    assert response.json()["loi"]["ma"] == "khong_co_quyen"


def test_cache_expires_and_keeps_only_hashes(harness: SessionHarness) -> None:
    headers = harness.headers()
    for _ in range(2):
        assert harness.client.get("/api/me", headers=headers).status_code == 200
    assert harness.online_calls == 1
    harness.now += 59
    assert harness.client.get("/api/me", headers=headers).status_code == 200
    assert harness.online_calls == 1
    harness.now += 1
    assert harness.client.get("/api/me", headers=headers).status_code == 200
    assert harness.online_calls == 2
    token = headers["Authorization"].split()[1]
    assert list(harness.verifier._online._cache) == [sha256(token.encode()).hexdigest()]
    assert token not in json.dumps(harness.verifier._online._cache)


@pytest.mark.parametrize("value, expected", [(None, 60), ("1", 10), ("1000", 300), ("120", 120)])
def test_ttl_clamped(monkeypatch: pytest.MonkeyPatch, value: str | None, expected: int) -> None:
    if value is None:
        monkeypatch.delenv("AUTH_ONLINE_TTL", raising=False)
    else:
        monkeypatch.setenv("AUTH_ONLINE_TTL", value)
    assert load_auth_settings().auth_online_ttl == expected


def test_health_and_off_bypass_checks(harness: SessionHarness) -> None:
    assert harness.client.get("/api/health").status_code == 200
    assert harness.online_calls == 0
    headers = harness.headers()
    assert harness.client.post("/api/dang-xuat", headers=headers).status_code == 200
    harness.app.state.auth_settings = harness.app.state.auth_settings.model_copy(
        update={"auth_mode": "off"}
    )
    for caller_headers in (headers, {}):
        assert harness.client.get("/api/cases", headers=caller_headers).status_code == 200
        assert harness.client.post("/api/dang-xuat", headers=caller_headers).status_code == 200
    assert harness.online_calls == 0


def test_revocation_cleanup_capacity_and_leeway() -> None:
    from app.auth.revocation import RevocationList

    now = [100.0]
    blocked = RevocationList(clock=lambda: now[0], max_entries=2)
    blocked.revoke("first", 110.0)
    blocked.revoke("second", 120.0)
    blocked.revoke("third", 130.0)
    assert not blocked.contains("first")
    assert blocked.contains("second")
    now[0] = 149.9
    assert blocked.contains("second")
    now[0] = 150.0
    assert not blocked.contains("second")
    assert blocked.contains("third")
    now[0] = 160.0
    assert not blocked.contains("third")
    assert not blocked._entries


def test_revocation_concurrent_updates() -> None:
    from app.auth.revocation import RevocationList

    blocked = RevocationList(clock=lambda: 100.0, max_entries=100)

    def block(index: int) -> bool:
        key = str(index)
        blocked.revoke(key, 200.0)
        return blocked.contains(key)

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(block, range(100)))
    assert len(blocked._entries) == 100


def test_online_cache_capacity_and_cleanup(harness: SessionHarness) -> None:
    from app.auth.online import OnlineChecker

    online = OnlineChecker(
        load_auth_settings(), transport=harness.transport, clock=lambda: harness.now, max_entries=2
    )
    for token in ("first", "second", "third"):
        assert online.check(token) == "duoc_si_ls"
    assert len(online._cache) == 2
    assert sha256(b"first").hexdigest() not in online._cache
    harness.now += 60
    online.check("fourth")
    assert len(online._cache) == 1
