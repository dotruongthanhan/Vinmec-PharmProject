"""Thành phần phản hồi của dược sĩ trên từng thẻ nhận định."""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping, Sequence
from datetime import datetime
from typing import Any, Literal

import streamlit as st

from app.feedback import PhanHoi, save_feedback
from app.ui.labels import NHAN_PHAN_HOI, NHOM_LY_DO, label_of
from app.ui.view_model import feedback_status, plain_label

_EDITING_KEY = "feedback_editing"
_PENDING_KEY = "feedback_pending_action"
_ERROR_KEY = "feedback_inline_error"


def _state_map(state: MutableMapping[str, Any], key: str) -> dict[str, Any]:
    """Đọc bản đồ trạng thái phụ theo khoá từ MutableMapping."""
    raw = state.get(key)
    return dict(raw) if isinstance(raw, dict) else {}


def _set_state_entry(
    state: MutableMapping[str, Any],
    map_key: str,
    entry_key: str,
    value: Any,
) -> None:
    """Cập nhật hoặc xoá một mục trong bản đồ trạng thái phụ."""
    updated = _state_map(state, map_key)
    if value is None:
        updated.pop(entry_key, None)
    else:
        updated[entry_key] = value
    state[map_key] = updated


def _extract_factor_num(row: Mapping[str, object]) -> int:
    """Tách số thứ tự yếu tố (1..7) từ nhãn hiển thị."""
    raw = str(row.get("yeu_to", "0"))
    prefix = raw.split(".", 1)[0].strip()
    return int(prefix) if prefix.isdigit() else 0


def _extract_line_ids(row: Mapping[str, object]) -> list[str]:
    """Lấy danh sách mã dòng y lệnh từ dòng nhận định."""
    raw = row.get("chi_tiet_y_lenh_id")
    return [str(item) for item in raw] if isinstance(raw, list) else []


def _record_feedback(
    ca_id: str,
    row: Mapping[str, object],
    phan_hoi: Literal["dong_y", "bac_bo", "can_sua"],
    nhom_ly_do: str | None,
    ly_do: str | None,
    save_fn: Callable[[PhanHoi], None],
) -> None:
    """Tạo đối tượng PhanHoi và ghi qua hàm lưu."""
    item = PhanHoi(
        thoi_diem=datetime.now().astimezone(),
        ca_id=ca_id,
        ma_luat=str(row.get("ma_luat", "")),
        yeu_to=_extract_factor_num(row),
        chi_tiet_y_lenh_id=_extract_line_ids(row),
        phan_hoi=phan_hoi,
        nhom_ly_do=nhom_ly_do,
        ly_do=ly_do,
    )
    save_fn(item)


def render_finding_feedback(
    ca_id: str,
    row: Mapping[str, object],
    widget_key: str,
    feedbacks: Sequence[PhanHoi],
    state: MutableMapping[str, Any],
    save_fn: Callable[[PhanHoi], None] = save_feedback,
) -> None:
    """Hiển thị trạng thái phản hồi và cụm nút Đồng ý · Bác bỏ · Cần sửa."""
    latest_fb = feedback_status(ca_id, row, feedbacks)
    editing_map = _state_map(state, _EDITING_KEY)
    pending_map = _state_map(state, _PENDING_KEY)
    error_map = _state_map(state, _ERROR_KEY)

    is_editing = bool(editing_map.get(widget_key, False))
    pending_action = pending_map.get(widget_key)
    inline_error = error_map.get(widget_key)

    if latest_fb is not None and not is_editing:
        fb_label = label_of(NHAN_PHAN_HOI, latest_fb.phan_hoi)
        time_text = latest_fb.thoi_diem.strftime("%H:%M")
        parts: list[str] = []
        if latest_fb.nhom_ly_do:
            parts.append(label_of(NHOM_LY_DO, latest_fb.nhom_ly_do))
        if latest_fb.ly_do:
            parts.append(latest_fb.ly_do)
        detail = f" ({' · '.join(parts)})" if parts else ""
        st.text(f"✓ Đã phản hồi: {fb_label} lúc {time_text}{detail}")
        if st.button("Sửa phản hồi", key=f"edit_fb__{widget_key}"):
            _set_state_entry(state, _EDITING_KEY, widget_key, True)
            _set_state_entry(state, _ERROR_KEY, widget_key, None)
            st.rerun()
        return

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("Đồng ý", key=f"dong_y__{widget_key}", width="stretch"):
            try:
                _record_feedback(ca_id, row, "dong_y", None, None, save_fn)
            except Exception as exc:
                _set_state_entry(state, _ERROR_KEY, widget_key, str(exc))
            else:
                _set_state_entry(state, _EDITING_KEY, widget_key, None)
                _set_state_entry(state, _PENDING_KEY, widget_key, None)
                _set_state_entry(state, _ERROR_KEY, widget_key, None)
                st.toast("Đã ghi phản hồi")
                st.rerun()
    with b2:
        if st.button("Bác bỏ", key=f"bac_bo__{widget_key}", width="stretch"):
            _set_state_entry(state, _PENDING_KEY, widget_key, "bac_bo")
            _set_state_entry(state, _ERROR_KEY, widget_key, None)
            st.rerun()
    with b3:
        if st.button("Cần sửa", key=f"can_sua__{widget_key}", width="stretch"):
            _set_state_entry(state, _PENDING_KEY, widget_key, "can_sua")
            _set_state_entry(state, _ERROR_KEY, widget_key, None)
            st.rerun()

    if pending_action in ("bac_bo", "can_sua"):
        action_label = label_of(NHAN_PHAN_HOI, str(pending_action))
        st.caption(f"Chọn lý do cho: {plain_label(action_label)}")
        reason_options = ["", *NHOM_LY_DO.keys()]
        chosen_group = st.selectbox(
            "Nhóm lý do (bắt buộc)",
            options=reason_options,
            format_func=lambda k: "— Chọn lý do —" if k == "" else label_of(NHOM_LY_DO, k),
            key=f"fb_group__{widget_key}",
        )
        note = st.text_input("Ghi chú (tuỳ chọn)", key=f"fb_note__{widget_key}")
        c_confirm, c_cancel = st.columns(2)
        with c_confirm:
            if st.button("Xác nhận ghi", key=f"fb_save__{widget_key}", width="stretch"):
                if not chosen_group:
                    st.warning("Vui lòng chọn một nhóm lý do trước khi ghi.")
                else:
                    clean_note = note.strip() or None
                    action_code: Literal["bac_bo", "can_sua"] = (
                        "bac_bo" if pending_action == "bac_bo" else "can_sua"
                    )
                    try:
                        _record_feedback(
                            ca_id,
                            row,
                            action_code,
                            chosen_group,
                            clean_note,
                            save_fn,
                        )
                    except Exception as exc:
                        _set_state_entry(state, _ERROR_KEY, widget_key, str(exc))
                    else:
                        _set_state_entry(state, _EDITING_KEY, widget_key, None)
                        _set_state_entry(state, _PENDING_KEY, widget_key, None)
                        _set_state_entry(state, _ERROR_KEY, widget_key, None)
                        st.toast("Đã ghi phản hồi")
                        st.rerun()
        with c_cancel:
            if st.button("Huỷ", key=f"fb_cancel__{widget_key}", width="stretch"):
                _set_state_entry(state, _PENDING_KEY, widget_key, None)
                _set_state_entry(state, _EDITING_KEY, widget_key, None)
                _set_state_entry(state, _ERROR_KEY, widget_key, None)
                st.rerun()

    latest_err = _state_map(state, _ERROR_KEY).get(widget_key) or inline_error
    if latest_err:
        st.error(f"Không ghi được phản hồi: {plain_label(str(latest_err))}")
