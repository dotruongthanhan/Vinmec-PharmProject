"""Chi muc goi y ten thuoc theo tang va so khop mo trigram/Damerau-Levenshtein."""

from __future__ import annotations

import heapq
import re
from bisect import bisect_left
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.kb.names import normalize_key

LoaiMuc = Literal["hoat_chat", "dong_nghia", "biet_duoc"]
KieuKhop = Literal["chinh_xac", "tien_to", "gan_dung"]
SuggestTuple = tuple[str, str, LoaiMuc, Sequence[str], str]

_LOAI_RANK: dict[LoaiMuc, int] = {
    "hoat_chat": 0,
    "dong_nghia": 1,
    "biet_duoc": 2,
}
_UNIT_RE_PART = r"(?:mcg|ug|microgam|mg|gam|kg|g|ml|lit|l|mmol|meq|miu|iu|ui|dvqt|pct)"
_STRENGTH_TOKEN_RE = (
    rf"(?:(?:\d+\s+)*\d+\s*{_UNIT_RE_PART}(?:\s+(?:ml|l|gio|phut|ngay))?"
    rf"|{_UNIT_RE_PART}\s+(?:ml|l|gio|phut|ngay))"
)
_TRAILING_STRENGTH_RE = re.compile(rf"(?:\s+{_STRENGTH_TOKEN_RE})+$")
_STANDALONE_STRENGTH_RE = re.compile(rf"^{_STRENGTH_TOKEN_RE}$")
_PCT_SUFFIX_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%(?=\s*(?:\d|$|\W))")

_TRIGRAM_THRESHOLD = 0.3
_MAX_CANDIDATES = 300


class MucGoiY(BaseModel):
    """Mot muc goi y ten thuoc tra ve cho giao dien va API."""

    model_config = ConfigDict(extra="forbid")

    nhan: str
    loai: LoaiMuc
    hoat_chat_ids: list[str]
    ten_hoat_chat: list[str]
    gia_tri_gui: str
    khop: KieuKhop


class KetQuaGoiY(BaseModel):
    """Ket qua goi y kem chuoi goi y sua loi chinh ta neu chi co khop gan dung."""

    model_config = ConfigDict(extra="forbid")

    ket_qua: list[MucGoiY]
    goi_y_sua: str | None = None


@dataclass(frozen=True, slots=True)
class _IndexedEntry:
    khoa: str
    nhan: str
    loai: LoaiMuc
    loai_rank: int
    hoat_chat_ids: tuple[str, ...]
    hoat_chat_set: frozenset[str]
    ten_hoat_chat: tuple[str, ...]
    gia_tri_gui: str


def normalize_suggest_query(q: str) -> str:
    """Chuan hoa truy van bang normalize_key va bo phan ham luong o cuoi."""
    if not q:
        return ""
    pre = _PCT_SUFFIX_RE.sub(r"\1 pct ", q)
    norm = normalize_key(pre)
    if not norm or _STANDALONE_STRENGTH_RE.fullmatch(norm):
        return ""
    return _TRAILING_STRENGTH_RE.sub("", norm).strip()


def _trigrams(text: str) -> frozenset[str]:
    """Tap trigram co dem mot khoang trang o hai dau."""
    padded = f" {text} "
    return frozenset(padded[i : i + 3] for i in range(len(padded) - 2))


def _jaccard(a: frozenset[str], b: frozenset[str], shared: int) -> float:
    """Do tuong dong Jaccard khong lam tron."""
    union = len(a) + len(b) - shared
    return shared / union if union > 0 else 0.0


def _damerau_levenshtein_bounded(a: str, b: str, max_dist: int) -> int:
    """Khoang cach sua Damerau-Levenshtein (OSA) co tran de cat nhanh."""
    m, n = len(a), len(b)
    if abs(m - n) > max_dist:
        return max_dist + 1
    if a == b:
        return 0
    if m == 0:
        return n
    if n == 0:
        return m

    inf = max_dist + 1
    prev2 = [inf] * (n + 1)
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [inf] * (n + 1)
        curr[0] = i
        j_start = max(1, i - max_dist - 1)
        j_end = min(n, i + max_dist + 1)
        ai = a[i - 1]
        for j in range(j_start, j_end + 1):
            cost = 0 if ai == b[j - 1] else 1
            best = prev[j] + 1
            insert_cost = curr[j - 1] + 1
            if insert_cost < best:
                best = insert_cost
            sub_cost = prev[j - 1] + cost
            if sub_cost < best:
                best = sub_cost
            if i > 1 and j > 1 and ai == b[j - 2] and a[i - 2] == b[j - 1]:
                trans = prev2[j - 2] + 1
                if trans < best:
                    best = trans
            curr[j] = best
        prev2, prev = prev, curr
    return prev[n]


class DrugSuggestIndex:
    """Chi muc goi y ten thuoc thuan trong bo nho, khong doc tep hay mang."""

    def __init__(
        self,
        entries: Iterable[SuggestTuple],
        inn_by_id: Mapping[str, str] | None = None,
    ) -> None:
        """Dung chi muc tu danh sach (khoa, nhan_hien_thi, loai, hoat_chat_ids, gia_tri_gui)."""
        raw_entries = list(entries)
        inn_map: dict[str, str] = dict(inn_by_id) if inn_by_id is not None else {}
        for _, nhan, loai, ids, gia_tri_gui in raw_entries:
            if loai == "hoat_chat" and len(ids) == 1:
                hid = str(ids[0])
                if hid:
                    inn_map.setdefault(hid, gia_tri_gui or nhan)

        by_key: dict[str, list[_IndexedEntry]] = {}
        seen_entries: set[tuple[str, LoaiMuc, frozenset[str]]] = set()

        for raw_key, nhan, loai, ids, gia_tri_gui in raw_entries:
            khoa = normalize_key(raw_key)
            if not khoa:
                continue
            clean_ids = tuple(dict.fromkeys(str(item) for item in ids if str(item)))
            if not clean_ids:
                continue
            id_set = frozenset(clean_ids)
            if loai == "dong_nghia" and len(clean_ids) == 1:
                inn = inn_map.get(clean_ids[0], clean_ids[0])
                if khoa == normalize_key(inn):
                    continue
            dedup_sig = (khoa, loai, id_set)
            if dedup_sig in seen_entries:
                continue
            seen_entries.add(dedup_sig)

            ten_hoat_chat = tuple(inn_map.get(hid, hid) for hid in clean_ids)
            indexed = _IndexedEntry(
                khoa=khoa,
                nhan=nhan,
                loai=loai,
                loai_rank=_LOAI_RANK[loai],
                hoat_chat_ids=clean_ids,
                hoat_chat_set=id_set,
                ten_hoat_chat=ten_hoat_chat,
                gia_tri_gui=gia_tri_gui,
            )
            by_key.setdefault(khoa, []).append(indexed)

        self._keys: list[str] = list(by_key.keys())
        self._entries_by_idx: list[list[_IndexedEntry]] = [by_key[k] for k in self._keys]
        self._key_to_idx: dict[str, int] = {k: idx for idx, k in enumerate(self._keys)}

        sorted_pairs = sorted((k, idx) for idx, k in enumerate(self._keys))
        self._sorted_keys: list[str] = [k for k, _ in sorted_pairs]
        self._sorted_key_ids: list[int] = [idx for _, idx in sorted_pairs]

        word_map: dict[str, list[int]] = {}
        key_trigrams: list[frozenset[str]] = []
        trigram_index: dict[str, list[int]] = {}

        for idx, k in enumerate(self._keys):
            words = k.split()
            for word in dict.fromkeys(words[1:]):
                word_map.setdefault(word, []).append(idx)
            tgs = _trigrams(k)
            key_trigrams.append(tgs)
            for tg in tgs:
                trigram_index.setdefault(tg, []).append(idx)

        self._word_to_key_ids = word_map
        self._sorted_words = sorted(word_map.keys())
        self._key_trigrams = key_trigrams
        self._trigram_index = trigram_index

    def _select_tier3_candidates(
        self,
        q_tgs: frozenset[str],
        excluded_idxs: set[int],
    ) -> list[tuple[int, int]]:
        """Chon toi da _MAX_CANDIDATES khoa co nhieu trigram chung nhat."""
        counts: dict[int, int] = {}
        for tg in q_tgs:
            for idx in self._trigram_index.get(tg, ()):
                if idx not in excluded_idxs:
                    counts[idx] = counts.get(idx, 0) + 1
        if not counts:
            return []
        if len(counts) <= _MAX_CANDIDATES:
            return list(counts.items())

        q_tg_len = len(q_tgs)
        half = _MAX_CANDIDATES // 2
        by_shared = heapq.nlargest(
            half,
            counts.items(),
            key=lambda item: (item[1], -len(self._keys[item[0]])),
        )
        by_bound = heapq.nlargest(
            _MAX_CANDIDATES - half,
            counts.items(),
            key=lambda item: (
                item[1] / max(1, q_tg_len + len(self._keys[item[0]]) - item[1]),
                item[1],
            ),
        )
        merged: dict[int, int] = {}
        for idx, shared in by_shared:
            merged[idx] = shared
        for idx, shared in by_bound:
            merged.setdefault(idx, shared)
        if len(merged) < _MAX_CANDIDATES:
            for idx, shared in heapq.nlargest(
                _MAX_CANDIDATES,
                counts.items(),
                key=lambda item: (item[1], -len(self._keys[item[0]])),
            ):
                if idx not in merged:
                    merged[idx] = shared
                    if len(merged) >= _MAX_CANDIDATES:
                        break
        return list(merged.items())

    def goi_y(self, q: str, gioi_han: int = 8) -> KetQuaGoiY:
        """Tra goi y ten thuoc theo thu tu tang 0..3 va gop trung theo tap hoat chat."""
        norm_q = normalize_suggest_query(q)
        if len(norm_q) < 2 or gioi_han <= 0:
            return KetQuaGoiY(ket_qua=[], goi_y_sua=None)

        matched_tier: dict[int, int] = {}
        exact_idx = self._key_to_idx.get(norm_q)
        if exact_idx is not None:
            matched_tier[exact_idx] = 0

        pos = bisect_left(self._sorted_keys, norm_q)
        while pos < len(self._sorted_keys) and self._sorted_keys[pos].startswith(norm_q):
            idx = self._sorted_key_ids[pos]
            matched_tier.setdefault(idx, 1)
            pos += 1

        q_words = norm_q.split()
        if len(q_words) == 1:
            wpos = bisect_left(self._sorted_words, norm_q)
            while wpos < len(self._sorted_words) and self._sorted_words[wpos].startswith(norm_q):
                for idx in self._word_to_key_ids[self._sorted_words[wpos]]:
                    matched_tier.setdefault(idx, 2)
                wpos += 1
        else:
            needle = f" {norm_q}"
            for idx in self._word_to_key_ids.get(q_words[0], ()):
                if needle in self._keys[idx]:
                    matched_tier.setdefault(idx, 2)

        tier0_2_rows: list[tuple[int, _IndexedEntry]] = []
        for idx, tier in matched_tier.items():
            for entry in self._entries_by_idx[idx]:
                tier0_2_rows.append((tier, entry))
        tier0_2_rows.sort(key=lambda row: (row[0], row[1].loai_rank, len(row[1].khoa), row[1].khoa))

        selected: list[MucGoiY] = []
        seen_non_brand: set[frozenset[str]] = set()
        brand_counts: dict[frozenset[str], int] = {}

        def _try_add(entry: _IndexedEntry, khop: KieuKhop) -> bool:
            if entry.loai == "biet_duoc":
                count = brand_counts.get(entry.hoat_chat_set, 0)
                if count >= 2:
                    return False
                brand_counts[entry.hoat_chat_set] = count + 1
            else:
                if entry.hoat_chat_set in seen_non_brand:
                    return False
                seen_non_brand.add(entry.hoat_chat_set)
            selected.append(
                MucGoiY(
                    nhan=entry.nhan,
                    loai=entry.loai,
                    hoat_chat_ids=list(entry.hoat_chat_ids),
                    ten_hoat_chat=list(entry.ten_hoat_chat),
                    gia_tri_gui=entry.gia_tri_gui,
                    khop=khop,
                )
            )
            return len(selected) >= gioi_han

        for tier, entry in tier0_2_rows:
            khop: KieuKhop = "chinh_xac" if tier == 0 else "tien_to"
            if _try_add(entry, khop):
                return KetQuaGoiY(ket_qua=selected, goi_y_sua=None)

        has_tier0_2 = bool(selected)
        q_tgs = _trigrams(norm_q)
        candidates = self._select_tier3_candidates(q_tgs, set(matched_tier))
        max_dist = max(1, len(norm_q) // 4)
        tier3_rows: list[tuple[float, int, _IndexedEntry]] = []

        for idx, shared in candidates:
            key = self._keys[idx]
            sim = _jaccard(q_tgs, self._key_trigrams[idx], shared)
            dist = _damerau_levenshtein_bounded(norm_q, key, max_dist)
            if sim >= _TRIGRAM_THRESHOLD or dist <= max_dist:
                for entry in self._entries_by_idx[idx]:
                    tier3_rows.append((sim, dist, entry))

        tier3_rows.sort(
            key=lambda row: (-row[0], row[1], row[2].loai_rank, len(row[2].khoa), row[2].khoa)
        )
        for _, _, entry in tier3_rows:
            if _try_add(entry, "gan_dung"):
                break

        goi_y_sua = selected[0].nhan if (not has_tier0_2 and selected) else None
        return KetQuaGoiY(ket_qua=selected, goi_y_sua=goi_y_sua)
