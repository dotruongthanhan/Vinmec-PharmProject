"""Kiểu dữ liệu chuẩn cho phát hiện và hàm trợ giúp dùng chung của bộ luật."""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.domain.models import CaBenh, ChiTietYLenh, Thuoc


class CanCu(BaseModel):
    """Căn cứ truy vết cho một phát hiện của bộ luật."""

    loai: Literal["du_lieu", "tinh_toan", "tai_lieu"]
    ban_ghi_id: str | None = None
    mo_ta: str


class PhatHien(BaseModel):
    """Phát hiện có căn cứ do bộ luật sinh ra khi rà soát một ca bệnh."""

    ma_luat: str
    yeu_to: int = Field(ge=1, le=7)
    ket_luan: Literal["dat", "can_xem", "khong_du_du_lieu", "ngoai_hdsd"]
    muc_do: Literal["nghiem_trong", "can_luu_y", "thong_tin"] | None = None
    chi_tiet_y_lenh_id: list[str]
    mo_ta: str
    can_cu: list[CanCu]
    thong_tin_con_thieu: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_missing_data_invariants(self) -> Self:
        """Bảo đảm phát hiện thiếu dữ liệu có muc_do=None và nêu trường còn thiếu."""
        if self.ket_luan == "khong_du_du_lieu":
            if self.muc_do is not None:
                raise ValueError("ket_luan='khong_du_du_lieu' phải có muc_do=None")
            if not self.thong_tin_con_thieu:
                raise ValueError("ket_luan='khong_du_du_lieu' phải có thong_tin_con_thieu")
        return self


def normalize_text(value: str | None) -> str:
    """Chuẩn hoá chuỗi so sánh: bỏ khoảng trắng hai đầu và chuyển chữ thường."""
    return value.strip().lower() if value is not None else ""


def pending_lines(ca: CaBenh) -> list[ChiTietYLenh]:
    """Trả về danh sách các dòng y lệnh đang chờ duyệt."""
    return list(ca.y_lenh_cho_duyet.chi_tiet)


def effective_lines(ca: CaBenh) -> list[ChiTietYLenh]:
    """Trả về các dòng đang hiệu lực gồm dòng đang xét và thuốc đang dùng còn hiệu lực."""
    active_statuses = ("active", "pending")
    current = [line for line in ca.thuoc_dang_dung if line.trang_thai_dong in active_statuses]
    return [*ca.y_lenh_cho_duyet.chi_tiet, *current]


def line_label(line: ChiTietYLenh, thuoc_by_id: dict[str, Thuoc]) -> str:
    """Lấy tên hiển thị ngắn gọn cho một dòng chi tiết y lệnh."""
    if line.thuoc_id is not None and line.thuoc_id in thuoc_by_id:
        return thuoc_by_id[line.thuoc_id].ten_thuoc
    if line.ten_tu_do is not None and line.ten_tu_do.strip() != "":
        return line.ten_tu_do.strip()
    return line.chi_tiet_y_lenh_id
