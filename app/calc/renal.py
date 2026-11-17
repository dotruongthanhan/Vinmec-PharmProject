"""Các công thức đánh giá chức năng thận (CrCl và eGFR)."""

from app.calc.body import adjusted_body_weight, ibw_devine
from app.calc.types import CalcInput, CalcResult, Sex, WeightType, validate_range, validate_sex
from app.calc.units import creatinine_to_mg_dl

_VERSION = "1.0"
_AGE_MIN = 0.0
_AGE_MAX = 120.0
_CKD_EPI_AGE_MIN = 18.0
_WEIGHT_MIN_KG = 0.3
_WEIGHT_MAX_KG = 400.0
_HEIGHT_MIN_CM = 20.0
_HEIGHT_MAX_CM = 250.0
_SCR_MIN_MG_DL = 0.05
_SCR_MAX_MG_DL = 40.0
_VALID_WEIGHT_TYPES = ("thuc_te", "ly_tuong", "hieu_chinh")


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


def _validate_and_convert_creatinine(
    creatinin: float | None,
    creatinin_don_vi: str | None,
) -> float | None:
    if creatinin_don_vi is not None:
        # Kiểm tra đơn vị hợp lệ ngay cả khi thiếu giá trị creatinin.
        creatinine_to_mg_dl(1.0, creatinin_don_vi)
    if creatinin is not None and creatinin_don_vi is not None:
        scr_mg_dl = creatinine_to_mg_dl(creatinin, creatinin_don_vi)
        validate_range("creatinin", scr_mg_dl, _SCR_MIN_MG_DL, _SCR_MAX_MG_DL)
        return scr_mg_dl
    return None


def cockcroft_gault(
    tuoi: float | None,
    gioi_tinh: Sex | None,
    can_nang_kg: float | None,
    creatinin: float | None,
    creatinin_don_vi: str | None,
    loai_can_nang: WeightType = "thuc_te",
    chieu_cao_cm: float | None = None,
) -> CalcResult:
    """Tính độ thanh thải creatinin (CrCl) theo công thức Cockcroft-Gault."""
    cong_thuc = "cockcroft_gault"
    don_vi = "mL/min"
    tham_khao = "Cockcroft DW, Gault MH. Nephron 1976;16:31-41."

    if loai_can_nang not in _VALID_WEIGHT_TYPES:
        raise ValueError(f"Tham số loai_can_nang không hợp lệ: {loai_can_nang!r}")

    validate_range("tuoi", tuoi, _AGE_MIN, _AGE_MAX, strict_min=True)
    validate_sex(gioi_tinh)
    validate_range("can_nang_kg", can_nang_kg, _WEIGHT_MIN_KG, _WEIGHT_MAX_KG)
    validate_range("chieu_cao_cm", chieu_cao_cm, _HEIGHT_MIN_CM, _HEIGHT_MAX_CM)
    scr_mg_dl = _validate_and_convert_creatinine(creatinin, creatinin_don_vi)

    missing: list[str] = []
    if tuoi is None:
        missing.append("tuoi")
    if gioi_tinh is None:
        missing.append("gioi_tinh")
    if loai_can_nang in ("thuc_te", "hieu_chinh") and can_nang_kg is None:
        missing.append("can_nang_kg")
    if loai_can_nang in ("ly_tuong", "hieu_chinh") and chieu_cao_cm is None:
        missing.append("chieu_cao_cm")
    if creatinin is None:
        missing.append("creatinin")
    if creatinin_don_vi is None:
        missing.append("creatinin_don_vi")
    if missing:
        return _missing_result(cong_thuc, don_vi, missing, tham_khao)

    assert tuoi is not None
    assert gioi_tinh is not None
    assert creatinin is not None
    assert creatinin_don_vi is not None
    assert scr_mg_dl is not None

    dau_vao: list[CalcInput] = [CalcInput(ten="tuoi", gia_tri=float(tuoi), don_vi="tuoi")]
    ghi_chu: list[str] = []

    if loai_can_nang == "thuc_te":
        assert can_nang_kg is not None
        weight = float(can_nang_kg)
        dau_vao.append(CalcInput(ten="can_nang_kg", gia_tri=float(can_nang_kg), don_vi="kg"))
    elif loai_can_nang == "ly_tuong":
        assert chieu_cao_cm is not None
        ibw_res = ibw_devine(gioi_tinh, chieu_cao_cm)
        assert ibw_res.ket_qua is not None
        weight = ibw_res.ket_qua
        dau_vao.append(CalcInput(ten="chieu_cao_cm", gia_tri=float(chieu_cao_cm), don_vi="cm"))
        ghi_chu.extend(ibw_res.ghi_chu)
    else:
        assert can_nang_kg is not None and chieu_cao_cm is not None
        adj_res = adjusted_body_weight(gioi_tinh, chieu_cao_cm, can_nang_kg)
        assert adj_res.ket_qua is not None
        weight = adj_res.ket_qua
        dau_vao.append(CalcInput(ten="can_nang_kg", gia_tri=float(can_nang_kg), don_vi="kg"))
        dau_vao.append(CalcInput(ten="chieu_cao_cm", gia_tri=float(chieu_cao_cm), don_vi="cm"))
        ghi_chu.extend(adj_res.ghi_chu)

    dau_vao.append(CalcInput(ten="creatinin", gia_tri=float(creatinin), don_vi=creatinin_don_vi))
    ghi_chu.insert(0, f"Dung can nang {loai_can_nang}: {weight} kg")

    crcl = ((140.0 - float(tuoi)) * weight) / (72.0 * scr_mg_dl)
    if gioi_tinh == "nu":
        crcl *= 0.85

    return CalcResult(
        cong_thuc=cong_thuc,
        phien_ban=_VERSION,
        ket_qua=crcl,
        don_vi=don_vi,
        dau_vao=dau_vao,
        thieu_dau_vao=[],
        ghi_chu=ghi_chu,
        tham_khao=tham_khao,
    )


def egfr_ckd_epi_2021(
    tuoi: float | None,
    gioi_tinh: Sex | None,
    creatinin: float | None,
    creatinin_don_vi: str | None,
) -> CalcResult:
    """Tính mức lọc cầu thận ước tính (eGFR) theo công thức CKD-EPI 2021."""
    cong_thuc = "egfr_ckd_epi_2021"
    don_vi = "mL/min/1.73m2"
    tham_khao = "Inker LA, et al. N Engl J Med 2021;385:1737-1749."

    validate_range("tuoi", tuoi, _CKD_EPI_AGE_MIN, _AGE_MAX)
    validate_sex(gioi_tinh)
    scr_mg_dl = _validate_and_convert_creatinine(creatinin, creatinin_don_vi)

    missing: list[str] = []
    if tuoi is None:
        missing.append("tuoi")
    if gioi_tinh is None:
        missing.append("gioi_tinh")
    if creatinin is None:
        missing.append("creatinin")
    if creatinin_don_vi is None:
        missing.append("creatinin_don_vi")
    if missing:
        return _missing_result(cong_thuc, don_vi, missing, tham_khao)

    assert tuoi is not None
    assert gioi_tinh is not None
    assert creatinin is not None
    assert creatinin_don_vi is not None
    assert scr_mg_dl is not None

    if gioi_tinh == "nu":
        kappa = 0.7
        alpha = -0.241
        sex_factor = 1.012
    else:
        kappa = 0.9
        alpha = -0.302
        sex_factor = 1.0

    ratio = scr_mg_dl / kappa
    egfr = (
        142.0
        * (min(ratio, 1.0) ** alpha)
        * (max(ratio, 1.0) ** -1.200)
        * (0.9938 ** float(tuoi))
        * sex_factor
    )

    return CalcResult(
        cong_thuc=cong_thuc,
        phien_ban=_VERSION,
        ket_qua=egfr,
        don_vi=don_vi,
        dau_vao=[
            CalcInput(ten="tuoi", gia_tri=float(tuoi), don_vi="tuoi"),
            CalcInput(ten="creatinin", gia_tri=float(creatinin), don_vi=creatinin_don_vi),
        ],
        thieu_dau_vao=[],
        ghi_chu=[],
        tham_khao=tham_khao,
    )
