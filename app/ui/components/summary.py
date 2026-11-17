"""Thành phần B: tóm tắt 3 cột và 4 chỉ số lâm sàng đã tính."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING

import streamlit as st

from app.domain.models import CaBenh
from app.ui.labels import (
    NHAN_CO_DIA_LOAI,
    NHAN_CO_DIA_TRANG_THAI,
    NHAN_CONG_THUC,
    NHAN_DAU_VAO,
    NHAN_LOAI_HO_SO,
    label_of,
)
from app.ui.view_model import (
    format_dt,
    format_number,
    labs_without_range,
    length_of_stay_days,
    metric_text,
    plain_label,
)

if TYPE_CHECKING:
    from app.pipeline import KetQuaThamDinh


def render_summary(
    ca: CaBenh,
    result: KetQuaThamDinh,
    trends: Sequence[dict[str, object]],
    los_days: int | None,
) -> None:
    """Hiển thị tóm tắt 3 cột (chẩn đoán, diễn biến, bất thường) và 4 chỉ số đã tính."""
    st.subheader("Tóm tắt ca bệnh")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.caption("Chẩn đoán và cơ địa")
        sorted_dx = sorted(ca.chan_doan, key=lambda cd: 0 if cd.loai == "chinh" else 1)
        if sorted_dx:
            for cd in sorted_dx:
                dx_type = "Chính" if cd.loai == "chinh" else "Kèm"
                icd = f" [{cd.ma_icd10}]" if cd.ma_icd10 else ""
                st.text(f"- [{dx_type}] {cd.noi_dung}{icd}")
        else:
            st.text("Chưa có chẩn đoán")

        if ca.co_dia:
            st.text("Cơ địa đặc biệt:")
            for item in ca.co_dia:
                loai_label = label_of(NHAN_CO_DIA_LOAI, item.loai)
                tt_label = label_of(NHAN_CO_DIA_TRANG_THAI, item.trang_thai)
                val = f" ({item.gia_tri})" if item.gia_tri else ""
                st.text(f"- {loai_label}: {tt_label}{val}")

        # Ca là ảnh chụp lúc kê y lệnh; giữ chữ ký gọi hiện có của ứng dụng.
        los_days = length_of_stay_days(ca, now=ca.y_lenh_cho_duyet.thoi_diem_ke)
        los_text = f"{los_days} ngày" if los_days is not None else "—"
        st.text(
            f"Vào viện: {format_dt(ca.dot_dieu_tri.thoi_diem_bat_dau)} · "
            f"Nằm viện: {los_text} (tính tới lúc kê y lệnh)"
        )

    with col2:
        st.caption("Diễn biến mới nhất")
        if ca.dien_bien:
            latest_note = max(ca.dien_bien, key=lambda db: db.thoi_diem_ghi)
            doc_type = label_of(NHAN_LOAI_HO_SO, latest_note.loai_ho_so)
            st.text(f"{format_dt(latest_note.thoi_diem_ghi)} · {doc_type}")
            st.text(latest_note.noi_dung)
            st.caption("Xem tất cả tại thẻ Diễn biến bên dưới.")
        else:
            st.text("Chưa có ghi nhận diễn biến")

    with col3:
        st.caption("Bất thường gần nhất")
        missing_ranges = labs_without_range(ca)
        if trends:
            for item in trends:
                prev_part = f" ({item['so_voi_truoc']})" if item["so_voi_truoc"] else ""
                ts_val = item["thoi_diem"]
                ts_text = format_dt(ts_val) if isinstance(ts_val, datetime) else "—"
                unit = str(item["don_vi"] or "").strip()
                unit_part = f" {unit}" if unit else ""
                st.text(
                    f"- {item['ten']}: {item['gia_tri_text']}{unit_part} "
                    f"{item['huong']}{prev_part} · {ts_text}"
                )
            if missing_ranges:
                st.caption(f"{missing_ranges} kết quả khác không có khoảng tham chiếu.")
        elif missing_ranges:
            st.text(f"Chưa đánh giá được: {missing_ranges} kết quả không có khoảng tham chiếu.")
        else:
            st.text("Không có xét nghiệm ngoài ngưỡng.")

    metric_cols = st.columns(4)
    for col, calc in zip(metric_cols, result.chi_so, strict=False):
        with col:
            title = label_of(NHAN_CONG_THUC, calc.cong_thuc)
            st.metric(
                label=f"{plain_label(title)} ({plain_label(calc.don_vi)})",
                value=metric_text(calc.cong_thuc, calc.ket_qua),
            )
            if calc.ket_qua is None and calc.thieu_dau_vao:
                missing_labels = [label_of(NHAN_DAU_VAO, code) for code in calc.thieu_dau_vao]
                st.text(f"Thiếu: {', '.join(missing_labels)}")
            with st.expander("Đầu vào và công thức"):
                if calc.dau_vao:
                    for inp in calc.dau_vao:
                        rec_id = inp.ban_ghi_id or "—"
                        ts = format_dt(inp.thoi_diem)
                        st.text(
                            f"- {label_of(NHAN_DAU_VAO, inp.ten)}: "
                            f"{format_number(inp.gia_tri)} {inp.don_vi} "
                            f"(mã: {rec_id}, lúc: {ts})"
                        )
                else:
                    st.text("Không có đầu vào hợp lệ.")
                for note in calc.ghi_chu:
                    st.text(f"Ghi chú: {note}")
                st.text(f"Trích dẫn: {calc.tham_khao}")
