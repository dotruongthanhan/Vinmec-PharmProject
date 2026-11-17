"""Che định danh và khôi phục văn bản bằng bảng ánh xạ tại chỗ."""

import re

from pydantic import BaseModel


class ThayThe(BaseModel):
    """Một mã tạm được cấp cho giá trị định danh."""

    loai: str
    ma_tam: str


class ScrubResult(BaseModel):
    """Văn bản đã che cùng thông tin khôi phục tại chỗ."""

    van_ban: str
    thay_the: list[ThayThe]
    anh_xa: dict[str, str]


class DeidError(Exception):
    """Không thể che định danh an toàn."""


_TOKEN = re.compile(r"\[(HN|CCCD|SDT|BHYT|EMAIL|NGAY|TEN)_\d+\]")
_DAY = r"(?:0?[1-9]|[12][0-9]|3[01])"
_MONTH = r"(?:0?[1-9]|1[0-2])"
_UPPER = "A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝĂĐĨŨƠƯẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼẾỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴỶỸ"
_NAME_WORD = rf"[{_UPPER}](?:[^\W\d_]|[\u0300-\u036f])*"
_SPACE = r"[^\S\r\n]"
_DOSE_UNIT = re.compile(r" ?(?:viên|ống|lọ|gói|liều|mg|mcg|ml|g)(?!\w)", re.IGNORECASE)
_DOSE_PREFIX = re.compile(r"(?<!\w)(?:liều|tỉ lệ|tỷ lệ):? ?\Z", re.IGNORECASE)
_HN_UNIT = re.compile(
    r" ?(?:mmHg|/L|/l|/uL|/µL|/mm3|G/L|T/L|U/L|IU/mL|IU/ml|copies/mL|copies/ml"
    r"|mg|ml|mL|umol/L|µmol/L|mmol/L)(?![^\W\d_])"
)
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "EMAIL",
        re.compile(r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+"),
    ),
    ("BHYT", re.compile(r"(?<!\w)[A-Za-z]{2}\d{13}(?!\w)")),
    ("CCCD", re.compile(r"(?<!\d)(?<!\d[.,])\d{12}(?!\d|[.,]\d)")),
    (
        "SDT",
        re.compile(r"(?<![\d+])(?<!\d[.,])(?:0|\+?84)[ .-]*[35789](?:[ .-]*\d){8}(?!\d|[.,]\d)"),
    ),
    ("HN", re.compile(r"(?<!\d)(?<!\d[.,])\d{9}(?!\d|[.,]\d)")),
    (
        "NGAY",
        re.compile(
            rf"(?<!\d){_DAY}(?P<sep>[/.-]){_MONTH}(?P=sep)\d{{4}}(?!\d)"
            rf"|(?P<short_date>(?<![\d/.,]){_DAY}/{_MONTH}(?![\d/]|[.,;:)]\d))"
        ),
    ),
    (
        "TEN",
        re.compile(
            r"(?<!\w)(?P<title>(?i:BN|bệnh nhân|người bệnh|BS|bác sĩ|ĐD|điều dưỡng"
            r"|DS|dược sĩ|ông|bà|anh|chị))"
            rf"(?!\w)(?:[.:]{_SPACE}*|{_SPACE}+)"
            rf"(?P<name>{_NAME_WORD}(?:{_SPACE}+{_NAME_WORD}){{0,3}})(?!\w)"
        ),
    ),
)


def scrub_text(van_ban: str) -> ScrubResult:
    """Che theo ưu tiên, cấp mã theo thứ tự xuất hiện và đóng khi lỗi."""
    try:
        if not isinstance(van_ban, str):
            raise DeidError("Văn bản đầu vào phải là str.")
        if _TOKEN.search(van_ban):
            raise DeidError("Văn bản đầu vào đã chứa mã tạm.")

        spans: list[tuple[int, int, str]] = []
        search_text = van_ban
        for kind, pattern in _PATTERNS:
            for match in pattern.finditer(search_text):
                start, end = match.span("name") if kind == "TEN" else match.span()
                if kind == "HN" and _HN_UNIT.match(van_ban, end):
                    continue
                if (
                    kind == "NGAY"
                    and match.group("short_date") is not None
                    and (_DOSE_UNIT.match(van_ban, end) or _DOSE_PREFIX.search(van_ban[:start]))
                ):
                    continue
                if (
                    kind == "TEN"
                    and match.group("title").casefold() in {"bn", "bệnh nhân", "người bệnh"}
                    and match.group("name") in {"Nam", "Nữ"}
                ):
                    continue
                spans.append((start, end, kind))
                # Giữ nguyên vị trí, chặn mẫu sau đọc lại phần đã che.
                search_text = search_text[:start] + "\0" * (end - start) + search_text[end:]

        counts: dict[str, int] = {}
        tokens: dict[str, str] = {}
        replacements: list[ThayThe] = []
        mapping: dict[str, str] = {}
        parts: list[str] = []
        cursor = 0
        for start, end, kind in sorted(spans):
            original = van_ban[start:end]
            if original not in tokens:
                counts[kind] = counts.get(kind, 0) + 1
                token = f"[{kind}_{counts[kind]}]"
                tokens[original] = token
                mapping[token] = original
                replacements.append(ThayThe(loai=kind, ma_tam=token))
            parts.extend((van_ban[cursor:start], tokens[original]))
            cursor = end
        parts.append(van_ban[cursor:])
        return ScrubResult(van_ban="".join(parts), thay_the=replacements, anh_xa=mapping)
    except DeidError:
        raise
    except Exception as exc:
        raise DeidError("Không thể che định danh.") from exc


def restore_text(van_ban: str, anh_xa: dict[str, str]) -> str:
    """Khôi phục từng mã một lần, giữ nguyên mã không có trong ánh xạ."""
    return _TOKEN.sub(lambda match: anh_xa.get(match.group(), match.group()), van_ban)
