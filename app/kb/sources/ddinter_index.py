"""Đọc, chuẩn hóa và nối danh mục tương tác thuốc DDInter 2.0 với hoạt chất chuẩn."""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.kb.names import DrugNameIndex, normalize_key, strip_salt

LevelType = Literal["Major", "Moderate", "Minor", "Unknown"]

BASE_COLUMNS: tuple[str, ...] = ("DDInterID_A", "Drug_A", "DDInterID_B", "Drug_B", "Level")
ENRICHED_COLUMNS: tuple[str, ...] = (
    "InteractionID",
    "Mechanism",
    "Interaction",
    "Management",
    "References",
)
ALL_CSV_COLUMNS: tuple[str, ...] = (*BASE_COLUMNS, *ENRICHED_COLUMNS)

_LEVEL_RANK: dict[LevelType, int] = {
    "Major": 4,
    "Moderate": 3,
    "Minor": 2,
    "Unknown": 1,
}
_ATC_CODE_RE = re.compile(r"^[A-Z]\d{2}[A-Z](?:\d{2})?$")


def canonical_pair_key(ddinter_id_a: str, ddinter_id_b: str) -> tuple[str, str, str]:
    """Trả về cặp mã DDInter theo thứ tự chuẩn (nhỏ trước, lớn sau) và khóa gộp."""
    if ddinter_id_a <= ddinter_id_b:
        return ddinter_id_a, ddinter_id_b, f"{ddinter_id_a}::{ddinter_id_b}"
    return ddinter_id_b, ddinter_id_a, f"{ddinter_id_b}::{ddinter_id_a}"


def _parse_list_cell(raw: str | None, *, sep: str, drop_atc: bool = False) -> list[str]:
    """Tách cột danh sách lưu trong CSV (hỗ trợ cả JSON array hoặc phân tách theo sep)."""
    text = (raw or "").strip()
    if not text or text.lower() in ("-", "none", "n/a"):
        return []
    if text.startswith("["):
        try:
            loaded = json.loads(text)
            if isinstance(loaded, list):
                items = [
                    str(item).strip()
                    for item in loaded
                    if str(item).strip() and str(item).strip().lower() not in ("-", "none", "n/a")
                ]
                return (
                    [item for item in items if not _ATC_CODE_RE.match(item)] if drop_atc else items
                )
        except json.JSONDecodeError:
            pass
    parts = [part.strip() for part in text.split(sep)]
    items = [part for part in parts if part and part.lower() not in ("-", "none", "n/a")]
    return [item for item in items if not _ATC_CODE_RE.match(item)] if drop_atc else items


def _clean_opt_text(raw: str | None) -> str | None:
    """Làm sạch ô văn bản tùy chọn trong CSV, coi '-', 'None' hoặc rỗng là None."""
    text = (raw or "").strip()
    if not text or text.lower() in ("-", "none", "n/a"):
        return None
    return text


class DdinterRow(BaseModel):
    """Một dòng thô từ tệp CSV DDInter (5 cột gốc hoặc 10 cột đã làm giàu)."""

    model_config = ConfigDict(extra="forbid")

    ddinter_id_a: str
    drug_a: str
    ddinter_id_b: str
    drug_b: str
    level: LevelType
    interaction_id: str | None = None
    mechanism: list[str] = Field(default_factory=list)
    interaction_text: str | None = None
    management_text: str | None = None
    references: list[str] = Field(default_factory=list)


class DdinterPair(BaseModel):
    """Một cặp tương tác vô hướng đã gộp trùng từ 14 tệp ATC của DDInter."""

    model_config = ConfigDict(extra="forbid")

    pair_key: str
    ddinter_id_1: str
    drug_1: str
    ddinter_id_2: str
    drug_2: str
    level: LevelType
    co_muc_lech: bool = False
    source_files: list[str] = Field(default_factory=list)
    interaction_id: str | None = None
    mechanism: list[str] = Field(default_factory=list)
    interaction_text: str | None = None
    management_text: str | None = None
    references: list[str] = Field(default_factory=list)


class IngredientBridge(BaseModel):
    """Cầu nối giữa hoạt chất chuẩn hoá (openFDA) và mã thuốc DDInter 2.0."""

    model_config = ConfigDict(extra="forbid")

    ddinter_by_hoat_chat: dict[str, list[str]]
    hoat_chat_by_ddinter: dict[str, list[str]]
    ddinter_names: dict[str, str]
    rxcui_by_hoat_chat: dict[str, list[str]] = Field(default_factory=dict)
    epc_by_hoat_chat: dict[str, list[str]] = Field(default_factory=dict)
    unmatched_hoat_chat: list[str] = Field(default_factory=list)
    in_scope_ddinter_ids: list[str] = Field(default_factory=list)


def iter_ddinter_csv_paths(ddinter_dir: Path) -> list[Path]:
    """Liệt kê có thứ tự các tệp CSV nguồn DDInter theo mã ATC."""
    return sorted(Path(ddinter_dir).glob("ddinter_downloads_code_*.csv"))


def _parse_csv_row(raw: Mapping[str, str]) -> DdinterRow:
    """Chuyển một dòng DictReader từ CSV DDInter sang DdinterRow."""
    level_raw = (raw.get("Level") or "Unknown").strip()
    level: LevelType = level_raw if level_raw in _LEVEL_RANK else "Unknown"  # type: ignore[assignment]
    return DdinterRow(
        ddinter_id_a=(raw["DDInterID_A"] or "").strip(),
        drug_a=(raw["Drug_A"] or "").strip(),
        ddinter_id_b=(raw["DDInterID_B"] or "").strip(),
        drug_b=(raw["Drug_B"] or "").strip(),
        level=level,
        interaction_id=_clean_opt_text(raw.get("InteractionID")),
        mechanism=_parse_list_cell(raw.get("Mechanism"), sep=";", drop_atc=True),
        interaction_text=_clean_opt_text(raw.get("Interaction")),
        management_text=_clean_opt_text(raw.get("Management")),
        references=_parse_list_cell(raw.get("References"), sep="\n"),
    )


def load_ddinter_rows(ddinter_dir: Path) -> tuple[list[tuple[str, DdinterRow]], dict[str, int]]:
    """Đọc toàn bộ dòng từ các tệp CSV DDInter (hỗ trợ cả 5 cột và 10 cột)."""
    paths = iter_ddinter_csv_paths(ddinter_dir)
    if not paths:
        raise FileNotFoundError(f"Không tìm thấy tệp CSV DDInter nào trong {ddinter_dir}")
    rows: list[tuple[str, DdinterRow]] = []
    counts: dict[str, int] = {}
    for path in paths:
        file_count = 0
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                counts[path.name] = 0
                continue
            missing_cols = [col for col in BASE_COLUMNS if col not in reader.fieldnames]
            if missing_cols:
                raise ValueError(f"Tệp {path.name} thiếu cột bắt buộc: {missing_cols}")
            for raw in reader:
                rows.append((path.name, _parse_csv_row(raw)))
                file_count += 1
        counts[path.name] = file_count
    return rows, counts


def dedupe_ddinter_pairs(
    rows_with_file: Iterable[tuple[str, DdinterRow]],
) -> tuple[list[DdinterPair], dict[str, str]]:
    """Gộp các cặp A-B / B-A và trùng lặp giữa 14 tệp, giữ mức nghiêm trọng cao nhất."""
    drug_names: dict[str, str] = {}
    buckets: dict[str, dict[str, object]] = {}

    for filename, row in rows_with_file:
        if row.ddinter_id_a and row.drug_a:
            drug_names.setdefault(row.ddinter_id_a, row.drug_a)
        if row.ddinter_id_b and row.drug_b:
            drug_names.setdefault(row.ddinter_id_b, row.drug_b)

        id1, id2, key = canonical_pair_key(row.ddinter_id_a, row.ddinter_id_b)
        name1 = row.drug_a if id1 == row.ddinter_id_a else row.drug_b
        name2 = row.drug_b if id2 == row.ddinter_id_b else row.drug_a

        entry = buckets.get(key)
        if entry is None:
            buckets[key] = {
                "pair_key": key,
                "ddinter_id_1": id1,
                "drug_1": drug_names.get(id1, name1),
                "ddinter_id_2": id2,
                "drug_2": drug_names.get(id2, name2),
                "level": row.level,
                "levels": {row.level},
                "source_files": {filename},
                "interaction_id": row.interaction_id,
                "mechanism": list(row.mechanism),
                "interaction_text": row.interaction_text,
                "management_text": row.management_text,
                "references": list(row.references),
            }
            continue

        levels = entry["levels"]
        assert isinstance(levels, set)
        levels.add(row.level)
        if _LEVEL_RANK[row.level] > _LEVEL_RANK[entry["level"]]:  # type: ignore[index]
            entry["level"] = row.level
        source_files = entry["source_files"]
        assert isinstance(source_files, set)
        source_files.add(filename)

        if not entry["interaction_id"] and row.interaction_id:
            entry["interaction_id"] = row.interaction_id
        if not entry["mechanism"] and row.mechanism:
            entry["mechanism"] = list(row.mechanism)
        if not entry["interaction_text"] and row.interaction_text:
            entry["interaction_text"] = row.interaction_text
        if not entry["management_text"] and row.management_text:
            entry["management_text"] = row.management_text
        if not entry["references"] and row.references:
            entry["references"] = list(row.references)

    pairs: list[DdinterPair] = []
    for key in sorted(buckets):
        item = buckets[key]
        levels = item["levels"]
        source_files = item["source_files"]
        assert isinstance(levels, set)
        assert isinstance(source_files, set)
        pairs.append(
            DdinterPair(
                pair_key=str(item["pair_key"]),
                ddinter_id_1=str(item["ddinter_id_1"]),
                drug_1=str(item["drug_1"]),
                ddinter_id_2=str(item["ddinter_id_2"]),
                drug_2=str(item["drug_2"]),
                level=item["level"],  # type: ignore[arg-type]
                co_muc_lech=len(levels) > 1,
                source_files=sorted(source_files),
                interaction_id=item["interaction_id"],  # type: ignore[arg-type]
                mechanism=list(item["mechanism"]),  # type: ignore[arg-type]
                interaction_text=item["interaction_text"],  # type: ignore[arg-type]
                management_text=item["management_text"],  # type: ignore[arg-type]
                references=list(item["references"]),  # type: ignore[arg-type]
            )
        )
    return pairs, drug_names


def load_ddinter_pairs(
    ddinter_dir: Path,
) -> tuple[list[DdinterPair], dict[str, str], dict[str, int]]:
    """Đọc toàn bộ thư mục DDInter và trả về các cặp đã gộp, từ điển tên và số dòng mỗi tệp."""
    rows, file_counts = load_ddinter_rows(ddinter_dir)
    pairs, drug_names = dedupe_ddinter_pairs(rows)
    return pairs, drug_names, file_counts


def _extract_openfda_metadata(
    names: DrugNameIndex,
    openfda_dir: Path | None,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Trích RxCUI và nhóm dược lý EPC từ nhãn openFDA cho từng hoạt chất."""
    rxcui_by_hc: dict[str, set[str]] = {}
    epc_by_hc: dict[str, set[str]] = {}
    if openfda_dir is None or not Path(openfda_dir).is_dir():
        return {}, {}

    for json_path in sorted(Path(openfda_dir).glob("*.json")):
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        results = payload.get("results") or []
        if not results or not isinstance(results, list):
            continue
        first = results[0] if isinstance(results[0], dict) else {}
        openfda = first.get("openfda") or {}
        if not isinstance(openfda, dict):
            continue
        hc_ids = names.ids_for_label(json_path.stem)
        rxcuis = [str(item).strip() for item in openfda.get("rxcui") or [] if str(item).strip()]
        epcs = [
            str(item).strip() for item in openfda.get("pharm_class_epc") or [] if str(item).strip()
        ]
        for hc_id in hc_ids:
            rxcui_by_hc.setdefault(hc_id, set()).update(rxcuis)
            epc_by_hc.setdefault(hc_id, set()).update(epcs)

    return (
        {k: sorted(v) for k, v in sorted(rxcui_by_hc.items())},
        {k: sorted(v) for k, v in sorted(epc_by_hc.items())},
    )


def build_ingredient_bridge(
    names: DrugNameIndex,
    ddinter_names: Mapping[str, str],
    *,
    openfda_dir: Path | None = None,
) -> IngredientBridge:
    """Nối từng hoạt chất đơn (chuẩn hoá) với mã DDInter qua DrugNameIndex và dạng muối."""
    ddinter_by_hc: dict[str, list[str]] = {}
    hc_by_ddinter: dict[str, list[str]] = {}

    for ddinter_id, drug_name in sorted(ddinter_names.items()):
        candidates = (
            normalize_key(drug_name),
            strip_salt(drug_name),
        )
        matched_hc_ids: list[str] = []
        for candidate in candidates:
            if not candidate:
                continue
            resolved = names.resolve(candidate)
            for hc_id in resolved:
                if hc_id not in matched_hc_ids:
                    matched_hc_ids.append(hc_id)
            if matched_hc_ids:
                break
        for hc_id in matched_hc_ids:
            ddinter_by_hc.setdefault(hc_id, [])
            if ddinter_id not in ddinter_by_hc[hc_id]:
                ddinter_by_hc[hc_id].append(ddinter_id)
            hc_by_ddinter.setdefault(ddinter_id, [])
            if hc_id not in hc_by_ddinter[ddinter_id]:
                hc_by_ddinter[ddinter_id].append(hc_id)

    for ids in ddinter_by_hc.values():
        ids.sort()
    for ids in hc_by_ddinter.values():
        ids.sort()

    single_ids = names.single_ingredient_ids()
    unmatched = [hc_id for hc_id in single_ids if hc_id not in ddinter_by_hc]
    rxcui_by_hc, epc_by_hc = _extract_openfda_metadata(names, openfda_dir)

    return IngredientBridge(
        ddinter_by_hoat_chat={k: ddinter_by_hc[k] for k in sorted(ddinter_by_hc)},
        hoat_chat_by_ddinter={k: hc_by_ddinter[k] for k in sorted(hc_by_ddinter)},
        ddinter_names=dict(sorted(ddinter_names.items())),
        rxcui_by_hoat_chat=rxcui_by_hc,
        epc_by_hoat_chat=epc_by_hc,
        unmatched_hoat_chat=unmatched,
        in_scope_ddinter_ids=sorted(hc_by_ddinter),
    )
