"""Nơi lắp ráp riêng cho nhúng và truy xuất của T04b."""

from pathlib import Path

from app.config.settings import get_secret
from app.container import Container
from app.core.errors import ConfigError
from app.core.interfaces import Embedder, Reranker
from app.providers.bm25_index import Bm25Index
from app.providers.cached_embedder import CachedEmbedder
from app.providers.http import create_client
from app.providers.memory_store import InMemoryVectorStore
from app.providers.openrouter_embed import OpenRouterEmbedder
from app.providers.openrouter_rerank import OpenRouterReranker
from app.retrieval.corpus import index_corpus, load_corpus
from app.retrieval.hybrid import HybridRetriever

_ROOT = Path(__file__).resolve().parents[2]


def build_retriever(container: Container, warnings: list[str] | None = None) -> HybridRetriever:
    """Lắp theo cấu hình, luôn dùng kho véc-tơ trong bộ nhớ."""
    settings = container.settings
    embedding, rerank = settings.embedding, settings.rerank
    if embedding.provider not in ("openrouter", "fake"):
        raise ConfigError("Nhà cung cấp nhúng chưa được hỗ trợ")
    if rerank.provider not in ("openrouter", "noop"):
        raise ConfigError("Nhà cung cấp xếp hạng lại chưa được hỗ trợ")
    chunks = load_corpus(_ROOT / "data/kb_curated/chunks.jsonl")
    client = None
    keys: list[str] = []
    if "openrouter" in (embedding.provider, rerank.provider):
        keys.append(get_secret("OPENROUTER_API_KEY"))
        try:
            keys.append(get_secret("OPENROUTER_API_KEY_2"))
        except ConfigError:
            pass
        client = create_client()
    try:
        embedder: Embedder
        if embedding.provider == "fake":
            embedder = container.embedder
        else:
            assert client is not None
            embedder = CachedEmbedder(
                OpenRouterEmbedder(
                    embedding.active,
                    embedding.dimensions,
                    embedding.batch_size,
                    keys,
                    client,
                    settings.agent.max_attempts,
                ),
                _ROOT / embedding.cache_path,
                model_id=embedding.active,
            )
        reranker: Reranker
        if rerank.provider == "noop":
            reranker = container.reranker
        else:
            assert client is not None
            reranker = OpenRouterReranker(rerank.active, keys, client, settings.agent.max_attempts)
        vector_store = InMemoryVectorStore()
        keyword_index = Bm25Index()
        index_corpus(chunks, embedder, vector_store, keyword_index)
        retriever = HybridRetriever(
            embedder,
            reranker,
            vector_store,
            keyword_index,
            settings.retrieval.rrf_k,
            settings.retrieval.rerank_min_score,
        )
        if settings.vector_store.provider != "memory":
            warning = "T04b dùng InMemoryVectorStore thay kho véc-tơ cấu hình."
            retriever.canh_bao.append(warning)
            if warnings is not None:
                warnings.append(warning)
        return retriever
    except Exception:
        if client is not None:
            client.close()
        raise
