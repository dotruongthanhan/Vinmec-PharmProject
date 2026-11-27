"""Kiểm thử lắp ráp LLM và Synthesizer trong app/llm/setup.py."""

from pathlib import Path

import pytest

from app.config.settings import load_settings
from app.container import build_container
from app.core.errors import ConfigError
from app.llm.setup import build_llm, build_synthesizer
from app.llm.synthesizer import Synthesizer
from app.providers.fakes import FakeLLM
from app.providers.llm_client import ChatLLMClient


def test_build_llm_and_synthesizer_for_test_profile() -> None:
    container = build_container("test")
    llm = build_llm(container)
    assert isinstance(llm, FakeLLM)

    synth = build_synthesizer(container)
    assert isinstance(synth, Synthesizer)
    assert synth.llm is llm


def test_build_llm_for_chat_api_uses_env_and_configured_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY_1", "test-only-token")
    container = build_container("dev")

    llm = build_llm(container)
    assert isinstance(llm, ChatLLMClient)
    assert llm.model == container.settings.llm.model
    assert llm.temperature == container.settings.generation.temperature
    assert llm.max_tokens == container.settings.llm.max_tokens
    assert llm.max_tokens_retry == container.settings.llm.max_tokens_retry
    assert llm.reasoning == container.settings.llm.reasoning
    assert llm.top_p == container.settings.generation.top_p
    assert llm.max_attempts == container.settings.agent.max_attempts

    synth = build_synthesizer(container)
    assert isinstance(synth.llm, ChatLLMClient)
    assert synth.prompt_path.is_file()


def test_load_settings_has_llm_token_budgets() -> None:
    settings = load_settings()
    assert settings.llm.max_tokens == 16000
    assert settings.llm.max_tokens_retry == 32000
    assert settings.llm.reasoning == {"reasoning_effort": "low"}


def test_build_synthesizer_falls_back_when_chat_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_missing(_name: str) -> str:
        raise ConfigError("missing")

    monkeypatch.setattr("app.llm.setup.get_secret", raise_missing)
    container = build_container("dev")

    with pytest.raises(ConfigError, match="khong_co_khoa_llm"):
        build_llm(container)

    synth = build_synthesizer(container)
    assert synth.llm is None
