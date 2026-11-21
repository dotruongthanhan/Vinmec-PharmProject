"""Dựng đồ thị thẩm định AI dạng luồng thẳng bằng LangGraph.

Sơ đồ: START -> thu_thap_nguon -> tong_hop -> hoan_tat -> END

Danh sách nút và thứ tự cạnh chỉ khai báo ở `dung_danh_sach_nut` bên dưới.

Cách chèn một nút mới (ví dụ `tra_cuu_ngoai`, chỉ đi khi không đủ đoạn nguồn):
1. Viết lớp nút trong `nodes.py` theo mẫu `ThuThapNguon` (dùng `@an_toan`, trả dict các trường
   thay đổi). Nếu nút ghi trường mới, thêm trường đó vào `ThamDinhState` (`state.py`).
2. Thêm vào `dung_danh_sach_nut` một cặp `(TRA_CUU_NGOAI, TraCuuNgoai(...))` ngay giữa
   `THU_THAP_NGUON` và `TONG_HOP`; cạnh nối tự sinh theo thứ tự danh sách.
3. Nếu nút chỉ chạy có điều kiện (ví dụ khi `len(doan)` quá ít): trong `dung_do_thi` thay cạnh
   thẳng bằng `builder.add_conditional_edges(THU_THAP_NGUON, ham_chon, {...})`, hoặc cho nút tự
   trả `{}` khi không cần chạy; rồi cập nhật test thứ tự nút ở `tests/orchestration/test_graph.py`.
4. Giữ bất biến: nút không xoá hay hạ phát hiện của bộ luật, không ghi log dữ liệu ca.

Đồ thị biên dịch không có checkpointer nên không lưu trạng thái (chứa dữ liệu ca) ở bất cứ đâu.
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.llm.synthesizer import Synthesizer
from app.orchestration.evidence import EvidenceCollector
from app.orchestration.graph.nodes import HoanTat, NodeFn, ThuThapNguon, TongHop
from app.orchestration.graph.state import ThamDinhState

THU_THAP_NGUON = "thu_thap_nguon"
TONG_HOP = "tong_hop"
HOAN_TAT = "hoan_tat"


def dung_danh_sach_nut(
    collector: EvidenceCollector, synthesizer: Synthesizer
) -> list[tuple[str, NodeFn]]:
    """Danh sách nút theo đúng thứ tự chạy; mỗi cặp là (tên nút, đối tượng nút)."""
    return [
        (THU_THAP_NGUON, ThuThapNguon(collector)),
        (TONG_HOP, TongHop(synthesizer)),
        (HOAN_TAT, HoanTat(synthesizer)),
    ]


def dung_do_thi(collector: EvidenceCollector, synthesizer: Synthesizer) -> Any:
    """Dựng và biên dịch đồ thị luồng thẳng; không có checkpointer, không lưu trạng thái."""
    nodes = dung_danh_sach_nut(collector, synthesizer)
    builder = StateGraph(ThamDinhState)
    for name, node in nodes:
        builder.add_node(name, node)
    names = [name for name, _ in nodes]
    builder.add_edge(START, names[0])
    for current, following in zip(names, names[1:], strict=False):
        builder.add_edge(current, following)
    builder.add_edge(names[-1], END)
    return builder.compile()
