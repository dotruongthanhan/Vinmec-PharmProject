"""Chuan hoa ten thuoc, loai bo muoi va anh xa ve ma hoat chat chuan."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.db.bang_luat_store import load_rule_data, register_cache_clear

_LOGGER = logging.getLogger(__name__)
_DEFAULT_HOAT_CHAT_PATH = Path(__file__).resolve().parents[2] / "data" / "kb" / "hoat_chat.json"


class IngredientCatalogEntry(BaseModel):
    """Một hoạt chất hoặc phối hợp cố định trong bảng từ điển hoạt chất."""

    model_config = ConfigDict(extra="ignore")

    hoat_chat_id: str
    ten_inn: str
    ten_viet: str | None = None
    dong_nghia: list[str] = Field(default_factory=list)
    thanh_phan: list[str] | None = None
    nhom: str | None = None


class DrugNameCatalog(BaseModel):
    """Cấu trúc đầy đủ của bảng từ điển hoạt chất và nhãn openFDA."""

    model_config = ConfigDict(extra="ignore")

    hoat_chat: list[IngredientCatalogEntry] = Field(default_factory=list)
    nhan: dict[str, list[str]] = Field(default_factory=dict)


@lru_cache(maxsize=1)
def _load_default_drug_name_catalog() -> DrugNameCatalog | None:
    """Nạp và giữ bộ đệm từ điển hoạt chất mặc định từ tệp hoặc DB."""
    return load_rule_data(
        "hoat_chat",
        _DEFAULT_HOAT_CHAT_PATH,
        DrugNameCatalog.model_validate,
        logger=_LOGGER,
    )


register_cache_clear(_load_default_drug_name_catalog.cache_clear)

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
    def load(cls, path: Path | None = None) -> DrugNameIndex:
        """Nap chi muc ten thuoc tu tep mac dinh hoac DB theo KB_SOURCE."""
        if path is None or Path(path).resolve() == _DEFAULT_HOAT_CHAT_PATH.resolve():
            catalog = _load_default_drug_name_catalog()
            if catalog is None:
                return cls(entries=[], labels={})
            return cls(
                entries=[entry.model_dump() for entry in catalog.hoat_chat],
                labels=dict(catalog.nhan),
            )
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        catalog = DrugNameCatalog.model_validate(data)
        return cls(
            entries=[entry.model_dump() for entry in catalog.hoat_chat],
            labels=dict(catalog.nhan),
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
