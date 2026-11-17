"""Thành phần hiển thị thông báo trạng thái hệ thống, lỗi nạp ca và chân trang."""

from collections.abc import Sequence

import streamlit as st

from app.ui.view_model import format_number, plain_label


def render_disclaimer() -> None:
    """Hiển thị dải thông báo cố định nhắc kết quả chỉ mang tính tham khảo."""
    st.info("Kết quả tham khảo từ dữ liệu giả lập. Dược sĩ kiểm chứng và quyết định.")


def render_no_llm_banner() -> None:
    """Hiển thị thông báo rõ hệ thống đang chạy chế độ chỉ dùng bộ luật (chưa có AI)."""
    st.caption("Đang chạy không có bước AI: bảng nhận định do bộ luật sinh ra")


def render_load_errors(load_errors: Sequence[tuple[str, str]]) -> None:
    """Hiển thị thông báo lỗi cho từng tệp ca bệnh không nạp được."""
    for file_name, err_msg in load_errors:
        st.error(f"Không nạp được tệp ca bệnh: {plain_label(file_name)}")
        st.text(err_msg)


def render_footer(thoi_gian_ms: float) -> None:
    """Hiển thị chân trang ghi thời gian chạy thẩm định ca."""
    st.divider()
    st.caption(f"Thời gian chạy: {plain_label(format_number(thoi_gian_ms, digits=2))} ms")
