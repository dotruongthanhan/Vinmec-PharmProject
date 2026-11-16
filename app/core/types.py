"""Dữ liệu qua ranh giới lớp và bộ lọc dùng chung."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Chunk(BaseModel):
    """Đoạn nguồn có siêu dữ liệu truy vết."""

    model_config = ConfigDict(frozen=True)

    doan_trich_id: str
    tai_lieu_id: str
    muc_cha_id: str | None
    nhom_nguon: str
    nguon: str
    tang_tin_cay: int = Field(ge=1, le=4)
    hoat_chat_ids: list[str]
    muc: str
    duong_dan_muc: str
    loai_noi_dung: Literal["van_ban", "bang", "danh_sach", "dong_bang"]
    ngon_ngu: Literal["vi", "en"]
    phien_ban_nguon: str | None
    url_goc: str | None
    noi_dung_goc: str
    noi_dung_nhung: str


class SearchFilter(BaseModel):
    """Các điều kiện lọc kết hợp bằng phép và."""

    model_config = ConfigDict(frozen=True)

    nhom_nguon: str | None = None
    hoat_chat_ids: list[str] = Field(default_factory=list)
    muc: list[str] = Field(default_factory=list)


class RetrievalQuery(BaseModel):
    """Truy vấn với nhiều cách diễn đạt và bộ lọc."""

    model_config = ConfigDict(frozen=True)

    van_ban: list[str]
    bo_loc: SearchFilter
    k_query: int
    k_rerank: int


class ScoredChunk(BaseModel):
    """Đoạn nguồn cùng điểm và nguồn điểm."""

    model_config = ConfigDict(frozen=True)

    chunk: Chunk
    diem: float
    nguon_diem: Literal["tu_khoa", "vec_to", "rrf", "xep_hang_lai"]


class ChatMessage(BaseModel):
    """Một thông điệp gửi tới mô hình."""

    model_config = ConfigDict(frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str


class ToolResult(BaseModel):
    """Kết quả công cụ hoặc thông báo lỗi."""

    model_config = ConfigDict(frozen=True)

    ok: bool
    du_lieu: dict | list | None
    loi: str | None


def matches(chunk: Chunk, bo_loc: SearchFilter) -> bool:
    """Kiểm tra nhóm nguồn, giao hoạt chất và mục của đoạn."""
    return (
        (bo_loc.nhom_nguon is None or chunk.nhom_nguon == bo_loc.nhom_nguon)
        and (not bo_loc.hoat_chat_ids or bool(set(chunk.hoat_chat_ids) & set(bo_loc.hoat_chat_ids)))
        and (not bo_loc.muc or chunk.muc in bo_loc.muc)
    )
