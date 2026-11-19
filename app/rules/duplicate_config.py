"""Nạp bảng nhóm và ATC bổ sung qua bộ đọc cấu hình chung."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.config.settings import _read_yaml
from app.db.bang_luat_store import load_rule_data, register_cache_clear

_LOGGER = logging.getLogger(__name__)
_CONFIG = Path(__file__).resolve().parents[2] / "config/kb"


class TreatmentGroup(BaseModel):
    """Nhóm sàng lọc theo tiền tố ATC và cặp ngoại lệ trên trục."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ma_nhom: str
    ten: str
    tien_to_atc: list[str] = Field(min_length=1)
    tien_to_atc_loai_tru: list[str] = Field(default_factory=list)
    muc_do: Literal["nghiem_trong", "can_luu_y"]
    ly_do: str
    nguon: str
    ngoai_le: list[tuple[str, str]] = Field(default_factory=list)

    def matching_codes(self, codes: list[str]) -> list[str]:
        """Chỉ giữ mã thuộc tiền tố nhóm và không thuộc tiền tố loại trừ."""
        return [
            code
            for code in codes
            if code.startswith(tuple(self.tien_to_atc))
            and not (
                self.tien_to_atc_loai_tru and code.startswith(tuple(self.tien_to_atc_loai_tru))
            )
        ]


class TreatmentGroups(BaseModel):
    """Bảng nhóm đang chờ duyệt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trang_thai: Literal["cho_duoc_si_duyet"]
    nhom: list[TreatmentGroup] = Field(min_length=1)


class AtcSupplement(BaseModel):
    """Mã bổ sung và nguồn để truy vết."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trang_thai: Literal["cho_claude_kiem"]
    nguon: str
    ma_atc: dict[str, list[str]]


class DuplicateConfig(BaseModel):
    """Hai bảng cấu hình của yếu tố 2."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    nhom_dieu_tri: TreatmentGroups
    atc_bo_sung: AtcSupplement


_EMPTY_DUPLICATE_CONFIG = DuplicateConfig.model_construct(
    nhom_dieu_tri=TreatmentGroups.model_construct(trang_thai="cho_duoc_si_duyet", nhom=[]),
    atc_bo_sung=AtcSupplement(trang_thai="cho_claude_kiem", nguon="", ma_atc={}),
)


@lru_cache(maxsize=1)
def _load_default_duplicate_config() -> DuplicateConfig | None:
    """Nạp một lần hai bảng cấu hình yếu tố 2 từ YAML mặc định hoặc PostgreSQL."""
    groups = load_rule_data(
        "nhom_dieu_tri_trung",
        _CONFIG / "nhom_dieu_tri_trung.yaml",
        TreatmentGroups.model_validate,
        logger=_LOGGER,
        fmt="yaml",
    )
    supplement = load_rule_data(
        "atc_bo_sung",
        _CONFIG / "atc_bo_sung.yaml",
        AtcSupplement.model_validate,
        logger=_LOGGER,
        fmt="yaml",
    )
    if groups is None or supplement is None:
        return None
    return DuplicateConfig(nhom_dieu_tri=groups, atc_bo_sung=supplement)


register_cache_clear(_load_default_duplicate_config.cache_clear)


def try_load_default_duplicate_config() -> DuplicateConfig | None:
    """Thử nạp cấu hình yếu tố 2 mặc định; trả None nếu thiếu tệp hoặc lỗi DB."""
    return _load_default_duplicate_config()


def load_duplicate_config(config_dir: Path | None = _CONFIG) -> DuplicateConfig:
    """Nạp một lần từ YAML mặc định hoặc DB theo KB_SOURCE; lỗi trả bảng rỗng an toàn."""
    if config_dir is None or Path(config_dir).resolve() == _CONFIG.resolve():
        loaded = _load_default_duplicate_config()
        return loaded if loaded is not None else _EMPTY_DUPLICATE_CONFIG
    resolved = Path(config_dir)
    return DuplicateConfig(
        nhom_dieu_tri=TreatmentGroups.model_validate(
            _read_yaml(resolved / "nhom_dieu_tri_trung.yaml")
        ),
        atc_bo_sung=AtcSupplement.model_validate(_read_yaml(resolved / "atc_bo_sung.yaml")),
    )
