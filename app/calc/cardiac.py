"""Các công thức hiệu chỉnh khoảng QT theo nhịp tim (QTc)."""

import math
from collections.abc import Callable

from app.calc.types import CalcInput, CalcResult, validate_range

_VERSION = "1.0"
_QT_MIN_MS = 100.0
_QT_MAX_MS = 1000.0
_HR_MIN_BPM = 20.0
_HR_MAX_BPM = 300.0


def _missing_result(
    cong_thuc: str,
    thieu_dau_vao: list[str],
    tham_khao: str,
) -> CalcResult:
    return CalcResult(
        cong_thuc=cong_thuc,
        phien_ban=_VERSION,
        ket_qua=None,
        don_vi="ms",
        dau_vao=[],
        thieu_dau_vao=thieu_dau_vao,
        ghi_chu=[],
        tham_khao=tham_khao,
    )


def _compute_qtc(
    cong_thuc: str,
    qt_ms: float | None,
    nhip_tim: float | None,
    tham_khao: str,
    formula: Callable[[float, float, float], float],
) -> CalcResult:
    validate_range("qt_ms", qt_ms, _QT_MIN_MS, _QT_MAX_MS)
    validate_range("nhip_tim", nhip_tim, _HR_MIN_BPM, _HR_MAX_BPM)

    missing: list[str] = []
    if qt_ms is None:
        missing.append("qt_ms")
    if nhip_tim is None:
        missing.append("nhip_tim")
    if missing:
        return _missing_result(cong_thuc, missing, tham_khao)

    assert qt_ms is not None and nhip_tim is not None
    qt_val = float(qt_ms)
    hr_val = float(nhip_tim)
    rr_sec = 60.0 / hr_val
    ket_qua = formula(qt_val, hr_val, rr_sec)

    return CalcResult(
        cong_thuc=cong_thuc,
        phien_ban=_VERSION,
        ket_qua=ket_qua,
        don_vi="ms",
        dau_vao=[
            CalcInput(ten="qt_ms", gia_tri=qt_val, don_vi="ms"),
            CalcInput(ten="nhip_tim", gia_tri=hr_val, don_vi="lan/phut"),
        ],
        thieu_dau_vao=[],
        ghi_chu=[],
        tham_khao=tham_khao,
    )


def qtc_bazett(qt_ms: float | None, nhip_tim: float | None) -> CalcResult:
    """Tính QTc theo công thức Bazett: QT / sqrt(RR)."""
    return _compute_qtc(
        cong_thuc="qtc_bazett",
        qt_ms=qt_ms,
        nhip_tim=nhip_tim,
        tham_khao="Bazett HC. Heart 1920;7:353-70.",
        formula=lambda qt, _hr, rr: qt / math.sqrt(rr),
    )


def qtc_fridericia(qt_ms: float | None, nhip_tim: float | None) -> CalcResult:
    """Tính QTc theo công thức Fridericia: QT / RR^(1/3)."""
    return _compute_qtc(
        cong_thuc="qtc_fridericia",
        qt_ms=qt_ms,
        nhip_tim=nhip_tim,
        tham_khao=(
            "Fridericia LS. Acta Med Scand 1920;53:469-86 "
            "(bản dịch Ann Noninvasive Electrocardiol 2003;8(4):343-51)."
        ),
        formula=lambda qt, _hr, rr: qt / (rr ** (1.0 / 3.0)),
    )


def qtc_framingham(qt_ms: float | None, nhip_tim: float | None) -> CalcResult:
    """Tính QTc theo công thức Framingham (Sagie): QT + 154 * (1 - RR)."""
    return _compute_qtc(
        cong_thuc="qtc_framingham",
        qt_ms=qt_ms,
        nhip_tim=nhip_tim,
        tham_khao="Sagie A, et al. Am J Cardiol 1992;70:797-801.",
        formula=lambda qt, _hr, rr: qt + 154.0 * (1.0 - rr),
    )


def qtc_hodges(qt_ms: float | None, nhip_tim: float | None) -> CalcResult:
    """Tính QTc theo công thức Hodges: QT + 1.75 * (nhịp tim - 60)."""
    return _compute_qtc(
        cong_thuc="qtc_hodges",
        qt_ms=qt_ms,
        nhip_tim=nhip_tim,
        tham_khao="Hodges M, et al. J Am Coll Cardiol 1983;1:694.",
        formula=lambda qt, hr, _rr: qt + 1.75 * (hr - 60.0),
    )


def qtc_rautaharju(qt_ms: float | None, nhip_tim: float | None) -> CalcResult:
    """Tính QTc theo công thức Rautaharju: QT * (120 + nhịp tim) / 180."""
    return _compute_qtc(
        cong_thuc="qtc_rautaharju",
        qt_ms=qt_ms,
        nhip_tim=nhip_tim,
        tham_khao="Rautaharju PM, et al. Int J Cardiol 2014;174(3):535-40.",
        formula=lambda qt, hr, _rr: qt * (120.0 + hr) / 180.0,
    )
