"""Kiểm luật tương tác trên đường chạy thật, chỉ dùng dữ liệu giả lập cục bộ."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import container as container_mod
from app.api.main import create_app
from app.api.presenter import present_ai_result, present_case
from app.api.schemas import MedicalRecord
from app.api.service import CaseService
from app.config.settings import load_settings
from app.container import Container
from app.db.reader import DbReviewService, load_source_cases
from app.domain.models import CaBenh
from app.kb.interactions import InteractionStore
from app.kb.interactions.models import MaTranTuongTac
from app.kb.names import DrugNameIndex
from app.kb.resolver import DrugResolver
from app.llm.synthesizer import Synthesizer
from app.orchestration.ai_review import AiReviewer, Engine
from app.orchestration.evidence import EvidenceCollector
from app.pipeline import run_case
from app.providers.fakes import FakeLLM
from app.retrieval.query_builder import QueryBuilder
from app.rules import interaction
from app.rules.engine import _priority_key
from app.rules.registry import RuleContext, default_rules
from app.ui.services import PipelineReviewService

ROOT = Path(__file__).resolve().parents[2]
RENAL = ROOT / "data/kb/quy_tac_lieu_than.json"


@pytest.fixture(scope="module")
def runtime_context() -> RuleContext:
    context = Container(load_settings("test")).rule_context
    assert context.resolver is not None
    assert context.interactions is not None
    return context


@pytest.fixture(scope="module")
def hs024() -> CaBenh:
    return next(case for case in load_source_cases(ROOT) if case.ca_id == "HS-024")


@pytest.fixture
def case_dir(tmp_path: Path, hs024: CaBenh) -> Path:
    (tmp_path / "HS-024.json").write_text(hs024.model_dump_json(), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("source", ["file", "db"])
def test_get_hs024_links_major_pair_and_reuses_evaluation(
    source: str,
    case_dir: Path,
    hs024: CaBenh,
    runtime_context: RuleContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CASE_SOURCE", source)
    monkeypatch.setattr(container_mod, "get_rule_context", lambda: runtime_context, raising=False)
    if source == "db":
        monkeypatch.setattr(DbReviewService, "list_cases", lambda self: ([hs024], []))
        monkeypatch.setattr(CaseService, "_administrative", lambda self, cases: {})
        monkeypatch.setattr(CaseService, "_read_medical_record", lambda self, case: MedicalRecord())
    evaluations: list[CaBenh] = []
    original = interaction._evaluate

    def evaluate(
        case: CaBenh, resolver: DrugResolver, store: InteractionStore
    ) -> tuple[MaTranTuongTac, list[interaction.PairAssessment]]:
        evaluations.append(case)
        return original(case, resolver, store)

    monkeypatch.setattr(interaction, "_evaluate", evaluate)
    service = CaseService(case_dir, RENAL, case_dir / "feedback.jsonl", ai_runner=None, asker=None)
    with TestClient(create_app(service)) as client:
        for _ in range(2):
            response = client.get("/api/cases/HS-024")
            assert response.status_code == 200
            body = response.json()
            matrix = body["ma_tran_tuong_tac"]
            assert matrix is not None
            assert len(matrix["thuoc"]) == 4
            assert len(matrix["cap"]) == 6
            assert body["nhan_dinh"]["so_luat_da_chay"] == len(default_rules())
            pair = next(pair for pair in matrix["cap"] if pair["muc"] == "nghiem_trong")
            finding = next(
                row
                for row in body["nhan_dinh"]["can_chu_y"]
                if row["nhan_dinh_id"] == pair["nhan_dinh_id"]
            )
            assert finding["yeu_to"].startswith("4.")
            assert finding["muc_do_ma"] == "nghiem_trong"
            assert {pair["a"], pair["b"]} == set(finding["chi_tiet_y_lenh_id"])
            assert "amiodarone" in pair["tom_tat"].lower()
            assert "digoxin" in pair["tom_tat"].lower()
        assert len(evaluations) == 1


def test_hs024_unknown_pair_shows_missing_consequence_and_no_nested_parentheses(
    case_dir: Path,
    runtime_context: RuleContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("CASE_SOURCE", "file")
    monkeypatch.setattr(container_mod, "get_rule_context", lambda: runtime_context, raising=False)
    service = CaseService(case_dir, RENAL, case_dir / "feedback.jsonl", ai_runner=None, asker=None)
    with TestClient(create_app(service)) as client:
        response = client.get("/api/cases/HS-024")
        assert response.status_code == 200
        body = response.json()
        pair = next(
            row
            for row in body["ma_tran_tuong_tac"]["cap"]
            if "amiodarone" in (row["tom_tat"] or "").lower()
            and "paracetamol" in row["tom_tat"].lower()
        )
        assert pair["muc"] == "thieu_du_lieu"
        finding = next(
            row
            for row in body["nhan_dinh"]["can_chu_y"]
            if row["nhan_dinh_id"] == pair["nhan_dinh_id"]
        )
        evidence = "\n".join(row["mo_ta"] for row in finding["can_cu"])
        assert "Hậu quả: thiếu" in evidence
        assert "Hậu quả: None" not in evidence
        assert pair["ly_do"] == "DDInter ghi mức chưa rõ (Unknown)"
        for text in (pair["tom_tat"], pair["ly_do"], finding["nhan_xet"]):
            assert text.count("(") == text.count(")") == 1


@pytest.mark.parametrize("missing", ["tra_cuu", "tuong_tac", "both"])
def test_missing_index_keeps_five_rules_and_warns_once(
    missing: str,
    case_dir: Path,
    runtime_context: RuleContext,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("CASE_SOURCE", "file")
    settings = load_settings("test")
    absent = {
        field: str(case_dir / f"absent_{field}.sqlite")
        for field in ([missing] if missing != "both" else ["tra_cuu", "tuong_tac"])
    }
    settings = settings.model_copy(update={"app": settings.app.model_copy(update=absent)})
    container = Container(settings)
    if missing == "tra_cuu":
        container.__dict__["interaction_store"] = runtime_context.interactions
    elif missing == "tuong_tac":
        container.__dict__["drug_resolver"] = runtime_context.resolver
    monkeypatch.setattr(
        container_mod, "get_rule_context", lambda: container.rule_context, raising=False
    )
    service = CaseService(case_dir, RENAL, case_dir / "feedback.jsonl", ai_runner=None, asker=None)
    with TestClient(create_app(service)) as client:
        caplog.clear()
        for _ in range(2):
            response = client.get("/api/cases/HS-024")
            assert response.status_code == 200
            body = response.json()
            assert body["ma_tran_tuong_tac"] is None
            assert body["nhan_dinh"]["so_luat_da_chay"] == len(default_rules()) - 1
            unchecked = body["nhan_dinh"]["yeu_to_chua_kiem"]
            assert "4. Tương tác thuốc" in unchecked
            all_rows = [*body["nhan_dinh"]["can_chu_y"], *body["nhan_dinh"]["dat"]]
            codes = {row["ma_luat"] for row in all_rows}
            base_codes = {"di_ung_khong_co", "trung_hoat_chat_khong_co", "lich_dung_phu_hop"}
            assert base_codes <= codes
            if missing in {"tra_cuu", "both"}:
                assert "3. Chỉ định, liều, đường dùng" in unchecked
                assert "thuoc_benh_ddinter" not in codes
                assert "lieu_toi_da_khong_co_nguon" not in codes
            else:
                assert "thuoc_benh_ddinter" in codes
                assert "lieu_toi_da_khong_co_nguon" in codes
            service._results.clear()
        warnings = [row for row in caplog.records if row.name.startswith("app.")]
        assert len(warnings) == 1


@pytest.mark.parametrize("service_type", [PipelineReviewService, DbReviewService])
def test_review_services_pass_shared_dependencies(
    service_type: type[PipelineReviewService] | type[DbReviewService],
    case_dir: Path,
    hs024: CaBenh,
    runtime_context: RuleContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(container_mod, "get_rule_context", lambda: runtime_context, raising=False)
    service = (
        service_type(case_dir, RENAL)
        if service_type is PipelineReviewService
        else service_type(RENAL)
    )
    result = service.review(hs024)
    assert any(row.yeu_to == 4 and row.muc_do == "nghiem_trong" for row in result.phat_hien)
    assert result.phat_hien == sorted(result.phat_hien, key=_priority_key)
    assert present_case(hs024, result, []).ma_tran_tuong_tac is not None


@pytest.mark.parametrize("engine", ["tuan_tu", "langgraph"])
def test_ai_keeps_factor_four_from_real_service(
    engine: Engine,
    case_dir: Path,
    hs024: CaBenh,
    runtime_context: RuleContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(container_mod, "get_rule_context", lambda: runtime_context, raising=False)
    service = CaseService(case_dir, RENAL, case_dir / "feedback.jsonl", ai_runner=None, asker=None)
    try:
        result = service._review(hs024)
        assert any(row.yeu_to == 4 for row in result.phat_hien)
        settings = load_settings("test")
        collector = EvidenceCollector(
            None,
            QueryBuilder(settings.retrieval),
            DrugNameIndex.load(ROOT / "data/kb/hoat_chat.json").resolve,
        )
        synthesizer = Synthesizer(
            llm=FakeLLM([{"nhan_dinh": []}]),
            prompt_path=ROOT / "config/prompts/tong_hop.v1.md",
            case_settings=settings.case_context,
            evidence_max_chars=settings.evidence.max_chars,
            max_synthesis_attempts=1,
            model_name="fake-t55f1",
        )
        run = AiReviewer(collector, synthesizer, engine=engine).run(hs024, result)
        assert run.llm.trang_thai == "ok"
        assert [row.phat_hien for row in run.llm.nhan_dinh] == result.phat_hien
        presented = present_ai_result(hs024, result, run)
        assert presented.trang_thai == "xong"
        assert presented.nhan_dinh is not None
        assert any(row.yeu_to.startswith("4.") for row in presented.nhan_dinh.can_chu_y)
    finally:
        service.shutdown()


def test_pipeline_retains_old_rules_and_refreshes_matrix(
    hs024: CaBenh, runtime_context: RuleContext
) -> None:
    old = run_case(hs024, runtime_context.renal_rules)
    result = run_case(
        hs024,
        runtime_context.renal_rules,
        resolver=runtime_context.resolver,
        interactions=runtime_context.interactions,
    )
    expected_legacy = [row for row in old.phat_hien if row.yeu_to != 2]
    assert expected_legacy
    for expected in expected_legacy:
        assert expected in result.phat_hien
    assert any(row.ma_luat == "thuoc_benh_ddinter" for row in result.phat_hien)
    duplicates = [row for row in result.phat_hien if row.yeu_to == 2]
    assert len(duplicates) == 1
    assert duplicates[0].ma_luat == "trung_hoat_chat_khong_co"
    assert duplicates[0].ket_luan == "dat"
    assert "theo 8 nhóm điều trị" in duplicates[0].mo_ta
    assert result.ma_tran_tuong_tac is not None
    assert result.ma_tran_tuong_tac.cap
    empty = hs024.model_copy(
        update={
            "thuoc_dang_dung": [],
            "y_lenh_cho_duyet": hs024.y_lenh_cho_duyet.model_copy(update={"chi_tiet": []}),
        }
    )
    refreshed = run_case(
        empty,
        runtime_context.renal_rules,
        resolver=runtime_context.resolver,
        interactions=runtime_context.interactions,
    )
    assert refreshed.ma_tran_tuong_tac is not None
    assert refreshed.ma_tran_tuong_tac.cap == []
    assert refreshed.ma_tran_tuong_tac.thuoc == []


def test_interaction_failure_keeps_old_findings(
    hs024: CaBenh, runtime_context: RuleContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object) -> None:
        raise ValueError("Lỗi kiểm thử")

    monkeypatch.setattr(interaction, "_evaluate", fail)
    old = run_case(hs024, runtime_context.renal_rules)
    result = run_case(
        hs024,
        runtime_context.renal_rules,
        resolver=runtime_context.resolver,
        interactions=runtime_context.interactions,
    )
    expected_legacy = [row for row in old.phat_hien if row.yeu_to != 2]
    assert expected_legacy
    for expected in expected_legacy:
        assert expected in result.phat_hien
    assert any(row.ma_luat == "thuoc_benh_ddinter" for row in result.phat_hien)
    duplicates = [row for row in result.phat_hien if row.yeu_to == 2]
    assert len(duplicates) == 1
    assert duplicates[0].ma_luat == "trung_hoat_chat_khong_co"
    assert duplicates[0].ket_luan == "dat"
    assert "theo 8 nhóm điều trị" in duplicates[0].mo_ta
    errors = [row for row in result.phat_hien if row.yeu_to == 4]
    assert len(errors) == 1
    assert errors[0].ma_luat == "loi_luat"
    assert errors[0].thong_tin_con_thieu == ["luat_chay_loi"]
    assert result.ma_tran_tuong_tac is None
