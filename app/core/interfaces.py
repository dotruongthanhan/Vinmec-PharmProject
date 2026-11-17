"""Mười hai hợp đồng nhỏ cho các thành phần thay thế được."""

from typing import Protocol, runtime_checkable

from app.core.types import ChatMessage, Chunk, RetrievalQuery, ScoredChunk, SearchFilter, ToolResult
from app.domain.models import CaBenh
from app.rules.registry import RuleContext
from app.rules.types import PhatHien


@runtime_checkable
class LLMClient(Protocol):
    def complete_json(self, messages: list[ChatMessage], schema: dict) -> dict: ...


@runtime_checkable
class Embedder(Protocol):
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


@runtime_checkable
class Reranker(Protocol):
    def rerank(self, query: str, passages: list[str], top_n: int) -> list[tuple[int, float]]: ...


@runtime_checkable
class VectorStore(Protocol):
    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None: ...
    def search(self, vector: list[float], k: int, bo_loc: SearchFilter) -> list[ScoredChunk]: ...
    def count(self) -> int: ...


@runtime_checkable
class KeywordIndex(Protocol):
    def build(self, chunks: list[Chunk]) -> None: ...
    def search(self, query: str, k: int, bo_loc: SearchFilter) -> list[ScoredChunk]: ...


@runtime_checkable
class Chunker(Protocol):
    def split(self, document: dict) -> list[Chunk]: ...


@runtime_checkable
class Retriever(Protocol):
    def retrieve(self, query: RetrievalQuery) -> list[ScoredChunk]: ...


@runtime_checkable
class Rule(Protocol):
    ma_nhom: str
    yeu_to: int

    def check(self, ca: CaBenh, ctx: RuleContext) -> list[PhatHien]: ...


@runtime_checkable
class Tool(Protocol):
    name: str

    def run(self, args: dict, ca: CaBenh) -> ToolResult: ...


@runtime_checkable
class Verifier(Protocol):
    def verify(self, nhan_dinh: dict, goi_can_cu: list[Chunk]) -> list[str]: ...


@runtime_checkable
class CaseRepository(Protocol):
    def list_ids(self) -> list[str]: ...
    def get(self, ca_id: str) -> CaBenh: ...


@runtime_checkable
class AuditLog(Protocol):
    def record(self, event: dict) -> None: ...
