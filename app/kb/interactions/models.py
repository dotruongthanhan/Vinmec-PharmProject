"""Các bản ghi DDInter đã gộp, giữ nguyên văn bản nguồn."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

Severity = Literal["Major", "Moderate", "Minor", "Unknown"]
SEVERITIES: tuple[Severity, ...] = ("Major", "Moderate", "Minor", "Unknown")


class PairRecord(BaseModel):
    """Một cặp hoạt chất chuẩn hóa theo thứ tự mã."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ddinter_id_a: str
    ddinter_id_b: str
    muc_do: Severity
    muc_do_so: int
    co_che: list[str]
    co_lech_muc: bool
    cac_muc_nguon: list[Severity]
    ma_trang_cap: list[int]
    hau_qua: str | None
    xu_tri: str | None
    tai_lieu: list[str]
    url_goc: str | None


class FoodRecord(BaseModel):
    """Tương tác thuốc–thức ăn từ bảng cấp thuốc."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ddinter_id: str
    thuc_an: str
    muc_do: Severity
    mo_ta: str | None
    xu_tri: str | None
    co_che: list[str]


class MatrixModel(BaseModel):
    """Chỉ nhận các trường trong hợp đồng ma trận v1.6."""

    model_config = ConfigDict(extra="forbid")


class ThuocMaTran(MatrixModel):
    chi_tiet_y_lenh_id: str
    ten: str
    nhom: Literal["cho_duyet", "dang_dung"]
    phan_giai: Literal["da_phan_giai", "mot_phan", "khong_nhan_dien", "khong_ap_dung"]
    hoat_chat: list[str]
    ly_do: str | None


class CapMaTran(MatrixModel):
    a: str
    b: str
    muc: Literal["nghiem_trong", "can_luu_y", "thieu_du_lieu", "khong_phat_hien", "khong_ap_dung"]
    nhan_dinh_id: str | None = None
    tom_tat: str | None
    ly_do: str | None


class TuongTacThucAn(MatrixModel):
    chi_tiet_y_lenh_id: str
    hoat_chat: str
    thuc_an: str
    muc: Literal["nghiem_trong", "can_luu_y", "thong_tin", "chua_ro"]
    mo_ta: str | None
    xu_tri: str | None


class MaTranTuongTac(MatrixModel):
    nguon: str
    ghi_chu: str
    thuoc: list[ThuocMaTran]
    cap: list[CapMaTran]
    thuc_an: list[TuongTacThucAn]
