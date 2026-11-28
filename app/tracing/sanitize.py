"""Lọc thuộc tính, che bí mật, che chữ số mã lý do, băm HMAC mã ca và tính chi phí."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
from collections.abc import Mapping
from threading import Lock
from typing import Any

from app.config.settings import ModelPriceSettings, get_process_secret
from app.deid.scrubber import TOKEN_PATTERN, DeidError, scrub_text
from app.tracing.models import (
    KHOA_THUOC_TINH_CHO_PHEP,
    MAX_ATTRIBUTES_BYTES,
    MAX_REDACTED_CONTENT_CHARS,
    LoaiSpan,
    MucNoiDung,
)

_LOGGER = logging.getLogger(__name__)
_NHAN_BI_MAT = "[DA_CHE_BI_MAT]"
_BIEN_MOI_TRUONG_HMAC = "TRACER_HMAC_KEY"
_HMAC_LOCK = Lock()
_PROCESS_HMAC_BYTES: bytes | None = None
_WARNED_MISSING_HMAC = False

_DEID_TAG_SPLIT_RE = re.compile(f"({TOKEN_PATTERN})")
_DEID_TAG_FULL_RE = re.compile(TOKEN_PATTERN)
_LABELED_RECORD_RE = re.compile(
    r"(?i)(?<!\w)(?:HN|mã\s+hồ\s+sơ)(?:\s*[:：-]\s*|\s+)([A-Z0-9_-]{4,})"
)

_MAU_BI_MAT: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b"),
    re.compile(r"\bsb_[a-z]+_[A-Za-z0-9_\-]{10,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-~+/]+=*"),
    re.compile(r"(?i)\bpostgres(?:ql)?://[^\s\"'`]+"),
)
_PHONE_IN_REASON_RE = re.compile(r"(?<![\d+])(?:0|\+?84)[ .\-]*[35789](?:[ .\-]*\d){8}(?!\d)")
_NUMBER_IN_REASON_RE = re.compile(r"\d+(?:[.,]\d+)?")


def che_bi_mat(text: str) -> str:
    """Che khoá API, JWT, Bearer và chuỗi kết nối DB nếu vô tình lọt vào chuỗi."""
    cleaned = text
    for pattern in _MAU_BI_MAT:
        cleaned = pattern.sub(_NHAN_BI_MAT, cleaned)
    return cleaned


def _scrub_pii_preserving_tags(text: str) -> str:
    """Che mẫu PII lớp 2 nhưng giữ nguyên các thẻ ẩn danh [TEN_1], [SDT_1]..."""
    text = _LABELED_RECORD_RE.sub("[HN_DA_CHE]", text)
    try:
        return scrub_text(text).van_ban
    except DeidError:
        try:
            parts = _DEID_TAG_SPLIT_RE.split(text)
            cleaned = [
                part if _DEID_TAG_FULL_RE.fullmatch(part) else scrub_text(part).van_ban
                for part in parts
                if part
            ]
            return "".join(cleaned)
        except DeidError:
            return "[khong_ghi_duoc_vi_loi_che_dinh_danh]"


def _sanitize_value(
    value: Any,
    *,
    scrub_pii: bool = False,
    max_str_len: int | None = None,
) -> Any:
    """Chuẩn hoá giá trị sang kiểu JSON an toàn, che bí mật và cắt chuỗi nếu cần."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        cleaned = che_bi_mat(value)
        if scrub_pii:
            cleaned = _scrub_pii_preserving_tags(cleaned)
        if max_str_len is not None and len(cleaned) > max_str_len:
            return cleaned[:max_str_len]
        return cleaned
    if isinstance(value, Mapping):
        return {
            che_bi_mat(str(k)): _sanitize_value(v, scrub_pii=scrub_pii, max_str_len=max_str_len)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [
            _sanitize_value(item, scrub_pii=scrub_pii, max_str_len=max_str_len) for item in value
        ]
    return _sanitize_value(str(value), scrub_pii=scrub_pii, max_str_len=max_str_len)


def che_chu_so_ma_ly_do(ma_ly_do: str) -> str:
    """Che con số có > 4 chữ số ở phần sau dấu ':' của mã lý do thành '#<n>'."""
    cleaned = che_bi_mat(ma_ly_do)
    if ":" not in cleaned:
        return cleaned
    prefix, suffix = cleaned.split(":", 1)

    def _mask_digits(match: re.Match[str]) -> str:
        raw = match.group(0)
        count = sum(1 for ch in raw if ch.isdigit())
        if count > 4:
            return f"#{count}"
        return raw

    masked = _PHONE_IN_REASON_RE.sub(_mask_digits, suffix)
    masked = _NUMBER_IN_REASON_RE.sub(_mask_digits, masked)
    return f"{prefix}:{masked}"


def _json_byte_len(data: Mapping[str, Any]) -> int:
    """Độ dài UTF-8 sau json.dumps của từ điển thuộc tính."""
    return len(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def _trim_attributes_to_limit(
    data: dict[str, Any],
    limit: int = MAX_ATTRIBUTES_BYTES,
) -> dict[str, Any]:
    """Cắt danh sách/chuỗi dài hoặc bỏ khoá lớn nhất để đảm bảo <= 4 KB sau json.dumps."""
    if _json_byte_len(data) <= limit:
        return data

    trimmed = dict(data)
    for key, value in list(trimmed.items()):
        if isinstance(value, list) and len(value) > 10:
            trimmed[key] = value[:10]
            if _json_byte_len(trimmed) <= limit:
                return trimmed
        elif isinstance(value, str) and len(value) > 256:
            trimmed[key] = value[:256]
            if _json_byte_len(trimmed) <= limit:
                return trimmed

    while trimmed and _json_byte_len(trimmed) > limit:
        largest_key = max(
            trimmed,
            key=lambda k: len(json.dumps(trimmed[k], ensure_ascii=False).encode("utf-8")),
        )
        value = trimmed[largest_key]
        if isinstance(value, list) and value:
            trimmed[largest_key] = value[: len(value) // 2]
        elif isinstance(value, str) and len(value) > 32:
            trimmed[largest_key] = value[: len(value) // 2]
        else:
            del trimmed[largest_key]
    return trimmed


def loc_thuoc_tinh(
    loai: LoaiSpan,
    raw: Mapping[str, Any],
    *,
    limit_bytes: int = MAX_ATTRIBUTES_BYTES,
) -> tuple[dict[str, Any], int]:
    """Chỉ giữ khoá thuộc danh sách cho phép của loại span, che lý do/bí mật và giới hạn 4 KB."""
    allowed = KHOA_THUOC_TINH_CHO_PHEP.get(loai, frozenset())
    kept: dict[str, Any] = {}
    dropped_unknown = 0
    for key, value in raw.items():
        if key not in allowed:
            dropped_unknown += 1
            continue
        if loai == "kiem_chung" and key == "ma_ly_do" and isinstance(value, (list, tuple)):
            kept[key] = [che_chu_so_ma_ly_do(str(item)) for item in value]
        else:
            kept[key] = _sanitize_value(value, scrub_pii=key not in {"bam_prompt", "bam_tham_so"})
    return _trim_attributes_to_limit(kept, limit=limit_bytes), dropped_unknown


def chuan_hoa_noi_dung(
    muc_noi_dung: MucNoiDung,
    raw: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Bỏ nội dung ở mức sieu_du_lieu; cắt 2.000 ký tự ở noi_dung_da_che; giữ ở day_du."""
    if not raw or muc_noi_dung == "sieu_du_lieu":
        return None
    max_len = MAX_REDACTED_CONTENT_CHARS if muc_noi_dung == "noi_dung_da_che" else None
    result = _sanitize_value(dict(raw), scrub_pii=True, max_str_len=max_len)
    return result if isinstance(result, dict) and result else None


def bam_du_lieu(value: Any) -> str:
    """Băm SHA-256 dữ liệu đầu vào theo dạng JSON chuẩn hoá."""
    try:
        canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        canonical = repr(value)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _resolve_hmac_bytes() -> bytes:
    """Đọc khoá HMAC từ TRACER_HMAC_KEY; thiếu thì sinh ngẫu nhiên theo tiến trình và cảnh báo."""
    global _PROCESS_HMAC_BYTES, _WARNED_MISSING_HMAC
    raw = (get_process_secret(_BIEN_MOI_TRUONG_HMAC) or "").strip()
    if raw:
        return raw.encode("utf-8")
    with _HMAC_LOCK:
        if _PROCESS_HMAC_BYTES is None:
            _PROCESS_HMAC_BYTES = secrets.token_bytes(32)
        if not _WARNED_MISSING_HMAC:
            _WARNED_MISSING_HMAC = True
            _LOGGER.warning(
                "Thiếu %s; tạm dùng khoá ngẫu nhiên theo tiến trình cho ca_bam.",
                _BIEN_MOI_TRUONG_HMAC,
            )
        return _PROCESS_HMAC_BYTES


def bam_ma_ca(ca_id: str | None, *, khoa: bytes | None = None) -> str | None:
    """Tính HMAC-SHA256 của mã ca; trả None với chế độ chung hoặc thiếu mã ca."""
    if not ca_id or ca_id == "__global__":
        return None
    material = khoa if khoa is not None else _resolve_hmac_bytes()
    return hmac.new(material, ca_id.encode("utf-8"), hashlib.sha256).hexdigest()


def tinh_chi_phi_uoc_tinh(
    mo_hinh: str | None,
    token_vao: int,
    token_ra: int,
    bang_gia: Mapping[str, ModelPriceSettings],
) -> float:
    """Tính chi phí ước tính (không làm tròn); trả 0.0 nếu thiếu bảng giá cho mô hình."""
    if not mo_hinh or mo_hinh not in bang_gia:
        return 0.0
    price = bang_gia[mo_hinh]
    return (
        float(max(0, token_vao)) * float(price.vao_moi_trieu)
        + float(max(0, token_ra)) * float(price.ra_moi_trieu)
    ) / 1_000_000.0
