"""Trạng thái chạy qua các nút của đồ thị thẩm định AI (chỉ sống trong một lượt chạy)."""

from typing import TypedDict

from app.core.types import Chunk
from app.domain.models import CaBenh
from app.llm.schema import KetQuaLLM
from app.orchestration.graph.result import AiRunResult
from app.pipeline import KetQuaThamDinh


class ThamDinhState(TypedDict, total=False):
    """Trạng thái đồ thị; mỗi nút chỉ trả phần trường mình thay đổi.

    Trạng thái không bao giờ được lưu hay gửi đi: đồ thị biên dịch không có checkpointer.
    """

    ca: CaBenh
    ket_qua_luat: KetQuaThamDinh
    doan: list[Chunk]
    canh_bao: list[str]
    ket_qua_llm: KetQuaLLM
    thoi_gian_bat_dau: float
    loi: str  # cảnh báo lỗi không mong muốn; có giá trị thì các nút sau bỏ qua việc của mình
    ket_qua: AiRunResult  # đầu ra cuối do nút hoan_tat dựng
