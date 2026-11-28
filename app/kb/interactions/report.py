"""Chạy ma trận trên các ca giả lập cục bộ, không thay đổi đầu vào."""

import json
from collections import Counter
from pathlib import Path

from app.kb.interactions import InteractionStore
from app.kb.interactions.build import INDEX_PATH
from app.kb.resolver import DrugResolver
from app.kb.resolver.build import INDEX_PATH as RESOLVER_PATH
from app.kb.resolver.build import _load_cases
from app.rules.interaction import build_interaction_matrix

REPORT_PATH = Path("data/kb_reports/T55_ma_tran_ca.json")


def report_cases(root: Path = Path(".")) -> dict[str, object]:
    """Ghi từng cặp cần chú ý và lý do thiếu dữ liệu theo ca."""
    resolver = DrugResolver.from_index(root / RESOLVER_PATH)
    store = InteractionStore.from_path(root / INDEX_PATH)
    totals: Counter[str] = Counter(
        dict.fromkeys(
            (
                "nghiem_trong",
                "can_luu_y",
                "thieu_du_lieu",
                "khong_phat_hien",
                "khong_ap_dung",
            ),
            0,
        )
    )
    cases = []
    for ca in sorted(_load_cases(root), key=lambda item: item.ca_id):
        matrix = build_interaction_matrix(ca, resolver, store)
        counts = Counter(row.muc for row in matrix.cap)
        totals.update(counts)
        names = {row.chi_tiet_y_lenh_id: row.ten for row in matrix.thuoc}
        pairs = [
            {**row.model_dump(), "ten_a": names[row.a], "ten_b": names[row.b]} for row in matrix.cap
        ]
        cases.append(
            {
                "ca_id": ca.ca_id,
                "so_cap_theo_muc": dict(counts),
                "can_chu_y": [row for row in pairs if row["muc"] in {"nghiem_trong", "can_luu_y"}],
                "thieu_du_lieu": [row for row in pairs if row["muc"] == "thieu_du_lieu"],
                "ma_tran_tuong_tac": matrix.model_dump(),
            }
        )
    result = {
        "so_ca": len(cases),
        "so_cap": sum(totals.values()),
        "so_cap_theo_muc": dict(totals),
        "chua_kiem": 0,
        "ca": cases,
    }
    path = root / REPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {key: value for key, value in result.items() if key != "ca"}
