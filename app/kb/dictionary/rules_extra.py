"""Áp dụng quy tắc có bằng chứng cho từng lần xuất hiện."""

import unicodedata
from collections import defaultdict
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from app.kb.dictionary.axis import Evidence, Inputs, Match
from app.kb.dictionary.catalog import CandidateName, Catalog
from app.kb.dictionary.split import Component, split_herbal_names
from app.kb.names import normalize_key
from app.kb.sources.rxnav import CacheMissing, RxIngredient

CONFIG = Path(__file__).resolve().parents[3] / "config/kb/tu_dien.yaml"
CONSONANTS = frozenset("bcdfghjklmnpqrstvwxyz")
UNRESOLVED_PIN_REASONS = frozenset({"pin_thieu_quan_he_in", "pin_trung_nhieu_ma"})


class Vitamin(BaseModel):
    ten_rxnorm: str
    rxcui: str
    ten_doi_chieu: str | None = None


class RulesConfig(BaseModel):
    tu_nhan_ngu_nghia: bool
    nguong_nhung: float = Field(ge=0, le=1)
    nguong_ky_tu: float = Field(ge=0, le=1)
    chenh_toi_thieu: float = Field(gt=0, le=2)
    bang_vitamin: dict[str, Vitamin]
    ly_do_lui_cho_phep: set[str] = Field(default_factory=set)


def load_rules() -> RulesConfig:
    cfg = RulesConfig.model_validate(yaml.safe_load(CONFIG.read_text(encoding="utf-8-sig")))
    return cfg.model_copy(
        update={"bang_vitamin": {k.lower(): v for k, v in cfg.bang_vitamin.items()}}
    )


def vitamin_code(key: str, config: RulesConfig) -> str | None:
    code = key.removeprefix("vitamin ")
    return code if code in config.bang_vitamin else None


def with_final_e(key: str, catalog: Catalog) -> CandidateName | None:
    if not key or key[-1] not in CONSONANTS or catalog.exact_entries(key):
        return None
    target = key + "e"
    entries = catalog.by_key.get(target, set())
    if entries and len({entry.identity for entry in catalog.exact_entries(target)}) == 1:
        return min(entries, key=lambda entry: (entry.tty != "PIN", entry.tty != "IN", entry.ten))
    return None


def verified_vitamins(
    config: RulesConfig,
    catalog: Catalog,
) -> tuple[dict[str, tuple[CandidateName, tuple[str, ...]]], list[str]]:
    entries = {}
    missing = []
    for code, vitamin in config.bang_vitamin.items():
        entry = catalog.concepts.get(vitamin.rxcui)
        if entry is None or entry.tty != "IN" or entry.ten != vitamin.ten_rxnorm:
            missing.append(code.upper())
            continue
        refs: tuple[str, ...] = ()
        if vitamin.ten_doi_chieu:
            try:
                exact, _ = catalog.rxnav.exact(vitamin.ten_doi_chieu)
            except CacheMissing:
                exact = None
            if not exact or exact.rxcui != vitamin.rxcui:
                missing.append(code.upper())
                continue
            refs = tuple(exact.nguon_ban_ghi_ids)
        entries[code] = entry, refs
    return entries, missing


def _vietnamese(name: str) -> bool:
    if len(normalize_key(name).split()) < 2:
        return False
    return any(
        char in "đĐ\u0300\u0302\u0303\u0306\u0309\u031b\u0323"
        for char in unicodedata.normalize("NFD", name)
    )


def apply_rules(
    inputs: Inputs,
    baseline_matches: dict[str, Match],
    identities: dict[str, RxIngredient],
    catalog: Catalog,
    config: RulesConfig,
    decisions: dict[str, Match],
    semantic: dict[str, CandidateName],
) -> tuple[dict[tuple[str, str], Match], dict[str, list[Component]], list[str]]:
    """Khớp trong ngữ cảnh DAV, giữ tên viết tắt và dược liệu ở đúng chế phẩm."""
    vitamins, missing = verified_vitamins(config, catalog)
    overrides: dict[tuple[str, str], Match] = {}
    herbal: dict[str, list[Component]] = {}
    inferred_herbal_names: set[str] = set()
    dav_by_key: dict[str, list[tuple[str, Component]]] = defaultdict(list)
    for raw, split in inputs.dav:
        dav_id = raw["dav_id"]
        parts = split.thanh_phan
        codes = {vitamin_code(normalize_key(part.ten_hoat_chat_goc), config) for part in parts} - {
            None
        }
        for part in parts:
            key = part.ten_chuan_hoa
            dav_by_key[key].append((dav_id, part))
            full_key = normalize_key(part.ten_hoat_chat_goc)
            if full_key != key and full_key in decisions:
                overrides[dav_id, key] = decisions[full_key].model_copy(
                    update={"khoa_nguon": full_key}
                )
                continue
            if key in decisions and (full_key == key or full_key not in catalog.pins):
                continue
            if code := vitamin_code(full_key, config):
                if (full_key.startswith("vitamin ") or len(codes) >= 2) and code in vitamins:
                    if not baseline_matches[key].hoat_chat_id:
                        entry, refs = vitamins[code]
                        overrides[dav_id, key] = catalog.match(
                            entry, "bang_vitamin", identities, refs
                        )
                elif not full_key.startswith("vitamin "):
                    overrides[dav_id, key] = Match(ly_do="ma_vitamin_thieu_ngu_canh")
                elif not baseline_matches[key].hoat_chat_id:
                    overrides[dav_id, key] = Match(ly_do="ma_vitamin_thieu_nguon")
                continue
            pins = catalog.pins.get(full_key, {})
            if pins:
                if len(pins) == 1 and not catalog.ins.get(full_key):
                    entry = catalog.concepts[next(iter(pins))]
                    match = catalog.match(entry, "rxnav_chinh_xac", identities)
                else:
                    match = Match(ly_do="pin_trung_nhieu_ma")
                overrides[dav_id, key] = match.model_copy(update={"khoa_nguon": full_key})
                continue
            if baseline_matches[key].hoat_chat_id:
                continue
            entry = with_final_e(full_key, catalog)
            if entry is None and full_key != key and not catalog.exact_entries(full_key):
                entry = with_final_e(key, catalog)
            if entry:
                match = catalog.match(entry, "them_e_cuoi", identities)
                overrides[dav_id, key] = match.model_copy(update={"khoa_nguon": full_key})

        herbal_parts = parts
        if split.ly_do == "duoc_lieu_can_duyet":
            herbal_parts = split_herbal_names(raw["hoat_chat_goc"])
        candidates = [
            part
            for part in herbal_parts
            if part.ten_chuan_hoa not in decisions
            and (dav_id, part.ten_chuan_hoa) not in overrides
            and not overrides.get(
                (dav_id, part.ten_chuan_hoa), baseline_matches.get(part.ten_chuan_hoa, Match())
            ).hoat_chat_id
            and not catalog.exact_entries(part.ten_chuan_hoa)
            and not catalog.exact_entries(normalize_key(part.ten_hoat_chat_goc))
            and with_final_e(normalize_key(part.ten_hoat_chat_goc), catalog) is None
            and _vietnamese(part.ten_hoat_chat_goc)
        ]
        marked = split.loai_san_pham == "duoc_lieu"
        if candidates and (marked or len(candidates) == len(parts) >= 3):
            herbal[dav_id] = candidates
            for part in candidates:
                key = part.ten_chuan_hoa
                overrides[dav_id, key] = Match(ly_do="khong_co_du_lieu_tra")
                inferred_herbal_names.add(key)
    # Tên Việt đã có bằng chứng dược liệu vẫn cần ngữ cảnh ở lần xuất hiện khác.
    for key, occurrences in dav_by_key.items():
        if key in decisions or key not in semantic or key in inferred_herbal_names:
            continue
        for dav_id, _ in occurrences:
            if (dav_id, key) not in overrides and not baseline_matches[key].hoat_chat_id:
                overrides[dav_id, key] = catalog.match(
                    semantic[key],
                    "ngu_nghia_tu_nhan",
                    identities,
                )
    return overrides, herbal, missing


def resolve_evidence(
    key: str,
    evidence: Evidence,
    matches: dict[str, Match],
    overrides: dict[tuple[str, str], Match],
) -> Match:
    if evidence.nguon == "dav":
        return overrides.get((evidence.ma_ban_ghi_nguon, key), matches[key])
    return matches[key]
