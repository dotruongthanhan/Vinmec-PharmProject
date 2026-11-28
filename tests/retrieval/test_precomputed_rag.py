"""Kiểm thử RAG dùng vector đã lưu trên DB, đường lui embedding NULL và kiểm chiều/mô hình."""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

import pytest

from app.config.settings import load_settings
from app.container import Container
from app.core.errors import RetrievalError
from app.core.types import RetrievalQuery, SearchFilter
from app.orchestration import evidence as evidence_mod
from app.orchestration.evidence import LazyRetrieverFactory
from app.providers.bm25_index import Bm25Index
from app.providers.fakes import HashEmbedder, NoopReranker
from app.providers.memory_store import InMemoryVectorStore
from app.retrieval.corpus import index_corpus
from app.retrieval.hybrid import HybridRetriever
from tests.core.test_types import make_chunk
from tests.kb.test_store_from_db import FakePsycopgConnection, _seed_chunks_in_fake_pg


class CountingEmbedder:
    """Bộ nhúng giả đếm số lần gọi embed_documents và embed_query."""

    def __init__(self, dimensions: int = 2048) -> None:
        self._inner = HashEmbedder(dimensions)
        self.dimensions = dimensions
        self.doc_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.doc_calls.append(list(texts))
        return self._inner.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return self._inner.embed_query(text)


def test_db_retriever_uses_precomputed_vectors_and_embeds_query_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunks = [
        make_chunk("M-1", "meropenem renal impairment", drug="meropenem", muc="lieu_than"),
        make_chunk("M-2", "meropenem allergic reaction", drug="meropenem", muc="canh_bao"),
        make_chunk("W-1", "warfarin bleeding risk", drug="warfarin", muc="canh_bao"),
    ]
    hasher = HashEmbedder(2048)
    vectors = {
        chunk.doan_trich_id: json.dumps(hasher.embed_query(chunk.noi_dung_nhung))
        for chunk in chunks
    }

    with closing(FakePsycopgConnection(as_dicts=True)) as conn:
        _seed_chunks_in_fake_pg(conn, chunks, embeddings=vectors)

        @contextmanager
        def fake_pool(url: str) -> Iterator[FakePsycopgConnection]:
            yield conn

        monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/test")
        monkeypatch.setattr(evidence_mod.read_pool, "connection", fake_pool)

        settings = load_settings("test")
        settings = settings.model_copy(
            update={"app": settings.app.model_copy(update={"kb_source": "db"})}
        )
        container = Container(settings)
        embedder = CountingEmbedder(2048)
        container.__dict__["embedder"] = embedder

        factory = LazyRetrieverFactory(container)
        retriever = factory.for_ingredients({"meropenem"})
        assert embedder.doc_calls == []
        assert retriever.vector_store.count() == 2

        query = RetrievalQuery(
            van_ban=["meropenem renal"],
            bo_loc=SearchFilter(hoat_chat_ids=["meropenem"]),
            k_query=5,
            k_rerank=2,
        )
        db_outcome = retriever.retrieve_detailed(query)
        assert embedder.doc_calls == []
        assert embedder.query_calls == ["meropenem renal"]
        assert [item.chunk.doan_trich_id for item in db_outcome.ket_qua] == ["M-1", "M-2"]

        # Đối chiếu xếp hạng giống hệt đường dựng trực tiếp trong bộ nhớ.
        mem_store = InMemoryVectorStore()
        bm25 = Bm25Index()
        index_corpus(chunks[:2], HashEmbedder(2048), mem_store, bm25)
        expected_retriever = HybridRetriever(
            HashEmbedder(2048),
            NoopReranker(),
            mem_store,
            bm25,
            settings.retrieval.rrf_k,
            settings.retrieval.rerank_min_score,
        )
        expected_outcome = expected_retriever.retrieve_detailed(query)
        assert db_outcome.ket_qua == expected_outcome.ket_qua


def test_db_retriever_embeds_missing_vectors_only_and_logs_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    chunks = [
        make_chunk("M-1", "meropenem renal impairment", drug="meropenem", muc="lieu_than"),
        make_chunk("M-2", "meropenem dosage guide", drug="meropenem", muc="lieu_dung"),
        make_chunk("M-3", "meropenem missing vector", drug="meropenem", muc="canh_bao"),
    ]
    hasher = HashEmbedder(2048)
    embeddings: dict[str, str | None] = {
        "M-1": json.dumps(hasher.embed_query(chunks[0].noi_dung_nhung)),
        "M-2": json.dumps(hasher.embed_query(chunks[1].noi_dung_nhung)),
        "M-3": None,
    }

    with closing(FakePsycopgConnection(as_dicts=True)) as conn:
        _seed_chunks_in_fake_pg(conn, chunks, embeddings=embeddings)

        @contextmanager
        def fake_pool(url: str) -> Iterator[FakePsycopgConnection]:
            yield conn

        monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/test")
        monkeypatch.setattr(evidence_mod.read_pool, "connection", fake_pool)

        settings = load_settings("test")
        settings = settings.model_copy(
            update={"app": settings.app.model_copy(update={"kb_source": "db"})}
        )
        container = Container(settings)
        embedder = CountingEmbedder(2048)
        container.__dict__["embedder"] = embedder

        factory = LazyRetrieverFactory(container)
        with caplog.at_level("WARNING", logger="app.retrieval.corpus"):
            retriever = factory.for_ingredients({"meropenem"})

        assert embedder.doc_calls == [[chunks[2].noi_dung_nhung]]
        assert retriever.vector_store.count() == 3
        assert "1 đoạn thiếu embedding" in caplog.text


def test_db_retriever_rejects_dimension_and_model_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunks = [
        make_chunk("M-1", "meropenem bad dim", drug="meropenem"),
        make_chunk("M-2", "meropenem good dim", drug="meropenem"),
    ]
    embeddings = {
        "M-1": json.dumps([0.1, 0.2, 0.3, 0.4]),
        "M-2": json.dumps([0.01] * 2048),
    }

    with closing(FakePsycopgConnection(as_dicts=True)) as conn:
        _seed_chunks_in_fake_pg(conn, chunks, embeddings=embeddings)

        @contextmanager
        def fake_pool(url: str) -> Iterator[FakePsycopgConnection]:
            yield conn

        monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/test")
        monkeypatch.setattr(evidence_mod.read_pool, "connection", fake_pool)

        base = load_settings("test")
        db_settings = base.model_copy(
            update={"app": base.app.model_copy(update={"kb_source": "db"})}
        )
        dim_factory = LazyRetrieverFactory(Container(db_settings))
        with pytest.raises(RetrievalError, match="Số chiều"):
            dim_factory.for_ingredients({"meropenem"})

        wrong_model_settings = db_settings.model_copy(
            update={
                "embedding": db_settings.embedding.model_copy(
                    update={"active": "other-embedding-model"}
                )
            }
        )
        model_factory = LazyRetrieverFactory(Container(wrong_model_settings))
        with pytest.raises(RetrievalError, match="Mô hình nhúng"):
            model_factory.for_ingredients({"meropenem"})


def test_memory_store_load_precomputed_validates_finite_and_dimensions() -> None:
    store = InMemoryVectorStore()
    chunk = make_chunk("C-1", "meropenem")
    with pytest.raises(RetrievalError, match="không hữu hạn"):
        store.load_precomputed([chunk], [[math.nan, 0.1]])
    with pytest.raises(RetrievalError, match="cấu hình"):
        store.load_precomputed([chunk], [[0.1, 0.2]], expected_dimensions=4)
    store.load_precomputed([chunk], [[0.1, 0.2]], expected_dimensions=2)
    assert store.count() == 1


def test_file_source_keeps_file_corpus_and_embedder_path(tmp_path: Path) -> None:
    corpus_path = tmp_path / "chunks.jsonl"
    chunk = make_chunk("F-1", "meropenem file corpus", drug="meropenem")
    corpus_path.write_text(chunk.model_dump_json() + "\n", encoding="utf-8")

    settings = load_settings("test")
    settings = settings.model_copy(
        update={"app": settings.app.model_copy(update={"kb_source": "file"})}
    )
    container = Container(settings)
    embedder = CountingEmbedder(2048)
    container.__dict__["embedder"] = embedder

    factory = LazyRetrieverFactory(container, corpus_path)
    retriever = factory.for_ingredients({"meropenem"})
    assert embedder.doc_calls == [[chunk.noi_dung_nhung]]
    assert retriever.vector_store.count() == 1
