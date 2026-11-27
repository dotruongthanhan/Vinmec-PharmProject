"""Kiểm thử hỏi đáp chung (ask_global) chịu được trường liều/đường dùng/tần suất là None."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.container import build_container
from app.domain.models import (
    CaBenh,
    ChiTietYLenh,
    DotDieuTri,
    HoatChat,
    NguoiBenh,
    ThanhPhan,
    Thuoc,
    TinhTrangDiUng,
    YLenh,
)
from app.orchestration.ask import CaseAsker, _format_global_order_line
from app.providers.fakes import FakeLLM
from app.retrieval.query_builder import QueryBuilder

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 11, 16, 8, 0, tzinfo=UTC)
pytestmark = pytest.mark.luong_cu_cung


def _make_case_with_lines(lines: list[ChiTietYLenh], *, tuoi: int | None = 4) -> CaBenh:
    return CaBenh(
        ca_id="CASE-NONE-01",
        mo_ta_ngan="Ca giả lập thiếu liều mỗi lần",
        nguoi_benh=NguoiBenh(nguoi_benh_id="NB-NONE-01", tuoi=tuoi, gioi_tinh="nam"),
        tinh_trang_di_ung=TinhTrangDiUng(
            trang_thai="khong_di_ung_da_hoi",
            nguon="EMR",
            thoi_diem=NOW,
        ),
        dot_dieu_tri=DotDieuTri(
            dot_dieu_tri_id="DT-NONE-01",
            khoa_dieu_tri="Nhi",
            loai_dieu_tri="noi_tru",
            thoi_diem_bat_dau=NOW,
        ),
        y_lenh_cho_duyet=YLenh(
            y_lenh_id="YL-NONE-01",
            khoa_ke_don="Nhi",
            luong_duyet="truc_tiep",
            thoi_diem_ke=NOW,
            chi_tiet=lines,
        ),
        danh_muc_thuoc=[
            Thuoc(
                thuoc_id="T-PARA-SIRO",
                ten_thuoc="Paracetamol 150 mg/5 mL",
                thanh_phan=[ThanhPhan(hoat_chat_id="HC-PARA")],
            ),
        ],
        danh_muc_hoat_chat=[
            HoatChat(
                hoat_chat_id="HC-PARA",
                ten_hoat_chat="Paracetamol",
                ten_quoc_te="acetaminophen",
            ),
        ],
    )


def _make_asker(llm: FakeLLM) -> CaseAsker:
    container = build_container("test")
    return CaseAsker(
        llm=llm,
        retriever=None,
        query_builder=QueryBuilder(container.settings.retrieval),
        resolve_name=lambda _name: [],
        prompt_path=ROOT / "config/prompts/hoi_them.v1.md",
        case_settings=container.settings.case_context,
        evidence_max_chars=container.settings.evidence.max_chars,
        model_name="model-test",
        renal_rules=container.renal_rules,
    )


def test_format_global_order_line_handles_none_and_present_fields() -> None:
    line_missing_dose = ChiTietYLenh(
        chi_tiet_y_lenh_id="CT-1",
        thuoc_id="T-PARA-SIRO",
        lieu_moi_lan=None,
        don_vi_lieu="mg/kg",
        tan_suat="mỗi 6 giờ khi sốt",
        duong_dung="uống",
        bat_dau=NOW,
        trang_thai_dong="pending",
    )
    assert (
        _format_global_order_line(line_missing_dose)
        == "T-PARA-SIRO liều chưa ghi (mg/kg) (mỗi 6 giờ khi sốt, uống)"
    )

    line_all_none = ChiTietYLenh(
        chi_tiet_y_lenh_id="CT-2",
        ten_tu_do="Thuốc thử",
        lieu_moi_lan=None,
        don_vi_lieu=None,
        tan_suat=None,
        duong_dung=None,
        bat_dau=NOW,
        trang_thai_dong="pending",
    )
    assert (
        _format_global_order_line(line_all_none)
        == "Thuốc thử liều chưa ghi (tần suất chưa ghi, đường dùng chưa ghi)"
    )

    line_missing_unit = ChiTietYLenh(
        chi_tiet_y_lenh_id="CT-3",
        ten_tu_do="Thuốc B",
        lieu_moi_lan=500.0,
        don_vi_lieu=None,
        tan_suat=None,
        duong_dung=None,
        bat_dau=NOW,
        trang_thai_dong="pending",
    )
    assert (
        _format_global_order_line(line_missing_unit)
        == "Thuốc B 500 (đơn vị chưa ghi) (tần suất chưa ghi, đường dùng chưa ghi)"
    )

    line_full = ChiTietYLenh(
        chi_tiet_y_lenh_id="CT-4",
        ten_tu_do="Meropenem",
        lieu_moi_lan=1.0,
        don_vi_lieu="g",
        tan_suat="mỗi 8 giờ",
        duong_dung="IV",
        bat_dau=NOW,
        trang_thai_dong="pending",
    )
    assert _format_global_order_line(line_full) == "Meropenem 1 g (mỗi 8 giờ, IV)"


def test_ask_global_with_none_dose_does_not_fail() -> None:
    case = _make_case_with_lines(
        [
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-NONE-01",
                thuoc_id="T-PARA-SIRO",
                lieu_moi_lan=None,
                don_vi_lieu="mg/kg",
                tan_suat="mỗi 6 giờ khi sốt",
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ]
    )
    fake_llm = FakeLLM(
        [
            {
                "pham_vi": "trong",
                "tra_loi": "Xin chào dược sĩ.",
                "trich_dan": [],
            }
        ]
    )
    asker = _make_asker(fake_llm)

    summary = asker._build_global_summary([case], {})
    assert "liều chưa ghi" in summary

    result = asker.ask_global([case], {}, "xin chào")
    assert result.trang_thai == "ok"
    assert result.noi_dung == "Xin chào dược sĩ."
    assert len(fake_llm.calls) == 1
    user_prompt = fake_llm.calls[0]["messages"][1].content
    assert "liều chưa ghi" in user_prompt
