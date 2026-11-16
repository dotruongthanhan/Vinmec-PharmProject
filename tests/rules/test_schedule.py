"""Kiểm thử luật yếu tố 7: kiểm tra lịch dùng dự kiến so với tần suất kê."""

from datetime import timedelta

from app.domain.models import CaBenh, ChiTietYLenh, LichDung
from app.rules.schedule import check
from tests.rules import NOW, make_minimal_case


def _schedule_case(
    *,
    offsets_hours: list[float],
    so_lan_moi_ngay: int | None = None,
    khoang_cach_gio: float | None = None,
    tan_suat: str | None = None,
) -> CaBenh:
    """Tạo ca bệnh với một dòng thuốc có lịch dùng theo danh sách độ lệch giờ."""
    lich = [
        LichDung(
            thoi_diem_du_kien=NOW + timedelta(hours=offset),
            lieu=50.0,
            don_vi="mg",
        )
        for offset in offsets_hours
    ]
    return make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-SCH",
                thuoc_id="T-DEFAULT",
                tan_suat=tan_suat,
                so_lan_moi_ngay=so_lan_moi_ngay,
                khoang_cach_gio=khoang_cach_gio,
                bat_dau=NOW,
                trang_thai_dong="active",
                lich_dung=lich,
            ),
        ],
    )


def test_schedule_empty_or_single_entry_returns_empty() -> None:
    """Lịch dùng rỗng hoặc chỉ có 1 mốc không sinh phát hiện."""
    assert check(_schedule_case(offsets_hours=[], khoang_cach_gio=12.0)) == []
    assert check(_schedule_case(offsets_hours=[0.0], khoang_cach_gio=12.0)) == []


def test_schedule_gap_exceeding_1_5_interval_flags_missing_dose() -> None:
    """Khoảng cách hai mốc liên tiếp > 1.5 * khoang_cach_gio -> lich_dung_thieu_lieu."""
    ca = _schedule_case(
        offsets_hours=[16.0, 0.0],
        khoang_cach_gio=8.0,
        tan_suat="3 lần/ngày",
    )
    findings = check(ca)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "lich_dung_thieu_lieu"
    assert finding.yeu_to == 7
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "can_luu_y"
    assert "3 lần/ngày" in finding.mo_ta
    assert "16.0" in finding.mo_ta


def test_schedule_too_few_doses_in_first_24h_flags_missing_dose() -> None:
    """Mốc cuối cách mốc đầu >= 24h nhưng số mốc trong [đầu, đầu+24h) < so_lan_moi_ngay."""
    ca = _schedule_case(
        offsets_hours=[0.0, 24.0],
        so_lan_moi_ngay=2,
        khoang_cach_gio=None,
        tan_suat="2 lần/ngày",
    )
    findings = check(ca)
    assert len(findings) == 1
    assert findings[0].ma_luat == "lich_dung_thieu_lieu"
    assert findings[0].ket_luan == "can_xem"
    assert findings[0].muc_do == "can_luu_y"


def test_schedule_both_conditions_met_returns_single_finding() -> None:
    """Hai điều kiện thiếu liều cùng đúng vẫn chỉ sinh một phát hiện cho mỗi dòng."""
    ca = _schedule_case(
        offsets_hours=[0.0, 24.0],
        so_lan_moi_ngay=2,
        khoang_cach_gio=12.0,
        tan_suat="2 lần/ngày",
    )
    findings = check(ca)
    assert len(findings) == 1
    assert findings[0].ma_luat == "lich_dung_thieu_lieu"


def test_schedule_three_times_daily_at_06_14_22_returns_dat() -> None:
    """Lịch dùng 3 lần/ngày vào 06:00, 14:00, 22:00 trả về lich_dung_phu_hop (dat)."""
    base_day = NOW.replace(hour=6, minute=0)
    lich = [
        LichDung(thoi_diem_du_kien=base_day, lieu=1.0, don_vi="g"),
        LichDung(thoi_diem_du_kien=base_day + timedelta(hours=8), lieu=1.0, don_vi="g"),
        LichDung(thoi_diem_du_kien=base_day + timedelta(hours=16), lieu=1.0, don_vi="g"),
    ]
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-TID",
                thuoc_id="T-DEFAULT",
                tan_suat="3 lần/ngày",
                so_lan_moi_ngay=3,
                khoang_cach_gio=8.0,
                bat_dau=base_day,
                trang_thai_dong="active",
                lich_dung=lich,
            ),
        ],
    )
    findings = check(ca)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "lich_dung_phu_hop"
    assert finding.ket_luan == "dat"
    assert finding.muc_do == "thong_tin"
    assert "3 lần/ngày" in finding.mo_ta
    assert "8.0" in finding.mo_ta
