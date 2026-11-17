"""Lớp bọc mỏng cho năm module luật hiện có."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.models import CaBenh
from app.rules import allergy, antibiotic, duplicate, renal_dose, schedule
from app.rules.engine import _priority_key
from app.rules.renal_dose import RenalRuleBook
from app.rules.types import PhatHien

if TYPE_CHECKING:
    from app.core.interfaces import Rule


@dataclass(frozen=True)
class RuleContext:
    """Phụ thuộc dùng chung của các luật."""

    renal_rules: RenalRuleBook


class AllergyRule:
    """Bọc luật dị ứng."""

    ma_nhom: str = "allergy"
    yeu_to: int = 1

    def check(self, ca: CaBenh, ctx: RuleContext) -> list[PhatHien]:
        return allergy.check(ca)


class DuplicateRule:
    """Bọc luật trùng thuốc."""

    ma_nhom: str = "duplicate"
    yeu_to: int = 2

    def check(self, ca: CaBenh, ctx: RuleContext) -> list[PhatHien]:
        return duplicate.check(ca)


class AntibioticRule:
    """Bọc luật kháng sinh."""

    ma_nhom: str = "antibiotic"
    yeu_to: int = 3

    def check(self, ca: CaBenh, ctx: RuleContext) -> list[PhatHien]:
        return antibiotic.check(ca)


class RenalDoseRule:
    """Bọc luật liều theo chức năng thận."""

    ma_nhom: str = "renal_dose"
    yeu_to: int = 6

    def check(self, ca: CaBenh, ctx: RuleContext) -> list[PhatHien]:
        return renal_dose.check(ca, ctx.renal_rules)


class ScheduleRule:
    """Bọc luật lịch dùng thuốc."""

    ma_nhom: str = "schedule"
    yeu_to: int = 7

    def check(self, ca: CaBenh, ctx: RuleContext) -> list[PhatHien]:
        return schedule.check(ca)


def default_rules() -> list["Rule"]:
    """Giữ nguyên thứ tự luật trong engine hiện có."""
    return [AllergyRule(), DuplicateRule(), AntibioticRule(), RenalDoseRule(), ScheduleRule()]


def run_registered(ca: CaBenh, ctx: RuleContext, rules: list["Rule"]) -> list[PhatHien]:
    """Chạy các luật rồi dùng chính khóa sắp xếp của engine."""
    findings = [finding for rule in rules for finding in rule.check(ca, ctx)]
    return sorted(findings, key=_priority_key)
