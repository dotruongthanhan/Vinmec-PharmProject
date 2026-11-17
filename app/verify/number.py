"""Trích xuất và đối chiếu con số trong nhận định của LLM với gói căn cứ."""

import math
import re
from collections.abc import Collection, Sequence

from app.llm.schema import GoiCanCu, NhanDinhDeXuat

_IGNORE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\[(?:HN|CCCD|SDT|BHYT|EMAIL|NGAY|TEN)_\d+\]"),
    re.compile(r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+(?![A-Za-z0-9_])"),
    re.compile(
        r"\b\d{4}-\d{1,2}-\d{1,2}(?:[T ]\d{1,2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?\b"
    ),
    re.compile(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{4}\b"),
    re.compile(r"\bngày\s+\d{1,2}/\d{1,2}\b", re.IGNORECASE),
    re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\b"),
    re.compile(r"\byếu\s+tố(?:\s+số)?\s+\d+(?:\s*[-–]\s*\d+)?\b", re.IGNORECASE),
)

_COUNT_UNIT = (
    r"(?:mg|mcg|µg|ug|ui|iu|đơn\s+vị|viên|ống|lọ|gói|liều|lần"
    r"|người|ca|ngày|giờ|tuần|tháng|năm|tuổi|chai|túi|vỉ|hộp|mũi|nhát|giọt|cfu"
    r"|(?:g|kg|ml|l)(?!\s*/\s*(?:phút|min|giờ|h)\b))"
)

_NUMBER_TOKEN = re.compile(
    rf"(?<![A-Za-z0-9_])(?:"
    rf"(?P<multi_thousand>[1-9]\d{{0,2}}(?:\.\d{{3}}){{2,}})\b"
    rf"|(?P<unit_thousand>[1-9]\d{{0,2}}\.\d{{3}})(?=\s*{_COUNT_UNIT}\b)"
    rf"|(?P<plain>\d+(?:[.,]\d+)?)"
    rf")",
    re.IGNORECASE,
)

_EN_THOUSAND_PATTERN = re.compile(r"(?<![A-Za-z0-9_])[1-9]\d{0,2}(?:,\d{3})+\b")
_CITATION_MARKER = re.compile(r"\[(\d+)\]")


def _mask_ignored(text: str) -> str:
    """Thay các đoạn mã bản ghi, ngày giờ và thứ tự yếu tố bằng khoảng trắng cùng độ dài."""
    masked = text
    for pattern in _IGNORE_PATTERNS:
        masked = pattern.sub(lambda match: " " * len(match.group(0)), masked)
    return masked


def _format_number_label(value: float) -> str:
    """Biểu diễn số ngắn gọn cho mã lỗi so_khong_co_nguon."""
    if value.is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _extract_number_pairs(text: str) -> list[tuple[float, str]]:
    """Tách danh sách (giá trị float, nhãn hiển thị) theo thứ tự xuất hiện."""
    masked = _mask_ignored(text)
    results: list[tuple[float, str]] = []
    for match in _NUMBER_TOKEN.finditer(masked):
        if match.group("multi_thousand") is not None:
            raw = match.group("multi_thousand")
            value = float(raw.replace(".", ""))
        elif match.group("unit_thousand") is not None:
            raw = match.group("unit_thousand")
            value = float(raw.replace(".", ""))
        else:
            raw = match.group("plain")
            value = float(raw.replace(",", "."))
        results.append((value, _format_number_label(value)))
    return results


def extract_numbers(text: str) -> list[float]:
    """Lấy mọi con số hợp lệ trong văn bản, bỏ qua mã bản ghi, ngày giờ và yếu tố."""
    return [value for value, _ in _extract_number_pairs(text)]


def numbers_in_text(text: str, *, include_en_thousands: bool = False) -> list[float]:
    """Lấy các con số trong văn bản, tuỳ chọn nhận dạng dấu phẩy hàng nghìn tiếng Anh."""
    numbers = extract_numbers(text)
    if include_en_thousands:
        for match in _EN_THOUSAND_PATTERN.finditer(_mask_ignored(text)):
            numbers.append(float(match.group(0).replace(",", "")))
    return numbers


def mask_citation_markers(text: str, citation_numbers: Collection[int]) -> str:
    """Thay các dấu trích dẫn [n] hợp lệ bằng khoảng trắng để tránh kiểm nhầm số liệu."""
    if not citation_numbers:
        return text
    allowed = set(citation_numbers)

    def _replace(match: re.Match[str]) -> str:
        if int(match.group(1)) in allowed:
            return " " * len(match.group(0))
        return match.group(0)

    return _CITATION_MARKER.sub(_replace, text)


def unverified_numbers(texts: Sequence[str], allowed_numbers: Sequence[float]) -> list[str]:
    """Tìm các số trong texts không có trong allowed_numbers theo sai số chuẩn."""
    errors: list[str] = []
    for text in texts:
        for num, label in _extract_number_pairs(text):
            matched = any(
                math.isclose(num, ref, rel_tol=1e-3, abs_tol=1e-6) for ref in allowed_numbers
            )
            if not matched:
                errors.append(f"so_khong_co_nguon:{label}")
    return list(dict.fromkeys(errors))


def check_numbers(de_xuat: NhanDinhDeXuat, goi: GoiCanCu) -> list[str]:
    """Kiểm tra mọi con số trong nhan_xet và de_xuat đều có nguồn trong gói căn cứ."""
    allowed_numbers = list(goi.so_cho_phep)
    cited_ids = {quote.doan_trich_id for quote in de_xuat.trich_dan}
    for chunk in goi.doan:
        if chunk.doan_trich_id in cited_ids:
            allowed_numbers.extend(
                numbers_in_text(
                    chunk.noi_dung_goc,
                    include_en_thousands=chunk.ngon_ngu == "en",
                )
            )

    texts_to_check = [de_xuat.nhan_xet]
    if de_xuat.de_xuat:
        texts_to_check.append(de_xuat.de_xuat)

    return unverified_numbers(texts_to_check, allowed_numbers)
