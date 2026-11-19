"""Chuẩn hoá và đối chiếu tên theo các khoá đã xác nhận."""

import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.models import HoatChat
from app.kb.names import normalize_key, strip_salt

_NUMBER = r"(?:\d{1,3}(?:[ .]\d{3})+|\d+)(?:[.,]\d+)?"
_UNIT = r"(?:mcg|[µμ]g|microgam|mg|gam|kg|g|ml|lit|l|mmol|meq|miu|iu|ui|đvqt|%)"
_AMOUNT = rf"{_NUMBER}(?:\s*{_UNIT}(?!\w))?"
_STRENGTH = re.compile(
    rf"(?<!\w)(?:{_AMOUNT}(?:\s*/\s*{_AMOUNT})+|{_NUMBER}\s*{_UNIT}(?!\w))"
    rf"(?:\s*/\s*(?:{_UNIT}(?!\w)|giờ\b|phút\b))?(?!\w)",
    re.IGNORECASE,
)
_FORM = (
    r"(?:thuoc bot|bot dong kho|bot pha|bot|vien nen bao phim|vien nen|vien nang cung"
    r"|vien nang mem|vien nang|dang vien|vien|goi pha|goi|dung dich|hon dich|siro"
    r"|intravenous infusion|injections?|infusion|tablets?|capsules?|solution|suspension|powder"
    r"|dich truyen tinh mach|dich truyen"
    r"|pha tiem|pha uong|tiem truyen|truyen tinh mach|tiem tinh mach|nho mui|nho mat)"
)
_LEADING_FORM = re.compile(rf"^{_FORM}\s+")
_TRAILING_FORM = re.compile(rf"\s+{_FORM}$")
_COMBINATION = re.compile(r"\s*(?:[+/;]|\bvà\b)\s*", re.IGNORECASE)


def without_strength(name: str) -> str:
    """Bỏ lượng ghi kèm tên, giữ dấu phân cách hoạt chất."""
    return _STRENGTH.sub(" ", unicodedata.normalize("NFC", name))


def product_key(name: str) -> str:
    """Tạo cùng một khoá cho tên DAV và tên cần tra."""
    key = normalize_key(without_strength(name))
    while True:
        cleaned = _TRAILING_FORM.sub("", _LEADING_FORM.sub("", key))
        if cleaned == key:
            return key
        key = cleaned


def combination_parts(name: str) -> list[str]:
    """Tách phối hợp sau khi bỏ các tỷ lệ hàm lượng."""
    return _COMBINATION.split(without_strength(name))


def salt_key(key: str) -> str:
    """Giữ tên đầy đủ nếu bỏ muối sẽ chỉ còn tên ion."""
    base = strip_salt(key)
    return key if strip_salt(f"x {base}") == "x" else base


@dataclass(frozen=True)
class CaseMatch:
    hoat_chat_id: str | None
    cach_khop: str | None = None
    ly_do: str | None = None


class IngredientNames:
    """Tập ứng viên để nhận ra xung đột giữa các tên đã biết."""

    def __init__(
        self,
        inn_by_id: dict[str, str],
        synonyms: Iterable[tuple[str, str, str]],
    ) -> None:
        self._inn_by_id = inn_by_id
        self._inn: dict[str, set[str]] = defaultdict(set)
        self._synonyms: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        self._ddinter: dict[str, set[str]] = defaultdict(set)
        for identifier, name in inn_by_id.items():
            key = normalize_key(name)
            self._inn[key].add(identifier)
            self._ddinter[salt_key(key)].add(identifier)
        for key, identifier, kind in synonyms:
            self._synonyms[key][identifier].add(kind)
            if kind in {"inn", "muoi"}:
                self._ddinter[salt_key(key)].add(identifier)

    def ddinter_ids(self, name: str) -> set[str]:
        return self._ddinter.get(salt_key(normalize_key(name)), set())

    def name_ids(self, key: str) -> set[str]:
        return set(self._synonyms.get(key, {})) | self._inn.get(key, set())

    def is_salt(self, key: str, identifier: str) -> bool:
        if key == normalize_key(self._inn_by_id[identifier]):
            return False
        base = salt_key(key)
        return key != base and (
            "muoi" in self._synonyms.get(key, {}).get(identifier, set())
            or identifier in self.name_ids(base)
        )

    def match_case(self, ingredient: HoatChat) -> CaseMatch:
        identifier = ingredient.hoat_chat_id
        if not identifier.startswith("HC-"):
            if identifier in self._inn_by_id:
                return CaseMatch(identifier, "ma_truc")
            return CaseMatch(None, ly_do="Mã hoạt chất không có trên trục")

        key = normalize_key(ingredient.ten_quoc_te or "")
        field = "ten_quoc_te"
        if ingredient.ten_quoc_te and ingredient.ten_quoc_te.strip():
            candidates = self.name_ids(key)
            method = "ten_quoc_te" if self._inn.get(key) else "dong_nghia"
            if not candidates and key != salt_key(key):
                candidates = self.name_ids(salt_key(key))
                method = "dang_muoi"
        else:
            key = normalize_key(ingredient.ten_hoat_chat)
            field = "ten_hoat_chat"
            candidates = set(self._synonyms.get(key, {}))
            method = "ten_viet"
        if len(candidates) == 1:
            match = next(iter(candidates))
            return CaseMatch(match, "dang_muoi" if self.is_salt(key, match) else method)
        if candidates:
            return CaseMatch(
                None, ly_do=f"Tên khớp nhiều hoạt chất: {', '.join(sorted(candidates))}"
            )
        reason = f"{field} chưa khớp từ điển: {key}" if key else f"Thiếu {field}"
        return CaseMatch(None, ly_do=reason)
