"""Hỗ trợ kiểm thử: tra mã tạm (R1, R2...) mà LLM nhìn thấy cho mã bản ghi thật của ca mẫu."""

from functools import cache

from app.container import build_container
from app.llm.case_context import build_case_bundle
from app.pipeline import run_case


@cache
def _temp_ids(ca_id: str) -> dict[str, str]:
    container = build_container("test")
    ca = container.case_repo.get(ca_id)
    bundle = build_case_bundle(
        ca, run_case(ca, container.renal_rules), container.settings.case_context
    )
    return {real: temp for temp, real in bundle.ma_ban_ghi.anh_xa.items()}


def temp_id(ca_id: str, real_id: str) -> str:
    """Mã tạm của một bản ghi thật trong ngữ cảnh gửi LLM của ca mẫu."""
    return _temp_ids(ca_id)[real_id]
