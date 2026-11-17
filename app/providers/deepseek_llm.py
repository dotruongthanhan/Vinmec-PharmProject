"""Máy khách gọi API DeepSeek trả về đối tượng JSON theo lược đồ."""

import json
import time
from collections.abc import Callable

import httpx

from app.core.errors import ProviderError
from app.core.types import ChatMessage
from app.providers.http import post_json

_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


class DeepSeekLLM:
    """Cài đặt giao diện LLMClient cho API tương thích OpenAI của DeepSeek."""

    def __init__(
        self,
        model: str,
        api_key: str,
        client: httpx.Client,
        max_tokens: int,
        max_tokens_retry: int,
        temperature: float = 0.0,
        top_p: float = 1.0,
        max_attempts: int = 3,
        sleep: Callable[[float], None] = time.sleep,
        reasoning: dict[str, str] | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("api_key không được rỗng")
        if max_attempts <= 0:
            raise ValueError("max_attempts phải > 0")
        self.model = model
        self.api_key = api_key
        self.client = client
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_tokens_retry = max_tokens_retry
        self.reasoning = dict(reasoning) if reasoning is not None else None
        self.top_p = top_p
        self.max_attempts = max_attempts
        self.sleep = sleep
        self.last_usage: dict | None = None

    def complete_json(self, messages: list[ChatMessage], schema: dict) -> dict:
        """Nối lược đồ vào tin nhắn hệ thống, gọi DeepSeek và đọc JSON đối tượng."""
        self.last_usage = None
        schema_block = (
            "Chỉ trả về một đối tượng JSON đúng lược đồ sau.\n"
            f"{json.dumps(schema, ensure_ascii=False)}"
        )
        payload_messages: list[dict[str, str]] = []
        appended = False
        for msg in messages:
            if msg.role == "system" and not appended:
                sep = "\n\n" if msg.content else ""
                payload_messages.append(
                    {"role": msg.role, "content": f"{msg.content}{sep}{schema_block}"}
                )
                appended = True
            else:
                payload_messages.append({"role": msg.role, "content": msg.content})
        if not appended:
            payload_messages.insert(0, {"role": "system", "content": schema_block})

        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "response_format": {"type": "json_object"},
            "messages": payload_messages,
        }
        if self.reasoning is not None:
            payload.update(self.reasoning)
        try:
            return self._request_json(payload)
        except ProviderError as exc:
            if str(exc) != "het_han_muc_token":
                raise
        payload["max_tokens"] = self.max_tokens_retry
        return self._request_json(payload)

    def _request_json(self, payload: dict) -> dict:
        """Gọi API, lưu số đo và phân biệt phản hồi bị cắt với JSON sai."""
        data = post_json(
            self.client,
            _DEEPSEEK_URL,
            payload,
            [self.api_key],
            self.max_attempts,
            sleep=self.sleep,
        )

        usage = data.get("usage")
        self.last_usage = usage if isinstance(usage, dict) else None

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError("dau_ra_khong_hop_le", retryable=False)
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ProviderError("dau_ra_khong_hop_le", retryable=False)
        if choice.get("finish_reason") == "length":
            raise ProviderError("het_han_muc_token", retryable=False)

        message = choice.get("message")
        if not isinstance(message, dict):
            raise ProviderError("dau_ra_khong_hop_le", retryable=False)
        content = message.get("content")
        if not isinstance(content, str):
            raise ProviderError("dau_ra_khong_hop_le", retryable=False)

        try:
            parsed = json.loads(content.strip())
        except ValueError:
            raise ProviderError("dau_ra_khong_hop_le", retryable=False) from None
        if not isinstance(parsed, dict):
            raise ProviderError("dau_ra_khong_hop_le", retryable=False)
        return parsed
