"""Nạp kho đoạn JSONL hoặc PostgreSQL và dựng hai chỉ mục."""

import json
import logging
import math
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.errors import ProviderError, RetrievalError
from app.core.interfaces import Embedder, KeywordIndex, VectorStore
from app.core.types import Chunk

_LOGGER = logging.getLogger(__name__)

_CHUNK_COLUMNS = (
    "doan_trich_id",
    "tai_lieu_id",
    "muc_cha_id",
    "nhom_nguon",
    "nguon",
    "tang_tin_cay",
    "hoat_chat_ids",
    "muc",
    "duong_dan_muc",
    "loai_noi_dung",
    "ngon_ngu",
    "phien_ban_nguon",
    "url_goc",
    "noi_dung_goc",
    "noi_dung_nhung",
)
_CHUNK_WITH_EMBEDDING_COLUMNS = (*_CHUNK_COLUMNS, "embedding")

_SELECT_CHUNKS_SQL = (
    "SELECT doan_trich_id, tai_lieu_id, muc_cha_id, nhom_nguon, nguon, "
    "tang_tin_cay, hoat_chat_ids, muc, duong_dan_muc, loai_noi_dung, "
    "ngon_ngu, phien_ban_nguon, url_goc, noi_dung_goc, noi_dung_nhung "
    "FROM tri_thuc.doan_trich ORDER BY doan_trich_id"
)

_SELECT_CHUNKS_BY_INGREDIENTS_SQL = (
    "SELECT doan_trich_id, tai_lieu_id, muc_cha_id, nhom_nguon, nguon, "
    "tang_tin_cay, hoat_chat_ids, muc, duong_dan_muc, loai_noi_dung, "
    "ngon_ngu, phien_ban_nguon, url_goc, noi_dung_goc, noi_dung_nhung, "
    "embedding "
    "FROM tri_thuc.doan_trich "
    "WHERE hoat_chat_ids ?| %s "
    "ORDER BY doan_trich_id"
)


def parse_pg_vector(raw: Any, *, expected_dimensions: int | None = None) -> list[float] | None:
    """Chuyển chuỗi hoặc dãy số embedding từ DB thành list[float] có kiểm tra chiều."""
    if raw is None:
        return None
    if isinstance(raw, str):
        stripped = raw.strip()
        if not (stripped.startswith("[") and stripped.endswith("]")):
            raise RetrievalError("Định dạng véc-tơ từ cơ sở dữ liệu không hợp lệ")
        inner = stripped[1:-1].strip()
        if not inner:
            raise RetrievalError("Véc-tơ từ cơ sở dữ liệu rỗng")
        try:
            values = [float(part) for part in inner.split(",")]
        except ValueError:
            raise RetrievalError("Giá trị véc-tơ từ cơ sở dữ liệu không phải số") from None
    elif isinstance(raw, Sequence) and not isinstance(raw, bytes | bytearray | str):
        try:
            values = [float(item) for item in raw]
        except (TypeError, ValueError):
            raise RetrievalError("Giá trị véc-tơ từ cơ sở dữ liệu không hợp lệ") from None
    else:
        tolist = getattr(raw, "tolist", None)
        if callable(tolist):
            return parse_pg_vector(tolist(), expected_dimensions=expected_dimensions)
        raise RetrievalError("Kiểu dữ liệu véc-tơ từ cơ sở dữ liệu không hỗ trợ")

    if not values or any(not math.isfinite(item) for item in values):
        raise RetrievalError("Véc-tơ từ cơ sở dữ liệu rỗng hoặc không hữu hạn")
    if expected_dimensions is not None and len(values) != expected_dimensions:
        raise RetrievalError(
            f"Số chiều véc-tơ trên cơ sở dữ liệu ({len(values)}) "
            f"lệch cấu hình ({expected_dimensions})"
        )
    return values


def _row_to_values(row: Any, columns: tuple[str, ...]) -> dict[str, Any]:
    """Chuyển hàng tuple hoặc Mapping từ DB thành dict theo tên cột."""
    if isinstance(row, Mapping):
        return dict(row)
    return dict(zip(columns, row, strict=True))


def _values_to_chunk(values: dict[str, Any]) -> Chunk:
    """Xác thực một bản ghi đoạn từ cơ sở dữ liệu thành mô hình Chunk."""
    raw_ids = values.get("hoat_chat_ids")
    if isinstance(raw_ids, str):
        try:
            values["hoat_chat_ids"] = json.loads(raw_ids)
        except ValueError:
            raise RetrievalError("hoat_chat_ids không hợp lệ từ cơ sở dữ liệu") from None
    try:
        return Chunk.model_validate(values)
    except ValidationError:
        raise RetrievalError("Đoạn không hợp lệ từ cơ sở dữ liệu") from None


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


def load_corpus_from_db(conn: Any) -> list[Chunk]:
    """Nạp toàn bộ đoạn nguồn từ bảng tri_thuc.doan_trich theo thứ tự doan_trich_id."""
    cursor = conn.execute(_SELECT_CHUNKS_SQL)
    fetch = getattr(cursor, "fetchall", None)
    rows = fetch() if callable(fetch) else cursor
    return [_values_to_chunk(_row_to_values(row, _CHUNK_COLUMNS)) for row in rows]


def load_corpus_for_ingredients_from_db(
    conn: Any,
    ingredient_ids: Collection[str],
    *,
    expected_dimensions: int | None = None,
) -> list[tuple[Chunk, list[float] | None]]:
    """Truy vấn các đoạn thuộc tập hoạt chất kèm vector đã lưu trên DB."""
    keys = sorted({item.strip() for item in ingredient_ids if item and item.strip()})
    if not keys:
        return []
    cursor = conn.execute(_SELECT_CHUNKS_BY_INGREDIENTS_SQL, (keys,))
    fetch = getattr(cursor, "fetchall", None)
    rows = fetch() if callable(fetch) else cursor
    items: list[tuple[Chunk, list[float] | None]] = []
    for row in rows:
        values = _row_to_values(row, _CHUNK_WITH_EMBEDDING_COLUMNS)
        raw_embedding = values.pop("embedding", None)
        chunk = _values_to_chunk(values)
        vector = parse_pg_vector(raw_embedding, expected_dimensions=expected_dimensions)
        items.append((chunk, vector))
    return items


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


def index_corpus_with_precomputed(
    items: Sequence[tuple[Chunk, list[float] | None]],
    embedder: Embedder,
    vector_store: VectorStore,
    keyword_index: KeywordIndex,
    *,
    expected_dimensions: int | None = None,
) -> int:
    """Dựng BM25 toàn bộ và nạp vector có sẵn; chỉ nhúng bù đoạn thiếu embedding."""
    chunks = [chunk for chunk, _ in items]
    keyword_index.build(chunks)
    if not chunks:
        return 0

    target_dim = expected_dimensions if expected_dimensions is not None else embedder.dimensions
    if embedder.dimensions != target_dim:
        raise RetrievalError(
            f"Số chiều bộ nhúng ({embedder.dimensions}) lệch cấu hình ({target_dim})"
        )

    ready_chunks: list[Chunk] = []
    ready_vectors: list[list[float]] = []
    missing_chunks: list[Chunk] = []
    for chunk, vector in items:
        if vector is None:
            missing_chunks.append(chunk)
            continue
        if len(vector) != target_dim:
            raise RetrievalError(
                f"Số chiều véc-tơ ({len(vector)}) lệch cấu hình ({target_dim}); không trộn vector"
            )
        ready_chunks.append(chunk)
        ready_vectors.append(vector)

    if ready_chunks:
        loader = getattr(vector_store, "load_precomputed", None)
        if callable(loader):
            loader(ready_chunks, ready_vectors, expected_dimensions=target_dim)
        else:
            vector_store.upsert(ready_chunks, ready_vectors)

    if missing_chunks:
        _LOGGER.warning(
            "Có %d đoạn thiếu embedding trên DB; nhúng bù qua embedder",
            len(missing_chunks),
        )
        try:
            extra_vectors = embedder.embed_documents(
                [chunk.noi_dung_nhung for chunk in missing_chunks]
            )
        except ProviderError:
            return len(missing_chunks)
        if len(extra_vectors) != len(missing_chunks) or any(
            len(vector) != target_dim for vector in extra_vectors
        ):
            raise RetrievalError("Số lượng hoặc số chiều véc-tơ nhúng bù không khớp cấu hình")
        vector_store.upsert(missing_chunks, extra_vectors)

    return len(missing_chunks)
