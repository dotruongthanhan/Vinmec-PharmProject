"""Kiểm chứng trích dẫn, con số và ghép phát hiện luật với đề xuất LLM."""

from app.verify.citation import check_citations, normalize_text, quote_matches_source
from app.verify.merge import merge
from app.verify.number import (
    check_numbers,
    extract_numbers,
    mask_citation_markers,
    numbers_in_text,
    unverified_numbers,
)
from app.verify.pipeline import verify_all

__all__ = [
    "check_citations",
    "check_numbers",
    "extract_numbers",
    "mask_citation_markers",
    "merge",
    "normalize_text",
    "numbers_in_text",
    "quote_matches_source",
    "unverified_numbers",
    "verify_all",
]
