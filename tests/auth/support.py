"""Khoá và Supabase giả, không dùng tài khoản hoặc bí mật thật."""

import json
from pathlib import Path
from secrets import token_urlsafe
from time import time
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.service import CaseService
from app.auth.verifier import JwtVerifier
from app.config.settings import load_auth_settings

ROOT = Path(__file__).resolve().parents[2]
URL = "https://auth.example.invalid"


class AuthHarness:
    """Tiêm đồng hồ, HTTP và khoá giả vào ứng dụng thật."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_MODE", "required")
        monkeypatch.setenv("SUPABASE_URL", URL)
        monkeypatch.setenv("SUPABASE_ANON_KEY", token_urlsafe(32))
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        self.keys: dict[str, Any] = {
            "ES256": ec.generate_private_key(ec.SECP256R1()),
            "RS256": rsa.generate_private_key(public_exponent=65537, key_size=2048),
            "EdDSA": ed25519.Ed25519PrivateKey.generate(),
        }
        self.jwks = []
        for algorithm, key in self.keys.items():
            jwk = json.loads(
                jwt.algorithms.get_default_algorithms()[algorithm].to_jwk(key.public_key())
            )
            self.jwks.append({**jwk, "kid": algorithm, "alg": algorithm, "use": "sig"})
        self.now = 100.0
        self.jwks_calls = 0
        self.online_calls = 0
        self.jwks_status = 200
        self.online_status = 200
        self.network_error = False
        self.transport = httpx.MockTransport(self.respond)
        self.verifier = JwtVerifier(
            load_auth_settings(), transport=self.transport, clock=lambda: self.now
        )
        self.path = tmp_path / "phan_hoi.jsonl"
        self.chat_path = tmp_path / "hoi_thoai.jsonl"
        self.service = CaseService(
            ROOT / "data/mock/demo",
            ROOT / "data/kb/quy_tac_lieu_than.json",
            self.path,
            ai_runner=None,
        )
        self.app = create_app(self.service, self.verifier)
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def respond(self, request: httpx.Request) -> httpx.Response:
        """Mọi yêu cầu phải đi vào đúng Supabase giả."""
        assert str(request.url).startswith(URL + "/auth/v1/")
        assert request.extensions["timeout"]["read"] == 3.0
        if request.url.path.endswith("jwks.json"):
            self.jwks_calls += 1
            return httpx.Response(self.jwks_status, json={"keys": self.jwks})
        assert request.url.path == "/auth/v1/user"
        assert request.headers["authorization"].startswith("Bearer ")
        assert request.headers["apikey"]
        self.online_calls += 1
        if self.network_error:
            raise httpx.ConnectError("Lỗi mạng giả lập")
        claims = jwt.decode(
            request.headers["authorization"].split()[1],
            options={"verify_signature": False},
        )
        return httpx.Response(
            self.online_status,
            json={"id": claims["sub"], "app_metadata": claims.get("app_metadata")},
        )

    def claims(self, **changes: Any) -> dict[str, Any]:
        """Tạo dữ liệu token giả có đủ trường bắt buộc."""
        return {
            "sub": "simulated-user-a",
            "email": "account@example.invalid",
            "session_id": "simulated-session-a",
            "iss": URL + "/auth/v1",
            "aud": "authenticated",
            "exp": int(time()) + 3600,
            "app_metadata": {"role": "duoc_si_ls"},
            **changes,
        }

    def token(self, algorithm: str = "ES256", **changes: Any) -> str:
        """Ký bằng khoá thử chỉ tồn tại trong bộ nhớ."""
        return jwt.encode(
            self.claims(**changes),
            self.keys[algorithm],
            algorithm=algorithm,
            headers={"kid": algorithm},
        )

    def headers(self, **changes: Any) -> dict[str, str]:
        return {"Authorization": "Bearer " + self.token(**changes)}

    def feedback_body(self) -> dict[str, str]:
        detail = self.service.get_case("DEMO-02").model_dump()
        return {
            "nhan_dinh_id": detail["nhan_dinh"]["can_chu_y"][0]["nhan_dinh_id"],
            "phan_hoi": "dong_y",
        }
