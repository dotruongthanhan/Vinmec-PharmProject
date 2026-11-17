"""Nhà cung cấp giả tất định, không gọi mạng."""

import hashlib
import math
import re
from copy import deepcopy

from app.core.errors import ProviderError
from app.core.types import ChatMessage


class FakeLLM:
    """Trả lần lượt phản hồi có sẵn và lưu các lời gọi."""

    def __init__(self, responses: list[dict]) -> None:
        self._responses = deepcopy(responses)
        self._position = 0
        self.calls: list[dict] = []

    def complete_json(self, messages: list[ChatMessage], schema: dict) -> dict:
        """Lấy phản hồi kế tiếp hoặc báo hết dữ liệu giả."""
        self.calls.append(deepcopy({"messages": messages, "schema": schema}))
        if self._position >= len(self._responses):
            raise ProviderError("Đã hết phản hồi giả", retryable=False)
        response = deepcopy(self._responses[self._position])
        self._position += 1
        return response


class HashEmbedder:
    """Băm từ vào véc-tơ đếm được chuẩn hoá L2."""

    def __init__(self, dimensions: int = 64) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions phải > 0")
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Nhúng từng văn bản theo cùng cách với truy vấn."""
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """Tách từ Unicode, băm SHA-256 rồi chuẩn hoá."""
        vector = [0.0] * self.dimensions
        for word in re.findall(r"\w+", text.lower()):
            digest = hashlib.sha256(word.encode("utf-8")).digest()
            vector[int.from_bytes(digest, "big") % self.dimensions] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector


class NoopReranker:
    """Giữ thứ tự sẵn có, gán điểm giảm dần."""

    def rerank(self, query: str, passages: list[str], top_n: int) -> list[tuple[int, float]]:
        """Trả tối đa top_n vị trí đầu tiên."""
        return [(index, 1.0 / (index + 1)) for index in range(min(max(top_n, 0), len(passages)))]
