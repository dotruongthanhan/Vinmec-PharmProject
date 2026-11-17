"""Kiểm thử hàm thuần quản lý trạng thái phiên làm việc."""

from app.pipeline import KetQuaThamDinh
from app.ui.services import TraLoi
from app.ui.state import (
    append_chat,
    clear_chat,
    get_cached_review,
    get_chat,
    get_queue_filter,
    get_selected,
    is_chat_visible,
    select_case,
    set_cached_review,
    set_chat_visible,
    set_queue_filter,
)


def test_get_selected_and_select_case() -> None:
    """get_selected chọn mã đầu khi chưa chọn hoặc mã cũ không còn hợp lệ."""
    state: dict[str, object] = {}

    assert get_selected(state, []) is None
    assert get_selected(state, ["DEMO-02", "DEMO-06"]) == "DEMO-02"

    select_case(state, "DEMO-06")
    assert get_selected(state, ["DEMO-02", "DEMO-06"]) == "DEMO-06"

    assert get_selected(state, ["DEMO-01", "DEMO-04"]) == "DEMO-01"


def test_chat_history_isolated_per_case() -> None:
    """Hội thoại của hai ca tách biệt và clear_chat chỉ xoá ca được chỉ định."""
    state: dict[str, object] = {}
    reply = TraLoi(trang_thai="chua_san_sang", noi_dung="Chưa nối hệ thống")

    append_chat(state, "DEMO-01", "user", "Câu hỏi 1")
    append_chat(state, "DEMO-01", "assistant", reply)
    append_chat(state, "DEMO-02", "user", "Câu hỏi 2")

    assert len(get_chat(state, "DEMO-01")) == 2
    assert get_chat(state, "DEMO-02") == [("user", "Câu hỏi 2")]

    clear_chat(state, "DEMO-01")
    assert get_chat(state, "DEMO-01") == []
    assert get_chat(state, "DEMO-02") == [("user", "Câu hỏi 2")]


def test_queue_filter_and_chat_visibility() -> None:
    """Bộ lọc hàng đợi và trạng thái thu gọn khung hỏi thêm được lưu đúng."""
    state: dict[str, object] = {}
    assert get_queue_filter(state) == "tat_ca"
    set_queue_filter(state, "can_xem")
    assert get_queue_filter(state) == "can_xem"

    assert is_chat_visible(state) is True
    set_chat_visible(state, False)
    assert is_chat_visible(state) is False


def test_cached_review_persists_per_case() -> None:
    """Kết quả thẩm định được lưu đệm riêng theo ca_id."""
    state: dict[str, object] = {}
    dummy = KetQuaThamDinh(ca_id="DEMO-01", chi_so=[], phat_hien=[], thoi_gian_ms=1.5)
    assert get_cached_review(state, "DEMO-01") is None

    set_cached_review(state, "DEMO-01", dummy)
    assert get_cached_review(state, "DEMO-01") is dummy
    assert get_cached_review(state, "DEMO-02") is None
