"""Lưu và đọc phản hồi của dược sĩ dưới dạng JSON Lines (UTF-8)."""

from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel

DEFAULT_FEEDBACK_PATH = Path("data/runtime/phan_hoi.jsonl")


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
