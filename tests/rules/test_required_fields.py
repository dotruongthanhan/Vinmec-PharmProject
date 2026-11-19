"""Kiểm thử luật yếu tố 7: y lệnh thuốc thiếu trường bắt buộc."""

from typing import Literal

from app.domain.models import ChiTietYLenh
from app.rules.required_fields import check
from tests.rules import NOW, make_minimal_case


def _line(
    *,
    chi_tiet_y_lenh_id: str = "CT-1",
    loai_san_pham: Literal["thuoc", "tpcn", "dinh_duong", "khac"] = "thuoc",
    lieu_moi_lan: float | None = 500.0,
    don_vi_lieu: str | None = "mg",
    duong_dung: str | None = "Uống",
    tan_suat: str | None = "2 lần/ngày",
    so_lan_moi_ngay: int | None = None,
    khoang_cach_gio: float | None = None,
) -> ChiTietYLenh:
    """Tạo dòng chi tiết y lệnh phục vụ kiểm thử trường bắt buộc."""
    return ChiTietYLenh(
        chi_tiet_y_lenh_id=chi_tiet_y_lenh_id,
        thuoc_id="T-DEFAULT",
        loai_san_pham=loai_san_pham,
        lieu_moi_lan=lieu_moi_lan,
        don_vi_lieu=don_vi_lieu,
        duong_dung=duong_dung,
        tan_suat=tan_suat,
        so_lan_moi_ngay=so_lan_moi_ngay,
        khoang_cach_gio=khoang_cach_gio,
        bat_dau=NOW,
        trang_thai_dong="active",
    )


def test_required_fields_complete_order_returns_empty() -> None:
    """Dòng thuốc có đủ trường bắt buộc không sinh phát hiện."""
    ca = make_minimal_case(chi_tiet=[_line()])
    assert check(ca) == []


def test_required_fields_missing_each_field_individually() -> None:
    """Thiếu từng trường (hoặc chuỗi rỗng sau strip) đều sinh đúng một phát hiện can_xem."""
    cases = [
        ({"lieu_moi_lan": None}, "lieu_moi_lan", "liều mỗi lần"),
        ({"don_vi_lieu": "   "}, "don_vi_lieu", "đơn vị liều"),
        ({"duong_dung": ""}, "duong_dung", "đường dùng"),
        (
            {"tan_suat": "  ", "so_lan_moi_ngay": None, "khoang_cach_gio": None},
            "tan_suat",
            "tần suất",
        ),
    ]
    for overrides, expected_field, expected_label in cases:
        ca = make_minimal_case(chi_tiet=[_line(**overrides)])
        findings = check(ca)
        assert len(findings) == 1
        finding = findings[0]
        assert finding.ma_luat == "y_lenh_thieu_truong"
        assert finding.yeu_to == 7
        assert finding.ket_luan == "can_xem"
        assert finding.muc_do == "can_luu_y"
        assert finding.chi_tiet_y_lenh_id == ["CT-1"]
        assert expected_label in finding.mo_ta
        assert finding.thong_tin_con_thieu == [expected_field]
        assert len(finding.can_cu) == 1
        assert finding.can_cu[0].loai == "du_lieu"
        assert finding.can_cu[0].ban_ghi_id == "CT-1"


def test_required_fields_multiple_missing_returns_single_finding() -> None:
    """Thiếu nhiều trường trên cùng một dòng chỉ sinh một phát hiện liệt kê đủ trường."""
    ca = make_minimal_case(
        chi_tiet=[
            _line(
                lieu_moi_lan=None,
                don_vi_lieu=None,
                duong_dung=None,
                tan_suat=None,
            )
        ]
    )
    findings = check(ca)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.thong_tin_con_thieu == [
        "lieu_moi_lan",
        "don_vi_lieu",
        "duong_dung",
        "tan_suat",
    ]
    for label in ("liều mỗi lần", "đơn vị liều", "đường dùng", "tần suất"):
        assert label in finding.mo_ta


def test_required_fields_frequency_satisfied_by_interval_or_daily_count() -> None:
    """Chỉ có khoang_cach_gio hoặc so_lan_moi_ngay được tính là đủ thông tin tần suất."""
    ca_interval = make_minimal_case(
        chi_tiet=[_line(tan_suat=None, so_lan_moi_ngay=None, khoang_cach_gio=8.0)]
    )
    ca_count = make_minimal_case(
        chi_tiet=[_line(tan_suat=None, so_lan_moi_ngay=3, khoang_cach_gio=None)]
    )
    assert check(ca_interval) == []
    assert check(ca_count) == []


def test_required_fields_non_drug_product_is_ignored() -> None:
    """Dòng có loai_san_pham='tpcn' được bỏ qua dù thiếu các trường liều và đường dùng."""
    ca = make_minimal_case(
        chi_tiet=[
            _line(
                loai_san_pham="tpcn",
                lieu_moi_lan=None,
                don_vi_lieu=None,
                duong_dung=None,
                tan_suat=None,
            )
        ]
    )
    assert check(ca) == []


def test_required_fields_current_medication_is_ignored() -> None:
    """Chỉ kiểm tra dòng chờ duyệt, bỏ qua thuốc đang dùng."""
    ca = make_minimal_case(
        chi_tiet=[_line(chi_tiet_y_lenh_id="CT-OK")],
        thuoc_dang_dung=[
            _line(
                chi_tiet_y_lenh_id="CT-CUR-MISSING",
                lieu_moi_lan=None,
                don_vi_lieu=None,
                duong_dung=None,
                tan_suat=None,
            )
        ],
    )
    assert check(ca) == []
