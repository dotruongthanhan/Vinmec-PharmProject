"""Lớp nền dữ liệu, ngữ cảnh thực thi và giao diện trừu tượng cho mọi công cụ agent."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agent.minh_hoa.models import BoDuLieu
from app.core.types import Chunk
from app.deid.session import DeidSession
from app.domain.models import CaBenh
from app.orchestration.ai_review import AiRunResult
from app.pipeline import KetQuaThamDinh

CheDo = Literal["ca", "chung"]


class CanCu(BaseModel):
    """Một đơn vị căn cứ do công cụ trả về để đưa sang bước kiểm chứng."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ma: str
    loai: Literal["doan", "bang", "tinh", "ca"]
    nhan: str
    doan: Chunk | None = None
    noi_dung: str | None = None


class KetQuaCongCu(BaseModel):
    """Kết quả chuẩn hoá sau khi chạy công cụ hoặc bị Gateway từ chối."""

    model_config = ConfigDict(extra="forbid")

    trang_thai: Literal["ok", "khong_co", "loi", "tu_choi"]
    noi_dung: str = ""
    can_cu: list[CanCu] = Field(default_factory=list)
    bo_du_lieu: list[BoDuLieu] = Field(default_factory=list)
    chi_tiet_tien_trinh: str | None = None
    ma_loi: str | None = None


@dataclass(frozen=True)
class ToolContext:
    """Ngữ cảnh bất biến của một lượt hỏi, giữ phạm vi ca và phiên che định danh."""

    vai_tro: str
    che_do: CheDo
    han_chot: float
    cau_hoi_goc: str
    lich_su_goc: tuple[tuple[str, str], ...] = ()
    ca: CaBenh | None = None
    ket_qua_luat: KetQuaThamDinh | None = None
    ai_result: AiRunResult | None = None
    nhan_dinh_id: str | None = None
    cac_ca: tuple[CaBenh, ...] = ()
    cac_ket_qua: Mapping[str, KetQuaThamDinh] = field(default_factory=dict)
    deid_session: DeidSession | None = None


class Tool(ABC):
    """Lớp cơ sở cho mọi công cụ chỉ đọc mà agent có thể gọi qua ToolGateway."""

    ten: ClassVar[str]
    ten_hien_thi: ClassVar[str]
    mo_ta: ClassVar[str]
    LuocDoThamSo: ClassVar[type[BaseModel]]
    che_do_cho_phep: ClassVar[frozenset[str]] = frozenset({"ca", "chung"})
    goi_ra_ngoai: ClassVar[bool] = False
    thoi_gian_toi_da: ClassVar[float] = 20.0
    so_can_cu_toi_da: ClassVar[int] = 20
    chi_doan_da_tra: ClassVar[bool] = False

    @abstractmethod
    def chay(
        self, tham_so: BaseModel, ctx: ToolContext, *, doan_goc: Chunk | None = None
    ) -> KetQuaCongCu:
        """Thực thi công cụ với tham số đã kiểm chứng và ngữ cảnh bất biến."""
