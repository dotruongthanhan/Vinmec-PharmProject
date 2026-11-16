"""Bo doc, lam sach va chuan hoa nhan thuoc openFDA thanh LabelDocument."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

from pydantic import BaseModel, Field

from app.kb.names import DrugNameIndex

_INVISIBLE_CHARS_RE = re.compile(r"[\u200b-\u200f\ufeff\u00ad]")
_PAREN_REF_RE = re.compile(r"\(\s*\d{1,2}\.\d{1,2}(?:\s*[,;-]\s*\d{1,2}\.\d{1,2})*\s*\)")
_LEADING_MAJOR_RE = re.compile(r"^\s*(\d{1,2})\s+(?=[A-Z][A-Z&,\s/-]{2,})")
_MAJOR_HEADING_RE = re.compile(
    r"(?:^|(?<=\s))(\d{1,2})\s+"
    r"((?:INDICATIONS|DOSAGE|CONTRAINDICATIONS|WARNINGS|PRECAUTIONS|ADVERSE|"
    r"DRUG|USE|OVERDOSAGE|CLINICAL|BOXED|PEDIATRIC|GERIATRIC|PREGNANCY|"
    r"LACTATION|GENERAL|PHARMACOKINETICS|MECHANISM)[A-Z&,\s/-]{0,60})"
)
_SUBSECTION_RE = re.compile(r"(?:^|(?<=\s))(\d{1,2})\.(\d{1,2})\s+([A-Z][A-Za-z0-9'/,()\-]+)")
_XREF_BEFORE_RE = re.compile(
    r"(?:see|section|table|figure|step|item|under|in|to)\s+$",
    re.IGNORECASE,
)
_BOILERPLATE_STUB_RE = re.compile(
    r"^(?:\d{1,2}(?:\.\d{1,2})?\s+[A-Z&,\s/-]+\s+)?(?:"
    r"none\.?|none known\.?|not applicable\.?|no data available\.?|"
    r"see\s+.{1,60}(?:section|warnings|precautions|information)\.?"
    r")$",
    re.IGNORECASE,
)
_BODY_SENTENCE_RE = re.compile(
    r"[A-Z][A-Za-z'-]* (?:[a-z][a-z'-]* )?(?:should|must|may|can|will|is|are|was|were|has|have)\b"
)

_SKIP_FIELDS: frozenset[str] = frozenset(
    {
        "set_id",
        "id",
        "effective_time",
        "version",
        "openfda",
        "spl_product_data_elements",
        "package_label_principal_display_panel",
        "how_supplied",
        "storage_and_handling",
        "clinical_studies",
        "nonclinical_toxicology",
        "carcinogenesis_and_mutagenesis_and_impairment_of_fertility",
        "references",
        "description",
        "microbiology",
        "information_for_patients",
        "recent_major_changes",
        "spl_unclassified_section",
    }
)

_PRIMARY_FIELD_ORDER: tuple[str, ...] = (
    "boxed_warning",
    "indications_and_usage",
    "dosage_and_administration",
    "contraindications",
    "warnings_and_cautions",
    "warnings",
    "precautions",
    "drug_interactions",
    "use_in_specific_populations",
    "adverse_reactions",
    "overdosage",
    "clinical_pharmacology",
)

_SUB_FIELD_ORDER: tuple[str, ...] = (
    "pregnancy",
    "lactation",
    "nursing_mothers",
    "labor_and_delivery",
    "females_and_males_of_reproductive_potential",
    "pregnancy_or_breast_feeding",
    "pediatric_use",
    "geriatric_use",
    "general_precautions",
    "laboratory_tests",
    "teratogenic_effects",
    "nonteratogenic_effects",
    "drug_and_or_laboratory_test_interactions",
    "mechanism_of_action",
    "pharmacodynamics",
    "pharmacokinetics",
    "pharmacogenomics",
    "risks",
    "user_safety_warnings",
)

_FIELD_MUC_MAP: dict[str, str] = {
    "indications_and_usage": "chi_dinh",
    "contraindications": "chong_chi_dinh",
    "dosage_and_administration": "lieu",
    "drug_interactions": "tuong_tac",
    "drug_and_or_laboratory_test_interactions": "tuong_tac",
    "boxed_warning": "canh_bao",
    "warnings_and_cautions": "canh_bao",
    "warnings": "canh_bao",
    "precautions": "canh_bao",
    "general_precautions": "canh_bao",
    "laboratory_tests": "canh_bao",
    "user_safety_warnings": "canh_bao",
    "use_in_specific_populations": "canh_bao",
    "risks": "canh_bao",
    "pregnancy": "thai_ky_cho_bu",
    "lactation": "thai_ky_cho_bu",
    "nursing_mothers": "thai_ky_cho_bu",
    "labor_and_delivery": "thai_ky_cho_bu",
    "teratogenic_effects": "thai_ky_cho_bu",
    "nonteratogenic_effects": "thai_ky_cho_bu",
    "females_and_males_of_reproductive_potential": "thai_ky_cho_bu",
    "pregnancy_or_breast_feeding": "thai_ky_cho_bu",
    "pediatric_use": "nhi_cao_tuoi",
    "geriatric_use": "nhi_cao_tuoi",
    "adverse_reactions": "tac_dung_phu",
    "overdosage": "qua_lieu",
    "clinical_pharmacology": "duoc_ly",
    "pharmacokinetics": "duoc_ly",
    "pharmacodynamics": "duoc_ly",
    "mechanism_of_action": "duoc_ly",
    "pharmacogenomics": "duoc_ly",
}

_FIELD_EXPECTED_MAJOR: dict[str, int] = {
    "indications_and_usage": 1,
    "dosage_and_administration": 2,
    "contraindications": 4,
    "warnings_and_cautions": 5,
    "adverse_reactions": 6,
    "drug_interactions": 7,
    "use_in_specific_populations": 8,
    "overdosage": 10,
    "clinical_pharmacology": 12,
}

_FIELD_DISPLAY_TITLES: dict[str, str] = {
    "boxed_warning": "Boxed Warning",
    "indications_and_usage": "Indications and Usage",
    "dosage_and_administration": "Dosage and Administration",
    "contraindications": "Contraindications",
    "warnings_and_cautions": "Warnings and Precautions",
    "warnings": "Warnings",
    "precautions": "Precautions",
    "general_precautions": "General Precautions",
    "laboratory_tests": "Laboratory Tests",
    "drug_interactions": "Drug Interactions",
    "drug_and_or_laboratory_test_interactions": "Drug and Laboratory Test Interactions",
    "use_in_specific_populations": "Use in Specific Populations",
    "pregnancy": "Pregnancy",
    "lactation": "Lactation",
    "nursing_mothers": "Nursing Mothers",
    "labor_and_delivery": "Labor and Delivery",
    "teratogenic_effects": "Teratogenic Effects",
    "nonteratogenic_effects": "Nonteratogenic Effects",
    "females_and_males_of_reproductive_potential": "Females and Males of Reproductive Potential",
    "pregnancy_or_breast_feeding": "Pregnancy or Breast-Feeding",
    "pediatric_use": "Pediatric Use",
    "geriatric_use": "Geriatric Use",
    "adverse_reactions": "Adverse Reactions",
    "overdosage": "Overdosage",
    "clinical_pharmacology": "Clinical Pharmacology",
    "pharmacokinetics": "Pharmacokinetics",
    "pharmacodynamics": "Pharmacodynamics",
    "mechanism_of_action": "Mechanism of Action",
    "pharmacogenomics": "Pharmacogenomics",
    "risks": "Risks",
    "user_safety_warnings": "User Safety Warnings",
}

_TITLE_CONNECTORS: frozenset[str] = frozenset(
    {
        "in",
        "of",
        "for",
        "with",
        "without",
        "and",
        "or",
        "to",
        "the",
        "a",
        "an",
        "by",
        "on",
        "from",
        "as",
        "at",
        "via",
        "per",
        "after",
        "before",
        "during",
    }
)

_SENTENCE_STARTERS: frozenset[str] = frozenset(
    {
        "The",
        "This",
        "These",
        "Those",
        "There",
        "It",
        "To",
        "When",
        "If",
        "Because",
        "Although",
        "After",
        "Before",
        "During",
        "Unless",
        "Since",
        "While",
        "However",
        "Administer",
        "Consider",
        "Monitor",
        "Avoid",
        "See",
        "Discontinue",
        "Do",
        "Advise",
        "Instruct",
        "Caution",
        "Table",
        "Data",
        "Studies",
        "Limited",
        "Available",
        "Published",
        "Postmarketing",
        "Clinical",
        "No",
    }
)


class LabelTable(BaseModel):
    """Bang du lieu trich tu HTML cua nhan thuoc openFDA."""

    tieu_de: str | None = None
    cot: list[str] = Field(default_factory=list)
    dong: list[list[str]] = Field(default_factory=list)
    van_ban_phang: str


class LabelSection(BaseModel):
    """Mot muc hoac tieu muc da chuan hoa trong nhan thuoc."""

    muc: str
    duong_dan_muc: str
    truong_goc: str
    van_ban: str
    bang: list[LabelTable] = Field(default_factory=list)


class LabelDocument(BaseModel):
    """Tai lieu nhan thuoc openFDA sau tien xu ly."""

    tai_lieu_id: str
    ten_goi: str
    hoat_chat_ids: list[str]
    ten_hoat_chat: list[str] = Field(default_factory=list)
    set_id: str
    phien_ban_nguon: str
    url_goc: str
    ten_hien_thi: str
    sections: list[LabelSection]
    canh_bao: list[str] = Field(default_factory=list)


def clean_text(raw: str) -> str:
    """Loai bo ky tu an va thu gon khoang trang, giu nguyen noi dung y khoa."""
    no_invisible = _INVISIBLE_CHARS_RE.sub("", raw)
    return " ".join(no_invisible.split())


class _TableHTMLParser(HTMLParser):
    """Trinh phan tich bang HTML bang html.parser (chuan hoa thead/tbody/tfoot)."""

    _BLOCK_TAGS: frozenset[str] = frozenset({"p", "paragraph", "div", "br", "li", "item"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.table_depth = 0
        self.in_caption = False
        self.caption_parts: list[str] = []
        self.section_group = "tbody"
        self.thead_rows: list[list[str]] = []
        self.tbody_rows: list[list[str]] = []
        self.tfoot_rows: list[list[str]] = []
        self.current_row: list[str] | None = None
        self.current_cell: list[str] | None = None
        self.body_has_span = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name == "table":
            self.table_depth += 1
            return
        if self.table_depth != 1:
            return
        if name == "caption":
            self.in_caption = True
            return
        if name in {"thead", "tbody", "tfoot"}:
            self.section_group = name
            return
        if name == "tr":
            self.current_row = []
            return
        if name in {"td", "th"}:
            self.current_cell = []
            if self.section_group != "tfoot":
                for attr_key, attr_val in attrs:
                    if attr_key.lower() in {"colspan", "rowspan"} and attr_val:
                        try:
                            if int(attr_val) > 1:
                                self.body_has_span = True
                        except ValueError:
                            self.body_has_span = True
            return
        if name in self._BLOCK_TAGS:
            if self.current_cell is not None:
                self.current_cell.append(" ")
            elif self.in_caption:
                self.caption_parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name == "table":
            if self.table_depth > 0:
                self.table_depth -= 1
            return
        if self.table_depth != 1:
            return
        if name == "caption":
            self.in_caption = False
            return
        if name in {"thead", "tbody", "tfoot"}:
            self.section_group = "tbody"
            return
        if name in {"td", "th"}:
            if self.current_row is not None and self.current_cell is not None:
                self.current_row.append(clean_text("".join(self.current_cell)))
            self.current_cell = None
            return
        if name == "tr":
            if self.current_row is not None and any(cell != "" for cell in self.current_row):
                if self.section_group == "thead":
                    self.thead_rows.append(self.current_row)
                elif self.section_group == "tfoot":
                    self.tfoot_rows.append(self.current_row)
                else:
                    self.tbody_rows.append(self.current_row)
            self.current_row = None
            return
        if name in self._BLOCK_TAGS:
            if self.current_cell is not None:
                self.current_cell.append(" ")
            elif self.in_caption:
                self.caption_parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self.table_depth != 1:
            return
        if self.current_cell is not None:
            self.current_cell.append(data)
        elif self.in_caption:
            self.caption_parts.append(data)


def parse_html_table(html: str) -> LabelTable | None:
    """Phan tich mot chuoi HTML <table> thanh LabelTable (hoac None neu bang rong)."""
    parser = _TableHTMLParser()
    parser.feed(html)
    parser.close()

    data_rows = parser.thead_rows + parser.tbody_rows
    all_rows = data_rows + parser.tfoot_rows
    if not all_rows:
        return None

    tieu_de_raw = clean_text("".join(parser.caption_parts))
    tieu_de = tieu_de_raw if tieu_de_raw else None
    van_ban_phang = "\n".join(" | ".join(row) for row in all_rows)

    col_counts = {len(row) for row in data_rows}
    if (
        data_rows
        and len(col_counts) == 1
        and next(iter(col_counts)) > 0
        and not parser.body_has_span
    ):
        cot = data_rows[0]
        dong = data_rows[1:]
    else:
        cot = []
        dong = []

    return LabelTable(
        tieu_de=tieu_de,
        cot=cot,
        dong=dong,
        van_ban_phang=van_ban_phang,
    )


def _table_probe_pattern(table: LabelTable) -> re.Pattern[str] | None:
    """Tao mau regex ngan de dinh vi bang trong van ban phang cua muc."""
    first_lines = table.van_ban_phang.splitlines()[:2]
    tokens: list[str] = []
    if table.tieu_de:
        tokens.extend(table.tieu_de.split()[:4])
    for line in first_lines:
        for cell in line.split(" | "):
            tokens.extend(cell.split())
            if len(tokens) >= 7:
                break
        if len(tokens) >= 7:
            break
    sample = [tok for tok in tokens[:7] if tok]
    if not sample:
        return None
    return re.compile(r"\s+".join(re.escape(tok) for tok in sample), re.IGNORECASE)


def _dedupe_array_items(raw_items: list[str]) -> list[str]:
    """Lam sach tung phan tu mang va loai bo phan tu bi lap lai hoan toan."""
    cleaned = [clean_text(item) for item in raw_items if clean_text(item)]
    kept: list[str] = []
    for idx, item in enumerate(cleaned):
        is_duplicate = any(
            (j != idx and item == other and j < idx)
            or (j != idx and item in other and len(item) < len(other))
            for j, other in enumerate(cleaned)
        )
        if not is_duplicate:
            kept.append(item)
    return kept


def _find_fpi_start(field: str, raw_text: str) -> int:
    """Xac dinh vi tri bat dau Full Prescribing Information (loai bo Highlights)."""
    expected_major = _FIELD_EXPECTED_MAJOR.get(field)

    major_pos: int | None = None
    for match in _MAJOR_HEADING_RE.finditer(raw_text):
        num = int(match.group(1))
        if expected_major is None or num == expected_major:
            major_pos = match.start()
            break

    sub_pos: int | None = None
    for match in _SUBSECTION_RE.finditer(raw_text):
        major = int(match.group(1))
        minor = int(match.group(2))
        if minor == 1 and (expected_major is None or major == expected_major):
            sub_pos = match.start()
            break

    candidates = [pos for pos in (major_pos, sub_pos) if pos is not None and pos > 0]
    if not candidates:
        return 0
    fpi_start = min(candidates)
    preamble = raw_text[:fpi_start]
    refs = _PAREN_REF_RE.findall(preamble)

    if len(refs) >= 2:
        return fpi_start
    if len(refs) == 1 and major_pos is not None and major_pos == fpi_start:
        return fpi_start
    return 0


def _split_tables_by_fpi(
    raw_tables: list[str],
    raw_text: str,
    fpi_start: int,
) -> list[LabelTable]:
    """Phan tich bang HTML va loai bo cac bang thuoc phan Highlights da cat."""
    parsed = [tbl for html in raw_tables if (tbl := parse_html_table(html)) is not None]
    if fpi_start <= 0 or not parsed:
        return parsed

    fpi_tables: list[LabelTable] = []
    cursor = 0
    highlights_norm = re.sub(r"\s+", " ", raw_text[:fpi_start]).lower()
    for tbl in parsed:
        pattern = _table_probe_pattern(tbl)
        if pattern is None:
            fpi_tables.append(tbl)
            continue
        match = pattern.search(raw_text, cursor)
        if match is not None:
            if match.start() < fpi_start:
                cursor = match.end()
                continue
            fpi_tables.append(tbl)
            cursor = match.end()
            continue

        # Thu doi chieu chuoi tu ngan o hang dau neu mau day khong khop khoang trang.
        first_row = tbl.van_ban_phang.splitlines()[0].replace("|", " ")
        first_line_tokens = [tok for tok in first_row.split()[:5] if tok]
        flat_sample = " ".join(first_line_tokens).lower()
        if flat_sample and flat_sample in highlights_norm:
            continue
        fpi_tables.append(tbl)
    return fpi_tables


def _select_monotonic_subsections(
    text: str,
    expected_major: int | None,
) -> list[tuple[int, int, int]]:
    """Chon chuoi tieu muc tang dan don dieu (tranh cat nham dai so trong bang)."""
    candidates: list[tuple[int, int, int]] = []
    for match in _SUBSECTION_RE.finditer(text):
        prefix = text[max(0, match.start() - 18) : match.start()]
        if _XREF_BEFORE_RE.search(prefix):
            continue
        major = int(match.group(1))
        minor = int(match.group(2))
        if expected_major is not None and major != expected_major:
            continue
        if minor == 0 or minor > 25:
            continue
        candidates.append((match.start(), major, minor))

    if not candidates:
        return []

    start_indices = [
        idx
        for idx, (pos, _, minor) in enumerate(candidates)
        if minor in {1, 2} and (minor == 1 or pos < 600)
    ]
    if not start_indices:
        return []

    n = len(candidates)
    best_next: list[int | None] = [None] * n
    best_len: list[int] = [1] * n

    for idx in range(n - 1, -1, -1):
        _, major_i, minor_i = candidates[idx]
        for nxt in range(idx + 1, n):
            _, major_j, minor_j = candidates[nxt]
            if major_j == major_i and 1 <= (minor_j - minor_i) <= 4:
                candidate_len = 1 + best_len[nxt]
                if candidate_len > best_len[idx]:
                    best_len[idx] = candidate_len
                    best_next[idx] = nxt

    best_start = max(start_indices, key=lambda idx: best_len[idx])
    chain: list[tuple[int, int, int]] = []
    cur: int | None = best_start
    while cur is not None:
        chain.append(candidates[cur])
        cur = best_next[cur]
    return chain


def _extract_subsection_title(segment: str, major: int, minor: int) -> str:
    """Trich tieu de ngan gon cho tieu muc dang N.M."""
    prefix = f"{major}.{minor}"
    after = segment[len(prefix) :].lstrip()
    tokens = after.split()
    picked: list[str] = []
    for idx, tok in enumerate(tokens[:10]):
        if picked and tok.rstrip(".,;:") in _SENTENCE_STARTERS:
            break
        cleaned_tok = tok.rstrip(":")
        if not cleaned_tok:
            continue
        is_connector = cleaned_tok.lower() in _TITLE_CONNECTORS
        if picked and cleaned_tok[0].islower() and not is_connector:
            break
        # Dung truoc chu ngu va dong tu mo dau than bai, vi du "Dosage should".
        if picked and _BODY_SENTENCE_RE.match(" ".join(tokens[idx : idx + 3])):
            break
        picked.append(cleaned_tok)
        if tok.endswith(":") or tok.endswith("."):
            if tok.endswith(".") and len(cleaned_tok) > 1:
                picked[-1] = cleaned_tok.rstrip(".")
            break
        if sum(len(p) + 1 for p in picked) >= 58:
            break
    if not picked:
        return prefix
    return f"{prefix} {' '.join(picked)}"


def _classify_subsection_muc(field: str, title: str, default_muc: str) -> str:
    """Phan loai muc cho tieu muc theo linh vuc lam sang."""
    lowered = title.lower()
    if field in {"dosage_and_administration", "use_in_specific_populations"}:
        if any(kw in lowered for kw in ("renal", "kidney", "creatinine", "dialysis")):
            return "lieu_than"
        if any(kw in lowered for kw in ("hepatic", "liver")):
            return "lieu_gan"
    if field == "use_in_specific_populations":
        if any(
            kw in lowered for kw in ("pregnan", "lactation", "nursing", "reproductive", "fertility")
        ):
            return "thai_ky_cho_bu"
        if any(kw in lowered for kw in ("pediatric", "geriatric", "elderly")):
            return "nhi_cao_tuoi"
    return default_muc


def _parent_title(field: str, raw_text: str) -> str:
    """Lay ten muc cha ngan gon cho duong_dan_muc."""
    if field in _FIELD_DISPLAY_TITLES:
        return _FIELD_DISPLAY_TITLES[field]
    lead = _MAJOR_HEADING_RE.match(raw_text)
    if lead:
        return lead.group(2).strip().title()
    return field.replace("_", " ").title()


def _split_field_into_sections(
    field: str,
    fpi_text: str,
    fpi_tables: list[LabelTable],
) -> tuple[list[LabelSection], bool]:
    """Tach mot truong openFDA da cat Highlights thanh cac LabelSection va gan bang."""
    default_muc = _FIELD_MUC_MAP.get(field, "khac")
    is_unknown = field not in _FIELD_MUC_MAP
    parent = _parent_title(field, fpi_text)

    expected_major = _FIELD_EXPECTED_MAJOR.get(field)
    if expected_major is None:
        lead_major = _LEADING_MAJOR_RE.match(fpi_text)
        if lead_major:
            expected_major = int(lead_major.group(1))

    chain = _select_monotonic_subsections(fpi_text, expected_major)
    if not chain:
        cleaned = fpi_text.strip()
        if not cleaned or (_BOILERPLATE_STUB_RE.match(cleaned) and not fpi_tables):
            return [], is_unknown
        sec = LabelSection(
            muc=default_muc,
            duong_dan_muc=parent,
            truong_goc=field,
            van_ban=cleaned,
            bang=fpi_tables,
        )
        return [sec], is_unknown

    # Loai bo cac diem tach se tao ra tieu muc qua ngan (< 50 ky tu) khong co noi dung.
    merged_chain: list[tuple[int, int, int]] = []
    for idx, item in enumerate(chain):
        start_pos = item[0]
        end_pos = chain[idx + 1][0] if idx + 1 < len(chain) else len(fpi_text)
        seg = fpi_text[start_pos:end_pos].strip()
        if len(seg) < 50 and (merged_chain or idx + 1 < len(chain)):
            continue
        merged_chain.append(item)

    if not merged_chain:
        cleaned = fpi_text.strip()
        if not cleaned or (_BOILERPLATE_STUB_RE.match(cleaned) and not fpi_tables):
            return [], is_unknown
        sec = LabelSection(
            muc=default_muc,
            duong_dan_muc=parent,
            truong_goc=field,
            van_ban=cleaned,
            bang=fpi_tables,
        )
        return [sec], is_unknown

    ranges: list[tuple[int, int, str, str]] = []
    first_pos = merged_chain[0][0]
    intro = fpi_text[:first_pos].strip()
    intro_body = _LEADING_MAJOR_RE.sub("", intro, count=1).strip()
    if len(intro_body) >= 50 and any(ch.islower() for ch in intro_body):
        ranges.append((0, first_pos, default_muc, parent))

    for idx, (pos, major, minor) in enumerate(merged_chain):
        end_pos = merged_chain[idx + 1][0] if idx + 1 < len(merged_chain) else len(fpi_text)
        seg = fpi_text[pos:end_pos].strip()
        sub_title = _extract_subsection_title(seg, major, minor)
        sub_muc = _classify_subsection_muc(field, sub_title, default_muc)
        ranges.append((pos, end_pos, sub_muc, f"{parent} > {sub_title}"))

    # Gan tung bang FPI vao tieu muc tuong ung theo thu tu xuat hien.
    assigned_tables: list[list[LabelTable]] = [[] for _ in ranges]
    cursor = 0
    last_sec_idx = 0
    for tbl in fpi_tables:
        pattern = _table_probe_pattern(tbl)
        sec_idx = last_sec_idx
        match = None
        start_pos = max(cursor, ranges[0][0])
        # Tim caption doc lap, khong ghep duoi caption bi cat voi tieu de cot.
        if tbl.tieu_de:
            caption_pattern = re.compile(
                r"\s+".join(re.escape(tok) for tok in tbl.tieu_de.split()), re.IGNORECASE
            )
            match = caption_pattern.search(fpi_text, start_pos)
        if match is None and pattern is not None:
            match = pattern.search(fpi_text, start_pos)
        if match is not None:
            m_pos = match.start()
            for idx, (r_start, r_end, _, _) in enumerate(ranges):
                if r_start <= m_pos < r_end:
                    sec_idx = idx
                    break
            cursor = match.end()
        assigned_tables[sec_idx].append(tbl)
        last_sec_idx = sec_idx

    sections: list[LabelSection] = []
    for idx, (r_start, r_end, sec_muc, path) in enumerate(ranges):
        text = fpi_text[r_start:r_end].strip()
        tbls = assigned_tables[idx]
        if not text or (_BOILERPLATE_STUB_RE.match(text) and not tbls):
            continue
        sections.append(
            LabelSection(
                muc=sec_muc,
                duong_dan_muc=path,
                truong_goc=field,
                van_ban=text,
                bang=tbls,
            )
        )
    return sections, is_unknown


def _format_effective_date(raw_date: str) -> str:
    """Dinh dang ngay YYYYMMDD thanh dd/mm/yyyy."""
    digits = raw_date.strip()
    if len(digits) == 8 and digits.isdigit():
        return f"{digits[6:8]}/{digits[4:6]}/{digits[0:4]}"
    return digits or "chua_ro"


def _first_str(value: object) -> str:
    """Lay phan tu chuoi dau tien tu gia tri dang danh sach trong openfda."""
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return clean_text(item)
    return ""


def _ordered_fields(entry: dict) -> list[str]:
    """Sap xep thu tu duyet truong: truong chinh truoc, truong con sau."""
    seen: set[str] = set()
    ordered: list[str] = []
    for field in (*_PRIMARY_FIELD_ORDER, *_SUB_FIELD_ORDER):
        if field in entry and field not in seen:
            ordered.append(field)
            seen.add(field)
    for field in entry:
        if field not in seen:
            ordered.append(field)
            seen.add(field)
    return ordered


def load_label(path: Path, manifest_entry: dict, names: DrugNameIndex) -> LabelDocument:
    """Doc va tien xu ly mot tep nhan openFDA thanh LabelDocument."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload.get("results") or []
    if not results or not isinstance(results[0], dict):
        raise ValueError(f"Tep openFDA khong co results[0] hop le: {path}")
    entry: dict = results[0]

    ten_goi = str(manifest_entry["ten_goi"])
    openfda_meta = entry.get("openfda") if isinstance(entry.get("openfda"), dict) else {}
    set_id = str(
        entry.get("set_id")
        or _first_str(openfda_meta.get("spl_set_id"))
        or manifest_entry.get("set_id")
        or ""
    )
    phien_ban = str(entry.get("effective_time") or manifest_entry.get("effective_time") or "")
    url_goc = f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}" if set_id else ""

    hoat_chat_ids = names.ids_for_label(ten_goi)
    if not hoat_chat_ids:
        for candidate in (
            _first_str(openfda_meta.get("generic_name")),
            _first_str(openfda_meta.get("substance_name")),
            ten_goi.replace("_", " "),
        ):
            if candidate:
                hoat_chat_ids = names.resolve(candidate)
                if hoat_chat_ids:
                    break
    ten_hoat_chat = names.inn_names(hoat_chat_ids)

    display_drug = (
        _first_str(openfda_meta.get("brand_name"))
        or _first_str(openfda_meta.get("generic_name"))
        or ten_goi.replace("_", " ").upper()
    )
    ten_hien_thi = f"Nhãn FDA {display_drug} ({_format_effective_date(phien_ban)})"

    sub_field_set = frozenset(_SUB_FIELD_ORDER)
    emitted_texts: list[str] = []
    seen_table_flat: set[str] = set()
    used_paths: set[str] = set()
    sections: list[LabelSection] = []
    canh_bao: list[str] = []

    for field in _ordered_fields(entry):
        if field in _SKIP_FIELDS or field.endswith("_table"):
            continue
        raw_val = entry.get(field)
        if not isinstance(raw_val, list) or not all(isinstance(x, str) for x in raw_val):
            continue

        items = _dedupe_array_items(raw_val)
        if not items:
            continue
        raw_text = " ".join(items)
        if not raw_text:
            continue

        fpi_start = _find_fpi_start(field, raw_text)
        fpi_text = raw_text[fpi_start:].strip()
        if not fpi_text:
            continue

        # Bo qua truong con bi lap lai hoan toan trong truong chinh da doc truoc do.
        if field in sub_field_set and any(
            fpi_text in prev or raw_text in prev for prev in emitted_texts
        ):
            continue

        raw_tables_val = entry.get(f"{field}_table")
        raw_tables = (
            [t for t in raw_tables_val if isinstance(t, str)]
            if isinstance(raw_tables_val, list)
            else []
        )
        fpi_tables = _split_tables_by_fpi(raw_tables, raw_text, fpi_start)
        deduped_tables: list[LabelTable] = []
        for tbl in fpi_tables:
            if tbl.van_ban_phang not in seen_table_flat:
                seen_table_flat.add(tbl.van_ban_phang)
                deduped_tables.append(tbl)

        field_sections, is_unknown = _split_field_into_sections(
            field=field,
            fpi_text=fpi_text,
            fpi_tables=deduped_tables,
        )
        if not field_sections:
            continue

        if is_unknown and field not in canh_bao:
            canh_bao.append(field)

        emitted_texts.append(raw_text)
        for sec in field_sections:
            path_key = sec.duong_dan_muc
            if path_key in used_paths:
                suffix = 2
                while f"{path_key} ({suffix})" in used_paths:
                    suffix += 1
                sec = sec.model_copy(update={"duong_dan_muc": f"{path_key} ({suffix})"})
            used_paths.add(sec.duong_dan_muc)
            sections.append(sec)

    return LabelDocument(
        tai_lieu_id=f"openfda:{set_id or ten_goi}",
        ten_goi=ten_goi,
        hoat_chat_ids=hoat_chat_ids,
        ten_hoat_chat=ten_hoat_chat,
        set_id=set_id,
        phien_ban_nguon=phien_ban,
        url_goc=url_goc,
        ten_hien_thi=ten_hien_thi,
        sections=sections,
        canh_bao=canh_bao,
    )
