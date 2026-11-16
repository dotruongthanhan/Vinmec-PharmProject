"""Kho véc-tơ trong bộ nhớ, tìm cosine sau khi lọc."""

import numpy as np
from numpy.typing import NDArray

from app.core.errors import RetrievalError
from app.core.types import Chunk, ScoredChunk, SearchFilter, matches


class InMemoryVectorStore:
    """Giữ đoạn nguồn và ma trận véc-tơ cùng thứ tự."""

    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._vectors: NDArray[np.float64] = np.empty((0, 0), dtype=float)

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Thêm hoặc thay thế theo mã đoạn, kiểm tra toàn bộ trước khi ghi."""
        if len(chunks) != len(vectors):
            raise RetrievalError("Số đoạn và số véc-tơ không khớp")
        if not chunks:
            return
        try:
            matrix = np.asarray(vectors, dtype=float)
        except (TypeError, ValueError) as exc:
            raise RetrievalError("Số chiều véc-tơ không khớp") from exc
        if matrix.ndim != 2 or matrix.shape[1] == 0:
            raise RetrievalError("Số chiều véc-tơ không hợp lệ")
        if self._chunks and matrix.shape[1] != self._vectors.shape[1]:
            raise RetrievalError("Số chiều véc-tơ không khớp")
        positions = {chunk.doan_trich_id: index for index, chunk in enumerate(self._chunks)}
        updated_chunks = list(self._chunks)
        rows = list(self._vectors)
        for chunk, row in zip(chunks, matrix, strict=True):
            index = positions.get(chunk.doan_trich_id)
            if index is None:
                positions[chunk.doan_trich_id] = len(updated_chunks)
                updated_chunks.append(chunk)
                rows.append(row)
            else:
                updated_chunks[index] = chunk
                rows[index] = row
        self._chunks = updated_chunks
        self._vectors = np.asarray(rows, dtype=float)

    def search(self, vector: list[float], k: int, bo_loc: SearchFilter) -> list[ScoredChunk]:
        """Lọc trước, rồi lấy k đoạn có cosine cao nhất; véc-tơ 0 có điểm 0."""
        try:
            query = np.asarray(vector, dtype=float)
        except (TypeError, ValueError) as exc:
            raise RetrievalError("Số chiều truy vấn không hợp lệ") from exc
        if query.ndim != 1 or query.size == 0:
            raise RetrievalError("Số chiều truy vấn không hợp lệ")
        if self._chunks and query.size != self._vectors.shape[1]:
            raise RetrievalError("Số chiều truy vấn không khớp")
        indices = [index for index, chunk in enumerate(self._chunks) if matches(chunk, bo_loc)]
        if not indices or k <= 0:
            return []
        matrix = self._vectors[indices]
        denominators = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query)
        scores = np.divide(
            matrix @ query, denominators, out=np.zeros(len(indices)), where=denominators != 0
        )
        ranking = np.argsort(-scores, kind="stable")[:k]
        return [
            ScoredChunk(chunk=self._chunks[indices[i]], diem=float(scores[i]), nguon_diem="vec_to")
            for i in ranking
        ]

    def count(self) -> int:
        """Đếm số mã đoạn duy nhất."""
        return len(self._chunks)
