"""Kiểm thử AgenticAsker: kiểm tra độ dài câu hỏi, thiếu LLM và ask_global."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from app.agent.asker import AgenticAsker
from app.agent.tools.policy import ChinhSachCongCu
from app.agent.tools.registry import DanhMucCongCu
from app.container import build_container
from app.domain.loader import load_case
from app.domain.models import CaBenh
from app.orchestration.ai_review import AiRunResult
from app.orchestration.ask import NOT_READY_MESSAGE, AskResult
from app.pipeline import KetQuaThamDinh, run_case
from app.providers.fakes import FakeLLM

ROOT = Path(__file__).resolve().parents[2]
DEMO_02_PATH = ROOT / "data/mock/demo/DEMO-02.json"
PROMPT_PATH = ROOT / "config/prompts/tac_tu.v1.md"


class _SpyAsker:
    def __init__(self, reply: AskResult) -> None:
        self._reply = reply
        self.global_calls: list[dict[str, Any]] = []

    def ask(
        self,
        ca: CaBenh,
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
        *,
        ket_qua: KetQuaThamDinh | None = None,
        ai_result: AiRunResult | None = None,
        nhan_dinh_id: str | None = None,
    ) -> AskResult:
        del ca, cau_hoi, lich_su, ket_qua, ai_result, nhan_dinh_id
        return self._reply

    def ask_global(
        self,
        cases: Sequence[CaBenh],
        results: dict[str, KetQuaThamDinh],
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
    ) -> AskResult:
        self.global_calls.append(
            {"cases": list(cases), "results": dict(results), "cau_hoi": cau_hoi}
        )
        return self._reply


def _make_asker(
    llm: FakeLLM | None,
    *,
    global_asker: _SpyAsker | None = None,
) -> AgenticAsker:
    container = build_container("test")
    reg = DanhMucCongCu()
    pol = ChinhSachCongCu.tu_tep(ROOT / "config/tool_policy.yaml")
    return AgenticAsker(
        llm=llm,
        danh_muc=reg,
        chinh_sach=pol,
        global_asker=global_asker,
        prompt_path=PROMPT_PATH,
        case_settings=container.settings.case_context,
        renal_rules=container.renal_rules,
        max_turns=5,
    )


def test_empty_or_too_long_question_raises_value_error() -> None:
    case = load_case(DEMO_02_PATH)
    asker = _make_asker(FakeLLM([]))
    for bad in ("", "   ", "a" * 1001):
        with pytest.raises(ValueError):
            asker.ask(case, bad)
        with pytest.raises(ValueError):
            asker.ask_global([case], {}, bad)


def test_missing_llm_returns_chua_san_sang() -> None:
    case = load_case(DEMO_02_PATH)
    asker = _make_asker(None)
    res_case = asker.ask(case, "Creatinin bao nhiêu?")
    res_global = asker.ask_global([case], {}, "Có ca nào cần chú ý?")
    assert res_case.trang_thai == "chua_san_sang"
    assert res_case.noi_dung == NOT_READY_MESSAGE
    assert res_global.trang_thai == "chua_san_sang"
    assert res_global.noi_dung == NOT_READY_MESSAGE


def test_ask_global_delegates_to_legacy_global_asker() -> None:
    container = build_container("test")
    case = load_case(DEMO_02_PATH)
    rule = run_case(case, container.renal_rules)
    spy = _SpyAsker(AskResult(trang_thai="ok", noi_dung="Tổng quan từ spy."))
    asker = _make_asker(FakeLLM([]), global_asker=spy)
    result = asker.ask_global([case], {case.ca_id: rule}, "Ca nào cần xem lại liều?")
    assert len(spy.global_calls) == 1
    assert result.trang_thai == "ok"
    assert result.noi_dung == "Tổng quan từ spy."


def test_ask_global_returns_unsupported_without_global_asker() -> None:
    case = load_case(DEMO_02_PATH)
    asker = _make_asker(FakeLLM([]))
    result = asker.ask_global([case], {}, "Ca nào cần chú ý?")
    assert result.trang_thai == "chua_san_sang"
    assert "chưa hỗ trợ" in result.noi_dung
