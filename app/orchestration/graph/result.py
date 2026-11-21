"""Kết quả một lượt phân tích AI, dùng chung cho đường tuần tự và đồ thị."""

from pydantic import BaseModel, ConfigDict

from app.core.types import Chunk
from app.llm.schema import KetQuaLLM


class AiRunResult(BaseModel):
    """Kết quả một lượt phân tích AI gồm đầu ra LLM, đoạn nguồn và cảnh báo."""

    model_config = ConfigDict(extra="forbid")

    llm: KetQuaLLM
    doan: list[Chunk]
    canh_bao: list[str]
    thoi_gian_ms: float
