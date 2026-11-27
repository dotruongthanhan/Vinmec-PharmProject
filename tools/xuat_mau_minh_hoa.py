"""Xuất 3 tệp dữ liệu mẫu minh hoạ tương tác theo ngữ pháp mh-0.

Chạy: KB_SOURCE=file uv run python tools/xuat_mau_minh_hoa.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.api.lookup import lookup_interactions  # noqa: E402
from app.api.schemas import KetQuaTraTuongTac  # noqa: E402
from app.calc.hien_thi import CONG_THUC_HIEN_THI  # noqa: E402
from app.calc.renal import cockcroft_gault  # noqa: E402
from app.calc.types import WeightType  # noqa: E402
from app.db.reader import load_source_cases  # noqa: E402
from app.domain.loader import ingredients_of, latest_lab, latest_vital, load_case  # noqa: E402
from app.domain.models import CaBenh  # noqa: E402
from app.kb.names import normalize_key  # noqa: E402
from app.rules.renal_dose import (  # noqa: E402
    RenalDrugRule,
    derive_draw_bounds,
    load_renal_rules,
    select_renal_tier,
)
from app.rules.types import effective_lines  # noqa: E402

_OUT_DIR = _ROOT / "web" / "src" / "features" / "minh-hoa" / "mau"
_DEMO_02_PATH = _ROOT / "data" / "mock" / "demo" / "DEMO-02.json"
_RENAL_RULES_PATH = _ROOT / "data" / "kb" / "quy_tac_lieu_than.json"
_HOSO_DIR = _ROOT / "data" / "mock" / "hoso_gia_lap"
_WEIGHT_TYPES: tuple[WeightType, ...] = ("thuc_te", "ly_tuong", "hieu_chinh")
_CREATININE_MIN = 50
_CREATININE_MAX = 400
_CREATININE_STEP = 5
_CO_CHE_MAX_LEN = 200
_SYNTHETIC_SEED = "VZ0-thong-ke-thang-2026-11-26"
_FALLBACK_CASE_IDS: tuple[str, ...] = ("HS-022", "HS-023", "HS-024", "HS-031", "HS-028")
_SEVERE_INTERACTION_LEVELS: frozenset[str] = frozenset({"nghiem_trong", "chong_chi_dinh"})
_LOOKUP_MIN_DRUGS = 2
_LOOKUP_MAX_DRUGS = 12


@dataclass(frozen=True)
class _InteractionCandidate:
    """Ứng viên ca để dựng ma trận tương tác."""

    source_label: str
    drug_names: list[str]
    result: KetQuaTraTuongTac
    severe_count: int
    warn_count: int


def _find_meropenem_rule() -> RenalDrugRule:
    """Tìm quy tắc liều thận đã duyệt của meropenem."""
    rule_book = load_renal_rules(_RENAL_RULES_PATH)
    for rule in rule_book.quy_tac:
        if rule.ten_quoc_te.strip().lower() == "meropenem":
            return rule
    raise RuntimeError("Không tìm thấy quy tắc meropenem trong quy_tac_lieu_than.json")


def _build_meropenem_sample() -> dict[str, Any]:
    """Dựng tệp mẫu 1: liều meropenem theo CrCl cho ca DEMO-02."""
    case = load_case(_DEMO_02_PATH)
    rule = _find_meropenem_rule()

    creatinin_lab = latest_lab(case, "creatinin")
    weight_vital = latest_vital(case, "can_nang")
    height_vital = latest_vital(case, "chieu_cao")

    if creatinin_lab is None or creatinin_lab.gia_tri_so is None or not creatinin_lab.don_vi:
        raise RuntimeError("DEMO-02 thiếu xét nghiệm creatinin hợp lệ")
    if weight_vital is None:
        raise RuntimeError("DEMO-02 thiếu cân nặng")

    tuoi = case.nguoi_benh.tuoi
    gioi_tinh = case.nguoi_benh.gioi_tinh
    can_nang_kg = float(weight_vital.gia_tri)
    chieu_cao_cm = float(height_vital.gia_tri) if height_vital is not None else None
    case_scr = float(creatinin_lab.gia_tri_so)
    case_scr_unit = creatinin_lab.don_vi

    ds1_rows: list[dict[str, Any]] = [
        {
            "crcl_tu": tier.crcl_tu,
            "crcl_den": tier.crcl_den,
            "bien_ve_tu": bien_ve_tu,
            "bien_ve_den": bien_ve_den,
            "can_chinh": tier.can_chinh,
            "khuyen_cao": tier.khuyen_cao,
        }
        for tier, bien_ve_tu, bien_ve_den in derive_draw_bounds(rule)
    ]

    scr_values = {float(v) for v in range(_CREATININE_MIN, _CREATININE_MAX + 1, _CREATININE_STEP)}
    if _CREATININE_MIN <= case_scr <= _CREATININE_MAX:
        scr_values.add(case_scr)

    ds2_rows: list[dict[str, Any]] = []
    for scr in sorted(scr_values):
        for wtype in _WEIGHT_TYPES:
            try:
                calc = cockcroft_gault(
                    tuoi=tuoi,
                    gioi_tinh=gioi_tinh,
                    can_nang_kg=can_nang_kg,
                    creatinin=scr,
                    creatinin_don_vi=case_scr_unit,
                    loai_can_nang=wtype,
                    chieu_cao_cm=chieu_cao_cm,
                )
            except ValueError:
                continue
            if calc.ket_qua is None:
                continue
            try:
                tier = select_renal_tier(calc.ket_qua, rule)
            except ValueError:
                continue
            ds2_rows.append(
                {
                    "creatinin": scr,
                    "loai_can_nang": wtype,
                    "crcl": calc.ket_qua,
                    "can_chinh": tier.can_chinh,
                    "khuyen_cao": tier.khuyen_cao,
                }
            )

    case_calc = cockcroft_gault(
        tuoi=tuoi,
        gioi_tinh=gioi_tinh,
        can_nang_kg=can_nang_kg,
        creatinin=case_scr,
        creatinin_don_vi=case_scr_unit,
        loai_can_nang="thuc_te",
        chieu_cao_cm=chieu_cao_cm,
    )
    if case_calc.ket_qua is None:
        raise RuntimeError("Không tính được CrCl hiện tại của DEMO-02")
    case_tier = select_renal_tier(case_calc.ket_qua, rule)

    ds3_rows: list[dict[str, Any]] = [
        {
            "ca_id": case.ca_id,
            "creatinin": case_scr,
            "can_nang": can_nang_kg,
            "loai_can_nang": "thuc_te",
            "crcl": case_calc.ket_qua,
            "khuyen_cao": case_tier.khuyen_cao,
        }
    ]

    dac_ta: dict[str, Any] = {
        "phien_ban": "mh-0",
        "tieu_de": "Liều meropenem theo CrCl",
        "phu_de": [
            {"o": {"ds": "ds-3", "cot": "ca_id", "dong": 0}},
            {"chu": " · CrCl "},
            {
                "o": {
                    "ds": "ds-2",
                    "cot": "crcl",
                    "theo_tham_so": True,
                    "dinh_dang": "0.0",
                }
            },
            {"chu": " mL/phút"},
        ],
        "lop": [
            {
                "dau": "dai",
                "du_lieu": "ds-1",
                "ma_hoa": {
                    "x_tu": {"cot": "bien_ve_tu"},
                    "x_den": {"cot": "bien_ve_den"},
                    "nhan": {"cot": "khuyen_cao"},
                    "mau": {"cot": "can_chinh"},
                },
            },
            {
                "dau": "quy_tac",
                "du_lieu": "ds-3",
                "ma_hoa": {
                    "x": {"cot": "crcl", "kieu": "dinh_luong"},
                    "nhan": {"chu": "Mốc của ca"},
                },
            },
            {
                "dau": "diem",
                "du_lieu": "ds-2",
                "loc": [
                    {"cot": "creatinin", "bang_tham_so": "cr"},
                    {"cot": "loai_can_nang", "bang_tham_so": "cn"},
                ],
                "ma_hoa": {
                    "x": {"cot": "crcl", "kieu": "dinh_luong"},
                    "nhan": {"chu": "giả định"},
                },
            },
        ],
        "truc": {
            "x": {"tieu_de": "CrCl (mL/phút)", "mien": "tu_0"},
            "y": None,
        },
        "tham_so": [
            {
                "ma": "cr",
                "loai": "thanh_keo",
                "nhan": "Creatinin (µmol/L)",
                "gia_tri_tu": {"ds": "ds-2", "cot": "creatinin"},
                "mac_dinh": {"o": {"ds": "ds-3", "cot": "creatinin", "dong": 0}},
                "nhan_gia_dinh": True,
            },
            {
                "ma": "cn",
                "loai": "chon_mot",
                "nhan": "Cân nặng",
                "gia_tri_tu": {"ds": "ds-2", "cot": "loai_can_nang"},
                "mac_dinh": {"o": {"ds": "ds-3", "cot": "loai_can_nang", "dong": 0}},
            },
            {
                "loai": "dat_lai",
                "nhan": "Về số của ca",
            },
        ],
        "so_hien": [
            {
                "nhan": "CrCl (mL/phút)",
                "o": {
                    "ds": "ds-2",
                    "cot": "crcl",
                    "theo_tham_so": True,
                    "dinh_dang": "0.0",
                },
            },
            {
                "nhan": "Mức liều",
                "o": {"ds": "ds-2", "cot": "khuyen_cao", "theo_tham_so": True},
            },
        ],
        "cong_thuc": "cockcroft_gault",
        "nguon": [
            "tinh:crcl_cg",
            "bang:meropenem",
            creatinin_lab.xet_nghiem_id,
            weight_vital.sinh_hieu_id,
        ],
    }

    return {
        "dac_ta": dac_ta,
        "cong_thuc_hien_thi": {
            "cockcroft_gault": CONG_THUC_HIEN_THI["cockcroft_gault"],
        },
        "bo_du_lieu": [
            {
                "ma": "ds-1",
                "cot": [
                    {"ten": "crcl_tu", "kieu": "dinh_luong", "don_vi": "mL/min"},
                    {"ten": "crcl_den", "kieu": "dinh_luong", "don_vi": "mL/min"},
                    {"ten": "bien_ve_tu", "kieu": "dinh_luong", "don_vi": "mL/min"},
                    {"ten": "bien_ve_den", "kieu": "dinh_luong", "don_vi": "mL/min"},
                    {"ten": "can_chinh", "kieu": "danh_muc", "don_vi": None},
                    {"ten": "khuyen_cao", "kieu": "danh_muc", "don_vi": None},
                ],
                "dong": ds1_rows,
            },
            {
                "ma": "ds-2",
                "cot": [
                    {"ten": "creatinin", "kieu": "dinh_luong", "don_vi": "µmol/L"},
                    {"ten": "loai_can_nang", "kieu": "danh_muc", "don_vi": None},
                    {"ten": "crcl", "kieu": "dinh_luong", "don_vi": "mL/min"},
                    {"ten": "can_chinh", "kieu": "danh_muc", "don_vi": None},
                    {"ten": "khuyen_cao", "kieu": "danh_muc", "don_vi": None},
                ],
                "dong": ds2_rows,
            },
            {
                "ma": "ds-3",
                "cot": [
                    {"ten": "ca_id", "kieu": "danh_muc", "don_vi": None},
                    {"ten": "creatinin", "kieu": "dinh_luong", "don_vi": "µmol/L"},
                    {"ten": "can_nang", "kieu": "dinh_luong", "don_vi": "kg"},
                    {"ten": "loai_can_nang", "kieu": "danh_muc", "don_vi": None},
                    {"ten": "crcl", "kieu": "dinh_luong", "don_vi": "mL/min"},
                    {"ten": "khuyen_cao", "kieu": "danh_muc", "don_vi": None},
                ],
                "dong": ds3_rows,
            },
        ],
    }


def _dedupe_drug_names(raw_names: list[str]) -> list[str]:
    """Khử trùng tên hoạt chất theo khoá chuẩn hoá, giữ nguyên thứ tự đầu tiên."""
    result: list[str] = []
    seen: set[str] = set()
    for name in raw_names:
        cleaned = name.strip()
        key = normalize_key(cleaned)
        if not cleaned or not key or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _order_ingredients_of_case(case: CaBenh) -> list[str]:
    """Lấy danh sách tên hoạt chất duy nhất trong y lệnh hiện tại của một ca."""
    names: list[str] = []
    for line in effective_lines(case):
        for hc in ingredients_of(case, line):
            label = hc.ten_quoc_te or hc.ten_hoat_chat
            if label:
                names.append(label)
    return _dedupe_drug_names(names)


def _all_encounter_ingredients(path: Path) -> tuple[str, list[str]]:
    """Lấy hoạt chất xuất hiện trong mọi y lệnh của một tệp hồ sơ nhiều đợt."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    case_id = str(raw.get("ho_so_id") or path.stem)
    hc_by_id = {
        str(item["hoat_chat_id"]): str(item.get("ten_quoc_te") or item.get("ten_hoat_chat") or "")
        for item in raw.get("danh_muc_hoat_chat") or []
    }
    thuoc_to_hcs: dict[str, list[str]] = {}
    for drug in raw.get("danh_muc_thuoc") or []:
        tid = str(drug.get("thuoc_id") or "")
        thuoc_to_hcs[tid] = [
            hc_by_id[str(tp["hoat_chat_id"])]
            for tp in drug.get("thanh_phan") or []
            if str(tp.get("hoat_chat_id")) in hc_by_id
        ]
    names: list[str] = []
    for encounter in raw.get("dot_dieu_tri") or []:
        for order in encounter.get("y_lenh") or []:
            for line in order.get("chi_tiet") or []:
                tid = line.get("thuoc_id")
                if tid and str(tid) in thuoc_to_hcs:
                    names.extend(thuoc_to_hcs[str(tid)])
    return case_id, _dedupe_drug_names(names)


def _evaluate_interaction_candidate(
    source_label: str,
    drug_names: list[str],
) -> _InteractionCandidate | None:
    """Gọi lookup_interactions cho một danh sách hoạt chất hợp lệ và đếm cặp nặng."""
    if not (_LOOKUP_MIN_DRUGS <= len(drug_names) <= _LOOKUP_MAX_DRUGS):
        return None
    if any(not name or len(name) > 200 for name in drug_names):
        return None
    result = lookup_interactions(drug_names)
    pairs = result.ma_tran.cap
    severe_count = sum(1 for pair in pairs if pair.muc in _SEVERE_INTERACTION_LEVELS)
    warn_count = sum(1 for pair in pairs if pair.muc == "can_luu_y")
    return _InteractionCandidate(
        source_label=source_label,
        drug_names=drug_names,
        result=result,
        severe_count=severe_count,
        warn_count=warn_count,
    )


def _pick_interaction_case() -> tuple[str, list[str], KetQuaTraTuongTac, str, bool]:
    """Ưu tiên ca có cặp nghiêm trọng/chống chỉ định, rồi tới ca có 5–8 hoạt chất."""
    cases = load_source_cases(_ROOT)
    order_candidates: list[_InteractionCandidate] = []
    for case in cases:
        names = _order_ingredients_of_case(case)
        evaluated = _evaluate_interaction_candidate(case.ca_id, names)
        if evaluated is not None:
            order_candidates.append(evaluated)

    single_severe_5_8 = [
        item
        for item in order_candidates
        if item.severe_count >= 1 and 5 <= len(item.drug_names) <= 8
    ]
    if single_severe_5_8:
        single_severe_5_8.sort(
            key=lambda item: (
                -item.severe_count,
                -len(item.drug_names),
                -item.warn_count,
                item.source_label,
            )
        )
        best = single_severe_5_8[0]
        reason = (
            f"ưu tiên ca {best.source_label} có {best.severe_count} cặp "
            f"nghiêm trọng/chống chỉ định và {len(best.drug_names)} hoạt chất trong y lệnh"
        )
        return best.source_label, best.drug_names, best.result, reason, False

    record_candidates: list[_InteractionCandidate] = []
    if _HOSO_DIR.is_dir():
        for path in sorted(_HOSO_DIR.glob("HS-*.json")):
            case_id, names = _all_encounter_ingredients(path)
            if not (5 <= len(names) <= 8):
                continue
            evaluated = _evaluate_interaction_candidate(case_id, names)
            if evaluated is not None:
                record_candidates.append(evaluated)

    record_severe_5_8 = [item for item in record_candidates if item.severe_count >= 1]
    if record_severe_5_8:
        record_severe_5_8.sort(
            key=lambda item: (
                -item.severe_count,
                -len(item.drug_names),
                -item.warn_count,
                item.source_label,
            )
        )
        best = record_severe_5_8[0]
        reason = (
            f"ưu tiên hồ sơ {best.source_label} (gộp các đợt) có {best.severe_count} cặp "
            f"nghiêm trọng/chống chỉ định và {len(best.drug_names)} hoạt chất"
        )
        return best.source_label, best.drug_names, best.result, reason, False

    single_severe_any = [item for item in order_candidates if item.severe_count >= 1]
    if single_severe_any:
        single_severe_any.sort(
            key=lambda item: (
                0 if len(item.drug_names) <= 8 else 1,
                -len(item.drug_names) if len(item.drug_names) <= 8 else len(item.drug_names),
                -item.severe_count,
                -item.warn_count,
                item.source_label,
            )
        )
        best = single_severe_any[0]
        reason = (
            f"ưu tiên ca {best.source_label} có {best.severe_count} cặp "
            f"nghiêm trọng/chống chỉ định ({len(best.drug_names)} hoạt chất trong y lệnh; "
            "không có ca 5–8 hoạt chất nào có cặp nghiêm trọng)"
        )
        return best.source_label, best.drug_names, best.result, reason, False

    # Không có ca nào có cặp nghiêm trọng/chống chỉ định: giữ cách chọn cũ (5–8 hoạt chất).
    order_5_8 = [item for item in order_candidates if 5 <= len(item.drug_names) <= 8]
    if order_5_8:
        order_5_8.sort(key=lambda item: (-len(item.drug_names), item.source_label))
        best = order_5_8[0]
        reason = (
            "không có ca nào có cặp nghiêm trọng/chống chỉ định; "
            f"giữ cách cũ chọn ca {best.source_label} "
            f"({len(best.drug_names)} hoạt chất trong y lệnh)"
        )
        return best.source_label, best.drug_names, best.result, reason, False

    if record_candidates:
        record_candidates.sort(key=lambda item: (-len(item.drug_names), item.source_label))
        best = record_candidates[0]
        reason = (
            "không có ca nào có cặp nghiêm trọng/chống chỉ định; "
            f"giữ cách cũ chọn hồ sơ {best.source_label} ({len(best.drug_names)} hoạt chất)"
        )
        return best.source_label, best.drug_names, best.result, reason, False

    # Dự phòng cuối cùng: gom 6 hoạt chất thật từ các ca tương tác trong data/mock/hoso_gia_lap/.
    case_by_id = {case.ca_id: case for case in cases}
    combined: list[str] = []
    used_cases: list[str] = []
    for cid in _FALLBACK_CASE_IDS:
        case = case_by_id.get(cid)
        if case is None:
            continue
        case_names = _order_ingredients_of_case(case)
        if case_names:
            used_cases.append(cid)
            combined.extend(case_names)
    deduped = _dedupe_drug_names(combined)[:6]
    if len(deduped) < 5:
        for case in cases:
            deduped = _dedupe_drug_names([*deduped, *_order_ingredients_of_case(case)])[:6]
            if len(deduped) >= 6:
                break
    label = f"Gộp y lệnh {', '.join(used_cases)}" if used_cases else "Gộp y lệnh mẫu"
    result = lookup_interactions(deduped)
    reason = (
        "không có ca đơn lẻ nào có cặp nghiêm trọng/chống chỉ định hoặc 5–8 hoạt chất; "
        f"dùng nhánh dự phòng {label} ({len(deduped)} hoạt chất)"
    )
    return label, deduped, result, reason, True


def _sanitize_mechanism(text: str) -> str:
    """Cắt ngắn cơ chế tối đa 200 ký tự và làm sạch khoảng trắng."""
    compact = " ".join(text.split())
    if len(compact) <= _CO_CHE_MAX_LEN:
        return compact
    return compact[: _CO_CHE_MAX_LEN - 1].rstrip() + "…"


def _build_interaction_sample() -> tuple[dict[str, Any], str]:
    """Dựng tệp mẫu 2: ma trận tương tác gọi qua app.api.lookup.lookup_interactions."""
    source_label, _drug_names, result, selection_reason, is_combined = _pick_interaction_case()
    matrix = result.ma_tran

    name_by_id = {row.chi_tiet_y_lenh_id: row.ten for row in matrix.thuoc}
    detail_by_pair = {(min(item.a, item.b), max(item.a, item.b)): item for item in result.chi_tiet}

    ds1_rows: list[dict[str, Any]] = []
    count_major = 0
    count_warn = 0
    for pair in matrix.cap:
        thuoc_a = name_by_id.get(pair.a, pair.a)
        thuoc_b = name_by_id.get(pair.b, pair.b)
        muc_do = pair.muc
        if muc_do in _SEVERE_INTERACTION_LEVELS:
            count_major += 1
        elif muc_do == "can_luu_y":
            count_warn += 1

        detail = detail_by_pair.get((min(pair.a, pair.b), max(pair.a, pair.b)))
        raw_desc = (
            pair.tom_tat
            or pair.ly_do
            or (detail.mo_ta if detail is not None else None)
            or (
                "Không phát hiện tương tác trong DDInter"
                if muc_do == "khong_phat_hien"
                else "Chưa có mô tả cơ chế"
            )
        )
        slug_a = normalize_key(thuoc_a).replace(" ", "_")
        slug_b = normalize_key(thuoc_b).replace(" ", "_")
        ds1_rows.append(
            {
                "thuoc_a": thuoc_a,
                "thuoc_b": thuoc_b,
                "muc_do": muc_do,
                "co_che": _sanitize_mechanism(raw_desc),
                "ma_can_cu": f"ddinter:{slug_a}_{slug_b}",
            }
        )

    ds2_rows: list[dict[str, Any]] = [
        {
            "nguon_ca": source_label,
            "so_thuoc": len(matrix.thuoc),
            "so_cap": len(ds1_rows),
            "so_nghiem_trong": count_major,
            "so_can_luu_y": count_warn,
        }
    ]

    dac_ta: dict[str, Any] = {
        "phien_ban": "mh-0",
        "tieu_de": "Ma trận tương tác thuốc",
        "phu_de": [
            {"o": {"ds": "ds-2", "cot": "nguon_ca", "dong": 0}},
            {"chu": " · "},
            {"o": {"ds": "ds-2", "cot": "so_thuoc", "dong": 0}},
            {"chu": " hoạt chất · "},
            {"o": {"ds": "ds-2", "cot": "so_cap", "dong": 0}},
            {"chu": " cặp"},
        ],
        "lop": [
            {
                "dau": "o",
                "du_lieu": "ds-1",
                "loc": [{"cot": "muc_do", "trong_tham_so": "loc_muc"}],
                "ma_hoa": {
                    "x": {"cot": "thuoc_a", "kieu": "danh_muc"},
                    "y": {"cot": "thuoc_b", "kieu": "danh_muc"},
                    "mau": {"cot": "muc_do"},
                    "nhan": {"cot": "co_che"},
                    "can_cu": {"cot": "ma_can_cu"},
                },
            }
        ],
        "truc": {
            "x": {"tieu_de": "Thuốc A", "mien": "tu_du_lieu"},
            "y": {"tieu_de": "Thuốc B", "mien": "tu_du_lieu"},
        },
        "tham_so": [
            {
                "ma": "loc_muc",
                "loai": "loc",
                "nhan": "Lọc theo mức độ",
                "gia_tri_tu": {"ds": "ds-1", "cot": "muc_do"},
            },
            {
                "loai": "dat_lai",
                "nhan": "Hiện tất cả",
            },
        ],
        "so_hien": [
            {"nhan": "Tổng số cặp", "o": {"ds": "ds-2", "cot": "so_cap", "dong": 0}},
            {"nhan": "Nghiêm trọng", "o": {"ds": "ds-2", "cot": "so_nghiem_trong", "dong": 0}},
            {"nhan": "Cần lưu ý", "o": {"ds": "ds-2", "cot": "so_can_luu_y", "dong": 0}},
        ],
        "nguon": ["ddinter:2.0", "tra_cuu:hoat_chat"],
    }

    payload: dict[str, Any] = {
        "dac_ta": dac_ta,
        "bo_du_lieu": [
            {
                "ma": "ds-1",
                "cot": [
                    {"ten": "thuoc_a", "kieu": "danh_muc", "don_vi": None},
                    {"ten": "thuoc_b", "kieu": "danh_muc", "don_vi": None},
                    {"ten": "muc_do", "kieu": "danh_muc", "don_vi": None},
                    {"ten": "co_che", "kieu": "danh_muc", "don_vi": None},
                    {"ten": "ma_can_cu", "kieu": "danh_muc", "don_vi": None},
                ],
                "dong": ds1_rows,
            },
            {
                "ma": "ds-2",
                "cot": [
                    {"ten": "nguon_ca", "kieu": "danh_muc", "don_vi": None},
                    {"ten": "so_thuoc", "kieu": "dinh_luong", "don_vi": "hoạt chất"},
                    {"ten": "so_cap", "kieu": "dinh_luong", "don_vi": "cặp"},
                    {"ten": "so_nghiem_trong", "kieu": "dinh_luong", "don_vi": "cặp"},
                    {"ten": "so_can_luu_y", "kieu": "dinh_luong", "don_vi": "cặp"},
                ],
                "dong": ds2_rows,
            },
        ],
    }
    if is_combined:
        payload["ghi_chu_nguon"] = (
            "Không có ca đơn lẻ nào trong data/mock/ có từ 5 đến 8 hoạt chất trong y lệnh; "
            "đã gộp 6 hoạt chất thật từ các ca mock tương tác."
        )
    return payload, selection_reason


def _deterministic_int(key: str, low: int, high: int) -> int:
    """Sinh số nguyên giả lập ổn định theo khoá và seed cố định (không dùng random)."""
    digest = hashlib.sha256(f"{_SYNTHETIC_SEED}:{key}".encode()).digest()
    raw = int.from_bytes(digest[:4], "big")
    return low + (raw % (high - low + 1))


def _build_monthly_stats_sample() -> dict[str, Any]:
    """Dựng tệp mẫu 3: thống kê giả lập 30 ngày theo 4 khoa giả định."""
    departments: tuple[tuple[str, int, int], ...] = (
        ("Khoa A", 18, 34),
        ("Khoa B", 12, 26),
        ("Khoa C", 8, 20),
        ("Khoa D", 5, 15),
    )
    end_date = dt.date(2026, 11, 26)
    days = [end_date - dt.timedelta(days=offset) for offset in range(29, -1, -1)]

    ds1_rows: list[dict[str, Any]] = []
    totals: dict[str, int] = {name: 0 for name, _, _ in departments}

    for day in days:
        weekend_shift = -4 if day.weekday() >= 5 else 0
        iso_day = day.isoformat()
        for dept_name, low, high in departments:
            base = _deterministic_int(f"{iso_day}:{dept_name}", low, high)
            value = max(2, base + weekend_shift)
            totals[dept_name] += value
            ds1_rows.append(
                {
                    "ngay": iso_day,
                    "khoa": dept_name,
                    "so_y_lenh": value,
                }
            )

    ds2_rows: list[dict[str, Any]] = [
        {
            "khoa": dept_name,
            "tong_y_lenh": totals[dept_name],
            "trung_binh_ngay": totals[dept_name] / float(len(days)),
        }
        for dept_name, _, _ in departments
    ]

    grand_total = sum(totals.values())
    top_dept = max(totals.items(), key=lambda item: item[1])[0]
    ds3_rows: list[dict[str, Any]] = [
        {
            "so_ngay": len(days),
            "tong_tat_ca": grand_total,
            "khoa_cao_nhat": top_dept,
        }
    ]

    dac_ta_duong: dict[str, Any] = {
        "phien_ban": "mh-0",
        "tieu_de": "Y lệnh cần thẩm định theo ngày",
        "phu_de": [
            {"chu": "Dữ liệu giả lập để xem mẫu · "},
            {"o": {"ds": "ds-3", "cot": "so_ngay", "dong": 0}},
            {"chu": " ngày"},
        ],
        "lop": [
            {
                "dau": "duong",
                "du_lieu": "ds-1",
                "loc": [{"cot": "khoa", "trong_tham_so": "chon_khoa"}],
                "ma_hoa": {
                    "x": {"cot": "ngay", "kieu": "thoi_gian"},
                    "y": {"cot": "so_y_lenh", "kieu": "dinh_luong"},
                    "mau": {"cot": "khoa"},
                    "nhom": {"cot": "khoa"},
                },
            },
            {
                "dau": "diem",
                "du_lieu": "ds-1",
                "loc": [{"cot": "khoa", "trong_tham_so": "chon_khoa"}],
                "ma_hoa": {
                    "x": {"cot": "ngay", "kieu": "thoi_gian"},
                    "y": {"cot": "so_y_lenh", "kieu": "dinh_luong"},
                    "mau": {"cot": "khoa"},
                    "nhom": {"cot": "khoa"},
                },
            },
        ],
        "truc": {
            "x": {"tieu_de": "Ngày", "mien": "tu_du_lieu"},
            "y": {"tieu_de": "Số y lệnh", "mien": "tu_0"},
        },
        "tham_so": [
            {
                "ma": "chon_khoa",
                "loai": "bat_tat",
                "nhan": "Khoa hiển thị",
                "gia_tri_tu": {"ds": "ds-1", "cot": "khoa"},
            },
            {
                "loai": "dat_lai",
                "nhan": "Bật tất cả khoa",
            },
        ],
        "so_hien": [
            {"nhan": "Tổng y lệnh", "o": {"ds": "ds-3", "cot": "tong_tat_ca", "dong": 0}},
            {"nhan": "Khoa cao nhất", "o": {"ds": "ds-3", "cot": "khoa_cao_nhat", "dong": 0}},
        ],
        "nguon": ["gia_lap:thong_ke_thang"],
    }

    dac_ta_cot: dict[str, Any] = {
        "phien_ban": "mh-0",
        "tieu_de": "Tổng y lệnh cần thẩm định theo khoa",
        "phu_de": [
            {"chu": "Dữ liệu giả lập để xem mẫu"},
        ],
        "lop": [
            {
                "dau": "cot",
                "du_lieu": "ds-2",
                "loc": [{"cot": "khoa", "trong_tham_so": "chon_khoa"}],
                "ma_hoa": {
                    "x": {"cot": "khoa", "kieu": "danh_muc"},
                    "y": {"cot": "tong_y_lenh", "kieu": "dinh_luong"},
                    "mau": {"cot": "khoa"},
                },
            }
        ],
        "truc": {
            "x": {"tieu_de": "Khoa", "mien": "tu_du_lieu"},
            "y": {"tieu_de": "Tổng số y lệnh", "mien": "tu_0"},
        },
        "tham_so": [
            {
                "ma": "chon_khoa",
                "loai": "bat_tat",
                "nhan": "Khoa hiển thị",
                "gia_tri_tu": {"ds": "ds-2", "cot": "khoa"},
            },
            {
                "loai": "dat_lai",
                "nhan": "Bật tất cả khoa",
            },
        ],
        "so_hien": [
            {"nhan": "Tổng y lệnh", "o": {"ds": "ds-3", "cot": "tong_tat_ca", "dong": 0}},
            {"nhan": "Khoa cao nhất", "o": {"ds": "ds-3", "cot": "khoa_cao_nhat", "dong": 0}},
        ],
        "nguon": ["gia_lap:thong_ke_thang"],
    }

    return {
        "gia_lap": True,
        "dac_ta": [dac_ta_duong, dac_ta_cot],
        "bo_du_lieu": [
            {
                "ma": "ds-1",
                "cot": [
                    {"ten": "ngay", "kieu": "thoi_gian", "don_vi": None},
                    {"ten": "khoa", "kieu": "danh_muc", "don_vi": None},
                    {"ten": "so_y_lenh", "kieu": "dinh_luong", "don_vi": "y lệnh"},
                ],
                "dong": ds1_rows,
            },
            {
                "ma": "ds-2",
                "cot": [
                    {"ten": "khoa", "kieu": "danh_muc", "don_vi": None},
                    {"ten": "tong_y_lenh", "kieu": "dinh_luong", "don_vi": "y lệnh"},
                    {"ten": "trung_binh_ngay", "kieu": "dinh_luong", "don_vi": "y lệnh/ngày"},
                ],
                "dong": ds2_rows,
            },
            {
                "ma": "ds-3",
                "cot": [
                    {"ten": "so_ngay", "kieu": "dinh_luong", "don_vi": "ngày"},
                    {"ten": "tong_tat_ca", "kieu": "dinh_luong", "don_vi": "y lệnh"},
                    {"ten": "khoa_cao_nhat", "kieu": "danh_muc", "don_vi": None},
                ],
                "dong": ds3_rows,
            },
        ],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Ghi tệp JSON UTF-8 dễ đọc với xuống dòng cuối tệp."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def _print_summary(file_name: str, payload: dict[str, Any], reason: str | None = None) -> None:
    """In số dòng từng bộ dữ liệu của tệp vừa xuất và lý do chọn ca nếu có."""
    parts = [f"{ds['ma']}={len(ds['dong'])} dòng" for ds in payload["bo_du_lieu"]]
    note = payload.get("ghi_chu_nguon")
    suffix = f" ({note})" if note else ""
    print(f"{file_name}: {', '.join(parts)}{suffix}")
    if reason:
        print(f"  Lý do chọn ca: {reason}")


def main() -> int:
    """Xuất đủ 3 tệp mẫu vào thư mục web/src/features/minh-hoa/mau/."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")

    interaction_payload, interaction_reason = _build_interaction_sample()
    outputs: list[tuple[str, dict[str, Any], str | None]] = [
        ("lieu-meropenem-crcl.json", _build_meropenem_sample(), None),
        ("ma-tran-tuong-tac.json", interaction_payload, interaction_reason),
        ("thong-ke-thang.json", _build_monthly_stats_sample(), None),
    ]
    for file_name, payload, reason in outputs:
        _write_json(_OUT_DIR / file_name, payload)
        _print_summary(file_name, payload, reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
