"""Thành phần A: dải định danh ca bệnh một hàng ở đầu vùng chính."""

import streamlit as st

from app.ui.view_model import plain_label


def render_case_header(header: dict[str, object], counts: dict[str, int]) -> None:
    """Hiển thị dải định danh ca trên cùng: hành chính, CrCl, dị ứng 3 trạng thái và số đếm."""
    with st.container(border=True):
        col_id, col_allergy, col_counts = st.columns([3, 3, 2])

        with col_id:
            identity = (
                f"{header['ca_id']} · {header['gioi_tuoi']} · "
                f"{header['can_nang']} · {header['khoa_loai']}"
            )
            st.text(identity)
            crcl_arrow = " ▼" if header["crcl_bat_thuong"] else ""
            st.caption(f"CrCl: {plain_label(str(header['crcl']))}{crcl_arrow}")

        with col_allergy:
            status = header["di_ung_trang_thai"]
            allergy_msg = str(header["di_ung_text"])
            safe_msg = plain_label(allergy_msg)
            if status == "co_di_ung":
                st.error(f"⛔ {safe_msg}")
            elif status == "chua_co_thong_tin":
                st.warning(f"⚠ {safe_msg}")
            else:
                st.text(f"✓ {allergy_msg}")

        with col_counts:
            parts = [
                f"⛔ {counts['nghiem_trong']} nghiêm trọng",
                f"⚠ {counts['can_luu_y']} cần lưu ý",
                f"? {counts['thieu_du_lieu']} thiếu dữ liệu",
            ]
            if counts["ngoai_hdsd"] > 0:
                parts.append(f"⚠ {counts['ngoai_hdsd']} ngoài HDSD")
            st.text(" · ".join(parts))
