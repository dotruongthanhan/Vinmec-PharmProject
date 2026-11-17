"""Thành phần hộp thoại xem căn cứ: dữ liệu ca bệnh, phép tính chỉ số và tài liệu."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import streamlit as st

from app.domain.models import CaBenh
from app.ui.labels import NHAN_CONG_THUC, NHAN_DAU_VAO, label_of
from app.ui.view_model import format_dt, format_number, metric_text, plain_label, record_detail

if TYPE_CHECKING:
    from app.calc.types import CalcResult
    from app.pipeline import KetQuaThamDinh


def _match_calcs(chi_so: Sequence[CalcResult], mo_ta: str) -> list[CalcResult]:
    """Tìm công thức tính chỉ số khớp với mô tả căn cứ tính toán."""
    text = mo_ta.lower()
    target_formula: str | None = None
    if "cockcroft" in text or "crcl" in text:
        target_formula = "cockcroft_gault"
    elif "egfr" in text or "ckd-epi" in text or "ckd_epi" in text:
        target_formula = "egfr_ckd_epi_2021"
    elif "bmi" in text:
        target_formula = "bmi"
    elif "bsa" in text or "mosteller" in text:
        target_formula = "bsa_mosteller"

    if target_formula is not None:
        matched = [calc for calc in chi_so if calc.cong_thuc == target_formula]
        if matched:
            return matched

    computed = [calc for calc in chi_so if calc.ket_qua is not None]
    return computed if computed else list(chi_so[:1])


@st.dialog("Căn cứ thẩm định")
def show_evidence_dialog(
    ca: CaBenh,
    result: KetQuaThamDinh,
    evidence: dict[str, object],
) -> None:
    """Hiển thị hộp thoại chi tiết cho một dòng căn cứ (dữ liệu ca, tính toán hoặc tài liệu)."""
    loai = str(evidence.get("loai", ""))
    raw_id = evidence.get("ban_ghi_id")
    ban_ghi_id = str(raw_id) if raw_id is not None else None
    mo_ta = str(evidence.get("mo_ta", ""))

    if loai == "du_lieu":
        detail = record_detail(ca, ban_ghi_id) if ban_ghi_id else None
        if detail is not None:
            st.subheader(plain_label(str(detail["tieu_de"])))
            st.caption(f"Loại bản ghi: {plain_label(str(detail['loai']))}")
            dong = detail["dong"]
            if isinstance(dong, list):
                for key, val in dong:
                    st.text(f"{key}: {val}")
        else:
            missing_id = plain_label(ban_ghi_id or "—")
            st.info(f"Không tìm thấy bản ghi chi tiết cho mã: {missing_id}")
            st.text(mo_ta)

    elif loai == "tinh_toan":
        matched_calcs = _match_calcs(result.chi_so, mo_ta)
        for calc in matched_calcs:
            title = label_of(NHAN_CONG_THUC, calc.cong_thuc)
            st.subheader(plain_label(title))
            st.text(f"Kết quả: {metric_text(calc.cong_thuc, calc.ket_qua)} {calc.don_vi}")
            st.caption("Đầu vào sử dụng")
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
            st.caption("Công thức và trích dẫn")
            st.text(f"Công thức: {title}")
            for note in calc.ghi_chu:
                st.text(f"Ghi chú: {note}")
            st.text(f"Trích dẫn bài báo: {calc.tham_khao}")
        st.text(f"Mô tả căn cứ: {mo_ta}")

    else:
        st.subheader("Căn cứ tài liệu")
        st.text(mo_ta)
        st.info("Nguyên văn đoạn nguồn sẽ có khi nối kho tri thức.")
