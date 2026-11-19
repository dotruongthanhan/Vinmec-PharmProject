"""Xây dựng kho tri thức tương tác thuốc – thuốc (tuong_tac.jsonl) nối DDInter 2.0 và openFDA."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

from app.core.types import Chunk
from app.kb.build import load_chunks
from app.kb.names import DrugNameIndex
from app.kb.sources.ddinter_index import (
    DdinterPair,
    IngredientBridge,
    build_ingredient_bridge,
    load_ddinter_pairs,
)
from app.rules.interaction import (
    DdinterLevel,
    InteractionBook,
    InteractionRecord,
    InteractionSeverity,
)

DEFAULT_DDINTER_DIR = Path("data/kb_sources/ddinter")
DEFAULT_CHUNKS_PATH = Path("data/kb_curated/chunks.jsonl")
DEFAULT_NAMES_PATH = Path("data/kb/hoat_chat.json")
DEFAULT_OPENFDA_DIR = Path("data/kb_sources/openfda")
DEFAULT_OUT_PATH = Path("data/kb_curated/tuong_tac.jsonl")
DEFAULT_REPORTS_DIR = Path("data/kb_reports")

_DDINTER_TO_SEVERITY: dict[DdinterLevel, InteractionSeverity] = {
    "Major": "nghiem_trong",
    "Moderate": "trung_binh",
    "Minor": "nhe",
    "Unknown": "chua_ro",
}
_LEVEL_RANK: dict[DdinterLevel, int] = {
    "Major": 4,
    "Moderate": 3,
    "Minor": 2,
    "Unknown": 1,
}
_TARGET_SECTIONS = ("tuong_tac", "chong_chi_dinh", "can_bao")
_SECTION_PRIORITY = {"tuong_tac": 0, "chong_chi_dinh": 1, "can_bao": 2}


def _short_id(hoat_chat_id: str) -> str:
    """Rút gọn tiền tố HC- để ghép tuong_tac_id ổn định."""
    return hoat_chat_id.removeprefix("HC-")


def _build_synonym_matchers(
    names: DrugNameIndex,
    hc_ids: list[str],
) -> dict[str, re.Pattern[str]]:
    """Tạo regex khớp nguyên từ (không phân biệt hoa thường) cho mọi tên/biệt dược của hoạt chất."""
    matchers: dict[str, re.Pattern[str]] = {}
    for hc_id in hc_ids:
        terms = names.synonyms_for(hc_id)
        if not terms:
            continue
        sorted_terms = sorted(set(terms), key=len, reverse=True)
        escaped = "|".join(re.escape(term) for term in sorted_terms)
        matchers[hc_id] = re.compile(rf"(?<![a-z0-9])(?:{escaped})(?![a-z0-9])", re.IGNORECASE)
    return matchers


def _index_target_chunks(chunks: list[Chunk]) -> dict[str, list[Chunk]]:
    """Lập chỉ mục các đoạn openFDA mục tương tác / chống chỉ định / cảnh báo theo hoạt chất."""
    by_hc: dict[str, list[Chunk]] = {}
    filtered = [c for c in chunks if c.muc in _TARGET_SECTIONS]
    filtered.sort(key=lambda c: (_SECTION_PRIORITY.get(c.muc, 9), c.doan_trich_id))
    for chunk in filtered:
        for hc_id in chunk.hoat_chat_ids:
            by_hc.setdefault(hc_id, []).append(chunk)
    return by_hc


def _find_fda_citations(
    hc_a_id: str,
    hc_b_id: str,
    chunks_by_hc: dict[str, list[Chunk]],
    matchers: dict[str, re.Pattern[str]],
) -> list[str]:
    """Tìm các doan_trich_id openFDA của A nhắc đến B hoặc ngược lại."""
    hits: list[tuple[int, str]] = []
    seen: set[str] = set()

    matcher_b = matchers.get(hc_b_id)
    if matcher_b is not None:
        for chunk in chunks_by_hc.get(hc_a_id, ()):
            if chunk.doan_trich_id not in seen and matcher_b.search(chunk.noi_dung_goc):
                seen.add(chunk.doan_trich_id)
                hits.append((_SECTION_PRIORITY.get(chunk.muc, 9), chunk.doan_trich_id))

    matcher_a = matchers.get(hc_a_id)
    if matcher_a is not None:
        for chunk in chunks_by_hc.get(hc_b_id, ()):
            if chunk.doan_trich_id not in seen and matcher_a.search(chunk.noi_dung_goc):
                seen.add(chunk.doan_trich_id)
                hits.append((_SECTION_PRIORITY.get(chunk.muc, 9), chunk.doan_trich_id))

    hits.sort(key=lambda item: (item[0], item[1]))
    return [chunk_id for _, chunk_id in hits]


def _merge_list_unique(base: list[str], extra: list[str]) -> list[str]:
    """Gộp hai danh sách giữ nguyên thứ tự và loại trùng."""
    seen = set(base)
    out = list(base)
    for item in extra:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _display_name(names: DrugNameIndex, hc_id: str) -> str:
    """Lấy tên chuẩn hiển thị của hoạt chất (viết hoa chữ cái đầu nếu ở dạng thường)."""
    inn = names.inn_names([hc_id])[0] or hc_id
    return inn[:1].upper() + inn[1:] if inn else hc_id


def _ordered_pair_for_hc(
    pair: DdinterPair,
    hc_1: str,
    hc_2: str,
    dd_1: str,
    dd_2: str,
) -> tuple[str, str, str, str]:
    """Đảm bảo cặp (hc_a_id, hc_b_id) sắp xếp tăng dần và (dd_a, dd_b) tương ứng đúng."""
    if hc_1 <= hc_2:
        return hc_1, hc_2, dd_1, dd_2
    return hc_2, hc_1, dd_2, dd_1


def build_interactions(
    *,
    ddinter_dir: Path = DEFAULT_DDINTER_DIR,
    chunks_path: Path = DEFAULT_CHUNKS_PATH,
    names_path: Path = DEFAULT_NAMES_PATH,
    openfda_dir: Path | None = DEFAULT_OPENFDA_DIR,
    out_path: Path = DEFAULT_OUT_PATH,
    reports_dir: Path | None = DEFAULT_REPORTS_DIR,
) -> tuple[InteractionBook, IngredientBridge, dict[str, object]]:
    """Hợp nhất DDInter 2.0 với danh mục hoạt chất và nhãn openFDA thành tuong_tac.jsonl."""
    names = DrugNameIndex.load(names_path)
    pairs, ddinter_names, file_counts = load_ddinter_pairs(ddinter_dir)
    bridge = build_ingredient_bridge(names, ddinter_names, openfda_dir=openfda_dir)

    chunks = load_chunks(chunks_path) if Path(chunks_path).is_file() else []
    chunks_by_hc = _index_target_chunks(chunks)
    matchers = _build_synonym_matchers(names, names.single_ingredient_ids())

    merged: dict[tuple[str, str], dict[str, object]] = {}
    for pair in pairs:
        hc_list_1 = bridge.hoat_chat_by_ddinter.get(pair.ddinter_id_1, [])
        hc_list_2 = bridge.hoat_chat_by_ddinter.get(pair.ddinter_id_2, [])
        if not hc_list_1 or not hc_list_2:
            continue

        for hc_1, hc_2 in product(hc_list_1, hc_list_2):
            if hc_1 == hc_2:
                continue
            hc_a, hc_b, dd_a, dd_b = _ordered_pair_for_hc(
                pair,
                hc_1,
                hc_2,
                pair.ddinter_id_1,
                pair.ddinter_id_2,
            )
            key = (hc_a, hc_b)
            existing = merged.get(key)
            if existing is None:
                merged[key] = {
                    "hc_a": hc_a,
                    "hc_b": hc_b,
                    "dd_a": dd_a,
                    "dd_b": dd_b,
                    "level": pair.level,
                    "co_muc_lech": pair.co_muc_lech,
                    "interaction_id": pair.interaction_id,
                    "mechanism": list(pair.mechanism),
                    "interaction_text": pair.interaction_text,
                    "management_text": pair.management_text,
                    "references": list(pair.references),
                }
                continue

            if pair.level != existing["level"]:
                existing["co_muc_lech"] = True
            if pair.co_muc_lech:
                existing["co_muc_lech"] = True
            if _LEVEL_RANK[pair.level] > _LEVEL_RANK[existing["level"]]:  # type: ignore[index]
                existing["level"] = pair.level
                if pair.interaction_id:
                    existing["interaction_id"] = pair.interaction_id
            elif not existing["interaction_id"] and pair.interaction_id:
                existing["interaction_id"] = pair.interaction_id

            existing["mechanism"] = _merge_list_unique(
                existing["mechanism"],  # type: ignore[arg-type]
                pair.mechanism,
            )
            existing["references"] = _merge_list_unique(
                existing["references"],  # type: ignore[arg-type]
                pair.references,
            )
            if not existing["interaction_text"] and pair.interaction_text:
                existing["interaction_text"] = pair.interaction_text
            if not existing["management_text"] and pair.management_text:
                existing["management_text"] = pair.management_text

    records: list[InteractionRecord] = []
    for hc_a, hc_b in sorted(merged):
        item = merged[(hc_a, hc_b)]
        level: DdinterLevel = item["level"]  # type: ignore[assignment]
        fda_chunks = _find_fda_citations(hc_a, hc_b, chunks_by_hc, matchers)
        records.append(
            InteractionRecord(
                tuong_tac_id=f"TT-{_short_id(hc_a)}-{_short_id(hc_b)}",
                hoat_chat_a_id=hc_a,
                hoat_chat_b_id=hc_b,
                ten_hoat_chat_a=_display_name(names, hc_a),
                ten_hoat_chat_b=_display_name(names, hc_b),
                ddinter_id_a=str(item["dd_a"]),
                ddinter_id_b=str(item["dd_b"]),
                ddinter_interaction_id=item["interaction_id"],  # type: ignore[arg-type]
                muc_do_ddinter=level,
                muc_do=_DDINTER_TO_SEVERITY[level],
                co_che=list(item["mechanism"]),  # type: ignore[arg-type]
                mo_ta_lam_sang=item["interaction_text"],  # type: ignore[arg-type]
                xu_tri=item["management_text"],  # type: ignore[arg-type]
                tai_lieu_ddinter=list(item["references"]),  # type: ignore[arg-type]
                trich_dan_nhan_fda=fda_chunks,
                nguon_chinh="DDInter 2.0",
                tang_tin_cay=3 if level == "Unknown" else 4,
                trang_thai="sang_loc",
                co_muc_lech_ddinter=bool(item["co_muc_lech"]),
            )
        )

    book = InteractionBook(tuong_tac=records)
    resolved_out = Path(out_path)
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = resolved_out.with_suffix(".jsonl.tmp")
    lines = [rec.model_dump_json() for rec in records]
    tmp_out.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
    os.replace(tmp_out, resolved_out)

    sev_counts = Counter(rec.muc_do for rec in records)
    ddinter_level_counts = Counter(rec.muc_do_ddinter for rec in records)
    report: dict[str, object] = {
        "thoi_diem_tao": datetime.now(UTC).isoformat(),
        "raw_csv_files": len(file_counts),
        "raw_csv_rows": sum(file_counts.values()),
        "unique_ddinter_drugs": len(ddinter_names),
        "unique_ddinter_pairs": len(pairs),
        "matched_hoat_chat": len(bridge.ddinter_by_hoat_chat),
        "unmatched_hoat_chat": bridge.unmatched_hoat_chat,
        "in_scope_ddinter_ids": len(bridge.in_scope_ddinter_ids),
        "pairs_built": len(records),
        "by_severity": dict(sorted(sev_counts.items())),
        "by_ddinter_level": dict(sorted(ddinter_level_counts.items())),
        "pairs_with_interaction_id": sum(1 for r in records if r.ddinter_interaction_id),
        "pairs_with_clinical_text": sum(1 for r in records if r.mo_ta_lam_sang),
        "pairs_with_management": sum(1 for r in records if r.xu_tri),
        "pairs_with_references": sum(1 for r in records if r.tai_lieu_ddinter),
        "pairs_with_fda_citations": sum(1 for r in records if r.trich_dan_nhan_fda),
        "out_path": str(resolved_out),
    }

    if reports_dir is not None:
        resolved_rep = Path(reports_dir)
        resolved_rep.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        rep_path = resolved_rep / f"interactions_{stamp}.json"
        rep_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report["report_path"] = str(rep_path)

    return book, bridge, report


def main() -> int:
    """Điểm vào CLI tạo data/kb_curated/tuong_tac.jsonl và báo cáo tổng hợp."""
    parser = argparse.ArgumentParser(
        description="Tạo kho tri thức tương tác thuốc tuong_tac.jsonl từ DDInter 2.0 và openFDA."
    )
    parser.add_argument("--ddinter-dir", type=Path, default=DEFAULT_DDINTER_DIR)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--names", type=Path, default=DEFAULT_NAMES_PATH)
    parser.add_argument("--openfda-dir", type=Path, default=DEFAULT_OPENFDA_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_PATH)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    args = parser.parse_args()

    _, _, report = build_interactions(
        ddinter_dir=args.ddinter_dir,
        chunks_path=args.chunks,
        names_path=args.names,
        openfda_dir=args.openfda_dir,
        out_path=args.out,
        reports_dir=args.reports_dir,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
