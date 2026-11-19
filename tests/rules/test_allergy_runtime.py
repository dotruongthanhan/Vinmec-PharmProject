"""Kiểm tra chạy thật yếu tố 1 trên toàn bộ 66 ca giả lập với SQLite D3."""

from pathlib import Path

import pytest

from app.config.settings import load_settings
from app.container import Container
from app.db.reader import load_source_cases
from app.domain.models import CaBenh
from app.rules.engine import run_rules
from app.rules.registry import AllergyRule, RuleContext

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.can_du_lieu("data/kb_curated/tra_cuu/tra_cuu.sqlite")


@pytest.fixture(scope="module")
def runtime_context() -> RuleContext:
    ctx = Container(load_settings("test")).rule_context
    assert ctx.resolver is not None
    return ctx


@pytest.fixture(scope="module")
def source_cases() -> list[CaBenh]:
    cases = load_source_cases(ROOT)
    assert len(cases) == 66
    return cases


@pytest.mark.parametrize(
    ("ca_id", "expected_rule", "expected_line_id", "expected_group"),
    [
        ("DEMO-06", "di_ung_cheo", "CT-DEMO06-01", "BL01_PENICILLIN_NOI_NHOM"),
        ("HS-010", "di_ung_cheo", "CT-HS-010-01-01", "BL01_PENICILLIN_NOI_NHOM"),
        ("HS-011", "di_ung_cheo", "CT-HS-011-04-01", "SU01_SULFONAMID_KHANG_KHUAN"),
        ("HS-013", "di_ung_cheo", "CT-HS-013-04-01", "BL01_PENICILLIN_NOI_NHOM"),
        ("HS-056", "di_ung_trung_hoat_chat", "CT-HS-056-05-01", None),
    ],
)
def test_five_allergy_cases_with_real_resolver(
    ca_id: str,
    expected_rule: str,
    expected_line_id: str,
    expected_group: str | None,
    source_cases: list[CaBenh],
    runtime_context: RuleContext,
) -> None:
    ca = next(case for case in source_cases if case.ca_id == ca_id)
    assert [line.chi_tiet_y_lenh_id for line in ca.y_lenh_cho_duyet.chi_tiet] == [
        expected_line_id
    ]
    (finding,) = AllergyRule().check(ca, runtime_context)

    assert finding.ma_luat == expected_rule
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "nghiem_trong"
    assert finding.chi_tiet_y_lenh_id == [expected_line_id]
    if expected_group is not None:
        assert any(
            cc.loai == "tai_lieu" and cc.ban_ghi_id == expected_group
            for cc in finding.can_cu
        )


def test_all_66_cases_factor_1_with_real_resolver(
    source_cases: list[CaBenh],
    runtime_context: RuleContext,
) -> None:
    missing_info_cases: list[str] = []
    no_allergy_cases: list[str] = []
    positive_rules: dict[str, str] = {}

    for ca in source_cases:
        rule_findings = AllergyRule().check(ca, runtime_context)
        engine_findings = [
            f
            for f in run_rules(ca, runtime_context.renal_rules, runtime_context.resolver)
            if f.yeu_to == 1
        ]
        assert rule_findings == engine_findings

        keys = [(f.ma_luat, tuple(f.chi_tiet_y_lenh_id)) for f in rule_findings]
        assert len(keys) == len(set(keys))
        assert len(rule_findings) == 1

        (finding,) = rule_findings
        if finding.ma_luat == "di_ung_thieu_thong_tin":
            missing_info_cases.append(ca.ca_id)
        elif finding.ma_luat == "di_ung_khong_co":
            no_allergy_cases.append(ca.ca_id)
        else:
            positive_rules[ca.ca_id] = finding.ma_luat

    assert sorted(missing_info_cases) == ["DEMO-03", "HS-012", "HS-038"]
    assert len(no_allergy_cases) == 58
    assert positive_rules == {
        "DEMO-06": "di_ung_cheo",
        "HS-010": "di_ung_cheo",
        "HS-011": "di_ung_cheo",
        "HS-013": "di_ung_cheo",
        "HS-056": "di_ung_trung_hoat_chat",
    }
