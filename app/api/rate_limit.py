"""Giới hạn tốc độ theo cửa sổ trượt và ngân sách gọi LLM theo ngày giờ Việt Nam."""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from threading import Lock

from app.config.settings import (
    DEFAULT_LLM_AI_PER_HOUR,
    DEFAULT_LLM_ASK_PER_5MIN,
    DEFAULT_LLM_DAILY_CALLS,
    load_llm_rate_limits,
)
from app.db.timezone import VN_TZ

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

DEFAULT_ASK_PER_5MIN = DEFAULT_LLM_ASK_PER_5MIN
DEFAULT_AI_PER_HOUR = DEFAULT_LLM_AI_PER_HOUR
DEFAULT_DAILY_CALLS = DEFAULT_LLM_DAILY_CALLS
ASK_WINDOW_SECONDS = 300.0
AI_WINDOW_SECONDS = 3600.0


class SlidingWindowLimiter:
    """Giới hạn lượt gọi theo cửa sổ trượt trong bộ nhớ tiến trình, an toàn luồng."""

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 10_000,
    ) -> None:
        if limit < 1:
            raise ValueError("limit phải >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds phải > 0")
        if max_keys < 1:
            raise ValueError("max_keys phải >= 1")
        self._limit = limit
        self._window = float(window_seconds)
        self._clock = clock
        self._max_keys = max_keys
        self._events: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _prune_locked(self, cutoff: float) -> None:
        """Dọn các khoá hết hạn hoặc cũ nhất khi vượt trần kích thước bộ nhớ."""
        stale = [key for key, queue in self._events.items() if not queue or queue[-1] <= cutoff]
        for key in stale:
            del self._events[key]
        while len(self._events) >= self._max_keys:
            oldest = next(iter(self._events))
            del self._events[oldest]

    def hit(self, key: str) -> float | None:
        """Ghi nhận một lượt và trả None nếu được phép; ngược lại trả số giây phải chờ."""
        with self._lock:
            now = self._clock()
            cutoff = now - self._window
            bucket = self._events.get(key)
            if bucket is not None:
                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()
                if not bucket:
                    del self._events[key]
                    bucket = None
            if bucket is not None and len(bucket) >= self._limit:
                wait = max(0.0, bucket[0] + self._window - now)
                return wait if wait > 0 else 1.0
            if bucket is None:
                if len(self._events) >= self._max_keys:
                    self._prune_locked(cutoff)
                bucket = deque()
                self._events[key] = bucket
            bucket.append(now)
            return None


class DailyBudget:
    """Đếm lượt LLM toàn hệ thống theo ngày dương lịch giờ Việt Nam (+07)."""

    def __init__(
        self,
        limit: int,
        *,
        clock: Callable[[], datetime | float] = time.time,
    ) -> None:
        if limit < 1:
            raise ValueError("limit phải >= 1")
        self._limit = limit
        self._clock = clock
        self._lock = Lock()
        self._day: date | None = None
        self._used = 0

    def _now_vn(self) -> datetime:
        """Chuyển giá trị đồng hồ về thời điểm có múi giờ Việt Nam."""
        raw = self._clock()
        if isinstance(raw, datetime):
            dt = raw if raw.tzinfo is not None else raw.replace(tzinfo=UTC)
            return dt.astimezone(VN_TZ)
        return (_EPOCH + timedelta(seconds=float(raw))).astimezone(VN_TZ)

    def take(self) -> bool:
        """Lấy 1 lượt nếu chưa chạm trần ngày; tự đặt lại khi sang ngày mới."""
        with self._lock:
            today = self._now_vn().date()
            if self._day != today:
                self._day = today
                self._used = 0
            if self._used >= self._limit:
                return False
            self._used += 1
            return True

    def seconds_until_reset(self) -> int:
        """Số giây làm tròn lên đến 00:00 ngày tiếp theo theo giờ Việt Nam."""
        with self._lock:
            now_vn = self._now_vn()
            next_day = datetime.combine(
                now_vn.date() + timedelta(days=1),
                datetime.min.time(),
                tzinfo=VN_TZ,
            )
            return max(1, math.ceil((next_day - now_vn).total_seconds()))


class LlmRateLimits:
    """Tập hợp bộ giới hạn tốc độ và trần ngày cho các điểm cuối gọi LLM."""

    def __init__(
        self,
        *,
        ask_per_5min: int = DEFAULT_ASK_PER_5MIN,
        ai_per_hour: int = DEFAULT_AI_PER_HOUR,
        daily_calls: int = DEFAULT_DAILY_CALLS,
        clock: Callable[[], float] | None = None,
        ask_limiter: SlidingWindowLimiter | None = None,
        ai_limiter: SlidingWindowLimiter | None = None,
        daily_budget: DailyBudget | None = None,
    ) -> None:
        window_clock = clock if clock is not None else time.monotonic
        budget_clock = clock if clock is not None else time.time
        self.ask_limiter = (
            ask_limiter
            if ask_limiter is not None
            else SlidingWindowLimiter(ask_per_5min, ASK_WINDOW_SECONDS, clock=window_clock)
        )
        self.ai_limiter = (
            ai_limiter
            if ai_limiter is not None
            else SlidingWindowLimiter(ai_per_hour, AI_WINDOW_SECONDS, clock=window_clock)
        )
        self.daily_budget = (
            daily_budget
            if daily_budget is not None
            else DailyBudget(daily_calls, clock=budget_clock)
        )

    @classmethod
    def from_env(cls, *, clock: Callable[[], float] | None = None) -> LlmRateLimits:
        """Đọc các biến LLM_* một lần khi dựng dịch vụ."""
        ask_per_5min, ai_per_hour, daily_calls = load_llm_rate_limits()
        return cls(
            ask_per_5min=ask_per_5min,
            ai_per_hour=ai_per_hour,
            daily_calls=daily_calls,
            clock=clock,
        )
