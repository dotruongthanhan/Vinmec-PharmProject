"""Mô hình dữ liệu, hằng số giới hạn và danh sách khoá thuộc tính cho phép của tracer."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_SPANS_PER_TRACE = 200
MAX_TRACE_BYTES = 256 * 1024
MAX_ATTRIBUTES_BYTES = 4096
MAX_REDACTED_CONTENT_CHARS = 2000
MAX_SPAN_NAME_CHARS = 120

LoaiVet = Literal["hoi_dap", "ai_review", "danh_gia"]
LoaiSpan = Literal[
    "node",
    "llm",
    "tool",
    "kiem_chung",
    "che_pii",
    "chan_dau_vao",
    "su_kien_bao_mat",
]
MucNoiDung = Literal["sieu_du_lieu", "noi_dung_da_che", "day_du"]

KHOA_THUOC_TINH_CHO_PHEP: dict[LoaiSpan, frozenset[str]] = {
    "node": frozenset(
        {
            "ma_buoc_tien_trinh",
            "so_vong",
            "luot",
            "so_nguon",
            "so_doan",
            "so_phat_hien",
            "hanh_dong",
            "ly_do_du_phong",
            "loai_ngoai_le",
            "buoc_tra_loi_chu",
            "ket_qua_tra_loi_trung_thuc",
            "so_cau_bi_loc",
        }
    ),
    "llm": frozenset(
        {
            "mo_hinh",
            "phien_ban_prompt",
            "token_vao",
            "token_ra",
            "token_suy_luan",
            "token_cache_trung",
            "tong_token",
            "chi_phi_uoc_tinh",
            "so_lan_thu_lai",
            "khoa_so",
            "so_khoa_da_thu",
            "ly_do_ket_thuc",
            "so_ky_tu_prompt",
            "bam_prompt",
            "ma_loi",
            "loai_ngoai_le",
        }
    ),
    "tool": frozenset(
        {
            "ten_cong_cu",
            "trang_thai_cong_cu",
            "ma_loi",
            "kich_thuoc_ket_qua",
            "bi_cat",
            "ma_can_cu",
            "so_can_cu",
            "khoa_tham_so",
            "bam_tham_so",
            "vai_tro",
            "che_do",
            "loai_ngoai_le",
            "ly_do_bo_bo_du_lieu",
            "phan",
            "so_dong_bo",
            "so_dong_bi_cat",
            "ly_do_cat_du_lieu",
            "kieu_dau",
            "so_lop",
            "so_phan_tu",
            "kich_thuoc_byte",
            "ly_do_tu_choi",
            "so_lan_trung_hinh",
        }
    ),
    "kiem_chung": frozenset(
        {
            "so_bi_chan",
            "so_dat",
            "tong_so",
            "ma_ly_do",
            "so_trich_dan_bi_loai",
            "trang_thai_ket_qua",
            "loai_ngoai_le",
        }
    ),
    "che_pii": frozenset(
        {
            "so_ma_tam",
            "loai_dinh_danh",
            "thanh_cong",
            "loai_ngoai_le",
        }
    ),
    "chan_dau_vao": frozenset(
        {
            "bi_chan",
            "nguon_kiem_tra",
            "loai_ngoai_le",
        }
    ),
    "su_kien_bao_mat": frozenset(
        {
            "loai_su_kien",
            "nguon",
            "ten_cong_cu",
            "ma_loi",
            "loai_ngoai_le",
        }
    ),
}


class SpanBanGhi(BaseModel):
    """Một bước trong cây vết tương thích khái niệm OpenTelemetry."""

    model_config = ConfigDict(extra="forbid")

    ma_vet: str
    ma_buoc: str
    ma_buoc_cha: str | None = None
    loai: LoaiSpan
    ten: str
    bat_dau: datetime
    thoi_gian_ms: float = Field(ge=0.0)
    trang_thai: str = "ok"
    thuoc_tinh: dict[str, Any] = Field(default_factory=dict)
    noi_dung: dict[str, Any] | None = None


class VetChay(BaseModel):
    """Bản ghi hoàn chỉnh một vết (tổng hợp + mảng span) để ghi một dòng JSONL."""

    model_config = ConfigDict(extra="forbid")

    ma_vet: str
    bat_dau: datetime
    ket_thuc: datetime
    thoi_gian_ms: float = Field(ge=0.0)
    loai: LoaiVet
    engine: str
    nguoi_dung_id: str | None = None
    vai_tro: str | None = None
    phien_id: str | None = None
    ca_bam: str | None = None
    phien_ban: dict[str, str] = Field(default_factory=dict)
    trang_thai_cuoi: str = "ok"
    tong_token_vao: int = Field(default=0, ge=0)
    tong_token_ra: int = Field(default=0, ge=0)
    chi_phi_uoc_tinh: float = Field(default=0.0, ge=0.0)
    so_tool: int = Field(default=0, ge=0)
    so_bi_chan: int = Field(default=0, ge=0)
    ma_loi: str | None = None
    muc_noi_dung: MucNoiDung = "sieu_du_lieu"
    vet_bi_cat: bool = False
    so_khoa_la_bi_bo: int = Field(default=0, ge=0)
    cac_buoc: list[SpanBanGhi] = Field(default_factory=list)
