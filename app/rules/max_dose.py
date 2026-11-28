"""Luật yếu tố 3: kiểm tra liều tối đa theo nhãn và bảng quy đổi SI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from app.domain.loader import latest_vital
from app.domain.models import CaBenh, ChiTietYLenh, SinhHieu, Thuoc
from app.kb.names import normalize_key
from app.rules.d5_config import (
    DoseLimit,
    MaxDoseConfig,
    MaxDoseRule,
    PopulationDefinition,
    is_same_route_or_iv,
    normalize_route_default,
    try_load_default_max_dose_config,
)
from app.rules.types import CanCu, PhatHien, effective_lines, line_label, pending_lines

if TYPE_CHECKING:
    from app.kb.resolver import DrugResolver
    from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai

_YEU_TO = 3
_EXCLUDED_KINDS = {"dich_truyen_dien_giai", "duoc_lieu"}
_MASS_TO_MG: dict[str, float] = {
    "mg": 1.0,
    "g": 1000.0,
    "mcg": 0.001,
}
_COUNT_UNITS: frozenset[str] = frozenset(
    {
        "vien",
        "vien nen",
        "vien nang",
        "ong",
        "ong tiem",
        "lo",
        "goi",
        "tui",
        "chai",
        "bom tiem",
    }
)

_MucDo = Literal["nghiem_trong", "can_luu_y", "thong_tin"]


@dataclass(frozen=True)
class _DoseConversion:
    """Liều mỗi lần của một hoạt chất sau khi quy đổi đơn vị."""

    mode: Literal["mass_mg", "mg_per_kg", "other", "missing"]
    value: float | None = None
    unit: str | None = None
    display: str = ""
    missing_field: str | None = None


@dataclass(frozen=True)
class _LimitCheck:
    """Kết quả so sánh một trần liều trên một hàng bảng."""

    exceeded: bool
    loai_gioi_han: str
    calc_text: str
    summary_text: str
    ref_text: str
    ref_calc_text: str
    rule: MaxDoseRule
    used_weight: bool
    co_med_names: tuple[str, ...]


def _extract_resolved_ids(result: KetQuaPhanGiai) -> set[str]:
    """Lấy tập mã hoạt chất trên trục từ kết quả phân giải đã hoặc một phần nhận diện."""
    if result.trang_thai not in {"da_phan_giai", "mot_phan"}:
        return set()
    return {tp.hoat_chat_id for tp in result.thanh_phan if tp.hoat_chat_id}


def _is_line_excluded(result: KetQuaPhanGiai) -> bool:
    """Kiểm tra dòng thuốc thuộc nhóm dịch truyền, điện giải hoặc dược liệu."""
    if result.trang_thai == "khong_ap_dung":
        return True
    return bool(result.thanh_phan) and all(tp.loai in _EXCLUDED_KINDS for tp in result.thanh_phan)


def _normalize_unit(raw: str | None) -> str:
    """Chuẩn hoá chuỗi đơn vị liều để so khớp và quy đổi SI."""
    if not raw:
        return ""
    cleaned = raw.replace("µ", "u").replace("μ", "u")
    key = normalize_key(cleaned)
    if not key:
        return ""
    if key in {"g", "gam", "gram"}:
        return "g"
    if key in {"mcg", "ug"}:
        return "mcg"
    if key == "mg kg":
        return "mg/kg"
    return key


def _fmt_num(val: float) -> str:
    """Định dạng số ở lớp hiển thị, không làm tròn trong logic tính toán."""
    if abs(val - round(val)) < 1e-9:
        return str(int(round(val)))
    return f"{val:.3f}".rstrip("0").rstrip(".")


def _weight_in_kg(weight_vital: SinhHieu | None) -> float | None:
    """Lấy cân nặng quy về kg từ sinh hiệu mới nhất."""
    if weight_vital is None or weight_vital.gia_tri <= 0:
        return None
    unit = _normalize_unit(weight_vital.don_vi)
    if unit == "g":
        return weight_vital.gia_tri / 1000.0
    if not unit or unit == "kg":
        return float(weight_vital.gia_tri)
    return None


def _resolve_strength(
    comp: ThanhPhanPhanGiai,
    thuoc: Thuoc | None,
    resolved_count: int,
) -> tuple[float | None, str | None]:
    """Tìm hàm lượng và đơn vị thành phần từ kết quả phân giải hoặc danh mục ca."""
    if comp.ham_luong is not None and comp.don_vi is not None:
        return comp.ham_luong, comp.don_vi
    if thuoc is None:
        return None, None
    for tp in thuoc.thanh_phan:
        if tp.hoat_chat_id == comp.hoat_chat_id or (
            comp.ma_ca is not None and tp.hoat_chat_id == comp.ma_ca
        ):
            return tp.ham_luong_thanh_phan, tp.don_vi
    if len(thuoc.thanh_phan) == 1 and resolved_count == 1:
        only = thuoc.thanh_phan[0]
        return only.ham_luong_thanh_phan, only.don_vi
    return None, None


def _convert_line_dose(
    line: ChiTietYLenh,
    comp: ThanhPhanPhanGiai,
    thuoc: Thuoc | None,
    resolved_count: int,
) -> _DoseConversion:
    """Đổi liều mỗi lần của dòng sang mg, mg/kg hoặc giữ nguyên đơn vị khác."""
    assert line.lieu_moi_lan is not None
    unit = _normalize_unit(line.don_vi_lieu)
    if unit in _MASS_TO_MG:
        if resolved_count > 1:
            return _DoseConversion(mode="missing", missing_field="ham_luong_thanh_phan")
        mg_val = float(line.lieu_moi_lan) * _MASS_TO_MG[unit]
        return _DoseConversion(
            mode="mass_mg",
            value=mg_val,
            unit="mg",
            display=f"{_fmt_num(mg_val)} mg",
        )

    if unit in _COUNT_UNITS:
        strength, tp_unit_raw = _resolve_strength(comp, thuoc, resolved_count)
        tp_unit = _normalize_unit(tp_unit_raw)
        if strength is None or strength <= 0 or tp_unit not in _MASS_TO_MG:
            return _DoseConversion(mode="missing", missing_field="ham_luong_thanh_phan")
        mg_val = float(line.lieu_moi_lan) * float(strength) * _MASS_TO_MG[tp_unit]
        return _DoseConversion(
            mode="mass_mg",
            value=mg_val,
            unit="mg",
            display=f"{_fmt_num(mg_val)} mg",
        )

    if unit == "mg/kg":
        val = float(line.lieu_moi_lan)
        return _DoseConversion(
            mode="mg_per_kg",
            value=val,
            unit="mg/kg",
            display=f"{_fmt_num(val)} mg/kg",
        )

    val = float(line.lieu_moi_lan)
    return _DoseConversion(
        mode="other",
        value=val,
        unit=unit,
        display=f"{_fmt_num(val)} {line.don_vi_lieu or unit}",
    )


def _check_population_def(
    defn: PopulationDefinition,
    tuoi: int | None,
    weight_kg: float | None,
) -> tuple[bool, list[str]]:
    """Kiểm tra người bệnh có thoả định nghĩa đối tượng hay thiếu trường đầu vào."""
    needs_age = any(
        v is not None
        for v in (
            defn.tuoi_tu,
            defn.tuoi_den,
            defn.tuoi_tren,
            defn.tuoi_duoi,
            defn.tuoi_thang_tu,
            defn.tuoi_thang_den,
            defn.tuoi_ngay_tu,
            defn.tuoi_ngay_den,
        )
    )
    if needs_age:
        if tuoi is None:
            return False, ["tuoi"]
        if defn.tuoi_tu is not None:
            ok = tuoi >= defn.tuoi_tu if defn.bao_gom_can_duoi else tuoi > defn.tuoi_tu
            if not ok:
                return False, []
        if defn.tuoi_tren is not None and not (tuoi > defn.tuoi_tren):
            return False, []
        if defn.tuoi_den is not None:
            ok = tuoi <= defn.tuoi_den if defn.bao_gom_can_tren else tuoi < defn.tuoi_den
            if not ok:
                return False, []
        if defn.tuoi_duoi is not None and not (tuoi < defn.tuoi_duoi):
            return False, []
        if defn.tuoi_thang_den is not None and tuoi * 12 > defn.tuoi_thang_den:
            return False, []
        if defn.tuoi_ngay_den is not None and tuoi * 365 > defn.tuoi_ngay_den:
            return False, []
        if defn.tuoi_thang_tu is not None:
            if (tuoi + 1) * 12 <= defn.tuoi_thang_tu:
                return False, []
            if tuoi == 0:
                return False, ["tuoi"]
        if defn.tuoi_ngay_tu is not None and tuoi == 0:
            return False, ["tuoi"]

    needs_weight = any(
        v is not None
        for v in (
            defn.can_nang_tu,
            defn.can_nang_den,
            defn.can_nang_tren,
            defn.can_nang_duoi,
        )
    )
    if needs_weight:
        if weight_kg is None:
            return False, ["can_nang"]
        if defn.can_nang_tu is not None and not (weight_kg >= defn.can_nang_tu):
            return False, []
        if defn.can_nang_tren is not None and not (weight_kg > defn.can_nang_tren):
            return False, []
        if defn.can_nang_den is not None and not (weight_kg <= defn.can_nang_den):
            return False, []
        if defn.can_nang_duoi is not None and not (weight_kg < defn.can_nang_duoi):
            return False, []

    return True, []


def _matches_population(
    rule: MaxDoseRule,
    config: MaxDoseConfig,
    tuoi: int | None,
    weight_kg: float | None,
) -> tuple[bool, list[str]]:
    """Xác định hàng quy tắc có áp dụng cho tuổi/cân nặng hiện tại không."""
    defn = config.doi_tuong_dinh_nghia.get(rule.doi_tuong)
    if defn is not None:
        return _check_population_def(defn, tuoi, weight_kg)

    if rule.doi_tuong == "nguoi_lon_va_tre_em":
        return True, []
    if rule.doi_tuong == "nguoi_lon":
        if tuoi is None:
            return False, ["tuoi"]
        return (tuoi >= 18), []
    return False, []


def _special_condition_text(rule: MaxDoseRule, config: MaxDoseConfig) -> str | None:
    """Lấy mô tả điều kiện đặc biệt nếu hàng có dieu_kien_khac khác null."""
    if rule.dieu_kien_khac:
        return rule.dieu_kien_khac
    defn = config.doi_tuong_dinh_nghia.get(rule.doi_tuong)
    if defn is not None and defn.dieu_kien_khac:
        return defn.dieu_kien_khac
    return None


def _max_kg_value(raw: float | tuple[float, ...] | None) -> float | None:
    """Lấy giá trị trần mg/kg lớn nhất khi nhãn ghi một số hoặc danh sách mức."""
    if raw is None:
        return None
    if isinstance(raw, tuple):
        return max(raw) if raw else None
    return float(raw)


def _limit_to_mg(limit: DoseLimit) -> tuple[float | None, str]:
    """Đổi ngưỡng liều bảng sang mg nếu là đơn vị khối lượng SI."""
    unit = _normalize_unit(limit.don_vi)
    if unit in _MASS_TO_MG:
        return float(limit.gia_tri) * _MASS_TO_MG[unit], "mg"
    return None, unit


def _build_source_evidence(rule: MaxDoseRule) -> CanCu | None:
    """Tạo căn cứ tài liệu từ nguồn nhãn FDA của một hàng liều tối đa."""
    if rule.nguon is None:
        return None
    src = rule.nguon
    name = src.ten_nhan or src.loai or "Nhãn"
    set_part = f" (set_id={src.set_id})" if src.set_id else ""
    url_part = f" — {src.url}" if src.url else ""
    quote = f'"{src.trich_nguyen_van}"' if src.trich_nguyen_van else ""
    prefix = f"[{rule.ma_dong}] " if rule.ma_dong else ""
    desc = f"{prefix}{name}{set_part}: {quote}{url_part} (chờ dược sĩ duyệt)".strip()
    return CanCu(loai="tai_lieu", ban_ghi_id=rule.ma_dong or None, mo_ta=desc)


def _dedupe_evidences(evidences: list[CanCu]) -> list[CanCu]:
    """Loại bỏ căn cứ trùng lặp nhưng giữ nguyên thứ tự."""
    seen: set[tuple[str, str | None, str]] = set()
    unique: list[CanCu] = []
    for item in evidences:
        key = (item.loai, item.ban_ghi_id, item.mo_ta)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _compare_row(
    *,
    rule: MaxDoseRule,
    conv: _DoseConversion,
    freq: int | None,
    weight_kg: float | None,
    co_med_names: tuple[str, ...],
) -> tuple[list[_LimitCheck], bool, bool]:
    """So sánh liều của dòng với mọi trần có trên một hàng áp dụng."""
    checks: list[_LimitCheck] = []
    missing_weight = False
    unit_mismatch = False
    co_suffix = f" [khi dùng cùng {', '.join(co_med_names)}]" if co_med_names else ""
    row_tag = f"hàng {rule.ma_dong}" if rule.ma_dong else "nhãn FDA"

    def _add_check(
        *,
        exceeded: bool,
        kind_label: str,
        lhs: str,
        limit: str,
        used_weight: bool,
    ) -> None:
        op = ">" if exceeded else "<="
        expr = f"{lhs} {op} {limit}"
        ref_expr = f"{lhs}, trần {limit}"
        checks.append(
            _LimitCheck(
                exceeded=exceeded,
                loai_gioi_han=rule.loai_gioi_han,
                calc_text=f"{kind_label}: {expr}{co_suffix} ({row_tag})",
                summary_text=f"{expr}{co_suffix}",
                ref_text=f"{ref_expr}{co_suffix}",
                ref_calc_text=f"Tham khảo {kind_label.lower()}: {ref_expr}{co_suffix} ({row_tag})",
                rule=rule,
                used_weight=used_weight,
                co_med_names=co_med_names,
            )
        )

    if rule.lieu_toi_da_lan is not None:
        limit_mg, limit_unit = _limit_to_mg(rule.lieu_toi_da_lan)
        if limit_mg is not None:
            if conv.mode == "mass_mg" and conv.value is not None:
                _add_check(
                    exceeded=conv.value > limit_mg,
                    kind_label="Liều lần",
                    lhs=f"{_fmt_num(conv.value)} mg/lần",
                    limit=f"{_fmt_num(limit_mg)} mg/lần",
                    used_weight=False,
                )
            elif conv.mode == "mg_per_kg" and conv.value is not None:
                if weight_kg is None:
                    missing_weight = True
                else:
                    dose_mg = conv.value * weight_kg
                    lhs = (
                        f"{_fmt_num(conv.value)} mg/kg × {_fmt_num(weight_kg)} kg "
                        f"= {_fmt_num(dose_mg)} mg/lần"
                    )
                    _add_check(
                        exceeded=dose_mg > limit_mg,
                        kind_label="Liều lần",
                        lhs=lhs,
                        limit=f"{_fmt_num(limit_mg)} mg/lần",
                        used_weight=True,
                    )
            else:
                unit_mismatch = True
        elif conv.mode == "other" and conv.value is not None and conv.unit == limit_unit:
            limit_val = float(rule.lieu_toi_da_lan.gia_tri)
            _add_check(
                exceeded=conv.value > limit_val,
                kind_label="Liều lần",
                lhs=f"{_fmt_num(conv.value)} {limit_unit}/lần",
                limit=f"{_fmt_num(limit_val)} {limit_unit}/lần",
                used_weight=False,
            )
        else:
            unit_mismatch = True

    if rule.lieu_toi_da_ngay is not None and freq is not None:
        limit_mg, limit_unit = _limit_to_mg(rule.lieu_toi_da_ngay)
        if limit_mg is not None:
            if conv.mode == "mass_mg" and conv.value is not None:
                daily_mg = conv.value * freq
                lhs = f"{_fmt_num(conv.value)} mg × {freq} lần = {_fmt_num(daily_mg)} mg/ngày"
                _add_check(
                    exceeded=daily_mg > limit_mg,
                    kind_label="Liều ngày",
                    lhs=lhs,
                    limit=f"{_fmt_num(limit_mg)} mg/ngày",
                    used_weight=False,
                )
            elif conv.mode == "mg_per_kg" and conv.value is not None:
                if weight_kg is None:
                    missing_weight = True
                else:
                    daily_mg = conv.value * weight_kg * freq
                    lhs = (
                        f"{_fmt_num(conv.value)} mg/kg × {_fmt_num(weight_kg)} kg "
                        f"× {freq} lần = {_fmt_num(daily_mg)} mg/ngày"
                    )
                    _add_check(
                        exceeded=daily_mg > limit_mg,
                        kind_label="Liều ngày",
                        lhs=lhs,
                        limit=f"{_fmt_num(limit_mg)} mg/ngày",
                        used_weight=True,
                    )
            else:
                unit_mismatch = True
        elif conv.mode == "other" and conv.value is not None and conv.unit == limit_unit:
            daily_val = conv.value * freq
            limit_val = float(rule.lieu_toi_da_ngay.gia_tri)
            lhs = (
                f"{_fmt_num(conv.value)} {limit_unit} × {freq} lần = "
                f"{_fmt_num(daily_val)} {limit_unit}/ngày"
            )
            _add_check(
                exceeded=daily_val > limit_val,
                kind_label="Liều ngày",
                lhs=lhs,
                limit=f"{_fmt_num(limit_val)} {limit_unit}/ngày",
                used_weight=False,
            )
        else:
            unit_mismatch = True

    if rule.theo_kg is not None:
        lan_kg_limit = _max_kg_value(rule.theo_kg.lan_mg_kg)
        if lan_kg_limit is not None:
            if conv.mode == "mg_per_kg" and conv.value is not None:
                _add_check(
                    exceeded=conv.value > lan_kg_limit,
                    kind_label="Liều lần theo kg",
                    lhs=f"{_fmt_num(conv.value)} mg/kg/lần",
                    limit=f"{_fmt_num(lan_kg_limit)} mg/kg/lần",
                    used_weight=False,
                )
            elif conv.mode == "mass_mg" and conv.value is not None:
                if weight_kg is None:
                    missing_weight = True
                else:
                    actual_kg = conv.value / weight_kg
                    lhs = (
                        f"{_fmt_num(conv.value)} mg / {_fmt_num(weight_kg)} kg "
                        f"= {_fmt_num(actual_kg)} mg/kg/lần"
                    )
                    _add_check(
                        exceeded=actual_kg > lan_kg_limit,
                        kind_label="Liều lần theo kg",
                        lhs=lhs,
                        limit=f"{_fmt_num(lan_kg_limit)} mg/kg/lần",
                        used_weight=True,
                    )
            else:
                unit_mismatch = True

        ngay_kg_limit = _max_kg_value(rule.theo_kg.ngay_mg_kg)
        if ngay_kg_limit is not None and freq is not None:
            if conv.mode == "mg_per_kg" and conv.value is not None:
                daily_kg = conv.value * freq
                lhs = f"{_fmt_num(conv.value)} mg/kg × {freq} lần = {_fmt_num(daily_kg)} mg/kg/ngày"
                _add_check(
                    exceeded=daily_kg > ngay_kg_limit,
                    kind_label="Liều ngày theo kg",
                    lhs=lhs,
                    limit=f"{_fmt_num(ngay_kg_limit)} mg/kg/ngày",
                    used_weight=False,
                )
            elif conv.mode == "mass_mg" and conv.value is not None:
                if weight_kg is None:
                    missing_weight = True
                else:
                    daily_mg = conv.value * freq
                    actual_kg = daily_mg / weight_kg
                    dose_expr = (
                        f"{_fmt_num(conv.value)} mg"
                        if freq == 1
                        else f"({_fmt_num(conv.value)} mg × {freq} lần)"
                    )
                    lhs = (
                        f"{dose_expr} / {_fmt_num(weight_kg)} kg = {_fmt_num(actual_kg)} mg/kg/ngày"
                    )
                    _add_check(
                        exceeded=actual_kg > ngay_kg_limit,
                        kind_label="Liều ngày theo kg",
                        lhs=lhs,
                        limit=f"{_fmt_num(ngay_kg_limit)} mg/kg/ngày",
                        used_weight=True,
                    )
            else:
                unit_mismatch = True

    return checks, missing_weight, unit_mismatch


def _build_line_data_evidence(
    line: ChiTietYLenh,
    label: str,
    weight_vital: SinhHieu | None,
    weight_kg: float | None,
    include_weight: bool,
) -> list[CanCu]:
    """Tạo danh sách căn cứ dữ liệu gồm liều dòng và cân nặng (nếu dùng)."""
    freq_text = (
        f"{line.so_lan_moi_ngay} lần/ngày" if line.so_lan_moi_ngay is not None else "chưa rõ"
    )
    dose_text = (
        f"{_fmt_num(line.lieu_moi_lan)} {line.don_vi_lieu or ''}".strip()
        if line.lieu_moi_lan is not None
        else "chưa rõ"
    )
    evidences = [
        CanCu(
            loai="du_lieu",
            ban_ghi_id=line.chi_tiet_y_lenh_id,
            mo_ta=(
                f"{label}: liều {dose_text}, tần suất {freq_text}, "
                f"đường dùng '{line.duong_dung or ''}'"
            ),
        )
    ]
    if include_weight and weight_vital is not None and weight_kg is not None:
        evidences.append(
            CanCu(
                loai="du_lieu",
                ban_ghi_id=weight_vital.sinh_hieu_id,
                mo_ta=(
                    f"Cân nặng: {_fmt_num(weight_kg)} kg "
                    f"lúc {weight_vital.thoi_diem_do.isoformat()}"
                ),
            )
        )
    return evidences


def _match_co_meds(
    rule: MaxDoseRule,
    other_med_by_hc: dict[str, list[str]],
) -> tuple[bool, tuple[str, ...]]:
    """Kiểm tra thuốc dùng cùng bắt buộc của hàng và trả về danh sách nhãn khớp."""
    if not rule.thuoc_dung_cung_hoat_chat_ids:
        return True, ()
    matched_labels: list[str] = []
    for co_hc in rule.thuoc_dung_cung_hoat_chat_ids:
        if co_hc in other_med_by_hc:
            matched_labels.append(f"{co_hc} ({', '.join(other_med_by_hc[co_hc])})")
    if not matched_labels:
        return False, ()
    return True, tuple(matched_labels)


def _describe_row_limits(rule: MaxDoseRule) -> str:
    """Mô tả ngắn các trần liều có trên một hàng bảng khi chưa tính so sánh được."""
    parts: list[str] = []
    if rule.lieu_toi_da_lan is not None:
        lan = rule.lieu_toi_da_lan
        parts.append(f"trần lần {_fmt_num(lan.gia_tri)} {lan.don_vi}/lần")
    if rule.lieu_toi_da_ngay is not None:
        ngay = rule.lieu_toi_da_ngay
        parts.append(f"trần ngày {_fmt_num(ngay.gia_tri)} {ngay.don_vi}/ngày")
    if rule.lieu_toi_da_tuan is not None:
        tuan = rule.lieu_toi_da_tuan
        parts.append(f"trần tuần {_fmt_num(tuan.gia_tri)} {tuan.don_vi}/tuần")
    if rule.theo_kg is not None:
        lan_kg = _max_kg_value(rule.theo_kg.lan_mg_kg)
        if lan_kg is not None:
            parts.append(f"trần lần {_fmt_num(lan_kg)} mg/kg/lần")
        ngay_kg = _max_kg_value(rule.theo_kg.ngay_mg_kg)
        if ngay_kg is not None:
            parts.append(f"trần ngày {_fmt_num(ngay_kg)} mg/kg/ngày")
    return ", ".join(parts) if parts else "xem chi tiết nhãn"


def _build_conditional_only_finding(
    *,
    line: ChiTietYLenh,
    label: str,
    hc_id: str,
    hc_name: str,
    conv: _DoseConversion,
    freq: int | None,
    tuoi: int | None,
    weight_vital: SinhHieu | None,
    weight_kg: float | None,
    route_rows: list[MaxDoseRule],
    active_config: MaxDoseConfig,
    other_med_by_hc: dict[str, list[str]],
    missing_notes_by_hc: dict[str, str],
) -> PhatHien:
    """Tạo phát hiện khi hoạt chất khớp đường dùng nhưng mọi hàng đều có điều kiện đặc biệt."""
    needs_weight = False
    needs_age = False
    row_descriptions: list[str] = []
    ref_checks: list[_LimitCheck] = []
    src_evidences: list[CanCu] = []

    for row in route_rows:
        cond_text = _special_condition_text(row, active_config) or "điều kiện đặc biệt"
        src_ev = _build_source_evidence(row)
        if src_ev is not None:
            src_evidences.append(src_ev)

        defn = active_config.doi_tuong_dinh_nghia.get(row.doi_tuong)
        if defn is not None or row.doi_tuong in {"nguoi_lon", "nguoi_lon_va_tre_em"}:
            pop_ok, pop_missing = _matches_population(row, active_config, tuoi, weight_kg)
            if "tuoi" in pop_missing:
                needs_age = True
            if "can_nang" in pop_missing:
                needs_weight = True
        else:
            pop_ok = True

        has_kg_limit = row.theo_kg is not None and (
            row.theo_kg.lan_mg_kg is not None or row.theo_kg.ngay_mg_kg is not None
        )
        if has_kg_limit and weight_kg is None and conv.mode != "mg_per_kg":
            needs_weight = True

        co_ok, co_names = _match_co_meds(row, other_med_by_hc)
        row_checks: list[_LimitCheck] = []
        row_missing_wt = False
        if pop_ok and co_ok:
            row_checks, row_missing_wt, _ = _compare_row(
                rule=row,
                conv=conv,
                freq=freq,
                weight_kg=weight_kg,
                co_med_names=co_names,
            )
            if row_missing_wt:
                needs_weight = True
            ref_checks.extend(row_checks)

        if row_checks:
            calc_summary = "; ".join(item.ref_text for item in row_checks)
            if row_missing_wt:
                calc_summary = f"{calc_summary}; {_describe_row_limits(row)}"
            row_descriptions.append(f"nếu là {cond_text}: {calc_summary}")
        else:
            row_descriptions.append(f"nếu là {cond_text}: {_describe_row_limits(row)}")

    missing_info = ["dieu_kien_ap_dung"]
    if needs_weight:
        missing_info.append("can_nang")
    if needs_age:
        missing_info.append("tuoi")

    used_weight = any(item.used_weight for item in ref_checks)
    evidences = _build_line_data_evidence(line, label, weight_vital, weight_kg, used_weight)
    for item in ref_checks:
        evidences.append(
            CanCu(
                loai="tinh_toan",
                ban_ghi_id=item.rule.ma_dong or None,
                mo_ta=item.ref_calc_text,
            )
        )
    evidences.extend(src_evidences)
    if not src_evidences and hc_id in missing_notes_by_hc:
        evidences.append(
            CanCu(
                loai="tai_lieu",
                ban_ghi_id=hc_id,
                mo_ta=(
                    f"Bảng liều tối đa ({hc_id}): {missing_notes_by_hc[hc_id]} (chờ dược sĩ duyệt)"
                ),
            )
        )

    return PhatHien(
        ma_luat="lieu_toi_da_chi_co_muc_dieu_kien",
        yeu_to=_YEU_TO,
        ket_luan="khong_du_du_lieu",
        muc_do=None,
        chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
        mo_ta=(
            f"{label} ({hc_name}): nhãn chỉ có mức theo điều kiện đặc biệt, "
            f"chưa kết luận tự động ({'; '.join(row_descriptions)})"
        ),
        can_cu=_dedupe_evidences(evidences),
        thong_tin_con_thieu=missing_info,
    )


def check(
    ca: CaBenh,
    resolver: DrugResolver | None = None,
    config: MaxDoseConfig | None = None,
) -> list[PhatHien]:
    """Kiểm tra liều tối đa mỗi lần và mỗi ngày cho các dòng thuốc chờ duyệt (yếu tố 3)."""
    if resolver is None:
        return []

    active_config = config if config is not None else try_load_default_max_dose_config()
    if active_config is None:
        return []

    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    missing_notes_by_hc = {item.hoat_chat_id: item.ly_do for item in active_config.khong_ghi_toi_da}

    effective_resolved: dict[str, tuple[set[str], str]] = {}
    for eff_line in effective_lines(ca):
        if eff_line.loai_san_pham != "thuoc":
            continue
        eff_res = resolver.resolve_line(ca, eff_line)
        if _is_line_excluded(eff_res):
            continue
        eff_ids = _extract_resolved_ids(eff_res)
        if eff_ids:
            effective_resolved[eff_line.chi_tiet_y_lenh_id] = (
                eff_ids,
                line_label(eff_line, thuoc_by_id),
            )

    weight_vital = latest_vital(ca, "can_nang")
    weight_kg = _weight_in_kg(weight_vital)
    tuoi = ca.nguoi_benh.tuoi
    findings: list[PhatHien] = []

    for line in pending_lines(ca):
        if line.loai_san_pham != "thuoc":
            continue

        result = resolver.resolve_line(ca, line)
        if _is_line_excluded(result):
            continue

        label = line_label(line, thuoc_by_id)
        resolved_ids = _extract_resolved_ids(result)
        if result.trang_thai == "khong_nhan_dien" or not resolved_ids:
            reason = f" ({result.ly_do})" if result.ly_do else ""
            findings.append(
                PhatHien(
                    ma_luat="lieu_toi_da_thieu_du_lieu",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=f"{label}: chưa nhận diện được hoạt chất để kiểm liều tối đa{reason}",
                    can_cu=[
                        CanCu(
                            loai="du_lieu",
                            ban_ghi_id=line.chi_tiet_y_lenh_id,
                            mo_ta=f"Phân giải '{label}' trạng thái {result.trang_thai}{reason}",
                        ),
                    ],
                    thong_tin_con_thieu=["hoat_chat"],
                )
            )
            continue

        partial_reason: str | None = None
        if result.trang_thai == "mot_phan":
            partial_reason = result.ly_do or "một phần thành phần"
            findings.append(
                PhatHien(
                    ma_luat="lieu_toi_da_thieu_du_lieu",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=(
                        f"{label}: chỉ phân giải được một phần hoạt chất ({partial_reason}), "
                        "không thể kết luận đạt liều tối đa"
                    ),
                    can_cu=[
                        CanCu(
                            loai="du_lieu",
                            ban_ghi_id=line.chi_tiet_y_lenh_id,
                            mo_ta=f"Phân giải '{label}' trạng thái mot_phan ({partial_reason})",
                        ),
                    ],
                    thong_tin_con_thieu=["hoat_chat"],
                )
            )

        if line.lieu_moi_lan is None:
            findings.append(
                PhatHien(
                    ma_luat="lieu_toi_da_thieu_du_lieu",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=f"{label}: thiếu liều mỗi lần (lieu_moi_lan)",
                    can_cu=_build_line_data_evidence(line, label, weight_vital, weight_kg, False),
                    thong_tin_con_thieu=["lieu_moi_lan"],
                )
            )
            continue

        if line.don_vi_lieu is None or not line.don_vi_lieu.strip():
            findings.append(
                PhatHien(
                    ma_luat="lieu_toi_da_thieu_du_lieu",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=f"{label}: thiếu đơn vị liều (don_vi_lieu)",
                    can_cu=_build_line_data_evidence(line, label, weight_vital, weight_kg, False),
                    thong_tin_con_thieu=["don_vi_lieu"],
                )
            )
            continue

        if line.duong_dung is None or not line.duong_dung.strip():
            findings.append(
                PhatHien(
                    ma_luat="lieu_toi_da_thieu_du_lieu",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=f"{label}: thiếu đường dùng để đối chiếu bảng liều tối đa",
                    can_cu=_build_line_data_evidence(line, label, weight_vital, weight_kg, False),
                    thong_tin_con_thieu=["duong_dung"],
                )
            )
            continue

        ordered_route, route_err = normalize_route_default(line.duong_dung)
        if ordered_route is None:
            detail = f" ({route_err})" if route_err else ""
            findings.append(
                PhatHien(
                    ma_luat="lieu_toi_da_thieu_du_lieu",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=(f"{label}: không chuẩn hoá được đường dùng '{line.duong_dung}'{detail}"),
                    can_cu=_build_line_data_evidence(line, label, weight_vital, weight_kg, False),
                    thong_tin_con_thieu=["duong_dung_chuan_hoa"],
                )
            )
            continue

        thuoc = thuoc_by_id.get(line.thuoc_id) if line.thuoc_id else None
        freq: int | None = None
        if line.so_lan_moi_ngay is not None and line.so_lan_moi_ngay > 0:
            freq = line.so_lan_moi_ngay
        missing_freq = freq is None

        other_med_by_hc: dict[str, list[str]] = {}
        for other_id, (other_hc_ids, other_label) in effective_resolved.items():
            if other_id == line.chi_tiet_y_lenh_id:
                continue
            for other_hc in other_hc_ids:
                other_med_by_hc.setdefault(other_hc, []).append(other_label)

        seen_hc: set[str] = set()
        components: list[ThanhPhanPhanGiai] = []
        for comp in result.thanh_phan:
            if comp.hoat_chat_id and comp.hoat_chat_id not in seen_hc:
                seen_hc.add(comp.hoat_chat_id)
                components.append(comp)

        resolved_count = len(components)
        if resolved_count > 1 and _normalize_unit(line.don_vi_lieu) in _MASS_TO_MG:
            findings.append(
                PhatHien(
                    ma_luat="lieu_toi_da_thieu_du_lieu",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=(
                        f"{label}: thuốc nhiều thành phần kê theo đơn vị khối lượng "
                        f"'{line.don_vi_lieu}', cần hàm lượng từng thành phần"
                    ),
                    can_cu=_build_line_data_evidence(line, label, weight_vital, weight_kg, False),
                    thong_tin_con_thieu=["ham_luong_thanh_phan"],
                )
            )
            continue

        need_missing_freq_finding = False
        had_missing_freq_context = False

        for comp in components:
            hc_id = comp.hoat_chat_id
            hc_name = comp.ten_inn or hc_id
            conv = _convert_line_dose(line, comp, thuoc, resolved_count)

            if conv.mode == "missing" and conv.missing_field is not None:
                findings.append(
                    PhatHien(
                        ma_luat="lieu_toi_da_thieu_du_lieu",
                        yeu_to=_YEU_TO,
                        ket_luan="khong_du_du_lieu",
                        muc_do=None,
                        chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                        mo_ta=(
                            f"{label} ({hc_name}): thiếu {conv.missing_field} "
                            "để quy đổi liều sang mg"
                        ),
                        can_cu=_build_line_data_evidence(
                            line, label, weight_vital, weight_kg, False
                        ),
                        thong_tin_con_thieu=[conv.missing_field],
                    )
                )
                continue

            route_rows = [
                row
                for row in active_config.nhom
                if hc_id in row.hoat_chat_ids
                and row.loai_gioi_han != "gioi_han_thiet_bi"
                and any(
                    is_same_route_or_iv(ordered_route, normalize_route_default(r)[0] or r)
                    for r in row.duong_dung
                )
            ]

            special_notes: list[str] = []
            auto_rows: list[MaxDoseRule] = []
            for row in route_rows:
                special_text = _special_condition_text(row, active_config)
                if special_text is not None:
                    if special_text not in special_notes:
                        special_notes.append(special_text)
                else:
                    auto_rows.append(row)

            special_suffix = (
                f"; nhãn có mức riêng cho: {'; '.join(special_notes)}" if special_notes else ""
            )

            if route_rows and not auto_rows:
                findings.append(
                    _build_conditional_only_finding(
                        line=line,
                        label=label,
                        hc_id=hc_id,
                        hc_name=hc_name,
                        conv=conv,
                        freq=freq,
                        tuoi=tuoi,
                        weight_vital=weight_vital,
                        weight_kg=weight_kg,
                        route_rows=route_rows,
                        active_config=active_config,
                        other_med_by_hc=other_med_by_hc,
                        missing_notes_by_hc=missing_notes_by_hc,
                    )
                )
                continue

            co_filtered: list[tuple[MaxDoseRule, tuple[str, ...]]] = []
            for row in auto_rows:
                co_ok, matched_labels = _match_co_meds(row, other_med_by_hc)
                if co_ok:
                    co_filtered.append((row, matched_labels))

            applicable_rows: list[tuple[MaxDoseRule, tuple[str, ...]]] = []
            missing_pop_fields: set[str] = set()
            for row, co_names in co_filtered:
                ok, missing_fields = _matches_population(row, active_config, tuoi, weight_kg)
                if ok:
                    applicable_rows.append((row, co_names))
                else:
                    missing_pop_fields.update(missing_fields)

            if not applicable_rows:
                if missing_pop_fields:
                    missing_list = sorted(missing_pop_fields)
                    findings.append(
                        PhatHien(
                            ma_luat="lieu_toi_da_thieu_du_lieu",
                            yeu_to=_YEU_TO,
                            ket_luan="khong_du_du_lieu",
                            muc_do=None,
                            chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                            mo_ta=(
                                f"{label} ({hc_name}): thiếu {', '.join(missing_list)} "
                                f"để xác định mức liều tối đa áp dụng{special_suffix}"
                            ),
                            can_cu=_build_line_data_evidence(
                                line, label, weight_vital, weight_kg, False
                            ),
                            thong_tin_con_thieu=missing_list,
                        )
                    )
                else:
                    reason = missing_notes_by_hc.get(hc_id)
                    reason_text = f": {reason}" if reason else ""
                    evidences = _build_line_data_evidence(
                        line, label, weight_vital, weight_kg, False
                    )
                    if reason:
                        evidences.append(
                            CanCu(
                                loai="tai_lieu",
                                ban_ghi_id=hc_id,
                                mo_ta=f"Bảng liều tối đa ({hc_id}): {reason} (chờ dược sĩ duyệt)",
                            )
                        )
                    findings.append(
                        PhatHien(
                            ma_luat="lieu_toi_da_khong_co_nguon",
                            yeu_to=_YEU_TO,
                            ket_luan="khong_du_du_lieu",
                            muc_do=None,
                            chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                            mo_ta=(
                                f"{label} ({hc_name}): không có trần liều tối đa áp dụng "
                                f"trong nguồn đã lấy{reason_text}{special_suffix}"
                            ),
                            can_cu=evidences,
                            thong_tin_con_thieu=["nguon_lieu_toi_da"],
                        )
                    )
                continue

            all_checks: list[_LimitCheck] = []
            any_missing_weight = False
            any_unit_mismatch = False
            for row, co_names in applicable_rows:
                row_checks, row_missing_wt, row_unit_err = _compare_row(
                    rule=row,
                    conv=conv,
                    freq=freq,
                    weight_kg=weight_kg,
                    co_med_names=co_names,
                )
                all_checks.extend(row_checks)
                any_missing_weight = any_missing_weight or row_missing_wt
                any_unit_mismatch = any_unit_mismatch or row_unit_err

            if missing_freq:
                had_missing_freq_context = True

            exceeded_checks = [item for item in all_checks if item.exceeded]
            if exceeded_checks:
                hard_exceeded = [
                    item for item in exceeded_checks if item.loai_gioi_han != "tran_up_to"
                ]
                chosen_checks = hard_exceeded or exceeded_checks
                if hard_exceeded:
                    ma_luat = "lieu_toi_da_vuot"
                    muc_do: _MucDo = "nghiem_trong"
                else:
                    ma_luat = "lieu_toi_da_vuot_tran_mem"
                    muc_do = "can_luu_y"

                used_weight = any(item.used_weight for item in all_checks)
                evidences = _build_line_data_evidence(
                    line, label, weight_vital, weight_kg, used_weight
                )
                for item in all_checks:
                    evidences.append(
                        CanCu(
                            loai="tinh_toan",
                            ban_ghi_id=item.rule.ma_dong or None,
                            mo_ta=item.calc_text,
                        )
                    )
                    src_ev = _build_source_evidence(item.rule)
                    if src_ev is not None:
                        evidences.append(src_ev)

                summary = "; ".join(item.summary_text for item in chosen_checks)
                findings.append(
                    PhatHien(
                        ma_luat=ma_luat,
                        yeu_to=_YEU_TO,
                        ket_luan="can_xem",
                        muc_do=muc_do,
                        chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                        mo_ta=f"{label} ({hc_name}): {summary} (nhãn FDA){special_suffix}",
                        can_cu=_dedupe_evidences(evidences),
                    )
                )
                if missing_freq:
                    need_missing_freq_finding = True
                continue

            if any_missing_weight:
                findings.append(
                    PhatHien(
                        ma_luat="lieu_toi_da_thieu_du_lieu",
                        yeu_to=_YEU_TO,
                        ket_luan="khong_du_du_lieu",
                        muc_do=None,
                        chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                        mo_ta=(
                            f"{label} ({hc_name}): thiếu cân nặng để đối chiếu trần liều "
                            f"theo kg{special_suffix}"
                        ),
                        can_cu=_build_line_data_evidence(
                            line, label, weight_vital, weight_kg, False
                        ),
                        thong_tin_con_thieu=["can_nang"],
                    )
                )
                continue

            if all_checks:
                used_weight = any(item.used_weight for item in all_checks)
                evidences = _build_line_data_evidence(
                    line, label, weight_vital, weight_kg, used_weight
                )
                for item in all_checks:
                    evidences.append(
                        CanCu(
                            loai="tinh_toan",
                            ban_ghi_id=item.rule.ma_dong or None,
                            mo_ta=item.calc_text,
                        )
                    )
                    src_ev = _build_source_evidence(item.rule)
                    if src_ev is not None:
                        evidences.append(src_ev)

                summary = "; ".join(item.summary_text for item in all_checks)
                if partial_reason is None:
                    findings.append(
                        PhatHien(
                            ma_luat="lieu_toi_da_trong_gioi_han",
                            yeu_to=_YEU_TO,
                            ket_luan="dat",
                            muc_do="thong_tin",
                            chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                            mo_ta=(
                                f"{label} ({hc_name}): trong giới hạn tối đa "
                                f"({summary}; nhãn FDA){special_suffix}"
                            ),
                            can_cu=_dedupe_evidences(evidences),
                        )
                    )
                if missing_freq:
                    need_missing_freq_finding = True
                continue

            if any_unit_mismatch:
                findings.append(
                    PhatHien(
                        ma_luat="lieu_toi_da_thieu_du_lieu",
                        yeu_to=_YEU_TO,
                        ket_luan="khong_du_du_lieu",
                        muc_do=None,
                        chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                        mo_ta=(
                            f"{label} ({hc_name}): đơn vị liều '{line.don_vi_lieu}' "
                            f"không quy đổi được sang đơn vị trần của bảng{special_suffix}"
                        ),
                        can_cu=_build_line_data_evidence(
                            line, label, weight_vital, weight_kg, False
                        ),
                        thong_tin_con_thieu=["don_vi_lieu_quy_doi"],
                    )
                )
                continue

            if missing_freq:
                need_missing_freq_finding = True

        if need_missing_freq_finding or (missing_freq and had_missing_freq_context):
            findings.append(
                PhatHien(
                    ma_luat="lieu_toi_da_thieu_du_lieu",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=(
                        f"{label}: thiếu số lần dùng mỗi ngày (so_lan_moi_ngay) để kiểm liều ngày"
                    ),
                    can_cu=_build_line_data_evidence(line, label, weight_vital, weight_kg, False),
                    thong_tin_con_thieu=["so_lan_moi_ngay"],
                )
            )

    return findings
