"""Chạy một lượt phân tích AI (thu thập đoạn nguồn và tổng hợp LLM có kiểm chứng)."""

import time
from typing import Any, Literal

from langsmith import tracing_context

from app.config.settings import load_settings
from app.core.errors import ConfigError
from app.core.types import Chunk
from app.domain.models import CaBenh
from app.llm.schema import KetQuaLLM, NhanDinhCuoi
from app.llm.synthesizer import Synthesizer
from app.orchestration.evidence import EvidenceCollector
from app.orchestration.graph import dung_do_thi
from app.orchestration.graph.nodes import dung_ket_qua_loi
from app.orchestration.graph.result import AiRunResult
from app.pipeline import KetQuaThamDinh

Engine = Literal["langgraph", "tuan_tu"]
_ENGINES = ("langgraph", "tuan_tu")

__all__ = ["AiReviewer", "AiRunResult"]


def _engine_from_settings() -> Engine:
    """Đọc `orchestration.engine` trong cấu hình; không đọc được thì dùng đường tuần tự."""
    try:
        return load_settings().orchestration.engine
    except ConfigError:
        return "tuan_tu"


class AiReviewer:
    """Nối bước thu thập đoạn nguồn với Synthesizer cho từng ca bệnh.

    `engine` chọn đường chạy: "langgraph" (đồ thị luồng thẳng, biên dịch một lần ở đây) hoặc
    "tuan_tu" (hàm tuần tự cũ). Bỏ trống thì lấy từ `orchestration.engine` trong cấu hình.
    """

    def __init__(
        self,
        collector: EvidenceCollector,
        synthesizer: Synthesizer,
        engine: Engine | None = None,
    ) -> None:
        self._collector = collector
        self._synthesizer = synthesizer
        selected = engine if engine is not None else _engine_from_settings()
        if selected not in _ENGINES:
            raise ValueError(f"engine không hợp lệ: {selected}")
        self._engine: Engine = selected
        self._graph: Any = dung_do_thi(collector, synthesizer) if selected == "langgraph" else None

    @property
    def engine(self) -> Engine:
        """Đường chạy đang dùng: "langgraph" hoặc "tuan_tu"."""
        return self._engine

    @property
    def model_name(self) -> str | None:
        """Tên mô hình LLM đang được cấu hình cho bộ tổng hợp."""
        return self._synthesizer.model_name

    def run(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult:
        """Chạy bước AI cho ca bệnh và bọc mọi ngoại lệ không mong muốn."""
        if self._graph is not None:
            return self._run_graph(ca, ket_qua)
        return self._run_sequential(ca, ket_qua)

    def _run_graph(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult:
        """Chạy đồ thị LangGraph; tắt tracing của LangSmith cho lượt chạy này."""
        start = time.perf_counter()
        try:
            with tracing_context(enabled=False):
                final = self._graph.invoke(
                    {
                        "ca": ca,
                        "ket_qua_luat": ket_qua,
                        "doan": [],
                        "canh_bao": [],
                        "thoi_gian_bat_dau": start,
                    }
                )
            result = final["ket_qua"]
            if not isinstance(result, AiRunResult):
                raise TypeError("ket_qua")
            return result
        except Exception as exc:
            warning = f"Bước AI gặp lỗi không mong muốn ({type(exc).__name__})"
            return dung_ket_qua_loi(self._synthesizer, ket_qua, [], warning, start)

    def _run_sequential(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult:
        """Đường tuần tự cũ: thu thập rồi tổng hợp, bọc mọi ngoại lệ không mong muốn."""
        start = time.perf_counter()
        chunks: list[Chunk] = []
        try:
            chunks, collect_warnings = self._collector.collect(ca, ket_qua)
            llm_result = self._synthesizer.run(ca, ket_qua, chunks)
            warnings = list(dict.fromkeys([*collect_warnings, *llm_result.canh_bao]))
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return AiRunResult(
                llm=llm_result,
                doan=chunks,
                canh_bao=warnings,
                thoi_gian_ms=elapsed_ms,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            warning = f"Bước AI gặp lỗi không mong muốn ({type(exc).__name__})"
            prompt_version = getattr(getattr(self._synthesizer, "prompt_path", None), "stem", "")
            model_name = getattr(self._synthesizer, "model_name", None)
            rule_only = [NhanDinhCuoi(nguon_goc="luat", phat_hien=ph) for ph in ket_qua.phat_hien]
            llm_error = KetQuaLLM(
                trang_thai="loi_llm",
                nhan_dinh=rule_only,
                so_lan_goi=0,
                canh_bao=[warning],
                phien_ban_prompt=prompt_version,
                mo_hinh=model_name,
            )
            return AiRunResult(
                llm=llm_error,
                doan=chunks,
                canh_bao=[warning],
                thoi_gian_ms=elapsed_ms,
            )
