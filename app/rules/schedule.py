"""Luật yếu tố 7: đối chiếu lịch dùng dự kiến với tần suất và khoảng cách liều kê."""

from datetime import timedelta
from itertools import pairwise

from app.domain.models import CaBenh, ChiTietYLenh, LichDung
from app.rules.types import CanCu, PhatHien, pending_lines

_YEU_TO = 7


def _gap_hours(first: LichDung, second: LichDung) -> float:
    """Tính khoảng cách thời gian giữa hai mốc lịch dùng theo giờ."""
    return (second.thoi_diem_du_kien - first.thoi_diem_du_kien).total_seconds() / 3600.0


def _prescribed_frequency_text(line: ChiTietYLenh) -> str:
    """Tạo chuỗi mô tả tần suất kê phục vụ hiển thị trong phát hiện."""
    if line.tan_suat is not None and line.tan_suat.strip() != "":
        return line.tan_suat.strip()
    if line.so_lan_moi_ngay is not None:
        return f"{line.so_lan_moi_ngay} lần/ngày"
    if line.khoang_cach_gio is not None:
        return f"mỗi {line.khoang_cach_gio:g} giờ"
    return "không rõ tần suất kê"


def check(ca: CaBenh) -> list[PhatHien]:
    """Kiểm tra tính đầy đủ của lịch dùng dự kiến trên từng dòng y lệnh đang xét."""
    findings: list[PhatHien] = []

    for line in pending_lines(ca):
        if len(line.lich_dung) <= 1:
            continue

        sorted_items = sorted(line.lich_dung, key=lambda item: item.thoi_diem_du_kien)
        max_gap = max(_gap_hours(cur, nxt) for cur, nxt in pairwise(sorted_items))

        first_ts = sorted_items[0].thoi_diem_du_kien
        last_ts = sorted_items[-1].thoi_diem_du_kien
        window_end = first_ts + timedelta(hours=24)
        count_first_24h = sum(
            1 for item in sorted_items if first_ts <= item.thoi_diem_du_kien < window_end
        )

        gap_too_long = (
            line.khoang_cach_gio is not None
            and line.khoang_cach_gio > 0
            and max_gap > 1.5 * line.khoang_cach_gio
        )
        too_few_in_24h = (
            line.so_lan_moi_ngay is not None
            and (last_ts - first_ts) >= timedelta(hours=24)
            and count_first_24h < line.so_lan_moi_ngay
        )

        freq_text = _prescribed_frequency_text(line)
        evidence = CanCu(
            loai="du_lieu",
            ban_ghi_id=line.chi_tiet_y_lenh_id,
            mo_ta=(
                f"Lịch dùng có {len(sorted_items)} mốc từ {first_ts.isoformat()} "
                f"đến {last_ts.isoformat()}, khoảng cách lớn nhất {max_gap:.1f} giờ"
            ),
        )

        if gap_too_long or too_few_in_24h:
            findings.append(
                PhatHien(
                    ma_luat="lich_dung_thieu_lieu",
                    yeu_to=_YEU_TO,
                    ket_luan="can_xem",
                    muc_do="can_luu_y",
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=(
                        f"Lịch dùng thiếu liều so với tần suất kê ({freq_text}); "
                        f"khoảng cách thực tế lớn nhất {max_gap:.1f} giờ"
                    ),
                    can_cu=[evidence],
                ),
            )
        else:
            findings.append(
                PhatHien(
                    ma_luat="lich_dung_phu_hop",
                    yeu_to=_YEU_TO,
                    ket_luan="dat",
                    muc_do="thong_tin",
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=(
                        f"Lịch dùng phù hợp với tần suất kê ({freq_text}); "
                        f"khoảng cách thực tế lớn nhất {max_gap:.1f} giờ"
                    ),
                    can_cu=[evidence],
                ),
            )

    return findings
