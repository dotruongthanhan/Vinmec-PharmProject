"""Hàm quy đổi đơn vị xét nghiệm và đo lường cơ bản."""

_UMOL_PER_MG_DL = 88.4
_BILIRUBIN_UMOL_PER_MG_DL = 17.1
_ALBUMIN_G_L_PER_G_DL = 10.0
_CALCIUM_MG_DL_PER_MMOL_L = 4.008
_CM_PER_INCH = 2.54
_UMOL_UNITS = frozenset({"umol/l", "µmol/l", "μmol/l"})


def creatinine_to_mg_dl(gia_tri: float, don_vi: str) -> float:
    """Quy đổi nồng độ creatinin huyết thanh sang đơn vị mg/dL."""
    unit = don_vi.strip().lower()
    if unit == "mg/dl":
        return float(gia_tri)
    if unit in _UMOL_UNITS:
        return float(gia_tri) / _UMOL_PER_MG_DL
    raise ValueError(f"Đơn vị creatinin không hợp lệ (don_vi={don_vi!r})")


def bilirubin_to_mg_dl(gia_tri: float, don_vi: str) -> float:
    """Quy đổi nồng độ bilirubin toàn phần sang đơn vị mg/dL."""
    unit = don_vi.strip().lower()
    if unit == "mg/dl":
        return float(gia_tri)
    if unit in _UMOL_UNITS:
        return float(gia_tri) / _BILIRUBIN_UMOL_PER_MG_DL
    raise ValueError(f"Đơn vị bilirubin không hợp lệ (don_vi={don_vi!r})")


def albumin_to_g_dl(gia_tri: float, don_vi: str) -> float:
    """Quy đổi nồng độ albumin huyết thanh sang đơn vị g/dL."""
    unit = don_vi.strip().lower()
    if unit == "g/dl":
        return float(gia_tri)
    if unit == "g/l":
        return float(gia_tri) / _ALBUMIN_G_L_PER_G_DL
    raise ValueError(f"Đơn vị albumin không hợp lệ (don_vi={don_vi!r})")


def calcium_to_mg_dl(gia_tri: float, don_vi: str) -> float:
    """Quy đổi nồng độ canxi huyết thanh sang đơn vị mg/dL."""
    unit = don_vi.strip().lower()
    if unit == "mg/dl":
        return float(gia_tri)
    if unit == "mmol/l":
        return float(gia_tri) * _CALCIUM_MG_DL_PER_MMOL_L
    raise ValueError(f"Đơn vị canxi không hợp lệ (don_vi={don_vi!r})")


def calcium_mg_dl_to_mmol_l(gia_tri: float) -> float:
    """Quy đổi nồng độ canxi huyết thanh từ mg/dL sang mmol/L."""
    return float(gia_tri) / _CALCIUM_MG_DL_PER_MMOL_L


def cm_to_inch(cm: float) -> float:
    """Quy đổi chiều cao từ centimet sang inch."""
    return float(cm) / _CM_PER_INCH
