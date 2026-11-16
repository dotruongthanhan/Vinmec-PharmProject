"""Kiểm thử luật yếu tố 3: đối chiếu kháng sinh với kết quả nuôi cấy vi sinh."""

from datetime import timedelta
from typing import Literal

import pytest

from app.domain.models import (
    CaBenh,
    ChiTietYLenh,
    HoatChat,
    KhangSinhDo,
    ThanhPhan,
    Thuoc,
    ViSinh,
)
from app.rules.antibiotic import check
from tests.rules import NOW, make_minimal_case


def _antibiotic_case(
    *,
    vi_sinh: list[ViSinh],
    la_khang_sinh: bool = True,
) -> CaBenh:
    """Tạo ca bệnh mẫu có kê kháng sinh Ceftriaxon để kiểm thử luật vi sinh."""
    hc_cef = HoatChat(
        hoat_chat_id="HC-CEF",
        ten_hoat_chat="Ceftriaxon",
        ten_quoc_te="ceftriaxone",
    )
    hc_mero = HoatChat(
        hoat_chat_id="HC-MERO",
        ten_hoat_chat="Meropenem",
        ten_quoc_te="meropenem",
    )
    thuoc = Thuoc(
        thuoc_id="T-CEF",
        ten_thuoc="Ceftriaxon 2 g",
        thanh_phan=[ThanhPhan(hoat_chat_id="HC-CEF")],
        la_khang_sinh=la_khang_sinh,
    )
    return make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-ABX",
                thuoc_id="T-CEF",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        vi_sinh=vi_sinh,
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc_cef, hc_mero],
    )


def test_no_positive_micro_returns_empty() -> None:
    """Không có vi sinh dương tính (rỗng hoặc vi_khuan=None) thì không sinh phát hiện."""
    ca_empty = _antibiotic_case(vi_sinh=[])
    assert check(ca_empty) == []

    ca_negative = _antibiotic_case(
        vi_sinh=[
            ViSinh(
                vi_sinh_id="VS-NEG",
                benh_pham="máu",
                vi_khuan=None,
                thoi_diem_lay_mau=NOW,
            ),
        ],
    )
    assert check(ca_negative) == []


def test_non_antibiotic_drug_returns_empty() -> None:
    """Thuốc không có la_khang_sinh=True không bị xét bởi luật kháng sinh - vi sinh."""
    ca = _antibiotic_case(
        la_khang_sinh=False,
        vi_sinh=[
            ViSinh(
                vi_sinh_id="VS-1",
                benh_pham="nước tiểu",
                vi_khuan="E. coli",
                thoi_diem_lay_mau=NOW,
                khang_sinh_do=[KhangSinhDo(hoat_chat_id="HC-CEF", ket_qua="R")],
            ),
        ],
    )
    assert check(ca) == []


@pytest.mark.parametrize(
    ("ksd_result", "expected_code", "expected_conclusion", "expected_severity"),
    [
        ("S", "khang_sinh_vi_sinh_nhay", "dat", "thong_tin"),
        ("R", "khang_sinh_vi_sinh_khang", "can_xem", "nghiem_trong"),
        ("I", "khang_sinh_vi_sinh_trung_gian", "can_xem", "can_luu_y"),
    ],
)
def test_antibiotic_ksd_outcomes(
    ksd_result: Literal["S", "I", "R"],
    expected_code: str,
    expected_conclusion: str,
    expected_severity: str,
) -> None:
    """Kết quả kháng sinh đồ S/R/I sinh đúng mã luật, kết luận, mức độ và căn cứ."""
    ca = _antibiotic_case(
        vi_sinh=[
            ViSinh(
                vi_sinh_id="VS-1",
                benh_pham="đờm",
                vi_khuan="Klebsiella pneumoniae",
                thoi_diem_lay_mau=NOW,
                khang_sinh_do=[KhangSinhDo(hoat_chat_id="HC-CEF", ket_qua=ksd_result)],
            ),
        ],
    )
    findings = check(ca)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == expected_code
    assert finding.yeu_to == 3
    assert finding.ket_luan == expected_conclusion
    assert finding.muc_do == expected_severity
    assert finding.chi_tiet_y_lenh_id == ["CT-ABX"]
    assert len(finding.can_cu) == 1
    evidence = finding.can_cu[0]
    assert evidence.loai == "du_lieu"
    assert evidence.ban_ghi_id == "VS-1"
    assert "đờm" in evidence.mo_ta
    assert "Klebsiella pneumoniae" in evidence.mo_ta
    assert ksd_result in evidence.mo_ta


def test_antibiotic_missing_ingredient_in_ksd() -> None:
    """Có vi sinh dương tính nhưng thiếu hoạt chất trong KSD -> khong_du_du_lieu."""
    ca = _antibiotic_case(
        vi_sinh=[
            ViSinh(
                vi_sinh_id="VS-OTHER",
                benh_pham="máu",
                vi_khuan="Pseudomonas aeruginosa",
                thoi_diem_lay_mau=NOW,
                khang_sinh_do=[KhangSinhDo(hoat_chat_id="HC-MERO", ket_qua="S")],
            ),
        ],
    )
    findings = check(ca)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "khang_sinh_khong_co_ksd"
    assert finding.ket_luan == "khong_du_du_lieu"
    assert finding.muc_do is None
    assert finding.thong_tin_con_thieu == ["khang_sinh_do"]


def test_antibiotic_selects_latest_sample_time() -> None:
    """Nhiều bản ghi vi sinh cho cùng hoạt chất thì chọn bản có thoi_diem_lay_mau mới nhất."""
    ca = _antibiotic_case(
        vi_sinh=[
            ViSinh(
                vi_sinh_id="VS-OLD",
                benh_pham="nước tiểu",
                vi_khuan="E. coli",
                thoi_diem_lay_mau=NOW - timedelta(days=2),
                khang_sinh_do=[KhangSinhDo(hoat_chat_id="HC-CEF", ket_qua="S")],
            ),
            ViSinh(
                vi_sinh_id="VS-NEW",
                benh_pham="máu",
                vi_khuan="E. coli",
                thoi_diem_lay_mau=NOW,
                khang_sinh_do=[KhangSinhDo(hoat_chat_id="HC-CEF", ket_qua="R")],
            ),
        ],
    )
    findings = check(ca)
    assert len(findings) == 1
    assert findings[0].ma_luat == "khang_sinh_vi_sinh_khang"
    assert findings[0].can_cu[0].ban_ghi_id == "VS-NEW"
