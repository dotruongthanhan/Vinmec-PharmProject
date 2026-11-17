"""Ứng dụng Streamlit thẩm định y lệnh: chỉ lắp bố cục và điều phối dịch vụ."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import streamlit as st

from app.feedback import load_feedback
from app.ui.components.case_header import render_case_header
from app.ui.components.chat import render_chat
from app.ui.components.detail_tabs import render_detail_tabs
from app.ui.components.findings import render_findings
from app.ui.components.queue import render_queue
from app.ui.components.status import (
    render_disclaimer,
    render_footer,
    render_load_errors,
    render_no_llm_banner,
)
from app.ui.components.summary import render_summary
from app.ui.services import AskService, NotReadyAskService, PipelineReviewService, ReviewService
from app.ui.state import (
    get_cached_review,
    is_chat_visible,
    set_cached_review,
    set_chat_visible,
)
from app.ui.view_model import (
    count_by_level,
    finding_rows,
    header_info,
    lab_trends,
    length_of_stay_days,
)

if TYPE_CHECKING:
    from app.domain.models import CaBenh
    from app.pipeline import KetQuaThamDinh

_ROOT_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_CASE_DIR = _ROOT_DIR / "data" / "mock" / "demo"
_RENAL_RULES_PATH = _ROOT_DIR / "data" / "kb" / "quy_tac_lieu_than.json"


@st.cache_resource
def _get_services(case_dir_str: str) -> tuple[ReviewService, AskService]:
    """Khởi tạo dịch vụ thẩm định và hỏi đáp một lần theo thư mục ca bệnh."""
    return (
        PipelineReviewService(Path(case_dir_str), _RENAL_RULES_PATH),
        NotReadyAskService(),
    )


def _load_cases_session(
    review_service: ReviewService,
    case_dir: str,
) -> tuple[list[CaBenh], list[tuple[str, str]]]:
    """Nạp danh sách ca bệnh qua ReviewService và lưu trong phiên theo case_dir."""
    cached_dir = st.session_state.get("loaded_case_dir")
    cached_payload = st.session_state.get("loaded_cases_payload")
    if cached_dir == case_dir and isinstance(cached_payload, tuple):
        return cached_payload
    payload = review_service.list_cases()
    st.session_state["loaded_case_dir"] = case_dir
    st.session_state["loaded_cases_payload"] = payload
    return payload


def _review_all_cached(
    cases: list[CaBenh],
    review_service: ReviewService,
) -> dict[str, KetQuaThamDinh]:
    """Lấy kết quả thẩm định từ bộ đệm phiên hoặc chạy một lần nếu chưa có."""
    missing = [ca for ca in cases if get_cached_review(st.session_state, ca.ca_id) is None]
    if missing:
        with st.status("Đang thẩm định danh sách ca…", expanded=False) as status_box:
            st.text("1. Lấy bối cảnh ca bệnh")
            st.text("2. Tính chỉ số lâm sàng và chạy bộ luật")
            for ca in missing:
                set_cached_review(st.session_state, ca.ca_id, review_service.review(ca))
            status_box.update(label=f"Đã hoàn tất rà soát {len(missing)} ca", state="complete")

    results_by_id: dict[str, KetQuaThamDinh] = {}
    for ca in cases:
        cached = get_cached_review(st.session_state, ca.ca_id)
        if cached is not None:
            results_by_id[ca.ca_id] = cached
    return results_by_id


def main() -> None:
    """Điểm vào chính của giao diện Streamlit đợt 1."""
    st.set_page_config(layout="wide", page_title="Hỗ trợ thẩm định y lệnh")
    chat_open = is_chat_visible(st.session_state)
    banner_col, toggle_col = st.columns([7, 1])
    with banner_col:
        render_disclaimer()
        render_no_llm_banner()
    with toggle_col:
        btn_label = "Ẩn hỏi thêm" if chat_open else "Mở hỏi thêm"
        if st.button(btn_label, key="toggle_chat_panel", use_container_width=True):
            set_chat_visible(st.session_state, not chat_open)
            st.rerun()

    case_dir = os.environ.get("CDSS_CASE_DIR", str(_DEFAULT_CASE_DIR))
    review_service, ask_service = _get_services(case_dir)
    cases, load_errors = _load_cases_session(review_service, case_dir)
    render_load_errors(load_errors)

    feedbacks = load_feedback()
    if not cases:
        render_queue([], {}, feedbacks, st.session_state)
        st.warning("Không có ca bệnh hợp lệ để hiển thị.")
        return

    results_by_id = _review_all_cached(cases, review_service)
    selected_case = render_queue(cases, results_by_id, feedbacks, st.session_state)
    if selected_case is None:
        return

    selected_result = results_by_id[selected_case.ca_id]

    if chat_open:
        col_main, col_chat = st.columns([5, 3])
    else:
        col_main = st.container()
        col_chat = None

    with col_main:
        render_case_header(
            header_info(selected_case, selected_result),
            count_by_level(selected_result.phat_hien),
        )
        render_summary(
            selected_case,
            selected_result,
            lab_trends(selected_case),
            length_of_stay_days(selected_case, datetime.now().astimezone()),
        )
        rows = finding_rows(selected_case, selected_result.phat_hien)
        render_findings(selected_case, selected_result, rows, feedbacks, st.session_state)
        render_detail_tabs(selected_case, selected_result)

    if col_chat is not None:
        with col_chat:
            render_chat(selected_case, ask_service, st.session_state)

    render_footer(selected_result.thoi_gian_ms)


if __name__ == "__main__":
    main()
