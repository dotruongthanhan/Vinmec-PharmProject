import json

import httpx
import pytest

from app.core.errors import ProviderError
from app.providers.openrouter_rerank import OpenRouterReranker


def test_rerank_sorts_and_limits_with_leading_blank_lines() -> None:
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/rerank"
        calls.append(json.loads(request.content))
        return httpx.Response(
            200,
            text="\n\n "
            + json.dumps(
                {
                    "results": [
                        {"index": 0, "relevance_score": 0.1},
                        {"index": 2, "relevance_score": 0.9},
                        {"index": 1, "relevance_score": 0.7},
                    ]
                }
            ),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        reranker = OpenRouterReranker("modele-factice", ["cle-factice"], client, 3)
        assert reranker.rerank("requête", ["a", "b", "c"], 2) == [(2, 0.9), (1, 0.7)]
        assert reranker.rerank("requête", [], 2) == []
        assert reranker.rerank("requête", ["a"], 0) == []
    assert calls == [{"model": "modele-factice", "query": "requête", "documents": ["a", "b", "c"]}]


@pytest.mark.parametrize(
    "result",
    [
        {"results": [{"index": 4, "relevance_score": 0.5}]},
        {"results": [{"index": 0, "relevance_score": "incorrect"}]},
        {"results": [{"index": 0, "relevance_score": 0.5}] * 2},
        {},
    ],
)
def test_malformed_response_is_a_provider_error(result: dict) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=result))
    ) as client:
        with pytest.raises(ProviderError) as error:
            OpenRouterReranker("modele-factice", ["cle-factice"], client, 3).rerank("q", ["a"], 1)
    assert error.value.retryable is False
