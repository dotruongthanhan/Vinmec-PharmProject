"""Giới hạn nhịp và thử lại các yêu cầu từ điển."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.kb.fetch.client import FetchError

USER_AGENT = "VinmecPharmProject-kb/1.0"


class SourceHTTP:
    def __init__(
        self,
        http: httpx.Client,
        interval: float,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.http = http
        self.interval = interval
        self.sleep = sleep
        self.clock = clock
        self.last_request: float | None = None

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Tối đa năm lần thử lại cho 429 và 5xx."""
        headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
        for attempt in range(6):
            if self.last_request is not None:
                delay = self.interval - (self.clock() - self.last_request)
                if delay > 0:
                    self.sleep(delay)
            self.last_request = self.clock()
            try:
                response = self.http.request(method, url, headers=headers, **kwargs)
            except httpx.RequestError as exc:
                raise FetchError(f"Kết nối {httpx.URL(url).host}: {type(exc).__name__}") from exc
            status = response.status_code
            if status != 429 and not 500 <= status <= 599:
                return response
            if attempt == 5:
                raise FetchError(f"{httpx.URL(url).host} trả HTTP {status} sau 5 lần thử lại")
            retry_after = response.headers.get("Retry-After", "0")
            try:
                wait = float(retry_after)
            except ValueError:
                try:
                    wait = (parsedate_to_datetime(retry_after) - datetime.now(UTC)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    wait = 0
            self.sleep(max(2.0**attempt, wait))
        raise AssertionError("Vượt số lần thử lại")
