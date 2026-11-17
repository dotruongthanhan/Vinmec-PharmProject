"""Luật yếu tố 2: phát hiện trùng hoạt chất giữa các dòng thuốc đang hiệu lực."""

from app.domain.loader import ingredients_of
from app.domain.models import CaBenh, ChiTietYLenh, HoatChat
from app.rules.types import CanCu, PhatHien, effective_lines, line_label, pending_lines

_YEU_TO = 2


def check(ca: CaBenh) -> list[PhatHien]:
    """Kiểm tra trùng hoạt chất trên các dòng đang hiệu lực có mặt dòng đang xét."""
    pending = pending_lines(ca)
    pending_ids = {line.chi_tiet_y_lenh_id for line in pending}
    effective = effective_lines(ca)
    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}

    lines_by_hc: dict[str, list[ChiTietYLenh]] = {}
    hc_by_id: dict[str, HoatChat] = {}
    for line in effective:
        for hc in ingredients_of(ca, line):
            hc_by_id[hc.hoat_chat_id] = hc
            lines_by_hc.setdefault(hc.hoat_chat_id, []).append(line)

    findings: list[PhatHien] = []
    for hoat_chat_id, lines_for_hc in lines_by_hc.items():
        if len(lines_for_hc) < 2:
            continue
        if not any(line.chi_tiet_y_lenh_id in pending_ids for line in lines_for_hc):
            continue

        hc = hc_by_id[hoat_chat_id]
        evidences: list[CanCu] = []
        for line in lines_for_hc:
            label = line_label(line, thuoc_by_id)
            origin = (
                "y lệnh chờ duyệt"
                if line.chi_tiet_y_lenh_id in pending_ids
                else f"thuốc đang dùng ({line.trang_thai_dong})"
            )
            evidences.append(
                CanCu(
                    loai="du_lieu",
                    ban_ghi_id=line.chi_tiet_y_lenh_id,
                    mo_ta=f"{label} ({origin}) chứa {hc.ten_hoat_chat}",
                ),
            )

        dup_desc = f"Trùng hoạt chất {hc.ten_hoat_chat} ở {len(lines_for_hc)} dòng đang hiệu lực"
        findings.append(
            PhatHien(
                ma_luat="trung_hoat_chat",
                yeu_to=_YEU_TO,
                ket_luan="can_xem",
                muc_do="can_luu_y",
                chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id for line in lines_for_hc],
                mo_ta=dup_desc,
                can_cu=evidences,
            ),
        )

    if not findings:
        return [
            PhatHien(
                ma_luat="trung_hoat_chat_khong_co",
                yeu_to=_YEU_TO,
                ket_luan="dat",
                muc_do="thong_tin",
                chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id for line in pending],
                mo_ta="Không có hoạt chất trùng lặp trong các dòng thuốc đang hiệu lực",
                can_cu=[
                    CanCu(
                        loai="du_lieu",
                        ban_ghi_id=None,
                        mo_ta=f"Đã đối chiếu {len(effective)} dòng thuốc đang hiệu lực",
                    ),
                ],
            ),
        ]

    return findings
