"""Lắp ráp máy khách LLM và Synthesizer từ Container mà không sửa app/container.py."""

import logging
from pathlib import Path

from app.config.settings import get_secret
from app.container import Container
from app.core.errors import ConfigError
from app.core.interfaces import LLMClient
from app.llm.synthesizer import Synthesizer
from app.providers.http import create_client
from app.providers.llm_client import ChatLLMClient

_ROOT = Path(__file__).resolve().parents[2]


def build_llm(container: Container) -> LLMClient:
    """Tạo máy khách LLM theo cấu hình, đọc bí mật tập trung."""
    settings = container.settings
    provider = settings.llm.provider
    if provider == "fake":
        return container.llm
    if provider == "chat_api":
        keys: list[str] = []
        for name in settings.llm.khoa_env:
            try:
                key = get_secret(name).strip()
            except ConfigError:
                key = ""
            if key:
                keys.append(key)
            else:
                logging.getLogger(__name__).warning("Thiếu khoá trong biến %s", name)
        if not keys:
            raise ConfigError("khong_co_khoa_llm")
        # CHỈ DÙNG CHO DEV: xoay nhiều khoá miễn phí. Triển khai thật: xoá module này, dùng một khoá trả phí (khoa_env một phần tử).  # noqa: E501
        return ChatLLMClient(
            model=settings.llm.model,
            url=settings.llm.url,
            keys=keys,
            client=create_client(),
            temperature=settings.generation.temperature,
            max_tokens=settings.llm.max_tokens,
            max_tokens_retry=settings.llm.max_tokens_retry,
            reasoning=settings.llm.reasoning,
            top_p=settings.generation.top_p,
            max_attempts=settings.agent.max_attempts,
            cho_khoa_toi_da_giay=settings.llm.cho_khoa_toi_da_giay,
        )
    raise ConfigError(f"Chưa có cài đặt cho llm.provider={provider}")


def build_synthesizer(container: Container) -> Synthesizer:
    """Lắp đặt Synthesizer; thiếu khoá thì lui về chế độ không có LLM."""
    settings = container.settings
    llm: LLMClient | None
    try:
        llm = build_llm(container)
    except ConfigError as exc:
        if settings.llm.provider == "chat_api" and str(exc) == "khong_co_khoa_llm":
            llm = None
        else:
            raise

    raw_prompt = Path(settings.prompts.tong_hop)
    prompt_path = raw_prompt if raw_prompt.is_absolute() else _ROOT / raw_prompt
    return Synthesizer(
        llm=llm,
        prompt_path=prompt_path,
        case_settings=settings.case_context,
        evidence_max_chars=settings.evidence.max_chars,
        max_synthesis_attempts=settings.agent.max_synthesis_attempts,
        model_name=settings.llm.model,
    )
