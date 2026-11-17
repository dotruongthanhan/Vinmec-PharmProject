import json

import httpx
import pytest

from app.core.errors import ProviderError
from app.providers.http import post_json
from app.providers.openrouter_embed import OpenRouterEmbedder


def test_batches_reverse_indices_and_leading_blank_lines() -> None:
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload)
        assert request.url.path == "/api/v1/embeddings"
        data = [
            {"index": index, "embedding": [float(text), 1.0]}
            for index, text in reversed(list(enumerate(payload["input"])))
        ]
        return httpx.Response(200, text="\n\n " + json.dumps({"data": data}))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        embedder = OpenRouterEmbedder("modele-factice", 2, 2, ["cle-factice"], client, 3)
        assert embedder.embed_documents(["0", "1", "2", "3", "4"]) == [
            [float(index), 1.0] for index in range(5)
        ]
        assert len(calls) == 3
        assert [len(call["input"]) for call in calls] == [2, 2, 1]
        assert all(call["model"] == "modele-factice" for call in calls)
        assert embedder.embed_query("5") == [5.0, 1.0]
        assert calls[-1]["input"] == ["5"]
        assert embedder.embed_documents([]) == []
        for texts in ([""], ["ok", "  "]):
            with pytest.raises(ValueError):
                embedder.embed_documents(texts)
        assert len(calls) == 4


@pytest.mark.parametrize(
    "data",
    [
        [{"index": 0, "embedding": [1.0]}],
        [],
        [{"index": 1, "embedding": [1.0, 2.0]}],
        [{"index": 0, "embedding": [1.0, "invalide"]}],
    ],
)
def test_invalid_embedding_response(data: list[dict]) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": data}))
    ) as client:
        embedder = OpenRouterEmbedder("modele-factice", 2, 2, ["cle-factice"], client, 3)
        with pytest.raises(ProviderError) as error:
            embedder.embed_query("texte")
        assert error.value.retryable is False


def test_duplicate_embedding_indices_are_rejected() -> None:
    data = [{"index": 0, "embedding": [1.0, 2.0]}] * 2
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": data}))
    ) as client:
        embedder = OpenRouterEmbedder("modele-factice", 2, 2, ["cle-factice"], client, 3)
        with pytest.raises(ProviderError):
            embedder.embed_documents(["a", "b"])


def test_retry_rotates_keys_and_waits() -> None:
    headers: list[str] = []
    waits: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        headers.append(request.headers["Authorization"])
        return httpx.Response(429) if len(headers) == 1 else httpx.Response(200, text="\n {}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert (
            post_json(
                client,
                "https://example.invalid/mock",
                {},
                ["cle-factice-un", "cle-factice-deux"],
                3,
                sleep=waits.append,
            )
            == {}
        )
    assert headers == ["Bearer cle-factice-un", "Bearer cle-factice-deux"]
    assert waits == [0.5]


@pytest.mark.parametrize(
    ("status", "count", "retryable"), [(401, 1, False), (403, 1, False), (500, 3, True)]
)
def test_error_retry_and_secret_redaction(status: int, count: int, retryable: bool) -> None:
    calls: list[str] = []
    waits: list[float] = []
    keys = ["cle-factice-un", "cle-factice-deux"]

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers["Authorization"])
        return httpx.Response(
            status, text=f"{keys[0]} {keys[1]}\nAuthorization: Bearer {keys[0]}\n" + "x" * 300
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as error:
            post_json(client, "https://example.invalid/mock", {}, keys, 3, sleep=waits.append)
    assert len(calls) == count
    assert error.value.retryable is retryable
    assert all(key not in str(error.value) for key in keys)
    assert "authorization" not in str(error.value).lower()
    assert len(str(error.value).split(": ", 1)[1]) <= 200
    assert waits == ([0.5, 1.0] if retryable else [])
    if retryable:
        assert calls == [f"Bearer {keys[0]}", f"Bearer {keys[1]}", f"Bearer {keys[0]}"]


def test_network_errors_do_not_leak_request_details() -> None:
    waits: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Authorization: Bearer cle-factice", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as error:
            post_json(
                client, "https://example.invalid/mock", {}, ["cle-factice"], 4, sleep=waits.append
            )
    assert error.value.retryable is True
    assert "cle-factice" not in str(error.value)
    assert "Authorization" not in str(error.value)
    assert waits == [0.5, 1.0, 2.0]


@pytest.mark.parametrize("body", ["not JSON", "[]", "null"])
def test_invalid_json_is_a_non_retryable_provider_error(body: str) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=body))
    ) as client:
        with pytest.raises(ProviderError) as error:
            post_json(client, "https://example.invalid/mock", {}, ["cle-factice"], 3)
    assert error.value.retryable is False


@pytest.fixture(autouse=True)
def block_real_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("Không được gọi mạng thật")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)


@pytest.mark.parametrize("keys,attempts", [([], 3), ([""], 3), (["cle-factice"], 0)])
def test_invalid_http_configuration(keys: list[str], attempts: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("Không được gửi yêu cầu")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError):
            post_json(client, "https://example.invalid/mock", {}, keys, attempts)
