"""Đo độ phủ trên ca giả lập và chạy các tên nghiệm thu."""

import csv
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from app.kb.resolver import DrugResolver
from app.kb.resolver.build import DDINTER_CSV, INDEX_PATH, REPORT_DIR, _load_cases

_EXAMPLES = (
    "Augmentin",
    "Ceftriaxon 1 g",
    "Cotrimoxazol 800/160 mg",
    "Amoxicilin + acid clavulanic 875 mg/125 mg",
    "Natri clorid 0,9% 500 mL",
    "Glibenclamid 5 mg",
    "Thuốc XYZ 10 mg",
)


def report(root: Path) -> dict[str, Any]:
    """Ghi thống kê, các dòng còn thiếu và lý do hoạt chất chưa nối DDInter."""
    started = perf_counter()
    resolver = DrugResolver.from_index(root / INDEX_PATH)
    load_seconds = perf_counter() - started
    cases = _load_cases(root)
    statuses = dict.fromkeys(("da_phan_giai", "mot_phan", "khong_nhan_dien", "khong_ap_dung"), 0)
    sources = dict.fromkeys(
        ("danh_muc_ca", "ten_thuoc_dav", "dong_nghia", "tach_phoi_hop", "khong_co"), 0
    )
    exceptions = []
    covered_lines = 0
    resolve_seconds = 0.0
    case_ingredients: dict[str, str | None] = {}
    unmapped = set()
    for case in cases:
        catalog = {row.thuoc_id: row.ten_thuoc for row in case.danh_muc_thuoc}
        ingredients = {row.hoat_chat_id: row for row in case.danh_muc_hoat_chat}
        for code in ingredients:
            match = resolver._match_case_ingredient(code, ingredients)
            if match.hoat_chat_id is None:
                unmapped.add((code, match.ly_do or "Chưa chuyển mã"))
            else:
                case_ingredients[match.hoat_chat_id] = resolver._axis[match.hoat_chat_id].ddinter_id
        for line in (*case.y_lenh_cho_duyet.chi_tiet, *case.thuoc_dang_dung):
            started = perf_counter()
            resolved = resolver.resolve_line(case, line)
            resolve_seconds += perf_counter() - started
            statuses[resolved.trang_thai] += 1
            sources[resolved.nguon_khop or "khong_co"] += 1
            if resolved.trang_thai != "da_phan_giai":
                exceptions.append(
                    {
                        "ca_id": case.ca_id,
                        "chi_tiet_y_lenh_id": line.chi_tiet_y_lenh_id,
                        "ten": catalog.get(line.thuoc_id or "", line.ten_tu_do),
                        "trang_thai": resolved.trang_thai,
                        "ly_do": resolved.ly_do,
                    }
                )
            if (
                resolved.trang_thai in {"da_phan_giai", "khong_ap_dung"}
                and resolved.thanh_phan
                and all(row.ddinter_id for row in resolved.thanh_phan)
            ):
                covered_lines += 1
            for row in resolved.thanh_phan:
                case_ingredients[row.hoat_chat_id] = row.ddinter_id

    with (root / REPORT_DIR / DDINTER_CSV).open(encoding="utf-8", newline="") as stream:
        unlinked = {
            row["hoat_chat_id"]: {
                "ly_do": row["ly_do"],
                "ung_vien_xung_dot": row["ung_vien_xung_dot"],
                "goi_y_atc": row["goi_y_atc"],
            }
            for row in csv.DictReader(stream)
            if row["phia"] == "truc" and row["hoat_chat_id"] in case_ingredients
        }
    total = sum(statuses.values())
    covered_ingredients = sum(value is not None for value in case_ingredients.values())
    data = {
        "so_ca": len(cases),
        "tong_so_dong": total,
        "theo_trang_thai": statuses,
        "theo_nguon_khop": sources,
        "dong_khong_da_phan_giai": exceptions,
        "so_dong_du_ddinter_id": covered_lines,
        "so_hoat_chat_ca": len(case_ingredients),
        "so_hoat_chat_ca_co_ddinter_id": covered_ingredients,
        "hoat_chat_ca_thieu_ddinter_id": unlinked,
        "ma_ca_chua_chuyen": [
            {"ma_ca": code, "ly_do": reason} for code, reason in sorted(unmapped)
        ],
        "giay_nap_chi_muc": load_seconds,
        "giay_trung_binh_moi_dong": resolve_seconds / total if total else None,
        "tra_thu": {name: resolver.resolve_name(name).model_dump() for name in _EXAMPLES},
    }
    (root / REPORT_DIR / "T53_phan_giai_ca.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return data
