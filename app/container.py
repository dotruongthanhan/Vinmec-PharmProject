"""Lắp ráp lười các thành phần qua bảng đăng ký nhà cung cấp."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from threading import Lock, RLock
from typing import TYPE_CHECKING, Any, cast

import psycopg

from app.config.settings import Settings, get_secret, load_settings
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
from app.db.read_pool import read_pool
from app.kb.interactions import InteractionStore
from app.kb.resolver import DrugResolver
from app.providers.bm25_index import Bm25Index
from app.providers.fakes import FakeLLM, HashEmbedder, NoopReranker
from app.providers.memory_store import InMemoryVectorStore
from app.rules.registry import RuleContext, default_rules
from app.rules.renal_dose import RenalRuleBook, load_renal_rules
from app.storage.case_repo import JsonCaseRepository

if TYPE_CHECKING:
    from app.orchestration.ask import CaseAsker

_ROOT = Path(__file__).resolve().parents[1]
_RULE_CONTEXT_LOCK = Lock()
_SHARED_RULE_CONTEXT: RuleContext | None = None
_NOT_FOUND = object()


class _LockedCachedProperty(cached_property):
    """Biến thể cached_property an toàn luồng dựa trên RLock của thực thể."""

    def __get__(self, instance: Any, owner: type[Any] | None = None) -> Any:
        if instance is None:
            return self
        if self.attrname is None:
            raise TypeError("Thuộc tính đệm chưa được gắn tên trên lớp.")
        cache = instance.__dict__
        val = cache.get(self.attrname, _NOT_FOUND)
        if val is not _NOT_FOUND:
            return val
        lock = getattr(instance, "_lock", None)
        if lock is None:
            return super().__get__(instance, owner)
        with lock:
            val = cache.get(self.attrname, _NOT_FOUND)
            if val is not _NOT_FOUND:
                return val
            val = self.func(instance)
            cache[self.attrname] = val
            return val


class Container:
    """Chỉ tạo từng phụ thuộc khi được truy cập lần đầu."""

    settings: Settings

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = RLock()

    def _resolve(self, kind: str, name: str) -> object:
        """Tra bảng đăng ký mà không rẽ nhánh theo tên nhà cung cấp."""
        factory = _PROVIDERS.get(kind, {}).get(name)
        if factory is None:
            raise ConfigError(f"Chưa có cài đặt cho {kind}.provider={name}")
        return factory(self)

    @_LockedCachedProperty
    def llm(self) -> LLMClient:
        return cast(LLMClient, self._resolve("llm", self.settings.llm.provider))

    @_LockedCachedProperty
    def embedder(self) -> Embedder:
        return cast(Embedder, self._resolve("embedding", self.settings.embedding.provider))

    @_LockedCachedProperty
    def reranker(self) -> Reranker:
        return cast(Reranker, self._resolve("rerank", self.settings.rerank.provider))

    @_LockedCachedProperty
    def vector_store(self) -> VectorStore:
        return cast(VectorStore, self._resolve("vector_store", self.settings.vector_store.provider))

    @_LockedCachedProperty
    def keyword_index(self) -> KeywordIndex:
        return Bm25Index()

    @_LockedCachedProperty
    def case_repo(self) -> CaseRepository:
        return JsonCaseRepository(_ROOT / self.settings.app.case_dir)

    @_LockedCachedProperty
    def renal_rules(self) -> RenalRuleBook:
        return load_renal_rules()

    @_LockedCachedProperty
    def rules(self) -> list[Rule]:
        return default_rules()

    def _resolve_path(self, raw_path: str) -> Path:
        raw = Path(raw_path)
        return raw if raw.is_absolute() else _ROOT / raw

    def _database_url(self) -> str | None:
        """Đọc chuỗi kết nối từ môi trường cấu hình, trả None nếu thiếu hoặc rỗng."""
        try:
            url = get_secret(self.settings.database.url_env).strip()
        except ConfigError:
            return None
        return url or None

    def _use_db(self, path: Path) -> bool:
        """Chọn đọc DB hay tệp cho một kho theo app.kb_source."""
        kb_source = self.settings.app.kb_source
        if kb_source == "db":
            return True
        if kb_source == "file":
            return False
        if path.is_file():
            return False
        return self._database_url() is not None

    @_LockedCachedProperty
    def drug_resolver(self) -> DrugResolver | None:
        """Chỉ mục vắng hoặc hỏng không ngăn các luật khác chạy."""
        path = self._resolve_path(self.settings.app.tra_cuu)
        if self._use_db(path):
            url = self._database_url()
            if url is None:
                logging.getLogger(__name__).debug(
                    "Không nạp được chỉ mục tra cứu từ DB: thiếu %s",
                    self.settings.database.url_env,
                )
                return None
            try:
                with read_pool.connection(url) as conn:
                    return DrugResolver.from_db(conn)
            except (OSError, psycopg.Error, sqlite3.Error, ValueError, ConfigError) as exc:
                logging.getLogger(__name__).debug(
                    "Không nạp được chỉ mục tra cứu từ DB: %s", type(exc).__name__
                )
                return None
        try:
            return DrugResolver.from_index(path)
        except (OSError, sqlite3.Error, ValueError) as exc:
            logging.getLogger(__name__).debug(
                "Không nạp được chỉ mục tra cứu: %s", type(exc).__name__
            )
            return None

    @_LockedCachedProperty
    def interaction_store(self) -> InteractionStore | None:
        """Nạp kho chỉ đọc một lần trong vòng đời container."""
        path = self._resolve_path(self.settings.app.tuong_tac)
        if self._use_db(path):
            url = self._database_url()
            if url is None:
                logging.getLogger(__name__).debug(
                    "Không nạp được bảng tương tác từ DB: thiếu %s",
                    self.settings.database.url_env,
                )
                return None
            try:
                with read_pool.connection(url) as conn:
                    return InteractionStore.from_db(conn, db_url=url)
            except (OSError, psycopg.Error, sqlite3.Error, ValueError, ConfigError) as exc:
                logging.getLogger(__name__).debug(
                    "Không nạp được bảng tương tác từ DB: %s", type(exc).__name__
                )
                return None
        try:
            return InteractionStore.from_path(path)
        except (OSError, sqlite3.Error, ValueError) as exc:
            logging.getLogger(__name__).debug(
                "Không nạp được bảng tương tác: %s", type(exc).__name__
            )
            return None

    @_LockedCachedProperty
    def rule_context(self) -> RuleContext:
        ctx = RuleContext(self.renal_rules, self.drug_resolver, self.interaction_store)
        tra_cuu_source = (
            "tri_thuc.tra_cuu_*"
            if self._use_db(self._resolve_path(self.settings.app.tra_cuu))
            else "tra_cuu.sqlite"
        )
        tuong_tac_source = (
            "tri_thuc.ddinter_*"
            if self._use_db(self._resolve_path(self.settings.app.tuong_tac))
            else "ddinter.sqlite"
        )
        missing = [
            name
            for name, dependency in (
                (tra_cuu_source, ctx.resolver),
                (tuong_tac_source, ctx.interactions),
            )
            if dependency is None
        ]
        if missing:
            logging.getLogger(__name__).warning(
                "Không chạy yếu tố 4: chỉ mục thiếu hoặc hỏng: %s", ", ".join(missing)
            )
        return ctx

    @_LockedCachedProperty
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
        retriever: LazyRetrieverFactory | None
        if self._use_db(corpus_path):
            if self._database_url() is None:
                logging.getLogger(__name__).warning(
                    "Không nạp được kho đoạn từ tri_thuc.doan_trich: thiếu %s",
                    self.settings.database.url_env,
                )
                retriever = None
            else:
                retriever = LazyRetrieverFactory(self, use_db=True)
        elif corpus_path.is_file():
            retriever = LazyRetrieverFactory(self, corpus_path, use_db=False)
        else:
            retriever = None
        names = DrugNameIndex.load()
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


def get_rule_context() -> RuleContext:
    """Giữ chỉ mục dùng chung cho API, DB và Streamlit trong tiến trình."""
    global _SHARED_RULE_CONTEXT
    with _RULE_CONTEXT_LOCK:
        if _SHARED_RULE_CONTEXT is None:
            _SHARED_RULE_CONTEXT = build_container().rule_context
        return _SHARED_RULE_CONTEXT
