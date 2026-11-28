"""Kiểm thử công thức canxi hiệu chỉnh theo albumin trong app/calc/electrolyte.py."""

import pytest

from app.calc import calcium_corrected


def test_calcium_corrected_mg_dl() -> None:
    """Ca thử 1: Ca 8.0 mg/dL, albumin 2.5 g/dL -> 9.2 mg/dL."""
    res = calcium_corrected(8.0, "mg/dL", 2.5, "g/dL")
    assert res.cong_thuc == "calcium_corrected"
    assert res.don_vi == "mg/dL"
    assert res.ket_qua == pytest.approx(9.2, abs=0.001)
    assert res.thieu_dau_vao == []
    assert res.tham_khao
    assert any("mmol/L" in note for note in res.ghi_chu)
    assert any("4.0" in note for note in res.ghi_chu)


def test_calcium_corrected_mmol_l_and_g_l() -> None:
    """Ca thử 2: Ca 2.00 mmol/L, albumin 25 g/L -> 2.2994 mmol/L (9.216 mg/dL)."""
    res = calcium_corrected(2.0, "mmol/L", 25.0, "g/L")
    assert res.don_vi == "mmol/L"
    assert res.ket_qua == pytest.approx(2.2994, abs=0.001)
    assert res.thieu_dau_vao == []
    assert any("9.216" in note and "mg/dL" in note for note in res.ghi_chu)
    assert any("4.0" in note for note in res.ghi_chu)
    raw = {item.ten: item for item in res.dau_vao}
    assert raw["canxi"].gia_tri == 2.0
    assert raw["canxi"].don_vi == "mmol/L"
    assert raw["albumin"].gia_tri == 25.0
    assert raw["albumin"].don_vi == "g/L"


def test_calcium_corrected_custom_normal_albumin() -> None:
    """Truyền albumin_binh_thuong khác 4.0 không ghi chú dùng giá trị mặc định."""
    res = calcium_corrected(8.0, "mg/dL", 2.5, "g/dL", albumin_binh_thuong=4.4)
    assert res.ket_qua == pytest.approx(9.52, abs=0.001)
    assert not any("mặc định" in note for note in res.ghi_chu)


def test_calcium_corrected_missing_inputs() -> None:
    """Thiếu đầu vào trả ket_qua=None và liệt kê đúng tên trường thiếu."""
    res = calcium_corrected(None, "mg/dL", None, "g/dL")
    assert res.ket_qua is None
    assert res.thieu_dau_vao == ["canxi", "albumin"]


def test_calcium_corrected_invalid_inputs_raise() -> None:
    """Đơn vị lạ hoặc giá trị ngoài miền hợp lệ ném ValueError."""
    with pytest.raises(ValueError, match="don_vi"):
        calcium_corrected(8.0, "umol/L", 2.5, "g/dL")
    with pytest.raises(ValueError, match="canxi"):
        calcium_corrected(-1.0, "mg/dL", 2.5, "g/dL")
    with pytest.raises(ValueError, match="albumin_binh_thuong"):
        calcium_corrected(8.0, "mg/dL", 2.5, "g/dL", albumin_binh_thuong=0.0)
