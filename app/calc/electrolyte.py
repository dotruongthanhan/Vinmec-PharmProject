"""Các công thức điện giải (canxi hiệu chỉnh theo albumin)."""

import math

from app.calc.types import CalcInput, CalcResult, validate_range
from app.calc.units import albumin_to_g_dl, calcium_mg_dl_to_mmol_l, calcium_to_mg_dl

_VERSION = "1.0"
_DEFAULT_NORMAL_ALBUMIN_G_DL = 4.0
_CALCIUM_MAX_MG_DL = 30.0
_ALBUMIN_MAX_G_DL = 10.0
_THAM_KHAO = (
    "Payne RB, Little AJ, Williams RB, Milner JR. "
    "Interpretation of serum calcium in patients with abnormal serum proteins. "
    "BMJ 1973;4(5893):643-6."
)


def _missing_result(don_vi: str, thieu_dau_vao: list[str]) -> CalcResult:
    return CalcResult(
        cong_thuc="calcium_corrected",
        phien_ban=_VERSION,
        ket_qua=None,
        don_vi=don_vi,
        dau_vao=[],
        thieu_dau_vao=thieu_dau_vao,
        ghi_chu=[],
        tham_khao=_THAM_KHAO,
    )


def _validate_positive_finite(name: str, value: float | None) -> None:
    if value is None:
        return
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"Tham số {name} phải là số dương hữu hạn: {value}")


def _validate_calcium(canxi: float | None, canxi_don_vi: str | None) -> float | None:
    if canxi_don_vi is not None:
        calcium_to_mg_dl(1.0, canxi_don_vi)
    if canxi is None:
        return None
    if canxi_don_vi is None:
        _validate_positive_finite("canxi", canxi)
        return None
    ca_mg_dl = calcium_to_mg_dl(canxi, canxi_don_vi)
    validate_range("canxi", ca_mg_dl, 0.0, _CALCIUM_MAX_MG_DL, strict_min=True)
    return ca_mg_dl


def _validate_albumin(albumin: float | None, albumin_don_vi: str | None) -> float | None:
    if albumin_don_vi is not None:
        albumin_to_g_dl(1.0, albumin_don_vi)
    if albumin is None:
        return None
    if albumin_don_vi is None:
        _validate_positive_finite("albumin", albumin)
        return None
    alb_g_dl = albumin_to_g_dl(albumin, albumin_don_vi)
    validate_range("albumin", alb_g_dl, 0.0, _ALBUMIN_MAX_G_DL, strict_min=True)
    return alb_g_dl


def calcium_corrected(
    canxi: float | None,
    canxi_don_vi: str | None,
    albumin: float | None,
    albumin_don_vi: str | None,
    albumin_binh_thuong: float = _DEFAULT_NORMAL_ALBUMIN_G_DL,
) -> CalcResult:
    """Tính canxi toàn phần hiệu chỉnh theo albumin (Payne 1973)."""
    validate_range(
        "albumin_binh_thuong",
        albumin_binh_thuong,
        0.0,
        _ALBUMIN_MAX_G_DL,
        strict_min=True,
    )
    ca_mg_dl = _validate_calcium(canxi, canxi_don_vi)
    alb_g_dl = _validate_albumin(albumin, albumin_don_vi)

    missing: list[str] = []
    if canxi is None:
        missing.append("canxi")
    if canxi_don_vi is None:
        missing.append("canxi_don_vi")
    if albumin is None:
        missing.append("albumin")
    if albumin_don_vi is None:
        missing.append("albumin_don_vi")
    if missing:
        fallback_unit = "mg/dL"
        if canxi_don_vi is not None:
            fallback_unit = "mg/dL" if canxi_don_vi.strip().lower() == "mg/dl" else "mmol/L"
        return _missing_result(fallback_unit, missing)

    assert canxi is not None and canxi_don_vi is not None
    assert albumin is not None and albumin_don_vi is not None
    assert ca_mg_dl is not None and alb_g_dl is not None

    ca_corr_mg_dl = ca_mg_dl + 0.8 * (float(albumin_binh_thuong) - alb_g_dl)
    ca_corr_mmol_l = calcium_mg_dl_to_mmol_l(ca_corr_mg_dl)

    input_unit_norm = canxi_don_vi.strip().lower()
    if input_unit_norm == "mg/dl":
        don_vi = "mg/dL"
        ket_qua = ca_corr_mg_dl
        ghi_chu = [f"Giá trị theo mmol/L: {ca_corr_mmol_l:.4f} mmol/L"]
    else:
        don_vi = "mmol/L"
        ket_qua = ca_corr_mmol_l
        ghi_chu = [f"Giá trị theo mg/dL: {ca_corr_mg_dl:.4f} mg/dL"]

    if float(albumin_binh_thuong) == _DEFAULT_NORMAL_ALBUMIN_G_DL:
        ghi_chu.append(f"Dùng albumin_binh_thuong mặc định: {_DEFAULT_NORMAL_ALBUMIN_G_DL} g/dL")

    return CalcResult(
        cong_thuc="calcium_corrected",
        phien_ban=_VERSION,
        ket_qua=ket_qua,
        don_vi=don_vi,
        dau_vao=[
            CalcInput(ten="canxi", gia_tri=float(canxi), don_vi=canxi_don_vi),
            CalcInput(ten="albumin", gia_tri=float(albumin), don_vi=albumin_don_vi),
        ],
        thieu_dau_vao=[],
        ghi_chu=ghi_chu,
        tham_khao=_THAM_KHAO,
    )
