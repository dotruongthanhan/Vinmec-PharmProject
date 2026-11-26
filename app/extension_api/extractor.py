"""Tách PII nhãn trường (0b) và điều phối 4 luồng Gemini song song (Giai đoạn 1) -> CaBenh."""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.errors import ProviderError
from app.db.timezone import VN_TZ
from app.deid.scrubber import TOKEN_PATTERN, DeidError, scrub_text
from app.deid.session import DeidSession
from app.domain.models import (
    CaBenh,
    ChanDoan,
    ChiTietYLenh,
    CoDia,
    DienBien,
    DiUng,
    DotDieuTri,
    HoatChat,
    KetQuaXetNghiem,
    KhangSinhDo,
    NguoiBenh,
    SinhHieu,
    ThanhPhan,
    Thuoc,
    TinhTrangDiUng,
    ViSinh,
    YLenh,
)
from app.kb.names import DrugNameIndex
from app.kb.resolver.matching import product_key

_LOGGER = logging.getLogger(__name__)
_ROOT = Path(__file__).resolve().parents[2]
_MAX_FIELD_LABEL_LEN = 80
_MAX_SECTION_TEXT_LEN = 40_000
_MIN_DT = datetime(2000, 1, 1, tzinfo=VN_TZ)

SchemaGroup = Literal["pii_xoa", "lam_sang_giu", "nghi_ngo_pii"]
_VALID_SCHEMA_GROUPS = frozenset({"pii_xoa", "lam_sang_giu", "nghi_ngo_pii"})
_VALID_IMAGE_PII_CODES = frozenset(
    {
        "ho_ten",
        "ngay_sinh",
        "so_cccd",
        "so_bhyt",
        "so_dien_thoai",
        "dia_chi",
        "ma_benh_nhan",
    }
)

# Sàn tất định nhãn PII tiếng Việt / tiếng Anh không thể bị mô hình bỏ sót.
_PII_FLOOR_TERMS = (
    "ho ten",
    "ho va ten",
    "ten benh nhan",
    "ngay sinh",
    "nam sinh",
    "cccd",
    "cmnd",
    "can cuoc",
    "chung minh",
    "bhyt",
    "so the",
    "bao hiem y te",
    "ma benh nhan",
    "ma bn",
    "pid",
    "patient id",
    "ma y te",
    "ma yt",
    "so luu tru",
    "hn",
    "mrn",
    "dia chi",
    "so nha",
    "thon pho",
    "xa phuong",
    "quan huyen",
    "tinh thanh",
    "dien thoai",
    "sdt",
    "so dien thoai",
    "phone",
    "email",
    "thu dien tu",
    "nguoi bao tin",
    "nguoi nha",
    "bo me",
    "ho ten bo",
    "ho ten me",
    "bac si dieu tri",
    "nguoi ke don",
    "nguoi lap phieu",
    "chu ky",
)

_CLINICAL_VITAL_ALIASES: dict[str, tuple[str, str]] = {
    "can nang": ("can_nang", "kg"),
    "weight": ("can_nang", "kg"),
    "can_nang": ("can_nang", "kg"),
    "chieu cao": ("chieu_cao", "cm"),
    "height": ("chieu_cao", "cm"),
    "chieu_cao": ("chieu_cao", "cm"),
    "mach": ("mach", "lần/phút"),
    "pulse": ("mach", "lần/phút"),
    "nhiet do": ("nhiet_do", "°C"),
    "nhiet_do": ("nhiet_do", "°C"),
    "temp": ("nhiet_do", "°C"),
    "huyet ap tam thu": ("huyet_ap_tam_thu", "mmHg"),
    "huyet_ap_tam_thu": ("huyet_ap_tam_thu", "mmHg"),
    "sbp": ("huyet_ap_tam_thu", "mmHg"),
    "huyet ap tam truong": ("huyet_ap_tam_truong", "mmHg"),
    "huyet_ap_tam_truong": ("huyet_ap_tam_truong", "mmHg"),
    "dbp": ("huyet_ap_tam_truong", "mmHg"),
    "nhip tho": ("nhip_tho", "lần/phút"),
    "nhip_tho": ("nhip_tho", "lần/phút"),
    "spo2": ("spo2", "%"),
}

_LAB_CODE_ALIASES: dict[str, str] = {
    "creatinin": "creatinin",
    "creatinine": "creatinin",
    "scr": "creatinin",
    "egfr": "egfr",
    "ure": "ure",
    "urea": "ure",
    "bun": "ure",
    "alt": "alt",
    "sgpt": "alt",
    "ast": "ast",
    "sgot": "ast",
    "bilirubin": "bilirubin_tp",
    "bilirubin tp": "bilirubin_tp",
    "bilirubin_tp": "bilirubin_tp",
    "albumin": "albumin",
    "inr": "inr",
    "natri": "natri",
    "na": "natri",
    "sodium": "natri",
    "kali": "kali",
    "k": "kali",
    "potassium": "kali",
    "calci": "calci",
    "ca": "calci",
    "calcium": "calci",
    "bach cau": "bach_cau",
    "wbc": "bach_cau",
    "tieu cau": "tieu_cau",
    "plt": "tieu_cau",
    "hemoglobin": "hemoglobin",
    "hb": "hemoglobin",
    "hgb": "hemoglobin",
    "crp": "crp",
    "procalcitonin": "procalcitonin",
    "pct": "procalcitonin",
    "qtc": "qtc",
}

_SECTION_BUCKET_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "labs_vitals",
        ("xet nghiem", "sinh hieu", "can lam sang", "vi sinh", "khang sinh do", "lab", "vital"),
    ),
    (
        "demographics_dx",
        ("hanh chinh", "chan doan", "co dia", "di ung", "quan ly nguoi benh", "tom tat"),
    ),
    (
        "meds_notes",
        ("y lenh", "thuoc", "phieu dieu tri", "dien bien", "hoi chan", "cham soc"),
    ),
)

_BLOCK_DELIMITER_RE = re.compile(r"<<<[A-Z0-9_]+|>>>")
_DEID_TOKEN_RE = re.compile(TOKEN_PATTERN)
_CLIENT_EXTRA_TOKEN_RE = re.compile(r"\[ID_\d+\]")
_REL_DATE_RE = re.compile(
    r"ng[aà]y\s*\+\s*(\d{1,5})(?:[^\d\n]{0,6}(\d{1,2}):(\d{2}))?",
    re.IGNORECASE,
)
_HHMM_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
_TOKEN_SEMANTIC_LABELS: dict[str, str] = {
    "TEN": "[đã che tên]",
    "NGAY": "[đã che ngày]",
    "BHYT": "[đã che bhyt]",
    "CCCD": "[đã che cccd]",
    "SDT": "[đã che sđt]",
    "HN": "[đã che mã]",
    "EMAIL": "[đã che email]",
    "DIACHI": "[đã che địa chỉ]",
    "MA": "[đã che mã]",
}


def _neutralize_deid_tokens(text: str) -> str:
    """Đổi mã tạm hai chiều ([NGAY_1], [TEN_1]...) sang nhãn một chiều không đụng TOKEN_PATTERN."""

    def _replace(match: re.Match[str]) -> str:
        kind = match.group(0)[1:].split("_", 1)[0]
        return _TOKEN_SEMANTIC_LABELS.get(kind, "[đã che định danh]")

    cleaned = _DEID_TOKEN_RE.sub(_replace, text)
    return _CLIENT_EXTRA_TOKEN_RE.sub("[đã che mã]", cleaned)


def _extract_relative_offset(item: dict[str, Any], iso_key: str) -> tuple[int, int, int] | None:
    """Đọc (delta_ngay, gio, phut) từ ngay_tuong_doi hoặc chuỗi 'Ngày +N HH:MM'."""
    raw_delta = item.get("ngay_tuong_doi")
    delta: int | None = None
    hour = 0
    minute = 0
    if isinstance(raw_delta, (int, float)) and not isinstance(raw_delta, bool):
        delta = max(0, int(raw_delta))
        raw_hm = str(item.get("gio_phut") or "").strip()
        hm_match = _HHMM_RE.fullmatch(raw_hm)
        if hm_match:
            h, m = int(hm_match.group(1)), int(hm_match.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59:
                hour, minute = h, m
        return (delta, hour, minute)

    raw_iso = item.get(iso_key)
    if isinstance(raw_iso, str):
        match = _REL_DATE_RE.search(raw_iso)
        if match:
            delta = max(0, int(match.group(1)))
            if match.group(2) and match.group(3):
                h, m = int(match.group(2)), int(match.group(3))
                if 0 <= h <= 23 and 0 <= m <= 59:
                    hour, minute = h, m
            return (delta, hour, minute)
    return None


def _resolve_item_dt(
    item: dict[str, Any],
    *,
    iso_key: str,
    synthetic_base: datetime,
    fallback: datetime,
) -> datetime:
    """Ưu tiên mốc ngày tương đối (Ngày +N) để giữ đúng chênh lệch ngày; sau đó mới đọc ISO."""
    rel = _extract_relative_offset(item, iso_key)
    if rel is not None:
        delta, hour, minute = rel
        return synthetic_base + timedelta(days=delta, hours=hour, minutes=minute)
    return _parse_dt(item.get(iso_key), fallback)


class GeminiClientProtocol(Protocol):
    """Giao diện tối thiểu để tiêm máy khách thật hoặc giả khi kiểm thử."""

    model: str

    def complete_json(
        self,
        system_prompt: str,
        user_text: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def complete_vision_json(
        self,
        system_prompt: str,
        user_text: str,
        image_bytes: bytes,
        mime_type: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class SchemaFieldDescriptor(BaseModel):
    """Mô tả một nhãn trường từ DOM (tuyệt đối không mang giá trị người bệnh)."""

    model_config = ConfigDict(extra="forbid")

    ten_nhan: str = Field(min_length=1, max_length=_MAX_FIELD_LABEL_LEN)
    kieu_dom: str = Field(default="dt_dd", max_length=40)
    ngu_canh_muc: str | None = Field(default=None, max_length=120)

    @field_validator("ten_nhan")
    @classmethod
    def _reject_pii_value_in_label(cls, value: str) -> str:
        """Chặn chuỗi mang dữ liệu định danh lọt vào tên nhãn trường."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("ten_nhan không được rỗng")
        try:
            has_pii = bool(scrub_text(cleaned).thay_the)
        except DeidError:
            raise ValueError("ten_nhan không được chứa mã tạm hoặc dữ liệu định danh") from None
        if has_pii:
            raise ValueError("ten_nhan chỉ được chứa tên nhãn trường, không chứa dữ liệu định danh")
        return cleaned


class ClassifiedField(BaseModel):
    """Kết quả phân loại một nhãn trường trả về cho trình duyệt lưu đệm."""

    model_config = ConfigDict(extra="forbid")

    ten_nhan: str
    nhom: SchemaGroup
    nguon: Literal["san_pii", "gemini", "mac_dinh_an_toan"]
    ly_do: str = ""


class EmrSectionPayload(BaseModel):
    """Một mục văn bản EMR đã được làm sạch PII tại trình duyệt."""

    model_config = ConfigDict(extra="forbid")

    tieu_de: str = Field(min_length=1, max_length=160)
    loai_muc: Literal["demographics_dx", "labs_vitals", "meds_notes", "other"] = "other"
    tab_id: int | None = None
    tab_title: str | None = Field(default=None, max_length=180)
    noi_dung: str = Field(min_length=1, max_length=_MAX_SECTION_TEXT_LEN)


class ExtractedCaseResult(BaseModel):
    """Đầu ra giai đoạn 1 gồm CaBenh chuẩn và các cảnh báo bóc tách."""

    model_config = ConfigDict(extra="forbid")

    ca_benh: CaBenh
    canh_bao: list[str] = Field(default_factory=list)
    canh_bao_pii_anh: list[str] = Field(default_factory=list)
    mo_hinh_da_dung: dict[str, str] = Field(default_factory=dict)
    thoi_gian_ms: float = 0.0


class EditableLinePatch(BaseModel):
    """Chỉnh sửa nhanh một dòng thuốc chờ duyệt trước khi chạy lại bộ luật."""

    model_config = ConfigDict(extra="forbid")

    chi_tiet_y_lenh_id: str = Field(min_length=1, max_length=64)
    ten_tu_do: str | None = Field(default=None, max_length=200)
    lieu_moi_lan: float | None = Field(default=None, ge=0.0, le=1_000_000.0)
    don_vi_lieu: str | None = Field(default=None, max_length=40)
    duong_dung: str | None = Field(default=None, max_length=64)
    tan_suat: str | None = Field(default=None, max_length=80)
    so_lan_moi_ngay: int | None = Field(default=None, ge=1, le=48)
    khoang_cach_gio: float | None = Field(default=None, gt=0.0, le=720.0)


class EditableLabPatch(BaseModel):
    """Bổ sung hoặc sửa nhanh một giá trị xét nghiệm."""

    model_config = ConfigDict(extra="forbid")

    ma_xet_nghiem: str = Field(min_length=1, max_length=64)
    ten_xet_nghiem: str | None = Field(default=None, max_length=120)
    gia_tri_so: float = Field(ge=-10_000.0, le=1_000_000.0)
    don_vi: str | None = Field(default=None, max_length=40)


class CaseRecalcPatch(BaseModel):
    """Tải trọng chỉnh sửa nhanh cho điểm cuối `/recalc`."""

    model_config = ConfigDict(extra="forbid")

    tuoi: int | None = Field(default=None, ge=0, le=120)
    gioi_tinh: Literal["nam", "nu"] | None = None
    can_nang_kg: float | None = Field(default=None, gt=0.2, le=400.0)
    chieu_cao_cm: float | None = Field(default=None, ge=20.0, le=250.0)
    tinh_trang_di_ung: Literal["co_di_ung", "khong_di_ung_da_hoi", "chua_co_thong_tin"] | None = (
        None
    )
    xet_nghiem: list[EditableLabPatch] = Field(default_factory=list, max_length=20)
    y_lenh: list[EditableLinePatch] = Field(default_factory=list, max_length=30)


def _fold_ascii(text: str) -> str:
    """Đưa chuỗi tiếng Việt về chữ thường ASCII không dấu để so khớp bền vững."""
    decomposed = unicodedata.normalize("NFKD", text)
    no_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    no_marks = no_marks.replace("đ", "d").replace("Đ", "D")
    return re.sub(r"[\s_:./-]+", " ", no_marks.lower()).strip()


def _load_prompt_text(rel_path: str) -> str:
    """Đọc tệp prompt của Extension theo đường dẫn tương đối từ gốc dự án."""
    path = Path(rel_path)
    if not path.is_absolute():
        path = _ROOT / path
    return path.read_text(encoding="utf-8")


def _strip_prompt_delimiters(text: str) -> str:
    """Gỡ các dấu phân khối có thể dùng cho prompt injection từ văn bản EMR."""
    return _BLOCK_DELIMITER_RE.sub("", text).strip()


def matches_pii_floor(label: str, section_hint: str | None = None) -> bool:
    """Kiểm tra nhãn có chắc chắn thuộc nhóm PII theo sàn tất định tiếng Việt không."""
    folded = _fold_ascii(label)
    if not folded:
        return True
    if any(
        folded == term
        or folded.startswith(f"{term} ")
        or folded.endswith(f" {term}")
        or f" {term} " in folded
        for term in _PII_FLOOR_TERMS
    ):
        return True
    if section_hint and "hanh chinh" in _fold_ascii(section_hint):
        # Trong phần Hành chính chỉ giữ lại tuổi, giới tính, cân nặng, chiều cao, đối tượng.
        clinical_admin = ("tuoi", "gioi tinh", "can nang", "chieu cao", "bmi", "nhom mau")
        if not any(term in folded for term in clinical_admin):
            return True
    return False


def classify_schema_fields(
    fields: Sequence[SchemaFieldDescriptor],
    gemini_client: GeminiClientProtocol | None,
    prompt_path: str,
) -> list[ClassifiedField]:
    """Phân loại chỉ tên nhãn trường EMR qua sàn PII tất định + Gemini 3.5 Flash Lite."""
    unique_fields: list[SchemaFieldDescriptor] = []
    seen: set[str] = set()
    for field in fields:
        cleaned = field.ten_nhan.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique_fields.append(field.model_copy(update={"ten_nhan": cleaned}))

    needs_llm: list[SchemaFieldDescriptor] = []
    floor_hits: dict[str, ClassifiedField] = {}
    for item in unique_fields:
        if matches_pii_floor(item.ten_nhan, item.ngu_canh_muc):
            floor_hits[item.ten_nhan] = ClassifiedField(
                ten_nhan=item.ten_nhan,
                nhom="pii_xoa",
                nguon="san_pii",
                ly_do="Trùng từ khoá định danh cá nhân",
            )
        else:
            needs_llm.append(item)

    llm_map: dict[str, tuple[SchemaGroup, str]] = {}
    if needs_llm and gemini_client is not None:
        system_prompt = _load_prompt_text(prompt_path)
        payload = [
            {
                "ten_nhan": item.ten_nhan,
                "kieu_dom": item.kieu_dom,
                "ngu_canh_muc": item.ngu_canh_muc,
            }
            for item in needs_llm
        ]
        user_text = (
            f"Phân loại danh sách nhãn trường dưới đây (không có dữ liệu bệnh nhân):\n{payload}"
        )
        try:
            raw = gemini_client.complete_json(system_prompt=system_prompt, user_text=user_text)
            rows = raw.get("phan_loai") if isinstance(raw, dict) else None
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    label = row.get("ten_nhan")
                    group = row.get("nhom")
                    reason = str(row.get("ly_do") or "")[:120]
                    if isinstance(label, str) and group in _VALID_SCHEMA_GROUPS:
                        llm_map[label.strip()] = (group, reason)
        except Exception as exc:
            _LOGGER.warning("Phân loại schema bằng Gemini thất bại (%s)", type(exc).__name__)

    results: list[ClassifiedField] = []
    for item in unique_fields:
        if item.ten_nhan in floor_hits:
            results.append(floor_hits[item.ten_nhan])
            continue
        hit = llm_map.get(item.ten_nhan)
        if hit is not None:
            results.append(
                ClassifiedField(
                    ten_nhan=item.ten_nhan,
                    nhom=hit[0],
                    nguon="gemini",
                    ly_do=hit[1],
                )
            )
        else:
            # Mặc định an toàn: nếu mô hình không trả lời hoặc trả sai định dạng -> bỏ cắt.
            results.append(
                ClassifiedField(
                    ten_nhan=item.ten_nhan,
                    nhom="nghi_ngo_pii",
                    nguon="mac_dinh_an_toan",
                    ly_do="Chưa xác nhận được nhãn lâm sàng, loại bỏ để an toàn PII",
                )
            )
    return results


def _route_section_bucket(
    section: EmrSectionPayload,
) -> Literal["demographics_dx", "labs_vitals", "meds_notes"]:
    """Định tuyến từng mục EMR về đúng luồng trích xuất song song."""
    if section.loai_muc != "other":
        return section.loai_muc
    folded = _fold_ascii(section.tieu_de)
    for bucket, keywords in _SECTION_BUCKET_PATTERNS:
        if any(kw in folded for kw in keywords):
            return bucket
    return "meds_notes"


def _parse_dt(raw: Any, fallback: datetime) -> datetime:
    """Chuyển chuỗi ngày giờ sang đối tượng có múi giờ VN (+07)."""
    if isinstance(raw, str) and raw.strip():
        candidate = raw.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=VN_TZ)
            else:
                dt = dt.astimezone(VN_TZ)
            if dt >= _MIN_DT:
                return dt
        except ValueError:
            pass
        for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%d-%m-%Y %H:%M", "%d-%m-%Y"):
            try:
                return datetime.strptime(raw.strip(), fmt).replace(tzinfo=VN_TZ)
            except ValueError:
                continue
    return fallback


def _safe_float(val: Any) -> float | None:
    """Ép kiểu số an toàn, hỗ trợ dấu phẩy thập phân."""
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.strip().replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _safe_int(val: Any) -> int | None:
    """Ép kiểu số nguyên an toàn."""
    num = _safe_float(val)
    if num is None:
        return None
    return int(round(num))


def _canonical_vital_kind(raw_kind: Any, raw_unit: Any) -> tuple[str, str]:
    """Chuẩn hoá mã sinh hiệu và đơn vị mặc định khớp với app/calc."""
    folded = _fold_ascii(str(raw_kind or ""))
    if folded in _CLINICAL_VITAL_ALIASES:
        canonical, default_unit = _CLINICAL_VITAL_ALIASES[folded]
        unit = (
            str(raw_unit).strip()
            if isinstance(raw_unit, str) and raw_unit.strip()
            else default_unit
        )
        return canonical, unit
    slug = re.sub(r"[^a-z0-9]+", "_", folded).strip("_") or "sinh_hieu_khac"
    unit = str(raw_unit).strip() if isinstance(raw_unit, str) and raw_unit.strip() else ""
    return slug, unit


_LAB_CONTAINS_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("creatinin", ("creatinin", "creatinine", "scr")),
    ("egfr", ("egfr", "gfr")),
    ("ure", ("ure", "urea", "bun")),
    ("alt", ("alt", "sgpt", "gpt")),
    ("ast", ("ast", "sgot", "got")),
    ("bilirubin_tp", ("bilirubin",)),
    ("albumin", ("albumin",)),
    ("inr", ("inr",)),
    ("natri", ("natri", "sodium")),
    ("kali", ("kali", "potassium")),
    ("calci", ("calci", "calcium")),
    ("bach_cau", ("bach cau", "wbc", "leukocyte")),
    ("tieu_cau", ("tieu cau", "plt", "platelet")),
    ("hemoglobin", ("hemoglobin", "hgb")),
    ("crp", ("crp",)),
    ("procalcitonin", ("procalcitonin",)),
    ("qtc", ("qtc",)),
)


def _canonical_lab_code(raw_code: Any, raw_name: Any) -> str:
    """Chuẩn hoá mã xét nghiệm về mã quy ước của bộ luật (creatinin, alt, ast, ...)."""
    for candidate in (raw_code, raw_name):
        folded = _fold_ascii(str(candidate or ""))
        if folded in _LAB_CODE_ALIASES:
            return _LAB_CODE_ALIASES[folded]
        for target, keywords in _LAB_CONTAINS_ALIASES:
            if any(
                folded == kw
                or folded.startswith(f"{kw} ")
                or folded.endswith(f" {kw}")
                or f" {kw} " in folded
                for kw in keywords
            ):
                return target
    source = str(raw_code or raw_name or "xet_nghiem").strip()
    slug = re.sub(r"[^a-z0-9]+", "_", _fold_ascii(source)).strip("_")
    return slug or "xet_nghiem"


def _norm_product_kind(raw: Any) -> Literal["thuoc", "tpcn", "dinh_duong", "khac"]:
    val = str(raw or "thuoc").strip().lower()
    if val in {"thuoc", "tpcn", "dinh_duong", "khac"}:
        return val  # type: ignore[return-value]
    return "thuoc"


def _build_order_line(
    raw: dict[str, Any],
    *,
    line_id: str,
    status: Literal["active", "pending"],
    now: datetime,
) -> ChiTietYLenh | None:
    """Chuyển bản ghi thuốc thô từ Vision/EMR thành ChiTietYLenh hợp lệ."""
    name_raw = raw.get("ten_thuoc") or raw.get("ten_tu_do")
    if not isinstance(name_raw, str) or not name_raw.strip():
        return None
    ham_luong = raw.get("ham_luong")
    display_name = name_raw.strip()
    if (
        isinstance(ham_luong, str)
        and ham_luong.strip()
        and ham_luong.strip().lower() not in display_name.lower()
    ):
        display_name = f"{display_name} {ham_luong.strip()}"

    return ChiTietYLenh(
        chi_tiet_y_lenh_id=line_id,
        thuoc_id=None,
        ten_tu_do=_neutralize_deid_tokens(display_name)[:220],
        loai_san_pham=_norm_product_kind(raw.get("loai_san_pham")),
        lieu_moi_lan=_safe_float(raw.get("lieu_moi_lan")),
        don_vi_lieu=str(raw.get("don_vi_lieu")).strip() if raw.get("don_vi_lieu") else None,
        tan_suat=str(raw.get("tan_suat")).strip() if raw.get("tan_suat") else None,
        so_lan_moi_ngay=_safe_int(raw.get("so_lan_moi_ngay")),
        khoang_cach_gio=_safe_float(raw.get("khoang_cach_gio")),
        duong_dung=str(raw.get("duong_dung")).strip() if raw.get("duong_dung") else None,
        cach_dung=_neutralize_deid_tokens(str(raw.get("cach_dung")).strip())
        if raw.get("cach_dung")
        else None,
        bat_dau=_parse_dt(raw.get("bat_dau_iso"), now),
        trang_thai_dong=status,
    )


def extract_to_case(
    *,
    ca_id: str,
    sections: Sequence[EmrSectionPayload],
    oh_image_bytes: bytes | None,
    oh_image_mime: str | None,
    vision_client: GeminiClientProtocol | None,
    emr_client: GeminiClientProtocol | None,
    vision_prompt_path: str,
    emr_prompt_path: str,
    max_workers: int = 4,
    now: datetime | None = None,
) -> ExtractedCaseResult:
    """Chạy song song tối đa 4 worker Gemini (1 Vision OH + 3 Text EMR) để dựng CaBenh."""
    reference_now = (now or datetime.now(VN_TZ)).astimezone(VN_TZ)
    deid = DeidSession()

    # Tầng bảo vệ phụ tại server: trung hòa mã tạm client,
    # chạy DeidSession bắt PII sót rồi trung hòa 1 chiều.
    buckets: dict[str, list[str]] = {
        "demographics_dx": [],
        "labs_vitals": [],
        "meds_notes": [],
    }
    for sec in sections:
        pre_cleaned = _neutralize_deid_tokens(_strip_prompt_delimiters(sec.noi_dung))
        scrubbed = deid.scrub(pre_cleaned, patterns=True)
        cleaned_body = _neutralize_deid_tokens(scrubbed)
        cleaned_title = _neutralize_deid_tokens(_strip_prompt_delimiters(sec.tieu_de))
        bucket = _route_section_bucket(sec)
        buckets[bucket].append(f"### {cleaned_title}\n{cleaned_body}")

    vision_prompt = _load_prompt_text(vision_prompt_path) if oh_image_bytes else ""
    emr_prompt = _load_prompt_text(emr_prompt_path)

    warnings: list[str] = []
    models_used: dict[str, str] = {}

    def _run_oh_vision() -> dict[str, Any]:
        assert oh_image_bytes is not None
        assert vision_client is not None
        models_used["oh_vision"] = vision_client.model
        return vision_client.complete_vision_json(
            system_prompt=vision_prompt,
            user_text="Trích xuất toàn bộ y lệnh chờ duyệt từ ảnh chụp bảng thuốc OH đính kèm.",
            image_bytes=oh_image_bytes,
            mime_type=oh_image_mime or "image/png",
        )

    def _run_emr_bucket(bucket_name: str, text_block: str) -> dict[str, Any]:
        assert emr_client is not None
        models_used[f"emr_{bucket_name}"] = emr_client.model
        user_msg = f"nhom_dich = {bucket_name}\n\nDữ liệu EMR đã che định danh:\n{text_block}"
        return emr_client.complete_json(system_prompt=emr_prompt, user_text=user_msg)

    vision_data: dict[str, Any] = {}
    emr_data: dict[str, dict[str, Any]] = {}

    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 4))) as pool:
        vision_future: Future[dict[str, Any]] | None = None
        if oh_image_bytes is not None:
            if vision_client is None:
                warnings.append("Chưa cấu hình GEMINI_API_KEY cho bước đọc ảnh OH.")
            else:
                vision_future = pool.submit(_run_oh_vision)

        emr_futures: dict[str, Future[dict[str, Any]]] = {}
        for bucket_name, items in buckets.items():
            if not items:
                continue
            if emr_client is None:
                continue
            emr_futures[bucket_name] = pool.submit(_run_emr_bucket, bucket_name, "\n\n".join(items))

        if vision_future is not None:
            try:
                vision_data = vision_future.result()
            except (ProviderError, Exception) as exc:
                _LOGGER.warning("Worker Vision OH gặp lỗi (%s)", type(exc).__name__)
                warnings.append("Không đọc được ảnh chụp y lệnh OH từ Gemini Vision.")

        for bucket_name, fut in emr_futures.items():
            try:
                emr_data[bucket_name] = fut.result()
            except (ProviderError, Exception) as exc:
                _LOGGER.warning("Worker EMR %s gặp lỗi (%s)", bucket_name, type(exc).__name__)
                warnings.append(f"Trích xuất nhóm {bucket_name} chưa hoàn tất.")

    if emr_client is None and any(buckets.values()):
        warnings.append("Chưa cấu hình GEMINI_API_KEY cho bước chuẩn hoá EMR.")

    return _assemble_case(
        ca_id=ca_id,
        vision_data=vision_data,
        emr_data=emr_data,
        warnings=warnings,
        models_used=models_used,
        now=reference_now,
    )


def _assemble_case(
    *,
    ca_id: str,
    vision_data: dict[str, Any],
    emr_data: dict[str, dict[str, Any]],
    warnings: list[str],
    models_used: dict[str, str],
    now: datetime,
) -> ExtractedCaseResult:
    """Hợp nhất kết quả 4 luồng về CaBenh hợp chuẩn Pydantic v2."""
    demo = emr_data.get("demographics_dx", {})
    labs_raw = emr_data.get("labs_vitals", {})
    meds_raw = emr_data.get("meds_notes", {})

    # 1. Nhân khẩu & Đợt điều trị
    raw_patient = demo.get("nguoi_benh") if isinstance(demo.get("nguoi_benh"), dict) else {}
    tuoi = _safe_int(raw_patient.get("tuoi"))
    if tuoi is not None and not (0 <= tuoi <= 120):
        tuoi = None
    gioi_raw = str(raw_patient.get("gioi_tinh") or "").strip().lower()
    gioi_tinh: Literal["nam", "nu"] | None = (
        gioi_raw if gioi_raw in {"nam", "nu"} else None  # type: ignore[assignment]
    )

    raw_stay = demo.get("dot_dieu_tri") if isinstance(demo.get("dot_dieu_tri"), dict) else {}
    khoa = (
        str(vision_data.get("khoa_ke_don") or raw_stay.get("khoa_dieu_tri") or "").strip()
        or "Chưa rõ khoa"
    )
    loai_dt_raw = str(raw_stay.get("loai_dieu_tri") or "noi_tru").strip().lower()
    loai_dieu_tri: Literal["noi_tru", "ngoai_tru"] = (
        "ngoai_tru" if loai_dt_raw == "ngoai_tru" else "noi_tru"
    )

    # Tính mốc neo giả lập theo độ lệch ngày lớn nhất (Ngày +N) để giữ đúng chênh lệch ngày.
    all_offsets: list[int] = []
    if isinstance(raw_stay, dict):
        stay_rel = _extract_relative_offset(raw_stay, "thoi_diem_bat_dau_iso")
        if stay_rel is not None:
            all_offsets.append(stay_rel[0])
    for group_items, iso_key in (
        (labs_raw.get("sinh_hieu") or [], "thoi_diem_iso"),
        (labs_raw.get("xet_nghiem") or [], "thoi_diem_iso"),
        (labs_raw.get("vi_sinh") or [], "thoi_diem_iso"),
        (meds_raw.get("dien_bien") or [], "thoi_diem_iso"),
        (meds_raw.get("thuoc_dang_dung") or [], "bat_dau_iso"),
    ):
        for item in group_items:
            if isinstance(item, dict):
                rel = _extract_relative_offset(item, iso_key)
                if rel is not None:
                    all_offsets.append(rel[0])
    max_offset = max(all_offsets, default=0)
    synthetic_base = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=max_offset
    )
    stay_dt = (
        _resolve_item_dt(
            raw_stay,
            iso_key="thoi_diem_bat_dau_iso",
            synthetic_base=synthetic_base,
            fallback=now,
        )
        if isinstance(raw_stay, dict)
        else now
    )

    # 2. Dị ứng (đảm bảo bất biến _check_allergy_consistency)
    di_ung_list: list[DiUng] = []
    raw_allergies = demo.get("di_ung") if isinstance(demo.get("di_ung"), list) else []
    for idx, item in enumerate(raw_allergies, start=1):
        if not isinstance(item, dict) or not str(item.get("tac_nhan") or "").strip():
            continue
        loai_ta = str(item.get("loai_tac_nhan") or "thuoc").strip().lower()
        if loai_ta not in {"thuoc", "thuc_an", "khac"}:
            loai_ta = "thuoc"
        di_ung_list.append(
            DiUng(
                di_ung_id=f"DU-{idx}",
                tac_nhan=_neutralize_deid_tokens(str(item["tac_nhan"]).strip()),
                loai_tac_nhan=loai_ta,  # type: ignore[arg-type]
                phan_ung=_neutralize_deid_tokens(str(item.get("phan_ung")).strip())
                if item.get("phan_ung")
                else None,
                muc_do=str(item.get("muc_do")).strip() if item.get("muc_do") else None,
            )
        )
    allergy_status_raw = str(demo.get("tinh_trang_di_ung") or "chua_co_thong_tin").strip()
    if di_ung_list:
        allergy_status: Literal["co_di_ung", "khong_di_ung_da_hoi", "chua_co_thong_tin"] = (
            "co_di_ung"
        )
    elif allergy_status_raw == "khong_di_ung_da_hoi":
        allergy_status = "khong_di_ung_da_hoi"
    else:
        allergy_status = "chua_co_thong_tin"

    # 3. Chẩn đoán & Cơ địa
    chan_doan: list[ChanDoan] = []
    for idx, item in enumerate(demo.get("chan_doan") or [], start=1):
        if not isinstance(item, dict) or not str(item.get("noi_dung") or "").strip():
            continue
        dx_kind: Literal["chinh", "kem"] = "chinh" if item.get("loai") == "chinh" else "kem"
        chan_doan.append(
            ChanDoan(
                chan_doan_id=f"CD-{idx}",
                ma_icd10=str(item.get("ma_icd10")).strip() if item.get("ma_icd10") else None,
                noi_dung=_neutralize_deid_tokens(str(item["noi_dung"]).strip()),
                loai=dx_kind,
            )
        )

    co_dia: list[CoDia] = []
    valid_codia = {"mang_thai", "cho_con_bu", "suy_than", "suy_gan", "hau_phau", "khac"}
    for item in demo.get("co_dia") or []:
        if not isinstance(item, dict):
            continue
        cd_kind = str(item.get("loai") or "khac").strip().lower()
        if cd_kind not in valid_codia:
            cd_kind = "khac"
        cd_status = str(item.get("trang_thai") or "chua_ro").strip().lower()
        if cd_status not in {"co", "khong", "chua_ro"}:
            cd_status = "chua_ro"
        co_dia.append(
            CoDia(
                loai=cd_kind,  # type: ignore[arg-type]
                trang_thai=cd_status,  # type: ignore[arg-type]
                gia_tri=_neutralize_deid_tokens(str(item.get("gia_tri")).strip())
                if item.get("gia_tri")
                else None,
            )
        )

    # 4. Sinh hiệu, Xét nghiệm, Vi sinh
    sinh_hieu: list[SinhHieu] = []
    for idx, item in enumerate(labs_raw.get("sinh_hieu") or [], start=1):
        if not isinstance(item, dict):
            continue
        val = _safe_float(item.get("gia_tri"))
        if val is None:
            continue
        kind, unit = _canonical_vital_kind(item.get("loai"), item.get("don_vi"))
        sinh_hieu.append(
            SinhHieu(
                sinh_hieu_id=f"SH-{idx}",
                loai=kind,
                gia_tri=val,
                don_vi=unit,
                thoi_diem_do=_resolve_item_dt(
                    item,
                    iso_key="thoi_diem_iso",
                    synthetic_base=synthetic_base,
                    fallback=now - timedelta(minutes=idx),
                ),
            )
        )

    xet_nghiem: list[KetQuaXetNghiem] = []
    for idx, item in enumerate(labs_raw.get("xet_nghiem") or [], start=1):
        if not isinstance(item, dict):
            continue
        num_val = _safe_float(item.get("gia_tri_so"))
        text_val = (
            _neutralize_deid_tokens(str(item.get("gia_tri_text")).strip())
            if item.get("gia_tri_text")
            else None
        )
        if num_val is None and not text_val:
            continue
        code = _canonical_lab_code(item.get("ma_xet_nghiem"), item.get("ten_xet_nghiem"))
        name = _neutralize_deid_tokens(str(item.get("ten_xet_nghiem") or code).strip())
        xet_nghiem.append(
            KetQuaXetNghiem(
                xet_nghiem_id=f"XN-{idx}",
                ma_xet_nghiem=code,
                ten_xet_nghiem=name,
                gia_tri_so=num_val,
                gia_tri_text=text_val,
                don_vi=str(item.get("don_vi")).strip() if item.get("don_vi") else None,
                nguong_duoi=_safe_float(item.get("nguong_duoi")),
                nguong_tren=_safe_float(item.get("nguong_tren")),
                thoi_diem_ket_qua=_resolve_item_dt(
                    item,
                    iso_key="thoi_diem_iso",
                    synthetic_base=synthetic_base,
                    fallback=now - timedelta(minutes=idx),
                ),
            )
        )

    vi_sinh: list[ViSinh] = []
    for idx, item in enumerate(labs_raw.get("vi_sinh") or [], start=1):
        if not isinstance(item, dict) or not str(item.get("benh_pham") or "").strip():
            continue
        ksd_rows: list[KhangSinhDo] = []
        vi_sinh.append(
            ViSinh(
                vi_sinh_id=f"VS-{idx}",
                benh_pham=_neutralize_deid_tokens(str(item["benh_pham"]).strip()),
                vi_khuan=_neutralize_deid_tokens(str(item.get("vi_khuan")).strip())
                if item.get("vi_khuan")
                else None,
                thoi_diem_lay_mau=_resolve_item_dt(
                    item,
                    iso_key="thoi_diem_iso",
                    synthetic_base=synthetic_base,
                    fallback=now - timedelta(hours=idx),
                ),
                khang_sinh_do=ksd_rows,
            )
        )

    # 5. Thuốc đang dùng, Diễn biến, Y lệnh chờ duyệt (OH Vision ưu tiên, fallback EMR)
    thuoc_dang_dung: list[ChiTietYLenh] = []
    for idx, item in enumerate(meds_raw.get("thuoc_dang_dung") or [], start=1):
        if not isinstance(item, dict):
            continue
        active_dt = _resolve_item_dt(
            item,
            iso_key="bat_dau_iso",
            synthetic_base=synthetic_base,
            fallback=now - timedelta(days=1),
        )
        line = _build_order_line(item, line_id=f"DD-{idx}", status="active", now=active_dt)
        if line is not None:
            thuoc_dang_dung.append(line)

    dien_bien: list[DienBien] = []
    for idx, item in enumerate(meds_raw.get("dien_bien") or [], start=1):
        if not isinstance(item, dict) or not str(item.get("noi_dung") or "").strip():
            continue
        dien_bien.append(
            DienBien(
                dien_bien_id=f"DB-{idx}",
                loai_ho_so=str(item.get("loai_ho_so") or "dien_bien").strip(),
                noi_dung=_neutralize_deid_tokens(str(item["noi_dung"]).strip()),
                thoi_diem_ghi=_resolve_item_dt(
                    item,
                    iso_key="thoi_diem_iso",
                    synthetic_base=synthetic_base,
                    fallback=now - timedelta(hours=idx),
                ),
            )
        )

    vision_lines = vision_data.get("y_lenh") if isinstance(vision_data.get("y_lenh"), list) else []
    emr_pending = (
        meds_raw.get("y_lenh_tu_emr") if isinstance(meds_raw.get("y_lenh_tu_emr"), list) else []
    )
    raw_pending = vision_lines if vision_lines else emr_pending

    pending_lines: list[ChiTietYLenh] = []
    for idx, item in enumerate(raw_pending, start=1):
        if not isinstance(item, dict):
            continue
        line = _build_order_line(item, line_id=f"YL-{idx}", status="pending", now=now)
        if line is not None:
            pending_lines.append(line)

    image_pii_raw = vision_data.get("canh_bao_pii_trong_anh")
    image_pii_codes = [
        str(code).strip()
        for code in (image_pii_raw if isinstance(image_pii_raw, list) else [])
        if str(code).strip() in _VALID_IMAGE_PII_CODES
    ]

    if not pending_lines:
        raise ValueError(
            "Chưa tìm thấy dòng thuốc nào trong y lệnh chờ duyệt (ảnh OH hoặc tab EMR)."
        )

    luong_raw = str(vision_data.get("luong_duyet") or "").strip().lower()
    luong_duyet: Literal["truc_tiep", "hau_kiem"] = (
        "hau_kiem" if luong_raw == "hau_kiem" else "truc_tiep"
    )

    main_dx = next((cd.noi_dung for cd in chan_doan if cd.loai == "chinh"), None)
    mo_ta = main_dx or f"Ca trích xuất từ trình duyệt ({len(pending_lines)} thuốc chờ duyệt)"

    # Gắn hoạt chất từ từ điển cục bộ để các luật chạy chính xác cả khi ngoại tuyến.
    name_index = DrugNameIndex.load()
    entry_by_id = {
        str(entry["hoat_chat_id"]): entry
        for entry in getattr(name_index, "_entries", [])
        if isinstance(entry, dict) and entry.get("hoat_chat_id")
    }
    hoat_chat_map: dict[str, HoatChat] = {}
    thuoc_catalog: list[Thuoc] = []

    def _enrich_lines(lines: list[ChiTietYLenh], prefix: str) -> list[ChiTietYLenh]:
        enriched: list[ChiTietYLenh] = []
        for idx, line in enumerate(lines, start=1):
            label = line.ten_tu_do or ""
            resolved_ids = name_index.resolve(product_key(label)) or name_index.resolve(label)
            if not resolved_ids:
                enriched.append(line)
                continue
            components: list[ThanhPhan] = []
            for hid in resolved_ids:
                if hid not in hoat_chat_map:
                    meta = entry_by_id.get(hid, {})
                    hoat_chat_map[hid] = HoatChat(
                        hoat_chat_id=hid,
                        ten_hoat_chat=str(meta.get("ten_inn") or hid),
                        ten_quoc_te=str(meta.get("ten_inn") or hid).lower(),
                        nhom_duoc_ly=str(meta["nhom"]) if meta.get("nhom") else None,
                    )
                components.append(
                    ThanhPhan(
                        hoat_chat_id=hid,
                        ham_luong_thanh_phan=line.lieu_moi_lan,
                        don_vi=line.don_vi_lieu,
                    )
                )
            thuoc_id = f"TH-{prefix}-{idx}"
            thuoc_catalog.append(
                Thuoc(
                    thuoc_id=thuoc_id,
                    ten_thuoc=label,
                    duong_dung=line.duong_dung,
                    thanh_phan=components,
                )
            )
            enriched.append(line.model_copy(update={"thuoc_id": thuoc_id}))
        return enriched

    thuoc_dang_dung = _enrich_lines(thuoc_dang_dung, "DD")
    pending_lines = _enrich_lines(pending_lines, "YL")

    case = CaBenh(
        ca_id=ca_id,
        mo_ta_ngan=mo_ta[:200],
        nguoi_benh=NguoiBenh(
            nguoi_benh_id=f"NB-{ca_id}",
            tuoi=tuoi,
            gioi_tinh=gioi_tinh,
        ),
        tinh_trang_di_ung=TinhTrangDiUng(
            trang_thai=allergy_status,
            nguon="trinh_duyet_extension",
        ),
        di_ung=di_ung_list,
        dot_dieu_tri=DotDieuTri(
            dot_dieu_tri_id=f"DOT-{ca_id}",
            khoa_dieu_tri=_neutralize_deid_tokens(khoa),
            loai_dieu_tri=loai_dieu_tri,
            thoi_diem_bat_dau=stay_dt,
        ),
        chan_doan=chan_doan,
        co_dia=co_dia,
        sinh_hieu=sinh_hieu,
        xet_nghiem=xet_nghiem,
        vi_sinh=vi_sinh,
        dien_bien=dien_bien,
        thuoc_dang_dung=thuoc_dang_dung,
        y_lenh_cho_duyet=YLenh(
            y_lenh_id=f"YL-{ca_id}",
            khoa_ke_don=khoa,
            luong_duyet=luong_duyet,
            thoi_diem_ke=now,
            chi_tiet=pending_lines,
        ),
        danh_muc_thuoc=thuoc_catalog,
        danh_muc_hoat_chat=list(hoat_chat_map.values()),
    )

    return ExtractedCaseResult(
        ca_benh=case,
        canh_bao=warnings,
        canh_bao_pii_anh=image_pii_codes,
        mo_hinh_da_dung=models_used,
    )


def apply_case_patch(
    case: CaBenh,
    patch: CaseRecalcPatch,
    *,
    now: datetime | None = None,
) -> CaBenh:
    """Áp dụng bản sửa nhanh của dược sĩ lên bản sao CaBenh trong RAM."""
    updated = case.model_copy(deep=True)
    ref_now = (now or datetime.now(VN_TZ)).astimezone(VN_TZ)

    if patch.tuoi is not None:
        updated.nguoi_benh.tuoi = patch.tuoi
    if patch.gioi_tinh is not None:
        updated.nguoi_benh.gioi_tinh = patch.gioi_tinh

    for vital_kind, value, unit in (
        ("can_nang", patch.can_nang_kg, "kg"),
        ("chieu_cao", patch.chieu_cao_cm, "cm"),
    ):
        if value is None:
            continue
        existing = [item for item in updated.sinh_hieu if item.loai != vital_kind]
        existing.append(
            SinhHieu(
                sinh_hieu_id=f"SH-EDIT-{vital_kind.upper()}",
                loai=vital_kind,
                gia_tri=value,
                don_vi=unit,
                thoi_diem_do=ref_now,
            )
        )
        updated.sinh_hieu = existing

    if patch.tinh_trang_di_ung is not None:
        if patch.tinh_trang_di_ung == "co_di_ung" and not updated.di_ung:
            updated.di_ung = [
                DiUng(
                    di_ung_id="DU-EDIT-1",
                    tac_nhan="Dị ứng (dược sĩ bổ sung)",
                    loai_tac_nhan="khac",
                )
            ]
        elif patch.tinh_trang_di_ung != "co_di_ung":
            updated.di_ung = []
        updated.tinh_trang_di_ung = updated.tinh_trang_di_ung.model_copy(
            update={"trang_thai": patch.tinh_trang_di_ung}
        )

    if patch.xet_nghiem:
        patched_codes = {
            _canonical_lab_code(item.ma_xet_nghiem, item.ten_xet_nghiem)
            for item in patch.xet_nghiem
        }
        kept_labs = [lab for lab in updated.xet_nghiem if lab.ma_xet_nghiem not in patched_codes]
        for idx, item in enumerate(patch.xet_nghiem, start=1):
            code = _canonical_lab_code(item.ma_xet_nghiem, item.ten_xet_nghiem)
            kept_labs.append(
                KetQuaXetNghiem(
                    xet_nghiem_id=f"XN-EDIT-{code}-{idx}",
                    ma_xet_nghiem=code,
                    ten_xet_nghiem=item.ten_xet_nghiem or code,
                    gia_tri_so=item.gia_tri_so,
                    don_vi=item.don_vi,
                    thoi_diem_ket_qua=ref_now,
                )
            )
        updated.xet_nghiem = kept_labs

    if patch.y_lenh:
        patch_by_id = {row.chi_tiet_y_lenh_id: row for row in patch.y_lenh}
        new_lines: list[ChiTietYLenh] = []
        for line in updated.y_lenh_cho_duyet.chi_tiet:
            edit = patch_by_id.get(line.chi_tiet_y_lenh_id)
            if edit is None:
                new_lines.append(line)
                continue
            changes: dict[str, Any] = {}
            for field_name in (
                "ten_tu_do",
                "lieu_moi_lan",
                "don_vi_lieu",
                "duong_dung",
                "tan_suat",
                "so_lan_moi_ngay",
                "khoang_cach_gio",
            ):
                val = getattr(edit, field_name)
                if val is not None:
                    changes[field_name] = val
            new_lines.append(line.model_copy(update=changes))
        updated.y_lenh_cho_duyet = updated.y_lenh_cho_duyet.model_copy(
            update={"chi_tiet": new_lines}
        )

    return CaBenh.model_validate(updated.model_dump())
