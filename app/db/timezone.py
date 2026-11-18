"""Đưa mọi mốc thời gian đọc từ PostgreSQL về giờ Việt Nam trước khi trình bày."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def to_vn_time(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cột timestamptz về múi +07; PostgreSQL qua bộ gộp kết nối trả về UTC."""
    for row in rows:
        for key, value in row.items():
            if isinstance(value, datetime) and value.tzinfo is not None:
                row[key] = value.astimezone(VN_TZ)
    return rows
