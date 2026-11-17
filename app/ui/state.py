"""Hàm thuần quản lý trạng thái phiên làm việc trên MutableMapping."""

from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.pipeline import KetQuaThamDinh
    from app.ui.services import TraLoi

_SELECTED_KEY = "selected_ca_id"
_CHAT_KEY = "chat_by_case"
_FILTER_KEY = "queue_filter"
_REVIEWS_KEY = "reviews_by_case"
_SHOW_CHAT_KEY = "show_chat_panel"
_DEFAULT_FILTER = "tat_ca"


def get_selected(state: MutableMapping[str, Any], valid_ids: Sequence[str]) -> str | None:
    """Lấy mã ca đang chọn; nếu không còn hợp lệ thì chọn mã đầu danh sách."""
    if not valid_ids:
        return None
    current = state.get(_SELECTED_KEY)
    if isinstance(current, str) and current in valid_ids:
        return current
    first_id = valid_ids[0]
    state[_SELECTED_KEY] = first_id
    return first_id


def select_case(state: MutableMapping[str, Any], ca_id: str) -> None:
    """Cập nhật mã ca đang chọn trong trạng thái phiên."""
    state[_SELECTED_KEY] = ca_id


def get_chat(state: MutableMapping[str, Any], ca_id: str) -> list[tuple[str, TraLoi | str]]:
    """Lấy danh sách cặp (vai, nội dung) của hội thoại riêng cho một ca bệnh."""
    chats = state.get(_CHAT_KEY)
    if not isinstance(chats, dict):
        return []
    history = chats.get(ca_id)
    if not isinstance(history, list):
        return []
    return list(history)


def append_chat(
    state: MutableMapping[str, Any],
    ca_id: str,
    vai: str,
    noi_dung: TraLoi | str,
) -> None:
    """Thêm một lượt hỏi hoặc trả lời vào hội thoại của ca bệnh."""
    chats = state.get(_CHAT_KEY)
    if not isinstance(chats, dict):
        chats = {}
    history = chats.get(ca_id)
    if not isinstance(history, list):
        history = []
    else:
        history = list(history)
    history.append((vai, noi_dung))
    chats = dict(chats)
    chats[ca_id] = history
    state[_CHAT_KEY] = chats


def clear_chat(state: MutableMapping[str, Any], ca_id: str) -> None:
    """Xoá toàn bộ lịch sử hội thoại của một ca bệnh."""
    chats = state.get(_CHAT_KEY)
    if not isinstance(chats, dict) or ca_id not in chats:
        return
    updated = dict(chats)
    updated[ca_id] = []
    state[_CHAT_KEY] = updated


def get_queue_filter(state: MutableMapping[str, Any]) -> str:
    """Lấy mã bộ lọc hàng đợi hiện tại, mặc định là 'tat_ca'."""
    value = state.get(_FILTER_KEY)
    if isinstance(value, str) and value:
        return value
    return _DEFAULT_FILTER


def set_queue_filter(state: MutableMapping[str, Any], value: str) -> None:
    """Lưu mã bộ lọc hàng đợi vào trạng thái phiên."""
    state[_FILTER_KEY] = value


def get_cached_review(state: MutableMapping[str, Any], ca_id: str) -> KetQuaThamDinh | None:
    """Lấy kết quả thẩm định đã lưu đệm cho ca bệnh nếu có."""
    reviews = state.get(_REVIEWS_KEY)
    if not isinstance(reviews, dict):
        return None
    return reviews.get(ca_id)


def set_cached_review(
    state: MutableMapping[str, Any],
    ca_id: str,
    result: KetQuaThamDinh,
) -> None:
    """Lưu đệm kết quả thẩm định theo mã ca để tránh chạy lại khi bấm phản hồi."""
    reviews = state.get(_REVIEWS_KEY)
    updated = dict(reviews) if isinstance(reviews, dict) else {}
    updated[ca_id] = result
    state[_REVIEWS_KEY] = updated


def is_chat_visible(state: MutableMapping[str, Any]) -> bool:
    """Kiểm tra khung hỏi thêm có đang mở hay đang thu gọn."""
    value = state.get(_SHOW_CHAT_KEY)
    if isinstance(value, bool):
        return value
    return True


def set_chat_visible(state: MutableMapping[str, Any], visible: bool) -> None:
    """Bật hoặc thu gọn khung hỏi thêm."""
    state[_SHOW_CHAT_KEY] = visible
