"""Đủ 19 tình huống mục 7.1 và các nhánh mặc định từ chối."""

import base64
import hashlib
import hmac
import json
from hashlib import sha256
from pathlib import Path
from secrets import token_urlsafe
from time import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.auth.errors import AuthError
from app.auth.principal import Principal
from app.auth.verifier import JwtVerifier
from app.config.settings import load_auth_settings
from tests.auth.support import AuthHarness


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AuthHarness:
    return AuthHarness(tmp_path, monkeypatch)


def assert_error(response: Any, status: int, code: str = "chua_dang_nhap") -> None:
    assert response.status_code == status
    assert set(response.json()) == {"loi"}
    assert response.json()["loi"]["ma"] == code
    assert isinstance(response.json()["loi"]["thong_bao"], str)


@pytest.mark.parametrize("algorithm", ["ES256", "RS256", "EdDSA"])
def test_01_valid_pharmacist(harness: AuthHarness, algorithm: str) -> None:
    response = harness.client.get("/api/me", headers=harness.headers(algorithm=algorithm))
    assert response.status_code == 200
    assert response.json() == {
        "id": "simulated-user-a",
        "email": "account@example.invalid",
        "vai_tro": "duoc_si_ls",
        "phien_id": "simulated-session-a",
    }
    harness.client.get("/api/me", headers=harness.headers(algorithm=algorithm))
    assert harness.jwks_calls == 1
    # Từ T39 mọi điểm cuối đều kiểm trực tuyến (có đệm theo băm token).
    assert 1 <= harness.online_calls <= 2


def test_02_valid_admin(harness: AuthHarness) -> None:
    response = harness.client.get(
        "/api/me", headers=harness.headers(app_metadata={"role": "admin"})
    )
    assert response.status_code == 200
    assert response.json()["vai_tro"] == "admin"


def test_03_missing_authorization(harness: AuthHarness) -> None:
    assert_error(harness.client.get("/api/cases"), 401)


@pytest.mark.parametrize("value", ["Basic abc", "Bearer", "Bearer ", "Bearer a b"])
def test_04_malformed_authorization(harness: AuthHarness, value: str) -> None:
    assert_error(harness.client.get("/api/me", headers={"Authorization": value}), 401)


def test_05_expired(harness: AuthHarness) -> None:
    response = harness.client.get("/api/me", headers=harness.headers(exp=int(time()) - 90))
    assert_error(response, 401, "phien_het_han")


def test_06_wrong_signature(harness: AuthHarness) -> None:
    token = jwt.encode(
        harness.claims(),
        ec.generate_private_key(ec.SECP256R1()),
        algorithm="ES256",
        headers={"kid": "ES256"},
    )
    assert_error(harness.client.get("/api/me", headers={"Authorization": "Bearer " + token}), 401)


def test_07_wrong_issuer(harness: AuthHarness) -> None:
    assert_error(harness.client.get("/api/me", headers=harness.headers(iss="wrong")), 401)


def test_08_wrong_audience(harness: AuthHarness) -> None:
    assert_error(harness.client.get("/api/me", headers=harness.headers(aud="other")), 401)


def test_09_none_algorithm(harness: AuthHarness) -> None:
    token = jwt.encode(harness.claims(), key=None, algorithm="none")
    assert_error(harness.client.get("/api/me", headers={"Authorization": "Bearer " + token}), 401)


def test_10_algorithm_confusion(harness: AuthHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    public_der = (
        harness.keys["RS256"]
        .public_key()
        .public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","kid":"RS256"}').rstrip(b"=")
    payload = base64.urlsafe_b64encode(json.dumps(harness.claims()).encode()).rstrip(b"=")
    message = header + b"." + payload
    signature = base64.urlsafe_b64encode(hmac.digest(public_der, message, hashlib.sha256)).rstrip(
        b"="
    )
    token = (message + b"." + signature).decode()
    assert_error(harness.client.get("/api/me", headers={"Authorization": "Bearer " + token}), 401)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", token_urlsafe(32))
    verifier = JwtVerifier(load_auth_settings(), transport=harness.transport)
    with pytest.raises(AuthError) as error:
        verifier.verify(token)
    assert error.value.status_code == 401


def test_11_anonymous(harness: AuthHarness) -> None:
    assert_error(
        harness.client.get("/api/me", headers=harness.headers(is_anonymous=True)),
        403,
        "khong_co_quyen",
    )


def test_12_missing_role(harness: AuthHarness) -> None:
    assert_error(
        harness.client.get("/api/me", headers=harness.headers(app_metadata={})),
        403,
        "khong_co_quyen",
    )


def test_13_user_metadata_never_grants_role(harness: AuthHarness) -> None:
    headers = harness.headers(app_metadata=None, user_metadata={"role": "admin"})
    assert_error(harness.client.get("/api/me", headers=headers), 403, "khong_co_quyen")


def test_14_unknown_role(harness: AuthHarness) -> None:
    headers = harness.headers(app_metadata={"role": "superuser"})
    assert_error(harness.client.get("/api/me", headers=headers), 403, "khong_co_quyen")


def test_15_unknown_kid_refresh_throttled(harness: AuthHarness) -> None:
    assert harness.client.get("/api/me", headers=harness.headers()).status_code == 200
    for index in range(20):
        token = jwt.encode(
            harness.claims(),
            harness.keys["ES256"],
            algorithm="ES256",
            headers={"kid": f"unknown-{index}"},
        )
        assert_error(
            harness.client.get("/api/me", headers={"Authorization": "Bearer " + token}), 401
        )
    assert harness.jwks_calls == 2
    harness.now += 30
    harness.client.get("/api/me", headers={"Authorization": "Bearer " + token})
    assert harness.jwks_calls == 3


def test_16_unavailable_jwks(harness: AuthHarness) -> None:
    harness.jwks_status = 503
    for _ in range(3):
        assert_error(
            harness.client.get("/api/me", headers=harness.headers()), 503, "xac_thuc_khong_san_sang"
        )
    assert harness.jwks_calls == 1


def test_17_public_health(harness: AuthHarness) -> None:
    response = harness.client.get("/api/health")
    assert response.status_code == 200
    assert set(response.json()) == {"ok", "che_do", "xac_thuc"}
    assert response.json()["xac_thuc"] == "required"
    assert harness.jwks_calls == 0


def test_18_no_token_in_logs_or_errors(
    harness: AuthHarness, caplog: pytest.LogCaptureFixture
) -> None:
    token = harness.token(iss="incorrect-issuer")
    response = harness.client.get("/api/me", headers={"Authorization": "Bearer " + token})
    assert_error(response, 401)
    for part in [token, *token.split(".")]:
        assert part not in response.text
        assert part not in caplog.text


def test_19_online_revocation_cache_and_network_failure(harness: AuthHarness) -> None:
    body = harness.feedback_body()
    token = harness.token()
    headers = {"Authorization": "Bearer " + token}
    harness.online_status = 401
    assert_error(
        harness.client.post("/api/cases/DEMO-02/feedback", json=body, headers=headers), 401
    )
    assert not harness.path.exists()
    harness.online_status = 200
    for _ in range(2):
        assert (
            harness.client.post(
                "/api/cases/DEMO-02/feedback", json=body, headers=headers
            ).status_code
            == 200
        )
    assert harness.online_calls == 2
    cache = harness.verifier._online._cache
    assert list(cache) == [sha256(token.encode()).hexdigest()]
    assert token not in json.dumps(cache)
    saved = harness.path.read_text()
    harness.now += 60
    harness.network_error = True
    assert_error(
        harness.client.post("/api/cases/DEMO-02/feedback", json=body, headers=headers),
        503,
        "xac_thuc_khong_san_sang",
    )
    assert harness.path.read_text() == saved
    harness.network_error = False
    harness.online_status = 503
    assert_error(
        harness.client.post("/api/cases/DEMO-02/feedback", json=body, headers=headers),
        503,
        "xac_thuc_khong_san_sang",
    )
    assert harness.path.read_text() == saved


def test_default_required_without_auth_mode(
    harness: AuthHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AUTH_MODE", raising=False)
    app = create_app()
    try:
        assert app.state.auth_settings.auth_mode == "required"
        assert_error(TestClient(app).get("/api/me"), 401)
    finally:
        app.state.service.shutdown()


@pytest.mark.parametrize("mode", [None, "typo", "required"])
def test_missing_configuration_stays_closed(
    harness: AuthHarness, monkeypatch: pytest.MonkeyPatch, mode: str | None
) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    if mode is None:
        monkeypatch.delenv("AUTH_MODE", raising=False)
    else:
        monkeypatch.setenv("AUTH_MODE", mode)
    with TestClient(create_app(harness.service)) as client:
        assert client.get("/api/health").status_code == 200
        assert_error(client.get("/api/me"), 503, "xac_thuc_khong_san_sang")
        assert_error(client.get("/api/cases"), 503, "xac_thuc_khong_san_sang")


def test_exp_leeway_and_required_claims(harness: AuthHarness) -> None:
    assert (
        harness.client.get("/api/me", headers=harness.headers(exp=int(time()) - 10)).status_code
        == 200
    )
    for field in ["exp", "iss", "aud", "sub"]:
        claims = harness.claims()
        del claims[field]
        token = jwt.encode(
            claims, harness.keys["ES256"], algorithm="ES256", headers={"kid": "ES256"}
        )
        assert_error(
            harness.client.get("/api/me", headers={"Authorization": "Bearer " + token}), 401
        )
    assert_error(harness.client.get("/api/me", headers=harness.headers(sub="")), 401)


def test_hs256_requires_explicit_secret(
    harness: AuthHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = token_urlsafe(32)
    token = jwt.encode(harness.claims(), secret, algorithm="HS256")
    with pytest.raises(AuthError):
        harness.verifier.verify(token)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)
    verifier = JwtVerifier(load_auth_settings(), transport=harness.transport)
    assert verifier.verify(token).nguoi_dung_id == "simulated-user-a"
    assert harness.jwks_calls == 0


def test_principal_is_frozen_and_optional_claims(harness: AuthHarness) -> None:
    principal = harness.verifier.verify(harness.token(email=None, session_id=None))
    assert principal.email is None and principal.phien_id is None
    with pytest.raises(ValueError):
        principal.vai_tro = "admin"


def test_unexpected_verifier_and_online_errors_closed(
    harness: AuthHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = harness.headers()
    body = harness.feedback_body()

    def fail(*args: Any) -> Principal:
        raise RuntimeError(headers["Authorization"])

    monkeypatch.setattr(harness.verifier, "online_check", fail)
    assert_error(
        harness.client.post("/api/cases/DEMO-02/feedback", headers=headers, json=body),
        503,
        "xac_thuc_khong_san_sang",
    )
    monkeypatch.setattr(harness.verifier, "verify", fail)
    response = harness.client.get("/api/me", headers=headers)
    assert_error(response, 401)
    assert headers["Authorization"] not in response.text
