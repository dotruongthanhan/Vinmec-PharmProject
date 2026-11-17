"""Gói tổng hợp LLM, dựng ngữ cảnh ca bệnh và lắp ráp Synthesizer."""

from app.llm.case_context import build_case_context
from app.llm.prompt_loader import load_prompt, render_prompt
from app.llm.schema import (
    GoiCanCu,
    KetQuaLLM,
    KetQuaTongHop,
    NhanDinhCuoi,
    NhanDinhDaKiem,
    NhanDinhDeXuat,
    TrichDanNguon,
    json_schema_for_llm,
)
from app.llm.setup import build_llm, build_synthesizer
from app.llm.synthesizer import Synthesizer

__all__ = [
    "GoiCanCu",
    "KetQuaLLM",
    "KetQuaTongHop",
    "NhanDinhCuoi",
    "NhanDinhDaKiem",
    "NhanDinhDeXuat",
    "Synthesizer",
    "TrichDanNguon",
    "build_case_context",
    "build_llm",
    "build_synthesizer",
    "json_schema_for_llm",
    "load_prompt",
    "render_prompt",
]
