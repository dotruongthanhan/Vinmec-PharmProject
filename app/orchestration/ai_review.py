"""Chạy một lượt phân tích AI (thu thập đoạn nguồn và tổng hợp LLM có kiểm chứng)."""

import time

from pydantic import BaseModel, ConfigDict

from app.core.types import Chunk
from app.domain.models import CaBenh
from app.llm.schema import KetQuaLLM, NhanDinhCuoi
from app.llm.synthesizer import Synthesizer
from app.orchestration.evidence import EvidenceCollector
from app.pipeline import KetQuaThamDinh


class AiRunResult(BaseModel):
    """Kết quả một lượt phân tích AI gồm đầu ra LLM, đoạn nguồn và cảnh báo."""

    model_config = ConfigDict(extra="forbid")

    llm: KetQuaLLM
    doan: list[Chunk]
    canh_bao: list[str]
    thoi_gian_ms: float


class AiReviewer:
    """Nối bước thu thập đoạn nguồn với Synthesizer cho từng ca bệnh."""

    def __init__(self, collector: EvidenceCollector, synthesizer: Synthesizer) -> None:
        self._collector = collector
        self._synthesizer = synthesizer

    @property
    def model_name(self) -> str | None:
        """Tên mô hình LLM đang được cấu hình cho bộ tổng hợp."""
        return self._synthesizer.model_name

    def run(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult:
        """Chạy bước AI cho ca bệnh và bọc mọi ngoại lệ không mong muốn."""
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
