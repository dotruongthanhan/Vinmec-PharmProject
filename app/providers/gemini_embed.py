"""Nhúng văn bản nguồn và truy vấn qua API Gemini batchEmbedContents."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from time import sleep as default_sleep
from typing import Literal

import httpx

from app.core.errors import ProviderError

MAX_GEMINI_BATCH_SIZE = 100
_DOCUMENT_TASK = "RETRIEVAL_DOCUMENT"
_QUERY_TASK = "RETRIEVAL_QUERY"
_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _error_message(response: httpx.Response, api_key: str) -> str:
    """Loại bí mật khỏi thân lỗi HTTP trước khi cắt ngắn."""
    body = response.text.replace(api_key, "[ẩn]")
    body = re.sub(r"(?:authorization|x-goog-api-key)[^\r\n]*", "[ẩn]", body, flags=re.IGNORECASE)
    return f"HTTP {response.status_code}: {body[:200]}"


def _post_gemini_json(
    client: httpx.Client,
    url: str,
    payload: dict,
    api_key: str,
    max_attempts: int,
    timeout: float = 60,
    *,
    sleep: Callable[[float], None] = default_sleep,
) -> dict:
    """Gửi yêu cầu JSON kèm header x-goog-api-key, thử lại khi gặp 429/5xx hoặc lỗi mạng."""
    message = "Lỗi kết nối nhà cung cấp"
    for attempt in range(max_attempts):
        try:
            response = client.post(
                url,
                json=payload,
                headers={"x-goog-api-key": api_key},
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
            message = _error_message(response, api_key)
            if response.status_code != 429 and not 500 <= response.status_code < 600:
                raise ProviderError(message, retryable=False)
        if attempt + 1 < max_attempts:
            sleep(0.5 * 2**attempt)
    raise ProviderError(message, retryable=True)


class GeminiEmbedder:
    """Chia lô tối đa 100 đoạn và kiểm tra số chiều, tính hữu hạn của từng véc-tơ."""

    def __init__(
        self,
        model: str,
        dimensions: int,
        batch_size: int,
        api_key: str,
        client: httpx.Client,
        max_attempts: int = 3,
        *,
        sleep: Callable[[float], None] = default_sleep,
    ) -> None:
        model_name = model.strip().removeprefix("models/")
        if not model_name:
            raise ValueError("model không được rỗng")
        if dimensions <= 0 or batch_size <= 0:
            raise ValueError("dimensions và batch_size phải > 0")
        if not api_key or not api_key.strip():
            raise ValueError("api_key không được rỗng")
        if max_attempts <= 0:
            raise ValueError("max_attempts phải > 0")
        self.model = model
        self._model_name = model_name
        self.dimensions = dimensions
        self.batch_size = min(batch_size, MAX_GEMINI_BATCH_SIZE)
        self.api_key = api_key
        self.client = client
        self.max_attempts = max_attempts
        self.sleep = sleep

    def _embed_batch(
        self,
        texts: list[str],
        task_type: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"],
    ) -> list[list[float]]:
        """Kiểm văn bản rỗng, chia lô <= 100 và kiểm tra véc-tơ trả về."""
        if any(not text.strip() for text in texts):
            raise ValueError("Văn bản nhúng không được rỗng")
        if not texts:
            return []
        url = f"{_BASE_URL}/{self._model_name}:batchEmbedContents"
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            payload = {
                "requests": [
                    {
                        "model": f"models/{self._model_name}",
                        "content": {"parts": [{"text": text}]},
                        "outputDimensionality": self.dimensions,
                        "taskType": task_type,
                    }
                    for text in batch
                ]
            }
            response = _post_gemini_json(
                self.client,
                url,
                payload,
                self.api_key,
                self.max_attempts,
                sleep=self.sleep,
            )
            try:
                embeddings = response["embeddings"]
                if not isinstance(embeddings, list) or len(embeddings) != len(batch):
                    raise ValueError
                for item in embeddings:
                    if not isinstance(item, dict):
                        raise ValueError
                    vector = item["values"]
                    if (
                        not isinstance(vector, list)
                        or len(vector) != self.dimensions
                        or any(
                            type(value) not in (int, float) or not math.isfinite(value)
                            for value in vector
                        )
                    ):
                        raise ValueError
                    vectors.append([float(value) for value in vector])
            except (KeyError, TypeError, ValueError, OverflowError):
                raise ProviderError(
                    "Phản hồi nhúng Gemini sai số lượng, cấu trúc hoặc số chiều",
                    retryable=False,
                ) from None
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Nhúng danh sách văn bản nguồn với taskType RETRIEVAL_DOCUMENT."""
        return self._embed_batch(texts, _DOCUMENT_TASK)

    def embed_query(self, text: str) -> list[float]:
        """Nhúng một truy vấn tìm kiếm với taskType RETRIEVAL_QUERY."""
        return self._embed_batch([text], _QUERY_TASK)[0]
