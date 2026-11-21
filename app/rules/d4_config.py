"""Mô hình pydantic, bộ nạp cấu hình và hàm dùng chung cho các luật đợt D4 (yếu tố 6)."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.bang_luat_store import BangLuatReadError, load_rule_data, register_cache_clear
from app.rules.types import CanCu, normalize_text

if TYPE_CHECKING:
    from app.kb.resolver.resolver import KetQuaPhanGiai

_LOGGER = logging.getLogger(__name__)
_KB_DIR = Path(__file__).resolve().parents[2] / "data" / "kb"
_DEFAULT_HEPATIC_PATH = _KB_DIR / "quy_tac_gan.json"
_DEFAULT_LAB_THRESHOLD_PATH = _KB_DIR / "nguong_xet_nghiem.json"
_DEFAULT_DRUG_DISEASE_PATH = _KB_DIR / "thuoc_benh_icd.json"

_EXCLUDED_KINDS = {"dich_truyen_dien_giai", "duoc_lieu"}

HepaticClass = Literal[
    "child_pugh_A",
    "child_pugh_B",
    "child_pugh_C",
    "nhe_vua",
    "nang",
    "khong_phan_loai",
]
HepaticAction = Literal[
    "chong_chi_dinh",
    "tranh_khong_khuyen_cao",
    "giam_lieu",
    "theo_doi",
    "khong_chinh_lieu",
    "khong_co_khuyen_cao_cu_the",
]
LabOperator = Literal["<", "<=", ">", ">=", "khoang"]
LabConditionKind = Literal[
    "canh_bao_khi_thoa",
    "canh_bao_khi_ngoai_khoang",
    "dieu_kien_khoi_dau",
]
LabSuggestedSeverity = Literal["nghiem_trong", "can_luu_y"]
DDInterSeverity = Literal["Major", "Moderate", "Minor"]


class D4SourceDetail(BaseModel):
    """Nguồn trích dẫn chi tiết từ nhãn cho các bảng tri thức D4."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    loai: str | None = None
    ten_nhan: str | None = None
    set_id: str | None = None
    trich_nguyen_van: str = ""
    url: str | None = None


class HepaticRule(BaseModel):
    """Một dòng quy tắc chỉnh liều theo suy gan trong bảng gan."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    ten_quoc_te: str
    hoat_chat_ids: tuple[str, ...] = ()
    phan_loai_gan: tuple[HepaticClass, ...] = ()
    hanh_dong_nhan: HepaticAction
    khuyen_cao: str
    trang_thai: str | None = None
    nguon_chi_tiet: tuple[D4SourceDetail, ...] = ()


class HepaticConfig(BaseModel):
    """Cấu hình toàn bộ bảng quy tắc chỉnh liều suy gan."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    phien_ban: str | None = None
    trang_thai: str | None = None
    ghi_chu: str | None = None
    quy_tac: tuple[HepaticRule, ...] = ()


class LabCondition(BaseModel):
    """Một điều kiện xét nghiệm đơn lẻ trong bảng ngưỡng xét nghiệm."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    ma_xet_nghiem: str
    toan_tu: LabOperator
    gia_tri: float
    gia_tri_den: float | None = None
    don_vi_nhan: str | None = None
    don_vi_ca: str | None = None
    he_so_ca_sang_nhan: float | None = None


class LabThresholdRule(BaseModel):
    """Một quy tắc ngưỡng xét nghiệm gắn với hoạt chất hoặc phối hợp."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    ten_quoc_te: str | None = None
    hoat_chat_ids: tuple[str, ...] = ()
    xet_nghiem: str
    dieu_kien: tuple[LabCondition, ...] = ()
    hanh_dong_nhan: str
    don_vi_nhan: str | None = None
    trang_thai: str | None = None
    nguon_chi_tiet: tuple[D4SourceDetail, ...] = ()
    kieu_dieu_kien: LabConditionKind | None = None
    muc_do_de_xuat: LabSuggestedSeverity | None = None
    dieu_kien_khac: str | None = None


class LabThresholdConfig(BaseModel):
    """Cấu hình toàn bộ bảng ngưỡng xét nghiệm theo nhãn."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    phien_ban: str | None = None
    trang_thai: str | None = None
    ghi_chu: str | None = None
    quy_tac: tuple[LabThresholdRule, ...] = ()


class DrugDiseasePair(BaseModel):
    """Một cặp thuốc – bệnh từ DDInter đã ánh xạ sang mã ICD-10."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    hoat_chat_id: str
    ddinter_id: str | None = None
    ten_benh: str
    ma_icd10: tuple[str, ...] = ()
    muc_do: DDInterSeverity
    noi_dung: str = ""
    url: str | None = None
    trang_thai: str | None = None


class DrugDiseaseConfig(BaseModel):
    """Cấu hình bảng thuốc – bệnh theo ICD-10."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    phien_ban: str | None = None
    trang_thai: str | None = None
    nguon: str | None = None
    ghi_chu: str | None = None
    cap_thuoc_benh: tuple[DrugDiseasePair, ...] = Field(default_factory=tuple)


@lru_cache(maxsize=1)
def _load_default_hepatic_config() -> HepaticConfig | None:
    """Đọc và lưu đệm bảng quy tắc gan mặc định từ tệp hoặc PostgreSQL."""
    return load_rule_data(
        "quy_tac_gan",
        _DEFAULT_HEPATIC_PATH,
        HepaticConfig.model_validate,
        logger=_LOGGER,
    )


register_cache_clear(_load_default_hepatic_config.cache_clear)


def load_hepatic_config(path: Path | None = None) -> HepaticConfig:
    """Nạp bảng quy tắc gan mặc định theo KB_SOURCE hoặc đường dẫn chỉ định."""
    if path is None or Path(path).resolve() == _DEFAULT_HEPATIC_PATH.resolve():
        loaded = _load_default_hepatic_config()
        if loaded is None:
            raise BangLuatReadError("Không nạp được bảng quy tắc gan mặc định.")
        return loaded
    return HepaticConfig.model_validate_json(Path(path).read_text(encoding="utf-8"))


def try_load_default_hepatic_config() -> HepaticConfig | None:
    """Thử nạp bảng quy tắc gan mặc định; trả None nếu thiếu tệp hoặc lỗi DB."""
    return _load_default_hepatic_config()


@lru_cache(maxsize=1)
def _load_default_lab_threshold_config() -> LabThresholdConfig | None:
    """Đọc và lưu đệm bảng ngưỡng xét nghiệm mặc định từ tệp hoặc PostgreSQL."""
    return load_rule_data(
        "nguong_xet_nghiem",
        _DEFAULT_LAB_THRESHOLD_PATH,
        LabThresholdConfig.model_validate,
        logger=_LOGGER,
    )


register_cache_clear(_load_default_lab_threshold_config.cache_clear)


def load_lab_threshold_config(path: Path | None = None) -> LabThresholdConfig:
    """Nạp bảng ngưỡng xét nghiệm mặc định theo KB_SOURCE hoặc đường dẫn chỉ định."""
    if path is None or Path(path).resolve() == _DEFAULT_LAB_THRESHOLD_PATH.resolve():
        loaded = _load_default_lab_threshold_config()
        if loaded is None:
            raise BangLuatReadError("Không nạp được bảng ngưỡng xét nghiệm mặc định.")
        return loaded
    return LabThresholdConfig.model_validate_json(Path(path).read_text(encoding="utf-8"))


def try_load_default_lab_threshold_config() -> LabThresholdConfig | None:
    """Thử nạp bảng ngưỡng xét nghiệm mặc định; trả None nếu thiếu tệp hoặc lỗi DB."""
    return _load_default_lab_threshold_config()


@lru_cache(maxsize=1)
def _load_default_drug_disease_config() -> DrugDiseaseConfig | None:
    """Đọc và lưu đệm bảng thuốc – bệnh mặc định từ tệp hoặc PostgreSQL."""
    return load_rule_data(
        "thuoc_benh_icd",
        _DEFAULT_DRUG_DISEASE_PATH,
        DrugDiseaseConfig.model_validate,
        logger=_LOGGER,
    )


register_cache_clear(_load_default_drug_disease_config.cache_clear)


def load_drug_disease_config(path: Path | None = None) -> DrugDiseaseConfig:
    """Nạp bảng thuốc – bệnh mặc định theo KB_SOURCE hoặc đường dẫn chỉ định."""
    if path is None or Path(path).resolve() == _DEFAULT_DRUG_DISEASE_PATH.resolve():
        loaded = _load_default_drug_disease_config()
        if loaded is None:
            raise BangLuatReadError("Không nạp được bảng thuốc – bệnh mặc định.")
        return loaded
    return DrugDiseaseConfig.model_validate_json(Path(path).read_text(encoding="utf-8"))


def try_load_default_drug_disease_config() -> DrugDiseaseConfig | None:
    """Thử nạp bảng thuốc – bệnh mặc định; trả None nếu thiếu tệp hoặc lỗi DB."""
    return _load_default_drug_disease_config()


def extract_resolved_ids(result: KetQuaPhanGiai) -> set[str]:
    """Lấy tập mã hoạt chất trên trục từ kết quả phân giải đã hoặc một phần nhận diện."""
    if result.trang_thai not in {"da_phan_giai", "mot_phan"}:
        return set()
    return {tp.hoat_chat_id for tp in result.thanh_phan if tp.hoat_chat_id}


def is_line_excluded(result: KetQuaPhanGiai) -> bool:
    """Kiểm tra dòng thuốc thuộc nhóm dịch truyền, điện giải hoặc dược liệu."""
    if result.trang_thai == "khong_ap_dung":
        return True
    return bool(result.thanh_phan) and all(tp.loai in _EXCLUDED_KINDS for tp in result.thanh_phan)


def format_fda_source_evidence(src: D4SourceDetail) -> CanCu:
    """Tạo căn cứ tài liệu theo chuẩn trích dẫn nhãn FDA cho các bảng D4."""
    ref = f"Nhãn FDA {src.ten_nhan or ''}".strip()
    if src.set_id:
        ref = f"{ref} (set_id={src.set_id})"
    url_part = f" — {src.url}" if src.url else ""
    return CanCu(
        loai="tai_lieu",
        ban_ghi_id=src.set_id,
        mo_ta=f'{ref}: "{src.trich_nguyen_van}"{url_part} (chờ dược sĩ duyệt)',
    )


def dedupe_evidences(evidences: list[CanCu]) -> list[CanCu]:
    """Loại bỏ căn cứ trùng lặp nhưng giữ nguyên thứ tự xuất hiện."""
    seen: set[tuple[str, str | None, str]] = set()
    unique: list[CanCu] = []
    for item in evidences:
        key = (item.loai, item.ban_ghi_id, item.mo_ta)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def rule_ingredient_key(
    hoat_chat_ids: tuple[str, ...],
    fallback_name: str | None,
) -> frozenset[str]:
    """Tạo khoá tập hoạt chất chuẩn hoá cho một nhóm quy tắc."""
    normalized = {normalize_text(item) for item in hoat_chat_ids if normalize_text(item)}
    if normalized:
        return frozenset(normalized)
    fallback = normalize_text(fallback_name)
    return frozenset({fallback}) if fallback else frozenset()


def display_name_for_ids(
    resolved: KetQuaPhanGiai,
    target_ids: frozenset[str],
    fallback: str | None = None,
) -> str:
    """Lấy tên hoạt chất hiển thị từ kết quả phân giải theo đúng thứ tự thành phần."""
    names = [
        tp.ten_inn
        for tp in resolved.thanh_phan
        if normalize_text(tp.hoat_chat_id) in target_ids and tp.ten_inn
    ]
    if names:
        return " + ".join(dict.fromkeys(names))
    if fallback:
        return fallback
    return ", ".join(sorted(target_ids))
