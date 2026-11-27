"""Kiểm thử T48 ở bước hỏi thêm: che theo trường, mã tạm, khôi phục và đóng an toàn."""

import json
from pathlib import Path

import pytest

from app.container import build_container
from app.domain.loader import load_case
from app.domain.models import CaBenh
from app.llm.schema import KetQuaLLM, NhanDinhCuoi, NhanDinhDeXuat, TrichDanNguon
from app.orchestration.ai_review import AiRunResult
from app.pipeline import run_case
from app.providers.fakes import FakeLLM
from tests.deid_support import temp_id
from tests.orchestration.test_ask import _make_asker, _sample_chunk

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "data/mock/demo"
pytestmark = pytest.mark.luong_cu_cung
NAME = json.loads((DEMO_DIR / "DEMO-02.json").read_text(encoding="utf-8"))["hanh_chinh"]["ho_ten"]
LAB = "XN-DEMO02-01"
LINE = "CT-DEMO02-01"


def _prompt(llm: FakeLLM, index: int = 0) -> str:
    return "\n".join(message.content for message in llm.calls[index]["messages"])


def _answer(text: str, record: str | None = None, kind: str = "du_lieu_ca") -> dict:
    citations = [{"so": 1, "loai": kind, "ma": record, "trich_nguyen_van": None}]
    return {"pham_vi": "trong", "tra_loi": text, "trich_dan": citations if record else []}


def test_question_history_and_case_text_are_masked_by_field_and_restored_in_reply() -> None:
    case = load_case(DEMO_DIR / "DEMO-02.json")
    llm = FakeLLM(
        [_answer("Người bệnh [TEN_1] có creatinin 212 umol/L [1].", temp_id("DEMO-02", LAB))]
    )

    result = _make_asker(llm).ask(
        case,
        f"{NAME} có cần chỉnh liều không? Mã NB-DEMO-02",
        lich_su=[("nguoi_dung", "Hôm qua chị Thị 62 hỏi, sđt 0900000062, thẻ GD4010000000062")],
    )

    prompt = _prompt(llm)
    for secret in (NAME, "NB-DEMO-02", "0900000062", "GD4010000000062", LAB, LINE):
        assert secret not in prompt
    assert result.trang_thai == "ok"
    assert result.noi_dung == f"Người bệnh {NAME} có creatinin 212 umol/L [1]."
    assert result.trich_dan[0].ban_ghi_id == LAB
    assert "[TEN_" not in result.noi_dung


def test_ai_blocks_are_remasked_and_use_temp_ids_even_when_ai_text_holds_real_identity() -> None:
    container = build_container("test")
    case = container.case_repo.get("DEMO-02")
    rule_result = run_case(case, container.renal_rules)
    target = rule_result.phat_hien[0]
    target_id = f"{target.ma_luat}|{','.join(sorted(target.chi_tiet_y_lenh_id))}"
    explanation = NhanDinhDeXuat(
        chi_tiet_y_lenh_id=list(target.chi_tiet_y_lenh_id),
        yeu_to=target.yeu_to,
        ket_luan="can_xem",
        muc_do="nghiem_trong",
        nhan_xet=f"Với {NAME}, CrCl 16,0 mL/phút cần giảm nửa liều (xem {LAB}).",
        ban_ghi_ids=[LAB],
        trich_dan=[
            TrichDanNguon(
                doan_trich_id="DT-AI-01",
                trich_nguyen_van="administer one-half the recommended dose.",
            )
        ],
    )
    ai_run = AiRunResult(
        llm=KetQuaLLM(
            trang_thai="ok",
            nhan_dinh=[
                NhanDinhCuoi(nguon_goc="luat", phat_hien=target, dien_giai=explanation),
                *[NhanDinhCuoi(nguon_goc="luat", phat_hien=ph) for ph in rule_result.phat_hien[1:]],
            ],
            so_lan_goi=1,
            canh_bao=[],
            phien_ban_prompt="tong_hop.v1",
            mo_hinh="model-test",
        ),
        doan=[_sample_chunk("DT-AI-01", "administer one-half the recommended dose.")],
        canh_bao=[],
        thoi_gian_ms=1.0,
    )
    llm = FakeLLM([_answer("CrCl 16,0 mL/phút theo bộ luật [1].", "cockcroft_gault", "tinh_toan")])

    result = _make_asker(llm).ask(
        case,
        "Giải thích nhận định này",
        ket_qua=rule_result,
        ai_result=ai_run,
        nhan_dinh_id=target_id,
    )

    prompt = _prompt(llm)
    assert result.trang_thai == "ok"
    assert "NHẬN ĐỊNH ĐANG ĐƯỢC HỎI (ƯU TIÊN)" in prompt
    assert NAME not in prompt
    assert LAB not in prompt and LINE not in prompt
    assert f"{target.ma_luat}|{temp_id('DEMO-02', LINE)}" in prompt


def test_case_with_record_id_citation_in_prose_is_restored_to_real_id() -> None:
    case = load_case(DEMO_DIR / "DEMO-02.json")
    lab = temp_id("DEMO-02", LAB)
    llm = FakeLLM([_answer(f"Creatinin 212 umol/L (bản ghi {lab}) [1].", lab)])

    result = _make_asker(llm).ask(case, "Creatinin của ca này?")

    assert result.trang_thai == "ok"
    assert result.noi_dung == f"Creatinin 212 umol/L (bản ghi {LAB}) [1]."
    assert result.trich_dan[0].ban_ghi_id == LAB


def test_real_record_id_from_llm_is_rejected_because_only_temp_ids_were_sent() -> None:
    case = load_case(DEMO_DIR / "DEMO-02.json")
    llm = FakeLLM(
        [_answer("Creatinin 212 umol/L [1].", LAB), _answer("Creatinin 212 umol/L [1].", LAB)]
    )

    result = _make_asker(llm).ask(case, "Creatinin của ca này?")

    assert result.trang_thai == "khong_co_nguon"
    assert "unknown_record_id" in llm.calls[1]["messages"][1].content


def test_identifier_lookup_failure_keeps_asking_with_pattern_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.deid.known import IdentifierLookupError

    def fail(_case: CaBenh) -> list:
        raise IdentifierLookupError("không đọc được")

    monkeypatch.setattr("app.llm.case_context.known_identifiers", fail)
    case = load_case(DEMO_DIR / "DEMO-02.json")
    llm = FakeLLM([_answer("Người bệnh [TEN_1] có creatinin 212 umol/L.")])

    result = _make_asker(llm).ask(case, "BS Trần Văn Bình hỏi sđt 0912 345 678 mã DEMO-02")

    prompt = _prompt(llm)
    assert result.trang_thai in {"ok", "khong_co_nguon"}
    for leaked in ("Trần Văn Bình", "0912 345 678", "DEMO-02"):
        assert leaked not in prompt


def test_global_question_masks_case_codes_in_summary_and_restores_them_in_reply() -> None:
    container = build_container("test")
    cases = [load_case(path) for path in sorted(DEMO_DIR.glob("DEMO-0[1-3].json"))]
    results = {case.ca_id: run_case(case, container.renal_rules) for case in cases}
    llm = FakeLLM([_answer("Ca [MA_2] cần xem lại liều; BS [TEN_1] quan tâm.")])

    result = _make_asker(llm).ask_global(
        cases, results, "Ca DEMO-02 có gì cần xem? BS Trần Văn Bình hỏi", lich_su=[]
    )

    prompt = _prompt(llm)
    for case in cases:
        assert case.ca_id not in prompt
        assert case.y_lenh_cho_duyet.y_lenh_id not in prompt
    assert "Trần Văn Bình" not in prompt
    assert result.trang_thai == "ok"
    assert result.noi_dung == "Ca DEMO-02 cần xem lại liều; BS [TEN_1] quan tâm."


def test_global_restores_two_case_ids_without_restoring_name() -> None:
    container = build_container("test")
    cases = [load_case(path) for path in sorted(DEMO_DIR.glob("DEMO-0[1-2].json"))]
    results = {case.ca_id: run_case(case, container.renal_rules) for case in cases}
    llm = FakeLLM([_answer("[MA_1], [MA_2], [TEN_1]")])
    result = _make_asker(llm).ask_global(
        cases, results, "DEMO-01 DEMO-02 BS Tr\u1ea7n V\u0103n B\u00ecnh?"
    )
    assert result.trang_thai == "ok"
    assert result.noi_dung == "DEMO-01, DEMO-02, [TEN_1]"


def test_global_restores_cases_from_summary_without_question_ids() -> None:
    container = build_container("test")
    cases = [load_case(path) for path in sorted(DEMO_DIR.glob("DEMO-0[1-2].json"))]
    results = {case.ca_id: run_case(case, container.renal_rules) for case in cases}
    llm = FakeLLM(
        [_answer("Ca liên quan đến warfarin là ca [MA_1] và ca [MA_2]. [TEN_1] [SDT_1] [MA_3]")]
    )
    asker = container.agentic_asker
    asker._llm = llm
    asker._global_asker = _make_asker(llm)
    result = asker.ask_global(cases, results, "Những ca nào? Giả Lập Sao, 0900000000, NB-TEST")
    assert "DEMO-01" in result.noi_dung
    assert "DEMO-02" in result.noi_dung
    assert "[MA_" not in result.noi_dung
    assert "[đã che]" in result.noi_dung
    assert "Giả Lập Sao" not in result.noi_dung
    assert "0900000000" not in result.noi_dung
    assert "NB-TEST" not in result.noi_dung
