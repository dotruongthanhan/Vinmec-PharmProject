"""Cấu hình, truy vấn nhiều bậc và quy tắc chọn nhãn/NDC xác định."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.kb.names import normalize_key, strip_salt
from app.kb.sources.openfda import parse_html_table

SECTION_FIELDS: dict[str, tuple[str, ...]] = {
    "chi_dinh": ("indications_and_usage",),
    "lieu_va_cach_dung": ("dosage_and_administration",),
    "chong_chi_dinh": ("contraindications",),
    "canh_bao": ("boxed_warning", "warnings_and_cautions", "warnings", "precautions"),
    "tuong_tac": ("drug_interactions", "drug_and_or_laboratory_test_interactions"),
    "nhom_dac_biet": (
        "use_in_specific_populations",
        "pregnancy",
        "lactation",
        "nursing_mothers",
        "pediatric_use",
        "geriatric_use",
        "labor_and_delivery",
        "females_and_males_of_reproductive_potential",
        "pregnancy_or_breast_feeding",
        "teratogenic_effects",
        "nonteratogenic_effects",
    ),
    "bang_lieu": ("dosage_and_administration_table",),
}

_BIOSIMILAR_SUFFIX_RE = re.compile(r"-[a-z]{4}\b", re.IGNORECASE)
_COMBO_GENERIC_RE = re.compile(r"(?:\s+(?:and|with)\s+|\s*[/+&]\s*)", re.IGNORECASE)
_COMBO_SPLIT_RE = re.compile(r"\s*(?:\+|/|\band\b|&|,)\s*", re.IGNORECASE)


class DrugSpec(BaseModel):
    """Một hoạt chất hoặc phối hợp đã được ghi rõ trong danh mục."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    hoat_chat: str = Field(min_length=1)
    ma: str = Field(pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
    duong_dung: list[str] = Field(min_length=1)
    ghi_chu: str = ""
    thanh_phan: list[str] = Field(default_factory=list)


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _base_substance(name: str) -> str:
    """Chuẩn hóa tên hoạt chất và bỏ thêm hậu tố dạng khan (anhydrous)."""
    cleaned = strip_salt(name)
    if cleaned.endswith(" anhydrous") and len(cleaned.split()) > 1:
        cleaned = strip_salt(cleaned.removesuffix(" anhydrous"))
    return cleaned


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and item.strip()]


def _effective_time_key(entry: dict[str, Any]) -> int:
    raw = str(entry.get("effective_time") or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    return int(digits) if digits else 0


def build_queries(
    spec: DrugSpec,
    route: str | None = None,
    *,
    ndc: bool = False,
) -> list[tuple[int, str]]:
    """Tạo 4 bậc truy vấn từ chặt đến lỏng; loại sản phẩm và đường dùng không dùng .exact."""
    prefix = "" if ndc else "openfda."
    substance_field = "active_ingredients.name" if ndc else "openfda.substance_name"
    tail = [f'{prefix}product_type:"HUMAN PRESCRIPTION DRUG"']
    if route is not None:
        tail.append(f"{prefix}route:{_quote(route)}")

    def join_query(head_terms: list[str]) -> str:
        return " AND ".join([*head_terms, *tail])

    tier2_parts = (
        [f"{substance_field}.exact:{_quote(part.upper())}" for part in spec.thanh_phan]
        if spec.thanh_phan
        else [f"{substance_field}.exact:{_quote(spec.hoat_chat.upper())}"]
    )
    queries: list[tuple[int, str]] = [
        (1, join_query([f"{prefix}generic_name.exact:{_quote(spec.hoat_chat.upper())}"])),
        (2, join_query(tier2_parts)),
        (3, join_query([f"{prefix}generic_name:{_quote(spec.hoat_chat)}"])),
    ]

    norm_name = normalize_key(spec.hoat_chat)
    saltless = strip_salt(spec.hoat_chat)
    if saltless and saltless != norm_name:
        queries.append((4, join_query([f"{prefix}generic_name:{_quote(saltless)}"])))
    return queries


def build_query(spec: DrugSpec, route: str | None = None, *, ndc: bool = False) -> str:
    """Trả về truy vấn bậc 1; httpx mã hóa tham số URL khi gửi."""
    return build_queries(spec, route, ndc=ndc)[0][1]


def field_text(entry: dict[str, Any], field: str) -> str:
    """Đọc văn bản, không sửa nội dung nhãn."""
    values = entry.get(field, [])
    if not isinstance(values, list):
        return ""
    return "\n".join(value for value in values if isinstance(value, str) and value.strip())


def dosage_tables(entry: dict[str, Any]) -> list[str]:
    """Đếm các bảng liều khác nhau có thể tách bằng bộ đọc hiện có."""
    values = entry.get("dosage_and_administration_table", [])
    if not isinstance(values, list):
        return []
    return sorted(
        {
            table.van_ban_phang
            for raw in values
            if isinstance(raw, str) and (table := parse_html_table(raw)) is not None
        }
    )


def section_counts(entry: dict[str, Any]) -> dict[str, int]:
    """Tính số ký tự của từng nhóm mục thẩm định."""
    counts = {
        section: sum(len(field_text(entry, field)) for field in fields)
        for section, fields in SECTION_FIELDS.items()
    }
    counts["bang_lieu"] = sum(len(table) for table in dosage_tables(entry))
    return counts


def _is_salt_token(token: str) -> bool:
    return strip_salt(f"x {token}") == "x"


def _single_generic_matches(raw_generic: str, spec: DrugSpec) -> bool:
    cleaned = raw_generic.strip()
    if not cleaned:
        return False
    if cleaned.casefold() == spec.hoat_chat.casefold():
        return True
    if _BIOSIMILAR_SUFFIX_RE.search(cleaned):
        if not _BIOSIMILAR_SUFFIX_RE.search(spec.hoat_chat):
            return False
    if _COMBO_GENERIC_RE.search(cleaned):
        return False
    g_tokens = normalize_key(cleaned).split()
    target_tokens = normalize_key(spec.hoat_chat).split()
    base_tokens = _base_substance(spec.hoat_chat).split()
    if not g_tokens or not target_tokens or not base_tokens:
        return False
    if g_tokens[: len(target_tokens)] == target_tokens:
        return True
    if target_tokens != base_tokens and g_tokens[: len(base_tokens)] == base_tokens:
        rest = g_tokens[len(base_tokens) :]
        if not rest:
            return True
        if _is_salt_token(rest[0]):
            expected_salt = target_tokens[len(base_tokens) :]
            return rest[: len(expected_salt)] == expected_salt
        return True
    return False


def _combo_generic_matches(raw_generic: str, spec: DrugSpec) -> bool:
    cleaned = raw_generic.strip()
    if not cleaned:
        return False
    if cleaned.casefold() == spec.hoat_chat.casefold():
        return True
    g_norm = normalize_key(cleaned)
    target_norm = normalize_key(spec.hoat_chat)
    if g_norm == target_norm or g_norm.startswith(f"{target_norm} "):
        return True
    parts = [part.strip() for part in _COMBO_SPLIT_RE.split(cleaned) if part.strip()]
    if len(parts) < 2:
        return False
    expected = {_base_substance(item) for item in spec.thanh_phan}
    return {_base_substance(part) for part in parts} == expected


def label_rejection_reason(entry: dict[str, Any], spec: DrugSpec, route: str) -> str | None:
    """Trả về lý do loại nhãn hoặc None nếu nhãn qua quy tắc chọn."""
    if not entry.get("set_id"):
        return "thiếu set_id"
    meta = entry.get("openfda")
    if not isinstance(meta, dict):
        return "thiếu khối openfda"
    substances = _str_list(meta.get("substance_name"))
    if not substances:
        return "thiếu substance_name"
    product_types = _str_list(meta.get("product_type"))
    if "HUMAN PRESCRIPTION DRUG" not in [item.upper() for item in product_types]:
        return f"sai product_type ({', '.join(product_types) or 'rỗng'})"
    routes = _str_list(meta.get("route"))
    if route.upper() not in [item.upper() for item in routes]:
        return f"sai đường dùng ({', '.join(routes) or 'rỗng'}, cần {route})"
    if spec.thanh_phan:
        expected = sorted(_base_substance(item) for item in spec.thanh_phan)
        actual = sorted(_base_substance(item) for item in substances)
        if actual != expected:
            return f"sai thành phần ({', '.join(substances)})"
    else:
        if len(substances) != 1:
            return f"dạng phối hợp ({', '.join(substances)})"
        if _base_substance(substances[0]) != _base_substance(spec.hoat_chat):
            return f"sai hoạt chất ({substances[0]})"
    generics = _str_list(meta.get("generic_name"))
    if not generics:
        return "thiếu generic_name"
    matcher = _combo_generic_matches if spec.thanh_phan else _single_generic_matches
    if not any(matcher(item, spec) for item in generics):
        return f"sai generic_name ({', '.join(generics)})"
    return None


def label_matches(entry: dict[str, Any], spec: DrugSpec, route: str) -> bool:
    """Kiểm đúng tên, loại, đường dùng và thành phần, không suy đoán hoạt chất."""
    return label_rejection_reason(entry, spec, route) is None


def ndc_rejection_reason(record: dict[str, Any], spec: DrugSpec) -> str | None:
    """Trả về lý do loại bản ghi NDC hoặc None nếu hợp lệ."""
    raw_type = record.get("product_type")
    if isinstance(raw_type, list):
        product_types = [str(item).strip().upper() for item in raw_type if item]
    elif isinstance(raw_type, str) and raw_type.strip():
        product_types = [raw_type.strip().upper()]
    else:
        product_types = []
    if "HUMAN PRESCRIPTION DRUG" not in product_types:
        return f"sai product_type ({', '.join(product_types) or 'rỗng'})"

    raw_ings = record.get("active_ingredients")
    if not isinstance(raw_ings, list):
        return "thiếu active_ingredients"
    ing_names = [
        str(item["name"]).strip()
        for item in raw_ings
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip()
    ]
    if not ing_names:
        return "thiếu active_ingredients"

    actual_set = {_base_substance(name) for name in ing_names}
    if spec.thanh_phan:
        expected_set = {_base_substance(item) for item in spec.thanh_phan}
        if actual_set != expected_set:
            return f"sai thành phần ({', '.join(ing_names)})"
    else:
        if len(actual_set) != 1:
            return f"dạng phối hợp ({', '.join(ing_names)})"
        if next(iter(actual_set)) != _base_substance(spec.hoat_chat):
            return f"sai hoạt chất ({', '.join(ing_names)})"

    generic_raw = record.get("generic_name")
    if isinstance(generic_raw, str) and generic_raw.strip():
        matcher = _combo_generic_matches if spec.thanh_phan else _single_generic_matches
        if not matcher(generic_raw, spec):
            return f"sai generic_name ({generic_raw.strip()})"
    return None


def ndc_matches(record: dict[str, Any], spec: DrugSpec) -> bool:
    """Kiểm bản ghi NDC đúng loại sản phẩm, đơn chất/phối hợp và tên chung."""
    return ndc_rejection_reason(record, spec) is None


def select_label(
    candidates: list[dict[str, Any]],
    spec: DrugSpec,
    route: str,
) -> dict[str, Any] | None:
    """Ưu tiên số mục, ngày mới nhất, set_id tăng dần; không phụ thuộc thứ tự."""
    valid = [entry for entry in candidates if label_matches(entry, spec, route)]
    if not valid:
        return None
    return min(
        valid,
        key=lambda entry: (
            -sum(value > 0 for value in section_counts(entry).values()),
            -_effective_time_key(entry),
            str(entry["set_id"]),
            json.dumps(entry, sort_keys=True, ensure_ascii=False),
        ),
    )
