"""Kiểm thử thang điểm Child-Pugh trong app/calc/hepatic.py."""

import pytest

from app.calc import child_pugh, child_pugh_class


def test_child_pugh_class_a() -> None:
    """Ca thử 1: bilirubin 1.0 mg/dL, albumin 4.0 g/dL, INR 1.1 -> 5 điểm, hạng A."""
    res = child_pugh(1.0, "mg/dL", 4.0, "g/dL", 1.1, "khong", "khong")
    assert res.cong_thuc == "child_pugh"
    assert res.don_vi == "diem"
    assert res.ket_qua == 5.0
    assert res.thieu_dau_vao == []
    assert any("Hạng A" in note for note in res.ghi_chu)
    assert res.tham_khao


def test_child_pugh_class_b_converted_units() -> None:
    """Ca thử 2: bilirubin 40 µmol/L, albumin 30 g/L, INR 1.8, cổ trướng nhẹ -> 9, B."""
    res = child_pugh(40.0, "µmol/L", 30.0, "g/L", 1.8, "nhe", "khong")
    assert res.ket_qua == 9.0
    assert res.thieu_dau_vao == []
    assert any("Hạng B" in note for note in res.ghi_chu)
    raw = {item.ten: item for item in res.dau_vao}
    assert raw["bilirubin"].gia_tri == 40.0
    assert raw["bilirubin"].don_vi == "µmol/L"
    assert raw["albumin"].gia_tri == 30.0
    assert raw["albumin"].don_vi == "g/L"


def test_child_pugh_class_c_max_score() -> None:
    """Ca thử 3: bilirubin 4 mg/dL, albumin 2.5 g/dL, INR 2.5, cổ trướng vừa, độ 3-4 -> 15."""
    res = child_pugh(4.0, "mg/dL", 2.5, "g/dL", 2.5, "vua", "do_3_4")
    assert res.ket_qua == 15.0
    assert res.thieu_dau_vao == []
    assert any("Hạng C" in note for note in res.ghi_chu)


def test_child_pugh_boundaries_inclusive() -> None:
    """Hai đầu khoảng giữa đều được tính 2 điểm."""
    res_low = child_pugh(2.0, "mg/dL", 3.5, "g/dL", 1.7, "khong", "khong")
    assert res_low.ket_qua == 8.0

    res_high = child_pugh(3.0, "mg/dL", 2.8, "g/dL", 2.3, "khong", "khong")
    assert res_high.ket_qua == 8.0

    res_umol = child_pugh(34.2, "umol/L", 28.0, "g/L", 1.7, "nhe", "do_1_2")
    assert res_umol.ket_qua == 10.0


def test_child_pugh_class_helper() -> None:
    """Hàm child_pugh_class phân hạng đúng và ném ValueError khi ngoài 5–15."""
    assert child_pugh_class(5) == "A"
    assert child_pugh_class(6) == "A"
    assert child_pugh_class(7) == "B"
    assert child_pugh_class(9) == "B"
    assert child_pugh_class(10) == "C"
    assert child_pugh_class(15) == "C"
    with pytest.raises(ValueError, match="Child-Pugh"):
        child_pugh_class(4)
    with pytest.raises(ValueError, match="Child-Pugh"):
        child_pugh_class(16)


def test_child_pugh_missing_inputs() -> None:
    """Thiếu bất kỳ thành phần nào trả về ket_qua=None và liệt kê tên trường thiếu."""
    res = child_pugh(1.0, "mg/dL", None, "g/dL", 1.1, None, "khong")
    assert res.ket_qua is None
    assert res.thieu_dau_vao == ["albumin", "co_truong"]


def test_child_pugh_invalid_inputs_raise() -> None:
    """Đơn vị lạ, giá trị âm/0 hoặc phân độ lạ phải ném ValueError."""
    with pytest.raises(ValueError, match="don_vi"):
        child_pugh(1.0, "g/L", 4.0, "g/dL", 1.1, "khong", "khong")
    with pytest.raises(ValueError, match="co_truong"):
        child_pugh(1.0, "mg/dL", 4.0, "g/dL", 1.1, "nang", "khong")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="nao_gan"):
        child_pugh(1.0, "mg/dL", 4.0, "g/dL", 1.1, "khong", "do_5")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="inr"):
        child_pugh(1.0, "mg/dL", 4.0, "g/dL", 0.0, "khong", "khong")
