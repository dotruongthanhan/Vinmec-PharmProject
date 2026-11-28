"""Kiểm tra log từ chối không ghi số dài."""

import logging

from app.orchestration.ask import _log_rejection


def test_rejection_log_masks_long_numbers(caplog):
    with caplog.at_level(logging.INFO):
        _log_rejection("verification", "so_khong_co_nguon:0912345678")
    assert "so_khong_co_nguon:#10" in caplog.text
    assert "0912345678" not in caplog.text
