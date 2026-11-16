import pytest

from app.core.errors import ProviderError
from app.core.types import RetrievalQuery, ScoredChunk, SearchFilter
from app.providers.bm25_index import Bm25Index
from app.providers.fakes import HashEmbedder
from app.providers.memory_store import InMemoryVectorStore
from app.retrieval.corpus import index_corpus
from app.retrieval.fusion import rrf
from app.retrieval.hybrid import HybridRetriever
from tests.core.test_types import make_chunk


class ControlledReranker:
    """Gán điểm theo nội dung để không phụ thuộc thứ tự ứng viên."""

    def __init__(self, scores: dict[str, float], fail: bool = False) -> None:
        self.scores = scores
        self.fail = fail
        self.calls: list[tuple[str, list[str], int]] = []

    def rerank(self, query: str, passages: list[str], top_n: int) -> list[tuple[int, float]]:
        self.calls.append((query, list(passages), top_n))
        if self.fail:
            raise ProviderError("Lỗi giả lập", retryable=True)
        return sorted(
            [(index, self.scores[passage]) for index, passage in enumerate(passages)],
            key=lambda item: item[1],
            reverse=True,
        )[:top_n]


def make_retriever(scores: dict[str, float], fail: bool = False) -> HybridRetriever:
    chunks = [
        make_chunk("a", "meropenem alpha", tang_tin_cay=3, muc="lieu_than"),
        make_chunk("b", "meropenem beta", tang_tin_cay=3, muc="lieu_than"),
        make_chunk("c", "meropenem gamma", tang_tin_cay=1, muc="lieu_than"),
        make_chunk("other-drug", "meropenem alpha beta gamma", "amlodipin", muc="lieu_than"),
        make_chunk("other-section", "meropenem alpha beta gamma", muc="tuong_tac"),
        make_chunk("other-group", "meropenem alpha beta gamma", muc="lieu_than", nhom_nguon="khac"),
    ]
    embedder = HashEmbedder(64)
    store, keyword = InMemoryVectorStore(), Bm25Index()
    index_corpus(chunks, embedder, store, keyword)
    return HybridRetriever(embedder, ControlledReranker(scores, fail), store, keyword, 60, 0.2)


def make_query() -> RetrievalQuery:
    return RetrievalQuery(
        van_ban=["meropenem alpha", "meropenem gamma"],
        bo_loc=SearchFilter(
            hoat_chat_ids=["meropenem"], nhom_nguon="nhan_thuoc", muc=["lieu_than"]
        ),
        k_query=10,
        k_rerank=3,
    )


def test_both_branches_apply_filters_for_every_language(monkeypatch: pytest.MonkeyPatch) -> None:
    retriever = make_retriever(
        {"meropenem alpha": 0.9, "meropenem beta": 0.8, "meropenem gamma": 0.7}
    )
    query = make_query()
    calls: dict[str, list[list[ScoredChunk]]] = {"keyword": [], "vector": []}
    keyword_search = retriever.keyword_index.search
    vector_search = retriever.vector_store.search

    def keyword(text: str, k: int, bo_loc: SearchFilter) -> list[ScoredChunk]:
        assert bo_loc == query.bo_loc and k == query.k_query
        results = keyword_search(text, k, bo_loc)
        calls["keyword"].append(results)
        return results

    def vector(values: list[float], k: int, bo_loc: SearchFilter) -> list[ScoredChunk]:
        assert bo_loc == query.bo_loc and k == query.k_query
        results = vector_search(values, k, bo_loc)
        calls["vector"].append(results)
        return results

    monkeypatch.setattr(retriever.keyword_index, "search", keyword)
    monkeypatch.setattr(retriever.vector_store, "search", vector)
    outcome = retriever.retrieve_detailed(query)
    assert outcome.che_do == "lai" and outcome.canh_bao == []
    assert len(calls["keyword"]) == len(calls["vector"]) == 2
    for branch in calls.values():
        for results in branch:
            assert {result.chunk.doan_trich_id for result in results} == {"a", "b", "c"}
    assert retriever.reranker.calls[0][0] == query.van_ban[0]


def test_threshold_and_stable_trust_tier_order() -> None:
    retriever = make_retriever(
        {"meropenem alpha": 0.8, "meropenem beta": 0.9, "meropenem gamma": 0.2}
    )
    results = retriever.retrieve(make_query())
    assert [result.chunk.doan_trich_id for result in results] == ["c", "b", "a"]
    assert [result.diem for result in results] == [0.2, 0.9, 0.8]
    assert all(result.nguon_diem == "xep_hang_lai" for result in results)
    retriever.reranker.scores["meropenem alpha"] = 0.199
    assert [result.chunk.doan_trich_id for result in retriever.retrieve(make_query())] == ["c", "b"]


def test_all_below_threshold_returns_empty_without_lowering_threshold() -> None:
    retriever = make_retriever(
        {"meropenem alpha": 0.1, "meropenem beta": 0.0, "meropenem gamma": 0.199}
    )
    outcome = retriever.retrieve_detailed(make_query())
    assert outcome.ket_qua == []
    assert outcome.che_do == "lai"
    assert outcome.canh_bao == []


@pytest.mark.parametrize("fail_on", [1, 2])
def test_embedding_failure_discards_entire_vector_branch(
    monkeypatch: pytest.MonkeyPatch, fail_on: int
) -> None:
    retriever = make_retriever(
        {"meropenem alpha": 0.8, "meropenem beta": 0.7, "meropenem gamma": 0.6}, True
    )
    query = make_query().model_copy(update={"k_rerank": 2})
    expected = rrf(
        [
            [
                result.chunk.doan_trich_id
                for result in retriever.keyword_index.search(text, query.k_query, query.bo_loc)
            ]
            for text in query.van_ban
        ],
        60,
    )[:2]
    inner = retriever.embedder.embed_query
    calls = 0

    def failing(text: str) -> list[float]:
        nonlocal calls
        calls += 1
        if calls == fail_on:
            raise ProviderError("Lỗi nhúng giả lập", retryable=True)
        return inner(text)

    monkeypatch.setattr(retriever.embedder, "embed_query", failing)
    outcome = retriever.retrieve_detailed(query)
    assert outcome.che_do == "tu_khoa"
    assert len(outcome.canh_bao) == 2
    assert [(result.chunk.doan_trich_id, result.diem) for result in outcome.ket_qua] == expected
    assert all(result.nguon_diem == "rrf" for result in outcome.ket_qua)


def test_embedding_failure_can_still_rerank_keyword_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retriever = make_retriever(
        {"meropenem alpha": 0.9, "meropenem beta": 0.8, "meropenem gamma": 0.7}
    )

    def failing(text: str) -> list[float]:
        raise ProviderError("Lỗi giả lập")

    monkeypatch.setattr(retriever.embedder, "embed_query", failing)
    outcome = retriever.retrieve_detailed(make_query())
    assert outcome.che_do == "tu_khoa" and len(outcome.canh_bao) == 1
    assert outcome.ket_qua
    assert all(result.nguon_diem == "xep_hang_lai" for result in outcome.ket_qua)


def test_reranker_failure_keeps_rrf_order_and_ignores_threshold() -> None:
    retriever = make_retriever({}, True)
    retriever.rerank_min_score = 1.0
    query = make_query().model_copy(update={"k_query": 2, "k_rerank": 2})
    rankings = []
    for text in query.van_ban:
        rankings.append(
            [
                result.chunk.doan_trich_id
                for result in retriever.keyword_index.search(text, query.k_query, query.bo_loc)
            ]
        )
        rankings.append(
            [
                result.chunk.doan_trich_id
                for result in retriever.vector_store.search(
                    retriever.embedder.embed_query(text), query.k_query, query.bo_loc
                )
            ]
        )
    expected = rrf(rankings, 60)[:2]
    outcome = retriever.retrieve_detailed(query)
    assert outcome.che_do == "tu_khoa" and outcome.canh_bao
    assert [(result.chunk.doan_trich_id, result.diem) for result in outcome.ket_qua] == expected
    assert all(result.nguon_diem == "rrf" for result in outcome.ket_qua)
    assert len(retriever.reranker.calls[0][1]) == query.k_query


def test_no_candidates_does_not_rerank() -> None:
    retriever = make_retriever({}, True)
    query = make_query().model_copy(update={"bo_loc": SearchFilter(hoat_chat_ids=["absent"])})
    assert retriever.retrieve(query) == []
    assert retriever.reranker.calls == []
