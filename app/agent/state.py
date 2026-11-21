"""Trạng thái và lược đồ kế hoạch của đồ thị agent hỏi đáp (chỉ sống trong một lượt)."""

from __future__ import annotations

from typing import Any, Literal, Self, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agent.tools.base import CanCu, ToolContext
from app.agent.tools.gateway import ToolGateway
from app.deid.session import DeidSession
from app.orchestration.ask import AskLLMOutput, AskResult, NguCanhCa


class LoiGoiCongCu(BaseModel):
    """Một lời gọi công cụ do mô hình đề xuất trong kế hoạch JSON."""

    model_config = ConfigDict(extra="forbid")

    cong_cu: str = Field(max_length=64)
    tham_so: dict[str, Any] = Field(default_factory=dict)


class KeHoachTacTu(BaseModel):
    """Kế hoạch một vòng của tác tử: gọi công cụ, trả lời, hỏi lại hoặc báo thiếu."""

    model_config = ConfigDict(extra="forbid")

    hanh_dong: Literal["goi_cong_cu", "tra_loi", "khong_du_can_cu", "hoi_lai"]
    goi: list[LoiGoiCongCu] = Field(default_factory=list, max_length=3)
    tra_loi: AskLLMOutput | None = None
    cau_hoi_lai: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _validate_action_payload(self) -> Self:
        """Bảo đảm trường đi kèm khớp đúng hành động đã chọn."""
        if self.hanh_dong == "goi_cong_cu" and not self.goi:
            raise ValueError("hanh_dong='goi_cong_cu' yêu cầu danh sách goi không rỗng")
        if self.hanh_dong == "tra_loi" and self.tra_loi is None:
            raise ValueError("hanh_dong='tra_loi' yêu cầu trường tra_loi")
        if self.hanh_dong == "hoi_lai" and (
            self.cau_hoi_lai is None or not self.cau_hoi_lai.strip()
        ):
            raise ValueError("hanh_dong='hoi_lai' yêu cầu trường cau_hoi_lai")
        return self


class HoiDapState(TypedDict, total=False):
    """Trạng thái đồ thị hỏi đáp LangGraph; không lưu checkpointer, chỉ sống trong lượt."""

    ctx: ToolContext
    cau_hoi_sach: str
    session: DeidSession
    cau_hoi_che: str
    lich_su_che: list[tuple[str, str]]
    ngu_canh: NguCanhCa
    can_cu: list[CanCu]
    ket_qua_cong_cu: list[str]
    so_vong: int
    luot_tac_tu: int
    so_lan_kiem_chung: int
    so_lan_sai_luoc_do: int
    loi_lan_truoc: str
    ke_hoach: KeHoachTacTu | None
    cong_cu_da_goi: list[str]
    gateway: ToolGateway
    thoi_gian_bat_dau: float
    ket_qua: AskResult
    can_du_phong: bool
    ly_do_du_phong: str
