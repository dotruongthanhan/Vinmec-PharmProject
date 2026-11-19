"""Kiểm thử GeminiEmbedder, hàm dựng chung và tách khoá cache theo mô hình."""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import httpx
import pytest

from app.config.settings import load_settings
from app.core.errors import ConfigError, ProviderError
from app.core.interfaces import Embedder
from app.providers import embedder_factory
from app.providers.cached_embedder import CachedEmbedder
from app.providers.fakes import HashEmbedder
from app.providers.gemini_embed import GeminiEmbedder
from app.providers.openrouter_embed import OpenRouterEmbedder
from tests.architecture.test_import_boundaries import environment_violations

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def block_real_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("Không được gọi mạng thật")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)


def test_gemini_embed_documents_query_payload_and_empty_checks() -> None:
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-embedding-2:batchEmbedContents"
        )
        assert request.headers["x-goog-api-key"] == "khoa-gemini-gia-lap"
        assert "authorization" not in request.headers
        payload = json.loads(request.content)
        calls.append(payload)
        embeddings = [
            {"values": [float(item["content"]["parts"][0]["text"]), 1.0]}
            for item in payload["requests"]
        ]
        return httpx.Response(200, text="\n\n " + json.dumps({"embeddings": embeddings}))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        embedder = GeminiEmbedder(
            "gemini-embedding-2",
            2,
            2,
            "khoa-gemini-gia-lap",
            client,
            3,
            sleep=lambda _: None,
        )
        assert isinstance(embedder, Embedder)
        assert embedder.embed_documents(["0", "1", "2", "3", "4"]) == [
            [float(index), 1.0] for index in range(5)
        ]
        assert [len(call["requests"]) for call in calls] == [2, 2, 1]
        for call in calls:
            for item in call["requests"]:
                assert item["model"] == "models/gemini-embedding-2"
                assert item["outputDimensionality"] == 2
                assert item["taskType"] == "RETRIEVAL_DOCUMENT"

        assert embedder.embed_query("5") == [5.0, 1.0]
        assert len(calls) == 4
        assert calls[-1]["requests"] == [
            {
                "model": "models/gemini-embedding-2",
                "content": {"parts": [{"text": "5"}]},
                "outputDimensionality": 2,
                "taskType": "RETRIEVAL_QUERY",
            }
        ]
        assert embedder.embed_documents([]) == []
        assert len(calls) == 4
        for bad_texts in ([""], ["ok", "   "]):
            with pytest.raises(ValueError):
                embedder.embed_documents(bad_texts)
        for bad_query in ("", "  "):
            with pytest.raises(ValueError):
                embedder.embed_query(bad_query)
        assert len(calls) == 4


def test_gemini_batch_size_is_capped_at_100() -> None:
    batch_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        batch_sizes.append(len(payload["requests"]))
        return httpx.Response(
            200,
            json={"embeddings": [{"values": [1.0, 0.0]} for _ in payload["requests"]]},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        embedder = GeminiEmbedder(
            "gemini-embedding-2",
            2,
            150,
            "khoa-gemini-gia-lap",
            client,
            3,
            sleep=lambda _: None,
        )
        assert embedder.batch_size == 100
        vectors = embedder.embed_documents([f"doan-{i}" for i in range(105)])
        assert len(vectors) == 105
        assert batch_sizes == [100, 5]


@pytest.mark.parametrize(
    "raw_response",
    [
        json.dumps({"embeddings": [{"values": [1.0]}]}),
        json.dumps({"embeddings": []}),
        json.dumps({"embeddings": [{"values": [1.0, 2.0]}, {"values": [3.0, 4.0]}]}),
        json.dumps({"embeddings": [{"values": [1.0, "khong-hop-le"]}]}),
        json.dumps({"embeddings": [{"values": [1.0, True]}]}),
        '{"embeddings": [{"values": [1.0, 1e999]}]}',
        json.dumps({"embeddings": [{}]}),
        json.dumps({}),
        "not JSON",
        "[]",
    ],
)
def test_gemini_invalid_response_raises_non_retryable_provider_error(raw_response: str) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _req: httpx.Response(200, text=raw_response))
    ) as client:
        embedder = GeminiEmbedder("gemini-embedding-2", 2, 2, "khoa-gia-lap", client, 3)
        with pytest.raises(ProviderError) as error:
            embedder.embed_query("van ban")
        assert error.value.retryable is False


def test_gemini_retries_429_and_5xx_with_exponential_backoff() -> None:
    statuses = [429, 503, 200]
    waits: list[float] = []
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        status = statuses[attempts]
        attempts += 1
        if status == 200:
            return httpx.Response(200, json={"embeddings": [{"values": [0.5, 0.5]}]})
        return httpx.Response(status, text="tam thoi qua tai")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        embedder = GeminiEmbedder(
            "gemini-embedding-2",
            2,
            10,
            "khoa-gia-lap",
            client,
            3,
            sleep=waits.append,
        )
        assert embedder.embed_query("meropenem") == [0.5, 0.5]
    assert attempts == 3
    assert waits == [0.5, 1.0]


@pytest.mark.parametrize(
    ("status", "expected_calls", "retryable"),
    [(401, 1, False), (403, 1, False), (500, 3, True)],
)
def test_gemini_error_retry_and_secret_redaction(
    status: int, expected_calls: int, retryable: bool
) -> None:
    calls = 0
    waits: list[float] = []
    secret = "khoa-gemini-bi-mat-123"

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers["x-goog-api-key"] == secret
        return httpx.Response(
            status,
            text=f"error {secret}\nx-goog-api-key: {secret}\n" + "x" * 300,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        embedder = GeminiEmbedder(
            "gemini-embedding-2",
            2,
            10,
            secret,
            client,
            3,
            sleep=waits.append,
        )
        with pytest.raises(ProviderError) as error:
            embedder.embed_query("van ban")
    assert calls == expected_calls
    assert error.value.retryable is retryable
    assert secret not in str(error.value)
    assert "x-goog-api-key" not in str(error.value).lower()
    assert len(str(error.value).split(": ", 1)[1]) <= 200
    assert waits == ([0.5, 1.0] if retryable else [])


def test_gemini_network_error_retries_and_does_not_leak_secret() -> None:
    waits: list[float] = []
    secret = "khoa-gemini-bi-mat-net"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"x-goog-api-key: {secret}", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        embedder = GeminiEmbedder(
            "gemini-embedding-2",
            2,
            10,
            secret,
            client,
            4,
            sleep=waits.append,
        )
        with pytest.raises(ProviderError) as error:
            embedder.embed_query("van ban")
    assert error.value.retryable is True
    assert secret not in str(error.value)
    assert waits == [0.5, 1.0, 2.0]


def test_build_embedder_uses_get_secret_and_selects_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = load_settings()
    assert base.embedding.provider == "gemini"
    assert base.embedding.active == "gemini-embedding-2"
    assert base.embedding.dimensions == 2048
    assert base.embedding.batch_size == 100

    seen_secrets: list[str] = []

    def fake_secret(name: str) -> str:
        seen_secrets.append(name)
        if name == "OPENROUTER_API_KEY_2":
            raise ConfigError(name)
        return f"secret-{name}"

    monkeypatch.setenv("GEMINI_API_KEY", "khong-duoc-doc-truc-tiep")
    monkeypatch.setattr(embedder_factory, "get_secret", fake_secret)

    with httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(200))) as client:
        gemini = embedder_factory.build_embedder(base, client)
        assert isinstance(gemini, GeminiEmbedder)
        assert gemini.model == "gemini-embedding-2"
        assert gemini.dimensions == 2048
        assert gemini.batch_size == 100
        assert gemini.api_key == "secret-GEMINI_API_KEY"
        assert seen_secrets == ["GEMINI_API_KEY"]

        openrouter_settings = base.model_copy(
            update={"embedding": base.embedding.model_copy(update={"provider": "openrouter"})}
        )
        openrouter = embedder_factory.build_embedder(openrouter_settings, client)
        assert isinstance(openrouter, OpenRouterEmbedder)
        assert openrouter.keys == ["secret-OPENROUTER_API_KEY"]

    fake_settings = load_settings("test")
    assert isinstance(embedder_factory.build_embedder(fake_settings), HashEmbedder)

    unknown = base.model_copy(
        update={"embedding": base.embedding.model_copy(update={"provider": "khac"})}
    )
    with pytest.raises(ConfigError):
        embedder_factory.build_embedder(unknown)


def test_architecture_no_direct_env_access_in_embedding_modules() -> None:
    for rel in (
        "app/providers/gemini_embed.py",
        "app/providers/embedder_factory.py",
        "app/retrieval/embed_corpus.py",
        "app/retrieval/setup.py",
        "app/orchestration/evidence.py",
        "app/kb/dictionary/candidates.py",
    ):
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert environment_violations(source) == [], rel


def test_cached_embedder_uses_distinct_keys_for_nemotron_and_gemini(tmp_path: Path) -> None:
    cache_path = tmp_path / "embeddings.sqlite"

    class _CounterEmbedder(HashEmbedder):
        def __init__(self) -> None:
            super().__init__(8)
            self.calls: list[list[str]] = []

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            self.calls.append(list(texts))
            return super().embed_documents(texts)

    inner = _CounterEmbedder()
    text = "meropenem chỉnh liều suy thận"
    old_cache = CachedEmbedder(inner, cache_path, "nvidia/nemotron-3.5-embed-1b:free")
    new_cache = CachedEmbedder(inner, cache_path, "gemini-embedding-2")

    old_key = old_cache._key("doc", text)
    new_key = new_cache._key("doc", text)
    assert old_key != new_key
    assert (
        old_key
        == hashlib.sha256(f"nvidia/nemotron-3.5-embed-1b:free\ndoc\n{text}".encode()).hexdigest()
    )
    assert new_key == hashlib.sha256(f"gemini-embedding-2\ndoc\n{text}".encode()).hexdigest()

    old_cache.embed_documents([text])
    new_cache.embed_documents([text])
    assert len(inner.calls) == 2

    with closing(sqlite3.connect(cache_path)) as connection:
        stored_keys = {row[0] for row in connection.execute("SELECT key FROM embeddings")}
    assert stored_keys == {old_key, new_key}
