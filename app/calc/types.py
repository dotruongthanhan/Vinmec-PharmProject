"""Kiểu dữ liệu và hàm kiểm tra miền hợp lệ cho mô-đun công thức lâm sàng."""

import math
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Sex = Literal["nam", "nu"]
WeightType = Literal["thuc_te", "ly_tuong", "hieu_chinh"]


class CalcInput(BaseModel):
    """Một đầu vào số liệu lâm sàng đã dùng để tính công thức."""

    ten: str
    gia_tri: float
    don_vi: str
    ban_ghi_id: str | None = None
    thoi_diem: datetime | None = None


class CalcResult(BaseModel):
    """Kết quả tính công thức lâm sàng kèm đầu vào và trích dẫn."""

    cong_thuc: str
    phien_ban: str
    ket_qua: float | None
    don_vi: str
    dau_vao: list[CalcInput]
    thieu_dau_vao: list[str]
    ghi_chu: list[str]
    tham_khao: str


def validate_range(
    name: str,
    value: float | None,
    min_val: float,
    max_val: float,
    *,
    strict_min: bool = False,
) -> None:
    """Kiểm tra giá trị số nằm trong miền hợp lệ, ném ValueError nếu ngoài miền."""
    if value is None:
        return
    if not math.isfinite(value):
        raise ValueError(f"Tham số {name} có giá trị không hợp lệ: {value}")
    too_low = value <= min_val if strict_min else value < min_val
    if too_low or value > max_val:
        op = "<" if strict_min else "<="
        raise ValueError(
            f"Tham số {name} ngoài miền hợp lệ ({min_val} {op} {name} <= {max_val}): {value}"
        )


def validate_sex(gioi_tinh: Sex | None) -> None:
    """Kiểm tra giới tính hợp lệ ('nam' hoặc 'nu')."""
    if gioi_tinh is not None and gioi_tinh not in ("nam", "nu"):
        raise ValueError(f"Tham số gioi_tinh không hợp lệ: {gioi_tinh!r}")
