from pathlib import Path

import pytest

from app.container import Container, build_container, register_provider
from app.core.errors import ConfigError
from app.core.interfaces import (
    CaseRepository,
    Embedder,
    KeywordIndex,
    LLMClient,
    Reranker,
    VectorStore,
)
from app.providers.fakes import FakeLLM


def test_test_container_protocols_and_caching() -> None:
    container = build_container("test")
    for name, protocol in [
        ("llm", LLMClient),
        ("embedder", Embedder),
        ("reranker", Reranker),
        ("vector_store", VectorStore),
        ("keyword_index", KeywordIndex),
        ("case_repo", CaseRepository),
    ]:
        assert isinstance(getattr(container, name), protocol)
        assert getattr(container, name) is getattr(container, name)
    assert container.embedder.dimensions == container.settings.embedding.dimensions
    assert len(container.rules) == 6
    assert len(container.case_repo.list_ids()) == 6
    assert container.renal_rules is container.renal_rules
    assert container.rules is container.rules


def test_dev_container_is_lazy_and_independent_of_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    container = build_container("dev")
    assert len(container.case_repo.list_ids()) == 6
    assert len(container.rules) == 6
    for name, block, provider in [
        ("llm", "llm", "deepseek"),
        ("embedder", "embedding", "openrouter"),
        ("reranker", "rerank", "openrouter"),
        ("vector_store", "vector_store", "pgvector"),
    ]:
        with pytest.raises(ConfigError) as error:
            getattr(container, name)
        assert str(error.value) == f"Chưa có cài đặt cho {block}.provider={provider}"


def test_provider_registration() -> None:
    llm = FakeLLM([{"ok": True}])
    seen: list[Container] = []

    def factory(container: Container) -> FakeLLM:
        seen.append(container)
        return llm

    register_provider("llm", "t11_custom", factory)
    settings = build_container("test").settings
    custom_llm = settings.llm.model_copy(update={"provider": "t11_custom"})
    container = Container(settings.model_copy(update={"llm": custom_llm}))
    assert container.llm is llm
    assert container.llm is llm
    assert seen == [container]
