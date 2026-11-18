"""Chuan hoa ten thuoc, loai bo muoi va anh xa ve ma hoat chat chuan."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

_SALT_TOKENS: frozenset[str] = frozenset(
    {
        "besylate",
        "besilate",
        "hydrochloride",
        "hydroclorid",
        "hcl",
        "sodium",
        "natri",
        "potassium",
        "kali",
        "tartrate",
        "tartrat",
        "succinate",
        "succinat",
        "sulfate",
        "sulfat",
        "sulphate",
        "calcium",
        "canxi",
        "magnesium",
        "magnesi",
        "maleate",
        "maleat",
        "bisulfate",
        "bisulfat",
        "citrate",
        "citrat",
        "mesylate",
        "mesilate",
        "etexilate",
        "etexilat",
        "tromethamine",
        "trometamol",
        "monohydrate",
        "trihydrate",
        "trihydrat",
        "dihydrate",
        "hemihydrate",
        "lactate",
        "lysine",
        "acetate",
        "phosphate",
        "fumarate",
        "gluconate",
        "nitrate",
        "chloride",
        "bromide",
        "hydrogen",
        "anhydrous",
        "hydrate",
    }
)

_COMBO_SPLIT_RE = re.compile(r"\s*(?:\+|/|\band\b|&|,)\s*", re.IGNORECASE)


def normalize_key(name: str) -> str:
    """Chuan hoa khoa tim kiem ten thuoc: chu thuong, bo dau, bo dau cau."""
    if not name:
        return ""
    text = name.replace("Đ", "d").replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^a-z0-9]+", " ", stripped.lower())
    return cleaned.strip()


def strip_salt(key: str) -> str:
    """Loai bo cac tu chi dang muoi/ngam nuoc o cuoi ten thuoc."""
    normalized = normalize_key(key)
    if not normalized:
        return ""
    tokens = normalized.split()
    while len(tokens) > 1 and tokens[-1] in _SALT_TOKENS:
        tokens.pop()
    return " ".join(tokens)


class DrugNameIndex:
    """Chi muc tra cuu va chuan hoa ten thuoc ve hoat_chat_id."""

    def __init__(self, entries: list[dict], labels: dict[str, list[str]]) -> None:
        """Khoi tao chi muc tu danh sach hoat chat va bang anh xa nhan."""
        self._entries = entries
        self._labels = {k: list(v) for k, v in labels.items()}
        self._inn_by_id: dict[str, str] = {}
        self._lookup: dict[str, list[str]] = {}

        for entry in entries:
            hid = str(entry["hoat_chat_id"])
            thanh_phan = entry.get("thanh_phan")
            if thanh_phan:
                target_ids = [str(item) for item in thanh_phan]
            else:
                target_ids = [hid]
                self._inn_by_id[hid] = str(entry.get("ten_inn") or hid)

            raw_names = [
                hid,
                str(entry.get("ten_inn") or ""),
                str(entry.get("ten_viet") or ""),
                *[str(syn) for syn in entry.get("dong_nghia") or []],
            ]
            for raw in raw_names:
                norm = normalize_key(raw)
                if norm:
                    self._lookup.setdefault(norm, list(target_ids))

        # Bo sung khoa da bo muoi neu chua trung voi khoa chinh xac.
        for norm_key, target_ids in list(self._lookup.items()):
            salt_less = strip_salt(norm_key)
            if salt_less and salt_less not in self._lookup:
                self._lookup[salt_less] = list(target_ids)

    @classmethod
    def load(cls, path: Path) -> DrugNameIndex:
        """Nap chi muc ten thuoc tu tep JSON."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            entries=list(data.get("hoat_chat", [])),
            labels=dict(data.get("nhan", {})),
        )

    def _resolve_single(self, fragment: str) -> list[str]:
        norm = normalize_key(fragment)
        if not norm:
            return []
        if norm in self._lookup:
            return list(self._lookup[norm])
        salt_less = strip_salt(norm)
        if salt_less in self._lookup:
            return list(self._lookup[salt_less])
        return []

    def resolve(self, name: str) -> list[str]:
        """Anh xa ten thuoc tho ve danh sach hoat_chat_id (khong trung lap)."""
        if not name or not name.strip():
            return []

        direct = self._resolve_single(name)
        if direct:
            return direct

        parts = [part.strip() for part in _COMBO_SPLIT_RE.split(name) if part.strip()]
        if len(parts) <= 1:
            return []

        resolved: list[str] = []
        seen: set[str] = set()
        for part in parts:
            ids = self._resolve_single(part)
            if not ids:
                return []
            for hid in ids:
                if hid not in seen:
                    seen.add(hid)
                    resolved.append(hid)
        return resolved

    def ids_for_label(self, ten_goi: str) -> list[str]:
        """Lay danh sach hoat_chat_id cho ten_goi nhan openFDA."""
        return list(self._labels.get(ten_goi, []))

    def inn_names(self, hoat_chat_ids: list[str]) -> list[str]:
        """Lay danh sach ten INN tuong ung voi cac hoat_chat_id."""
        return [self._inn_by_id.get(hid, hid) for hid in hoat_chat_ids]

    def synonyms_for(self, hoat_chat_id: str) -> list[str]:
        """Tra ve danh sach ten goc/dong nghia de do tim trong van ban openFDA."""
        for entry in self._entries:
            if str(entry.get("hoat_chat_id")) != hoat_chat_id:
                continue
            terms: list[str] = []
            seen: set[str] = set()
            candidates = [
                str(entry.get("ten_inn") or ""),
                str(entry.get("ten_viet") or ""),
                hoat_chat_id.replace("_", " "),
                *[str(syn) for syn in entry.get("dong_nghia") or []],
            ]
            for term in candidates:
                cleaned = term.strip()
                key = cleaned.lower()
                if cleaned and key not in seen:
                    seen.add(key)
                    terms.append(cleaned)
            return terms
        return [hoat_chat_id.replace("_", " ")]

    def single_ingredient_ids(self) -> list[str]:
        """Tra ve danh sach cac hoat_chat_id don chat trong chi muc."""
        return [
            str(entry["hoat_chat_id"]) for entry in self._entries if not entry.get("thanh_phan")
        ]
