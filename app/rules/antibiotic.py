"""Luật yếu tố 3: đối chiếu kháng sinh trong y lệnh với kết quả vi sinh."""

from typing import Literal

from app.domain.loader import ingredients_of
from app.domain.models import CaBenh, KhangSinhDo, ViSinh
from app.rules.types import CanCu, PhatHien, pending_lines

_YEU_TO = 3

_KSD_STATUS: dict[
    Literal["S", "I", "R"],
    tuple[
        str,
        Literal["dat", "can_xem"],
        Literal["thong_tin", "can_luu_y", "nghiem_trong"],
        str,
    ],
] = {
    "S": ("khang_sinh_vi_sinh_nhay", "dat", "thong_tin", "nhạy cảm (S)"),
    "R": ("khang_sinh_vi_sinh_khang", "can_xem", "nghiem_trong", "đề kháng (R)"),
    "I": ("khang_sinh_vi_sinh_trung_gian", "can_xem", "can_luu_y", "trung gian (I)"),
}


def _latest_ksd_for_ingredient(
    positive_micro: list[ViSinh],
    hoat_chat_id: str,
) -> tuple[ViSinh, KhangSinhDo] | None:
    """Tìm bản ghi vi sinh mới nhất có kháng sinh đồ cho hoạt chất."""
    matches = [
        (vs, ksd)
        for vs in positive_micro
        for ksd in vs.khang_sinh_do
        if ksd.hoat_chat_id == hoat_chat_id
    ]
    if not matches:
        return None
    return max(matches, key=lambda pair: pair[0].thoi_diem_lay_mau)


def check(ca: CaBenh) -> list[PhatHien]:
    """Đối chiếu dòng kháng sinh đang xét với kết quả vi sinh dương tính."""
    positive_micro = [
        vs for vs in ca.vi_sinh if vs.vi_khuan is not None and vs.vi_khuan.strip() != ""
    ]
    if not positive_micro:
        return []

    latest_positive = max(positive_micro, key=lambda vs: vs.thoi_diem_lay_mau)
    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    findings: list[PhatHien] = []

    for line in pending_lines(ca):
        if line.thuoc_id is None or line.thuoc_id not in thuoc_by_id:
            continue
        thuoc = thuoc_by_id[line.thuoc_id]
        if not thuoc.la_khang_sinh:
            continue

        matched_any = False
        for hc in ingredients_of(ca, line):
            latest_pair = _latest_ksd_for_ingredient(positive_micro, hc.hoat_chat_id)
            if latest_pair is None:
                continue

            matched_any = True
            vs, ksd = latest_pair
            ma_luat, ket_luan, muc_do, status_label = _KSD_STATUS[ksd.ket_qua]
            findings.append(
                PhatHien(
                    ma_luat=ma_luat,
                    yeu_to=_YEU_TO,
                    ket_luan=ket_luan,
                    muc_do=muc_do,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=(
                        f"Kháng sinh {thuoc.ten_thuoc} ({hc.ten_hoat_chat}) {status_label} "
                        f"trên mẫu {vs.benh_pham} phân lập {vs.vi_khuan}"
                    ),
                    can_cu=[
                        CanCu(
                            loai="du_lieu",
                            ban_ghi_id=vs.vi_sinh_id,
                            mo_ta=(
                                f"Bệnh phẩm {vs.benh_pham}, vi khuẩn {vs.vi_khuan}, "
                                f"kháng sinh đồ {hc.ten_hoat_chat}: {ksd.ket_qua}"
                            ),
                        ),
                    ],
                ),
            )

        if not matched_any:
            evidence_desc = (
                f"Bệnh phẩm {latest_positive.benh_pham}, vi khuẩn {latest_positive.vi_khuan}, "
                f"chưa có kháng sinh đồ cho {thuoc.ten_thuoc}"
            )
            findings.append(
                PhatHien(
                    ma_luat="khang_sinh_khong_co_ksd",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=(
                        f"Có kết quả vi sinh dương tính ({latest_positive.vi_khuan}) "
                        f"nhưng chưa có kháng sinh đồ cho {thuoc.ten_thuoc}"
                    ),
                    can_cu=[
                        CanCu(
                            loai="du_lieu",
                            ban_ghi_id=latest_positive.vi_sinh_id,
                            mo_ta=evidence_desc,
                        ),
                    ],
                    thong_tin_con_thieu=["khang_sinh_do"],
                ),
            )

    return findings
