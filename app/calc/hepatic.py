"""Các công thức đánh giá chức năng gan (thang điểm Child-Pugh)."""

import math
from typing import Literal

from app.calc.types import CalcInput, CalcResult, validate_range
from app.calc.units import albumin_to_g_dl, bilirubin_to_mg_dl

AscitesGrade = Literal["khong", "nhe", "vua"]
EncephalopathyGrade = Literal["khong", "do_1_2", "do_3_4"]
ChildPughClass = Literal["A", "B", "C"]

_VERSION = "1.0"
_BILIRUBIN_MAX_MG_DL = 100.0
_ALBUMIN_MAX_G_DL = 10.0
_INR_MAX = 30.0
_VALID_ASCITES = ("khong", "nhe", "vua")
_VALID_ENCEPHALOPATHY = ("khong", "do_1_2", "do_3_4")
_THAM_KHAO = (
    "Child CG, Turcotte JG. Surgery and portal hypertension. "
    "In: The liver and portal hypertension. Philadelphia: Saunders 1964:50-64. "
    "Pugh RN, Murray-Lyon IM, Dawson JL, Pietroni MC, Williams R. "
    "Transection of the oesophagus for bleeding oesophageal varices. "
    "Br J Surg 1973;60(8):646-9."
)


def _missing_result(thieu_dau_vao: list[str]) -> CalcResult:
    return CalcResult(
        cong_thuc="child_pugh",
        phien_ban=_VERSION,
        ket_qua=None,
        don_vi="diem",
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


def _validate_bilirubin(bilirubin: float | None, bilirubin_don_vi: str | None) -> float | None:
    if bilirubin_don_vi is not None:
        bilirubin_to_mg_dl(1.0, bilirubin_don_vi)
    if bilirubin is None:
        return None
    if bilirubin_don_vi is None:
        _validate_positive_finite("bilirubin", bilirubin)
        return None
    bili_mg_dl = bilirubin_to_mg_dl(bilirubin, bilirubin_don_vi)
    validate_range("bilirubin", bili_mg_dl, 0.0, _BILIRUBIN_MAX_MG_DL, strict_min=True)
    return bili_mg_dl


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


def _score_bilirubin(bili_mg_dl: float) -> int:
    if bili_mg_dl < 2.0:
        return 1
    if bili_mg_dl <= 3.0:
        return 2
    return 3


def _score_albumin(alb_g_dl: float) -> int:
    if alb_g_dl > 3.5:
        return 1
    if alb_g_dl >= 2.8:
        return 2
    return 3


def _score_inr(inr: float) -> int:
    if inr < 1.7:
        return 1
    if inr <= 2.3:
        return 2
    return 3


def _score_ascites(co_truong: AscitesGrade) -> int:
    return {"khong": 1, "nhe": 2, "vua": 3}[co_truong]


def _score_encephalopathy(nao_gan: EncephalopathyGrade) -> int:
    return {"khong": 1, "do_1_2": 2, "do_3_4": 3}[nao_gan]


def child_pugh_class(diem: int | float) -> ChildPughClass:
    """Phân hạng Child-Pugh (A: 5–6, B: 7–9, C: 10–15) theo Pugh 1973."""
    if not math.isfinite(diem) or diem < 5 or diem > 15 or int(diem) != diem:
        raise ValueError(f"Điểm Child-Pugh ngoài miền hợp lệ (5 <= diem <= 15): {diem}")
    if diem <= 6:
        return "A"
    if diem <= 9:
        return "B"
    return "C"


def child_pugh(
    bilirubin: float | None,
    bilirubin_don_vi: str | None,
    albumin: float | None,
    albumin_don_vi: str | None,
    inr: float | None,
    co_truong: AscitesGrade | None,
    nao_gan: EncephalopathyGrade | None,
) -> CalcResult:
    """Tính điểm Child-Pugh (5–15) và phân hạng A/B/C đánh giá mức độ suy gan."""
    if co_truong is not None and co_truong not in _VALID_ASCITES:
        raise ValueError(f"Tham số co_truong không hợp lệ: {co_truong!r}")
    if nao_gan is not None and nao_gan not in _VALID_ENCEPHALOPATHY:
        raise ValueError(f"Tham số nao_gan không hợp lệ: {nao_gan!r}")

    bili_mg_dl = _validate_bilirubin(bilirubin, bilirubin_don_vi)
    alb_g_dl = _validate_albumin(albumin, albumin_don_vi)
    validate_range("inr", inr, 0.0, _INR_MAX, strict_min=True)

    missing: list[str] = []
    if bilirubin is None:
        missing.append("bilirubin")
    if bilirubin_don_vi is None:
        missing.append("bilirubin_don_vi")
    if albumin is None:
        missing.append("albumin")
    if albumin_don_vi is None:
        missing.append("albumin_don_vi")
    if inr is None:
        missing.append("inr")
    if co_truong is None:
        missing.append("co_truong")
    if nao_gan is None:
        missing.append("nao_gan")
    if missing:
        return _missing_result(missing)

    assert bilirubin is not None and bilirubin_don_vi is not None
    assert albumin is not None and albumin_don_vi is not None
    assert bili_mg_dl is not None and alb_g_dl is not None
    assert inr is not None and co_truong is not None and nao_gan is not None

    bili_pts = _score_bilirubin(bili_mg_dl)
    alb_pts = _score_albumin(alb_g_dl)
    inr_pts = _score_inr(float(inr))
    asc_pts = _score_ascites(co_truong)
    enc_pts = _score_encephalopathy(nao_gan)

    tong_diem = bili_pts + alb_pts + inr_pts + asc_pts + enc_pts
    hang = child_pugh_class(tong_diem)
    chi_tiet = (
        f"Thành phần: bilirubin={bili_pts}, albumin={alb_pts}, inr={inr_pts}, "
        f"co_truong={co_truong} ({asc_pts}), nao_gan={nao_gan} ({enc_pts})"
    )

    return CalcResult(
        cong_thuc="child_pugh",
        phien_ban=_VERSION,
        ket_qua=float(tong_diem),
        don_vi="diem",
        dau_vao=[
            CalcInput(ten="bilirubin", gia_tri=float(bilirubin), don_vi=bilirubin_don_vi),
            CalcInput(ten="albumin", gia_tri=float(albumin), don_vi=albumin_don_vi),
            CalcInput(ten="inr", gia_tri=float(inr), don_vi=""),
        ],
        thieu_dau_vao=[],
        ghi_chu=[f"Hạng {hang}", chi_tiet],
        tham_khao=_THAM_KHAO,
    )
