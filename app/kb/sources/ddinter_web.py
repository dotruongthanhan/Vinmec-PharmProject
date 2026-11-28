"""Đọc HTML và JSON của DDInter 2.0."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SOURCE = "DDInter 2.0"
LICENSE = "CC BY-NC-SA 4.0"
BASE = "https://ddinter2.scbdd.com"
ATTRIBUTION = {"nguon": SOURCE, "giay_phep": LICENSE}
TABLES = {
    "tuong_tac_thuoc": "interact-with",
    "tuong_tac_benh": "interact-with-dis",
    "tuong_tac_thuc_an": "interact-with-food",
    "che_pham_phoi_hop": "interact-with-multi",
}
DRUG_ID = re.compile(r"DDInter[0-9]+")
DRUG_LINK = re.compile(r"/server/drug-detail/(DDInter[0-9]+)/")
ATC = re.compile(r"\b[A-Z][0-9]{2}(?:[A-Z]{1,2}(?:[0-9]{2})?)?\b")
MECHANISMS = {
    "antagonistic_effect": "Antagonism",
    "synergistic_effect": "Synergy",
    "absorption": "Absorption",
    "distribution": "Distribution",
    "metabolism": "Metabolism",
    "excretion": "Excretion",
    "others": "Others",
}
LEVELS = {0: "Unknown", 1: "Minor", 2: "Moderate", 3: "Major"}
VOID = set("area base br col embed hr img input link meta param source track wbr".split())
BLOCK = set("br div p li tr td th section article ul ol h1 h2 h3 h4 h5 h6".split())


class ParseError(ValueError):
    """Phản hồi không đủ cấu trúc để lưu làm dữ liệu nguồn."""


@dataclass
class Element:
    tag: str = ""
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Element | str] = field(default_factory=list)

    def walk(self, *tags: str) -> Iterator[Element]:
        for child in self.children:
            if isinstance(child, Element):
                if not tags or child.tag in tags:
                    yield child
                yield from child.walk(*tags)

    def raw_text(self) -> str:
        if self.tag in {"style", "script", "template"}:
            return ""
        content = "".join(c if isinstance(c, str) else c.raw_text() for c in self.children)
        return f" {content} " if self.tag in BLOCK else content

    def text(self) -> str:
        return " ".join(self.raw_text().split())


class Document(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__()
        self.root = Element()
        self.stack = [self.root]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.handle_endtag("tr")
        if tag in {"td", "th"} and self.stack[-1].tag in {"td", "th"}:
            self.stack.pop()
        element = Element(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(element)
        if tag not in VOID:
            self.stack.append(element)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


class TablePage(BaseModel):
    """Trang DataTables đã kiểm tra kiểu dữ liệu."""

    model_config = ConfigDict(strict=True, extra="ignore")
    data: list[list[Any] | dict[str, Any]]
    recordsTotal: int = Field(ge=0)
    recordsFiltered: int | None = Field(default=None, ge=0)


def parse_table(body: bytes) -> TablePage:
    try:
        page = TablePage.model_validate_json(body)
    except ValidationError as exc:
        raise ParseError("Phản hồi bảng thiếu data hoặc recordsTotal hợp lệ") from exc
    if page.recordsFiltered not in (None, page.recordsTotal):
        raise ParseError("Bảng bị lọc trong yêu cầu lấy toàn bộ")
    return page


def fragment(value: Any) -> Element:
    if isinstance(value, list):
        return Element(children=[Element("li", children=[fragment(item)]) for item in value])
    if isinstance(value, (str, int, float)):
        return Document(str(value)).root
    return Element()


def value_text(value: Any) -> str | None:
    return fragment(value).text() or None


def severity_number(value: Any) -> int:
    if isinstance(value, str) and re.fullmatch(r"[0-3]", value.strip()):
        return int(value)
    if type(value) is int and value in LEVELS:
        return value
    raise ParseError(f"Mức độ DDInter không hợp lệ: {value!r}")


def interaction_id(value: Any) -> int | None:
    if type(value) is int and value > 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value) and int(value) > 0:
        return int(value)
    return None


def split_references(value: Any) -> list[str]:
    return [item for part in (value_text(value) or "").split("|") if (item := part.strip())]


def parse_drug(body: bytes, drug_id: str) -> dict[str, Any]:
    root = Document(body.decode("utf-8")).root
    fields: dict[str, Element] = {}
    for row in root.walk("tr"):
        cells = [child for child in row.children if isinstance(child, Element)]
        if len(cells) == 2 and all(cell.tag in {"td", "th"} for cell in cells):
            fields[cells[0].text().rstrip(":").casefold()] = cells[1]
    if fields.get("id", Element()).text() != drug_id:
        raise ParseError(f"Trang thuốc thiếu ID đúng: {drug_id}")
    name = re.search(r"\bDrugs? Information\s*:\s*(.+)", root.text(), re.I)
    title = next(
        (
            node.text().split(":", 1)[1].strip()
            for node in root.walk("h1", "h2", "h3", "h4", "h5", "h6")
            if re.match(r"Drugs? Information\s*:", node.text(), re.I)
        ),
        None,
    )
    if title is None and name:
        title = re.split(r"\s+Basic Information\b", name[1], maxsplit=1, flags=re.I)[0]
    links = {}
    for link in fields.get("useful links", Element()).walk("a"):
        label = link.text().casefold()
        key = "pubchem" if label.startswith("pubchem") else re.sub(r"\W+", "_", label).strip("_")
        if key and link.attrs.get("href"):
            links.setdefault(key, urljoin(BASE, link.attrs["href"]))
    return {
        "ddinter_id": drug_id,
        "ten": title or None,
        "loai_thuoc": fields.get("drug type", Element()).text() or None,
        "ma_atc": list(
            dict.fromkeys(ATC.findall(fields.get("atc classification", Element()).text()))
        ),
        "cas": fields.get("cas number", Element()).text() or None,
        "mo_ta": fields.get("description", Element()).text() or None,
        "lien_ket": links,
        "tong_tuong_tac_tren_trang": {kind: None for kind in TABLES},
    }


TABLE_COLUMN_COUNTS = dict(zip(TABLES, (5, 4, 6, 5), strict=True))
COMBINATION_COLUMNS = (
    ("multi_drug_trade", "trade", "trade_name"),
    ("multi_drug", "drug", "name"),
    ("drug_type", "type"),
    ("warning",),
    ("note",),
)


def combination_cells(row: list[Any] | dict[str, Any]) -> list[Any]:
    kind = "che_pham_phoi_hop"
    columns = COMBINATION_COLUMNS
    if isinstance(row, list):
        if len(row) != len(columns):
            raise ParseError(f"{kind}: số cột không hợp lệ ({len(row)})")
        return row
    normalized = {re.sub(r"[^a-z0-9]+", "_", key.casefold()): value for key, value in row.items()}
    if all(str(i) in normalized for i in range(len(columns))):
        return [normalized[str(i)] for i in range(len(columns))]
    if not any(key in normalized for names in columns for key in names):
        raise ParseError(f"{kind}: cột JSON chưa được nhận diện: {', '.join(row)}")
    return [
        next((normalized[key] for key in names if key in normalized), None) for names in columns
    ]


def parse_row(
    kind: str, row: list[Any] | dict[str, Any], drug_id: str, name: str | None
) -> dict[str, Any]:
    if kind == "che_pham_phoi_hop":
        texts = [value_text(item) for item in combination_cells(row)]
        keys = ("ten_thuong_mai", "ten_phoi_hop", "loai_thuoc", "canh_bao", "ghi_chu")
        return {
            "ddinter_id": drug_id,
            **dict(zip(keys, texts, strict=True)),
            "cot_goc": row,
        }
    if not isinstance(row, dict):
        raise ParseError(f"{kind}: dòng JSON không phải đối tượng")
    level = severity_number(row.get("level"))
    if kind == "tuong_tac_thuoc":
        other = row.get("drug_id")
        if not isinstance(other, str) or not DRUG_ID.fullmatch(other):
            raise ParseError(f"{drug_id}: dòng thuốc–thuốc thiếu ID đối tác")
        endpoints = sorted(
            ((drug_id, name), (other, value_text(row.get("drug_name")))),
            key=lambda endpoint: endpoint[0],
        )
        return {
            "ddinter_id_a": endpoints[0][0],
            "ddinter_id_b": endpoints[1][0],
            "ten_a": endpoints[0][1],
            "ten_b": endpoints[1][1],
            "muc_do": LEVELS[level],
            "muc_do_so": level,
            "co_che": [label for key, label in MECHANISMS.items() if row.get(key) == "1"],
            "ma_trang_cap": interaction_id(row.get("interaction_id")),
            "tu_trang_cua": drug_id,
            "cot_goc": row,
        }

    shared = {
        "ddinter_id": drug_id,
        "muc_do": LEVELS[level],
        "tai_lieu": split_references(row.get("references")),
    }
    if kind == "tuong_tac_benh":
        return {
            **shared,
            "ten_benh": value_text(row.get("diseaseName")),
            "noi_dung": value_text(row.get("text")),
            "ma_trang": interaction_id(row.get("interaction_id")),
        }
    mechanism = value_text(row.get("magnesium"))
    return {
        **shared,
        "thuc_an": value_text(row.get("foodName")),
        "mo_ta": value_text(row.get("newInteraction")),
        "xu_tri": value_text(row.get("newManagement")),
        "co_che": [mechanism] if mechanism else [],
    }


def alternative(node: Element, script: str, side: str) -> dict[str, Any]:
    match = ATC.search(node.text())
    # Danh sách đầy đủ nằm trong chuỗi HTML của nút More.
    hidden_links = re.findall(
        rf"all_candidate_{side}_html\s*\+=\s*'(<a\b[^']*</a>)'",
        script,
    )
    names = [
        anchor.text()
        for part in (node, fragment(" ".join(hidden_links)))
        for anchor in part.walk("a")
        if DRUG_LINK.fullmatch(anchor.attrs.get("href", "")) and anchor.text()
    ]
    return {"ma_atc": match[0] if match else None, "thuoc": list(dict.fromkeys(names))}


def parse_pair(body: bytes, pair: dict[str, Any]) -> dict[str, Any]:
    root = Document(body.decode("utf-8")).root
    main = next(root.walk("main"), Element())
    header = next((node for node in main.walk() if node.attrs.get("role") == "alert"), Element())
    title = next(
        (node for node in header.walk("span") if node.text().startswith("Interaction between ")),
        Element(),
    )
    names = [node.text() for node in title.walk("strong")]
    if len(names) != 2 or not all(names):
        raise ParseError("Trang cặp thiếu tiêu đề Interaction between")

    fields = {}
    for row in main.walk("tr"):
        columns = list(row.walk("td"))
        if len(columns) == 2 and "key" in columns[0].attrs.get("class", "").split():
            fields[columns[0].text().casefold()] = columns[1]

    ids = [
        match[1]
        for anchor in fields.get("id", Element()).walk("a")
        if (match := DRUG_LINK.fullmatch(anchor.attrs.get("href", "")))
    ]
    if sorted(ids) != sorted((pair["ddinter_id_a"], pair["ddinter_id_b"])):
        raise ParseError("ID trên trang chi tiết không khớp cặp thuốc")

    badges = [
        node.text()
        for node in header.walk("span")
        if "badge" in node.attrs.get("class", "").split()
    ]
    references = [
        node.text()
        for node in fields.get("references", Element()).walk("span")
        if re.match(r"\[\d+\]", node.text())
    ]
    scripts = "\n".join(
        child for node in root.walk("script") for child in node.children if isinstance(child, str)
    )
    subtitles = main.walk()
    cyp = None
    if any(
        "sub-title" in node.attrs.get("class", "").split()
        and node.text().casefold() == "potential metabolism interactions"
        for node in subtitles
    ):
        cyp = next((node.text() for node in subtitles if node.tag == "blockquote"), None)
    return {
        "ma_trang_cap": pair["ma_trang_cap"],
        "ddinter_id_a": ids[0],
        "ddinter_id_b": ids[1],
        "ten_a": names[0],
        "ten_b": names[1],
        "muc_do": next((label for label in badges if label in LEVELS.values()), None),
        "co_che": list(dict.fromkeys(label for label in badges if label in MECHANISMS.values())),
        "hau_qua": fields.get("interaction", Element()).text() or None,
        "xu_tri": fields.get("management", Element()).text() or None,
        "tai_lieu": references,
        "thay_the_a": alternative(
            fields.get(f"alternative for {names[0].casefold()}", Element()), scripts, "a"
        ),
        "thay_the_b": alternative(
            fields.get(f"alternative for {names[1].casefold()}", Element()), scripts, "b"
        ),
        "cyp_tho": cyp or None,
    }
