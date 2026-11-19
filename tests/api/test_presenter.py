"""Kiểm thử hàm trình bày không làm đổi dữ liệu đầu vào."""

from datetime import UTC, datetime
from pathlib import Path

from app.domain.loader import load_case
from app.feedback import PhanHoi
from app.pipeline import run_case
from app.rules import load_renal_rules

ROOT = Path(__file__).resolve().parents[2]


def test_presenter_is_pure_and_uses_latest_feedback() -> None:
    from app.api.presenter import present_case, present_queue, present_record

    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    result = run_case(case, load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json"))
    finding = result.phat_hien[0]
    feedback = PhanHoi(
        thoi_diem=datetime(2026, 11, 16, tzinfo=UTC),
        ca_id=case.ca_id,
        ma_luat=finding.ma_luat,
        yeu_to=finding.yeu_to,
        chi_tiet_y_lenh_id=finding.chi_tiet_y_lenh_id,
        phan_hoi="bac_bo",
        nhom_ly_do="khac",
        ly_do="Đã xem",
    )
    newer = feedback.model_copy(
        update={"thoi_diem": datetime(2026, 11, 17, tzinfo=UTC), "phan_hoi": "dong_y"}
    )
    before = (case.model_dump_json(), result.model_dump_json())
    body = present_case(case, result, [newer, feedback])
    assert body.nhan_dinh.can_chu_y[0].phan_hoi.phan_hoi == "dong_y"
    assert body.nhan_dinh.can_chu_y[0].phan_hoi.thoi_diem_text == "17/11/2026 07:00"
    assert newer.thoi_diem.tzinfo is UTC
    assert body.nhan_dinh.can_chu_y[0].dien_giai_ai is None
    assert body.nhan_dinh.can_chu_y[0].de_xuat_ai is None
    assert body.nhan_dinh.can_chu_y[0].trich_dan == []
    assert present_queue([case], {case.ca_id: result}, [newer, feedback])[0].da_phan_hoi_het
    assert present_record(case, "XN-DEMO02-01").loai == "Xét nghiệm"
    assert present_record(case, "LA") is None
    assert before == (case.model_dump_json(), result.model_dump_json())


def test_unknown_calculation_evidence_cannot_open() -> None:
    from app.api.presenter import present_case
    from app.rules.types import CanCu

    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    result = run_case(case, load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json"))
    finding = result.phat_hien[0].model_copy(
        update={"ma_luat": "LA", "can_cu": [CanCu(loai="tinh_toan", mo_ta="Chưa xác định")]}
    )
    result = result.model_copy(update={"phat_hien": [finding]})
    evidence = present_case(case, result, []).nhan_dinh.can_chu_y[0].can_cu[0]
    assert evidence.cong_thuc is None
    assert evidence.mo_duoc is False
