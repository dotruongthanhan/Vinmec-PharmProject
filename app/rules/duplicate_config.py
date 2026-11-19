"""Nạp bảng nhóm và ATC bổ sung qua bộ đọc cấu hình chung."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.config.settings import _read_yaml

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


@lru_cache(maxsize=1)
def load_duplicate_config(config_dir: Path = _CONFIG) -> DuplicateConfig:
    """Đọc một lần, không đọc biến môi trường."""
    return DuplicateConfig(
        nhom_dieu_tri=TreatmentGroups.model_validate(
            _read_yaml(config_dir / "nhom_dieu_tri_trung.yaml")
        ),
        atc_bo_sung=AtcSupplement.model_validate(_read_yaml(config_dir / "atc_bo_sung.yaml")),
    )
