"""Nạp kho đoạn JSONL và dựng hai chỉ mục."""

from pathlib import Path

from pydantic import ValidationError

from app.core.errors import ProviderError, RetrievalError
from app.core.interfaces import Embedder, KeywordIndex, VectorStore
from app.core.types import Chunk


def load_corpus(path: Path) -> list[Chunk]:
    """Nạp mỗi dòng không rỗng thành một đoạn có kiểm tra kiểu."""
    try:
        with path.open(encoding="utf-8") as source:
            chunks = []
            for line_number, line in enumerate(source, start=1):
                if line.strip():
                    try:
                        chunks.append(Chunk.model_validate_json(line))
                    except ValidationError:
                        raise RetrievalError(
                            f"Đoạn không hợp lệ tại {path}, dòng {line_number}"
                        ) from None
            return chunks
    except FileNotFoundError:
        raise RetrievalError(f"Không có kho đoạn {path}; chạy python -m app.kb.build") from None
    except (OSError, UnicodeError):
        raise RetrievalError(f"Không đọc được kho đoạn {path}") from None


def index_corpus(
    chunks: list[Chunk], embedder: Embedder, vector_store: VectorStore, keyword_index: KeywordIndex
) -> None:
    """Lập chỉ mục từ khoá trước, sau đó nhúng nội dung nguồn nạp kho véc-tơ."""
    keyword_index.build(chunks)
    try:
        vectors = embedder.embed_documents([chunk.noi_dung_nhung for chunk in chunks])
    except ProviderError:
        return
    vector_store.upsert(chunks, vectors)
