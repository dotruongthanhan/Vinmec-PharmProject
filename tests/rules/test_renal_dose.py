"""Kiểm thử luật yếu tố 6: chỉnh liều theo chức năng thận và ranh giới CrCl."""

from pathlib import Path
from typing import Literal

import pytest

from app.domain.models import (
    CaBenh,
    ChiTietYLenh,
    HoatChat,
    KetQuaXetNghiem,
    SinhHieu,
    ThanhPhan,
    Thuoc,
)
from app.rules.renal_dose import check, load_renal_rules, select_renal_tier
from tests.rules import NOW, make_minimal_case

_RULES_PATH = Path(__file__).resolve().parents[2] / "data" / "kb" / "quy_tac_lieu_than.json"


def _meropenem_case(
    *,
    tuoi: int | None = 75,
    gioi_tinh: Literal["nam", "nu"] | None = "nu",
    sinh_hieu: list[SinhHieu] | None = None,
    xet_nghiem: list[KetQuaXetNghiem] | None = None,
    ten_quoc_te: str | None = "meropenem",
) -> CaBenh:
    """Tạo ca bệnh dùng meropenem phục vụ kiểm thử luật chỉnh liều thận."""
    hc_mero = HoatChat(
        hoat_chat_id="HC-MERO",
        ten_hoat_chat="Meropenem",
        ten_quoc_te=ten_quoc_te,
        nhom_duoc_ly="carbapenem",
    )
    thuoc_mero = Thuoc(
        thuoc_id="T-MERO",
        ten_thuoc="Meropenem 1 g",
        thanh_phan=[ThanhPhan(hoat_chat_id="HC-MERO")],
        la_khang_sinh=True,
    )
    return make_minimal_case(
        tuoi=tuoi,
        gioi_tinh=gioi_tinh,
        sinh_hieu=sinh_hieu,
        xet_nghiem=xet_nghiem,
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-MERO",
                thuoc_id="T-MERO",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[thuoc_mero],
        danh_muc_hoat_chat=[hc_mero],
    )


@pytest.mark.parametrize(
    ("crcl", "expected_adjust", "expected_advice"),
    [
        (50.01, False, "Liều khuyến cáo, mỗi 8 giờ"),
        (50.0, True, "Liều khuyến cáo, mỗi 12 giờ"),
        (25.01, True, "Liều khuyến cáo, mỗi 12 giờ"),
        (25.0, True, "Một nửa liều khuyến cáo, mỗi 12 giờ"),
        (10.0, True, "Một nửa liều khuyến cáo, mỗi 12 giờ"),
        (9.99, True, "Một nửa liều khuyến cáo, mỗi 24 giờ"),
    ],
)
def test_select_renal_tier_boundaries(
    crcl: float,
    expected_adjust: bool,
    expected_advice: str,
) -> None:
    """Kiểm tra bốn điều kiện chọn mức CrCl liên tục không có khe hở ở mọi biên."""
    rules = load_renal_rules(_RULES_PATH)
    mero_rule = rules.quy_tac[0]
    tier = select_renal_tier(crcl, mero_rule)
    assert tier.can_chinh is expected_adjust
    assert tier.khuyen_cao == expected_advice


def test_renal_dose_adjustment_required() -> None:
    """CrCl <= 50 sinh lieu_than_can_chinh, nghiem_trong, đủ 3 căn cứ theo đúng thứ tự."""
    rules = load_renal_rules(_RULES_PATH)
    ca = _meropenem_case(
        tuoi=75,
        gioi_tinh="nu",
        ten_quoc_te="Meropenem",
        sinh_hieu=[
            SinhHieu(
                sinh_hieu_id="SH-50",
                loai="can_nang",
                gia_tri=50.0,
                don_vi="kg",
                thoi_diem_do=NOW,
            ),
        ],
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-212",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=212.0,
                don_vi="umol/L",
                thoi_diem_ket_qua=NOW,
            ),
        ],
    )
    findings = check(ca, rules)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "lieu_than_can_chinh"
    assert finding.yeu_to == 6
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "nghiem_trong"
    assert "16.0" in finding.mo_ta
    assert "Một nửa liều khuyến cáo, mỗi 12 giờ" in finding.mo_ta
    assert [c.loai for c in finding.can_cu] == ["du_lieu", "tinh_toan", "tai_lieu"]
    assert finding.can_cu[0].ban_ghi_id == "XN-212"
    assert finding.can_cu[1].ban_ghi_id == "cockcroft_gault"
    assert "thuc_te" in finding.can_cu[1].mo_ta
    assert finding.can_cu[2].mo_ta == rules.quy_tac[0].nguon


def test_renal_dose_no_adjustment_needed() -> None:
    """CrCl > 50 sinh lieu_than_khong_can_chinh với kết luận dat."""
    rules = load_renal_rules(_RULES_PATH)
    ca = _meropenem_case(
        tuoi=45,
        gioi_tinh="nam",
        sinh_hieu=[
            SinhHieu(
                sinh_hieu_id="SH-70",
                loai="can_nang",
                gia_tri=70.0,
                don_vi="kg",
                thoi_diem_do=NOW,
            ),
        ],
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-80",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=80.0,
                don_vi="umol/L",
                thoi_diem_ket_qua=NOW,
            ),
        ],
    )
    findings = check(ca, rules)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "lieu_than_khong_can_chinh"
    assert finding.ket_luan == "dat"
    assert finding.muc_do == "thong_tin"
    assert [c.loai for c in finding.can_cu] == ["du_lieu", "tinh_toan", "tai_lieu"]


def test_renal_dose_missing_weight() -> None:
    """Thiếu cân nặng sinh lieu_than_thieu_du_lieu có can_nang_kg trong thong_tin_con_thieu."""
    rules = load_renal_rules(_RULES_PATH)
    ca = _meropenem_case(sinh_hieu=[])
    findings = check(ca, rules)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "lieu_than_thieu_du_lieu"
    assert finding.ket_luan == "khong_du_du_lieu"
    assert finding.muc_do is None
    assert "can_nang_kg" in finding.thong_tin_con_thieu


def test_renal_dose_abnormal_creatinine_value_error() -> None:
    """Creatinin 212 mg/dL vượt miền gây ValueError -> lieu_than_so_lieu_bat_thuong."""
    rules = load_renal_rules(_RULES_PATH)
    ca = _meropenem_case(
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-BAD",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=212.0,
                don_vi="mg/dL",
                thoi_diem_ket_qua=NOW,
            ),
        ],
    )
    findings = check(ca, rules)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "lieu_than_so_lieu_bat_thuong"
    assert finding.ket_luan == "khong_du_du_lieu"
    assert finding.muc_do is None
    assert finding.thong_tin_con_thieu == ["so_lieu_hop_le"]
    assert "creatinin" in finding.mo_ta


def test_renal_dose_unlisted_ingredient_returns_empty() -> None:
    """Hoạt chất không có trong bảng luật thận không sinh phát hiện."""
    rules = load_renal_rules(_RULES_PATH)
    ca = make_minimal_case()
    assert check(ca, rules) == []
