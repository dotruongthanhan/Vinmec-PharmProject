"""Gọi HTTP, xoay khoá và chuyển lỗi nhà cung cấp."""

import json
import re
from collections.abc import Callable
from time import sleep as default_sleep

import httpx

from app.core.errors import ProviderError


def create_client() -> httpx.Client:
    """Tạo máy khách dùng chung tại ranh giới hạ tầng."""
    return httpx.Client()


def _error_message(response: httpx.Response, keys: list[str]) -> str:
    """Loại bí mật trước khi giới hạn độ dài thân lỗi."""
    body = response.text
    for key in sorted(keys, key=len, reverse=True):
        body = body.replace(key, "[ẩn]")
    body = re.sub(r"authorization[^\r\n]*", "[ẩn]", body, flags=re.IGNORECASE)
    return f"HTTP {response.status_code}: {body[:200]}"


def post_json(
    client: httpx.Client,
    url: str,
    payload: dict,
    keys: list[str],
    max_attempts: int,
    timeout: float = 60,
    *,
    sleep: Callable[[float], None] = default_sleep,
) -> dict:
    """Thử lại lỗi tạm thời với khoá kế tiếp và chờ lũy tiến."""
    if not keys or any(not key.strip() for key in keys):
        raise ValueError("Cần ít nhất một khoá không rỗng")
    if max_attempts <= 0:
        raise ValueError("max_attempts phải > 0")
    message = "Lỗi kết nối nhà cung cấp"
    for attempt in range(max_attempts):
        try:
            response = client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {keys[attempt % len(keys)]}"},
                timeout=timeout,
            )
        except httpx.RequestError:
            message = "Lỗi kết nối nhà cung cấp"
        else:
            if response.is_success:
                try:
                    result = json.loads(response.text.strip())
                except ValueError:
                    raise ProviderError(
                        f"HTTP {response.status_code}: JSON không hợp lệ", retryable=False
                    ) from None
                if not isinstance(result, dict):
                    raise ProviderError("Phản hồi JSON phải là ánh xạ", retryable=False)
                return result
            message = _error_message(response, keys)
            if response.status_code != 429 and not 500 <= response.status_code < 600:
                raise ProviderError(message, retryable=False)
        if attempt + 1 < max_attempts:
            sleep(0.5 * 2**attempt)
    raise ProviderError(message, retryable=True)
