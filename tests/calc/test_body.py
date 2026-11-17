"""Kiểm thử các công thức nhân trắc trong app/calc/body.py."""

import pytest

from app.calc import adjusted_body_weight, bmi, bsa_dubois, bsa_mosteller, ibw_devine


def test_bmi() -> None:
    """Test 3: BMI với 70 kg, 170 cm -> 24.2215."""
    res = bmi(70, 170)
    assert res.cong_thuc == "bmi"
    assert res.don_vi == "kg/m2"
    assert res.ket_qua == pytest.approx(24.2215, rel=1e-3)
    assert res.thieu_dau_vao == []
    assert res.tham_khao


def test_bsa_mosteller() -> None:
    """Test 4: BSA Mosteller với 70 kg, 170 cm -> 1.81812."""
    res = bsa_mosteller(70, 170)
    assert res.cong_thuc == "bsa_mosteller"
    assert res.don_vi == "m2"
    assert res.ket_qua == pytest.approx(1.81812, rel=1e-3)
    assert res.thieu_dau_vao == []
    assert res.tham_khao


def test_bsa_dubois() -> None:
    """Test 5: BSA Du Bois với 70 kg, 170 cm -> 1.80971."""
    res = bsa_dubois(70, 170)
    assert res.cong_thuc == "bsa_dubois"
    assert res.don_vi == "m2"
    assert res.ket_qua == pytest.approx(1.80971, rel=1e-3)
    assert res.thieu_dau_vao == []
    assert res.tham_khao


def test_ibw_devine_male() -> None:
    """Test 6: IBW Devine nam, 170 cm -> 65.9370."""
    res = ibw_devine("nam", 170)
    assert res.cong_thuc == "ibw_devine"
    assert res.don_vi == "kg"
    assert res.ket_qua == pytest.approx(65.9370, rel=1e-3)
    assert res.thieu_dau_vao == []
    assert res.ghi_chu == []
    assert res.tham_khao


def test_ibw_devine_female() -> None:
    """Test 7: IBW Devine nữ, 160 cm -> 52.3819."""
    res = ibw_devine("nu", 160)
    assert res.ket_qua == pytest.approx(52.3819, rel=1e-3)
    assert res.thieu_dau_vao == []
    assert res.ghi_chu == []
    assert res.tham_khao


def test_adjusted_body_weight() -> None:
    """Test 8: AdjBW nam, 170 cm, 100 kg -> 79.5622."""
    res = adjusted_body_weight("nam", 170, 100)
    assert res.cong_thuc == "adjusted_body_weight"
    assert res.don_vi == "kg"
    assert res.ket_qua == pytest.approx(79.5622, rel=1e-3)
    assert res.thieu_dau_vao == []
    assert res.tham_khao


def test_ibw_devine_below_152_4_cm_warns_and_calculates() -> None:
    """Chiều cao dưới 152.4 cm vẫn tính và kèm cảnh báo trong ghi_chu."""
    res = ibw_devine("nam", 150)
    assert res.ket_qua is not None
    assert res.thieu_dau_vao == []
    assert res.tham_khao
    assert any("152.4" in note for note in res.ghi_chu)


def test_body_missing_inputs() -> None:
    """Thiếu đầu vào trả ket_qua=None và liệt kê tên tham số thiếu."""
    res = bmi(None, 170)
    assert res.ket_qua is None
    assert res.thieu_dau_vao == ["can_nang_kg"]

    res_adj = adjusted_body_weight(None, None, 70)
    assert res_adj.ket_qua is None
    assert res_adj.thieu_dau_vao == ["gioi_tinh", "chieu_cao_cm"]


def test_body_out_of_range_raises() -> None:
    """Giá trị ngoài miền hợp lệ ném ValueError."""
    with pytest.raises(ValueError, match="can_nang_kg"):
        bmi(0.2, 170)
    with pytest.raises(ValueError, match="chieu_cao_cm"):
        bsa_mosteller(70, 260)
