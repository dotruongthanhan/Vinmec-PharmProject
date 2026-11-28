"""Danh sách chặn phiên trong bộ nhớ tiến trình."""

from collections.abc import Callable
from hashlib import sha256
from threading import RLock
from time import time

from app.auth.principal import Principal


def session_key(principal: Principal, token: str) -> str:
    """Ưu tiên mã phiên, không giữ token thô."""
    if principal.phien_id:
        return "session:" + principal.phien_id
    return "token:" + sha256(token.encode()).hexdigest()


class RevocationList:
    """Chặn tới exp cộng 30 giây, dọn hết hạn và giới hạn bộ nhớ."""

    def __init__(self, *, clock: Callable[[], float] = time, max_entries: int = 10_000) -> None:
        if max_entries < 1:
            raise ValueError("Trần danh sách phải dương.")
        self._clock = clock
        self._max_entries = max_entries
        self._entries: dict[str, float] = {}
        self._lock = RLock()

    def _cleanup(self) -> None:
        """Chỉ gọi trong vùng khoá."""
        now = self._clock()
        self._entries = {key: expiry for key, expiry in self._entries.items() if expiry > now}

    def revoke(self, key: str, exp: float) -> None:
        """Không rút ngắn hạn khi cùng phiên đăng xuất nhiều token."""
        with self._lock:
            self._cleanup()
            expiry = max(self._entries.get(key, float("-inf")), exp + 30)
            if expiry <= self._clock():
                return
            self._entries[key] = expiry
            while len(self._entries) > self._max_entries:
                del self._entries[next(iter(self._entries))]

    def contains(self, key: str) -> bool:
        """Kiểm tra và tự dọn mục hết hạn."""
        with self._lock:
            self._cleanup()
            return key in self._entries
