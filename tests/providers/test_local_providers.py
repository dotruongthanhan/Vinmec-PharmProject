import math

import pytest

from app.core.errors import ProviderError, RetrievalError
from app.core.types import ChatMessage, SearchFilter
from app.providers.bm25_index import Bm25Index
from app.providers.fakes import FakeLLM, HashEmbedder, NoopReranker
from app.providers.memory_store import InMemoryVectorStore
from tests.core.test_types import make_chunk


def test_fake_llm_records_calls_and_exhaustion() -> None:
    llm = FakeLLM([{"a": 1}, {"b": 2}])
    messages = [ChatMessage(role="user", content="Giả lập")]
    schema = {"type": "object"}
    assert llm.complete_json(messages, schema) == {"a": 1}
    assert llm.complete_json(messages, schema) == {"b": 2}
    with pytest.raises(ProviderError) as error:
        llm.complete_json(messages, schema)
    assert error.value.retryable is False
    assert llm.calls[0] == {"messages": messages, "schema": schema}


def test_hash_embedder_determinism_normalization_and_similarity() -> None:
    embedder = HashEmbedder()
    query, related, unrelated, empty = embedder.embed_documents(
        ["meropenem suy thận", "meropenem chỉnh liều suy thận", "amlodipin huyết áp", "?!"]
    )
    assert query == HashEmbedder().embed_query("MEROPENEM suy thận")
    assert len(query) == 64
    assert math.sqrt(sum(x * x for x in query)) == pytest.approx(1)
    assert sum(x * y for x, y in zip(query, related, strict=True)) > sum(
        x * y for x, y in zip(query, unrelated, strict=True)
    )
    assert empty == [0.0] * 64


def test_noop_reranker_preserves_order() -> None:
    reranker = NoopReranker()
    result = reranker.rerank("q", ["a", "b", "c"], 2)
    assert [i for i, _ in result] == [0, 1]
    assert result[0][1] == 1.0 > result[1][1]
    assert reranker.rerank("q", ["a"], 0) == []


def test_memory_store_filters_before_ranking_and_upserts() -> None:
    embedder = HashEmbedder()
    chunks = [
        make_chunk("m1", "meropenem suy thận"),
        make_chunk("m2", "meropenem chỉnh liều"),
        make_chunk("a1", "meropenem suy thận", "amlodipin"),
        make_chunk("a2", "amlodipin huyết áp", "amlodipin"),
    ]
    store = InMemoryVectorStore()
    assert store.search([0.0] * 64, 3, SearchFilter()) == []
    store.upsert(chunks, embedder.embed_documents([c.noi_dung_nhung for c in chunks]))
    result = store.search(
        embedder.embed_query("meropenem suy thận"), 2, SearchFilter(hoat_chat_ids=["meropenem"])
    )
    assert [r.chunk.doan_trich_id for r in result] == ["m1", "m2"]
    assert result[0].diem == pytest.approx(1)
    assert all(r.nguon_diem == "vec_to" for r in result)
    store.upsert([make_chunk("m1", "nội dung mới")], [embedder.embed_query("nội dung mới")])
    assert store.count() == 4
    result = store.search(embedder.embed_query("nội dung mới"), 1, SearchFilter())
    assert result[0].chunk.noi_dung_nhung == "nội dung mới"


def test_memory_cosine_zero_and_dimension_errors_are_atomic() -> None:
    store = InMemoryVectorStore()
    store.upsert([make_chunk("a"), make_chunk("b"), make_chunk("z")], [[2, 0], [1, 1], [0, 0]])
    result = store.search([1, 0], 3, SearchFilter())
    assert [r.diem for r in result] == pytest.approx([1, 1 / math.sqrt(2), 0])
    for chunks, vectors in [([make_chunk()], []), ([make_chunk()], [[1, 0, 0]])]:
        with pytest.raises(RetrievalError):
            store.upsert(chunks, vectors)
        assert store.count() == 3
    with pytest.raises(RetrievalError):
        store.upsert([make_chunk("x"), make_chunk("y")], [[1, 0], [1]])
    with pytest.raises(RetrievalError):
        store.search([1], 1, SearchFilter())


def test_bm25_unaccented_filter_and_rebuild() -> None:
    index = Bm25Index()
    index.build(
        [
            make_chunk("m1", "chỉnh liều khi suy thận"),
            make_chunk("a1", "chỉnh liều khi suy thận", "amlodipin"),
            make_chunk("a2", "điều trị huyết áp", "amlodipin"),
        ]
    )
    results = index.search("chinh lieu suy than", 1, SearchFilter(hoat_chat_ids=["meropenem"]))
    assert [r.chunk.doan_trich_id for r in results] == ["m1"]
    assert results[0].diem > 0
    assert results[0].nguon_diem == "tu_khoa"
    assert index.search("die u", 3, SearchFilter()) == []
    assert index.search("dieu tri", 3, SearchFilter())[0].chunk.doan_trich_id == "a2"
    assert index.search("zzzz", 3, SearchFilter()) == []
    index.build([])
    assert index.search("than", 3, SearchFilter()) == []


def test_bm25_okapi_score() -> None:
    index = Bm25Index()
    index.build([make_chunk("a", "alpha alpha beta"), make_chunk("b", "beta")])
    results = index.search("alpha", 2, SearchFilter())
    expected = math.log(1 + 1.5 / 1.5) * (2 * 2.5) / (2 + 1.5 * (0.25 + 0.75 * 3 / 2))
    assert len(results) == 1
    assert results[0].diem == pytest.approx(expected)
