"""Xếp hạng lại các đoạn nguồn qua OpenRouter."""

import math

import httpx

from app.core.errors import ProviderError
from app.providers.http import post_json


class OpenRouterReranker:
    """Trả vị trí đoạn và điểm giảm dần."""

    def __init__(
        self, model: str, keys: list[str], client: httpx.Client, max_attempts: int
    ) -> None:
        self.model = model
        self.keys = list(keys)
        self.client = client
        self.max_attempts = max_attempts

    def rerank(self, query: str, passages: list[str], top_n: int) -> list[tuple[int, float]]:
        """Không gọi nhà cung cấp khi không có đoạn cần xếp hạng."""
        if not passages or top_n <= 0:
            return []
        response = post_json(
            self.client,
            "https://openrouter.ai/api/v1/rerank",
            {"model": self.model, "query": query, "documents": passages},
            self.keys,
            self.max_attempts,
        )
        try:
            results = response["results"]
            if not isinstance(results, list):
                raise ValueError
            ranked: list[tuple[int, float]] = []
            seen: set[int] = set()
            for item in results:
                index, score = item["index"], item["relevance_score"]
                if (
                    type(index) is not int
                    or not 0 <= index < len(passages)
                    or index in seen
                    or type(score) not in (int, float)
                    or not math.isfinite(score)
                ):
                    raise ValueError
                seen.add(index)
                ranked.append((index, float(score)))
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ProviderError("Phản hồi xếp hạng lại không hợp lệ", retryable=False) from None
        return sorted(ranked, key=lambda item: item[1], reverse=True)[:top_n]
