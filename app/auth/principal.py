"""Danh tính đã được xác thực."""

from pydantic import BaseModel, ConfigDict


class Principal(BaseModel):
    """Người gọi bất biến, truyền rõ ràng xuống dịch vụ."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    nguoi_dung_id: str
    email: str | None = None
    vai_tro: str
    phien_id: str | None = None
    het_han_luc: float | None = None
