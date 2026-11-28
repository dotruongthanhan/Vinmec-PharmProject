"""Tách thành phần ở cấp ngoài cùng, giữ nguyên dữ kiện hàm lượng."""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel

from app.kb.names import _SALT_TOKENS, normalize_key

_SALTS = _SALT_TOKENS | {
    "acetat",
    "besilat",
    "besylat",
    "chlorid",
    "clorid",
    "dihydrat",
    "gluconat",
    "hemihydrat",
    "hydrat",
    "lactat",
    "monohydrat",
    "nitrat",
    "phosphat",
    "fumarat",
}
_PREFIX_SALTS = {
    "kali clavulanat": "clavulanat",
    "potassium clavulanate": "clavulanate",
    "sodium valproate": "valproate",
}
_STANDARD = re.compile(
    r"(?<!\w)(?:USP|BP|EP|DĐVN|DDVN|JP|Ph\s*\.\s*Eur\.?)"
    r"(?:\s*[-–]?\s*(?:20\d{2}|19\d{2}|I{1,3}|IV|VI?|VII|VIII|IX|X))?(?!\w)",
    re.I,
)
_FORM = re.compile(r"\(\s*(?:dưới dạng|duoi dang|dạng|dang|as)\s+([^()]+)\)", re.I)
_EQUIV_TEXT = r"(?:tương đương(?:\s+với)?|tuong duong(?:\s+voi)?|eq\.\s*to)"
_EQUIVALENT = re.compile(rf"\s*{_EQUIV_TEXT}\s*", re.I)
_PAREN_EQUIVALENT = re.compile(rf"\(\s*({_EQUIV_TEXT}\s+[^()]+)\)\s*$", re.I)
# Tiền tố mô tả liều dùng: "Mỗi viên chứa:", "Lọ 12ml chứa:", "Trong mỗi ống 10ml dung dịch chứa".
_CONTAINER = re.compile(
    r"^\s*(?:mỗi|trong mỗi|trong|lọ|chai|ống|gói|viên|\d[\d.,]*\s*(?:ml|g|mg|l)\b)"
    r"[^:;()]{0,70}?\s(?:có\s+)?chứa\s*:?\s*",
    re.I,
)
_NUM = r"\d+(?:[.,]\d+)?"
_UNIT = r"(?:mg|mcg|[µμu]g|kg|gam|g|ml|l|mmol|mol|mEq|IU|UI|đvqt|dvqt|%|đv|units?)"
_STRENGTH = re.compile(
    rf"(?<![\w.,])(?P<value>{_NUM})\s*(?P<unit>{_UNIT}"
    rf"(?:\s*/\s*(?:{_NUM}\s*)?(?:ml|l|g|mg|liều|viên))?)$",
    re.I,
)
_RATIO = re.compile(rf"(?P<numbers>{_NUM}(?:\s*/\s*{_NUM})+)\s*(?P<unit>{_UNIT})", re.I)
_STRENGTH_IN_NAME = re.compile(rf"(?<!\w){_NUM}\s*{_UNIT}(?!\w)", re.I)
_BIO = re.compile(r"\b(?:vac\s?xin|vaccin(?:e)?|sinh pham|khang nguyen)\b")
_HERBAL = re.compile(
    r"\b(?:duoc lieu|dong duoc|thuoc co truyen|cao (?:kho|dac|long)|"
    r"extract(?:um)?|radix|rhizoma|folium|flos|fructus|herba|cortex|semen)\b"
)
_MINERAL_PREFIXES = {
    "natri",
    "sodium",
    "kali",
    "potassium",
    "calcium",
    "canxi",
    "magnesium",
    "magnesi",
    "iron",
    "zinc",
    "kem",
    "dong",
    "sat",
    "copper",
    "ferrous",
    "ferric",
    "manganese",
    "mangan",
    "aluminium",
    "aluminum",
    "nhom",
    "ammonium",
    "amoni",
    "lithium",
}


class Component(BaseModel):
    ten_hoat_chat_goc: str
    ten_chuan_hoa: str
    dang_muoi: str | None = None
    ham_luong: float | None = None
    don_vi: str | None = None


class SplitResult(BaseModel):
    thanh_phan: list[Component]
    trang_thai: Literal["tach_duoc", "chua_khop"]
    ly_do: str | None = None
    loai_san_pham: Literal["thuoc", "duoc_lieu", "sinh_pham"] = "thuoc"


def has_strength(name: str) -> bool:
    """Nhận diện số kèm đơn vị hàm lượng trong tên."""
    return bool(_STRENGTH_IN_NAME.search(name))


def split_salt(name: str) -> tuple[str, str | None]:
    """Giữ các hợp chất mà phần còn lại chỉ là tên ion hoặc axit."""
    if prefix_base := _PREFIX_SALTS.get(normalize_key(name)):
        return prefix_base, name.split()[0]
    tokens = name.split()
    end = len(tokens)
    while end > 1 and normalize_key(tokens[end - 1]) in _SALTS:
        end -= 1
    base = " ".join(tokens[:end])
    base_key = normalize_key(base)
    if end == len(tokens) or base_key in _MINERAL_PREFIXES | _SALTS | {"acid", "axit"}:
        return name, None
    return base, " ".join(tokens[end:])


def _fragments(text: str) -> list[str]:
    parts: list[str] = []
    stack: list[str] = []
    start = pos = 0
    while pos < len(text):
        char = text[pos]
        if char in "([":
            stack.append(")" if char == "(" else "]")
        elif char in ")]":
            if not stack or stack.pop() != char:
                raise ValueError("ngoac_khong_can_bang")
        elif not stack:
            connector = re.match(r"\s+v[àa]\s+", text[pos:], re.I) if char.isspace() else None
            decimal = (
                char == "," and text[pos - 1 : pos].isdigit() and text[pos + 1 : pos + 2].isdigit()
            )
            chemical = char == "," and bool(re.match(r"[a-z0-9]+-", text[pos + 1 :], re.I))
            dose_slash = char == "/" and bool(
                re.search(r"\d\s*(?:" + _UNIT + r")?\s*$", text[start:pos], re.I)
                and re.match(r"\s*(?:\d|" + _UNIT + r"\b|liều\b|viên\b)", text[pos + 1 :], re.I)
            )
            charge = char == "+" and bool(re.match(r"\s*\)", text[pos + 1 :]))
            if (char in ";,+/" and not (decimal or chemical or dose_slash or charge)) or connector:
                parts.append(text[start:pos].strip())
                pos += len(connector[0]) if connector else 1
                start = pos
                continue
        pos += 1
    if stack:
        raise ValueError("ngoac_khong_can_bang")
    return [*parts, text[start:].strip()]


def _amount(match: re.Match[str]) -> tuple[float, str]:
    unit = re.sub(r"\s+", "", match["unit"])
    if unit.lower() == "gam":
        unit = "g"
    return float(match["value"].replace(",", ".")), unit


def _component(fragment: str) -> Component:
    forms = _FORM.findall(fragment)
    if len(forms) > 1:
        raise ValueError("nhieu_dang_muoi")
    text = _STANDARD.sub("", _FORM.sub(" ", fragment)).strip()
    text = _PAREN_EQUIVALENT.sub(r"\1", text)
    text = re.sub(r"\(\s*\)|\[\s*\]", "", text).strip()
    # "Lansoprazole (30mg)": ngoặc chỉ chứa hàm lượng thì coi như hàm lượng ngay sau tên.
    text = re.sub(rf"\(\s*({_NUM}\s*{_UNIT})\s*\)\s*$", r" \1", text, flags=re.I).strip()
    equivalent = _EQUIVALENT.split(text)
    if len(equivalent) > 2:
        raise ValueError("tuong_duong_khong_ro")
    candidate = equivalent[-1]
    if len(equivalent) == 2:
        left = _STRENGTH.sub("", equivalent[0]).strip()
        right = _STRENGTH.sub("", candidate).strip()
        if not left:
            raise ValueError("tuong_duong_khong_ro")
        if not _STRENGTH.search(candidate):
            # "Ceftriaxone natri tương đương Ceftriaxone": cùng gốc, hàm lượng lấy ở cột riêng.
            left_base, left_salt = split_salt(left)
            if not left_salt or normalize_key(left_base) != normalize_key(candidate):
                raise ValueError("tuong_duong_khong_ro")
            forms.append(left)
            text_name = left_base
            return Component(
                ten_hoat_chat_goc=text_name,
                ten_chuan_hoa=normalize_key(left_base),
                dang_muoi=left_salt,
            )
        if right:
            left_base, left_salt = split_salt(left)
            if normalize_key(left_base) != normalize_key(right):
                raise ValueError("tuong_duong_khong_ro")
            if left_salt and not forms:
                forms.append(left)
        else:
            candidate = f"{left} {candidate}"
    match = _STRENGTH.search(candidate)
    # Số trong tên có thể thuộc về tên hóa học, chỉ nhận số kèm đơn vị.
    name = candidate[: match.start()].strip(" :-") if match else candidate.strip()
    if not name or re.search(r"[()\[\]:;+/=%<>]", name) or not any(c.isalpha() for c in name):
        raise ValueError("ten_thanh_phan_khong_ro")
    if re.search(r"\b(?:ta duoc|vua du|thanh phan|hon hop|khong ro|n a)\b", normalize_key(name)):
        raise ValueError("ten_thanh_phan_khong_ro")
    if re.search(r"\d\s*(?:" + _UNIT + r")(?!\w)", name, re.I):
        raise ValueError("ham_luong_noi_tuyen_khong_ro")
    base, salt = split_salt(name)
    strength, unit = _amount(match) if match else (None, None)
    return Component(
        ten_hoat_chat_goc=name,
        ten_chuan_hoa=normalize_key(base),
        dang_muoi=forms[0].strip() if forms else salt,
        ham_luong=strength,
        don_vi=unit,
    )


def _strengths(text: str, count: int) -> list[tuple[float, str] | None]:
    ratio = _RATIO.fullmatch(text.strip())
    if ratio and count > 1:
        numbers = re.split(r"\s*/\s*", ratio["numbers"])
        if len(numbers) == count:
            return [(float(number.replace(",", ".")), ratio["unit"]) for number in numbers]
    parts = _fragments(text)
    if len(parts) != count:
        return [None] * count
    matches = [_STRENGTH.fullmatch(part) for part in parts]
    return [_amount(match) if match else None for match in matches]


def split_herbal_names(raw: str) -> list[Component]:
    """Đọc tên từ mô tả dược liệu đã được T50 gắn cờ, chỉ để báo cáo."""
    try:
        text = _CONTAINER.sub("", unicodedata.normalize("NFC", raw), count=1)
        return [_component(part) for part in _fragments(text)]
    except ValueError:
        return []


def split_components(
    hoat_chat_goc: str | None,
    ham_luong_goc: str | None,
    *,
    context: str = "",
) -> SplitResult:
    """Chỉ tách khi cấu trúc rõ, giữ hàm lượng chưa biết dưới dạng null."""
    # Dữ liệu thật của Cục Quản lý Dược có dấu tiếng Việt dạng tổ hợp (NFD): đưa về NFC.
    hoat_chat_goc = unicodedata.normalize("NFC", hoat_chat_goc) if hoat_chat_goc else hoat_chat_goc
    ham_luong_goc = unicodedata.normalize("NFC", ham_luong_goc) if ham_luong_goc else ham_luong_goc
    clue = normalize_key(f"{hoat_chat_goc or ''} {context}")
    kind = "sinh_pham" if _BIO.search(clue) else "duoc_lieu" if _HERBAL.search(clue) else "thuoc"
    if not hoat_chat_goc or not normalize_key(hoat_chat_goc):
        return SplitResult(
            thanh_phan=[], trang_thai="chua_khop", ly_do="thieu_hoat_chat_goc", loai_san_pham=kind
        )
    try:
        fragments = _fragments(_CONTAINER.sub("", hoat_chat_goc, count=1))
        if kind == "duoc_lieu" and len(fragments) > 1:
            raise ValueError("duoc_lieu_can_duyet")
        parts = [_component(part) for part in fragments]
    except ValueError as exc:
        return SplitResult(
            thanh_phan=[], trang_thai="chua_khop", ly_do=str(exc), loai_san_pham=kind
        )
    keys = [part.ten_chuan_hoa for part in parts]
    if len(set(keys)) != len(keys):
        return SplitResult(
            thanh_phan=[],
            trang_thai="chua_khop",
            ly_do="thanh_phan_trung_lap",
            loai_san_pham=kind,
        )
    if ham_luong_goc and ham_luong_goc.strip():
        try:
            strengths = _strengths(ham_luong_goc, len(parts))
        except ValueError:
            strengths = [None] * len(parts)
        for part, amount in zip(parts, strengths, strict=True):
            if amount is None:
                continue  # hàm lượng chung không tách được: giữ hàm lượng nội tuyến nếu có
            if part.ham_luong is None:
                part.ham_luong, part.don_vi = amount
            elif (part.ham_luong, part.don_vi.lower() if part.don_vi else None) != (
                amount[0],
                amount[1].lower(),
            ):
                part.ham_luong = part.don_vi = None
    return SplitResult(thanh_phan=parts, trang_thai="tach_duoc", loai_san_pham=kind)
