"""Bộ chạy tổng hợp 5 luật thẩm định y lệnh và sắp xếp kết quả theo mức độ ưu tiên."""

from collections.abc import Callable

from app.domain.models import CaBenh
from app.rules import allergy, antibiotic, duplicate, renal_dose, schedule
from app.rules.renal_dose import RenalRuleBook
from app.rules.types import CanCu, PhatHien, pending_lines


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
    interaction_rules: object | None = None,
) -> list[PhatHien]:
    """Chạy lần lượt 6 luật theo thứ tự 1, 2, 3, 4, 6, 7, cô lập lỗi và sắp xếp ổn định."""
    from pathlib import Path

    from app.rules import interaction
    from app.rules.interaction import InteractionBook, load_interaction_rules_if_exists

    resolved_interactions = (
        interaction_rules
        if isinstance(interaction_rules, InteractionBook)
        else load_interaction_rules_if_exists(Path("data/kb_curated/tuong_tac.jsonl"))
    )
    steps: list[tuple[str, int, Callable[[], list[PhatHien]]]] = [
        ("allergy", 1, lambda: allergy.check(ca)),
        ("duplicate", 2, lambda: duplicate.check(ca)),
        ("antibiotic", 3, lambda: antibiotic.check(ca)),
        ("interaction", 4, lambda: interaction.check(ca, resolved_interactions)),
        ("renal_dose", 6, lambda: renal_dose.check(ca, renal_rules)),
        ("schedule", 7, lambda: schedule.check(ca)),
    ]

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

    return sorted(findings, key=_priority_key)
