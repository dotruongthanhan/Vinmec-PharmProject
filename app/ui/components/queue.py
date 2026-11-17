"""Thành phần thanh bên hiển thị hàng đợi ca bệnh, bộ lọc và sắp xếp ưu tiên."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from typing import TYPE_CHECKING, Any

import streamlit as st

from app.domain.models import CaBenh
from app.ui.labels import NHAN_BO_LOC_HANG_DOI, label_of
from app.ui.state import (
    get_queue_filter,
    get_selected,
    select_case,
    set_queue_filter,
)
from app.ui.view_model import (
    feedback_status,
    finding_rows,
    plain_label,
    queue_rows,
    split_findings,
)

if TYPE_CHECKING:
    from app.feedback import PhanHoi
    from app.pipeline import KetQuaThamDinh


def _priority_int(row: dict[str, object]) -> int:
    """Lấy mức ưu tiên nguyên của dòng hàng đợi."""
    val = row.get("uu_tien")
    return val if isinstance(val, int) else 4


def _responded_case_ids(
    cases: Sequence[CaBenh],
    results_by_id: Mapping[str, KetQuaThamDinh],
    feedbacks: Sequence[PhanHoi],
) -> set[str]:
    """Xác định các ca có mục cần chú ý và đã phản hồi đầy đủ tất cả mục đó."""
    responded: set[str] = set()
    for ca in cases:
        res = results_by_id.get(ca.ca_id)
        if res is None:
            continue
        rows = finding_rows(ca, res.phat_hien)
        attention, _ = split_findings(rows)
        if attention and all(
            feedback_status(ca.ca_id, row, feedbacks) is not None for row in attention
        ):
            responded.add(ca.ca_id)
    return responded


def render_queue(
    cases: Sequence[CaBenh],
    results_by_id: Mapping[str, KetQuaThamDinh],
    feedbacks: Sequence[PhanHoi],
    state: MutableMapping[str, Any],
) -> CaBenh | None:
    """Hiển thị hàng đợi ca ở thanh bên và trả về ca đang được chọn."""
    with st.sidebar:
        st.header("Hàng đợi y lệnh")
        if not cases:
            st.info("Không có y lệnh chờ thẩm định")
            return None

        all_rows = queue_rows(cases, results_by_id)
        valid_ids = [str(row["ca_id"]) for row in all_rows]
        selected_id = get_selected(state, valid_ids)

        responded_ids = _responded_case_ids(cases, results_by_id, feedbacks)

        filter_options = list(NHAN_BO_LOC_HANG_DOI.keys())
        current_filter = get_queue_filter(state)
        if current_filter not in filter_options:
            current_filter = filter_options[0]

        chosen_filter = st.radio(
            "Lọc hàng đợi",
            options=filter_options,
            index=filter_options.index(current_filter),
            format_func=lambda code: label_of(NHAN_BO_LOC_HANG_DOI, code),
            key="queue_filter_radio",
        )
        set_queue_filter(state, chosen_filter)

        if chosen_filter == "can_xem":
            visible_rows = [row for row in all_rows if _priority_int(row) < 4]
        elif chosen_filter == "da_phan_hoi_het":
            visible_rows = [row for row in all_rows if str(row["ca_id"]) in responded_ids]
        else:
            visible_rows = all_rows

        if not visible_rows:
            st.info("Không có ca phù hợp bộ lọc.")

        for row in visible_rows:
            ca_id = str(row["ca_id"])
            done_mark = " · Đã xem" if ca_id in responded_ids else ""
            header_line = (
                f"{plain_label(ca_id)} · {plain_label(str(row['khoa']))} · "
                f"{plain_label(str(row['huy_hieu']))}{done_mark}"
            )
            button_label = f"{header_line}\n{plain_label(str(row['mo_ta']))}"
            is_selected = selected_id == ca_id
            if st.button(
                button_label,
                key=f"select_case_{ca_id}",
                width="stretch",
                type="primary" if is_selected else "secondary",
            ):
                select_case(state, ca_id)
                st.rerun()

    if selected_id is None:
        return None
    return next((ca for ca in cases if ca.ca_id == selected_id), None)
