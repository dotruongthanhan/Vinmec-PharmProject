"""Lắp ráp máy khách LLM và Synthesizer từ Container mà không sửa app/container.py."""

from pathlib import Path

from app.config.settings import get_secret
from app.container import Container
from app.core.errors import ConfigError
from app.core.interfaces import LLMClient
from app.llm.synthesizer import Synthesizer
from app.providers.deepseek_llm import DeepSeekLLM
from app.providers.http import create_client

_ROOT = Path(__file__).resolve().parents[2]


def build_llm(container: Container) -> LLMClient:
    """Tạo máy khách LLM theo cấu hình, đọc bí mật tập trung khi dùng DeepSeek."""
    settings = container.settings
    provider = settings.llm.provider
    if provider == "fake":
        return container.llm
    if provider == "deepseek":
        api_key = get_secret("DEEPSEEK_API_KEY")
        return DeepSeekLLM(
            model=settings.llm.model,
            api_key=api_key,
            client=create_client(),
            temperature=settings.generation.temperature,
            max_tokens=settings.llm.max_tokens,
            max_tokens_retry=settings.llm.max_tokens_retry,
            reasoning=settings.llm.reasoning,
            top_p=settings.generation.top_p,
            max_attempts=settings.agent.max_attempts,
        )
    raise ConfigError(f"Chưa có cài đặt cho llm.provider={provider}")


def build_synthesizer(container: Container) -> Synthesizer:
    """Lắp đặt Synthesizer từ Container; thiếu khoá DeepSeek thì lui về chế độ không có LLM."""
    settings = container.settings
    llm: LLMClient | None
    try:
        llm = build_llm(container)
    except ConfigError as exc:
        if settings.llm.provider == "deepseek" and str(exc) == "DEEPSEEK_API_KEY":
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
