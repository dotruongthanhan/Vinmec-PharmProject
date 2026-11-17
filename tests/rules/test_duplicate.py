"""Kiểm thử luật yếu tố 2: phát hiện trùng hoạt chất trong các dòng thuốc đang hiệu lực."""

from app.domain.models import ChiTietYLenh, HoatChat, ThanhPhan, Thuoc
from app.rules.duplicate import check
from tests.rules import NOW, make_minimal_case


def test_duplicate_ingredient_with_active_current_medication() -> None:
    """Trùng hoạt chất giữa dòng chờ duyệt và thuốc đang dùng active -> can_xem."""
    ca = make_minimal_case(
        thuoc_dang_dung=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-CUR",
                thuoc_id="T-DEFAULT",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
    )
    findings = check(ca)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "trung_hoat_chat"
    assert finding.yeu_to == 2
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "can_luu_y"
    assert finding.chi_tiet_y_lenh_id == ["CT-1", "CT-CUR"]


def test_duplicate_ingredient_with_pending_current_medication() -> None:
    """Thuốc đang dùng có trang_thai_dong='pending' vẫn được tính vào dòng đang hiệu lực."""
    ca = make_minimal_case(
        thuoc_dang_dung=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-PEND",
                thuoc_id="T-DEFAULT",
                bat_dau=NOW,
                trang_thai_dong="pending",
            ),
        ],
    )
    findings = check(ca)
    assert len(findings) == 1
    assert findings[0].ma_luat == "trung_hoat_chat"
    assert findings[0].chi_tiet_y_lenh_id == ["CT-1", "CT-PEND"]


def test_duplicate_discontinued_current_medication_is_ignored() -> None:
    """Thuốc đang dùng đã discontinued không bị tính trùng hoạt chất."""
    ca = make_minimal_case(
        thuoc_dang_dung=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-STOP",
                thuoc_id="T-DEFAULT",
                bat_dau=NOW,
                trang_thai_dong="discontinued",
            ),
        ],
    )
    findings = check(ca)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "trung_hoat_chat_khong_co"
    assert finding.ket_luan == "dat"
    assert finding.muc_do == "thong_tin"


def test_duplicate_within_pending_lines() -> None:
    """Hai dòng trong cùng y lệnh chờ duyệt chứa cùng hoạt chất vẫn báo trùng."""
    hc_para = HoatChat(hoat_chat_id="HC-PARA", ten_hoat_chat="Paracetamol")
    t1 = Thuoc(
        thuoc_id="T-1",
        ten_thuoc="Paracetamol 500 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="HC-PARA")],
    )
    t2 = Thuoc(
        thuoc_id="T-2",
        ten_thuoc="Efferalgan 500 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="HC-PARA")],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-1",
                thuoc_id="T-1",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-2",
                thuoc_id="T-2",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[t1, t2],
        danh_muc_hoat_chat=[hc_para],
    )
    findings = check(ca)
    assert len(findings) == 1
    assert findings[0].ma_luat == "trung_hoat_chat"
    assert findings[0].chi_tiet_y_lenh_id == ["CT-1", "CT-2"]


def test_duplicate_only_among_current_meds_not_in_pending_returns_dat() -> None:
    """Hai thuốc đang dùng trùng nhau nhưng không liên quan dòng đang xét -> không báo trùng."""
    hc_para = HoatChat(hoat_chat_id="HC-PARA", ten_hoat_chat="Paracetamol")
    hc_amlo = HoatChat(hoat_chat_id="HC-AMLO", ten_hoat_chat="Amlodipin")
    t_para = Thuoc(
        thuoc_id="T-PARA",
        ten_thuoc="Paracetamol 500 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="HC-PARA")],
    )
    t_amlo = Thuoc(
        thuoc_id="T-AMLO",
        ten_thuoc="Amlodipin 5 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="HC-AMLO")],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-AMLO",
                thuoc_id="T-AMLO",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        thuoc_dang_dung=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-P1",
                thuoc_id="T-PARA",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-P2",
                thuoc_id="T-PARA",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[t_para, t_amlo],
        danh_muc_hoat_chat=[hc_para, hc_amlo],
    )
    findings = check(ca)
    assert len(findings) == 1
    assert findings[0].ma_luat == "trung_hoat_chat_khong_co"
    assert findings[0].ket_luan == "dat"
