"""Kiểm thử quy đổi đơn vị trong app/calc/units.py."""

import pytest

from app.calc import (
    albumin_to_g_dl,
    bilirubin_to_mg_dl,
    calcium_mg_dl_to_mmol_l,
    calcium_to_mg_dl,
    cm_to_inch,
    creatinine_to_mg_dl,
)


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


def test_bilirubin_to_mg_dl() -> None:
    """Quy đổi bilirubin từ mg/dL và các biến thể µmol/L sang mg/dL."""
    assert bilirubin_to_mg_dl(2.0, "mg/dL") == pytest.approx(2.0, rel=1e-6)
    assert bilirubin_to_mg_dl(34.2, "µmol/L") == pytest.approx(2.0, rel=1e-6)
    assert bilirubin_to_mg_dl(34.2, "umol/L") == pytest.approx(2.0, rel=1e-6)
    assert bilirubin_to_mg_dl(51.3, "μmol/L") == pytest.approx(3.0, rel=1e-6)
    assert bilirubin_to_mg_dl(40.0, "UMOL/L") == pytest.approx(40.0 / 17.1, rel=1e-6)


def test_bilirubin_invalid_unit_raises() -> None:
    """Đơn vị bilirubin lạ phải ném ValueError."""
    with pytest.raises(ValueError, match="don_vi"):
        bilirubin_to_mg_dl(1.0, "g/L")


def test_albumin_to_g_dl() -> None:
    """Quy đổi albumin từ g/dL và g/L sang g/dL."""
    assert albumin_to_g_dl(3.5, "g/dL") == pytest.approx(3.5, rel=1e-6)
    assert albumin_to_g_dl(35.0, "g/L") == pytest.approx(3.5, rel=1e-6)
    assert albumin_to_g_dl(28.0, "G/L") == pytest.approx(2.8, rel=1e-6)


def test_albumin_invalid_unit_raises() -> None:
    """Đơn vị albumin lạ phải ném ValueError."""
    with pytest.raises(ValueError, match="don_vi"):
        albumin_to_g_dl(35.0, "mg/dL")


def test_calcium_unit_conversions() -> None:
    """Quy đổi canxi giữa mg/dL và mmol/L theo khối lượng mol 40.08."""
    assert calcium_to_mg_dl(8.0, "mg/dL") == pytest.approx(8.0, rel=1e-6)
    assert calcium_to_mg_dl(2.0, "mmol/L") == pytest.approx(8.016, rel=1e-6)
    assert calcium_to_mg_dl(2.0, "MMOL/L") == pytest.approx(8.016, rel=1e-6)
    assert calcium_mg_dl_to_mmol_l(9.216) == pytest.approx(2.2994, abs=0.001)


def test_calcium_invalid_unit_raises() -> None:
    """Đơn vị canxi lạ phải ném ValueError."""
    with pytest.raises(ValueError, match="don_vi"):
        calcium_to_mg_dl(2.0, "g/L")
