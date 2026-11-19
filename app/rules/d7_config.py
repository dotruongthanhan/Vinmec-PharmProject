"""Tải và truy vấn bảng danh mục kháng sinh cần quản lý theo QĐ 5631/QĐ-BYT."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.db.bang_luat_store import BangLuatReadError, load_rule_data, register_cache_clear

_LOGGER = logging.getLogger(__name__)
DEFAULT_STEWARDSHIP_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "kb" / "khang_sinh_quan_ly.json"
)


class StewardshipSourceDoc(BaseModel):
    """Thông tin văn bản nguồn của bảng kháng sinh quản lý."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    so_hieu: str = "5631/QĐ-BYT"
    ngay: str | None = None
    tep: str | None = None
    ban_sao_thu_cap: bool = True
    url: str = ""


class StewardshipGroup(BaseModel):
    """Nhóm quản lý kháng sinh và yêu cầu nguyên văn từ văn bản."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    ma_nhom: str
    ten_nhom_van_ban: str
    yeu_cau: str
    trang_pdf: int = 0


class ManagedAntibiotic(BaseModel):
    """Một mục kháng sinh thuộc danh mục quản lý đã ánh xạ sang hoạt chất."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    ten_trong_van_ban: str
    hoat_chat_ids: tuple[str, ...]
    ma_nhom: str
    trang_pdf: int = 0
    trang_thai: str | None = None


class UnmappedAntibiotic(BaseModel):
    """Mục kháng sinh trong văn bản chưa ánh xạ được sang trục hoạt chất."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    ten_trong_van_ban: str
    ly_do: str


class StewardshipConfig(BaseModel):
    """Cấu hình bảng danh mục kháng sinh quản lý theo QĐ 5631/QĐ-BYT."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    phien_ban: str = "D7-v1"
    ngay: str | None = None
    trang_thai: str = "cho_duoc_si_duyet"
    nguon_van_ban: StewardshipSourceDoc
    ghi_chu: str | None = None
    nhom: tuple[StewardshipGroup, ...] = Field(default_factory=tuple)
    khang_sinh: tuple[ManagedAntibiotic, ...] = Field(default_factory=tuple)
    khong_anh_xa: tuple[UnmappedAntibiotic, ...] = Field(default_factory=tuple)

    def group_by_code(self) -> dict[str, StewardshipGroup]:
        """Tạo từ điển tra cứu nhóm quản lý theo mã nhóm."""
        return {group.ma_nhom: group for group in self.nhom}


@lru_cache(maxsize=1)
def _load_default_stewardship_config() -> StewardshipConfig | None:
    """Đọc và cache bảng kháng sinh quản lý mặc định từ tệp hoặc PostgreSQL."""
    return load_rule_data(
        "khang_sinh_quan_ly",
        DEFAULT_STEWARDSHIP_CONFIG_PATH,
        StewardshipConfig.model_validate,
        logger=_LOGGER,
    )


register_cache_clear(_load_default_stewardship_config.cache_clear)


def load_stewardship_config(path: Path | None = None) -> StewardshipConfig:
    """Nạp bảng kháng sinh quản lý mặc định theo KB_SOURCE hoặc đường dẫn chỉ định."""
    if path is None or Path(path).resolve() == DEFAULT_STEWARDSHIP_CONFIG_PATH.resolve():
        loaded = _load_default_stewardship_config()
        if loaded is None:
            raise BangLuatReadError("Không nạp được bảng kháng sinh quản lý mặc định.")
        return loaded
    return StewardshipConfig.model_validate_json(Path(path).read_text(encoding="utf-8"))


def try_load_default_stewardship_config() -> StewardshipConfig | None:
    """Thử nạp bảng kháng sinh quản lý mặc định; trả None nếu thiếu hoặc lỗi."""
    return _load_default_stewardship_config()
