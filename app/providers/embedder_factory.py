"""Hàm dựng chung cho bộ nhúng và lớp dự phòng khi thiếu khoá API."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import httpx

from app.config.settings import Settings, get_secret
from app.core.errors import ConfigError, ProviderError
from app.core.interfaces import Embedder, Reranker
from app.providers.cached_embedder import CachedEmbedder
from app.providers.fakes import HashEmbedder
from app.providers.gemini_embed import GeminiEmbedder
from app.providers.openrouter_embed import OpenRouterEmbedder
from app.providers.openrouter_rerank import OpenRouterReranker


class UnavailableEmbedder:
    """Bộ nhúng dự phòng báo lỗi nhà cung cấp để RAG lùi về tìm theo từ khoá."""

    def __init__(self, dimensions: int, secret_name: str) -> None:
        self.dimensions = dimensions
        self.secret_name = secret_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Ném ValueError nếu rỗng, ngược lại ném ProviderError để bỏ qua bước nhúng."""
        if any(not text.strip() for text in texts):
            raise ValueError("Văn bản nhúng không được rỗng")
        if not texts:
            return []
        raise ProviderError(f"Thiếu cấu hình {self.secret_name}", retryable=False)

    def embed_query(self, text: str) -> list[float]:
        """Ném ValueError nếu rỗng, ngược lại ném ProviderError để chạy chế độ từ khoá."""
        if not text.strip():
            raise ValueError("Văn bản nhúng không được rỗng")
        raise ProviderError(f"Thiếu cấu hình {self.secret_name}", retryable=False)


class UnavailableReranker:
    """Bộ xếp hạng lại dự phòng báo lỗi nhà cung cấp để giữ thứ tự RRF."""

    def __init__(self, secret_name: str) -> None:
        self.secret_name = secret_name

    def rerank(self, query: str, passages: list[str], top_n: int) -> list[tuple[int, float]]:
        """Trả rỗng khi không có đoạn, ngược lại ném ProviderError để giữ thứ tự RRF."""
        del query
        if not passages or top_n <= 0:
            return []
        raise ProviderError(f"Thiếu cấu hình {self.secret_name}", retryable=False)


def read_openrouter_keys(get_secret_fn: Callable[[str], str] = get_secret) -> list[str]:
    """Đọc khoá chính OpenRouter và khoá dự phòng thứ hai nếu có."""
    keys = [get_secret_fn("OPENROUTER_API_KEY")]
    try:
        keys.append(get_secret_fn("OPENROUTER_API_KEY_2"))
    except ConfigError:
        pass
    return keys


def build_embedder(
    settings: Settings,
    client: httpx.Client | None = None,
    *,
    keys: Sequence[str] | None = None,
    get_secret_fn: Callable[[str], str] | None = None,
) -> Embedder:
    """Dựng bộ nhúng theo `settings.embedding.provider` (`gemini` | `openrouter` | `fake`)."""
    embedding = settings.embedding
    provider = embedding.provider
    secret_reader = get_secret if get_secret_fn is None else get_secret_fn

    if provider == "fake":
        return HashEmbedder(embedding.dimensions)
    if provider == "gemini":
        if client is None:
            raise ValueError("Cần client HTTP cho bộ nhúng gemini")
        api_key = keys[0] if keys else secret_reader("GEMINI_API_KEY")
        return GeminiEmbedder(
            model=embedding.active,
            dimensions=embedding.dimensions,
            batch_size=embedding.batch_size,
            api_key=api_key,
            client=client,
            max_attempts=settings.agent.max_attempts,
        )
    if provider == "openrouter":
        if client is None:
            raise ValueError("Cần client HTTP cho bộ nhúng openrouter")
        resolved_keys = list(keys) if keys is not None else read_openrouter_keys(secret_reader)
        return OpenRouterEmbedder(
            model=embedding.active,
            dimensions=embedding.dimensions,
            batch_size=embedding.batch_size,
            keys=resolved_keys,
            client=client,
            max_attempts=settings.agent.max_attempts,
        )
    raise ConfigError("Nhà cung cấp nhúng chưa được hỗ trợ")


def resolve_rag_providers(
    settings: Settings,
    *,
    cache_path: Path,
    get_fake_embedder: Callable[[], Embedder],
    get_noop_reranker: Callable[[], Reranker],
    create_client_fn: Callable[[], httpx.Client],
    get_secret_fn: Callable[[str], str] | None = None,
) -> tuple[Embedder, Reranker, httpx.Client | None]:
    """Lắp bộ nhúng có bộ đệm và bộ xếp hạng lại; thiếu khoá thì lùi về chế độ từ khoá."""
    embedding, rerank = settings.embedding, settings.rerank
    if embedding.provider not in ("gemini", "openrouter", "fake"):
        raise ConfigError("Nhà cung cấp nhúng chưa được hỗ trợ")
    if rerank.provider not in ("openrouter", "noop"):
        raise ConfigError("Nhà cung cấp xếp hạng lại chưa được hỗ trợ")

    secret_reader = get_secret if get_secret_fn is None else get_secret_fn
    client = (
        create_client_fn()
        if embedding.provider != "fake" or rerank.provider == "openrouter"
        else None
    )
    try:
        keys: list[str] | None = None
        if "openrouter" in (embedding.provider, rerank.provider):
            try:
                keys = read_openrouter_keys(secret_reader)
            except ConfigError:
                keys = None

        embedder: Embedder
        if embedding.provider == "fake":
            embedder = get_fake_embedder()
        else:
            assert client is not None
            inner: Embedder
            if embedding.provider == "openrouter" and keys is None:
                inner = UnavailableEmbedder(embedding.dimensions, "OPENROUTER_API_KEY")
            else:
                try:
                    inner = build_embedder(
                        settings,
                        client,
                        keys=keys if embedding.provider == "openrouter" else None,
                        get_secret_fn=secret_reader,
                    )
                except ConfigError as exc:
                    inner = UnavailableEmbedder(embedding.dimensions, str(exc))
            embedder = CachedEmbedder(inner, cache_path, model_id=embedding.active)

        reranker: Reranker
        if rerank.provider == "noop":
            reranker = get_noop_reranker()
        else:
            assert client is not None
            if keys is None:
                reranker = UnavailableReranker("OPENROUTER_API_KEY")
            else:
                reranker = OpenRouterReranker(
                    rerank.active, keys, client, settings.agent.max_attempts
                )
        return embedder, reranker, client
    except Exception:
        if client is not None:
            client.close()
        raise
