"""Lop co so cho viec tach cau, gop doan, chong lan va tao van ban nhung."""

from __future__ import annotations

import hashlib
import re

from app.config.settings import ChunkingSettings

_ABBREV_WORDS: frozenset[str] = frozenset(
    {
        "e.g",
        "i.e",
        "vs",
        "no",
        "fig",
        "approx",
        "al",
        "dr",
        "mr",
        "mrs",
        "ms",
        "st",
        "inc",
        "corp",
        "ltd",
        "ref",
        "sec",
        "tab",
        "vol",
        "est",
        "min",
        "max",
        "ca",
        "u.s",
        "i.v",
        "i.m",
        "p.o",
        "s.c",
    }
)

_NUMBER_LABEL_WORDS: frozenset[str] = frozenset(
    {
        "table",
        "figure",
        "fig",
        "section",
        "step",
        "grade",
        "type",
        "stage",
        "phase",
        "class",
        "category",
        "group",
        "level",
        "day",
        "week",
        "month",
        "year",
    }
)

_SENTENCE_BREAK_RE = re.compile(r"\.\s+(?=[A-Z\u2022])")
_BULLET_BREAK_RE = re.compile(r"\s+(?=\u2022\s+)")
_PARA_BREAK_RE = re.compile(r"\n\s*\n+")


def make_parent_id(tai_lieu_id: str, duong_dan_muc: str) -> str:
    """Tao ma muc_cha_id on dinh bang SHA-1 16 ky tu."""
    raw = f"{tai_lieu_id}|{duong_dan_muc}".encode()
    return hashlib.sha1(raw).hexdigest()[:16]


def make_chunk_id(
    tai_lieu_id: str,
    duong_dan_muc: str,
    thu_tu: int,
    noi_dung_goc: str,
) -> str:
    """Tao ma doan_trich_id on dinh theo tai lieu, duong dan, thu tu va noi dung."""
    raw = f"{tai_lieu_id}|{duong_dan_muc}|{thu_tu}|{noi_dung_goc}".encode()
    return "DT-" + hashlib.sha1(raw).hexdigest()[:12]


def build_embedding_text(
    hoat_chat_list: list[str],
    ten_hien_thi: str,
    duong_dan_muc: str,
    noi_dung_goc: str,
) -> str:
    """Ghep tieu de ngu canh vao dau noi_dung_nhung cho buoc nhung."""
    actives = " + ".join(hoat_chat_list) if hoat_chat_list else "unknown"
    return f"[{actives} | {ten_hien_thi} | {duong_dan_muc}]\n{noi_dung_goc}"


def _is_protected_period(text: str, period_pos: int) -> bool:
    """Kiem tra dau cham tai period_pos co thuoc chu viet tat hay nhan so khong."""
    left = text[:period_pos]
    token_match = re.search(r"([A-Za-z0-9.]+)$", left)
    if not token_match:
        return True
    token = token_match.group(1)
    lowered = token.lower().strip("()")

    if lowered in _ABBREV_WORDS:
        return True
    # Chu cai don (vi du: "E. coli", "S. aureus") hoac chuoi viet tat dang A.B.
    if len(token) == 1 and token.isalpha():
        return True
    if "." in token and all(len(part) <= 2 for part in token.split(".") if part):
        return True

    # Tranh tach sau "Table 1.", "Fig 2.", "Step 1."
    if token.isdigit():
        before_num = left[: token_match.start()].rstrip()
        prev_word_match = re.search(r"([A-Za-z]+)$", before_num)
        if prev_word_match and prev_word_match.group(1).lower() in _NUMBER_LABEL_WORDS:
            return True
    return False


def split_sentence_spans(text: str, base_offset: int = 0) -> list[tuple[int, int]]:
    """Tach van ban thanh cac khoang cau (start, end) tren chuoi goc, giu nguyen lieu."""
    stripped = text.strip()
    if not stripped:
        return []

    lead_ws = len(text) - len(text.lstrip())
    spans: list[tuple[int, int]] = []
    cur_start = lead_ws

    for match in _SENTENCE_BREAK_RE.finditer(text):
        period_pos = match.start()
        if period_pos < cur_start:
            continue
        if _is_protected_period(text, period_pos):
            continue
        end_pos = period_pos + 1
        while cur_start < end_pos and text[cur_start].isspace():
            cur_start += 1
        if end_pos > cur_start:
            spans.append((base_offset + cur_start, base_offset + end_pos))
        cur_start = match.end()

    tail_end = len(text.rstrip())
    while cur_start < tail_end and text[cur_start].isspace():
        cur_start += 1
    if tail_end > cur_start:
        spans.append((base_offset + cur_start, base_offset + tail_end))
    return spans


def _split_unit_spans(text: str, base_offset: int = 0) -> list[tuple[int, int]]:
    """Tach theo doan/danh sach co dau bullet (giu cau dan cung muc dau tien)."""
    if "\u2022" not in text:
        return split_sentence_spans(text, base_offset)

    bullet_positions = [m.start() for m in _BULLET_BREAK_RE.finditer(text)]
    if not bullet_positions:
        return split_sentence_spans(text, base_offset)

    # Gop phan dan truoc dau bullet thu nhat voi muc bullet dau tien de khong mat ngu canh.
    spans: list[tuple[int, int]] = []
    start = len(text) - len(text.lstrip())
    split_points = bullet_positions[1:] if text[: bullet_positions[0]].strip() else bullet_positions
    for brk in split_points:
        piece_end = len(text[:brk].rstrip())
        while start < piece_end and text[start].isspace():
            start += 1
        if piece_end > start:
            spans.append((base_offset + start, base_offset + piece_end))
        start = brk
    tail_end = len(text.rstrip())
    while start < tail_end and text[start].isspace():
        start += 1
    if tail_end > start:
        spans.append((base_offset + start, base_offset + tail_end))

    expanded: list[tuple[int, int]] = []
    for s, e in spans:
        rel = text[s - base_offset : e - base_offset]
        expanded.extend(split_sentence_spans(rel, base_offset=s))
    return expanded


def _hard_split_span(
    text: str,
    start: int,
    end: int,
    limit: int,
    min_chars: int,
) -> list[tuple[int, int]]:
    """Chia mot cau qua dai > max_chars theo ranh gioi khoang trang/dau phay."""
    spans: list[tuple[int, int]] = []
    cur = start
    while end - cur > limit:
        remaining = end - cur
        # Neu phan con lai chi vuot nhe 1x..2x limit, chia can doi de tranh manh duoi < 50 ky tu.
        step_target = min(limit, remaining // 2 + 40) if remaining <= limit * 2 else limit
        window_end = min(end, cur + step_target)
        min_offset = cur + min(step_target - 1, max(min_chars, step_target // 3))
        cut = -1
        for sep in ("; ", ", ", " "):
            idx = text.rfind(sep, min_offset, window_end)
            if idx != -1:
                cut = idx + len(sep.rstrip())
                break
        if cut == -1:
            idx = text.rfind(" ", cur + 1, window_end)
            cut = idx if idx != -1 else window_end

        piece_end = cut
        while piece_end > cur and text[piece_end - 1].isspace():
            piece_end -= 1
        if piece_end > cur:
            spans.append((cur, piece_end))
        next_cur = cut
        while next_cur < end and text[next_cur].isspace():
            next_cur += 1
        cur = next_cur

    while cur < end and text[cur].isspace():
        cur += 1
    if end > cur:
        spans.append((cur, end))
    return spans


class BaseChunker:
    """Bo cat doan co so: gop doan ngan, cat van ban dai co chong lan."""

    def __init__(self, settings: ChunkingSettings) -> None:
        """Khoi tao bo cat doan voi cau hinh ChunkingSettings."""
        self.settings = settings

    def chunk_text(self, text: str) -> list[str]:
        """Tach mot van ban sach thanh cac chuoi con tuan thu min/target/max/overlap."""
        cleaned = text.strip()
        if not cleaned:
            return []
        if len(text) <= self.settings.target_chars:
            return [cleaned]

        if _PARA_BREAK_RE.search(text):
            return self._chunk_paragraphs(text)
        return self._chunk_atomic_spans(text, _split_unit_spans(text))

    def _chunk_paragraphs(self, text: str) -> list[str]:
        """Tach theo doan van ro rang (\n\n), chi tach sau khi doan vuot max_chars."""
        para_spans: list[tuple[int, int]] = []
        pos = 0
        for match in _PARA_BREAK_RE.finditer(text):
            p_start = pos
            p_end = match.start()
            while p_start < p_end and text[p_start].isspace():
                p_start += 1
            while p_end > p_start and text[p_end - 1].isspace():
                p_end -= 1
            if p_end > p_start:
                para_spans.append((p_start, p_end))
            pos = match.end()
        tail_start = pos
        tail_end = len(text)
        while tail_start < tail_end and text[tail_start].isspace():
            tail_start += 1
        while tail_end > tail_start and text[tail_end - 1].isspace():
            tail_end -= 1
        if tail_end > tail_start:
            para_spans.append((tail_start, tail_end))

        target = self.settings.target_chars
        max_len = self.settings.max_chars
        min_len = self.settings.min_chars

        groups: list[tuple[int, int]] = []
        idx = 0
        while idx < len(para_spans):
            p_start, p_end = para_spans[idx]
            if (p_end - p_start) > max_len:
                sub = split_sentence_spans(text[p_start:p_end], base_offset=p_start)
                groups.extend(self._atomic_span_ranges(text, sub))
                idx += 1
                continue

            cur_start, cur_end = p_start, p_end
            idx += 1
            while idx < len(para_spans):
                nxt_start, nxt_end = para_spans[idx]
                if (nxt_end - nxt_start) > max_len:
                    break
                if (nxt_end - cur_start) <= target:
                    cur_end = nxt_end
                    idx += 1
                else:
                    break
            groups.append((cur_start, cur_end))

        # Neu doan cuoi ngan hon min_chars va gop vao doan truoc khong vuot max_chars thi gop.
        if len(groups) >= 2:
            last_start, last_end = groups[-1]
            prev_start, _ = groups[-2]
            if (last_end - last_start) < min_len and (last_end - prev_start) <= max_len:
                groups[-2] = (prev_start, last_end)
                groups.pop()

        return [text[s:e] for s, e in groups]

    def _chunk_atomic_spans(
        self,
        text: str,
        raw_spans: list[tuple[int, int]],
    ) -> list[str]:
        """Gop cac khoang cau/don vi lien tiep toi target_chars co overlap khi tach dai."""
        if not raw_spans:
            return [text.strip()] if text.strip() else []
        return [text[s:e] for s, e in self._atomic_span_ranges(text, raw_spans)]

    def _atomic_span_ranges(
        self,
        text: str,
        raw_spans: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """Tra ve danh sach (start, end) sau khi gop va chong lan."""
        if not raw_spans:
            return []

        target = self.settings.target_chars
        max_len = self.settings.max_chars
        min_len = self.settings.min_chars
        overlap_n = self.settings.overlap_sentences

        spans: list[tuple[int, int]] = []
        for s, e in raw_spans:
            if (e - s) > max_len:
                spans.extend(_hard_split_span(text, s, e, max_len, min_len))
            else:
                spans.append((s, e))

        # Tach thanh cac nhom theo target_chars va giu chong lan giua cac doan ke nhau.
        groups: list[list[int]] = []
        i = 0
        n = len(spans)
        while i < n:
            if not groups:
                cur_indices = [i]
                i += 1
            else:
                # Chon toi da overlap_n cau cuoi cua doan truoc ma van giu do dai <= max_len.
                prev_indices = groups[-1]
                max_overlap = min(overlap_n, max(0, len(prev_indices) - 1))
                overlap_start = prev_indices[-max_overlap:] if max_overlap > 0 else []
                while overlap_start:
                    span_start = spans[overlap_start[0]][0]
                    span_end = spans[i][1]
                    if (span_end - span_start) <= max_len:
                        break
                    overlap_start = overlap_start[1:]
                cur_indices = [*overlap_start, i]
                i += 1

            while i < n:
                start_char = spans[cur_indices[0]][0]
                cand_end = spans[i][1]
                if (cand_end - start_char) <= target:
                    cur_indices.append(i)
                    i += 1
                else:
                    break

            groups.append(cur_indices)

        # Kiem tra doan cuoi < min_chars (tinh phan moi hoac toan doan) va gop neu <= max_len.
        if len(groups) >= 2:
            last_grp = groups[-1]
            prev_grp = groups[-2]
            last_start, last_end = spans[last_grp[0]][0], spans[last_grp[-1]][1]
            prev_start = spans[prev_grp[0]][0]
            new_only_indices = [idx for idx in last_grp if idx > prev_grp[-1]]
            new_len = (
                spans[new_only_indices[-1]][1] - spans[new_only_indices[0]][0]
                if new_only_indices
                else 0
            )
            if ((last_end - last_start) < min_len or new_len < min_len) and (
                last_end - prev_start
            ) <= max_len:
                merged = list(dict.fromkeys([*prev_grp, *last_grp]))
                groups[-2] = merged
                groups.pop()

        return [(spans[grp[0]][0], spans[grp[-1]][1]) for grp in groups]
