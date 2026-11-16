"""Thành phần E: 4 thẻ chi tiết (Y lệnh, Xét nghiệm, Vi sinh, Diễn biến)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import streamlit as st

from app.domain.models import CaBenh
from app.ui.labels import NHAN_LOAI_HO_SO, NHAN_LUONG_DUYET, label_of
from app.ui.view_model import (
    finding_rows,
    format_dt,
    format_number,
    format_ref_range,
    lab_rows,
    order_table_rows,
    prescribed_active_ingredient_ids,
    split_findings,
)

if TYPE_CHECKING:
    from app.pipeline import KetQuaThamDinh


def _attention_line_ids(ca: CaBenh, result: KetQuaThamDinh) -> set[str]:
    """Gom các mã dòng y lệnh đang có nhận định cần chú ý."""
    rows = finding_rows(ca, result.phat_hien)
    attention, _ = split_findings(rows)
    ids: set[str] = set()
    for row in attention:
        raw_ids = row.get("chi_tiet_y_lenh_id")
        if isinstance(raw_ids, list):
            for item in raw_ids:
                ids.add(str(item))
    return ids


def render_detail_tabs(ca: CaBenh, result: KetQuaThamDinh) -> None:
    """Hiển thị 4 thẻ chi tiết hồ sơ ca bệnh: Y lệnh, Xét nghiệm, Vi sinh, Diễn biến."""
    st.subheader("Chi tiết hồ sơ")
    tab_orders, tab_labs, tab_micro, tab_notes = st.tabs(
        ["Y lệnh", "Xét nghiệm", "Vi sinh", "Diễn biến"],
    )

    with tab_orders:
        yl = ca.y_lenh_cho_duyet
        st.text(
            f"Mã y lệnh: {yl.y_lenh_id} · Khoa kê: {yl.khoa_ke_don} · "
            f"Luồng: {label_of(NHAN_LUONG_DUYET, yl.luong_duyet)} · "
            f"Thời điểm kê: {format_dt(yl.thoi_diem_ke)}"
        )
        line_ids = _attention_line_ids(ca, result)
        st.dataframe(
            order_table_rows(ca, yl.chi_tiet, finding_line_ids=line_ids),
            use_container_width=True,
            hide_index=True,
        )

        if ca.thuoc_dang_dung:
            st.caption("Thuốc đang dùng và đã ngừng")
            st.dataframe(
                order_table_rows(
                    ca,
                    ca.thuoc_dang_dung,
                    include_status=True,
                    finding_line_ids=line_ids,
                ),
                use_container_width=True,
                hide_index=True,
            )

    with tab_labs:
        rows = lab_rows(ca)
        if rows:
            display_rows: list[dict[str, str]] = []
            for row in rows:
                gia_tri_so = row["gia_tri_so"]
                low = row["nguong_duoi"]
                high = row["nguong_tren"]
                if isinstance(gia_tri_so, int | float):
                    val_text = format_number(float(gia_tri_so))
                    if isinstance(high, int | float) and gia_tri_so > high:
                        val_text = f"{val_text} ▲"
                    elif isinstance(low, int | float) and gia_tri_so < low:
                        val_text = f"{val_text} ▼"
                else:
                    val_text = str(row["gia_tri_text"] or "—")

                ts = row["thoi_diem_ket_qua"]
                display_rows.append(
                    {
                        "Thời điểm": format_dt(ts) if isinstance(ts, datetime) else "—",
                        "Xét nghiệm": str(row["ten_xet_nghiem"]),
                        "Giá trị": val_text,
                        "Đơn vị": str(row["don_vi"] or ""),
                        "Khoảng tham chiếu": format_ref_range(
                            float(low) if isinstance(low, int | float) else None,
                            float(high) if isinstance(high, int | float) else None,
                        ),
                        "Bất thường": "Ngoài ngưỡng" if row["ngoai_nguong"] else "",
                    },
                )
            st.dataframe(display_rows, use_container_width=True, hide_index=True)
        else:
            st.text("Chưa có kết quả xét nghiệm.")

    with tab_micro:
        if ca.vi_sinh:
            hc_by_id = {hc.hoat_chat_id: hc.ten_hoat_chat for hc in ca.danh_muc_hoat_chat}
            prescribed_hc = prescribed_active_ingredient_ids(ca)
            sorted_micro = sorted(
                ca.vi_sinh,
                key=lambda item: item.thoi_diem_lay_mau,
                reverse=True,
            )
            for vs in sorted_micro:
                bacteria = vs.vi_khuan or "Chưa phân lập vi khuẩn"
                st.text(
                    f"Bệnh phẩm: {vs.benh_pham} · Lấy mẫu: {format_dt(vs.thoi_diem_lay_mau)} "
                    f"· Vi khuẩn: {bacteria}"
                )
                if vs.khang_sinh_do:
                    ksd_rows = []
                    for ksd in vs.khang_sinh_do:
                        mic_text = format_number(ksd.mic, digits=2) if ksd.mic is not None else "—"
                        in_order = "★ Đang kê" if ksd.hoat_chat_id in prescribed_hc else ""
                        ksd_rows.append(
                            {
                                "Hoạt chất": hc_by_id.get(ksd.hoat_chat_id, ksd.hoat_chat_id),
                                "Kết quả": ksd.ket_qua,
                                "MIC": mic_text,
                                "Đơn hiện tại": in_order,
                            },
                        )
                    st.dataframe(ksd_rows, use_container_width=True, hide_index=True)
        else:
            st.text("Chưa có kết quả vi sinh.")

    with tab_notes:
        if ca.dien_bien:
            notes = sorted(ca.dien_bien, key=lambda db: db.thoi_diem_ghi, reverse=True)
            for idx, note in enumerate(notes):
                doc_type = label_of(NHAN_LOAI_HO_SO, note.loai_ho_so)
                st.text(f"{format_dt(note.thoi_diem_ghi)} · {doc_type}")
                st.text(note.noi_dung)
                if idx < len(notes) - 1:
                    st.divider()
        else:
            st.text("Chưa có ghi nhận diễn biến.")
