"""Gọi HTTP, xoay khoá và chuyển lỗi nhà cung cấp."""

import json
import re
from collections.abc import Callable
from contextvars import ContextVar
from time import sleep as default_sleep
from typing import TYPE_CHECKING

import httpx

from app.core.errors import ProviderError

if TYPE_CHECKING:
    from app.providers.key_router import KeyRouter


han_chot_llm: ContextVar[float | None] = ContextVar("han_chot_llm", default=None)


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


def post_chat_json(
    client: httpx.Client,
    url: str,
    payload: dict,
    router: "KeyRouter",
    on_attempt: Callable[[int], None],
    timeout: float = 60,
    *,
    cho_toi_da_giay: float = 0,
) -> dict:
    """Gọi chat với số lượt giới hạn và báo kết quả cho bộ chọn khoá."""
    message = "Lỗi kết nối nhà cung cấp"
    rate_limited = 0
    for attempt in range(min(len(router), 8) * 2):
        if attempt == len(router) and rate_limited != len(router):
            break
        number, key = router.chon(cho_toi_da_giay=cho_toi_da_giay, han_chot=han_chot_llm.get())
        on_attempt(number)
        try:
            response = client.post(
                url, json=payload, headers={"Authorization": f"Bearer {key}"}, timeout=timeout
            )
        except httpx.RequestError:
            continue
        code = response.status_code
        delay = None
        if code == 429:
            rate_limited += 1
            try:
                delay = float(response.headers.get("Retry-After", ""))
            except ValueError:
                pass
            try:
                body = response.json()
                details = body.get("error", {}).get("details", [])
                for detail in details:
                    value = detail.get("retryDelay") if isinstance(detail, dict) else None
                    if isinstance(value, str) and re.fullmatch(r"\d+(?:\.\d+)?s", value):
                        delay = float(value[:-1])
                        break
            except (ValueError, AttributeError, TypeError):
                pass
        router.bao_ket_qua(number, code, delay)
        if response.is_success:
            try:
                data = response.json()
            except ValueError:
                raise ProviderError(f"HTTP {code}: JSON không hợp lệ", retryable=False) from None
            if not isinstance(data, dict):
                raise ProviderError("Phản hồi JSON phải là ánh xạ", retryable=False)
            return data
        # Không đưa thân lỗi không tin cậy hoặc khoá vào thông báo.
        message = f"HTTP {code}"
        if code not in (401, 403, 429) and not 500 <= code < 600:
            raise ProviderError(message, retryable=False)
    raise ProviderError(message, retryable=True)
