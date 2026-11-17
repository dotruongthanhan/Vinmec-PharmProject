"""Máy khách openFDA có giới hạn tốc độ và thử lại."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from app.config.settings import get_secret
from app.core.errors import ConfigError


class FetchError(Exception):
    """Lỗi tải đã loại bỏ URL và khóa bí mật."""


class MalformedResponseError(FetchError):
    """Phản hồi không có cấu trúc JSON nguồn hợp lệ."""


class FDAClient:
    """Chỉ gửi yêu cầu tới hai endpoint được phép của api.fda.gov."""

    def __init__(
        self,
        http: httpx.Client,
        api_key: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.http = http
        self.api_key = api_key
        if api_key is None:
            try:
                self.api_key = get_secret("OPENFDA_API_KEY")
            except ConfigError:
                self.api_key = None
        self.sleep = sleep
        self.clock = clock
        self.last_request: float | None = None

    def get(self, endpoint: str, query: str, limit: int, skip: int = 0) -> dict[str, Any]:
        """Thử lại tối đa bốn lần khi nhận HTTP 429 hoặc 5xx."""
        if endpoint not in {"label", "ndc"}:
            raise ValueError("Endpoint không được phép")
        params: dict[str, str | int] = {"search": query, "limit": limit, "skip": skip}
        if self.api_key:
            params["api_key"] = self.api_key
        for attempt in range(5):
            if self.last_request is not None:
                wait = 0.34 - (self.clock() - self.last_request)
                if wait > 0:
                    self.sleep(wait)
            self.last_request = self.clock()
            try:
                response = self.http.get(
                    f"https://api.fda.gov/drug/{endpoint}.json",
                    params=params,
                )
            except httpx.HTTPError as exc:
                raise FetchError(f"Lỗi kết nối openFDA ({type(exc).__name__})") from None
            status = response.status_code
            if status == 429 or 500 <= status <= 599:
                if attempt == 4:
                    raise FetchError(f"HTTP {status}: đã hết 4 lần thử lại")
                delay = float(2**attempt)
                try:
                    delay = max(delay, float(response.headers.get("Retry-After", "0")))
                except ValueError:
                    pass
                self.sleep(delay)
                continue
            if status == 404:
                try:
                    if (response.json().get("error") or {}).get("code") == "NOT_FOUND":
                        return {"results": []}
                except (ValueError, AttributeError):
                    pass
            if status != 200:
                raise MalformedResponseError(
                    f"HTTP {status}: phản hồi openFDA không phải 200 hoặc NOT_FOUND hợp lệ"
                )
            try:
                payload = response.json()
            except ValueError:
                raise MalformedResponseError("Phản hồi openFDA không phải JSON hợp lệ") from None
            if not isinstance(payload, dict):
                raise MalformedResponseError("Phản hồi openFDA phải là đối tượng JSON")
            if not isinstance(payload.get("results"), list):
                raise MalformedResponseError("Phản hồi openFDA thiếu results dạng danh sách")
            for index, entry in enumerate(payload["results"]):
                if not isinstance(entry, dict):
                    raise MalformedResponseError(
                        f"Phản hồi openFDA có results[{index}] không phải đối tượng"
                    )
            return payload
        raise FetchError("Không lấy được phản hồi openFDA")
