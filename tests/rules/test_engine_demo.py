"""Kiểm thử bộ chạy run_rules, CLI và đối chiếu trên 6 ca demo với bộ đáp án."""

import json
from datetime import timedelta
from pathlib import Path

import pytest

import app.rules.__main__ as rules_cli
from app.domain.loader import load_answer, load_case
from app.domain.models import CaBenh, ChiTietYLenh, LichDung
from app.rules.engine import run_rules
from app.rules.renal_dose import load_renal_rules
from app.rules.types import PhatHien
from tests.rules import NOW, make_minimal_case

_ROOT = Path(__file__).resolve().parents[2]
_DEMO_MOCK_DIR = _ROOT / "data" / "mock" / "demo"
_DEMO_GOLD_DIR = _ROOT / "data" / "gold" / "demo"
_RENAL_RULES_PATH = _ROOT / "data" / "kb" / "quy_tac_lieu_than.json"


def _issue_set_from_findings(findings: list[PhatHien]) -> set[tuple[int, str]]:
    """Trích tập (yeu_to, ket_luan) của các phát hiện khác 'dat'."""
    return {(item.yeu_to, item.ket_luan) for item in findings if item.ket_luan != "dat"}


def test_demo_cases_expected_issues_and_details() -> None:
    """Chạy bộ luật trên cả 6 ca demo và kiểm tra đúng tập vấn đề cùng chi tiết bắt buộc."""
    renal_rules = load_renal_rules(_RENAL_RULES_PATH)
    expected_by_case: dict[str, set[tuple[int, str]]] = {
        "DEMO-01": set(),
        "DEMO-02": {(6, "can_xem")},
        "DEMO-03": {(1, "khong_du_du_lieu")},
        "DEMO-04": set(),
        "DEMO-05": {(7, "can_xem")},
        "DEMO-06": {(1, "can_xem")},
    }

    findings_by_case = {}
    for case_id, expected_issues in expected_by_case.items():
        ca = load_case(_DEMO_MOCK_DIR / f"{case_id}.json")
        findings = run_rules(ca, renal_rules)
        findings_by_case[case_id] = findings
        assert _issue_set_from_findings(findings) == expected_issues

    demo2_issue = next(
        item
        for item in findings_by_case["DEMO-02"]
        if (item.yeu_to, item.ket_luan) == (6, "can_xem")
    )
    assert demo2_issue.muc_do == "nghiem_trong"
    assert demo2_issue.ma_luat == "lieu_than_can_chinh"
    assert "16.0" in demo2_issue.mo_ta
    assert len(demo2_issue.can_cu) == 3
    assert [c.loai for c in demo2_issue.can_cu] == ["du_lieu", "tinh_toan", "tai_lieu"]
    assert demo2_issue.can_cu[0].ban_ghi_id == "XN-DEMO02-01"
    assert demo2_issue.can_cu[1].ban_ghi_id == "cockcroft_gault"
    assert demo2_issue.can_cu[2].mo_ta == renal_rules.quy_tac[0].nguon

    assert any(
        item.ket_luan == "dat" and item.ma_luat == "khang_sinh_vi_sinh_nhay"
        for item in findings_by_case["DEMO-04"]
    )

    demo5_issue = next(
        item
        for item in findings_by_case["DEMO-05"]
        if (item.yeu_to, item.ket_luan) == (7, "can_xem")
    )
    assert demo5_issue.ma_luat == "lich_dung_thieu_lieu"

    demo6_issue = next(
        item
        for item in findings_by_case["DEMO-06"]
        if (item.yeu_to, item.ket_luan) == (1, "can_xem")
    )
    assert demo6_issue.muc_do == "nghiem_trong"
    assert demo6_issue.ma_luat == "di_ung_cung_nhom"


@pytest.mark.parametrize(
    "case_id",
    ["DEMO-01", "DEMO-02", "DEMO-03", "DEMO-04", "DEMO-05", "DEMO-06"],
)
def test_demo_cases_match_gold_answers(case_id: str) -> None:
    """Tập vấn đề do bộ luật sinh ra khớp với tập vấn đề trong bộ đáp án chuẩn."""
    renal_rules = load_renal_rules(_RENAL_RULES_PATH)
    ca = load_case(_DEMO_MOCK_DIR / f"{case_id}.json")
    gold = load_answer(_DEMO_GOLD_DIR / f"{case_id}.json")

    expected = {
        (item.yeu_to, item.ket_luan) for item in gold.phat_hien_ky_vong if item.ket_luan != "dat"
    }
    actual = _issue_set_from_findings(run_rules(ca, renal_rules))
    assert actual == expected


def test_engine_isolates_rule_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Một luật ném RuntimeError không làm mất kết quả các luật khác và sinh loi_luat."""
    renal_rules = load_renal_rules(_RENAL_RULES_PATH)
    ca = make_minimal_case(
        trang_thai_di_ung="khong_di_ung_da_hoi",
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-1",
                thuoc_id="T-DEFAULT",
                tan_suat="2 lần/ngày",
                so_lan_moi_ngay=2,
                khoang_cach_gio=12.0,
                bat_dau=NOW,
                trang_thai_dong="active",
                lich_dung=[
                    LichDung(thoi_diem_du_kien=NOW, lieu=500.0, don_vi="mg"),
                    LichDung(
                        thoi_diem_du_kien=NOW + timedelta(hours=24),
                        lieu=500.0,
                        don_vi="mg",
                    ),
                ],
            ),
        ],
    )

    def _boom(_ca: CaBenh) -> list[PhatHien]:
        raise RuntimeError("lỗi giả lập")

    monkeypatch.setattr("app.rules.duplicate.check", _boom)
    findings = run_rules(ca, renal_rules)

    error_findings = [item for item in findings if item.ma_luat == "loi_luat"]
    assert len(error_findings) == 1
    err = error_findings[0]
    assert err.yeu_to == 2
    assert err.ket_luan == "khong_du_du_lieu"
    assert err.muc_do is None
    assert err.thong_tin_con_thieu == ["luat_chay_loi"]
    assert "duplicate" in err.mo_ta
    assert "RuntimeError" in err.mo_ta

    by_code = {item.ma_luat: item for item in findings}
    expected_codes = {
        "loi_luat",
        "di_ung_khong_co",
        "lich_dung_thieu_lieu",
        "y_lenh_thieu_truong",
    }
    assert expected_codes <= set(by_code)
    assert by_code["lich_dung_thieu_lieu"].ket_luan == "can_xem"
    assert by_code["y_lenh_thieu_truong"].ket_luan == "can_xem"
    assert by_code["di_ung_khong_co"].ket_luan == "dat"


def test_cli_outputs_valid_utf8_json(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI python -m app.rules xuất JSON UTF-8 hợp lệ cho DEMO-02."""
    exit_code = rules_cli.main(
        [
            str(_DEMO_MOCK_DIR / "DEMO-02.json"),
            "--renal-rules",
            str(_RENAL_RULES_PATH),
        ],
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert isinstance(parsed, list)
    assert any(item["ma_luat"] == "lieu_than_can_chinh" for item in parsed)
