"""Công cụ dựng khối minh hoạ từ dữ liệu đã qua Gateway."""

from collections.abc import Mapping
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from app.agent.minh_hoa.kiem import LoiDacTa, kiem_dac_ta
from app.agent.minh_hoa.models import BoDuLieu, KhoiMinhHoa
from app.agent.tools.base import KetQuaCongCu, Tool, ToolContext


class ThamSoVeBieuDo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    dac_ta: dict[str, Any]


class VeBieuDo(Tool):
    """Chỉ sử dụng bộ dữ liệu và căn cứ của lượt hiện tại."""

    ten: ClassVar[str] = "ve_bieu_do"
    ten_hien_thi: ClassVar[str] = "Vẽ biểu đồ"
    mo_ta: ClassVar[str] = "Dựng minh hoạ từ các bộ dữ liệu và căn cứ của lượt."
    LuocDoThamSo: ClassVar[type[BaseModel]] = ThamSoVeBieuDo
    che_do_cho_phep: ClassVar[frozenset[str]] = frozenset({"ca"})

    def tao(
        self, tham_so: ThamSoVeBieuDo, data: Mapping[str, BoDuLieu], evidence: set[str]
    ) -> KhoiMinhHoa | LoiDacTa:
        return kiem_dac_ta(tham_so.dac_ta, data, evidence)

    def chay(self, tham_so: BaseModel, ctx: ToolContext) -> KetQuaCongCu:
        return KetQuaCongCu(trang_thai="tu_choi", ma_loi="thieu_ngu_canh", noi_dung="Cần Gateway.")
