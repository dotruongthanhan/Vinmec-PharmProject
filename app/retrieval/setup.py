"""Nơi lắp ráp riêng cho nhúng và truy xuất của T04b."""

from pathlib import Path

from app.config.settings import get_secret
from app.container import Container
from app.providers.bm25_index import Bm25Index
from app.providers.embedder_factory import resolve_rag_providers
from app.providers.http import create_client
from app.providers.memory_store import InMemoryVectorStore
from app.retrieval.corpus import index_corpus, load_corpus
from app.retrieval.hybrid import HybridRetriever

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_GET_SECRET = get_secret


def build_retriever(container: Container, warnings: list[str] | None = None) -> HybridRetriever:
    """Lắp theo cấu hình, luôn dùng kho véc-tơ trong bộ nhớ."""
    settings = container.settings
    chunks = load_corpus(_ROOT / "data/kb_curated/chunks.jsonl")
    raw_cache = Path(settings.embedding.cache_path)
    cache_path = raw_cache if raw_cache.is_absolute() else _ROOT / raw_cache
    secret_fn = get_secret if get_secret is not _DEFAULT_GET_SECRET else None
    embedder, reranker, client = resolve_rag_providers(
        settings,
        cache_path=cache_path,
        get_fake_embedder=lambda: container.embedder,
        get_noop_reranker=lambda: container.reranker,
        create_client_fn=create_client,
        get_secret_fn=secret_fn,
    )
    try:
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
