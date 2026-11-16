"""Lắp ráp lười các thành phần qua bảng đăng ký nhà cung cấp."""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from typing import cast

from app.config.settings import Settings, load_settings
from app.core.errors import ConfigError
from app.core.interfaces import (
    CaseRepository,
    Embedder,
    KeywordIndex,
    LLMClient,
    Reranker,
    Rule,
    VectorStore,
)
from app.providers.bm25_index import Bm25Index
from app.providers.fakes import FakeLLM, HashEmbedder, NoopReranker
from app.providers.memory_store import InMemoryVectorStore
from app.rules.registry import default_rules
from app.rules.renal_dose import RenalRuleBook, load_renal_rules
from app.storage.case_repo import JsonCaseRepository

_ROOT = Path(__file__).resolve().parents[1]


class Container:
    """Chỉ tạo từng phụ thuộc khi được truy cập lần đầu."""

    settings: Settings

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _resolve(self, kind: str, name: str) -> object:
        """Tra bảng đăng ký mà không rẽ nhánh theo tên nhà cung cấp."""
        factory = _PROVIDERS.get(kind, {}).get(name)
        if factory is None:
            raise ConfigError(f"Chưa có cài đặt cho {kind}.provider={name}")
        return factory(self)

    @cached_property
    def llm(self) -> LLMClient:
        return cast(LLMClient, self._resolve("llm", self.settings.llm.provider))

    @cached_property
    def embedder(self) -> Embedder:
        return cast(Embedder, self._resolve("embedding", self.settings.embedding.provider))

    @cached_property
    def reranker(self) -> Reranker:
        return cast(Reranker, self._resolve("rerank", self.settings.rerank.provider))

    @cached_property
    def vector_store(self) -> VectorStore:
        return cast(VectorStore, self._resolve("vector_store", self.settings.vector_store.provider))

    @cached_property
    def keyword_index(self) -> KeywordIndex:
        return Bm25Index()

    @cached_property
    def case_repo(self) -> CaseRepository:
        return JsonCaseRepository(_ROOT / self.settings.app.case_dir)

    @cached_property
    def renal_rules(self) -> RenalRuleBook:
        return load_renal_rules(_ROOT / "data/kb/quy_tac_lieu_than.json")

    @cached_property
    def rules(self) -> list[Rule]:
        return default_rules()


_PROVIDERS: dict[str, dict[str, Callable[[Container], object]]] = {
    "llm": {"fake": lambda container: FakeLLM([])},
    "embedding": {"fake": lambda container: HashEmbedder(container.settings.embedding.dimensions)},
    "rerank": {"noop": lambda container: NoopReranker()},
    "vector_store": {"memory": lambda container: InMemoryVectorStore()},
}


def register_provider(kind: str, name: str, factory: Callable[[Container], object]) -> None:
    """Đăng ký cài đặt cho các task tiếp theo."""
    _PROVIDERS.setdefault(kind, {})[name] = factory


def build_container(profile: str | None = None) -> Container:
    """Nạp cấu hình và tạo nơi lắp ráp chưa khởi tạo các nhà cung cấp."""
    return Container(load_settings(profile))
