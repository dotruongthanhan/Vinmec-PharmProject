"""Thành phần C: bảng nhận định dạng thẻ 3 cột kèm căn cứ và khối mục đạt."""

from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from typing import TYPE_CHECKING, Any

import streamlit as st

from app.domain.models import CaBenh
from app.ui.components.evidence_dialog import show_evidence_dialog
from app.ui.components.feedback import render_finding_feedback
from app.ui.labels import NHAN_DAU_VAO, NHAN_KET_LUAN, NHAN_MUC_DO, label_of
from app.ui.view_model import (
    evidence_rows,
    plain_label,
    sort_attention_rows,
    split_findings,
    unchecked_factors,
)

if TYPE_CHECKING:
    from app.feedback import PhanHoi
    from app.pipeline import KetQuaThamDinh
    from app.rules.types import CanCu


def _render_severity_header(row: dict[str, object]) -> None:
    """Hiển thị dải mức độ (luôn có chữ và biểu tượng) cùng nhãn nguồn gốc."""
    ket_luan = str(row["ket_luan"])
    muc_do = row.get("muc_do")
    col_badge, col_source = st.columns([3, 2])

    with col_badge:
        if muc_do == "nghiem_trong" and ket_luan == NHAN_KET_LUAN["can_xem"]:
            st.error(f"⛔ Nghiêm trọng · {plain_label(ket_luan)}")
        elif ket_luan == NHAN_KET_LUAN["can_xem"]:
            level_label = label_of(NHAN_MUC_DO, str(muc_do or "can_luu_y"))
            st.warning(f"⚠ {plain_label(level_label)} · {plain_label(ket_luan)}")
        elif ket_luan == NHAN_KET_LUAN["ngoai_hdsd"]:
            st.warning(f"⚠ {plain_label(ket_luan)}")
        else:
            st.info(f"? {plain_label(ket_luan)}")

    with col_source:
        st.caption(f"Luật · {plain_label(str(row['yeu_to']))}")


def render_findings(
    ca: CaBenh,
    result: KetQuaThamDinh,
    rows: list[dict[str, object]],
    feedbacks: Sequence[PhanHoi],
    state: MutableMapping[str, Any],
) -> None:
    """Hiển thị thẻ nhận định cần chú ý, căn cứ mở được, phản hồi và khối mục đạt."""
    attention_raw, passed_rows = split_findings(rows)
    attention_rows = sort_attention_rows(attention_raw)

    st.subheader(f"Bảng nhận định – {len(attention_rows)} mục cần chú ý")
    unchecked = unchecked_factors(result.phat_hien)
    st.caption(f"Chưa có luật kiểm tra cho các yếu tố: {plain_label(', '.join(unchecked))}")
    if not attention_rows:
        st.success(f"Không có mục cần chú ý trong phạm vi {len(rows)} luật đã chạy.")

    for idx, row in enumerate(attention_rows):
        with st.container(border=True):
            _render_severity_header(row)

            c_drug, c_factor, c_comment = st.columns([2, 2, 3])
            with c_drug:
                st.caption("Thuốc")
                st.text(str(row["thuoc"]) or "Toàn đơn")
            with c_factor:
                st.caption("Yếu tố kiểm tra")
                st.text(str(row["yeu_to"]))
            with c_comment:
                st.caption("Nhận xét")
                st.text(str(row["nhan_xet"]))

            missing_fields = row["thong_tin_con_thieu"]
            if isinstance(missing_fields, list) and missing_fields:
                missing_labels = [label_of(NHAN_DAU_VAO, str(f)) for f in missing_fields]
                st.text(
                    f"Còn thiếu: {', '.join(missing_labels)} (kiểm tra hồ sơ lâm sàng để bổ sung)"
                )

            raw_ev = row["can_cu"]
            can_cu_list: list[CanCu] = list(raw_ev) if isinstance(raw_ev, list) else []
            ev_rows = evidence_rows(can_cu_list)
            raw_ids = row["chi_tiet_y_lenh_id"]
            line_ids = [str(item) for item in raw_ids] if isinstance(raw_ids, list) else []
            widget_key = f"{ca.ca_id}__{row['ma_luat']}__{'_'.join(line_ids)}__{idx}"

            is_serious = row.get("muc_do") == "nghiem_trong"
            with st.expander(f"Căn cứ ({len(ev_rows)})", expanded=is_serious):
                if ev_rows:
                    for ev in ev_rows:
                        rec_suffix = f" [{ev['ban_ghi_id']}]" if ev["ban_ghi_id"] else ""
                        st.text(f"{ev['so']}. {ev['loai_nhan']}: {ev['mo_ta']}{rec_suffix}")
                        if ev["mo_duoc"]:
                            is_calc = ev["loai"] == "tinh_toan"
                            btn_text = "Xem phép tính" if is_calc else "Mở bản ghi"
                            if st.button(
                                btn_text,
                                key=f"ev_btn__{widget_key}__{ev['so']}",
                            ):
                                show_evidence_dialog(ca, result, ev)
                        elif ev["loai"] == "tai_lieu":
                            st.caption("Nguyên văn đoạn nguồn sẽ có khi nối kho tri thức.")
                else:
                    st.text("Không có căn cứ chi tiết.")

            render_finding_feedback(ca.ca_id, row, widget_key, feedbacks, state)

    with st.expander(f"Các mục đạt ({len(passed_rows)})", expanded=False):
        if passed_rows:
            compact = [
                {
                    "Thuốc": str(r["thuoc"]) or "Toàn đơn",
                    "Yếu tố": str(r["yeu_to"]),
                    "Nhận xét": str(r["nhan_xet"]),
                    "Kết luận": str(r["ket_luan"]),
                }
                for r in passed_rows
            ]
            st.dataframe(compact, width="stretch", hide_index=True)
        else:
            st.text("Không có mục đạt.")
