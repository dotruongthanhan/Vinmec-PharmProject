from pathlib import Path

import pytest

from app.core.interfaces import Rule
from app.domain.loader import load_case
from app.rules.engine import run_rules
from app.rules.registry import RuleContext, default_rules, run_registered
from app.rules.renal_dose import load_renal_rules

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("number", range(1, 7))
def test_registered_matches_existing_engine(number: int) -> None:
    ca = load_case(ROOT / f"data/mock/demo/DEMO-{number:02}.json")
    renal = load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json")
    rules = default_rules()
    assert all(isinstance(rule, Rule) for rule in rules)
    assert [(rule.ma_nhom, rule.yeu_to) for rule in rules] == [
        ("allergy", 1),
        ("duplicate", 2),
        ("antibiotic", 3),
        ("interaction", 4),
        ("renal_dose", 6),
        ("schedule", 7),
    ]
    assert run_registered(ca, RuleContext(renal), rules) == run_rules(ca, renal)
