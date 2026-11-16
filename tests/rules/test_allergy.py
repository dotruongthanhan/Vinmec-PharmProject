"""Kiểm thử luật yếu tố 1: dị ứng thuốc, dị ứng chéo và sản phẩm gõ tay."""

from app.domain.models import ChiTietYLenh, DiUng, HoatChat, ThanhPhan, Thuoc
from app.rules.allergy import check
from tests.rules import NOW, make_minimal_case


def test_allergy_unknown_status_returns_missing_data() -> None:
    """Trạng thái chua_co_thong_tin trả về khong_du_du_lieu gắn mọi dòng đang xét."""
    ca = make_minimal_case(
        trang_thai_di_ung="chua_co_thong_tin",
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-1",
                thuoc_id="T-DEFAULT",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-2",
                ten_tu_do="Sản phẩm gõ tay",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
    )
    findings = check(ca)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "di_ung_thieu_thong_tin"
    assert finding.yeu_to == 1
    assert finding.ket_luan == "khong_du_du_lieu"
    assert finding.muc_do is None
    assert finding.chi_tiet_y_lenh_id == ["CT-1", "CT-2"]
    assert finding.thong_tin_con_thieu == ["tinh_trang_di_ung"]


def test_allergy_none_reported_returns_dat() -> None:
    """Trạng thái khong_di_ung_da_hoi trả về 1 phát hiện dat gắn mọi dòng đang xét."""
    ca = make_minimal_case(trang_thai_di_ung="khong_di_ung_da_hoi")
    findings = check(ca)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "di_ung_khong_co"
    assert finding.yeu_to == 1
    assert finding.ket_luan == "dat"
    assert finding.muc_do == "thong_tin"
    assert finding.chi_tiet_y_lenh_id == ["CT-1"]


def test_allergy_exact_ingredient_match() -> None:
    """Trùng hoat_chat_id với dị ứng thuốc sinh di_ung_trung_hoat_chat mức nghiem_trong."""
    hc_amox = HoatChat(
        hoat_chat_id="HC-AMOX",
        ten_hoat_chat="Amoxicillin",
        nhom_duoc_ly="penicillin",
    )
    thuoc_amox = Thuoc(
        thuoc_id="T-AMOX",
        ten_thuoc="Amoxicillin 500 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="HC-AMOX")],
    )
    ca = make_minimal_case(
        trang_thai_di_ung="co_di_ung",
        di_ung=[
            DiUng(
                di_ung_id="DU-1",
                tac_nhan="Amoxicillin",
                loai_tac_nhan="thuoc",
                hoat_chat_id="HC-AMOX",
                nhom_duoc_ly="penicillin",
                phan_ung="Sốc phản vệ",
            ),
        ],
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-AMOX",
                thuoc_id="T-AMOX",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[thuoc_amox],
        danh_muc_hoat_chat=[hc_amox],
    )
    findings = check(ca)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "di_ung_trung_hoat_chat"
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "nghiem_trong"
    assert finding.chi_tiet_y_lenh_id == ["CT-AMOX"]
    assert len(finding.can_cu) == 1
    assert finding.can_cu[0].loai == "du_lieu"
    assert finding.can_cu[0].ban_ghi_id == "DU-1"
    assert "Amoxicillin" in finding.can_cu[0].mo_ta
    assert "Sốc phản vệ" in finding.can_cu[0].mo_ta


def test_allergy_same_group_match_case_and_whitespace_insensitive() -> None:
    """Cùng nhom_duoc_ly không phân biệt hoa thường hay khoảng trắng đầu cuối -> can_xem."""
    hc_pen = HoatChat(
        hoat_chat_id="HC-PEN",
        ten_hoat_chat="Penicillin",
        nhom_duoc_ly="Penicillin",
    )
    hc_amox = HoatChat(
        hoat_chat_id="HC-AMOX",
        ten_hoat_chat="Amoxicillin",
        nhom_duoc_ly=" penicillin ",
    )
    thuoc_amox = Thuoc(
        thuoc_id="T-AMOX",
        ten_thuoc="Amoxicillin 500 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="HC-AMOX")],
    )
    ca = make_minimal_case(
        trang_thai_di_ung="co_di_ung",
        di_ung=[
            DiUng(
                di_ung_id="DU-1",
                tac_nhan="Penicillin",
                loai_tac_nhan="thuoc",
                hoat_chat_id="HC-PEN",
                nhom_duoc_ly="PENICILLIN",
                phan_ung="Mày đay",
            ),
        ],
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-AMOX",
                thuoc_id="T-AMOX",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[thuoc_amox],
        danh_muc_hoat_chat=[hc_pen, hc_amox],
    )
    findings = check(ca)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "di_ung_cung_nhom"
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "nghiem_trong"
    assert finding.can_cu[0].ban_ghi_id == "DU-1"


def test_allergy_exact_match_takes_precedence_over_same_group() -> None:
    """Một cặp (dòng, dị ứng) chỉ sinh một phát hiện, ưu tiên trùng hoạt chất."""
    hc_amox = HoatChat(
        hoat_chat_id="HC-AMOX",
        ten_hoat_chat="Amoxicillin",
        nhom_duoc_ly="penicillin",
    )
    hc_ampi = HoatChat(
        hoat_chat_id="HC-AMPI",
        ten_hoat_chat="Ampicillin",
        nhom_duoc_ly="penicillin",
    )
    thuoc_combo = Thuoc(
        thuoc_id="T-COMBO",
        ten_thuoc="Amoxicillin + Ampicillin",
        thanh_phan=[
            ThanhPhan(hoat_chat_id="HC-AMOX"),
            ThanhPhan(hoat_chat_id="HC-AMPI"),
        ],
    )
    ca = make_minimal_case(
        trang_thai_di_ung="co_di_ung",
        di_ung=[
            DiUng(
                di_ung_id="DU-1",
                tac_nhan="Amoxicillin",
                loai_tac_nhan="thuoc",
                hoat_chat_id="HC-AMOX",
                nhom_duoc_ly="penicillin",
                phan_ung="Phát ban",
            ),
        ],
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-COMBO",
                thuoc_id="T-COMBO",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[thuoc_combo],
        danh_muc_hoat_chat=[hc_amox, hc_ampi],
    )
    findings = check(ca)
    assert len(findings) == 1
    assert findings[0].ma_luat == "di_ung_trung_hoat_chat"


def test_allergy_no_match_returns_dat() -> None:
    """Có dị ứng nhưng không dòng nào khớp sinh di_ung_khong_khop (dat)."""
    ca = make_minimal_case(
        trang_thai_di_ung="co_di_ung",
        di_ung=[
            DiUng(
                di_ung_id="DU-FOOD",
                tac_nhan="Tôm",
                loai_tac_nhan="thuc_an",
                nhom_duoc_ly=None,
                phan_ung="Ngứa",
            ),
        ],
    )
    findings = check(ca)
    assert len(findings) == 1
    assert findings[0].ma_luat == "di_ung_khong_khop"
    assert findings[0].ket_luan == "dat"
    assert findings[0].muc_do == "thong_tin"


def test_allergy_free_text_product_when_co_di_ung() -> None:
    """Dòng không có thuoc_id khi trạng thái co_di_ung sinh di_ung_san_pham_khong_ro."""
    ca = make_minimal_case(
        trang_thai_di_ung="co_di_ung",
        di_ung=[
            DiUng(
                di_ung_id="DU-1",
                tac_nhan="Penicillin",
                loai_tac_nhan="thuoc",
                nhom_duoc_ly="penicillin",
                phan_ung="Mày đay",
            ),
        ],
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-FREE",
                thuoc_id=None,
                ten_tu_do="Thuốc tự nhập chưa mã hóa",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
    )
    findings = check(ca)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "di_ung_san_pham_khong_ro"
    assert finding.ket_luan == "khong_du_du_lieu"
    assert finding.muc_do is None
    assert finding.chi_tiet_y_lenh_id == ["CT-FREE"]
    assert finding.thong_tin_con_thieu == ["thanh_phan_san_pham"]
