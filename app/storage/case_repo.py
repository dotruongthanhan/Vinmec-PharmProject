"""Kho ca JSON dùng bộ nạp mô hình hiện có."""

from pathlib import Path

from pydantic import ValidationError

from app.domain.loader import load_case
from app.domain.models import CaBenh


class JsonCaseRepository:
    """Tra cứu bằng ca_id trong nội dung, không dựa vào tên tệp."""

    def __init__(self, folder: Path) -> None:
        self._folder = Path(folder)
        self.errors: list[tuple[str, str]] = []

    def _scan(self) -> dict[str, Path]:
        """Quét lại thư mục, bỏ qua tệp hỏng và làm mới danh sách lỗi."""
        self.errors.clear()
        paths = {}
        for path in sorted(self._folder.glob("*.json")):
            try:
                case = load_case(path)
            except (OSError, UnicodeError, ValidationError) as exc:
                self.errors.append((str(path), str(exc)))
                continue
            paths[case.ca_id] = path
        return paths

    def list_ids(self) -> list[str]:
        """Trả mã ca hợp lệ theo thứ tự tăng dần."""
        return sorted(self._scan())

    def get(self, ca_id: str) -> CaBenh:
        """Nạp ca được chọn bằng bộ nạp domain; không có thì KeyError."""
        paths = self._scan()
        if ca_id not in paths:
            raise KeyError(ca_id)
        return load_case(paths[ca_id])
