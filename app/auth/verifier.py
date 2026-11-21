"""Kiểm chữ ký JWT cục bộ bằng thuật toán và nguồn khoá cố định."""

from collections.abc import Callable
from threading import RLock
from time import monotonic
from typing import Any, Protocol

import httpx
import jwt

from app.auth.errors import AuthError
from app.auth.online import OnlineChecker
from app.auth.principal import Principal
from app.auth.roles import VALID_ROLES
from app.config.settings import AuthSettings


class Authenticator(Protocol):
    """Giao diện cho phép tiêm bộ kiểm không dùng mạng trong test."""

    def verify(self, token: str) -> Principal: ...

    def online_check(self, token: str) -> str: ...


class JwtVerifier:
    """Giữ JWKS trong bộ nhớ, giới hạn làm mới khi gặp kid lạ."""

    def __init__(
        self,
        settings: AuthSettings,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._clock = clock
        self._keys: dict[str, jwt.PyJWK] | None = None
        self._last_refresh = float("-inf")
        self._last_failure = float("-inf")
        self._lock = RLock()
        self._online = OnlineChecker(settings, transport=transport, clock=clock)

    def _fetch_keys(self) -> None:
        """Chỉ nhận khoá công khai với loại và thuật toán đã định sẵn."""
        try:
            if self._clock() - self._last_failure < 30:
                raise AuthError("xac_thuc_khong_san_sang")
            with httpx.Client(transport=self._transport, timeout=3.0) as client:
                response = client.get(
                    f"{self._settings.supabase_url}/auth/v1/.well-known/jwks.json"
                )
                response.raise_for_status()
                entries = response.json()["keys"]
            keys: dict[str, jwt.PyJWK] = {}
            for entry in entries:
                algorithm = {
                    ("RSA", None): "RS256",
                    ("EC", "P-256"): "ES256",
                    ("OKP", "Ed25519"): "EdDSA",
                }.get((entry.get("kty"), entry.get("crv")))
                if (
                    algorithm is None
                    or entry.get("use", "sig") != "sig"
                    or entry.get("alg", algorithm) != algorithm
                    or "d" in entry
                    or "verify" not in entry.get("key_ops", ["verify"])
                ):
                    continue
                kid = entry.get("kid")
                if isinstance(kid, str) and kid:
                    keys[kid] = jwt.PyJWK.from_dict(entry, algorithm=algorithm)
            self._keys = keys
        except Exception:
            self._last_failure = self._clock()
            raise AuthError("xac_thuc_khong_san_sang") from None

    def _public_key(self, kid: str) -> jwt.PyJWK:
        """Làm mới tối đa một lần mỗi 30 giây khi không thấy kid."""
        with self._lock:
            if self._keys is None:
                self._fetch_keys()
            assert self._keys is not None
            if kid not in self._keys and self._clock() - self._last_refresh >= 30:
                self._last_refresh = self._clock()
                self._fetch_keys()
            key = self._keys.get(kid)
            if key is None:
                raise AuthError()
            return key

    def _decode(self, token: str) -> dict[str, Any]:
        """Ràng buộc riêng khoá đối xứng và bất đối xứng để tránh nhầm thuật toán."""
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")
        if algorithm == "HS256" and self._settings.supabase_jwt_secret:
            key: Any = self._settings.supabase_jwt_secret
            algorithms = ["HS256"]
        elif algorithm in ("ES256", "RS256", "EdDSA"):
            kid = header.get("kid")
            if not isinstance(kid, str) or not kid:
                raise AuthError()
            public_key = self._public_key(kid)
            key = public_key.key
            algorithms = [public_key.algorithm_name]
        else:
            raise AuthError()
        return jwt.decode(
            token,
            key,
            algorithms=algorithms,
            issuer=f"{self._settings.supabase_url}/auth/v1",
            audience="authenticated",
            leeway=30,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )

    def verify(self, token: str) -> Principal:
        """Không đưa token hoặc ngoại lệ gốc ra lỗi và nhật ký."""
        try:
            if not self._settings.supabase_url:
                raise AuthError("xac_thuc_khong_san_sang")
            claims = self._decode(token)
            if not isinstance(claims["sub"], str) or not claims["sub"].strip():
                raise AuthError()
            metadata = claims.get("app_metadata")
            role = metadata.get("role") if isinstance(metadata, dict) else None
            if claims.get("is_anonymous") is True or not isinstance(role, str):
                raise AuthError("khong_co_quyen")
            if role not in VALID_ROLES:
                raise AuthError("khong_co_quyen")
            return Principal(
                nguoi_dung_id=claims["sub"],
                email=claims.get("email"),
                vai_tro=role,
                phien_id=claims.get("session_id"),
                het_han_luc=float(claims["exp"]),
            )
        except jwt.ExpiredSignatureError:
            raise AuthError("phien_het_han") from None
        except AuthError:
            raise
        except Exception:
            raise AuthError() from None

    def online_check(self, token: str) -> str:
        """Trả vai trò sống đã kiểm tra từ Supabase."""
        return self._online.check(token)
