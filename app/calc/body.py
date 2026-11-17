"""Các công thức tính chỉ số nhân trắc và cân nặng lâm sàng."""

import math

from app.calc.types import CalcInput, CalcResult, Sex, validate_range, validate_sex
from app.calc.units import cm_to_inch

_VERSION = "1.0"
_HEIGHT_MIN_CM = 20.0
_HEIGHT_MAX_CM = 250.0
_WEIGHT_MIN_KG = 0.3
_WEIGHT_MAX_KG = 400.0
_DEVINE_MIN_INCH = 60.0
_DEVINE_SHORT_NOTE = "chieu cao duoi 152.4 cm: cong thuc Devine kem tin cay"


def _missing_result(
    cong_thuc: str,
    don_vi: str,
    thieu_dau_vao: list[str],
    tham_khao: str,
) -> CalcResult:
    return CalcResult(
        cong_thuc=cong_thuc,
        phien_ban=_VERSION,
        ket_qua=None,
        don_vi=don_vi,
        dau_vao=[],
        thieu_dau_vao=thieu_dau_vao,
        ghi_chu=[],
        tham_khao=tham_khao,
    )


def bmi(can_nang_kg: float | None, chieu_cao_cm: float | None) -> CalcResult:
    """Tính chỉ số khối cơ thể (BMI) theo công thức WHO."""
    cong_thuc = "bmi"
    don_vi = "kg/m2"
    tham_khao = "WHO. Body mass index (BMI)."

    validate_range("can_nang_kg", can_nang_kg, _WEIGHT_MIN_KG, _WEIGHT_MAX_KG)
    validate_range("chieu_cao_cm", chieu_cao_cm, _HEIGHT_MIN_CM, _HEIGHT_MAX_CM)

    missing: list[str] = []
    if can_nang_kg is None:
        missing.append("can_nang_kg")
    if chieu_cao_cm is None:
        missing.append("chieu_cao_cm")
    if missing:
        return _missing_result(cong_thuc, don_vi, missing, tham_khao)

    assert can_nang_kg is not None and chieu_cao_cm is not None
    chieu_cao_m = float(chieu_cao_cm) / 100.0
    ket_qua = float(can_nang_kg) / (chieu_cao_m**2)
    return CalcResult(
        cong_thuc=cong_thuc,
        phien_ban=_VERSION,
        ket_qua=ket_qua,
        don_vi=don_vi,
        dau_vao=[
            CalcInput(ten="can_nang_kg", gia_tri=float(can_nang_kg), don_vi="kg"),
            CalcInput(ten="chieu_cao_cm", gia_tri=float(chieu_cao_cm), don_vi="cm"),
        ],
        thieu_dau_vao=[],
        ghi_chu=[],
        tham_khao=tham_khao,
    )


def bsa_mosteller(can_nang_kg: float | None, chieu_cao_cm: float | None) -> CalcResult:
    """Tính diện tích da cơ thể (BSA) theo công thức Mosteller."""
    cong_thuc = "bsa_mosteller"
    don_vi = "m2"
    tham_khao = "Mosteller RD. N Engl J Med 1987;317:1098."

    validate_range("can_nang_kg", can_nang_kg, _WEIGHT_MIN_KG, _WEIGHT_MAX_KG)
    validate_range("chieu_cao_cm", chieu_cao_cm, _HEIGHT_MIN_CM, _HEIGHT_MAX_CM)

    missing: list[str] = []
    if can_nang_kg is None:
        missing.append("can_nang_kg")
    if chieu_cao_cm is None:
        missing.append("chieu_cao_cm")
    if missing:
        return _missing_result(cong_thuc, don_vi, missing, tham_khao)

    assert can_nang_kg is not None and chieu_cao_cm is not None
    ket_qua = math.sqrt((float(chieu_cao_cm) * float(can_nang_kg)) / 3600.0)
    return CalcResult(
        cong_thuc=cong_thuc,
        phien_ban=_VERSION,
        ket_qua=ket_qua,
        don_vi=don_vi,
        dau_vao=[
            CalcInput(ten="can_nang_kg", gia_tri=float(can_nang_kg), don_vi="kg"),
            CalcInput(ten="chieu_cao_cm", gia_tri=float(chieu_cao_cm), don_vi="cm"),
        ],
        thieu_dau_vao=[],
        ghi_chu=[],
        tham_khao=tham_khao,
    )


def bsa_dubois(can_nang_kg: float | None, chieu_cao_cm: float | None) -> CalcResult:
    """Tính diện tích da cơ thể (BSA) theo công thức Du Bois."""
    cong_thuc = "bsa_dubois"
    don_vi = "m2"
    tham_khao = "Du Bois D, Du Bois EF. Arch Intern Med 1916;17:863-871."

    validate_range("can_nang_kg", can_nang_kg, _WEIGHT_MIN_KG, _WEIGHT_MAX_KG)
    validate_range("chieu_cao_cm", chieu_cao_cm, _HEIGHT_MIN_CM, _HEIGHT_MAX_CM)

    missing: list[str] = []
    if can_nang_kg is None:
        missing.append("can_nang_kg")
    if chieu_cao_cm is None:
        missing.append("chieu_cao_cm")
    if missing:
        return _missing_result(cong_thuc, don_vi, missing, tham_khao)

    assert can_nang_kg is not None and chieu_cao_cm is not None
    ket_qua = 0.007184 * (float(can_nang_kg) ** 0.425) * (float(chieu_cao_cm) ** 0.725)
    return CalcResult(
        cong_thuc=cong_thuc,
        phien_ban=_VERSION,
        ket_qua=ket_qua,
        don_vi=don_vi,
        dau_vao=[
            CalcInput(ten="can_nang_kg", gia_tri=float(can_nang_kg), don_vi="kg"),
            CalcInput(ten="chieu_cao_cm", gia_tri=float(chieu_cao_cm), don_vi="cm"),
        ],
        thieu_dau_vao=[],
        ghi_chu=[],
        tham_khao=tham_khao,
    )


def ibw_devine(gioi_tinh: Sex | None, chieu_cao_cm: float | None) -> CalcResult:
    """Tính cân nặng lý tưởng (IBW) theo công thức Devine."""
    cong_thuc = "ibw_devine"
    don_vi = "kg"
    tham_khao = "Devine BJ. Drug Intell Clin Pharm 1974;8:650-655."

    validate_sex(gioi_tinh)
    validate_range("chieu_cao_cm", chieu_cao_cm, _HEIGHT_MIN_CM, _HEIGHT_MAX_CM)

    missing: list[str] = []
    if gioi_tinh is None:
        missing.append("gioi_tinh")
    if chieu_cao_cm is None:
        missing.append("chieu_cao_cm")
    if missing:
        return _missing_result(cong_thuc, don_vi, missing, tham_khao)

    assert gioi_tinh is not None and chieu_cao_cm is not None
    chieu_cao_inch = cm_to_inch(chieu_cao_cm)
    base = 50.0 if gioi_tinh == "nam" else 45.5
    ket_qua = base + 2.3 * (chieu_cao_inch - _DEVINE_MIN_INCH)
    ghi_chu = [_DEVINE_SHORT_NOTE] if chieu_cao_inch < _DEVINE_MIN_INCH else []

    return CalcResult(
        cong_thuc=cong_thuc,
        phien_ban=_VERSION,
        ket_qua=ket_qua,
        don_vi=don_vi,
        dau_vao=[CalcInput(ten="chieu_cao_cm", gia_tri=float(chieu_cao_cm), don_vi="cm")],
        thieu_dau_vao=[],
        ghi_chu=ghi_chu,
        tham_khao=tham_khao,
    )


def adjusted_body_weight(
    gioi_tinh: Sex | None,
    chieu_cao_cm: float | None,
    can_nang_kg: float | None,
) -> CalcResult:
    """Tính cân nặng hiệu chỉnh (AdjBW) dựa trên IBW Devine với hệ số 0.4."""
    cong_thuc = "adjusted_body_weight"
    don_vi = "kg"
    tham_khao = "Bauer LA. Applied Clinical Pharmacokinetics. Hệ số hiệu chỉnh 0.4."

    validate_sex(gioi_tinh)
    validate_range("chieu_cao_cm", chieu_cao_cm, _HEIGHT_MIN_CM, _HEIGHT_MAX_CM)
    validate_range("can_nang_kg", can_nang_kg, _WEIGHT_MIN_KG, _WEIGHT_MAX_KG)

    missing: list[str] = []
    if gioi_tinh is None:
        missing.append("gioi_tinh")
    if chieu_cao_cm is None:
        missing.append("chieu_cao_cm")
    if can_nang_kg is None:
        missing.append("can_nang_kg")
    if missing:
        return _missing_result(cong_thuc, don_vi, missing, tham_khao)

    assert gioi_tinh is not None and chieu_cao_cm is not None and can_nang_kg is not None
    ibw_res = ibw_devine(gioi_tinh, chieu_cao_cm)
    assert ibw_res.ket_qua is not None
    ket_qua = ibw_res.ket_qua + 0.4 * (float(can_nang_kg) - ibw_res.ket_qua)

    return CalcResult(
        cong_thuc=cong_thuc,
        phien_ban=_VERSION,
        ket_qua=ket_qua,
        don_vi=don_vi,
        dau_vao=[
            CalcInput(ten="chieu_cao_cm", gia_tri=float(chieu_cao_cm), don_vi="cm"),
            CalcInput(ten="can_nang_kg", gia_tri=float(can_nang_kg), don_vi="kg"),
        ],
        thieu_dau_vao=[],
        ghi_chu=list(ibw_res.ghi_chu),
        tham_khao=tham_khao,
    )
