"""Luật yếu tố 7: kiểm tra y lệnh thuốc kê thiếu trường bắt buộc."""

from app.domain.models import CaBenh, ChiTietYLenh
from app.rules.types import CanCu, PhatHien, line_label, pending_lines

_YEU_TO = 7


def _is_blank_str(value: str | None) -> bool:
    """Kiểm tra chuỗi rỗng hoặc chỉ gồm khoảng trắng."""
    return value is None or value.strip() == ""


def _missing_fields_for_line(line: ChiTietYLenh) -> list[tuple[str, str]]:
    """Trả về danh sách (ten_truong, nhan_tieng_viet) đang bị thiếu của dòng thuốc."""
    missing: list[tuple[str, str]] = []
    if line.lieu_moi_lan is None:
        missing.append(("lieu_moi_lan", "liều mỗi lần"))
    if _is_blank_str(line.don_vi_lieu):
        missing.append(("don_vi_lieu", "đơn vị liều"))
    if _is_blank_str(line.duong_dung):
        missing.append(("duong_dung", "đường dùng"))
    if (
        _is_blank_str(line.tan_suat)
        and line.so_lan_moi_ngay is None
        and line.khoang_cach_gio is None
    ):
        missing.append(("tan_suat", "tần suất"))
    return missing


def check(ca: CaBenh) -> list[PhatHien]:
    """Kiểm tra thiếu trường bắt buộc trên các dòng y lệnh thuốc chờ duyệt."""
    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    findings: list[PhatHien] = []

    for line in pending_lines(ca):
        if line.loai_san_pham != "thuoc":
            continue

        missing = _missing_fields_for_line(line)
        if not missing:
            continue

        field_names = [field_name for field_name, _ in missing]
        field_labels = [field_label for _, field_label in missing]
        label = line_label(line, thuoc_by_id)
        findings.append(
            PhatHien(
                ma_luat="y_lenh_thieu_truong",
                yeu_to=_YEU_TO,
                ket_luan="can_xem",
                muc_do="can_luu_y",
                chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                mo_ta=(f"Y lệnh thuốc {label} kê thiếu trường bắt buộc: {', '.join(field_labels)}"),
                can_cu=[
                    CanCu(
                        loai="du_lieu",
                        ban_ghi_id=line.chi_tiet_y_lenh_id,
                        mo_ta=f"Thiếu trường: {', '.join(field_names)}",
                    ),
                ],
                thong_tin_con_thieu=field_names,
            )
        )

    return findings
