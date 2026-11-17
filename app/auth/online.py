"""Kiểm thu hồi trực tuyến, chỉ giữ băm token trong bộ đệm."""

from collections.abc import Callable
from hashlib import sha256
from threading import RLock
from time import monotonic

import httpx

from app.auth.errors import AuthError
from app.config.settings import AuthSettings


class OnlineChecker:
    """Đệm kết quả thành công trong 60 giây và mặc định từ chối lỗi."""

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
        self._cache: dict[str, float] = {}
        self._lock = RLock()

    def check(self, token: str) -> None:
        """Chỉ chấp nhận phản hồi thành công từ Supabase."""
        try:
            if not self._settings.supabase_url or not self._settings.supabase_anon_key:
                raise AuthError("xac_thuc_khong_san_sang")
            digest = sha256(token.encode()).hexdigest()
            with self._lock:
                now = self._clock()
                self._cache = {key: expiry for key, expiry in self._cache.items() if expiry > now}
                if digest in self._cache:
                    return
                with httpx.Client(transport=self._transport, timeout=3.0) as client:
                    response = client.get(
                        f"{self._settings.supabase_url}/auth/v1/user",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "apikey": self._settings.supabase_anon_key,
                        },
                    )
                if response.status_code == 401:
                    raise AuthError()
                if response.status_code != 200:
                    raise AuthError("xac_thuc_khong_san_sang")
                self._cache[digest] = self._clock() + 60
        except AuthError:
            raise
        except Exception:
            raise AuthError("xac_thuc_khong_san_sang") from None
