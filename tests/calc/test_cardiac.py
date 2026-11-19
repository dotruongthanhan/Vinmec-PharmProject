"""Kiểm thử các công thức QTc trong app/calc/cardiac.py."""

import pytest

from app.calc import (
    qtc_bazett,
    qtc_framingham,
    qtc_fridericia,
    qtc_hodges,
    qtc_rautaharju,
)


def test_qtc_formulas_at_75_bpm() -> None:
    """Ca thử: QT 400 ms, nhịp 75 lần/phút (RR 0.8 s) khớp năm công thức."""
    expected = [
        (qtc_bazett, "qtc_bazett", 447.2),
        (qtc_fridericia, "qtc_fridericia", 430.9),
        (qtc_framingham, "qtc_framingham", 430.8),
        (qtc_hodges, "qtc_hodges", 426.25),
        (qtc_rautaharju, "qtc_rautaharju", 433.3),
    ]
    for fn, name, target in expected:
        res = fn(400.0, 75.0)
        assert res.cong_thuc == name
        assert res.don_vi == "ms"
        assert res.ket_qua == pytest.approx(target, abs=0.1)
        assert res.thieu_dau_vao == []
        assert res.ghi_chu == []
        assert res.tham_khao


def test_qtc_formulas_at_60_bpm_equal_qt() -> None:
    """Ca thử nhịp 60 lần/phút (RR = 1 s): cả năm công thức trả đúng 400 ms."""
    for fn in (qtc_bazett, qtc_fridericia, qtc_framingham, qtc_hodges, qtc_rautaharju):
        res = fn(400.0, 60.0)
        assert res.ket_qua == pytest.approx(400.0, abs=1e-9)
        assert res.don_vi == "ms"


def test_qtc_missing_inputs() -> None:
    """Thiếu qt_ms hoặc nhip_tim trả ket_qua=None và liệt kê trường thiếu."""
    res_qt = qtc_bazett(None, 75.0)
    assert res_qt.ket_qua is None
    assert res_qt.thieu_dau_vao == ["qt_ms"]

    res_both = qtc_fridericia(None, None)
    assert res_both.ket_qua is None
    assert res_both.thieu_dau_vao == ["qt_ms", "nhip_tim"]


def test_qtc_out_of_range_raises() -> None:
    """Giá trị ngoài miền hợp lệ ném ValueError."""
    with pytest.raises(ValueError, match="qt_ms"):
        qtc_bazett(50.0, 75.0)
    with pytest.raises(ValueError, match="nhip_tim"):
        qtc_hodges(400.0, 0.0)
    with pytest.raises(ValueError, match="nhip_tim"):
        qtc_rautaharju(400.0, 350.0)
