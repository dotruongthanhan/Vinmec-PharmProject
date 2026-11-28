"""Đối chiếu T57 trên ca giả lập qua registry, pipeline và API."""

from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import container as container_mod
from app.api.main import create_app
from app.api.schemas import ChiTietCa
from app.api.service import CaseService
from app.config.settings import load_settings
from app.container import Container
from app.db.reader import load_source_cases
from app.pipeline import run_case
from app.rules.duplicate import check
from app.rules.engine import run_rules
from app.rules.registry import run_registered

ROOT = Path(__file__).resolve().parents[2]


def test_all_source_cases_have_only_four_expected_treatment_duplicates() -> None:
    container = Container(load_settings("test"))
    ctx = container.rule_context
    assert ctx.resolver is not None
    cases = load_source_cases(ROOT)
    assert len(cases) == 66
    duplicate_rule = next(rule for rule in container.rules if rule.yeu_to == 2)
    before: Counter[str] = Counter()
    after: Counter[str] = Counter()
    groups: dict[str, tuple[str, str | None]] = {}
    missing: set[str] = set()
    for ca in cases:
        before[check(ca)[0].ket_luan] += 1
        findings = duplicate_rule.check(ca, ctx)
        after[findings[0].ket_luan] += 1
        for finding in findings:
            if finding.ma_luat == "trung_nhom_dieu_tri":
                assert ca.ca_id not in groups
                group = next(row.ban_ghi_id for row in finding.can_cu if row.loai == "tai_lieu")
                assert group is not None
                groups[ca.ca_id] = (group, finding.muc_do)
            if finding.ket_luan == "khong_du_du_lieu":
                missing.add(ca.ca_id)
        registered = run_registered(ca, ctx, container.rules)
        existing = run_rules(ca, ctx.renal_rules, ctx.resolver, ctx.interactions)
        assert [row for row in registered if row.yeu_to != 2] == [
            row for row in existing if row.yeu_to != 2
        ]
    assert before == {"dat": 63, "can_xem": 3}
    assert after == {"dat": 56, "can_xem": 7, "khong_du_du_lieu": 3}
    assert groups == {
        "HS-014": ("uc_che_ras", "nghiem_trong"),
        "HS-015": ("ppi", "can_luu_y"),
        "HS-016": ("chong_dong", "nghiem_trong"),
        "HS-017": ("nsaid", "nghiem_trong"),
    }
    assert missing == {"HS-013", "HS-039", "HS-040"}


@pytest.mark.parametrize("with_resolver", [True, False])
def test_run_case_hs016_uses_new_rule_only_with_resolver(with_resolver: bool) -> None:
    ctx = Container(load_settings("test")).rule_context
    assert ctx.resolver is not None
    case = next(case for case in load_source_cases(ROOT) if case.ca_id == "HS-016")
    result = run_case(case, ctx.renal_rules, resolver=ctx.resolver if with_resolver else None)
    findings = [row for row in result.phat_hien if row.yeu_to == 2]
    assert len(findings) == 1
    finding = findings[0]
    if with_resolver:
        assert finding.ma_luat == "trung_nhom_dieu_tri"
        assert finding.ket_luan == "can_xem"
        assert finding.muc_do == "nghiem_trong"
        assert any(row.ban_ghi_id == "chong_dong" for row in finding.can_cu)
    else:
        assert finding.ma_luat == "trung_hoat_chat_khong_co"
        assert finding.ket_luan == "dat"
        assert findings == check(case)


def test_api_all_source_cases_match_registry_treatment_duplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("CASE_SOURCE", "file")
    container = Container(load_settings("test"))
    ctx = container.rule_context
    assert ctx.resolver is not None
    monkeypatch.setattr(container_mod, "get_rule_context", lambda: ctx)
    cases = load_source_cases(ROOT)
    assert len(cases) == 66
    for case in cases:
        (tmp_path / f"{case.ca_id}.json").write_text(case.model_dump_json(), encoding="utf-8")
    rule = next(rule for rule in container.rules if rule.yeu_to == 2)
    counts: Counter[str] = Counter()
    groups: dict[str, tuple[str, str | None]] = {}
    missing: set[str] = set()
    service = CaseService(
        tmp_path,
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "feedback.jsonl",
        ai_runner=None,
        asker=None,
    )
    with TestClient(create_app(service)) as client:
        for case in cases:
            response = client.get(f"/api/cases/{case.ca_id}")
            assert response.status_code == 200, case.ca_id
            detail = ChiTietCa.model_validate(response.json())
            findings = [
                row
                for row in detail.nhan_dinh.can_chu_y + detail.nhan_dinh.dat
                if row.yeu_to.startswith("2.")
            ]
            assert findings, case.ca_id
            assert sorted((row.ma_luat, row.ket_luan_ma) for row in findings) == sorted(
                (row.ma_luat, row.ket_luan) for row in rule.check(case, ctx)
            ), case.ca_id
            conclusions = {row.ket_luan_ma for row in findings}
            assert len(conclusions) == 1, case.ca_id
            counts[conclusions.pop()] += 1
            for finding in findings:
                if finding.ket_luan_ma == "khong_du_du_lieu":
                    missing.add(case.ca_id)
                if finding.ma_luat == "trung_nhom_dieu_tri":
                    assert case.ca_id not in groups
                    group = next(
                        row.ban_ghi_id for row in finding.can_cu if row.loai_ma == "tai_lieu"
                    )
                    assert group is not None
                    groups[case.ca_id] = (group, finding.muc_do_ma)
                    if case.ca_id == "HS-016":
                        assert "Trùng nhóm chống đông" in finding.nhan_xet
                        evidence = "\n".join(row.mo_ta for row in finding.can_cu)
                        assert "B01AB" in evidence
                        assert "B01AF" in evidence
                        assert "chờ dược sĩ duyệt bảng nhóm" in evidence
    assert counts == {"dat": 56, "can_xem": 7, "khong_du_du_lieu": 3}
    assert groups == {
        "HS-014": ("uc_che_ras", "nghiem_trong"),
        "HS-015": ("ppi", "can_luu_y"),
        "HS-016": ("chong_dong", "nghiem_trong"),
        "HS-017": ("nsaid", "nghiem_trong"),
    }
    assert missing == {"HS-013", "HS-039", "HS-040"}
