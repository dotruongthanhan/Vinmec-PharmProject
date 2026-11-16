"""Hàm quy đổi đơn vị xét nghiệm và đo lường cơ bản."""

_UMOL_PER_MG_DL = 88.4
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


def cm_to_inch(cm: float) -> float:
    """Quy đổi chiều cao từ centimet sang inch."""
    return float(cm) / _CM_PER_INCH
