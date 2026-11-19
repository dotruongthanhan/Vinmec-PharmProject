"""Lớp dịch vụ tách giao diện khỏi đường chạy thẩm định và hệ thống hỏi đáp."""

from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from app.domain.loader import load_case
from app.domain.models import CaBenh
from app.pipeline import KetQuaThamDinh, run_case
from app.rules import RenalRuleBook, load_renal_rules

_NOT_READY_MESSAGE = (
    "Chức năng hỏi thêm chưa được nối với hệ thống. Bảng nhận định bên trái vẫn dùng được."
)


class TrichDan(BaseModel):
    """Một mục trích dẫn gắn trong câu trả lời hỏi thêm."""

    so: int
    loai: Literal["du_lieu", "tinh_toan", "tai_lieu"]
    nhan: str
    ban_ghi_id: str | None = None


class TraLoi(BaseModel):
    """Kết quả trả về từ dịch vụ hỏi đáp theo ca bệnh."""

    trang_thai: Literal["chua_san_sang", "ok", "khong_co_nguon", "ngoai_pham_vi", "loi"]
    noi_dung: str
    trich_dan: list[TrichDan] = Field(default_factory=list)
    cong_cu_da_goi: list[str] = Field(default_factory=list)


class ReviewService(Protocol):
    """Giao diện dịch vụ nạp danh sách ca bệnh và chạy thẩm định từng ca."""

    def list_cases(self) -> tuple[list[CaBenh], list[tuple[str, str]]]:
        """Trả về cặp (danh sách ca hợp lệ, danh sách (tên tệp, lỗi))."""
        ...

    def review(self, ca: CaBenh) -> KetQuaThamDinh:
        """Chạy thẩm định một ca bệnh và trả kết quả tổng hợp."""
        ...


class AskService(Protocol):
    """Giao diện dịch vụ hỏi thêm về ca bệnh đang mở."""

    def ask(self, ca: CaBenh, cau_hoi: str, lich_su: list[tuple[str, str]]) -> TraLoi:
        """Trả lời câu hỏi về ca đang mở dựa trên lịch sử hội thoại."""
        ...


class PipelineReviewService:
    """Dịch vụ thẩm định dùng bộ nạp ca bệnh JSON và pipeline run_case."""

    def __init__(self, case_dir: Path, renal_rules_path: Path) -> None:
        self._case_dir = Path(case_dir)
        self._renal_rules_path = Path(renal_rules_path)
        self._renal_rules: RenalRuleBook | None = None

    def _get_renal_rules(self) -> RenalRuleBook:
        """Nạp và giữ bảng quy tắc chỉnh liều thận trên thực thể dịch vụ."""
        if self._renal_rules is None:
            self._renal_rules = load_renal_rules(self._renal_rules_path)
        return self._renal_rules

    def list_cases(self) -> tuple[list[CaBenh], list[tuple[str, str]]]:
        """Nạp toàn bộ ca bệnh hợp lệ trong thư mục và gom lỗi từng tệp nếu có."""
        if not self._case_dir.exists():
            return [], [(str(self._case_dir), "Thư mục ca bệnh không tồn tại")]

        cases: list[CaBenh] = []
        errors: list[tuple[str, str]] = []
        for file_path in sorted(self._case_dir.glob("*.json")):
            try:
                cases.append(load_case(file_path))
            except Exception as exc:
                errors.append((file_path.name, str(exc)))

        cases.sort(key=lambda ca: ca.ca_id)
        return cases, errors

    def review(self, ca: CaBenh) -> KetQuaThamDinh:
        """Chạy pipeline thẩm định trên một ca bệnh."""
        from app.container import get_rule_context

        ctx = get_rule_context()
        return run_case(
            ca, self._get_renal_rules(), resolver=ctx.resolver, interactions=ctx.interactions
        )


class NotReadyAskService:
    """Bản cài tạm của dịch vụ hỏi thêm khi chưa nối đồ thị hỏi đáp."""

    def ask(self, ca: CaBenh, cau_hoi: str, lich_su: list[tuple[str, str]]) -> TraLoi:
        """Luôn trả trạng thái chưa sẵn sàng, không giả lập câu trả lời."""
        del ca, cau_hoi, lich_su
        return TraLoi(
            trang_thai="chua_san_sang",
            noi_dung=_NOT_READY_MESSAGE,
            trich_dan=[],
            cong_cu_da_goi=[],
        )
