"""Kiem thu chuan hoa ten thuoc va anh xa hoat_chat_id."""

from __future__ import annotations

import json
from pathlib import Path

from app.kb.names import DrugNameIndex, normalize_key, strip_salt

_ROOT = Path(__file__).resolve().parents[2]
_HOAT_CHAT_PATH = _ROOT / "data" / "kb" / "hoat_chat.json"
_MANIFEST_PATH = _ROOT / "data" / "kb_sources" / "manifest.json"


def _manifest_entries() -> list[dict]:
    raw = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    for val in raw.values():
        if isinstance(val, list) and val and isinstance(val[0], dict) and "ten_goi" in val[0]:
            return val
    raise AssertionError("Khong doc duoc danh sach manifest")


def test_normalize_key_basic() -> None:
    assert normalize_key("Acid Valproïc ") == "acid valproic"
    assert normalize_key("Đường uống - Thuốc A") == "duong uong thuoc a"
    assert normalize_key("  AMOXICILLIN / CLAVULANATE ") == "amoxicillin clavulanate"


def test_strip_salt_removes_trailing_salts() -> None:
    assert strip_salt("amlodipine besylate") == "amlodipine"
    assert strip_salt("Metoprolol Succinate") == "metoprolol"
    assert strip_salt("clavulanate potassium") == "clavulanate"
    assert strip_salt("clopidogrel hydrogen sulfate") == "clopidogrel"
    assert strip_salt("acid valproic") == "acid valproic"


def test_resolve_from_real_hoat_chat_index() -> None:
    index = DrugNameIndex.load(_HOAT_CHAT_PATH)

    assert index.resolve("AMOXICILLIN AND CLAVULANATE POTASSIUM") == [
        "amoxicillin",
        "clavulanic_acid",
    ]
    assert index.resolve("Metoprolol Succinate") == ["metoprolol"]
    assert index.resolve("amoxicilin") == ["amoxicillin"]
    assert index.resolve("Co-trimoxazole") == ["sulfamethoxazole", "trimethoprim"]
    assert index.resolve("Paracetamol") == ["acetaminophen"]
    assert index.resolve("thuoc la") == []
    assert index.resolve("") == []


def test_hoat_chat_json_unique_and_covers_all_manifest_labels() -> None:
    data = json.loads(_HOAT_CHAT_PATH.read_text(encoding="utf-8"))
    entries = data["hoat_chat"]
    ids = [item["hoat_chat_id"] for item in entries]
    assert len(ids) == len(set(ids)), "Co hoat_chat_id bi trung lap"
    valid_ids = set(ids)

    index = DrugNameIndex.load(_HOAT_CHAT_PATH)
    openfda_labels = [e for e in _manifest_entries() if e.get("nguon") == "openfda_drug_label"]
    assert len(openfda_labels) == 50

    for item in openfda_labels:
        ten_goi = item["ten_goi"]
        mapped = index.ids_for_label(ten_goi)
        assert mapped, f"Thieu anh xa trong hoat_chat.json cho {ten_goi}"
        assert all(hid in valid_ids for hid in mapped), f"ID khong ton tai cho {ten_goi}"
