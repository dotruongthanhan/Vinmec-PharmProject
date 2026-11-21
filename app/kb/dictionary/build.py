"""Xuất dữ liệu tầng 2 và giữ liên kết về bản ghi nguồn."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from random import Random
from typing import get_args

from app.kb.dictionary.accept import load_auto_picks
from app.kb.dictionary.axis import Inputs, Match, MatchMethod, mock_unmatched
from app.kb.dictionary.catalog import baseline
from app.kb.dictionary.review import read_decisions
from app.kb.dictionary.rules_extra import (
    UNRESOLVED_PIN_REASONS,
    RulesConfig,
    apply_rules,
    load_rules,
    resolve_evidence,
    vitamin_code,
)
from app.kb.dictionary.storage import Row, read_jsonl, write_json, write_jsonl
from app.kb.names import normalize_key
from app.kb.sources.rxnav import RxIngredient


def _ingredient_kind(name: str, atc: list[str]) -> str:
    key = normalize_key(name)
    if key in {"sodium chloride", "potassium chloride", "natri clorid", "kali clorid"}:
        return "dich_truyen_dien_giai"
    if any(code.startswith("J07") for code in atc):
        return "sinh_pham"
    if key.startswith("vitamin ") or any(code.startswith(("A11", "A12")) for code in atc):
        return "vitamin_khoang"
    return "thuoc"


def _axis_rows(
    inputs: Inputs,
    matches: dict[str, Match],
    identities: dict[str, RxIngredient],
    overrides: dict[tuple[str, str], Match],
    config: RulesConfig,
) -> tuple[list[Row], dict[str, list[str]]]:
    source_refs: dict[str, set[str]] = defaultdict(set)
    spellings: dict[str, Counter[str]] = defaultdict(Counter)
    for key, evidence_rows in inputs.names.items():
        for evidence in evidence_rows:
            match = resolve_evidence(key, evidence, matches, overrides)
            if hid := match.hoat_chat_id:
                source_refs[hid].add(evidence.reference)
                if evidence.nguon == "dav" and evidence.loai == "viet":
                    raw_key = normalize_key(evidence.ten_goc)
                    if not vitamin_code(raw_key, config) or raw_key.startswith("vitamin "):
                        spellings[hid][evidence.ten_goc] += 1
    rows = []
    refs: dict[str, list[str]] = {}
    herbal_ids = {
        overrides.get((raw["dav_id"], key), matches[key]).hoat_chat_id
        for raw, split in inputs.dav
        if len(split.thanh_phan) == 1 and split.loai_san_pham == "duoc_lieu"
        for key in [split.thanh_phan[0].ten_chuan_hoa]
    }
    for hid in sorted(inputs.legacy.keys() | identities.keys()):
        legacy = inputs.legacy.get(hid)
        identity = identities.get(hid)
        direct_refs = set(identity.nguon_ban_ghi_ids if identity else [])
        if legacy:
            direct_refs.add(f"kb:hoat_chat:{hid}")
        refs[hid] = sorted(direct_refs)
        atc = identity.ma_atc if identity else []
        inn = legacy["ten_inn"] if legacy else identity.ten_inn
        common = sorted(spellings[hid].items(), key=lambda item: (-item[1], item[0]))
        rows.append(
            {
                "hoat_chat_id": hid,
                "ten_inn": inn,
                "ten_viet": common[0][0] if common else legacy["ten_viet"] if legacy else inn,
                "rxcui": identity.rxcui if identity else None,
                "ma_atc": atc,
                "ten_lop_atc": identity.ten_lop_atc if identity else [],
                "loai": "duoc_lieu" if hid in herbal_ids else _ingredient_kind(inn, atc),
                "nguon_ban_ghi_ids": sorted(direct_refs | source_refs[hid]),
            }
        )
    return rows, refs


def _t50_snapshot(reports: Path) -> dict[str, set[str]] | None:
    """Đọc mốc cố định của bản T50, nếu bộ dữ liệu có mốc."""
    path = reports / "T52_moc_T50.jsonl"
    if not path.is_file():
        if (reports / "T50_do_phu.csv").is_file():
            raise ValueError(f"Thieu moc doi chieu T50: {path}")
        return None
    snapshot = {}
    for row in read_jsonl(path):
        thuoc_id, ids = row["thuoc_id"], row["hoat_chat_ids"]
        if thuoc_id in snapshot or not ids:
            raise ValueError(f"Moc T50 khong hop le: {thuoc_id}")
        snapshot[thuoc_id] = set(ids)
    if not snapshot:
        raise ValueError(f"Moc T50 rong: {path}")
    return snapshot


def build_dictionary(root: Path) -> Row:
    """Xuất sáu tệp từ điển từ các nguồn đã lưu tại chỗ."""
    reports = root / "kb_reports"
    snapshot = _t50_snapshot(reports)
    remaining_t50 = snapshot.copy() if snapshot is not None else {}
    inputs, original, identities, catalog = baseline(root)
    config = load_rules()
    decisions = read_decisions(root, catalog)
    active_keys = original.keys() | {
        normalize_key(part.ten_hoat_chat_goc)
        for _, split in inputs.dav
        for part in split.thanh_phan
    }
    manual: dict[str, Match] = {}
    for key, row in decisions.items():
        if key not in active_keys:
            continue
        if row["quyet_dinh"] in {"duoc_lieu", "bo_qua"}:
            manual[key] = Match(
                ly_do=(
                    "khong_co_du_lieu_tra"
                    if row["quyet_dinh"] == "duoc_lieu"
                    else "nguoi_duyet_bo_qua"
                )
            )
        else:
            match = catalog.match(catalog.by_code(row["rxcui"]), "nguoi_duyet", identities)
            if not match.hoat_chat_id:
                raise ValueError(f"Duyet tay khong con hop le: {key} ({match.ly_do})")
            manual[key] = match
    matches = original | {key: match for key, match in manual.items() if key in original}
    semantic = load_auto_picks(root, catalog, config)
    overrides, herbal, missing_vitamins = apply_rules(
        inputs,
        matches,
        identities,
        catalog,
        config,
        manual,
        semantic,
    )
    ingredients, axis_refs = _axis_rows(inputs, matches, identities, overrides, config)
    reviews: list[Row] = []
    mappings: list[Row] = []
    synonyms: dict[tuple[str, str, str, str, str], set[str]] = defaultdict(set)

    for key, evidence_rows in sorted(inputs.names.items()):
        for evidence in evidence_rows:
            match = resolve_evidence(key, evidence, matches, overrides)
            refs = {evidence.reference, *match.nguon_ban_ghi_ids}
            row = {
                "nguon": evidence.nguon,
                "ma_ban_ghi_nguon": evidence.ma_ban_ghi_nguon,
                "ten_goc": evidence.ten_goc,
                "khoa_chuan_hoa": match.khoa_nguon or key,
            }
            if hid := match.hoat_chat_id:
                refs.update(axis_refs[hid])
                mappings.append(
                    {
                        **row,
                        "hoat_chat_id": hid,
                        "cach_khop": match.cach_khop,
                        **({"pin_ve_in": match.pin_ve_in} if match.pin_ve_in else {}),
                        "do_tin_cay": {
                            "ngu_nghia_tu_nhan": "ngu_nghia",
                            "nguoi_duyet": "da_duyet",
                        }.get(match.cach_khop, "chinh_xac"),
                        "nguon_ban_ghi_ids": sorted(refs),
                        **(
                            {
                                field: decisions[match.khoa_nguon or key][field]
                                for field in ("nguoi_duyet", "ghi_chu")
                            }
                            if match.cach_khop == "nguoi_duyet"
                            else {}
                        ),
                    }
                )
                if evidence.nguon != "mock":
                    raw_key = normalize_key(evidence.ten_goc)
                    if not vitamin_code(raw_key, config) or raw_key.startswith("vitamin "):
                        synonyms[
                            (raw_key, hid, evidence.loai, evidence.nguon, match.cach_khop)
                        ].update(refs)
                    if (
                        raw_key != key
                        and match.khoa_nguon is None
                        and not vitamin_code(key, config)
                        and match.cach_khop
                        not in {
                            "them_e_cuoi",
                            "nguoi_duyet",
                            "ngu_nghia_tu_nhan",
                        }
                    ):
                        synonyms[(key, hid, "viet", evidence.nguon, match.cach_khop)].update(refs)
            elif match.ly_do not in {"khong_co_du_lieu_tra", "nguoi_duyet_bo_qua"}:
                reviews.append(
                    {
                        **row,
                        "loai_ban_ghi": "ten",
                        "ly_do": match.ly_do,
                        "cach_khop": "cho_duyet_gan_dung" if match.goi_y else "chua_khop",
                        "goi_y": match.goi_y,
                        "nguon_ban_ghi_ids": sorted(refs),
                    }
                )
    for identifier, ids in sorted(inputs.labels.items()):
        for hid in ids:
            mappings.append(
                {
                    "nguon": "kb",
                    "ma_ban_ghi_nguon": f"nhan:{identifier}",
                    "ten_goc": identifier,
                    "hoat_chat_id": hid,
                    "cach_khop": "ma_chuan",
                    "do_tin_cay": "chinh_xac",
                    "nguon_ban_ghi_ids": [f"kb:nhan:{identifier}", f"kb:hoat_chat:{hid}"],
                }
            )
    for hid, concept in identities.items():
        key = normalize_key(concept.ten_inn)
        synonyms[(key, hid, "inn", "rxnav", "rxnav_chinh_xac")].update(concept.nguon_ban_ghi_ids)

    products, components = [], []
    before, after = Counter(), Counter()
    gains = 0
    lost_reasons: Counter[str] = Counter()
    losses = 0
    regressions: list[Row] = []
    herbal_rows: list[Row] = []
    herbal_names: Counter[str] = Counter()
    for raw, split in inputs.dav:
        registration = raw["so_dang_ky"]
        product_id = f"dav:{registration}"
        dav_ref = f"dav:{raw['dav_id']}"
        original_parts = [original[part.ten_chuan_hoa] for part in split.thanh_phan]
        was_matched = split.trang_thai == "tach_duoc" and all(
            part.hoat_chat_id for part in original_parts
        )
        if was_matched:
            before["du_thanh_phan"] += 1
            before.update({part.cach_khop for part in original_parts})
        expected = remaining_t50.pop(product_id, None)
        if snapshot is None and was_matched:
            expected = {
                target
                for part in original_parts
                for hid in [part.hoat_chat_id]
                for target in inputs.legacy.get(hid, {}).get("thanh_phan") or [hid]
            }
        matched = [
            (part, overrides.get((raw["dav_id"], key), matches[key]))
            for part in split.thanh_phan
            for key in [part.ten_chuan_hoa]
        ]
        if expected is not None:
            # Giữ thành phần T50 đã xác nhận độc lập và đưa tên PIN mơ hồ vào hàng duyệt.
            matched = [
                (part, prior)
                if match.ly_do in UNRESOLVED_PIN_REASONS and prior.hoat_chat_id
                else (part, match)
                for (part, match), prior in zip(matched, original_parts, strict=True)
            ]
        unresolved = [
            match.khoa_nguon or part.ten_chuan_hoa
            for part, match in matched
            if not match.hoat_chat_id
        ]
        is_herbal = raw["dav_id"] in herbal or any(
            match.ly_do == "khong_co_du_lieu_tra" for _, match in matched
        )
        complete = split.trang_thai == "tach_duoc" and not unresolved and not is_herbal
        if complete:
            after["du_thanh_phan"] += 1
            after.update({match.cach_khop for _, match in matched})
        if complete and expected is None:
            gains += 1
        product_refs = sorted(
            {
                dav_ref,
                *(
                    f"dav:{value}"
                    for value in inputs.dav_manifest.get("so_dang_ky_trung", {}).get(
                        registration, []
                    )
                ),
            }
        )
        products.append(
            {
                "thuoc_id": product_id,
                "dav_id": raw["dav_id"],
                "ten_thuoc": raw["ten_thuoc"],
                "so_dang_ky": registration,
                "ham_luong": raw["ham_luong_goc"],
                "dang_bao_che": raw["dang_bao_che"],
                "duong_dung_goc": raw["duong_dung_goc"],
                "con_hieu_luc": raw["con_hieu_luc"],
                "url_hdsd": raw["url_hdsd"],
                "trang_thai_tach": split.trang_thai,
                "ly_do_tach": split.ly_do,
                "loai_san_pham": "duoc_lieu" if is_herbal else split.loai_san_pham,
                "trang_thai_tra": (
                    "khong_co_du_lieu_tra"
                    if is_herbal
                    else "du_thanh_phan"
                    if complete
                    else "chua_khop"
                ),
                "khoa_chuan_hoa": normalize_key(raw["ten_thuoc"] or ""),
                "nguon_ban_ghi_ids": product_refs,
            }
        )
        if is_herbal:
            reported_parts = [
                *herbal.get(raw["dav_id"], []),
                *(part for part, match in matched if match.ly_do == "khong_co_du_lieu_tra"),
            ]
            for key, part in {part.ten_chuan_hoa: part for part in reported_parts}.items():
                herbal_names[key] += 1
                herbal_rows.append(
                    {
                        "loai": "duoc_lieu",
                        "trang_thai": "khong_co_du_lieu_tra",
                        "thuoc_id": product_id,
                        "ten_goc": part.ten_hoat_chat_goc,
                        "khoa_chuan_hoa": key,
                        "nguon_ban_ghi_ids": product_refs,
                    }
                )
        actual: set[str] = set()
        if complete:
            for part, match in matched:
                hid = match.hoat_chat_id
                children = inputs.legacy.get(hid, {}).get("thanh_phan") or []
                for target in children or [hid]:
                    actual.add(target)
                    refs = {dav_ref, *axis_refs[hid], *axis_refs[target], *match.nguon_ban_ghi_ids}
                    components.append(
                        {
                            "thuoc_id": product_id,
                            "hoat_chat_id": target,
                            "ham_luong": None if children else part.ham_luong,
                            "don_vi": None if children else part.don_vi,
                            "dang_muoi": None if children else part.dang_muoi,
                            "cach_khop": match.cach_khop,
                            **({"pin_ve_in": match.pin_ve_in} if match.pin_ve_in else {}),
                            "nguon_ban_ghi_ids": sorted(refs),
                        }
                    )
        elif not is_herbal and (
            split.trang_thai != "tach_duoc"
            or any(
                match.ly_do != "nguoi_duyet_bo_qua"
                for _, match in matched
                if not match.hoat_chat_id
            )
        ):
            reviews.append(
                {
                    "loai_ban_ghi": "thuoc",
                    "nguon": "dav",
                    "thuoc_id": product_id,
                    "ma_ban_ghi_nguon": raw["dav_id"],
                    "ten_goc": raw["ten_thuoc"],
                    "ly_do": split.ly_do or "thanh_phan_chua_khop",
                    "thanh_phan_chua_khop": unresolved,
                    "goi_y": [
                        item
                        for part, match in matched
                        if not match.hoat_chat_id
                        for item in match.goi_y
                    ],
                    "nguon_ban_ghi_ids": sorted(
                        {
                            *product_refs,
                            *(ref for _, match in matched for ref in match.nguon_ban_ghi_ids),
                        }
                    ),
                }
            )
        if expected is not None and (not complete or expected != actual):
            if complete:
                reasons = {"doi_tap_hoat_chat"}
            else:
                reasons = {
                    match.ly_do or "chua_khop" for _, match in matched if not match.hoat_chat_id
                }
                if split.ly_do:
                    reasons.add(split.ly_do)
                if is_herbal:
                    reasons.add("khong_co_du_lieu_tra")
                if not reasons:
                    reasons.add("chua_khop")
                losses += 1
                lost_reasons.update(reasons)
            regressions.append(
                {
                    "thuoc_id": product_id,
                    "ly_do": sorted(reasons),
                    "hoat_chat_ids_truoc": sorted(expected),
                    "hoat_chat_ids_sau": sorted(actual),
                }
            )

    if snapshot is not None:
        before["du_thanh_phan"] = len(snapshot)
    losses += len(remaining_t50)
    lost_reasons["thieu_che_pham"] += len(remaining_t50)
    for product_id, expected in remaining_t50.items():
        regressions.append(
            {
                "thuoc_id": product_id,
                "ly_do": ["thieu_che_pham"],
                "hoat_chat_ids_truoc": sorted(expected),
                "hoat_chat_ids_sau": [],
            }
        )
    regression_path = reports / "T52_lui.jsonl"
    write_jsonl(regression_path, sorted(regressions, key=lambda row: row["thuoc_id"]))
    blocked = sum(bool(set(row["ly_do"]) - config.ly_do_lui_cho_phep) for row in regressions)
    if blocked:
        raise ValueError(f"{blocked} che pham lui so voi T50, xem {regression_path}")

    for raw_id in inputs.dav_manifest.get("id_thieu_so_dang_ky", []):
        reviews.append(
            {
                "loai_ban_ghi": "thuoc",
                "nguon": "dav",
                "ma_ban_ghi_nguon": raw_id,
                "ly_do": "thieu_so_dang_ky",
                "goi_y": [],
                "nguon_ban_ghi_ids": [f"dav:{raw_id}"],
            }
        )

    synonyms_targets: dict[str, set[str]] = defaultdict(set)
    for key, hid, _, _, _ in synonyms:
        synonyms_targets[key].add(hid)
    alias_rows = []
    for (key, hid, kind, source, method), refs in sorted(synonyms.items()):
        if len(synonyms_targets[key]) > 1:
            reviews.append(
                {
                    "loai_ban_ghi": "dong_nghia",
                    "nguon": source,
                    "ten_goc": key,
                    "ly_do": "dong_nghia_trung_nhieu_hoat_chat",
                    "goi_y": sorted(synonyms_targets[key]),
                    "nguon_ban_ghi_ids": sorted(refs),
                }
            )
            continue
        alias_rows.append(
            {
                "khoa_chuan_hoa": key,
                "hoat_chat_id": hid,
                "loai": kind,
                "nguon": source,
                "cach_khop": method,
                "nguon_ban_ghi_ids": sorted(refs),
            }
        )

    metadata = {
        "phien_ban": "T52-v1",
        "ngay_dung": datetime.now(UTC).date().isoformat(),
    }
    tables = {
        "hoat_chat": ingredients,
        "dong_nghia": alias_rows,
        "thuoc": products,
        "thuoc_thanh_phan": components,
        "anh_xa": mappings,
        "cho_duyet": reviews,
    }
    mock_misses = mock_unmatched(inputs, matches)
    if mock_unmatched(inputs, original) == [] and mock_misses:
        raise ValueError("T52 lam mat anh xa hoat chat cua ca gia lap")
    for table, rows in tables.items():
        if any(not row["nguon_ban_ghi_ids"] for row in rows):
            raise ValueError(f"Bang {table} co dong thieu nguon neo")
    if any(not refs for refs in axis_refs.values()):
        raise ValueError("Co hoat chat khong neo")
    summary = {
        "tong_che_pham": len(products),
        "truoc": {key: before[key] for key in ("du_thanh_phan", *get_args(MatchMethod))},
        "sau": {key: after[key] for key in ("du_thanh_phan", *get_args(MatchMethod))},
        "so_che_pham_du_thanh_phan_moi": gains,
        "so_che_pham_chuyen_ve_chua_du": losses,
        "ly_do_chuyen_ve_chua_du": dict(sorted((+lost_reasons).items())),
        "so_che_pham_du_nhung_doi_tap_hoat_chat": sum(
            row["ly_do"] == ["doi_tap_hoat_chat"] for row in regressions
        ),
        "so_ten_con_trong_hang_duyet": len(
            {row["khoa_chuan_hoa"] for row in reviews if row["loai_ban_ghi"] == "ten"}
        ),
        "so_che_pham_duoc_lieu": sum(row["loai_san_pham"] == "duoc_lieu" for row in products),
        "so_che_pham_duoc_lieu_khong_co_du_lieu_tra": len({row["thuoc_id"] for row in herbal_rows}),
        "hoat_chat_ca_gia_lap_chua_khop": mock_misses,
        "top_30_duoc_lieu": dict(
            sorted(herbal_names.items(), key=lambda item: (-item[1], item[0]))[:30]
        ),
        "ma_vitamin_thieu_nguon": missing_vitamins,
    }
    folder = root / "kb_curated/tu_dien"
    for table, rows in tables.items():
        write_jsonl(folder / f"{table}.jsonl", ({**row, **metadata} for row in rows))
    write_json(reports / "T52_do_phu_truoc_sau.json", summary)
    rng = Random(52)  # noqa: S311  # mẫu kiểm dữ liệu tất định
    samples = []
    for method in ("them_e_cuoi", "bang_vitamin"):
        group = [row for row in mappings if row["cach_khop"] == method]
        samples.extend(
            {"nhom_mau": method, **row} for row in rng.sample(group, min(10, len(group)))
        )
    samples.extend(
        {"nhom_mau": "duoc_lieu", **row}
        for row in rng.sample(herbal_rows, min(10, len(herbal_rows)))
    )
    write_jsonl(reports / "T52_mau_kiem.jsonl", samples)
    return {
        "do_phu": summary,
        "so_dong": {table: len(rows) for table, rows in tables.items()},
        "so_ten_theo_cach_khop": {
            method: len(
                {
                    row["khoa_chuan_hoa"]
                    for row in mappings
                    if row["cach_khop"] == method and "khoa_chuan_hoa" in row
                }
            )
            for method in get_args(MatchMethod)
        },
    }
