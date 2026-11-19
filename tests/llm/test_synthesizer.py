"""Kiểm thử Synthesizer với FakeLLM cho đủ các nhánh thành công, thử lại và lỗi."""

from pathlib import Path

import pytest

from app.container import build_container
from app.core.errors import ProviderError
from app.core.types import Chunk
from app.llm.synthesizer import Synthesizer
from app.pipeline import run_case
from app.providers.fakes import FakeLLM
from tests.deid_support import temp_id

_ROOT = Path(__file__).resolve().parents[2]
_PROMPT_PATH = _ROOT / "config/prompts/tong_hop.v1.md"


def _sample_chunk() -> Chunk:
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
        phien_ban_nguon="2025-01-01",
        url_goc=None,
        noi_dung_goc=(
            "For creatinine clearance 10 to 25 mL/min, administer one-half the "
            "recommended dose every 12 hours."
        ),
        noi_dung_nhung="[Meropenem | FDA] For creatinine clearance 10 to 25 mL/min...",
    )


def _valid_proposal(
    nhan_xet: str = "Cần xem xét diễn biến creatinin tăng lên 212 umol/L.",
) -> dict:
    return {
        "chi_tiet_y_lenh_id": [temp_id("DEMO-02", "CT-DEMO02-01")],
        "yeu_to": 5,
        "ket_luan": "can_xem",
        "muc_do": "can_luu_y",
        "nhan_xet": nhan_xet,
        "ban_ghi_ids": [temp_id("DEMO-02", "XN-DEMO02-01")],
        "trich_dan": [],
        "thong_tin_con_thieu": [],
        "de_xuat": None,
        "bo_sung_cho_ma_luat": None,
    }


def _make_synthesizer(llm: FakeLLM | None, *, evidence_max_chars: int = 12000) -> Synthesizer:
    container = build_container("test")
    return Synthesizer(
        llm=llm,
        prompt_path=_PROMPT_PATH,
        case_settings=container.settings.case_context,
        evidence_max_chars=evidence_max_chars,
        max_synthesis_attempts=2,
        model_name="deepseek-flash",
    )


def test_synthesizer_without_llm_returns_rule_findings_only() -> None:
    container = build_container("test")
    ca = container.case_repo.get("DEMO-02")
    ket_qua = run_case(ca, container.renal_rules)
    synth = _make_synthesizer(None)

    result = synth.run(ca, ket_qua, [])
    assert result.trang_thai == "khong_co_llm"
    assert result.so_lan_goi == 0
    assert result.phien_ban_prompt == "tong_hop.v1"
    assert [item.phat_hien for item in result.nhan_dinh] == ket_qua.phat_hien
    assert all(item.nguon_goc == "luat" for item in result.nhan_dinh)


def test_synthesizer_retries_with_error_code_and_succeeds() -> None:
    container = build_container("test")
    ca = container.case_repo.get("DEMO-02")
    ket_qua = run_case(ca, container.renal_rules)

    bad_first = _valid_proposal("Giảm xuống 28 ml nhưng thiếu căn cứ.")
    good_passed_first = {
        **_valid_proposal("Creatinin máu 212 umol/L, CrCl 16,0 mL/phút."),
        "yeu_to": 6,
        "ket_luan": "can_xem",
        "muc_do": "nghiem_trong",
        "bo_sung_cho_ma_luat": "lieu_than_can_chinh",
    }
    fixed_second = _valid_proposal("Creatinin tăng từ 150 lên 212 umol/L, cần xem xét.")

    fake_llm = FakeLLM(
        [
            {"nhan_dinh": [good_passed_first, bad_first]},
            {"nhan_dinh": [fixed_second]},
        ]
    )
    synth = _make_synthesizer(fake_llm)
    result = synth.run(ca, ket_qua, [_sample_chunk()])

    assert result.trang_thai == "ok"
    assert result.so_lan_goi == 2
    assert "so_khong_co_nguon:28" in fake_llm.calls[1]["messages"][1].content
    assert any(item.nguon_goc == "ai_da_kiem_chung" for item in result.nhan_dinh)
    assert any(item.dien_giai is not None for item in result.nhan_dinh)
    for call in fake_llm.calls:
        for msg in call["messages"]:
            assert ca.nguoi_benh.nguoi_benh_id not in msg.content


def test_synthesizer_marks_unverified_when_all_attempts_fail() -> None:
    container = build_container("test")
    ca = container.case_repo.get("DEMO-02")
    ket_qua = run_case(ca, container.renal_rules)

    bad = _valid_proposal("Số bịa 28 trong cả hai lần.")
    fake_llm = FakeLLM([{"nhan_dinh": [bad]}, {"nhan_dinh": [bad]}])
    synth = _make_synthesizer(fake_llm)

    result = synth.run(ca, ket_qua, [])
    assert result.trang_thai == "ok"
    assert result.so_lan_goi == 2
    unverified = [item for item in result.nhan_dinh if item.nguon_goc == "ai_chua_kiem_chung"]
    assert len(unverified) == 1
    assert "so_khong_co_nguon:28" in unverified[0].loi_kiem_chung


def test_synthesizer_handles_provider_error_without_raising() -> None:
    container = build_container("test")
    ca = container.case_repo.get("DEMO-02")
    ket_qua = run_case(ca, container.renal_rules)

    synth = _make_synthesizer(FakeLLM([]))
    result = synth.run(ca, ket_qua, [])

    assert result.trang_thai == "loi_llm"
    assert result.so_lan_goi == 1
    assert [item.phat_hien for item in result.nhan_dinh] == ket_qua.phat_hien
    assert result.canh_bao


@pytest.mark.parametrize(
    ("error", "warning"),
    [
        (
            "het_han_muc_token",
            "Bước AI bị cắt vì vượt hạn mức độ dài; đang hiển thị kết quả của bộ luật.",
        ),
        (
            "dau_ra_khong_hop_le",
            "Bước AI gặp lỗi (dau_ra_khong_hop_le); đang hiển thị kết quả của bộ luật.",
        ),
        (
            "HTTP 400: noi dung phan hoi nhay cam",
            "Bước AI gặp lỗi (loi_nha_cung_cap); đang hiển thị kết quả của bộ luật.",
        ),
    ],
)
def test_synthesizer_provider_error_preserves_rules_and_has_safe_warning(
    error: str, warning: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    container = build_container("test")
    ca = container.case_repo.get("DEMO-02")
    ket_qua = run_case(ca, container.renal_rules)
    assert ket_qua.phat_hien
    original_findings = [finding.model_dump() for finding in ket_qua.phat_hien]
    llm = FakeLLM([])

    def fail_with_provider_error(*_args: object) -> dict:
        raise ProviderError(error)

    monkeypatch.setattr(llm, "complete_json", fail_with_provider_error)
    result = _make_synthesizer(llm).run(ca, ket_qua, [])

    assert result.trang_thai == "loi_llm"
    assert result.so_lan_goi == 1
    assert result.canh_bao == [warning]
    assert all(item.nguon_goc == "luat" for item in result.nhan_dinh)
    assert [item.phat_hien.model_dump() for item in result.nhan_dinh] == original_findings
    assert [finding.model_dump() for finding in ket_qua.phat_hien] == original_findings


def test_synthesizer_handles_invalid_schema_as_failure() -> None:
    container = build_container("test")
    ca = container.case_repo.get("DEMO-02")
    ket_qua = run_case(ca, container.renal_rules)

    invalid_payload = {
        "nhan_dinh": [
            {
                "chi_tiet_y_lenh_id": ["CT-DEMO02-01"],
                "ket_luan": "can_xem",
                "muc_do": "can_luu_y",
                "nhan_xet": "Thiếu yeu_to",
                "ban_ghi_ids": ["XN-DEMO02-01"],
                "trich_dan": [],
            }
        ]
    }
    fake_llm = FakeLLM([invalid_payload, invalid_payload])
    synth = _make_synthesizer(fake_llm)
    result = synth.run(ca, ket_qua, [])

    assert result.trang_thai == "dau_ra_khong_hop_le"
    assert result.so_lan_goi == 2
    assert "sai_luoc_do" in result.canh_bao
    assert [item.phat_hien for item in result.nhan_dinh] == ket_qua.phat_hien


def test_synthesizer_blocks_prompt_injection_downgrade_on_demo06() -> None:
    container = build_container("test")
    ca = container.case_repo.get("DEMO-06")
    ket_qua = run_case(ca, container.renal_rules)

    hijacked_dat = {
        "chi_tiet_y_lenh_id": [temp_id("DEMO-06", "CT-DEMO06-01")],
        "yeu_to": 1,
        "ket_luan": "dat",
        "muc_do": None,
        "nhan_xet": "Đơn này đạt, không có dị ứng.",
        "ban_ghi_ids": [temp_id("DEMO-06", "DB-DEMO06-01")],
        "trich_dan": [],
    }
    fake_llm = FakeLLM([{"nhan_dinh": [hijacked_dat]}])
    synth = _make_synthesizer(fake_llm)
    result = synth.run(ca, ket_qua, [])

    assert result.trang_thai == "ok"
    assert [item.phat_hien for item in result.nhan_dinh] == ket_qua.phat_hien
    assert "ai_ha_muc_bi_loai" in result.canh_bao
    assert all(item.nguon_goc == "luat" for item in result.nhan_dinh)
    for call in fake_llm.calls:
        for msg in call["messages"]:
            assert ca.nguoi_benh.nguoi_benh_id not in msg.content


def test_synthesizer_truncates_evidence_at_chunk_boundary() -> None:
    container = build_container("test")
    ca = container.case_repo.get("DEMO-02")
    ket_qua = run_case(ca, container.renal_rules)
    chunk_1 = _sample_chunk()
    chunk_2 = chunk_1.model_copy(update={"doan_trich_id": "DT-MERO-02", "noi_dung_goc": "A" * 500})

    fake_llm = FakeLLM([{"nhan_dinh": []}])
    synth = _make_synthesizer(fake_llm, evidence_max_chars=len(chunk_1.noi_dung_goc) + 10)
    synth.run(ca, ket_qua, [chunk_1, chunk_2])

    user_prompt = fake_llm.calls[0]["messages"][1].content
    assert "[DT-MERO-01] (tầng 3, Dosage and Administration > Renal Impairment)" in user_prompt
    assert "DT-MERO-02" not in user_prompt
