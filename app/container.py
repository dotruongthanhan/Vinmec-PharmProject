"""Lắp ráp lười các thành phần qua bảng đăng ký nhà cung cấp."""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, cast

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
from app.rules.interaction import InteractionBook, load_interaction_rules_if_exists
from app.rules.registry import default_rules
from app.rules.renal_dose import RenalRuleBook, load_renal_rules
from app.storage.case_repo import JsonCaseRepository

if TYPE_CHECKING:
    from app.orchestration.ask import CaseAsker

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
    def interaction_rules(self) -> InteractionBook:
        return load_interaction_rules_if_exists(_ROOT / "data/kb_curated/tuong_tac.jsonl")

    @cached_property
    def rules(self) -> list[Rule]:
        return default_rules()

    @cached_property
    def case_asker(self) -> CaseAsker:
        """Dựng bộ hỏi đáp theo ca từ cấu hình, máy khách LLM, bộ truy xuất và prompt."""
        from app.kb.names import DrugNameIndex
        from app.llm import setup as llm_setup
        from app.orchestration.ask import CaseAsker
        from app.orchestration.evidence import LazyRetrieverFactory
        from app.retrieval.query_builder import QueryBuilder

        try:
            llm: LLMClient | None = llm_setup.build_llm(self)
        except ConfigError as exc:
            if self.settings.llm.provider == "deepseek" and str(exc) == "DEEPSEEK_API_KEY":
                llm = None
            else:
                raise

        corpus_path = _ROOT / "data/kb_curated/chunks.jsonl"
        retriever = LazyRetrieverFactory(self, corpus_path) if corpus_path.is_file() else None
        names = DrugNameIndex.load(_ROOT / "data/kb/hoat_chat.json")
        raw_prompt = Path(self.settings.prompts.hoi_them)
        prompt_path = raw_prompt if raw_prompt.is_absolute() else _ROOT / raw_prompt
        return CaseAsker(
            llm=llm,
            retriever=retriever,
            query_builder=QueryBuilder(self.settings.retrieval),
            resolve_name=names.resolve,
            prompt_path=prompt_path,
            case_settings=self.settings.case_context,
            evidence_max_chars=self.settings.evidence.max_chars,
            model_name=self.settings.llm.model if llm is not None else None,
            renal_rules=self.renal_rules,
        )


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
