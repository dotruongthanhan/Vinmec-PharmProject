"""Bộ hỏi đáp agent theo đồ thị LangGraph cùng giao diện ask / ask_global với CaseAsker."""

from __future__ import annotations

import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from langsmith import tracing_context

from app.agent.graph import dung_do_thi_hoi_dap
from app.agent.tools.base import ToolContext
from app.agent.tools.gateway import ToolGateway
from app.agent.tools.policy import ChinhSachCongCu
from app.agent.tools.registry import DanhMucCongCu
from app.config.settings import CaseContextSettings
from app.core.interfaces import LLMClient
from app.domain.models import CaBenh
from app.orchestration.ai_review import AiRunResult
from app.orchestration.ask import ERROR_MESSAGE, NOT_READY_MESSAGE, AskResult
from app.pipeline import KetQuaThamDinh
from app.rules import RenalRuleBook, load_renal_rules

DEFAULT_AGENT_TIMEOUT_SECONDS = 75.0
_GLOBAL_UNSUPPORTED_MESSAGE = (
    "Chế độ hỏi đáp chung chưa hỗ trợ trên agent. Vui lòng mở từng ca bệnh để đặt câu hỏi."
)


class _GlobalAsker(Protocol):
    """Bộ hỏi đáp chung của luồng cũ (CaseAsker.ask_global)."""

    def ask_global(
        self,
        cases: Sequence[CaBenh],
        results: dict[str, KetQuaThamDinh],
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
    ) -> AskResult: ...


class AgenticAsker:
    """Điều phối hỏi đáp bằng đồ thị LangGraph (chế độ ca).

    Chế độ chung chưa có đồ thị riêng: chuyển thẳng cho bộ hỏi chung của luồng cũ
    (định tuyến ở mức engine, không phải công cụ của agent).
    """

    def __init__(
        self,
        llm: LLMClient | None,
        danh_muc: DanhMucCongCu,
        chinh_sach: ChinhSachCongCu,
        global_asker: _GlobalAsker | None,
        prompt_path: Path,
        case_settings: CaseContextSettings,
        renal_rules: RenalRuleBook | None = None,
        max_turns: int = 5,
        timeout_seconds: float = DEFAULT_AGENT_TIMEOUT_SECONDS,
    ) -> None:
        self._llm = llm
        self._danh_muc = danh_muc
        self._chinh_sach = chinh_sach
        self._global_asker = global_asker
        self._prompt_path = Path(prompt_path)
        self._case_settings = case_settings
        self._renal_rules = renal_rules
        self._max_turns = max(1, max_turns)
        self._timeout_seconds = timeout_seconds
        self._graph: Any = (
            dung_do_thi_hoi_dap(
                llm=llm,
                danh_muc=danh_muc,
                chinh_sach=chinh_sach,
                prompt_path=self._prompt_path,
                case_settings=case_settings,
                renal_rules_getter=self._get_renal_rules,
                max_turns=self._max_turns,
            )
            if llm is not None
            else None
        )

    def _get_renal_rules(self) -> RenalRuleBook:
        """Nạp bảng quy tắc chỉnh liều thận khi người gọi chưa truyền sẵn kết quả luật."""
        if self._renal_rules is None:
            self._renal_rules = load_renal_rules()
        return self._renal_rules

    def close(self) -> None:
        """Đóng máy khách HTTP dùng chung nếu có."""
        if self._llm is not None:
            client = getattr(self._llm, "client", None)
            close_fn = getattr(client, "close", None)
            if callable(close_fn):
                close_fn()
        close_global = getattr(self._global_asker, "close", None)
        if callable(close_global):
            close_global()

    def ask(
        self,
        ca: CaBenh,
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
        *,
        ket_qua: KetQuaThamDinh | None = None,
        ai_result: AiRunResult | None = None,
        nhan_dinh_id: str | None = None,
        vai_tro: str = "duoc_si_ls",
    ) -> AskResult:
        """Trả lời câu hỏi theo ca qua đồ thị agent có che PII, Gateway và kiểm chứng."""
        perf_start = time.perf_counter()
        cleaned_question = cau_hoi.strip()
        if not 1 <= len(cleaned_question) <= 1000:
            raise ValueError("cau_hoi phải dài từ 1 đến 1000 ký tự sau khi cắt khoảng trắng")

        if self._llm is None or self._graph is None:
            return AskResult(
                trang_thai="chua_san_sang",
                noi_dung=NOT_READY_MESSAGE,
                thoi_gian_ms=int((time.perf_counter() - perf_start) * 1000.0),
            )

        ctx = ToolContext(
            vai_tro=vai_tro,
            che_do="ca",
            han_chot=time.monotonic() + self._timeout_seconds,
            cau_hoi_goc=cleaned_question,
            lich_su_goc=tuple(lich_su or ()),
            ca=ca,
            ket_qua_luat=ket_qua,
            ai_result=ai_result,
            nhan_dinh_id=nhan_dinh_id,
        )
        gateway = ToolGateway(
            self._danh_muc,
            self._chinh_sach,
            so_lan_goi_toi_da=self._max_turns * 3,
        )
        initial_state = {
            "ctx": ctx,
            "cau_hoi_sach": cleaned_question,
            "gateway": gateway,
            "thoi_gian_bat_dau": perf_start,
            "so_vong": 0,
            "luot_tac_tu": 0,
            "so_lan_kiem_chung": 0,
            "so_lan_sai_luoc_do": 0,
            "can_cu": [],
            "ket_qua_cong_cu": [],
            "cong_cu_da_goi": [],
            "can_du_phong": False,
        }
        try:
            with tracing_context(enabled=False):
                final = self._graph.invoke(initial_state)
            result = final.get("ket_qua")
            if isinstance(result, AskResult):
                return result
        except Exception:
            return AskResult(
                trang_thai="loi",
                noi_dung=ERROR_MESSAGE,
                thoi_gian_ms=int((time.perf_counter() - perf_start) * 1000.0),
            )
        return AskResult(
            trang_thai="loi",
            noi_dung=ERROR_MESSAGE,
            thoi_gian_ms=int((time.perf_counter() - perf_start) * 1000.0),
        )

    def ask_global(
        self,
        cases: Sequence[CaBenh],
        results: dict[str, KetQuaThamDinh],
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
        *,
        vai_tro: str = "duoc_si_ls",
    ) -> AskResult:
        """Chế độ chung tạm thời chuyển thẳng cho bộ hỏi chung của luồng cũ."""
        perf_start = time.perf_counter()
        cleaned_question = cau_hoi.strip()
        if not 1 <= len(cleaned_question) <= 1000:
            raise ValueError("cau_hoi phải dài từ 1 đến 1000 ký tự sau khi cắt khoảng trắng")

        if self._llm is None:
            return AskResult(
                trang_thai="chua_san_sang",
                noi_dung=NOT_READY_MESSAGE,
                thoi_gian_ms=int((time.perf_counter() - perf_start) * 1000.0),
            )

        del vai_tro
        if self._global_asker is None:
            return AskResult(
                trang_thai="chua_san_sang",
                noi_dung=_GLOBAL_UNSUPPORTED_MESSAGE,
                thoi_gian_ms=int((time.perf_counter() - perf_start) * 1000.0),
            )
        return self._global_asker.ask_global(
            list(cases), dict(results), cleaned_question, list(lich_su or [])
        )
