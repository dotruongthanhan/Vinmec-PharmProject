"""Phiên che định danh cho một lần gọi LLM: lớp 1 theo giá trị đã biết, lớp 2 theo mẫu.

Một giá trị một mã tạm trong cả phiên. Bảng ánh xạ chỉ sống trong bộ nhớ của phiên:
không ghi log, không lưu tệp.
"""

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from app.deid.known import GiaTriDinhDanh
from app.deid.scrubber import _TOKEN, DeidError, find_pattern_spans, restore_text

_WORD_EDGE_BEFORE = r"(?<![0-9a-z])"
_WORD_EDGE_AFTER = r"(?![0-9a-z])"
_TITLES = r"(?:bn|benh\s+nhan|nguoi\s+benh|ong|ba|anh|chi|chau)"
_MIN_FOLDED_LENGTH = {"TEN": 4, "DIACHI": 4, "SDT": 6, "BHYT": 6, "MA": 3, "NGAY": 6}


def _fold(text: str) -> tuple[str, list[int]]:
    """Gấp chữ: bỏ dấu, không phân biệt hoa thường; trả chuỗi gấp và chỉ số gốc từng ký tự."""
    chars: list[str] = []
    origin: list[int] = []
    for index, char in enumerate(text):
        for part in unicodedata.normalize("NFD", char):
            if unicodedata.category(part).startswith("M"):
                continue
            folded = part.casefold()
            folded = "d" if folded == "đ" else folded
            for item in folded:
                chars.append(item)
                origin.append(index)
    return "".join(chars), origin


def _words(value: str) -> list[str]:
    """Tách các cụm chữ-số của giá trị đã gấp."""
    return re.findall(r"[0-9a-z]+", _fold(value)[0])


def _join(words: list[str], separator: str) -> str:
    return separator.join(re.escape(word) for word in words)


def _parse_date(value: str) -> date | None:
    for pattern, order in (
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", (0, 1, 2)),
        (r"(\d{1,2})/(\d{1,2})/(\d{4})", (2, 1, 0)),
    ):
        match = re.fullmatch(pattern, value.strip())
        if match:
            parts = [int(match.group(i + 1)) for i in range(3)]
            try:
                return date(parts[order[0]], parts[order[1]], parts[order[2]])
            except ValueError:
                return None
    return None


@dataclass(frozen=True)
class _Matcher:
    """Một mẫu dò giá trị đã biết trên văn bản đã gấp."""

    loai: str
    canonical: str
    pattern: re.Pattern[str]
    weight: int
    given_name: bool = False


def _display(item: GiaTriDinhDanh) -> str:
    """Giá trị dùng để khôi phục; ngày sinh về dạng dd/mm/yyyy."""
    if item.loai == "NGAY":
        parsed = _parse_date(item.gia_tri)
        if parsed is not None:
            return parsed.strftime("%d/%m/%Y")
    return item.gia_tri


def _date_patterns(value: str) -> list[str]:
    parsed = _parse_date(value)
    if parsed is None:
        words = _words(value)
        return [_WORD_EDGE_BEFORE + _join(words, r"\s*") + _WORD_EDGE_AFTER] if words else []
    day, month, year = parsed.day, parsed.month, parsed.year
    separator = r"[/.\-]"
    return [
        rf"(?<!\d)0?{day}{separator}0?{month}{separator}{year}(?!\d)",
        rf"(?<!\d){year}{separator}0?{month}{separator}0?{day}(?!\d)",
        rf"{_WORD_EDGE_BEFORE}ngay\s+0?{day}\s+thang\s+0?{month}\s+nam\s+{year}(?!\d)",
    ]


def _phone_pattern(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("84") and len(digits) >= 10:
        digits = "0" + digits[2:]
    rest = digits[1:] if digits.startswith("0") else digits
    if len(rest) < 6:
        return None
    body = r"[ .\-]*".join(rest)
    return rf"(?<![\d+])(?:\+?84|0)[ .\-]*{body}(?!\d)"


def _build_matchers(identifiers: Iterable[GiaTriDinhDanh]) -> list[_Matcher]:
    """Dựng mẫu dò cho từng giá trị, kể cả biến thể; chuỗi dài dò trước."""
    matchers: list[_Matcher] = []
    for item in dict.fromkeys(identifiers):
        words = _words(item.gia_tri)
        folded_length = sum(len(word) for word in words)
        if not words or folded_length < _MIN_FOLDED_LENGTH.get(item.loai, 1):
            continue
        patterns: list[tuple[str, int, bool]] = []
        if item.loai == "TEN":
            patterns.append(
                (_WORD_EDGE_BEFORE + _join(words, r"\s+") + _WORD_EDGE_AFTER, folded_length, False)
            )
            for size in (2, 1):
                tail = words[-size:]
                if len(words) > size and all(w.isalpha() and len(w) >= 2 for w in tail):
                    body = _join(tail, r"\s+")
                    patterns.append(
                        (
                            rf"{_WORD_EDGE_BEFORE}{_TITLES}{_WORD_EDGE_AFTER}"
                            rf"(?:[.:]\s*|\s+)(?P<given>{body}){_WORD_EDGE_AFTER}",
                            folded_length - 1000 + sum(len(w) for w in tail),
                            True,
                        )
                    )
        elif item.loai == "NGAY":
            for text in _date_patterns(item.gia_tri):
                patterns.append((text, folded_length, False))
            parsed = _parse_date(item.gia_tri)
            if parsed is not None:
                patterns.append(
                    (
                        rf"{_WORD_EDGE_BEFORE}(?:sinh\s+nam|nam\s+sinh|sn)\s*:?\s*"
                        rf"(?P<given>{parsed.year})(?!\d)",
                        folded_length - 1000,
                        True,
                    )
                )
        elif item.loai == "SDT":
            phone = _phone_pattern(item.gia_tri)
            if phone is not None:
                patterns.append((phone, folded_length, False))
        elif item.loai == "BHYT":
            body = r"[ \-]?".join(re.escape(char) for char in "".join(words))
            patterns.append((_WORD_EDGE_BEFORE + body + _WORD_EDGE_AFTER, folded_length, False))
        elif item.loai == "MA":
            patterns.append(
                (
                    _WORD_EDGE_BEFORE + _join(words, r"[\s\-_]*") + _WORD_EDGE_AFTER,
                    folded_length,
                    False,
                )
            )
        else:
            patterns.append(
                (
                    _WORD_EDGE_BEFORE + _join(words, r"[\s,.\-]+") + _WORD_EDGE_AFTER,
                    folded_length,
                    False,
                )
            )
        for text, weight, given in patterns:
            matchers.append(
                _Matcher(
                    loai=item.loai,
                    canonical=item.gia_tri,
                    pattern=re.compile(text),
                    weight=weight,
                    given_name=given,
                )
            )
    matchers.sort(key=lambda matcher: -matcher.weight)
    return matchers


class DeidSession:
    """Phiên che và khôi phục định danh cho đúng một lần gọi LLM."""

    def __init__(self, identifiers: Iterable[GiaTriDinhDanh] = ()) -> None:
        values = list(dict.fromkeys(identifiers))
        self._matchers = _build_matchers(values)
        self._display_of = {(item.loai, item.gia_tri): _display(item) for item in values}
        self._counts: dict[str, int] = {}
        self._tokens: dict[tuple[str, str], str] = {}
        self._mapping: dict[str, str] = {}

    @property
    def anh_xa(self) -> dict[str, str]:
        """Bảng mã tạm -> giá trị thật, chỉ dùng trong bộ nhớ của lần gọi."""
        return self._mapping

    def _token(self, kind: str, key: str, original: str) -> str:
        token = self._tokens.get((kind, key))
        if token is None:
            self._counts[kind] = self._counts.get(kind, 0) + 1
            token = f"[{kind}_{self._counts[kind]}]"
            self._tokens[(kind, key)] = token
            self._mapping[token] = original
        return token

    def _known_spans(self, van_ban: str) -> list[tuple[int, int, str, str, str]]:
        """Dò lớp 1: trả (đầu, cuối, loại, khóa, giá trị khôi phục) trên văn bản gốc."""
        if not self._matchers:
            return []
        folded, origin = _fold(van_ban)
        if not folded:
            return []
        taken: list[tuple[int, int]] = []
        spans: list[tuple[int, int, str, str, str]] = []
        for matcher in self._matchers:
            for match in matcher.pattern.finditer(folded):
                begin, finish = match.span("given") if matcher.given_name else match.span()
                if finish <= begin or any(begin < b and a < finish for a, b in taken):
                    continue
                taken.append((begin, finish))
                start = origin[begin]
                end = origin[finish - 1] + 1
                while end < len(van_ban) and unicodedata.category(van_ban[end]).startswith("M"):
                    end += 1
                shown = self._display_of.get((matcher.loai, matcher.canonical), matcher.canonical)
                spans.append((start, end, matcher.loai, matcher.canonical, shown))
        return spans

    def mask_known(self, van_ban: str) -> str:
        """Chỉ che giá trị đã biết (lớp 1); dùng cho văn bản đã chứa mã tạm."""
        try:
            return self._apply(van_ban, sorted(self._known_spans(van_ban)))
        except Exception as exc:
            raise DeidError("Không thể che định danh.") from exc

    def scrub(self, van_ban: str, *, patterns: bool = True) -> str:
        """Che lớp 1 rồi (mặc định) lớp 2; ném DeidError khi đầu vào đã chứa mã tạm hoặc lỗi."""
        try:
            if not isinstance(van_ban, str):
                raise DeidError("Văn bản đầu vào phải là str.")
            if _TOKEN.search(van_ban):
                raise DeidError("Văn bản đầu vào đã chứa mã tạm.")
            spans = self._known_spans(van_ban)
            if patterns:
                masked = van_ban
                for start, end, *_ in spans:
                    masked = masked[:start] + "\0" * (end - start) + masked[end:]
                for start, end, kind in find_pattern_spans(van_ban, masked):
                    original = van_ban[start:end]
                    spans.append((start, end, kind, original, original))
            return self._apply(van_ban, sorted(spans))
        except DeidError:
            raise
        except Exception as exc:
            raise DeidError("Không thể che định danh.") from exc

    def _apply(self, van_ban: str, spans: list[tuple[int, int, str, str, str]]) -> str:
        parts: list[str] = []
        cursor = 0
        for start, end, kind, key, shown in spans:
            parts.extend((van_ban[cursor:start], self._token(kind, key, shown)))
            cursor = end
        parts.append(van_ban[cursor:])
        return "".join(parts)

    def restore(self, van_ban: str) -> str:
        """Khôi phục mã tạm bằng bảng của phiên; mã lạ giữ nguyên."""
        return restore_text(van_ban, self._mapping)
