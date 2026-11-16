"""Nhúng văn bản nguồn và truy vấn mẫu qua OpenRouter."""

import math

import httpx

from app.core.errors import ProviderError
from app.providers.http import post_json


class OpenRouterEmbedder:
    """Chia lô và kiểm tra thứ tự, số lượng, số chiều véc-tơ."""

    def __init__(
        self,
        model: str,
        dimensions: int,
        batch_size: int,
        keys: list[str],
        client: httpx.Client,
        max_attempts: int,
    ) -> None:
        if dimensions <= 0 or batch_size <= 0:
            raise ValueError("dimensions và batch_size phải > 0")
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.keys = list(keys)
        self.client = client
        self.max_attempts = max_attempts

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Chỉ gửi văn bản không rỗng, khôi phục thứ tự theo index."""
        if any(not text.strip() for text in texts):
            raise ValueError("Văn bản nhúng không được rỗng")
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            response = post_json(
                self.client,
                "https://openrouter.ai/api/v1/embeddings",
                {"model": self.model, "input": batch},
                self.keys,
                self.max_attempts,
            )
            try:
                data = response["data"]
                if not isinstance(data, list) or len(data) != len(batch):
                    raise ValueError
                ordered: dict[int, list[float]] = {}
                for item in data:
                    index = item["index"]
                    vector = item["embedding"]
                    if (
                        type(index) is not int
                        or not 0 <= index < len(batch)
                        or index in ordered
                        or not isinstance(vector, list)
                        or len(vector) != self.dimensions
                        or any(
                            type(value) not in (int, float) or not math.isfinite(value)
                            for value in vector
                        )
                    ):
                        raise ValueError
                    ordered[index] = [float(value) for value in vector]
                vectors.extend(ordered[index] for index in range(len(batch)))
            except (KeyError, TypeError, ValueError, OverflowError):
                raise ProviderError(
                    "Phản hồi nhúng sai số lượng, chỉ số hoặc số chiều", retryable=False
                ) from None
        return vectors

    def embed_query(self, text: str) -> list[float]:
        """Nhúng một truy vấn do mẫu sinh ra."""
        return self.embed_documents([text])[0]
