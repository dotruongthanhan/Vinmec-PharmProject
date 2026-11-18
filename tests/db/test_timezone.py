"""Mốc thời gian đọc từ PostgreSQL phải được đưa về giờ Việt Nam (+07)."""

from datetime import UTC, datetime

from app.db.timezone import to_vn_time


def test_utc_values_become_vietnam_time_with_same_instant() -> None:
    rows = [{"thoi_diem_ke": datetime(2026, 11, 14, 3, 0, tzinfo=UTC), "ma": "YL-1", "so": 5}]
    result = to_vn_time(rows)
    assert result[0]["thoi_diem_ke"].isoformat() == "2026-11-14T10:00:00+07:00"
    assert result[0]["thoi_diem_ke"] == datetime(2026, 11, 14, 3, 0, tzinfo=UTC)
    assert result[0]["ma"] == "YL-1" and result[0]["so"] == 5


def test_naive_and_missing_values_are_left_alone() -> None:
    naive = datetime(2026, 1, 1, 8, 0)
    result = to_vn_time([{"a": naive, "b": None}])
    assert result[0]["a"] == naive and result[0]["b"] is None
