"""Máy khách gọi Gemini API hỗ trợ JSON có cấu trúc và đầu vào đa phương thức (ảnh OH)."""

from __future__ import annotations

import base64
import json
import re
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.core.errors import ProviderError

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _mask_secret(text: str, api_key: str) -> str:
    """Ẩn khoá API khỏi mọi thông điệp lỗi HTTP trước khi ghi nhật ký hoặc trả về."""
    cleaned = text.replace(api_key, "[ẩn]") if api_key else text
    cleaned = re.sub(r"x-goog-api-key[^\r\n]*", "[ẩn]", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"authorization[^\r\n]*", "[ẩn]", cleaned, flags=re.IGNORECASE)
    return cleaned[:220]


def _extract_json_text(raw_text: str) -> dict[str, Any]:
    """Tách khối JSON từ phản hồi mô hình, xử lý rào markdown nếu có."""
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        stripped = _FENCE_RE.sub("", stripped).strip()
    try:
        parsed = json.loads(stripped)
    except ValueError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end <= start:
            raise ProviderError(
                "Phản hồi Gemini không chứa đối tượng JSON hợp lệ", retryable=False
            ) from None
        try:
            parsed = json.loads(stripped[start : end + 1])
        except ValueError:
            raise ProviderError("Phản hồi Gemini có JSON bị lỗi cú pháp", retryable=False) from None
    if not isinstance(parsed, dict):
        raise ProviderError("Phản hồi JSON từ Gemini phải là một đối tượng", retryable=False)
    return parsed


class GeminiLLM:
    """Máy khách Gemini v1beta dùng cho phân loại schema, OCR bảng OH và trích xuất EMR."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        client: httpx.Client,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        timeout_seconds: float = 30.0,
        max_attempts: int = 2,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("api_key không được rỗng")
        if max_attempts < 1:
            raise ValueError("max_attempts phải >= 1")
        self.model = model
        self.api_key = api_key
        self.client = client
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.sleep = sleep
        self.last_usage: dict[str, Any] | None = None

    def complete_json(
        self,
        system_prompt: str,
        user_text: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Gọi Gemini với văn bản thuần và trả về đối tượng JSON."""
        parts: list[dict[str, Any]] = [{"text": user_text}]
        return self._generate_json(system_prompt=system_prompt, parts=parts, schema=schema)

    def complete_vision_json(
        self,
        system_prompt: str,
        user_text: str,
        image_bytes: bytes,
        mime_type: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Gọi Gemini đa phương thức (ảnh PNG/JPEG/WebP + chỉ dẫn) trả JSON."""
        encoded = base64.b64encode(image_bytes).decode("ascii")
        parts: list[dict[str, Any]] = [
            {"text": user_text},
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": encoded,
                }
            },
        ]
        return self._generate_json(system_prompt=system_prompt, parts=parts, schema=schema)

    def _generate_json(
        self,
        *,
        system_prompt: str,
        parts: list[dict[str, Any]],
        schema: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Thực thi POST tới Gemini `generateContent` với retry cho lỗi tạm thời."""
        self.last_usage = None
        full_system = system_prompt.strip()
        if schema is not None:
            full_system = (
                f"{full_system}\n\n"
                "Chỉ trả về đúng một đối tượng JSON theo lược đồ:\n"
                f"{json.dumps(schema, ensure_ascii=False)}"
            )

        payload: dict[str, Any] = {
            "system_instruction": {"parts": [{"text": full_system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
                "responseMimeType": "application/json",
            },
        }

        url = f"{_GEMINI_BASE_URL}/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        last_message = "Không thể kết nối Gemini API"
        for attempt in range(self.max_attempts):
            try:
                response = self.client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except httpx.RequestError:
                last_message = "Lỗi kết nối mạng tới Gemini API"
            else:
                if response.is_success:
                    return self._parse_response(response.text)
                last_message = (
                    f"HTTP {response.status_code}: {_mask_secret(response.text, self.api_key)}"
                )
                if response.status_code != 429 and not 500 <= response.status_code < 600:
                    raise ProviderError(last_message, retryable=False)

            if attempt + 1 < self.max_attempts:
                self.sleep(0.5 * (2**attempt))

        raise ProviderError(last_message, retryable=True)

    def _parse_response(self, raw_body: str) -> dict[str, Any]:
        """Giải mã JSON từ phản hồi Gemini và lưu số đo sử dụng."""
        try:
            body = json.loads(raw_body)
        except ValueError:
            raise ProviderError(
                "Gemini trả về thân phản hồi không phải JSON", retryable=False
            ) from None

        if isinstance(body, dict) and isinstance(body.get("usageMetadata"), dict):
            self.last_usage = dict(body["usageMetadata"])

        candidates = body.get("candidates") if isinstance(body, dict) else None
        if not isinstance(candidates, list) or not candidates:
            raise ProviderError("Gemini không trả về ứng viên kết quả nào", retryable=True)

        first = candidates[0]
        if not isinstance(first, dict):
            raise ProviderError("Định dạng ứng viên Gemini không hợp lệ", retryable=False)

        finish_reason = first.get("finishReason")
        if finish_reason == "MAX_TOKENS":
            raise ProviderError("het_han_muc_token", retryable=True)

        content = first.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list) or not parts:
            raise ProviderError("Phản hồi Gemini thiếu nội dung văn bản", retryable=True)

        texts = [
            part["text"]
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        if not texts:
            raise ProviderError("Phản hồi Gemini không chứa chuỗi JSON", retryable=True)
        return _extract_json_text("\n".join(texts))
