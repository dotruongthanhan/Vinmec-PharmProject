"""Chỉ mục BM25 Okapi hỗ trợ truy vấn tiếng Việt không dấu."""

import math
import re
import unicodedata
from collections import Counter

from app.core.types import Chunk, ScoredChunk, SearchFilter, matches


def _tokenize(text: str) -> list[str]:
    """Tách từ Unicode, thêm dạng bỏ dấu khi khác từ gốc."""
    tokens = []
    for word in re.findall(r"\w+", text.lower()):
        tokens.append(word)
        plain = "".join(
            char for char in unicodedata.normalize("NFD", word) if not unicodedata.combining(char)
        ).replace("đ", "d")
        if plain != word:
            tokens.append(plain)
    return tokens


class Bm25Index:
    """Lập chỉ mục nội dung nhúng với k1=1.5, b=0.75."""

    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._terms: list[Counter[str]] = []
        self._lengths: list[int] = []
        self._document_frequency: Counter[str] = Counter()
        self._average_length = 0.0

    def build(self, chunks: list[Chunk]) -> None:
        """Thay toàn bộ chỉ mục bằng các đoạn được cung cấp."""
        self._chunks = list(chunks)
        self._terms = [Counter(_tokenize(chunk.noi_dung_nhung)) for chunk in chunks]
        self._lengths = [sum(terms.values()) for terms in self._terms]
        self._document_frequency = Counter(term for terms in self._terms for term in terms)
        self._average_length = sum(self._lengths) / len(chunks) if chunks else 0.0

    def search(self, query: str, k: int, bo_loc: SearchFilter) -> list[ScoredChunk]:
        """Chấm BM25 trên các đoạn khớp bộ lọc, bỏ điểm 0."""
        if k <= 0 or not self._average_length:
            return []
        query_terms = _tokenize(query)
        results = []
        count = len(self._chunks)
        for chunk, terms, length in zip(self._chunks, self._terms, self._lengths, strict=True):
            if not matches(chunk, bo_loc):
                continue
            score = 0.0
            for term in query_terms:
                frequency = terms[term]
                if not frequency:
                    continue
                df = self._document_frequency[term]
                idf = math.log(1.0 + (count - df + 0.5) / (df + 0.5))
                score += (
                    idf
                    * frequency
                    * 2.5
                    / (frequency + 1.5 * (0.25 + 0.75 * length / self._average_length))
                )
            if score > 0:
                results.append(ScoredChunk(chunk=chunk, diem=score, nguon_diem="tu_khoa"))
        return sorted(results, key=lambda item: item.diem, reverse=True)[:k]
