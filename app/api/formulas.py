"""Máy tính công thức: chỉ gọi hàm đã cài trong app/calc theo danh mục config/kb/cong_thuc.yaml."""

import inspect
import logging
import math
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from starlette.exceptions import HTTPException

from app import calc
from app.api import schemas as s
from app.calc.types import CalcResult

_LOGGER = logging.getLogger(__name__)
_CATALOG_PATH = Path(__file__).resolve().parents[2] / "config/kb/cong_thuc.yaml"

# Danh sách cho phép: đường dẫn `ham` trong yaml -> hàm thuần. Không import động.
_ALLOWED: dict[str, Callable[..., CalcResult]] = {
    "app.calc.body.bmi": calc.bmi,
    "app.calc.body.bsa_mosteller": calc.bsa_mosteller,
    "app.calc.body.bsa_dubois": calc.bsa_dubois,
    "app.calc.body.ibw_devine": calc.ibw_devine,
    "app.calc.body.adjusted_body_weight": calc.adjusted_body_weight,
    "app.calc.renal.cockcroft_gault": calc.cockcroft_gault,
    "app.calc.renal.egfr_ckd_epi_2021": calc.egfr_ckd_epi_2021,
    "app.calc.hepatic.child_pugh": calc.child_pugh,
    "app.calc.cardiac.qtc_bazett": calc.qtc_bazett,
    "app.calc.cardiac.qtc_fridericia": calc.qtc_fridericia,
    "app.calc.cardiac.qtc_framingham": calc.qtc_framingham,
    "app.calc.cardiac.qtc_hodges": calc.qtc_hodges,
    "app.calc.cardiac.qtc_rautaharju": calc.qtc_rautaharju,
    "app.calc.electrolyte.calcium_corrected": calc.calcium_corrected,
}


def _bad(message: str) -> HTTPException:
    """Lỗi 422 thân chuẩn, thông báo tiếng Việt, không kèm dấu vết."""
    return HTTPException(422, detail={"ma": "du_lieu_khong_hop_le", "thong_bao": message})


@lru_cache(maxsize=1)
def _load_entries() -> dict[str, dict[str, Any]]:
    """Đọc yaml một lần; bỏ mục có hàm ngoài danh sách cho phép."""
    raw = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8"))
    entries: dict[str, dict[str, Any]] = {}
    for item in raw:
        if item.get("ham") not in _ALLOWED:
            _LOGGER.warning("Bỏ công thức %s: hàm ngoài danh sách cho phép", item.get("ma"))
            continue
        entries[item["ma"]] = item
    return entries


def _unit_field(function: Callable[..., Any], name: str) -> str | None:
    """Tên trường đơn vị đi kèm (`<ten>_don_vi`) nếu hàm có tham số đó."""
    candidate = f"{name}_don_vi"
    return candidate if candidate in inspect.signature(function).parameters else None


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _default(value: Any) -> str | float | None:
    """Giá trị mặc định của yaml dưới dạng số hoặc chuỗi."""
    if value is None or isinstance(value, bool):
        return None
    return float(value) if isinstance(value, int | float) else str(value)


def _present_input(function: Callable[..., Any], row: dict[str, Any]) -> s.DauVaoCongThuc:
    is_choice = row.get("kieu") == "lua_chon"
    default = row.get("mac_dinh")
    choices = _as_list(row.get("gia_tri")) if is_choice else []
    raw_choice_labels = row.get("nhan_lua_chon") if is_choice else None
    choice_labels = (
        {
            choice: str(raw_choice_labels[choice])
            for choice in choices
            if choice in raw_choice_labels
        }
        if isinstance(raw_choice_labels, dict)
        else {}
    )
    return s.DauVaoCongThuc(
        ten=row["ten"],
        nhan=str(row.get("nhan") or row["ten"]),
        kieu="lua_chon" if is_choice else "so",
        don_vi=[] if is_choice else _as_list(row.get("don_vi")),
        lua_chon=choices,
        nhan_lua_chon=choice_labels,
        truong_don_vi=None if is_choice else _unit_field(function, row["ten"]),
        bat_buoc=bool(row.get("bat_buoc", True)),
        mac_dinh=_default(default),
    )


def list_formulas() -> s.DanhMucCongThuc:
    """Danh mục công thức kèm đặc tả đầu vào, đầu ra và nguồn gốc."""
    items = []
    for entry in _load_entries().values():
        function = _ALLOWED[entry["ham"]]
        output = entry.get("dau_ra") or {}
        items.append(
            s.CongThucMuc(
                ma=entry["ma"],
                ten=entry["ten"],
                loai=entry["loai"],
                dau_vao=[_present_input(function, row) for row in entry["dau_vao"]],
                dau_ra=s.DauRaCongThuc(
                    don_vi=_as_list(output.get("don_vi")),
                    phan_hang=_as_list(output.get("phan_hang")),
                ),
                tham_khao_goc=_as_list(entry.get("tham_khao_goc")),
                tham_chieu_mdcalc=entry.get("tham_chieu_mdcalc"),
                trang_thai=str(entry.get("trang_thai", "chua_duoc_si_duyet")),
            )
        )
    return s.DanhMucCongThuc(cong_thuc=items)


def _number(name: str, value: Any) -> float:
    """Chấp nhận số hoặc chuỗi số (dấu phẩy thập phân Việt)."""
    if isinstance(value, bool):
        raise _bad(f"Trường {name} phải là số.")
    if isinstance(value, int | float):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip().replace(",", "."))
        except ValueError:
            raise _bad(f"Trường {name} phải là số.") from None
    else:
        raise _bad(f"Trường {name} phải là số.")
    if not math.isfinite(number):
        raise _bad(f"Trường {name} có giá trị không hợp lệ.")
    return number


def _build_kwargs(entry: dict[str, Any], supplied: dict[str, Any]) -> dict[str, Any]:
    """Ánh xạ dau_vao của yêu cầu sang tham số hàm; ngoài đặc tả thì từ chối."""
    function = _ALLOWED[entry["ham"]]
    params = inspect.signature(function).parameters
    specs = {row["ten"]: row for row in entry["dau_vao"]}
    unit_fields = {f"{name}_don_vi": name for name in specs if f"{name}_don_vi" in params}
    unknown = [key for key in supplied if key not in specs and key not in unit_fields]
    if unknown:
        raise _bad(f"Trường không thuộc công thức: {', '.join(sorted(unknown))}.")
    kwargs: dict[str, Any] = {}
    for key, value in supplied.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        if key in unit_fields:
            allowed = _as_list(specs[unit_fields[key]].get("don_vi"))
            unit = str(value).strip()
            if allowed and unit.lower() not in {item.lower() for item in allowed}:
                name = unit_fields[key]
                raise _bad(f"Đơn vị của {name} phải là một trong: {', '.join(allowed)}.")
            kwargs[key] = unit
        elif specs[key].get("kieu") == "lua_chon":
            choice = str(value).strip()
            allowed = _as_list(specs[key].get("gia_tri"))
            if choice not in allowed:
                raise _bad(f"Trường {key} phải là một trong: {', '.join(allowed)}.")
            kwargs[key] = choice
        else:
            kwargs[key] = _number(key, value)
    for name, parameter in params.items():
        if name not in kwargs and parameter.default is inspect.Parameter.empty:
            kwargs[name] = None
    return kwargs


def calculate(code: str, supplied: dict[str, Any]) -> s.KetQuaCongThuc:
    """Gọi đúng hàm đã cài; ngoài miền hợp lệ thì 422, không lộ dấu vết."""
    entry = _load_entries().get(code)
    if entry is None:
        raise HTTPException(404, "Không tìm thấy công thức.")
    kwargs = _build_kwargs(entry, supplied)
    try:
        result = _ALLOWED[entry["ham"]](**kwargs)
    except ValueError as exc:
        raise _bad(str(exc)) from None
    return s.KetQuaCongThuc(
        ma=code,
        cong_thuc=result.cong_thuc,
        phien_ban=result.phien_ban,
        ket_qua=result.ket_qua,
        don_vi=result.don_vi,
        dau_vao_da_dung=[
            s.DauVaoDaDung(ten=item.ten, gia_tri=item.gia_tri, don_vi=item.don_vi)
            for item in result.dau_vao
        ],
        thieu_dau_vao=list(result.thieu_dau_vao),
        ghi_chu=list(result.ghi_chu),
        tham_khao=result.tham_khao,
        trang_thai=str(entry.get("trang_thai", "chua_duoc_si_duyet")),
    )
