"""Lưu và đọc phản hồi của dược sĩ qua JSON Lines (UTF-8) hoặc PostgreSQL."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from psycopg.types.json import Jsonb
from pydantic import AwareDatetime, BaseModel

DEFAULT_FEEDBACK_PATH = Path("data/runtime/phan_hoi.jsonl")

_FEEDBACK_COLUMNS = (
    "thoi_diem",
    "ca_id",
    "ma_luat",
    "yeu_to",
    "chi_tiet_y_lenh_id",
    "phan_hoi",
    "nhom_ly_do",
    "ly_do",
    "nguoi_dung_id",
)

_INSERT_FEEDBACK_SQL = """
INSERT INTO nghiep_vu.phan_hoi (
    thoi_diem, ca_id, ma_luat, yeu_to, chi_tiet_y_lenh_id,
    phan_hoi, nhom_ly_do, ly_do, nguoi_dung_id
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (ca_id, ma_luat, thoi_diem) DO UPDATE SET
    yeu_to = EXCLUDED.yeu_to,
    chi_tiet_y_lenh_id = EXCLUDED.chi_tiet_y_lenh_id,
    phan_hoi = EXCLUDED.phan_hoi,
    nhom_ly_do = EXCLUDED.nhom_ly_do,
    ly_do = EXCLUDED.ly_do,
    nguoi_dung_id = EXCLUDED.nguoi_dung_id
"""

_SELECT_FEEDBACK_SQL = (
    "SELECT thoi_diem, ca_id, ma_luat, yeu_to, chi_tiet_y_lenh_id, "
    "phan_hoi, nhom_ly_do, ly_do, nguoi_dung_id "
    "FROM nghiep_vu.phan_hoi "
    "ORDER BY thoi_diem ASC"
)


class PhanHoi(BaseModel):
    """Một lượt phản hồi của dược sĩ trên từng phát hiện thẩm định."""

    thoi_diem: AwareDatetime
    ca_id: str
    ma_luat: str
    yeu_to: int
    chi_tiet_y_lenh_id: list[str]
    phan_hoi: Literal["dong_y", "bac_bo", "can_sua"]
    nhom_ly_do: str | None = None
    ly_do: str | None = None
    nguoi_dung_id: str | None = None
    phien_id: str | None = None


def save_feedback(item: PhanHoi, path: Path = DEFAULT_FEEDBACK_PATH) -> None:
    """Ghi nối thêm một phản hồi vào tệp JSONL (UTF-8), tự tạo thư mục nếu chưa có."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(item.model_dump_json() + "\n")


def load_feedback(path: Path = DEFAULT_FEEDBACK_PATH) -> list[PhanHoi]:
    """Đọc toàn bộ phản hồi từ tệp JSONL; trả danh sách rỗng nếu tệp chưa tồn tại."""
    target = Path(path)
    if not target.exists():
        return []
    items: list[PhanHoi] = []
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        if raw_line.strip():
            items.append(PhanHoi.model_validate_json(raw_line))
    return items


def save_feedback_to_db(conn: Any, item: PhanHoi) -> None:
    """Ghi một phản hồi vào bảng nghiep_vu.phan_hoi trên PostgreSQL."""
    conn.execute(
        _INSERT_FEEDBACK_SQL,
        (
            item.thoi_diem,
            item.ca_id,
            item.ma_luat,
            item.yeu_to,
            Jsonb(list(item.chi_tiet_y_lenh_id)),
            item.phan_hoi,
            item.nhom_ly_do,
            item.ly_do,
            item.nguoi_dung_id,
        ),
    )


def load_feedback_from_db(conn: Any) -> list[PhanHoi]:
    """Đọc toàn bộ phản hồi từ bảng nghiep_vu.phan_hoi theo thứ tự thời gian."""
    cursor = conn.execute(_SELECT_FEEDBACK_SQL)
    fetch = getattr(cursor, "fetchall", None)
    rows = fetch() if callable(fetch) else cursor
    items: list[PhanHoi] = []
    for row in rows:
        if isinstance(row, Mapping):
            values = dict(row)
        else:
            values = dict(zip(_FEEDBACK_COLUMNS, row, strict=True))
        line_ids = values.get("chi_tiet_y_lenh_id")
        if isinstance(line_ids, str):
            values["chi_tiet_y_lenh_id"] = json.loads(line_ids)
        items.append(PhanHoi.model_validate(values))
    return items
