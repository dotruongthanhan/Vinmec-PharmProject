"""Kiểm thử quy đổi đơn vị trong app/calc/units.py."""

import pytest

from app.calc import cm_to_inch, creatinine_to_mg_dl


def test_creatinine_88_4_umol_to_mg_dl() -> None:
    """Test 1: 88.4 µmol/L -> 1.0 mg/dL."""
    assert creatinine_to_mg_dl(88.4, "µmol/L") == pytest.approx(1.0, rel=1e-3)


def test_creatinine_212_umol_ascii_to_mg_dl() -> None:
    """Test 2: 212 umol/L -> 2.39819 mg/dL."""
    assert creatinine_to_mg_dl(212, "umol/L") == pytest.approx(2.39819, rel=1e-3)


def test_creatinine_greek_mu_and_case_insensitive() -> None:
    """Chấp nhận ký tự μ Hy Lạp và không phân biệt hoa thường."""
    assert creatinine_to_mg_dl(88.4, "μmol/L") == pytest.approx(1.0, rel=1e-3)
    assert creatinine_to_mg_dl(88.4, "UMOL/L") == pytest.approx(1.0, rel=1e-3)
    assert creatinine_to_mg_dl(1.5, "MG/DL") == pytest.approx(1.5, rel=1e-3)


def test_creatinine_invalid_unit_raises() -> None:
    """Đơn vị lạ như g/L phải ném ValueError."""
    with pytest.raises(ValueError, match="don_vi"):
        creatinine_to_mg_dl(1.0, "g/L")


def test_cm_to_inch() -> None:
    """Quy đổi centimet sang inch theo hệ số 2.54."""
    assert cm_to_inch(152.4) == pytest.approx(60.0, rel=1e-6)
