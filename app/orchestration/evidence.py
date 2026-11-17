"""Thu thập đoạn nguồn theo hoạt chất và dựng lười bộ truy xuất cho từng ca bệnh."""

from collections.abc import Callable, Sequence
from pathlib import Path
from threading import RLock

from app.config.settings import get_secret
from app.container import Container
from app.core.errors import ConfigError
from app.core.interfaces import Embedder, Reranker, Retriever
from app.core.types import Chunk, RetrievalQuery, ScoredChunk
from app.domain.loader import ingredients_of
from app.domain.models import CaBenh
from app.pipeline import KetQuaThamDinh
from app.providers.bm25_index import Bm25Index
from app.providers.cached_embedder import CachedEmbedder
from app.providers.http import create_client
from app.providers.memory_store import InMemoryVectorStore
from app.providers.openrouter_embed import OpenRouterEmbedder
from app.providers.openrouter_rerank import OpenRouterReranker
from app.retrieval.corpus import index_corpus, load_corpus
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.query_builder import QueryBuilder

MAX_EVIDENCE_CHUNKS = 8

_ROOT = Path(__file__).resolve().parents[2]
_RETRIEVAL_ERROR_WARNING = "Không lấy được đoạn nguồn, AI chỉ dùng dữ liệu ca"

IngredientResolver = Callable[[str], Sequence[str] | str | None]


def _normalize_resolved(raw: Sequence[str] | str | None) -> list[str]:
    """Chuẩn hoá kết quả tra tên hoạt chất thành danh sách mã không trùng lặp."""
    if raw is None:
        return []
    if isinstance(raw, str):
        cleaned = raw.strip()
        return [cleaned] if cleaned else []
    seen: list[str] = []
    for item in raw:
        cleaned = str(item).strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _query_key(query: RetrievalQuery) -> tuple[object, ...]:
    """Khoá nhận diện truy vấn trùng lặp giữa các phát hiện và truy vấn nền."""
    return (
        tuple(query.van_ban),
        query.bo_loc.nhom_nguon,
        tuple(query.bo_loc.hoat_chat_ids),
        tuple(query.bo_loc.muc),
        query.k_query,
        query.k_rerank,
    )


class LazyRetrieverFactory:
    """Nạp kho đoạn một lần và dựng HybridRetriever riêng cho tập hoạt chất đang xét."""

    def __init__(self, container: Container, corpus_path: Path | None = None) -> None:
        self._container = container
        self._corpus_path = (
            Path(corpus_path) if corpus_path is not None else _ROOT / "data/kb_curated/chunks.jsonl"
        )
        self._lock = RLock()
        self._chunks: list[Chunk] | None = None
        self._cache: dict[frozenset[str], HybridRetriever] = {}
        self._client: object | None = None
        self._embedder: Embedder | None = None
        self._reranker: Reranker | None = None

    def _get_chunks(self) -> list[Chunk]:
        """Nạp toàn bộ kho đoạn đúng một lần."""
        if self._chunks is None:
            self._chunks = load_corpus(self._corpus_path)
        return self._chunks

    def _ensure_providers(self) -> tuple[Embedder, Reranker]:
        """Khởi tạo bộ nhúng và bộ xếp hạng lại dùng chung theo cấu hình."""
        if self._embedder is not None and self._reranker is not None:
            return self._embedder, self._reranker

        settings = self._container.settings
        embedding, rerank = settings.embedding, settings.rerank
        if embedding.provider not in ("openrouter", "fake"):
            raise ConfigError("Nhà cung cấp nhúng chưa được hỗ trợ")
        if rerank.provider not in ("openrouter", "noop"):
            raise ConfigError("Nhà cung cấp xếp hạng lại chưa được hỗ trợ")

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
            if embedding.provider == "fake":
                embedder: Embedder = self._container.embedder
            else:
                assert client is not None
                raw_cache = Path(embedding.cache_path)
                cache_path = raw_cache if raw_cache.is_absolute() else _ROOT / raw_cache
                embedder = CachedEmbedder(
                    OpenRouterEmbedder(
                        embedding.active,
                        embedding.dimensions,
                        embedding.batch_size,
                        keys,
                        client,
                        settings.agent.max_attempts,
                    ),
                    cache_path,
                    model_id=embedding.active,
                )

            if rerank.provider == "noop":
                reranker: Reranker = self._container.reranker
            else:
                assert client is not None
                reranker = OpenRouterReranker(
                    rerank.active,
                    keys,
                    client,
                    settings.agent.max_attempts,
                )
        except Exception:
            if client is not None:
                client.close()
            raise

        self._client = client
        self._embedder = embedder
        self._reranker = reranker
        return embedder, reranker

    def for_ingredients(self, ids: set[str]) -> HybridRetriever:
        """Trả HybridRetriever chỉ lập chỉ mục các đoạn liên quan tới tập hoạt chất."""
        key = frozenset(ids)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached

            chunks = self._get_chunks()
            embedder, reranker = self._ensure_providers()
            subset = [chunk for chunk in chunks if set(chunk.hoat_chat_ids) & key]
            vector_store = InMemoryVectorStore()
            keyword_index = Bm25Index()
            if subset:
                index_corpus(subset, embedder, vector_store, keyword_index)

            settings = self._container.settings
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
            self._cache[key] = retriever
            return retriever

    def close(self) -> None:
        """Đóng máy khách HTTP dùng chung nếu đã khởi tạo."""
        with self._lock:
            if self._client is not None:
                close_fn = getattr(self._client, "close", None)
                if callable(close_fn):
                    close_fn()
                self._client = None


class EvidenceCollector:
    """Thu thập tối đa 8 đoạn nguồn ưu tiên theo phát hiện của bộ luật rồi truy vấn nền."""

    def __init__(
        self,
        retriever: Retriever | LazyRetrieverFactory | None,
        query_builder: QueryBuilder,
        resolve_name: IngredientResolver,
    ) -> None:
        self._retriever = retriever
        self._query_builder = query_builder
        self._resolve_name = resolve_name

    def collect(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> tuple[list[Chunk], list[str]]:
        """Lấy đoạn nguồn cho ca bệnh; lỗi truy xuất chuyển thành cảnh báo và không ném tiếp."""
        warnings: list[str] = []
        resolved_by_hc: dict[str, list[tuple[str, str, str]]] = {}
        line_entries: dict[str, list[tuple[str, str, str]]] = {}
        all_entries: list[tuple[str, str, str]] = []
        seen_kb_ids: set[str] = set()

        for line in ca.y_lenh_cho_duyet.chi_tiet:
            entries_for_line: list[tuple[str, str, str]] = []
            for hc in ingredients_of(ca, line):
                if hc.hoat_chat_id not in resolved_by_hc:
                    lookup = (
                        hc.ten_quoc_te.strip()
                        if hc.ten_quoc_te and hc.ten_quoc_te.strip()
                        else hc.ten_hoat_chat
                    )
                    resolved_ids = _normalize_resolved(self._resolve_name(lookup))
                    if not resolved_ids:
                        warning = f"Chưa có nguồn cho hoạt chất {hc.ten_hoat_chat}"
                        if warning not in warnings:
                            warnings.append(warning)
                        resolved_by_hc[hc.hoat_chat_id] = []
                    else:
                        resolved_by_hc[hc.hoat_chat_id] = [
                            (
                                kb_id,
                                lookup if len(resolved_ids) == 1 else kb_id.replace("_", " "),
                                hc.ten_hoat_chat,
                            )
                            for kb_id in resolved_ids
                        ]
                for entry in resolved_by_hc[hc.hoat_chat_id]:
                    entries_for_line.append(entry)
                    if entry[0] not in seen_kb_ids:
                        seen_kb_ids.add(entry[0])
                        all_entries.append(entry)
            line_entries[line.chi_tiet_y_lenh_id] = entries_for_line

        seen_queries: set[tuple[object, ...]] = set()
        finding_queries: list[RetrievalQuery] = []
        for finding in ket_qua.phat_hien:
            if finding.ket_luan == "dat":
                continue
            for line_id in finding.chi_tiet_y_lenh_id:
                for kb_id, ten_inn, ten_viet in line_entries.get(line_id, []):
                    query = self._query_builder.for_finding(
                        kb_id,
                        ten_inn,
                        ten_viet,
                        finding.yeu_to,
                        finding.ma_luat,
                    )
                    qkey = _query_key(query)
                    if qkey not in seen_queries:
                        seen_queries.add(qkey)
                        finding_queries.append(query)

        baseline_queries: list[RetrievalQuery] = []
        for kb_id, ten_inn, ten_viet in all_entries:
            for query in self._query_builder.baseline(kb_id, ten_inn, ten_viet):
                qkey = _query_key(query)
                if qkey not in seen_queries:
                    seen_queries.add(qkey)
                    baseline_queries.append(query)

        if not finding_queries and not baseline_queries:
            return [], warnings

        if self._retriever is None:
            warnings.append(_RETRIEVAL_ERROR_WARNING)
            return [], warnings

        active_retriever: Retriever
        if isinstance(self._retriever, LazyRetrieverFactory):
            try:
                active_retriever = self._retriever.for_ingredients(seen_kb_ids)
            except Exception:
                warnings.append(_RETRIEVAL_ERROR_WARNING)
                return [], warnings
        else:
            active_retriever = self._retriever

        finding_scored: list[ScoredChunk] = []
        baseline_scored: list[ScoredChunk] = []
        retrieval_failed = False

        for query in finding_queries:
            try:
                finding_scored.extend(active_retriever.retrieve(query))
            except Exception:
                retrieval_failed = True
                break

        if not retrieval_failed:
            for query in baseline_queries:
                try:
                    baseline_scored.extend(active_retriever.retrieve(query))
                except Exception:
                    retrieval_failed = True
                    break

        if retrieval_failed:
            warnings.append(_RETRIEVAL_ERROR_WARNING)

        finding_sorted = sorted(finding_scored, key=lambda item: item.diem, reverse=True)
        baseline_sorted = sorted(baseline_scored, key=lambda item: item.diem, reverse=True)

        selected: list[Chunk] = []
        seen_chunk_ids: set[str] = set()
        for scored in (*finding_sorted, *baseline_sorted):
            chunk_id = scored.chunk.doan_trich_id
            if chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk_id)
            selected.append(scored.chunk)
            if len(selected) >= MAX_EVIDENCE_CHUNKS:
                break

        return selected, warnings
