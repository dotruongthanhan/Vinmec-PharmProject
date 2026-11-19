"""Bộ chạy luật thẩm định, dùng thêm yếu tố 4 khi có đủ chỉ mục."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from app.domain.models import CaBenh
from app.rules import allergy, antibiotic, duplicate, renal_dose, schedule
from app.rules.renal_dose import RenalRuleBook
from app.rules.types import CanCu, PhatHien, pending_lines

if TYPE_CHECKING:
    from app.kb.interactions import InteractionStore
    from app.kb.interactions.models import MaTranTuongTac
    from app.kb.resolver import DrugResolver


def _priority_key(finding: PhatHien) -> int:
    """Xác định khóa sắp xếp ưu tiên ổn định cho phát hiện."""
    if finding.ket_luan == "can_xem":
        if finding.muc_do == "nghiem_trong":
            return 0
        if finding.muc_do == "can_luu_y":
            return 1
        return 2
    if finding.ket_luan == "khong_du_du_lieu":
        return 3
    if finding.ket_luan == "ngoai_hdsd":
        return 4
    if finding.ket_luan == "dat":
        return 5
    return 6


def run_rules(
    ca: CaBenh,
    renal_rules: RenalRuleBook,
    resolver: DrugResolver | None = None,
    interactions: InteractionStore | None = None,
) -> list[PhatHien]:
    """Giữ giao diện trả phát hiện; phụ thuộc mới đều tùy chọn."""
    return run_rules_with_matrix(ca, renal_rules, resolver, interactions)[0]


def run_rules_with_matrix(
    ca: CaBenh,
    renal_rules: RenalRuleBook,
    resolver: DrugResolver | None = None,
    interactions: InteractionStore | None = None,
) -> tuple[list[PhatHien], MaTranTuongTac | None]:
    """Cô lập lỗi từng luật, sắp ổn định và giữ lại ma trận đã tính."""
    matrix: MaTranTuongTac | None = None

    def run_interaction() -> list[PhatHien]:
        """Nhập trễ để luật dùng chung khóa ưu tiên của engine."""
        from app.rules.interaction import check_with_matrix

        nonlocal matrix
        findings, matrix = check_with_matrix(ca, resolver, interactions)
        return findings

    steps: list[tuple[str, int, Callable[[], list[PhatHien]]]] = [
        ("allergy", 1, lambda: allergy.check(ca)),
        (
            "duplicate",
            2,
            lambda: duplicate.check(ca, resolver) if resolver is not None else duplicate.check(ca),
        ),
        ("antibiotic", 3, lambda: antibiotic.check(ca)),
        ("renal_dose", 6, lambda: renal_dose.check(ca, renal_rules)),
        ("schedule", 7, lambda: schedule.check(ca)),
    ]
    if resolver is not None and interactions is not None:
        steps.insert(3, ("interaction", 4, run_interaction))

    all_line_ids = [line.chi_tiet_y_lenh_id for line in pending_lines(ca)]
    findings: list[PhatHien] = []
    for rule_name, yeu_to, runner in steps:
        try:
            findings.extend(runner())
        except Exception as exc:
            findings.append(
                PhatHien(
                    ma_luat="loi_luat",
                    yeu_to=yeu_to,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=all_line_ids,
                    mo_ta=f"Luật {rule_name} gặp lỗi {type(exc).__name__}: {exc}",
                    can_cu=[
                        CanCu(
                            loai="tinh_toan",
                            ban_ghi_id=rule_name,
                            mo_ta=f"Ngoại lệ {type(exc).__name__}: {exc}",
                        ),
                    ],
                    thong_tin_con_thieu=["luat_chay_loi"],
                ),
            )

    return sorted(findings, key=_priority_key), matrix
