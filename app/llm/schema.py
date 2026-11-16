"""Lược đồ dữ liệu dùng chung cho bước LLM tổng hợp và bước kiểm chứng."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import Chunk
from app.rules.types import PhatHien


class TrichDanNguon(BaseModel):
    """Câu trích nguyên văn gắn với mã đoạn nguồn."""

    model_config = ConfigDict(extra="forbid")

    doan_trich_id: str
    trich_nguyen_van: str


class NhanDinhDeXuat(BaseModel):
    """Một dòng nhận định hoặc diễn giải do LLM đề xuất."""

    model_config = ConfigDict(extra="forbid")

    chi_tiet_y_lenh_id: list[str]
    yeu_to: int
    ket_luan: Literal["dat", "can_xem", "khong_du_du_lieu", "ngoai_hdsd"]
    muc_do: Literal["nghiem_trong", "can_luu_y"] | None = None
    nhan_xet: str
    ban_ghi_ids: list[str]
    trich_dan: list[TrichDanNguon]
    thong_tin_con_thieu: list[str] = Field(default_factory=list)
    de_xuat: str | None = None
    bo_sung_cho_ma_luat: str | None = None


class KetQuaTongHop(BaseModel):
    """Danh sách đề xuất trả về từ bước tổng hợp LLM."""

    model_config = ConfigDict(extra="forbid")

    nhan_dinh: list[NhanDinhDeXuat]


class GoiCanCu(BaseModel):
    """Tập dữ liệu và đoạn nguồn đã chuẩn hoá mà LLM được phép dẫn."""

    model_config = ConfigDict(extra="forbid")

    ca_id: str
    van_ban_ca: str
    ban_ghi_ids: list[str]
    dong_y_lenh_ids: list[str]
    so_cho_phep: list[float]
    doan: list[Chunk] = Field(default_factory=list)


class NhanDinhDaKiem(BaseModel):
    """Kết quả kiểm chứng bằng code cho một đề xuất của LLM."""

    model_config = ConfigDict(extra="forbid")

    de_xuat: NhanDinhDeXuat
    dat: bool
    loi: list[str] = Field(default_factory=list)


class NhanDinhCuoi(BaseModel):
    """Một dòng nhận định cuối cùng sau khi ghép phát hiện luật và LLM."""

    model_config = ConfigDict(extra="forbid")

    nguon_goc: Literal["luat", "ai_da_kiem_chung", "ai_chua_kiem_chung"]
    phat_hien: PhatHien | None = None
    de_xuat: NhanDinhDeXuat | None = None
    dien_giai: NhanDinhDeXuat | None = None
    loi_kiem_chung: list[str] = Field(default_factory=list)


class KetQuaLLM(BaseModel):
    """Đầu ra tổng thể của bước tổng hợp và kiểm chứng LLM."""

    model_config = ConfigDict(extra="forbid")

    trang_thai: Literal["ok", "khong_co_llm", "loi_llm", "dau_ra_khong_hop_le"]
    nhan_dinh: list[NhanDinhCuoi]
    so_lan_goi: int
    canh_bao: list[str] = Field(default_factory=list)
    phien_ban_prompt: str
    mo_hinh: str | None = None


def json_schema_for_llm() -> dict:
    """Trả về lược đồ JSON của KetQuaTongHop để đưa cho mô hình."""
    return KetQuaTongHop.model_json_schema()
