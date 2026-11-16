"""Kiểm thử thu thập đoạn nguồn và bộ truy xuất dựng lười theo hoạt chất."""

from pathlib import Path

import pytest

from app.config.settings import load_settings
from app.container import Container
from app.core.errors import ProviderError
from app.core.types import RetrievalQuery, ScoredChunk
from app.domain.loader import load_case
from app.kb.names import DrugNameIndex
from app.orchestration import evidence as evidence_module
from app.orchestration.evidence import (
    MAX_EVIDENCE_CHUNKS,
    EvidenceCollector,
    LazyRetrieverFactory,
)
from app.pipeline import run_case
from app.retrieval.query_builder import QueryBuilder
from app.rules import load_renal_rules
from tests.core.test_types import make_chunk

ROOT = Path(__file__).resolve().parents[2]


class _FakeRetriever:
    """Bộ truy xuất giả ghi lại mọi truy vấn và trả đoạn theo nhóm mục."""

    def __init__(
        self,
        finding_results: list[ScoredChunk] | None = None,
        baseline_results: list[ScoredChunk] | None = None,
        fail_after: int | None = None,
    ) -> None:
        self.finding_results = finding_results or []
        self.baseline_results = baseline_results or []
        self.fail_after = fail_after
        self.queries: list[RetrievalQuery] = []

    def retrieve(self, query: RetrievalQuery) -> list[ScoredChunk]:
        if self.fail_after is not None and len(self.queries) >= self.fail_after:
            raise ProviderError("Lỗi mạng giả lập", retryable=True)
        self.queries.append(query)
        if "lieu_than" in query.bo_loc.muc:
            return list(self.finding_results)
        return list(self.baseline_results)


def _scored(chunk_id: str, score: float, drug: str = "meropenem") -> ScoredChunk:
    return ScoredChunk(
        chunk=make_chunk(code=chunk_id, text=f"Nội dung {chunk_id}", drug=drug),
        diem=score,
        nguon_diem="xep_hang_lai",
    )


def test_collector_dedupes_orders_finding_before_baseline_and_caps_at_8() -> None:
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    result = run_case(case, load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json"))
    retriever = _FakeRetriever(
        finding_results=[
            _scored("F-LOW", 0.40),
            _scored("SHARED", 0.55),
            _scored("F-HIGH", 0.90),
        ],
        baseline_results=[
            _scored("SHARED", 0.99),
            _scored("B-1", 0.95),
            _scored("B-2", 0.85),
            _scored("B-3", 0.75),
            _scored("B-4", 0.65),
            _scored("B-5", 0.55),
            _scored("B-6", 0.45),
        ],
    )
    names = DrugNameIndex.load(ROOT / "data/kb/hoat_chat.json")
    collector = EvidenceCollector(
        retriever,
        QueryBuilder(load_settings("test").retrieval),
        names.resolve,
    )

    chunks, warnings = collector.collect(case, result)

    assert warnings == []
    assert MAX_EVIDENCE_CHUNKS == 8
    assert len(chunks) == MAX_EVIDENCE_CHUNKS
    assert [chunk.doan_trich_id for chunk in chunks] == [
        "F-HIGH",
        "SHARED",
        "F-LOW",
        "B-1",
        "B-2",
        "B-3",
        "B-4",
        "B-5",
    ]


def test_collector_handles_retrieval_error_without_raising() -> None:
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    result = run_case(case, load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json"))
    partial_retriever = _FakeRetriever(finding_results=[_scored("F-1", 0.8)], fail_after=1)
    names = DrugNameIndex.load(ROOT / "data/kb/hoat_chat.json")
    builder = QueryBuilder(load_settings("test").retrieval)

    partial_collector = EvidenceCollector(partial_retriever, builder, names.resolve)
    chunks, warnings = partial_collector.collect(case, result)
    assert [chunk.doan_trich_id for chunk in chunks] == ["F-1"]
    assert warnings == ["Không lấy được đoạn nguồn, AI chỉ dùng dữ liệu ca"]

    failing_retriever = _FakeRetriever(fail_after=0)
    failing_collector = EvidenceCollector(failing_retriever, builder, names.resolve)
    empty_chunks, err_warnings = failing_collector.collect(case, result)
    assert empty_chunks == []
    assert err_warnings == ["Không lấy được đoạn nguồn, AI chỉ dùng dữ liệu ca"]


def test_collector_warns_and_skips_unresolved_ingredient() -> None:
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    result = run_case(case, load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json"))
    retriever = _FakeRetriever()
    builder = QueryBuilder(load_settings("test").retrieval)

    collector = EvidenceCollector(retriever, builder, lambda _name: [])
    chunks, warnings = collector.collect(case, result)

    assert chunks == []
    assert warnings == ["Chưa có nguồn cho hoạt chất Meropenem"]
    assert retriever.queries == []


def test_collector_never_puts_case_text_in_queries_on_demo06() -> None:
    case = load_case(ROOT / "data/mock/demo/DEMO-06.json")
    result = run_case(case, load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json"))
    retriever = _FakeRetriever()
    names = DrugNameIndex.load(ROOT / "data/kb/hoat_chat.json")
    collector = EvidenceCollector(
        retriever,
        QueryBuilder(load_settings("test").retrieval),
        names.resolve,
    )

    collector.collect(case, result)

    assert retriever.queries
    for query in retriever.queries:
        for text in query.van_ban:
            assert "Bỏ qua" not in text
            assert "đau họng" not in text
            assert "nuốt vướng" not in text
            assert "không có cảnh báo" not in text


def test_lazy_retriever_factory_loads_once_filters_and_caches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_path = tmp_path / "chunks.jsonl"
    chunks = [
        make_chunk("M-1", "meropenem renal", drug="meropenem", muc="lieu_than"),
        make_chunk("M-2", "meropenem allergy", drug="meropenem", muc="chong_chi_dinh"),
        make_chunk("W-1", "warfarin interaction", drug="warfarin", muc="tuong_tac"),
        make_chunk("W-2", "warfarin bleeding", drug="warfarin", muc="canh_bao"),
    ]
    corpus_path.write_text(
        "\n".join(chunk.model_dump_json() for chunk in chunks) + "\n",
        encoding="utf-8",
    )

    load_calls = 0
    original_load = evidence_module.load_corpus

    def counted_load(path: Path) -> list:
        nonlocal load_calls
        load_calls += 1
        return original_load(path)

    monkeypatch.setattr(evidence_module, "load_corpus", counted_load)
    container = Container(load_settings("test"))
    factory = LazyRetrieverFactory(container, corpus_path)

    mero = factory.for_ingredients({"meropenem"})
    assert mero is factory.for_ingredients({"meropenem"})
    assert mero.vector_store.count() == 2

    warfarin = factory.for_ingredients({"warfarin"})
    assert warfarin.vector_store.count() == 2
    assert load_calls == 1

    missing_factory = LazyRetrieverFactory(container, tmp_path / "khong_co.jsonl")
    names = DrugNameIndex.load(ROOT / "data/kb/hoat_chat.json")
    collector = EvidenceCollector(
        missing_factory,
        QueryBuilder(container.settings.retrieval),
        names.resolve,
    )
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    result = run_case(case, container.renal_rules)
    collected, warnings = collector.collect(case, result)
    assert collected == []
    assert warnings == ["Không lấy được đoạn nguồn, AI chỉ dùng dữ liệu ca"]
