"""Mô hình pydantic và bộ nạp bảng độc tính thuốc D6 (yếu tố 5)."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.db.bang_luat_store import BangLuatReadError, load_rule_data, register_cache_clear
from app.rules.types import normalize_text

_LOGGER = logging.getLogger(__name__)
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "kb" / "doc_tinh.json"


class ToxicitySource(BaseModel):
    """Nguồn trích dẫn nhãn FDA hoặc LiverTox cho một mục độc tính."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    loai: str
    ten_nhan: str | None = None
    set_id: str | None = None
    tep: str | None = None
    truong_nhan: str | None = None
    ma_chuyen_luan: str | None = None
    trich_nguyen_van: str = ""
    url: str = ""
    ngay_lay: str | None = None


class NephrotoxicEntry(BaseModel):
    """Hoạt chất có cảnh báo độc thận trong bảng D6."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    hoat_chat_id: str
    nhom: str | None = None
    nguon: tuple[ToxicitySource, ...] = ()
    trang_thai: str | None = None


class QtProlongationEntry(BaseModel):
    """Hoạt chất có cảnh báo kéo dài khoảng QT trên nhãn FDA."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    hoat_chat_id: str
    muc_nhan: str | None = None
    nguon: tuple[ToxicitySource, ...] = ()
    trang_thai: str | None = None


class NarrowTherapeuticEntry(BaseModel):
    """Hoạt chất có khoảng điều trị hẹp cần theo dõi nồng độ thuốc."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    hoat_chat_id: str
    ma_xet_nghiem_nong_do: tuple[str, ...] = ()
    nguon: tuple[ToxicitySource, ...] = ()
    trang_thai: str | None = None


class LiverToxEntry(BaseModel):
    """Hoạt chất được phân hạng độc gan theo LiverTox."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    hoat_chat_id: str
    likelihood_score: str
    nguon: tuple[ToxicitySource, ...] = ()
    trang_thai: str | None = None


class MissingToxicitySource(BaseModel):
    """Ghi nhận hoạt chất đã rà nhưng nguồn không có thông tin độc tính."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    hoat_chat_id: str
    danh_sach: str | None = None
    ly_do: str | None = None


class ToxicityConfig(BaseModel):
    """Cấu hình toàn bộ bảng tri thức độc tính thuốc D6."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    phien_ban: str = "D6-v1"
    ngay: str | None = None
    trang_thai: str | None = None
    ghi_chu: str | None = None
    doc_than: tuple[NephrotoxicEntry, ...] = ()
    keo_dai_qt: tuple[QtProlongationEntry, ...] = ()
    khoang_dieu_tri_hep: tuple[NarrowTherapeuticEntry, ...] = ()
    doc_gan_livertox: tuple[LiverToxEntry, ...] = ()
    khong_co_nguon: tuple[MissingToxicitySource, ...] = ()

    def nephrotoxic_map(self) -> dict[str, list[NephrotoxicEntry]]:
        """Lập chỉ mục danh sách độc thận theo mã hoạt chất chuẩn hoá."""
        grouped: dict[str, list[NephrotoxicEntry]] = {}
        for entry in self.doc_than:
            key = normalize_text(entry.hoat_chat_id)
            if key:
                grouped.setdefault(key, []).append(entry)
        return grouped

    def qt_map(self) -> dict[str, list[QtProlongationEntry]]:
        """Lập chỉ mục danh sách kéo dài QT theo mã hoạt chất chuẩn hoá."""
        grouped: dict[str, list[QtProlongationEntry]] = {}
        for entry in self.keo_dai_qt:
            key = normalize_text(entry.hoat_chat_id)
            if key:
                grouped.setdefault(key, []).append(entry)
        return grouped

    def narrow_map(self) -> dict[str, list[NarrowTherapeuticEntry]]:
        """Lập chỉ mục danh sách khoảng điều trị hẹp theo mã hoạt chất chuẩn hoá."""
        grouped: dict[str, list[NarrowTherapeuticEntry]] = {}
        for entry in self.khoang_dieu_tri_hep:
            key = normalize_text(entry.hoat_chat_id)
            if key:
                grouped.setdefault(key, []).append(entry)
        return grouped

    def livertox_map(self) -> dict[str, list[LiverToxEntry]]:
        """Lập chỉ mục danh sách LiverTox theo mã hoạt chất chuẩn hoá."""
        grouped: dict[str, list[LiverToxEntry]] = {}
        for entry in self.doc_gan_livertox:
            key = normalize_text(entry.hoat_chat_id)
            if key:
                grouped.setdefault(key, []).append(entry)
        return grouped


@lru_cache(maxsize=1)
def _load_default_toxicity_config() -> ToxicityConfig | None:
    """Đọc và lưu đệm bảng độc tính D6 mặc định từ tệp hoặc PostgreSQL."""
    return load_rule_data(
        "doc_tinh",
        _DEFAULT_CONFIG_PATH,
        ToxicityConfig.model_validate,
        logger=_LOGGER,
    )


register_cache_clear(_load_default_toxicity_config.cache_clear)


def load_toxicity_config(path: Path | None = None) -> ToxicityConfig:
    """Nạp bảng độc tính D6 mặc định theo KB_SOURCE hoặc đường dẫn chỉ định."""
    if path is None or Path(path).resolve() == _DEFAULT_CONFIG_PATH.resolve():
        loaded = _load_default_toxicity_config()
        if loaded is None:
            raise BangLuatReadError("Không nạp được bảng độc tính D6 mặc định.")
        return loaded
    return ToxicityConfig.model_validate_json(Path(path).read_text(encoding="utf-8"))


def try_load_default_toxicity_config() -> ToxicityConfig | None:
    """Thử nạp bảng độc tính D6 mặc định; trả None nếu thiếu tệp hoặc lỗi DB."""
    return _load_default_toxicity_config()
