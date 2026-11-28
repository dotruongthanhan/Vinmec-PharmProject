"""Thu thập đoạn nguồn theo hoạt chất và dựng lười bộ truy xuất cho từng ca bệnh."""

import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from threading import RLock

import numpy as np
import psycopg

from app.config.settings import get_secret
from app.container import Container
from app.core.errors import ConfigError, RetrievalError
from app.core.interfaces import Embedder, Reranker, Retriever
from app.core.types import Chunk, RetrievalQuery, ScoredChunk
from app.db.read_pool import read_pool
from app.domain.loader import ingredients_of
from app.domain.models import CaBenh
from app.pipeline import KetQuaThamDinh
from app.providers.bm25_index import Bm25Index
from app.providers.embedder_factory import resolve_rag_providers
from app.providers.http import create_client
from app.providers.memory_store import InMemoryVectorStore
from app.retrieval.corpus import (
    index_corpus,
    index_corpus_with_precomputed,
    load_corpus,
    load_corpus_for_ingredients_from_db,
)
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.query_builder import QueryBuilder

MAX_EVIDENCE_CHUNKS = 8
_DB_EMBEDDING_MODEL = "gemini-embedding-2"

_LOGGER = logging.getLogger(__name__)
_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_GET_SECRET = get_secret
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

    def __init__(
        self,
        container: Container,
        corpus_path: Path | None = None,
        *,
        use_db: bool | None = None,
        db_embedding_model: str = _DB_EMBEDDING_MODEL,
    ) -> None:
        self._container = container
        self._explicit_path = corpus_path is not None
        self._corpus_path = (
            Path(corpus_path) if corpus_path is not None else _ROOT / "data/kb_curated/chunks.jsonl"
        )
        self._use_db = use_db
        self._db_embedding_model = db_embedding_model
        self._lock = RLock()
        self._chunks: list[Chunk] | None = None
        self._cache: dict[frozenset[str], HybridRetriever] = {}
        self._item_cache: dict[frozenset[str], list[tuple[Chunk, list[float] | None]]] = {}
        self._client: object | None = None
        self._embedder: Embedder | None = None
        self._reranker: Reranker | None = None

    def _should_use_db(self) -> bool:
        """Xác định đọc kho đoạn từ PostgreSQL hay tệp theo cấu hình kb_source."""
        if self._use_db is not None:
            return self._use_db
        kb_source = self._container.settings.app.kb_source
        if kb_source == "db":
            return True
        if kb_source == "file":
            return False
        if self._explicit_path or self._corpus_path.is_file():
            return False
        try:
            return bool(get_secret(self._container.settings.database.url_env).strip())
        except ConfigError:
            return False

    def _get_chunks(self) -> list[Chunk]:
        """Nạp toàn bộ kho đoạn từ tệp đúng một lần."""
        if self._chunks is None:
            self._chunks = load_corpus(self._corpus_path)
        return self._chunks

    def _validate_db_embedding_settings(self, embedder: Embedder) -> None:
        """Kiểm tra mô hình và số chiều cấu hình khớp với vector lưu trên DB."""
        embedding = self._container.settings.embedding
        if embedding.active != self._db_embedding_model:
            raise RetrievalError(
                f"Mô hình nhúng cấu hình ({embedding.active}) "
                f"không khớp dữ liệu DB ({self._db_embedding_model})"
            )
        if embedder.dimensions != embedding.dimensions:
            raise RetrievalError(
                f"Số chiều bộ nhúng ({embedder.dimensions}) lệch cấu hình ({embedding.dimensions})"
            )

    def _load_db_chunks_for_ingredients(
        self, ids: frozenset[str]
    ) -> list[tuple[Chunk, list[float] | None]]:
        """Truy vấn các đoạn thuộc tập hoạt chất kèm embedding từ PostgreSQL."""
        dims = self._container.settings.embedding.dimensions
        try:
            url = get_secret(self._container.settings.database.url_env).strip()
            if not url:
                raise ConfigError(self._container.settings.database.url_env)
            with read_pool.connection(url) as conn:
                return load_corpus_for_ingredients_from_db(
                    conn,
                    ids,
                    expected_dimensions=dims,
                )
        except RetrievalError as exc:
            _LOGGER.warning("Không nạp được kho đoạn từ DB (%s)", type(exc).__name__)
            raise
        except (ConfigError, OSError, psycopg.Error, ValueError) as exc:
            _LOGGER.warning("Không nạp được kho đoạn từ DB (%s)", type(exc).__name__)
            raise RetrievalError("Không đọc được kho đoạn từ cơ sở dữ liệu") from None

    def _ensure_providers(self) -> tuple[Embedder, Reranker]:
        """Khởi tạo bộ nhúng và bộ xếp hạng lại dùng chung theo cấu hình."""
        if self._embedder is not None and self._reranker is not None:
            return self._embedder, self._reranker

        settings = self._container.settings
        raw_cache = Path(settings.embedding.cache_path)
        cache_path = raw_cache if raw_cache.is_absolute() else _ROOT / raw_cache
        secret_fn = get_secret if get_secret is not _DEFAULT_GET_SECRET else None
        embedder, reranker, client = resolve_rag_providers(
            settings,
            cache_path=cache_path,
            get_fake_embedder=lambda: self._container.embedder,
            get_noop_reranker=lambda: self._container.reranker,
            create_client_fn=create_client,
            get_secret_fn=secret_fn,
        )

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

            settings = self._container.settings
            embedder, reranker = self._ensure_providers()
            vector_store = InMemoryVectorStore()
            keyword_index = Bm25Index()

            if self._should_use_db():
                self._validate_db_embedding_settings(embedder)
                if key:
                    items = self._load_db_chunks_for_ingredients(key)
                    if items:
                        index_corpus_with_precomputed(
                            items,
                            embedder,
                            vector_store,
                            keyword_index,
                            expected_dimensions=settings.embedding.dimensions,
                        )
            else:
                chunks = self._get_chunks()
                subset = [chunk for chunk in chunks if set(chunk.hoat_chat_ids) & key]
                if subset:
                    index_corpus(subset, embedder, vector_store, keyword_index)

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

    def ingredient_items(self, ids: set[str]) -> list[tuple[Chunk, list[float] | None]]:
        """Đoạn của tập hoạt chất kèm vector có sẵn (None nếu chưa có); không gọi nhúng."""
        key = frozenset(ids)
        if not key:
            return []
        with self._lock:
            cached = self._item_cache.get(key)
            if cached is None:
                if self._should_use_db():
                    cached = self._load_db_chunks_for_ingredients(key)
                else:
                    cached = [
                        (chunk, None)
                        for chunk in self._get_chunks()
                        if set(chunk.hoat_chat_ids) & key
                    ]
                self._item_cache[key] = cached
            return list(cached)

    def rank_by_vector(
        self, items: Sequence[tuple[Chunk, list[float] | None]], query: str, k: int
    ) -> list[Chunk]:
        """Xếp hạng đoạn theo cosine với vector câu hỏi; chỉ nhúng bù đoạn chưa có vector."""
        if not items or k <= 0:
            return []
        embedder, _ = self._ensure_providers()
        if self._should_use_db():
            self._validate_db_embedding_settings(embedder)
        query_vector = np.asarray(embedder.embed_query(query), dtype=float)
        vectors: list[list[float] | None] = [vector for _, vector in items]
        missing = [index for index, vector in enumerate(vectors) if vector is None]
        if missing:
            computed = embedder.embed_documents([items[i][0].noi_dung_nhung for i in missing])
            for index, vector in zip(missing, computed, strict=True):
                vectors[index] = vector
        try:
            matrix = np.asarray(vectors, dtype=float)
        except (TypeError, ValueError):
            raise RetrievalError("Số chiều véc-tơ không khớp") from None
        if matrix.ndim != 2 or matrix.shape[1] != query_vector.size:
            raise RetrievalError("Số chiều véc-tơ không khớp truy vấn")
        denominators = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_vector)
        scores = np.divide(
            matrix @ query_vector, denominators, out=np.zeros(len(items)), where=denominators != 0
        )
        order = np.argsort(-scores, kind="stable")[:k]
        return [items[int(i)][0] for i in order]

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
