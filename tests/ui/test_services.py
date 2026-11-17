"""Kiểm thử lớp dịch vụ thẩm định và hỏi đáp cho giao diện."""

import shutil
from pathlib import Path

from app.domain.loader import load_case
from app.ui.services import NotReadyAskService, PipelineReviewService

_ROOT = Path(__file__).resolve().parents[2]
_DEMO_DIR = _ROOT / "data" / "mock" / "demo"
_RENAL_RULES_PATH = _ROOT / "data" / "kb" / "quy_tac_lieu_than.json"


def test_pipeline_review_service_lists_and_reviews_demo_cases() -> None:
    """PipelineReviewService nạp đủ 6 ca demo hợp lệ và chạy thẩm định thành công."""
    service = PipelineReviewService(_DEMO_DIR, _RENAL_RULES_PATH)
    cases, errors = service.list_cases()

    assert errors == []
    assert [ca.ca_id for ca in cases] == [
        "DEMO-01",
        "DEMO-02",
        "DEMO-03",
        "DEMO-04",
        "DEMO-05",
        "DEMO-06",
    ]

    result = service.review(cases[1])
    assert result.ca_id == "DEMO-02"
    assert any(p.yeu_to == 6 and p.ket_luan == "can_xem" for p in result.phat_hien)


def test_pipeline_review_service_collects_bad_file_errors(tmp_path: Path) -> None:
    """Tệp JSON lỗi được gom vào danh sách lỗi mà không làm hỏng ca hợp lệ."""
    shutil.copy(_DEMO_DIR / "DEMO-01.json", tmp_path / "DEMO-01.json")
    (tmp_path / "BROKEN.json").write_text("{not valid json", encoding="utf-8")

    service = PipelineReviewService(tmp_path, _RENAL_RULES_PATH)
    cases, errors = service.list_cases()

    assert [ca.ca_id for ca in cases] == ["DEMO-01"]
    assert len(errors) == 1
    assert errors[0][0] == "BROKEN.json"


def test_pipeline_review_service_missing_dir_returns_error(tmp_path: Path) -> None:
    """Thư mục ca bệnh không tồn tại trả danh sách rỗng kèm thông báo lỗi."""
    service = PipelineReviewService(tmp_path / "missing", _RENAL_RULES_PATH)
    cases, errors = service.list_cases()

    assert cases == []
    assert len(errors) == 1


def test_not_ready_ask_service_returns_fixed_status() -> None:
    """NotReadyAskService luôn trả trang_thai='chua_san_sang' và không giả lập câu trả lời."""
    ca = load_case(_DEMO_DIR / "DEMO-02.json")
    reply = NotReadyAskService().ask(ca, "Thuốc nào cần chỉnh liều?", [])

    assert reply.trang_thai == "chua_san_sang"
    assert reply.trich_dan == []
    assert reply.cong_cu_da_goi == []
    assert "chưa được nối" in reply.noi_dung
