"""Kiểm thử đồ thị LangGraph của bước AI: thứ tự nút, biên dịch một lần, tương đương tuần tự."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from langsmith.run_helpers import get_tracing_context

from app.config.settings import load_settings
from app.container import build_container
from app.core.types import Chunk, RetrievalQuery, ScoredChunk
from app.db.reader import load_source_cases
from app.domain.loader import load_case
from app.domain.models import CaBenh
from app.kb.names import DrugNameIndex
from app.llm.synthesizer import Synthesizer
from app.orchestration import ai_review
from app.orchestration.ai_review import AiReviewer, AiRunResult
from app.orchestration.evidence import EvidenceCollector
from app.orchestration.graph import dung_danh_sach_nut, dung_do_thi
from app.pipeline import KetQuaThamDinh, run_case
from app.providers.fakes import FakeLLM
from app.retrieval.query_builder import QueryBuilder
from tests.deid_support import temp_id

ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = ROOT / "config/prompts/tong_hop.v1.md"
NAMES = DrugNameIndex.load(ROOT / "data/kb/hoat_chat.json")


def _chunk() -> Chunk:
    return Chunk(
        doan_trich_id="DT-MERO-01",
        tai_lieu_id="TL-MERO",
        muc_cha_id=None,
        nhom_nguon="nhan_thuoc",
        nguon="openfda",
        tang_tin_cay=3,
        hoat_chat_ids=["meropenem"],
        muc="lieu_than",
        duong_dan_muc="Dosage and Administration > Renal Impairment",
        loai_noi_dung="van_ban",
        ngon_ngu="en",
        phien_ban_nguon="20261102",
        url_goc="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=mero",
        noi_dung_goc=(
            "For creatinine clearance 10 to 25 mL/min, administer one-half the "
            "recommended dose every 12 hours."
        ),
        noi_dung_nhung="[Meropenem | FDA] For creatinine clearance 10 to 25 mL/min...",
    )


class _StaticRetriever:
    """Bộ truy xuất giả, không gọi mạng: luôn trả cùng một đoạn."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks

    def retrieve(self, query: RetrievalQuery) -> list[ScoredChunk]:
        del query
        return [ScoredChunk(chunk=c, diem=0.9, nguon_diem="xep_hang_lai") for c in self._chunks]


class _StatelessLLM:
    """LLM giả tất định: lần nào cũng trả cùng một đầu ra (không nhận định thêm)."""

    def complete_json(self, messages: list[Any], schema: dict) -> dict:
        del messages, schema
        return {"nhan_dinh": []}


def _collector(chunks: list[Chunk] | None = None) -> EvidenceCollector:
    container = build_container("test")
    return EvidenceCollector(
        _StaticRetriever(chunks if chunks is not None else [_chunk()]),
        QueryBuilder(container.settings.retrieval),
        NAMES.resolve,
    )


def _synth(llm: Any) -> Synthesizer:
    container = build_container("test")
    return Synthesizer(
        llm=llm,
        prompt_path=PROMPT_PATH,
        case_settings=container.settings.case_context,
        evidence_max_chars=12000,
        max_synthesis_attempts=2,
        model_name="deepseek-flash",
    )


def _comparable(run: AiRunResult) -> dict:
    data = run.model_dump(mode="json")
    data.pop("thoi_gian_ms")
    return data


def _both(
    case: CaBenh,
    rule: KetQuaThamDinh,
    make_collector: Callable[[], EvidenceCollector],
    make_synth: Callable[[], Synthesizer],
) -> tuple[AiRunResult, AiRunResult]:
    sequential = AiReviewer(make_collector(), make_synth(), engine="tuan_tu").run(case, rule)
    graph = AiReviewer(make_collector(), make_synth(), engine="langgraph").run(case, rule)
    return sequential, graph


def build_case_pair() -> tuple[CaBenh, KetQuaThamDinh]:
    container = build_container("test")
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    return case, run_case(case, container.renal_rules)


@pytest.fixture(scope="module")
def cases() -> list[tuple[CaBenh, KetQuaThamDinh]]:
    container = build_container("test")
    loaded = load_source_cases(ROOT)
    assert len(loaded) >= 66
    return [(case, run_case(case, container.renal_rules)) for case in loaded]


def test_graph_node_order_and_edges() -> None:
    nodes = dung_danh_sach_nut(_collector(), _synth(None))
    assert [name for name, _ in nodes] == ["thu_thap_nguon", "tong_hop", "hoan_tat"]

    drawn = dung_do_thi(_collector(), _synth(None)).get_graph()
    edges = {(edge.source, edge.target) for edge in drawn.edges}
    assert edges == {
        ("__start__", "thu_thap_nguon"),
        ("thu_thap_nguon", "tong_hop"),
        ("tong_hop", "hoan_tat"),
        ("hoan_tat", "__end__"),
    }
    assert all(edge.conditional is False for edge in drawn.edges)


def test_graph_has_no_checkpointer() -> None:
    graph = dung_do_thi(_collector(), _synth(None))
    assert graph.checkpointer is None
    assert graph.store is None


def test_graph_compiled_once_per_reviewer(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    real = ai_review.dung_do_thi

    def counting(*args: Any) -> Any:
        calls.append(1)
        return real(*args)

    monkeypatch.setattr(ai_review, "dung_do_thi", counting)
    case = build_case_pair()
    reviewer = AiReviewer(_collector(), _synth(_StatelessLLM()), engine="langgraph")
    for _ in range(3):
        reviewer.run(*case)
    assert calls == [1]
    # Đường tuần tự không biên dịch đồ thị.
    AiReviewer(_collector(), _synth(None), engine="tuan_tu")
    assert calls == [1]


def test_engines_identical_on_all_cases_stateless_llm(
    cases: list[tuple[CaBenh, KetQuaThamDinh]],
) -> None:
    for case, rule in cases:
        sequential, graph = _both(case, rule, _collector, lambda: _synth(_StatelessLLM()))
        assert _comparable(graph) == _comparable(sequential), case.ca_id
        assert graph.llm.trang_thai == "ok"
        assert len(graph.llm.nhan_dinh) == len(rule.phat_hien)


def test_engines_identical_on_all_cases_without_llm_and_without_evidence(
    cases: list[tuple[CaBenh, KetQuaThamDinh]],
) -> None:
    for case, rule in cases:
        sequential, graph = _both(case, rule, lambda: _collector([]), lambda: _synth(None))
        assert _comparable(graph) == _comparable(sequential), case.ca_id
        assert graph.llm.trang_thai == "khong_co_llm"


def test_engines_identical_when_llm_exhausted_provider_error(
    cases: list[tuple[CaBenh, KetQuaThamDinh]],
) -> None:
    for case, rule in cases[:12]:
        sequential, graph = _both(case, rule, _collector, lambda: _synth(FakeLLM([])))
        assert _comparable(graph) == _comparable(sequential), case.ca_id
        assert graph.llm.trang_thai == "loi_llm"


def test_engines_identical_with_verified_ai_finding() -> None:
    case, rule = build_case_pair()
    response = {
        "nhan_dinh": [
            {
                "chi_tiet_y_lenh_id": [temp_id("DEMO-02", "CT-DEMO02-01")],
                "yeu_to": 6,
                "ket_luan": "can_xem",
                "muc_do": "nghiem_trong",
                "nhan_xet": "CrCl 16,0 mL/phút, cần xem xét giảm liều theo nhãn FDA.",
                "ban_ghi_ids": [temp_id("DEMO-02", "XN-DEMO02-01")],
                "trich_dan": [
                    {
                        "doan_trich_id": "DT-MERO-01",
                        "trich_nguyen_van": (
                            "administer one-half the recommended dose every 12 hours."
                        ),
                    }
                ],
                "thong_tin_con_thieu": [],
                "de_xuat": "Cân nhắc giảm một nửa liều mỗi 12 giờ.",
                "bo_sung_cho_ma_luat": "lieu_than_can_chinh",
            }
        ]
    }
    sequential, graph = _both(case, rule, _collector, lambda: _synth(FakeLLM([response])))
    assert _comparable(graph) == _comparable(sequential)
    assert graph.llm.trang_thai == "ok"
    assert any(item.dien_giai is not None for item in graph.llm.nhan_dinh)
    assert graph.doan == [_chunk()]


class _BoomCollector(EvidenceCollector):
    def collect(  # type: ignore[override]
        self, ca: object, ket_qua: object
    ) -> tuple[list[Chunk], list[str]]:
        del ca, ket_qua
        raise RuntimeError("Dữ liệu nhạy cảm bệnh nhân X")


class _BoomSynth(Synthesizer):
    def run(self, ca: object, ket_qua: object, doan: object) -> Any:  # type: ignore[override]
        del ca, ket_qua, doan
        raise ValueError("Prompt nhạy cảm")


class _BadResultSynth(Synthesizer):
    """Trả đối tượng không dựng được AiRunResult, mô phỏng lỗi ở nút hoàn tất."""

    def run(self, ca: object, ket_qua: object, doan: object) -> Any:  # type: ignore[override]
        del ca, ket_qua, doan

        class _Bad:
            canh_bao: list[str] = ["x"]

        return _Bad()


@pytest.mark.parametrize(
    ("collector_cls", "synth_cls", "name", "expects_chunks"),
    [
        (_BoomCollector, Synthesizer, "RuntimeError", False),
        (EvidenceCollector, _BoomSynth, "ValueError", True),
        (EvidenceCollector, _BadResultSynth, "ValidationError", True),
    ],
)
def test_node_exceptions_give_rule_only_result_same_as_sequential(
    collector_cls: type[EvidenceCollector],
    synth_cls: type[Synthesizer],
    name: str,
    expects_chunks: bool,
) -> None:
    case, rule = build_case_pair()
    container = build_container("test")

    def make_collector() -> EvidenceCollector:
        return collector_cls(
            _StaticRetriever([_chunk()]),
            QueryBuilder(container.settings.retrieval),
            NAMES.resolve,
        )

    def make_synth() -> Synthesizer:
        return synth_cls(
            llm=_StatelessLLM(),
            prompt_path=PROMPT_PATH,
            case_settings=container.settings.case_context,
            evidence_max_chars=12000,
            max_synthesis_attempts=2,
            model_name="deepseek-flash",
        )

    sequential, graph = _both(case, rule, make_collector, make_synth)
    assert _comparable(graph) == _comparable(sequential)
    assert graph.llm.trang_thai == "loi_llm"
    assert graph.canh_bao == [f"Bước AI gặp lỗi không mong muốn ({name})"]
    assert graph.llm.so_lan_goi == 0
    assert graph.llm.phien_ban_prompt == "tong_hop.v1"
    assert graph.llm.mo_hinh == "deepseek-flash"
    assert bool(graph.doan) is expects_chunks
    assert "nhạy cảm" not in " ".join(graph.canh_bao)
    # Không phát hiện nào của bộ luật bị mất hay đổi.
    assert [item.phat_hien for item in graph.llm.nhan_dinh] == rule.phat_hien
    assert all(item.nguon_goc == "luat" for item in graph.llm.nhan_dinh)


def test_graph_machinery_failure_falls_back_to_rule_only() -> None:
    case, rule = build_case_pair()
    reviewer = AiReviewer(_collector(), _synth(_StatelessLLM()), engine="langgraph")

    class _BrokenGraph:
        def invoke(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("hỏng")

    reviewer._graph = _BrokenGraph()
    run = reviewer.run(case, rule)
    assert run.llm.trang_thai == "loi_llm"
    assert run.canh_bao == ["Bước AI gặp lỗi không mong muốn (RuntimeError)"]
    assert [item.phat_hien for item in run.llm.nhan_dinh] == rule.phat_hien


def test_graph_run_disables_langsmith_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    seen: list[object] = []

    class _Probe(Synthesizer):
        def run(self, ca: object, ket_qua: object, doan: object) -> Any:  # type: ignore[override]
            seen.append(get_tracing_context()["enabled"])
            return super().run(ca, ket_qua, doan)  # type: ignore[arg-type]

    container = build_container("test")
    synth = _Probe(
        llm=_StatelessLLM(),
        prompt_path=PROMPT_PATH,
        case_settings=container.settings.case_context,
        evidence_max_chars=12000,
        max_synthesis_attempts=1,
        model_name="deepseek-flash",
    )
    case, rule = build_case_pair()
    AiReviewer(_collector(), synth, engine="langgraph").run(case, rule)
    assert seen == [False]


def test_engine_flag_from_settings_and_override() -> None:
    expected = load_settings().orchestration.engine
    assert expected in ("langgraph", "tuan_tu")
    assert AiReviewer(_collector(), _synth(None)).engine == expected
    assert AiReviewer(_collector(), _synth(None), engine="tuan_tu").engine == "tuan_tu"
    assert AiReviewer(_collector(), _synth(None), engine="langgraph").engine == "langgraph"
    with pytest.raises(ValueError):
        AiReviewer(_collector(), _synth(None), engine="khac")  # type: ignore[arg-type]
