"""Lấy giá trị định danh đã biết của đúng người bệnh để che theo trường (lớp 1).

Giá trị chỉ sống trong bộ nhớ của lần gọi: không cache, không log, không đưa vào cảnh báo.
"""

import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.domain.models import CaBenh

LoaiDinhDanh = Literal["TEN", "NGAY", "SDT", "DIACHI", "BHYT", "MA"]

_ROOT = Path(__file__).resolve().parents[2]
_SAFE_CASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_FALLBACK_CASE_DIRS = ("data/mock/demo", "data/mock/hoso_gia_lap")
_ENCOUNTER_CODE_KEYS = ("so_luu_tru", "ma_yt", "so_giuong")
_MIN_TEXT_LENGTH = 4


class GiaTriDinhDanh(BaseModel):
    """Một giá trị định danh cần che: loại và giá trị thật (ngày dạng ISO yyyy-mm-dd)."""

    model_config = ConfigDict(frozen=True)

    loai: LoaiDinhDanh
    gia_tri: str


class IdentifierLookupError(Exception):
    """Không lấy được định danh hành chính; thông điệp không chứa giá trị nào."""


AdministrativeReader = Callable[[Sequence[str]], Mapping[str, Any]]


def _clean(value: object) -> str | None:
    """Trả chuỗi đã cắt khoảng trắng hoặc None khi rỗng."""
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def base_identifiers(ca: CaBenh) -> list[GiaTriDinhDanh]:
    """Mã luôn che: mã người bệnh, mã ca/hồ sơ và mã đợt điều trị."""
    values = (ca.nguoi_benh.nguoi_benh_id, ca.ca_id, ca.dot_dieu_tri.dot_dieu_tri_id)
    return [GiaTriDinhDanh(loai="MA", gia_tri=item) for item in values if _clean(item)]


def identifiers_from_administrative(
    identity: Mapping[str, Any] | None,
    encounters: Iterable[Mapping[str, Any] | None] = (),
    extra_codes: Iterable[str | None] = (),
) -> list[GiaTriDinhDanh]:
    """Rút giá trị định danh từ khối hành chính, hàm thuần chỉ đọc dữ liệu truyền vào."""
    found: list[GiaTriDinhDanh] = []

    def add(loai: LoaiDinhDanh, value: object, *, minimum: int = 1) -> None:
        text = _clean(value)
        if text is not None and len(text) >= minimum:
            found.append(GiaTriDinhDanh(loai=loai, gia_tri=text))

    identity = identity or {}
    add("TEN", identity.get("ho_ten"), minimum=_MIN_TEXT_LENGTH)
    add("NGAY", str(identity["ngay_sinh"]) if identity.get("ngay_sinh") else None)
    contact = identity.get("nguoi_bao_tin") or {}
    add("TEN", contact.get("ho_ten"), minimum=_MIN_TEXT_LENGTH)
    add("SDT", contact.get("dien_thoai"))
    insurance = identity.get("bhyt") or {}
    add("BHYT", insurance.get("so_the"))
    parents = identity.get("bo_me") or {}
    for key in ("bo", "me"):
        parent = parents.get(key) or {}
        add("TEN", parent.get("ho_ten"), minimum=_MIN_TEXT_LENGTH)

    address = identity.get("dia_chi") or {}
    parts = {
        key: _clean(address.get(key))
        for key in ("so_nha", "thon_pho", "xa_phuong", "huyen", "tinh_thanh")
    }
    full_address = _clean(identity.get("dia_chi_text")) or ", ".join(
        value for value in parts.values() if value
    )
    add("DIACHI", full_address, minimum=_MIN_TEXT_LENGTH)
    street = parts["thon_pho"]
    house = parts["so_nha"]
    if house and street:
        add("DIACHI", f"{house} {street}", minimum=_MIN_TEXT_LENGTH)
    for key in ("thon_pho", "xa_phuong", "huyen"):
        add("DIACHI", parts[key], minimum=_MIN_TEXT_LENGTH)
    if house and not house.isdigit():
        add("DIACHI", house, minimum=_MIN_TEXT_LENGTH)

    for encounter in encounters:
        for key in _ENCOUNTER_CODE_KEYS:
            add("MA", (encounter or {}).get(key))
    for code in extra_codes:
        add("MA", code)
    return list(dict.fromkeys(found))


def _identifiers_from_case_file(raw: Mapping[str, Any]) -> list[GiaTriDinhDanh]:
    """Rút định danh từ khối hanh_chinh và quan_ly của một tệp ca."""
    encounters: list[Mapping[str, Any] | None] = []
    stay = raw.get("dot_dieu_tri")
    if isinstance(stay, Mapping):
        encounters.append(stay.get("quan_ly"))
    elif isinstance(stay, list):
        encounters.extend(item.get("quan_ly") for item in stay if isinstance(item, Mapping))
    return identifiers_from_administrative(
        raw.get("hanh_chinh"), encounters, extra_codes=(raw.get("ho_so_id"),)
    )


def _default_case_dirs() -> list[Path]:
    """Thư mục ca cấu hình rồi các thư mục dữ liệu giả lập cố định của kho."""
    dirs: list[Path] = []
    try:
        from app.config.settings import load_settings

        dirs.append(_ROOT / load_settings().app.case_dir)
    except Exception:
        pass
    dirs.extend(_ROOT / item for item in _FALLBACK_CASE_DIRS)
    return list(dict.fromkeys(dirs))


def _read_from_file(ca: CaBenh, case_dirs: Sequence[Path] | None) -> list[GiaTriDinhDanh]:
    """Tìm tệp ca theo mã ca đã có (không lấy đường dẫn từ dữ liệu người dùng)."""
    if not _SAFE_CASE_ID.fullmatch(ca.ca_id):
        raise IdentifierLookupError("Mã ca không hợp lệ để tìm tệp hành chính.")
    for folder in case_dirs if case_dirs is not None else _default_case_dirs():
        path = Path(folder) / f"{ca.ca_id}.json"
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise IdentifierLookupError("Không đọc được tệp hành chính của ca.") from exc
        if not isinstance(raw, dict):
            continue
        same_case = ca.ca_id in (raw.get("ca_id"), raw.get("ho_so_id"))
        patient = raw.get("nguoi_benh")
        same_patient = (
            isinstance(patient, Mapping)
            and patient.get("nguoi_benh_id") == ca.nguoi_benh.nguoi_benh_id
        )
        if same_case and same_patient and isinstance(raw.get("hanh_chinh"), Mapping):
            return _identifiers_from_case_file(raw)
    raise IdentifierLookupError("Không tìm thấy dữ liệu hành chính của ca.")


def _read_from_database(ca: CaBenh, reader: AdministrativeReader | None) -> list[GiaTriDinhDanh]:
    """Đọc hành chính từ DB, không cache."""
    try:
        if reader is None:
            from app.db.administrative import read_administrative

            reader = read_administrative
        patient_id = ca.nguoi_benh.nguoi_benh_id
        record = reader([patient_id]).get(patient_id)
        if record is None:
            raise IdentifierLookupError("Không có dữ liệu hành chính của người bệnh.")
        data = record.model_dump(mode="json") if hasattr(record, "model_dump") else dict(record)
        return identifiers_from_administrative(
            data.get("dinh_danh_day_du"), data.get("lich_su_vao_vien") or []
        )
    except IdentifierLookupError:
        raise
    except Exception as exc:
        raise IdentifierLookupError(f"Lỗi đọc hành chính ({type(exc).__name__}).") from exc


def known_identifiers(
    ca: CaBenh,
    *,
    source: Literal["db", "file"] | None = None,
    case_dirs: Sequence[Path] | None = None,
    administrative_reader: AdministrativeReader | None = None,
) -> list[GiaTriDinhDanh]:
    """Mọi giá trị định danh đã biết của người bệnh trong ca; ném IdentifierLookupError khi lỗi.

    Chế độ DB đọc trực tiếp (không cache); chế độ tệp đọc khối hanh_chinh của tệp ca.
    Người gọi nên bắt IdentifierLookupError, dùng base_identifiers và thêm cảnh báo.
    """
    if source is None:
        try:
            from app.config.settings import load_case_source

            source = load_case_source()
        except Exception as exc:
            raise IdentifierLookupError("Không xác định được nguồn ca.") from exc
    if source == "db":
        found = _read_from_database(ca, administrative_reader)
    else:
        found = _read_from_file(ca, case_dirs)
    return list(dict.fromkeys([*base_identifiers(ca), *found]))
