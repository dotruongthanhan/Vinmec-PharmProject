"""Kiểm tra nhận diện yêu cầu vẽ."""

import pytest

from app.agent.nodes import nguoi_dung_yeu_cau_ve


@pytest.mark.parametrize(
    "text", ["Vẽ", "biểu đồ", "đồ thị", "minh hoạ", "minh họa", "hình", "chart", "plot"]
)
def test_nhan_dien(text: str) -> None:
    assert nguoi_dung_yeu_cau_ve(text)


@pytest.mark.parametrize("text", ["hình thức", "hình ảnh học", "định hình", "plotting"])
def test_khong_nhan_nham(text: str) -> None:
    assert not nguoi_dung_yeu_cau_ve(text)
