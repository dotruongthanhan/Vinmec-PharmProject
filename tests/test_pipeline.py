"""Kiểm thử đường chạy (pipeline) thẩm định y lệnh trên dữ liệu demo và ca biên."""

from pathlib import Path

import pytest

from app.domain.loader import load_all_cases, load_case
from app.pipeline import run_case
from app.rules import load_renal_rules

_ROOT = Path(__file__).resolve().parents[1]
_DEMO_DIR = _ROOT / "data" / "mock" / "demo"
_RENAL_RULES_PATH = _ROOT / "data" / "kb" / "quy_tac_lieu_than.json"


def test_run_case_demo02_cockcroft_gault_and_provenance() -> None:
    """DEMO-02 tính đúng CrCl Cockcroft-Gault và gắn đúng nguồn gốc dữ liệu đầu vào."""
    ca = load_case(_DEMO_DIR / "DEMO-02.json")
    renal_rules = load_renal_rules(_RENAL_RULES_PATH)

    res = run_case(ca, renal_rules)

    assert [c.cong_thuc for c in res.chi_so] == [
        "cockcroft_gault",
        "egfr_ckd_epi_2021",
        "bmi",
        "bsa_mosteller",
    ]
    cg = res.chi_so[0]
    assert cg.cong_thuc == "cockcroft_gault"
    assert cg.ket_qua == pytest.approx(15.9988, rel=1e-3)

    creat_input = next(inp for inp in cg.dau_vao if inp.ten == "creatinin")
    assert creat_input.ban_ghi_id == "XN-DEMO02-01"
    assert creat_input.gia_tri == 212.0
    assert creat_input.thoi_diem is not None

    weight_input = next(inp for inp in cg.dau_vao if inp.ten == "can_nang_kg")
    assert weight_input.ban_ghi_id == "SH-DEMO02-01"
    assert weight_input.thoi_diem is not None


def test_run_case_missing_vitals_returns_missing_input() -> None:
    """Ca bị xoá hết sinh hiệu không ném lỗi, Cockcroft-Gault báo thiếu can_nang_kg."""
    ca = load_case(_DEMO_DIR / "DEMO-02.json").model_copy(update={"sinh_hieu": []})
    renal_rules = load_renal_rules(_RENAL_RULES_PATH)

    res = run_case(ca, renal_rules)

    cg = res.chi_so[0]
    assert cg.cong_thuc == "cockcroft_gault"
    assert cg.ket_qua is None
    assert "can_nang_kg" in cg.thieu_dau_vao


def test_run_case_pediatric_age_handles_value_error_safely() -> None:
    """Người bệnh 10 tuổi khiến CKD-EPI ném ValueError được bắt thành so_lieu_hop_le."""
    base = load_case(_DEMO_DIR / "DEMO-01.json")
    young_patient = base.nguoi_benh.model_copy(update={"tuoi": 10})
    ca = base.model_copy(update={"nguoi_benh": young_patient})
    renal_rules = load_renal_rules(_RENAL_RULES_PATH)

    res = run_case(ca, renal_rules)

    egfr = res.chi_so[1]
    assert egfr.cong_thuc == "egfr_ckd_epi_2021"
    assert egfr.ket_qua is None
    assert egfr.thieu_dau_vao == ["so_lieu_hop_le"]
    assert egfr.ghi_chu


def test_run_case_all_six_demo_cases() -> None:
    """Cả 6 ca demo đều chạy thông suốt qua đường chạy và đo thời gian >= 0."""
    cases = load_all_cases(_DEMO_DIR)
    renal_rules = load_renal_rules(_RENAL_RULES_PATH)

    assert len(cases) == 6
    for ca in cases:
        res = run_case(ca, renal_rules)
        assert res.ca_id == ca.ca_id
        assert len(res.chi_so) == 4
        assert res.thoi_gian_ms >= 0.0
