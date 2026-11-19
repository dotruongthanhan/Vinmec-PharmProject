"""Tải và truy vấn hai bảng cấu hình D5: đường dùng hợp lệ và liều tối đa."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.db.bang_luat_store import BangLuatReadError, load_rule_data, register_cache_clear
from app.kb.names import normalize_key

_LOGGER = logging.getLogger(__name__)
_KB_DIR = Path(__file__).resolve().parents[2] / "data" / "kb"
_DEFAULT_ROUTE_PATH = _KB_DIR / "duong_dung_hop_le.json"
_DEFAULT_MAX_DOSE_PATH = _KB_DIR / "lieu_toi_da.json"

ROUTE_TO_FORM_GROUP: dict[str, str] = {
    "uong": "dang_uong",
    "ngam_duoi_luoi": "dang_uong",
    "tiem_tinh_mach": "dang_tiem_truyen",
    "truyen_tinh_mach": "dang_tiem_truyen",
    "tiem_bap": "dang_tiem_truyen",
    "tiem_duoi_da": "dang_tiem_truyen",
    "tiem_trong_ong_tuy": "dang_tiem_truyen",
    "tiem_ngoai_mang_cung": "dang_tiem_truyen",
    "dat_truc_trang": "dang_dat",
    "dat_am_dao": "dang_dat",
    "boi_ngoai_da": "dang_boi_ngoai_da",
    "nho_mat": "dang_nho_mat",
    "xit_mui": "dang_xit_mui",
}

_FALLBACK_ROUTE_MAP: dict[str, str | None] = {
    "boi": "boi_ngoai_da",
    "boi da": "boi_ngoai_da",
    "boi ngoai da": "boi_ngoai_da",
    "dat": None,
    "dat am dao": "dat_am_dao",
    "dat hau mon": "dat_truc_trang",
    "dat truc trang": "dat_truc_trang",
    "duong uong": "uong",
    "epidural": "tiem_ngoai_mang_cung",
    "hit": "hit",
    "hit qua duong ho hap": "hit",
    "im": "tiem_bap",
    "intrathecal": "tiem_trong_ong_tuy",
    "iv": "tiem_tinh_mach",
    "iv infusion": "truyen_tinh_mach",
    "iv push": "tiem_tinh_mach",
    "ivpb": "truyen_tinh_mach",
    "khi dung": "hit",
    "ngam duoi luoi": "ngam_duoi_luoi",
    "nho": "nho_mat",
    "nho mat": "nho_mat",
    "nho mui": "xit_mui",
    "nho tai": "nho_tai",
    "oral": "uong",
    "per os": "uong",
    "phun mu": "hit",
    "po": "uong",
    "sc": "tiem_duoi_da",
    "sq": "tiem_duoi_da",
    "sub q": "tiem_duoi_da",
    "subcutaneous": "tiem_duoi_da",
    "tb": "tiem_bap",
    "tdd": "tiem_duoi_da",
    "tiem bap": "tiem_bap",
    "tiem bap sau": "tiem_bap",
    "tiem duoi da": "tiem_duoi_da",
    "tiem ngoai mang cung": "tiem_ngoai_mang_cung",
    "tiem nhan mo": "tiem_trong_ong_tuy",
    "tiem tinh mach": "tiem_tinh_mach",
    "tiem tinh mach cham": "tiem_tinh_mach",
    "tiem tinh mach truc tiep": "tiem_tinh_mach",
    "tiem tm": "tiem_tinh_mach",
    "tiem trong ong tuy": "tiem_trong_ong_tuy",
    "tiem truyen": "truyen_tinh_mach",
    "tiem truyen tinh mach": "truyen_tinh_mach",
    "tiem tuy song": "tiem_trong_ong_tuy",
    "tm": "tiem_tinh_mach",
    "topical": "boi_ngoai_da",
    "tra mat": "nho_mat",
    "truyen": "truyen_tinh_mach",
    "truyen nho giot tinh mach": "truyen_tinh_mach",
    "truyen tinh mach": "truyen_tinh_mach",
    "truyen tm": "truyen_tinh_mach",
    "uong": "uong",
    "uong sau an": "uong",
    "uong truoc an": "uong",
    "xit mui": "xit_mui",
}

_FALLBACK_AMBIGUOUS_ROUTES: dict[str, str] = {
    "dat": "Phải hỏi: đặt trực tràng (dat_truc_trang) hay đặt âm đạo (dat_am_dao)",
}


class RouteCount(BaseModel):
    """Số lượng sản phẩm theo đường dùng gốc trên NDC."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    route: str
    so_san_pham: int | None = None


class RouteSource(BaseModel):
    """Nguồn căn cứ của một hàng đường dùng hợp lệ."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    loai: str
    tang_tin_cay: str | None = None
    so_san_pham_dav: int | None = None
    vi_du_so_dang_ky: str | None = None
    route_goc: tuple[RouteCount | str, ...] = ()
    truy_van: str | None = None
    ten_nhan: str | None = None
    set_id: str | None = None
    url: str | None = None
    url_api: str | None = None
    ghi_chu: str | None = None


class RouteNormalization(BaseModel):
    """Bảng ánh xạ chuẩn hoá đường dùng và danh sách từ mơ hồ."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    khoa_sang_ma: dict[str, str | None] = Field(default_factory=dict)
    tu_mo_ho: dict[str, str] = Field(default_factory=dict)


class RouteRule(BaseModel):
    """Một hàng đường dùng hợp lệ theo hoạt chất và nhóm dạng bào chế."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    ma_dong: str = ""
    hoat_chat_ids: tuple[str, ...]
    nhom_dang_bao_che: str
    ten_nhom_dang: str | None = None
    duong_dung_hop_le: tuple[str, ...] = ()
    muc_chac_chan: str | None = None
    nguon: tuple[RouteSource, ...] = ()
    ghi_chu: str | None = None
    trang_thai: str | None = None


class RouteConfig(BaseModel):
    """Cấu hình bảng đường dùng hợp lệ."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    ten: str = ""
    phien_ban: str = ""
    trang_thai: str = "cho_duoc_si_duyet"
    bang_chuan_hoa_duong_dung: RouteNormalization = RouteNormalization()
    nhom: tuple[RouteRule, ...] = ()

    def normalize_route(self, raw: str | None) -> tuple[str | None, str | None]:
        """Chuẩn hoá chuỗi đường dùng; trả về (mã chuẩn, lý do mơ hồ/lỗi nếu có)."""
        return normalize_route_with_table(
            raw,
            self.bang_chuan_hoa_duong_dung.khoa_sang_ma,
            self.bang_chuan_hoa_duong_dung.tu_mo_ho,
        )


class DoseLimit(BaseModel):
    """Ngưỡng liều tối đa theo giá trị và đơn vị."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    gia_tri: float
    don_vi: str


class PerKgLimit(BaseModel):
    """Ngưỡng liều tối đa theo cân nặng (mg/kg)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    lan_mg_kg: float | tuple[float, ...] | None = None
    ngay_mg_kg: float | tuple[float, ...] | None = None


class MaxDoseSource(BaseModel):
    """Nguồn trích dẫn của một hàng liều tối đa."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    loai: str = ""
    ten_nhan: str | None = None
    set_id: str | None = None
    muc_nhan: str | None = None
    trich_nguyen_van: str = ""
    url: str = ""
    url_api: str | None = None


class PopulationDefinition(BaseModel):
    """Định nghĩa điều kiện tuổi và cân nặng cho một mã đối tượng."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    tuoi_tu: float | None = None
    tuoi_den: float | None = None
    tuoi_tren: float | None = None
    tuoi_duoi: float | None = None
    bao_gom_can_duoi: bool = True
    bao_gom_can_tren: bool = True
    tuoi_thang_tu: float | None = None
    tuoi_thang_den: float | None = None
    tuoi_ngay_tu: float | None = None
    tuoi_ngay_den: float | None = None
    can_nang_tu: float | None = None
    can_nang_den: float | None = None
    can_nang_tren: float | None = None
    can_nang_duoi: float | None = None
    dieu_kien_khac: str | None = None


class MaxDoseRule(BaseModel):
    """Một hàng quy tắc liều tối đa theo hoạt chất, đường dùng và đối tượng."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    ma_dong: str = ""
    hoat_chat_ids: tuple[str, ...]
    duong_dung: tuple[str, ...]
    doi_tuong: str
    dieu_kien: str | None = None
    dieu_kien_khac: str | None = None
    loai_gioi_han: str = "toi_da_ro"
    lieu_toi_da_lan: DoseLimit | None = None
    lieu_toi_da_ngay: DoseLimit | None = None
    lieu_toi_da_tuan: DoseLimit | None = None
    theo_kg: PerKgLimit | None = None
    thuoc_dung_cung_hoat_chat_ids: tuple[str, ...] | None = None
    ghi_chu: str | None = None
    nguon: MaxDoseSource | None = None
    trang_thai: str | None = None


class MissingMaxDoseNote(BaseModel):
    """Lý do hoạt chất không có trần liều tối đa chung trong nguồn."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    hoat_chat_id: str
    co_dong_theo_nhom_dac_biet: tuple[str, ...] = ()
    ly_do: str


class MissingMaxDoseByRoute(BaseModel):
    """Cặp (hoạt chất, đường dùng) trong ca không có trần tối đa."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    hoat_chat_ids: tuple[str, ...]
    duong_dung: str


class MaxDoseConfig(BaseModel):
    """Cấu hình bảng liều tối đa."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    ten: str = ""
    phien_ban: str = ""
    trang_thai: str = "cho_duoc_si_duyet"
    doi_tuong_dinh_nghia: dict[str, PopulationDefinition] = Field(default_factory=dict)
    nhom: tuple[MaxDoseRule, ...] = ()
    khong_ghi_toi_da: tuple[MissingMaxDoseNote, ...] = ()
    khong_ghi_toi_da_theo_duong_trong_ca: tuple[MissingMaxDoseByRoute, ...] = ()


def normalize_route_with_table(
    raw: str | None,
    khoa_sang_ma: dict[str, str | None],
    tu_mo_ho: dict[str, str],
) -> tuple[str | None, str | None]:
    """Chuẩn hoá đường dùng theo bảng ánh xạ; trả về (mã chuẩn, lý do nếu không ra)."""
    key = normalize_key(raw or "")
    if not key:
        return None, None

    ambiguous_map = {normalize_key(k): v for k, v in tu_mo_ho.items()}
    if key in ambiguous_map:
        return None, ambiguous_map[key]

    route_map = {normalize_key(k): v for k, v in khoa_sang_ma.items()}
    if key not in route_map:
        return None, None

    mapped = route_map[key]
    if mapped is None:
        return None, None
    return mapped, None


def normalize_route_default(raw: str | None) -> tuple[str | None, str | None]:
    """Chuẩn hoá đường dùng theo bảng mặc định của kho KB (hoặc bảng dự phòng)."""
    cfg = try_load_default_route_config()
    if cfg is not None:
        return cfg.normalize_route(raw)
    return normalize_route_with_table(raw, _FALLBACK_ROUTE_MAP, _FALLBACK_AMBIGUOUS_ROUTES)


def is_same_route_or_iv(route_a: str, route_b: str) -> bool:
    """So khớp hai mã đường dùng chuẩn, coi tiêm tĩnh mạch và truyền tĩnh mạch tương đương."""
    if route_a == route_b:
        return True
    iv_family = {"tiem_tinh_mach", "truyen_tinh_mach"}
    return route_a in iv_family and route_b in iv_family


@lru_cache(maxsize=1)
def _load_default_route_config() -> RouteConfig | None:
    """Đọc và cache bảng đường dùng hợp lệ mặc định từ tệp hoặc PostgreSQL."""
    return load_rule_data(
        "duong_dung_hop_le",
        _DEFAULT_ROUTE_PATH,
        RouteConfig.model_validate,
        logger=_LOGGER,
    )


register_cache_clear(_load_default_route_config.cache_clear)


def load_route_config(path: Path | None = None) -> RouteConfig:
    """Nạp bảng đường dùng hợp lệ mặc định theo KB_SOURCE hoặc đường dẫn chỉ định."""
    if path is None or Path(path).resolve() == _DEFAULT_ROUTE_PATH.resolve():
        loaded = _load_default_route_config()
        if loaded is None:
            raise BangLuatReadError("Không nạp được bảng đường dùng hợp lệ mặc định.")
        return loaded
    return RouteConfig.model_validate_json(Path(path).read_text(encoding="utf-8"))


def try_load_default_route_config() -> RouteConfig | None:
    """Thử nạp bảng đường dùng hợp lệ mặc định; trả None nếu thiếu tệp hoặc lỗi DB."""
    return _load_default_route_config()


@lru_cache(maxsize=1)
def _load_default_max_dose_config() -> MaxDoseConfig | None:
    """Đọc và cache bảng liều tối đa mặc định từ tệp hoặc PostgreSQL."""
    return load_rule_data(
        "lieu_toi_da",
        _DEFAULT_MAX_DOSE_PATH,
        MaxDoseConfig.model_validate,
        logger=_LOGGER,
    )


register_cache_clear(_load_default_max_dose_config.cache_clear)


def load_max_dose_config(path: Path | None = None) -> MaxDoseConfig:
    """Nạp bảng liều tối đa mặc định theo KB_SOURCE hoặc đường dẫn chỉ định."""
    if path is None or Path(path).resolve() == _DEFAULT_MAX_DOSE_PATH.resolve():
        loaded = _load_default_max_dose_config()
        if loaded is None:
            raise BangLuatReadError("Không nạp được bảng liều tối đa mặc định.")
        return loaded
    return MaxDoseConfig.model_validate_json(Path(path).read_text(encoding="utf-8"))


def try_load_default_max_dose_config() -> MaxDoseConfig | None:
    """Thử nạp bảng liều tối đa mặc định; trả None nếu thiếu tệp hoặc lỗi DB."""
    return _load_default_max_dose_config()
