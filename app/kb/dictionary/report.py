"""Tạo ma trận độ phủ và mẫu kiểm có seed cố định."""

from __future__ import annotations

import csv
import io
import random
from collections import Counter, defaultdict
from pathlib import Path

from app.kb.dictionary.axis import Inputs
from app.kb.dictionary.storage import Row, read_json, read_jsonl, store, write_json, write_jsonl


def report_dictionary(root: Path) -> Row:
    """Đếm theo tên và chế phẩm duy nhất, dùng dữ liệu đã dựng."""
    inputs = Inputs(root)
    folder = root / "kb_curated/tu_dien"
    out = root / "kb_reports"
    ingredients = read_jsonl(folder / "hoat_chat.jsonl")
    mappings = read_jsonl(folder / "anh_xa.jsonl")
    reviews = read_jsonl(folder / "cho_duyet.jsonl")
    components = read_jsonl(folder / "thuoc_thanh_phan.jsonl")
    rx_manifest = root / "kb_sources/rxnav/manifest.json"
    rx_status = read_json(rx_manifest).get("trang_thai") if rx_manifest.exists() else "chua_lay"

    unique_matches: dict[str, str] = {}
    dav_matches: dict[str, list[Row]] = defaultdict(list)
    mock_mapped: dict[str, set[str]] = defaultdict(set)
    for row in mappings:
        if "khoa_chuan_hoa" in row:
            unique_matches[row["khoa_chuan_hoa"]] = row["cach_khop"]
        if row["nguon"] == "mock":
            mock_mapped[row["ma_ban_ghi_nguon"]].add(row["hoat_chat_id"])
        elif row["nguon"] == "dav":
            dav_matches[row["ma_ban_ghi_nguon"]].append(row)
    dav_reviews: dict[str, list[Row]] = defaultdict(list)
    for row in reviews:
        if row["loai_ban_ghi"] == "ten":
            unique_matches.setdefault(
                row["khoa_chuan_hoa"], "cho_duyet_gan_dung" if row["goi_y"] else "chua_khop"
            )
        if row["nguon"] == "dav" and "ma_ban_ghi_nguon" in row:
            dav_reviews[row["ma_ban_ghi_nguon"]].append(row)
    mock_misses = sorted(
        {
            key
            for ref, keys in inputs.mock_groups.items()
            if len(mock_mapped[ref]) != 1
            for key in keys
        }
    )
    mock_ids = {hid for ids in mock_mapped.values() if len(ids) == 1 for hid in ids}
    product_sets: dict[str, set[str]] = defaultdict(set)
    product_components: dict[str, list[Row]] = defaultdict(list)
    for row in components:
        product_sets[row["hoat_chat_id"]].add(row["thuoc_id"])
        product_components[row["thuoc_id"]].append(row)

    csv_buffer = io.StringIO(newline="")
    writer = csv.writer(csv_buffer)
    writer.writerow(
        [
            "hoat_chat_id",
            "so_thuoc_dav",
            "co_rxcui",
            "co_atc",
            "co_nhan_openfda",
            "trong_ca_gia_lap",
            "ddinter_id",
        ]
    )
    label_files = {
        path.stem.split("__", 1)[0] for path in (root / "kb_sources/openfda").glob("*.json")
    }
    for row in ingredients:
        hid = row["hoat_chat_id"]
        writer.writerow(
            [
                hid,
                len(product_sets[hid]),
                bool(row["rxcui"]),
                bool(row["ma_atc"]),
                hid in label_files,
                hid in mock_ids,
                "",
            ]
        )
    store(out / "T50_do_phu.csv", csv_buffer.getvalue().encode())

    statuses = Counter(split.trang_thai for _, split in inputs.dav)
    reasons = Counter(split.ly_do for _, split in inputs.dav if split.ly_do)
    if missing := inputs.dav_manifest.get("id_thieu_so_dang_ky"):
        reasons["thieu_so_dang_ky"] = len(missing)
    length = len(inputs.dav)
    summary = {
        "trang_thai_dav": inputs.dav_manifest.get("trang_thai", "chua_lay"),
        "trang_thai_rxnav": rx_status,
        "tong_ban_ghi_dav": inputs.dav_manifest.get("totalCount"),
        "so_che_pham_dav": length,
        "so_tach_duoc": statuses["tach_duoc"],
        "so_chua_khop": statuses["chua_khop"],
        "ty_le_tach_duoc": statuses["tach_duoc"] / length if length else None,
        "ty_le_chua_khop": statuses["chua_khop"] / length if length else None,
        "ly_do_tach_hang_dau": dict(reasons.most_common(10)),
        "so_ten_theo_cach_khop": dict(sorted(Counter(unique_matches.values()).items())),
        "so_hoat_chat": len(ingredients),
        "so_hoat_chat_co_rxcui": sum(bool(row["rxcui"]) for row in ingredients),
        "so_hoat_chat_co_atc": sum(bool(row["ma_atc"]) for row in ingredients),
        "hoat_chat_ca_gia_lap_chua_khop": mock_misses,
    }
    write_json(out / "T50_tom_tat.json", summary)

    rng = random.Random(50)
    samples = []
    for raw, split in rng.sample(inputs.dav, min(50, length)):
        product_id = f"dav:{raw['so_dang_ky']}"
        samples.append(
            {
                "loai_ban_ghi": "thuoc_dav",
                "ban_ghi": raw,
                "tach": split.model_dump(),
                "anh_xa": dav_matches[raw["dav_id"]],
                "cho_duyet": dav_reviews[raw["dav_id"]],
                "thanh_phan": product_components[product_id],
            }
        )
    for row in rng.sample(ingredients, min(30, len(ingredients))):
        samples.append({"loai_ban_ghi": "hoat_chat", "ban_ghi": row})
    write_jsonl(out / "T50_mau_kiem.jsonl", samples)
    return summary
