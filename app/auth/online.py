"""Kiểm thu hồi trực tuyến, chỉ giữ băm token trong bộ đệm."""

from collections.abc import Callable
from hashlib import sha256
from threading import RLock
from time import monotonic

import httpx

from app.auth.errors import AuthError
from app.auth.roles import VALID_ROLES
from app.config.settings import AuthSettings

_UNAVAILABLE_BACKOFF = 10.0  # giây nhớ việc Supabase lỗi, tránh chờ nối tiếp


class OnlineChecker:
    """Đệm vai trò sống theo băm token, có giới hạn kích thước."""

    def __init__(
        self,
        settings: AuthSettings,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = monotonic,
        max_entries: int = 2_000,
    ) -> None:
        if max_entries < 1:
            raise ValueError("Trần bộ đệm phải dương.")
        self._settings = settings
        self._transport = transport
        self._clock = clock
        self._cache: dict[str, tuple[float, str]] = {}
        self._max_entries = max_entries
        self._lock = RLock()
        self._unavailable_until = float("-inf")

    def _mark_unavailable(self) -> None:
        """Nhớ ngắn hạn việc Supabase không sẵn sàng."""
        with self._lock:
            self._unavailable_until = self._clock() + _UNAVAILABLE_BACKOFF

    def check(self, token: str) -> str:
        """Chỉ chấp nhận vai trò hợp lệ trong phản hồi thành công."""
        try:
            if not self._settings.supabase_url or not self._settings.supabase_anon_key:
                raise AuthError("xac_thuc_khong_san_sang")
            digest = sha256(token.encode()).hexdigest()
            with self._lock:
                now = self._clock()
                self._cache = {key: item for key, item in self._cache.items() if item[0] > now}
                if digest in self._cache:
                    return self._cache[digest][1]
                if now < self._unavailable_until:
                    # Vừa lỗi dịch vụ: không chờ thêm 3 giây cho từng yêu cầu nối tiếp.
                    raise AuthError("xac_thuc_khong_san_sang")
                with httpx.Client(transport=self._transport, timeout=3.0) as client:
                    response = client.get(
                        f"{self._settings.supabase_url}/auth/v1/user",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "apikey": self._settings.supabase_anon_key,
                        },
                    )
                if response.status_code in (401, 403, 404):
                    raise AuthError()
                if response.status_code != 200:
                    raise AuthError("xac_thuc_khong_san_sang")
                payload = response.json()
                if not isinstance(payload, dict):
                    raise AuthError("xac_thuc_khong_san_sang")
                metadata = payload.get("app_metadata")
                role = metadata.get("role") if isinstance(metadata, dict) else None
                if not isinstance(role, str) or role not in VALID_ROLES:
                    raise AuthError("khong_co_quyen")
                self._cache[digest] = (self._clock() + self._settings.auth_online_ttl, role)
                while len(self._cache) > self._max_entries:
                    del self._cache[next(iter(self._cache))]
                return role
        except AuthError as exc:
            if exc.status_code == 503:
                self._mark_unavailable()
            raise
        except Exception:
            self._mark_unavailable()
            raise AuthError("xac_thuc_khong_san_sang") from None
