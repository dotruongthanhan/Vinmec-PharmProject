"""Thành phần D: khung hỏi thêm về ca bệnh đang mở."""

from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from app.domain.models import CaBenh
from app.ui.labels import NHAN_LOAI_CAN_CU, label_of
from app.ui.services import AskService, TraLoi
from app.ui.state import append_chat, clear_chat, get_chat
from app.ui.view_model import plain_label, suggested_questions


def _submit_question(
    ca: CaBenh,
    question: str,
    history: list[tuple[str, TraLoi | str]],
    ask_service: AskService,
    state: MutableMapping[str, Any],
) -> None:
    """Gọi AskService và lưu cặp câu hỏi - câu trả lời vào hội thoại của ca."""
    plain_history = [
        (vai, item.noi_dung if isinstance(item, TraLoi) else item) for vai, item in history
    ]
    append_chat(state, ca.ca_id, "user", question)
    try:
        answer = ask_service.ask(ca, question, plain_history)
    except Exception as exc:
        answer = TraLoi(
            trang_thai="loi",
            noi_dung=f"Không thể xử lý câu hỏi: {exc}",
        )
    append_chat(state, ca.ca_id, "assistant", answer)


def _render_assistant_reply(reply: TraLoi) -> None:
    """Hiển thị câu trả lời TraLoi theo đúng trạng thái và chỉ dùng st.text cho nội dung."""
    if reply.trang_thai == "chua_san_sang":
        st.caption("Chế độ hiện tại: chưa nối đồ thị hỏi đáp")
    elif reply.trang_thai == "khong_co_nguon":
        st.caption("Không tìm thấy căn cứ trong kho nguồn hiện có.")
    elif reply.trang_thai == "ngoai_pham_vi":
        st.caption("Yêu cầu ngoài phạm vi chỉ đọc của ca đang mở.")
    elif reply.trang_thai == "loi":
        st.error("Đã xảy ra lỗi khi hỏi thêm.")

    st.text(reply.noi_dung)

    if reply.trich_dan:
        st.caption("Trích dẫn:")
        for td in reply.trich_dan:
            ref_suffix = f" [{td.ban_ghi_id}]" if td.ban_ghi_id else ""
            st.text(f"[{td.so}] {label_of(NHAN_LOAI_CAN_CU, td.loai)}: {td.nhan}{ref_suffix}")

    if reply.cong_cu_da_goi:
        with st.expander("Hệ thống đã tra gì", expanded=False):
            for tool_name in reply.cong_cu_da_goi:
                st.text(f"- {tool_name}")


def render_chat(
    ca: CaBenh,
    ask_service: AskService,
    state: MutableMapping[str, Any],
) -> None:
    """Hiển thị khung hỏi thêm riêng cho ca đang mở."""
    col_title, col_clear = st.columns([3, 1])
    with col_title:
        st.subheader("Hỏi thêm về ca này")
    with col_clear:
        if st.button("Xoá hội thoại", key=f"clear_chat__{ca.ca_id}", use_container_width=True):
            clear_chat(state, ca.ca_id)
            st.rerun()

    history = get_chat(state, ca.ca_id)
    if not history:
        st.caption("Câu hỏi gợi ý cho ca này:")
        for idx, question in enumerate(suggested_questions(ca)):
            if st.button(
                plain_label(question),
                key=f"suggest_q__{ca.ca_id}__{idx}",
                use_container_width=True,
            ):
                _submit_question(ca, question, history, ask_service, state)
                st.rerun()

    for vai, content in history:
        msg_role = "user" if vai == "user" else "assistant"
        with st.chat_message(msg_role):
            if isinstance(content, TraLoi):
                _render_assistant_reply(content)
            else:
                st.text(str(content))

    prompt = st.chat_input("Nhập câu hỏi về ca đang mở…", key=f"chat_input__{ca.ca_id}")
    if prompt and prompt.strip():
        _submit_question(ca, prompt.strip(), history, ask_service, state)
        st.rerun()

    st.caption("Trả lời tham khảo, có trích dẫn. Không dán dữ liệu người bệnh thật.")
