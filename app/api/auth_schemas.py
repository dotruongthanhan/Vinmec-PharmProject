"""Mô hình trao đổi bổ sung của hợp đồng xác thực v1.3."""

from app.api.schemas import ApiModel


class NguoiDung(ApiModel):
    """Danh tính công khai đã được máy chủ xác thực."""

    id: str
    email: str | None
    vai_tro: str
    phien_id: str | None
