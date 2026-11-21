"""Che định danh theo mẫu (lớp 2) và khôi phục văn bản bằng bảng ánh xạ tại chỗ."""

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


# Mẫu regex nhận diện thẻ ẩn danh nội bộ, không phải bí mật hay token xác thực.
TOKEN_PATTERN = r"\[(?:HN|CCCD|SDT|BHYT|EMAIL|NGAY|TEN|DIACHI|MA)_\d+\]"  # noqa: S105  # mẫu regex
_TOKEN = re.compile(TOKEN_PATTERN)
_DAY = r"(?:0?[1-9]|[12][0-9]|3[01])"
_MONTH = r"(?:0?[1-9]|1[0-2])"
_UPPER = "A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝĂĐĨŨƠƯẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼẾỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴỶỸ"
_NAME_WORD = rf"[{_UPPER}](?:[^\W\d_]|[̀-ͯ])*"
_ANY_WORD = r"(?:[^\W\d_]|[̀-ͯ])+"
_SPACE = r"[^\S\r\n]"
# Chữ đệm thường gặp để nhận ra họ tên viết thường như "Trần thị hoa".
_PARTICLE = r"(?:[Tt]hị|[Vv]ăn)"
_LOWER_SURNAME = (
    r"(?:nguyễn|trần|lê|phạm|hoàng|huỳnh|phan|vũ|võ|đặng|bùi|đỗ|hồ|ngô|dương|lý|đinh|trịnh)"
)
_DOSE_UNIT = re.compile(r" ?(?:viên|ống|lọ|gói|liều|mg|mcg|ml|g)(?!\w)", re.IGNORECASE)
_DOSE_PREFIX = re.compile(r"(?<!\w)(?:liều|tỉ lệ|tỷ lệ):? ?\Z", re.IGNORECASE)
_HN_UNIT = re.compile(
    r" ?(?:mmHg|/L|/l|/uL|/µL|/mm3|G/L|T/L|U/L|IU/mL|IU/ml|copies/mL|copies/ml"
    r"|mg|ml|mL|umol/L|µmol/L|mmol/L)(?![^\W\d_])"
)
# Từ khóa quan hệ: sau đó là họ tên người nhà. Nhóm mạnh chấp nhận tên một từ.
_STRONG_CONTEXT = {
    "người nhà",
    "thân nhân",
    "người thân",
    "người liên hệ",
    "người bảo hộ",
    "người đại diện",
    "người giám hộ",
    "người bảo lãnh",
    "họ tên",
    "họ và tên",
}
# Dấu chấm trong địa chỉ không kết thúc câu: viết tắt (TP.), số thập phân, hoặc nối tiếp.
_ADDRESS_ABBREVIATION = r"(?:(?<=TP)|(?<=TX)|(?<=Tp)|(?<=Tx)|(?<=Q)|(?<=P)|(?<=X)|(?<=H)|(?<=T))\."
_ADDRESS_CHAR = (
    rf"(?:[^\n\0;.]|{_ADDRESS_ABBREVIATION}|\.(?![^\S\r\n]|$)|\.(?={_SPACE}+[a-zà-ỹ\d])"
    r")"
)
_ADDRESS_END = (
    r"(?=[^\S\r\n]*(?:\n|\0|;|$|\."
    r"|,?[^\S\r\n]*(?i:sđt|sdt|đt|điện\s+thoại|bhyt|cccd|liên\s+hệ|người\s+nhà)(?!\w)))"
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
            rf"(?<![\d-])\d{{4}}(?P<isep>[-/.]){_MONTH}(?P=isep){_DAY}(?![\d-])"
            rf"|(?<!\d){_DAY}(?P<sep>[/.-]){_MONTH}(?P=sep)\d{{4}}(?!\d)"
            rf"|(?P<short_date>(?<![\d/.,]){_DAY}/{_MONTH}(?![\d/]|[.,;:)]\d))"
        ),
    ),
    (
        "DIACHI",
        re.compile(
            r"(?<!\w)(?i:địa\s+chỉ|đ/c|đc|trú\s+tại|thường\s+trú(?:\s+tại)?"
            r"|tạm\s+trú(?:\s+tại)?|số\s+nhà)(?!\w)"
            r"(?:[^\S\r\n]*[:：-][^\S\r\n]*|[^\S\r\n]+)"
            rf"(?P<address>(?=[^\n\0;]*[\d{_UPPER}]){_ADDRESS_CHAR}{{3,100}}?){_ADDRESS_END}"
        ),
    ),
    (
        "TEN",
        re.compile(
            r"(?<!\w)(?P<title>(?i:BN|bệnh nhân|người bệnh|BS|bác sĩ|ĐD|điều dưỡng"
            r"|DS|dược sĩ|ông|bà|anh|chị))"
            rf"(?!\w)(?:[.:]{_SPACE}*|{_SPACE}+)"
            rf"(?P<name>{_NAME_WORD}{_SPACE}+{_PARTICLE}{_SPACE}+{_ANY_WORD}"
            rf"(?:{_SPACE}+{_NAME_WORD})?"
            rf"|{_LOWER_SURNAME}{_SPACE}+{_PARTICLE}{_SPACE}+{_ANY_WORD}"
            rf"|{_NAME_WORD}(?:{_SPACE}+{_NAME_WORD}){{0,3}})(?!\w)"
        ),
    ),
    (
        "TEN",
        re.compile(
            r"(?<!\w)(?P<context>(?i:người nhà|thân nhân|người thân|người liên hệ"
            r"|người bảo hộ|người đại diện|người giám hộ|người bảo lãnh|họ và tên|họ tên"
            r"|vợ|chồng|con trai|con gái|con|mẹ|bố|cha|cháu))"
            rf"(?!\w)(?:[.:]{_SPACE}*|{_SPACE}+)"
            rf"(?P<name>{_NAME_WORD}(?:{_SPACE}+{_NAME_WORD}){{0,3}})(?!\w)"
        ),
    ),
)


def _normalize_context(label: str) -> str:
    """Chuẩn hoá từ khóa ngữ cảnh để tra nhóm mạnh."""
    return " ".join(label.casefold().split())


def find_pattern_spans(van_ban: str, search_text: str) -> list[tuple[int, int, str]]:
    """Quét các mẫu lớp 2 trên search_text; vùng đã che bằng "\\0" bị bỏ qua.

    van_ban dùng để kiểm đơn vị và tiền tố; search_text cùng độ dài van_ban.
    """
    spans: list[tuple[int, int, str]] = []
    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(search_text):
            groups = match.groupdict()
            if kind == "DIACHI":
                start, end = match.span("address")
            elif kind == "TEN":
                start, end = match.span("name")
            else:
                start, end = match.span()
            if kind == "HN" and _HN_UNIT.match(van_ban, end):
                continue
            if (
                kind == "NGAY"
                and groups.get("short_date") is not None
                and (_DOSE_UNIT.match(van_ban, end) or _DOSE_PREFIX.search(van_ban[:start]))
            ):
                continue
            if kind == "TEN":
                title = groups.get("title")
                name = match.group("name")
                if (
                    title is not None
                    and title.casefold() in {"bn", "bệnh nhân", "người bệnh"}
                    and name in {"Nam", "Nữ"}
                ):
                    continue
                context = groups.get("context")
                if (
                    context is not None
                    and _normalize_context(context) not in _STRONG_CONTEXT
                    and len(name.split()) < 2
                ):
                    continue
            spans.append((start, end, kind))
            # Giữ nguyên vị trí, chặn mẫu sau đọc lại phần đã che.
            search_text = search_text[:start] + "\0" * (end - start) + search_text[end:]
    return spans


def scrub_text(van_ban: str) -> ScrubResult:
    """Che theo ưu tiên, cấp mã theo thứ tự xuất hiện và đóng khi lỗi."""
    try:
        if not isinstance(van_ban, str):
            raise DeidError("Văn bản đầu vào phải là str.")
        if _TOKEN.search(van_ban):
            raise DeidError("Văn bản đầu vào đã chứa mã tạm.")

        spans = find_pattern_spans(van_ban, van_ban)

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
