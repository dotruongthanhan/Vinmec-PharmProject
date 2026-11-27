"""Kiểm thử thay thế placeholder một lượt trong dựng prompt hỏi đáp (L7)."""

from pathlib import Path

import pytest

from app.container import build_container
from app.core.types import Chunk, RetrievalQuery, ScoredChunk
from app.domain.loader import load_case
from app.kb.names import DrugNameIndex
from app.llm.prompt_loader import load_prompt
from app.orchestration.ask import CaseAsker, _build_messages
from app.providers.fakes import FakeLLM
from app.retrieval.query_builder import QueryBuilder
from tests.deid_support import temp_id

ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = ROOT / "config/prompts/hoi_them.v1.md"
pytestmark = pytest.mark.luong_cu_cung


class _StaticRetriever:
    """Bộ truy xuất giả trả về đúng một đoạn nguồn định danh rõ."""

    def __init__(self, chunk: Chunk) -> None:
        self._chunk = chunk

    def retrieve(self, query: RetrievalQuery) -> list[ScoredChunk]:
        del query
        return [ScoredChunk(chunk=self._chunk, diem=0.95, nguon_diem="xep_hang_lai")]


def test_build_messages_single_pass_keeps_literal_placeholders_in_case_text() -> None:
    _, template = load_prompt(PROMPT_PATH)
    question = "CÂU_HỎI_THẬT_DUY_NHẤT"
    evidence = "[DT-1] ĐOẠN_NGUỒN_THẬT_DUY_NHẤT"
    history = "- Dược sĩ: LỊCH_SỬ_THẬT_DUY_NHẤT"
    prev_error = "LỖI_CŨ_THẬT_DUY_NHẤT"
    case_text = "Ghi chú chứa {{cau_hoi}} và {{doan_nguon}} cùng {{lich_su}} và {{loi_lan_truoc}}."

    messages = _build_messages(
        template,
        van_ban_ca=case_text,
        doan_nguon=evidence,
        lich_su=history,
        cau_hoi=question,
        loi_lan_truoc=prev_error,
    )

    user_prompt = messages[1].content
    case_section = user_prompt.split("<<<DU_LIEU_BENH_AN", 1)[1].split("DU_LIEU_BENH_AN>>>", 1)[0]
    question_section = user_prompt.split("<<<CAU_HOI", 1)[1].split("CAU_HOI>>>", 1)[0]

    assert "{{cau_hoi}}" in case_section
    assert "{{doan_nguon}}" in case_section
    assert "{{lich_su}}" in case_section
    assert "{{loi_lan_truoc}}" in case_section
    assert question not in case_section
    assert "ĐOẠN_NGUỒN_THẬT_DUY_NHẤT" not in case_section
    assert user_prompt.count(question) == 1
    assert question in question_section


def test_build_messages_fallback_handles_backslashes_without_rescanning() -> None:
    template = "Ca:\n{{van_ban_ca}}\nNguồn:\n{{doan_nguon}}\nHỏi:\n{{cau_hoi}}"
    messages = _build_messages(
        template,
        van_ban_ca=r"Văn bản {{cau_hoi}} {{doan_nguon}} \1 \g<1>",
        doan_nguon="NOI_DUNG_NGUON",
        lich_su="(không có)",
        cau_hoi="CAU_HOI_CHINH",
        loi_lan_truoc="Không có.",
    )
    expected = (
        "Ca:\n"
        r"Văn bản {{cau_hoi}} {{doan_nguon}} \1 \g<1>"
        "\nNguồn:\nNOI_DUNG_NGUON\nHỏi:\nCAU_HOI_CHINH"
    )
    assert messages[1].content == expected


def test_case_asker_preserves_placeholders_inside_case_note_in_final_prompt() -> None:
    base_case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    modified_note = base_case.dien_bien[0].model_copy(
        update={"noi_dung": "Ghi chú lâm sàng có {{cau_hoi}} và {{doan_nguon}} để kiểm tra."}
    )
    case = base_case.model_copy(update={"dien_bien": [modified_note]})
    chunk = Chunk(
        doan_trich_id="DT-MERO-SINGLE",
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
        noi_dung_goc="NOI_DUNG_NGUON_RIENG_BIET_123",
        noi_dung_nhung="NOI_DUNG_NGUON_RIENG_BIET_123",
    )
    fake_llm = FakeLLM(
        [
            {
                "pham_vi": "trong",
                "tra_loi": "Creatinin máu 212 umol/L [1].",
                "trich_dan": [
                    {
                        "so": 1,
                        "loai": "du_lieu_ca",
                        "ma": temp_id("DEMO-02", "XN-DEMO02-01"),
                        "trich_nguyen_van": None,
                    }
                ],
            }
        ]
    )
    container = build_container("test")
    names = DrugNameIndex.load(ROOT / "data/kb/hoat_chat.json")
    asker = CaseAsker(
        llm=fake_llm,
        retriever=_StaticRetriever(chunk),
        query_builder=QueryBuilder(container.settings.retrieval),
        resolve_name=names.resolve,
        prompt_path=PROMPT_PATH,
        case_settings=container.settings.case_context,
        evidence_max_chars=container.settings.evidence.max_chars,
        model_name="model-test",
        renal_rules=container.renal_rules,
    )

    question = "CÂU_HỎI_LÂM_SÀNG_CẦN_TRẢ_LỜI?"
    result = asker.ask(case, question)
    assert result.trang_thai == "ok"

    user_prompt = fake_llm.calls[0]["messages"][1].content
    case_block = user_prompt.split("<<<DU_LIEU_BENH_AN", 1)[1].split("DU_LIEU_BENH_AN>>>", 1)[0]
    evidence_block = user_prompt.split("<<<DOAN_NGUON", 1)[1].split("DOAN_NGUON>>>", 1)[0]
    question_block = user_prompt.split("<<<CAU_HOI", 1)[1].split("CAU_HOI>>>", 1)[0]

    assert "{{cau_hoi}}" in case_block
    assert "{{doan_nguon}}" in case_block
    assert question not in case_block
    assert "NOI_DUNG_NGUON_RIENG_BIET_123" not in case_block
    assert "NOI_DUNG_NGUON_RIENG_BIET_123" in evidence_block
    assert user_prompt.count(question) == 1
    assert question in question_block
