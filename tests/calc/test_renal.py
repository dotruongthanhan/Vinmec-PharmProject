"""Kiểm thử các công thức chức năng thận trong app/calc/renal.py."""

import pytest

from app.calc import cockcroft_gault, egfr_ckd_epi_2021


def test_cockcroft_gault_male_actual_weight() -> None:
    """Test 9: 60 tuổi, nam, 72 kg, 1.0 mg/dL, thực tế -> 80.0."""
    res = cockcroft_gault(60, "nam", 72, 1.0, "mg/dL", "thuc_te")
    assert res.cong_thuc == "cockcroft_gault"
    assert res.don_vi == "mL/min"
    assert res.ket_qua == pytest.approx(80.0, rel=1e-3)
    assert res.thieu_dau_vao == []
    assert res.tham_khao


def test_cockcroft_gault_female_actual_weight() -> None:
    """Test 10: 60 tuổi, nữ, 72 kg, 1.0 mg/dL, thực tế -> 68.0."""
    res = cockcroft_gault(60, "nu", 72, 1.0, "mg/dL", "thuc_te")
    assert res.ket_qua == pytest.approx(68.0, rel=1e-3)
    assert res.thieu_dau_vao == []
    assert res.tham_khao


def test_cockcroft_gault_female_umol_records_raw_input() -> None:
    """Test 11: 75 tuổi, nữ, 50 kg, 212 µmol/L, thực tế -> 15.9988 và giữ nguyên đầu vào."""
    res = cockcroft_gault(75, "nu", 50, 212, "µmol/L", "thuc_te")
    assert res.ket_qua == pytest.approx(15.9988, rel=1e-3)
    assert res.thieu_dau_vao == []
    assert res.tham_khao
    creat_inputs = [item for item in res.dau_vao if item.ten == "creatinin"]
    assert len(creat_inputs) == 1
    assert creat_inputs[0].gia_tri == 212
    assert creat_inputs[0].don_vi == "µmol/L"


def test_cockcroft_gault_adjusted_weight_and_note() -> None:
    """Test 12: 60 tuổi, nam, 100 kg, 170 cm, 1.0 mg/dL, hiệu chỉnh -> 88.4024."""
    res = cockcroft_gault(60, "nam", 100, 1.0, "mg/dL", "hieu_chinh", 170)
    assert res.ket_qua == pytest.approx(88.4024, rel=1e-3)
    assert res.thieu_dau_vao == []
    assert res.tham_khao
    assert any("hieu_chinh" in note for note in res.ghi_chu)


def test_egfr_ckd_epi_2021_male_60() -> None:
    """Test 13: 60 tuổi, nam, 1.0 mg/dL -> 86.1626."""
    res = egfr_ckd_epi_2021(60, "nam", 1.0, "mg/dL")
    assert res.cong_thuc == "egfr_ckd_epi_2021"
    assert res.don_vi == "mL/min/1.73m2"
    assert res.ket_qua == pytest.approx(86.1626, rel=1e-3)
    assert res.thieu_dau_vao == []
    assert res.tham_khao


def test_egfr_ckd_epi_2021_female_60() -> None:
    """Test 14: 60 tuổi, nữ, 1.0 mg/dL -> 64.4950."""
    res = egfr_ckd_epi_2021(60, "nu", 1.0, "mg/dL")
    assert res.ket_qua == pytest.approx(64.4950, rel=1e-3)
    assert res.thieu_dau_vao == []
    assert res.tham_khao


def test_egfr_ckd_epi_2021_female_50_low_scr() -> None:
    """Test 15: 50 tuổi, nữ, 0.6 mg/dL -> 109.283."""
    res = egfr_ckd_epi_2021(50, "nu", 0.6, "mg/dL")
    assert res.ket_qua == pytest.approx(109.283, rel=1e-3)
    assert res.thieu_dau_vao == []
    assert res.tham_khao


def test_cockcroft_gault_missing_weight() -> None:
    """Thiếu can_nang_kg khi chọn thực tế trả về ket_qua=None và thieu_dau_vao."""
    res = cockcroft_gault(60, "nam", None, 1.0, "mg/dL")
    assert res.ket_qua is None
    assert res.thieu_dau_vao == ["can_nang_kg"]


def test_cockcroft_gault_missing_weight_and_creatinine() -> None:
    """Thiếu cả can_nang_kg và creatinin thì cả hai tên có trong thieu_dau_vao."""
    res = cockcroft_gault(60, "nam", None, None, "mg/dL")
    assert res.ket_qua is None
    assert "can_nang_kg" in res.thieu_dau_vao
    assert "creatinin" in res.thieu_dau_vao


def test_cockcroft_gault_ideal_weight_missing_height() -> None:
    """Chọn loai_can_nang='ly_tuong' mà thiếu chieu_cao_cm báo thiếu chieu_cao_cm."""
    res = cockcroft_gault(60, "nam", 70, 1.0, "mg/dL", loai_can_nang="ly_tuong")
    assert res.ket_qua is None
    assert res.thieu_dau_vao == ["chieu_cao_cm"]


def test_cockcroft_gault_invalid_creatinine_range_raises() -> None:
    """Creatinin 212 mg/dL vượt miền hợp lệ phải ném ValueError."""
    with pytest.raises(ValueError, match="creatinin"):
        cockcroft_gault(60, "nam", 70, 212, "mg/dL")


def test_cockcroft_gault_invalid_unit_raises() -> None:
    """Đơn vị creatinin lạ ('g/L') phải ném ValueError."""
    with pytest.raises(ValueError, match="don_vi"):
        cockcroft_gault(60, "nam", 70, 1.0, "g/L")


def test_egfr_ckd_epi_2021_under_18_raises() -> None:
    """Tuổi dưới 18 cho CKD-EPI 2021 phải ném ValueError."""
    with pytest.raises(ValueError, match="tuoi"):
        egfr_ckd_epi_2021(10, "nam", 0.8, "mg/dL")
