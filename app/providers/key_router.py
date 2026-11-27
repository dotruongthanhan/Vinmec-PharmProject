# CHỈ DÙNG CHO DEV: xoay nhiều khoá miễn phí. Triển khai thật: xoá module này, dùng một khoá trả phí (khoa_env một phần tử).  # noqa: E501
"""Điều phối các khoá theo vòng tròn và thời gian nghỉ."""

import math
import threading
import time
from collections.abc import Callable

from app.core.errors import ProviderError


class KeyRouter:
    """Chọn khoá còn dùng được, không hiển thị giá trị khoá."""

    def __init__(
        self,
        keys: list[str],
        monotonic: Callable[[], float] = time.monotonic,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not keys or len(keys) > 8 or any(not key.strip() for key in keys):
            raise ValueError("Cần từ 1 đến 8 khoá không rỗng")
        self._keys = tuple(keys)
        self._clock = monotonic
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next = 0
        self._until = [0.0] * len(keys)
        self._failures = [0] * len(keys)
        self._disabled = [False] * len(keys)

    def __repr__(self) -> str:
        return f"KeyRouter(so_khoa={len(self._keys)})"

    def __len__(self) -> int:
        return len(self._keys)

    def chon(self, *, cho_toi_da_giay: float = 0, han_chot: float | None = None) -> tuple[int, str]:
        """Chon khoa, co the cho trong gioi han."""
        if not math.isfinite(cho_toi_da_giay) or cho_toi_da_giay < 0:
            raise ValueError("Thoi gian cho khong hop le")
        started = self._clock()
        while True:
            with self._lock:
                now = self._clock()
                for offset in range(len(self._keys)):
                    index = (self._next + offset) % len(self._keys)
                    if not self._disabled[index] and self._until[index] <= now:
                        self._next = (index + 1) % len(self._keys)
                        return index + 1, self._keys[index]
                waits = [
                    until - now
                    for until, disabled in zip(self._until, self._disabled, strict=True)
                    if not disabled
                ]
                if not waits:
                    raise ProviderError("tất cả khoá đã bị vô hiệu", retryable=True)
                delay = max(0.0, min(waits))
                if (
                    cho_toi_da_giay == 0
                    or now - started + delay > cho_toi_da_giay
                    or (han_chot is not None and now + delay >= han_chot)
                ):
                    raise ProviderError(
                        f"tất cả khoá đang nghỉ, sớm nhất sau {math.ceil(delay)} giây",
                        retryable=True,
                    )
            self._sleep(delay)

    def bao_ket_qua(
        self, so_thu_tu: int, ma_http: int, retry_after_giay: float | None = None
    ) -> None:
        """Cập nhật trạng thái của khoá theo mã phản hồi."""
        with self._lock:
            index = so_thu_tu - 1
            if not 0 <= index < len(self._keys):
                raise ValueError("Số thứ tự khoá không hợp lệ")
            if ma_http == 200:
                self._until[index] = 0
                self._failures[index] = 0
            elif ma_http == 429:
                self._failures[index] += 1
                delay = (
                    900.0
                    if self._failures[index] >= 3
                    else (
                        max(0.0, retry_after_giay)
                        if retry_after_giay is not None and math.isfinite(retry_after_giay)
                        else 60.0
                    )
                )
                self._until[index] = self._clock() + delay
            elif ma_http in (401, 403):
                self._disabled[index] = True
