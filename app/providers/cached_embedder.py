"""Bộ đệm SQLite cho véc-tơ tài liệu và truy vấn."""

import hashlib
import sqlite3
from pathlib import Path
from typing import Literal

import numpy as np

from app.core.errors import ProviderError
from app.core.interfaces import Embedder


class CachedEmbedder:
    """Tách khoá theo mô hình và loại văn bản, lưu véc-tơ float32."""

    def __init__(self, inner: Embedder, cache_path: Path, model_id: str) -> None:
        self.inner = inner
        self.dimensions = inner.dimensions
        self.model_id = model_id
        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._hits = 0
        self._misses = 0
        with sqlite3.connect(self.cache_path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS embeddings "
                "(key TEXT PRIMARY KEY, dims INTEGER, vec BLOB)"
            )

    def _key(self, kind: Literal["doc", "query"], text: str) -> str:
        """Băm mô hình, loại và nguyên văn."""
        return hashlib.sha256(f"{self.model_id}\n{kind}\n{text}".encode()).hexdigest()

    def _embed(self, texts: list[str], kind: Literal["doc", "query"]) -> list[list[float]]:
        """Gộp văn bản chưa có thành một lô, giữ thứ tự đầu vào."""
        if any(not text.strip() for text in texts):
            raise ValueError("Văn bản nhúng không được rỗng")
        if not texts:
            return []
        keys = [self._key(kind, text) for text in texts]
        cached: dict[str, list[float]] = {}
        missing: dict[str, str] = {}
        with sqlite3.connect(self.cache_path) as connection:
            for key, text in zip(keys, texts, strict=True):
                row = connection.execute(
                    "SELECT dims, vec FROM embeddings WHERE key = ?", (key,)
                ).fetchone()
                if row is None:
                    self._misses += 1
                    missing[key] = text
                else:
                    self._hits += 1
                    vector = np.frombuffer(row[1], dtype=np.float32)
                    if row[0] != self.dimensions or len(vector) != self.dimensions:
                        raise ProviderError("Số chiều bộ đệm không khớp", retryable=False)
                    cached[key] = vector.tolist()
            if missing:
                vectors = (
                    self.inner.embed_documents(list(missing.values()))
                    if kind == "doc"
                    else [self.inner.embed_query(text) for text in missing.values()]
                )
                if len(vectors) != len(missing) or any(
                    len(vector) != self.dimensions for vector in vectors
                ):
                    raise ProviderError("Số lượng hoặc số chiều véc-tơ không khớp", retryable=False)
                for key, vector in zip(missing, vectors, strict=True):
                    array = np.asarray(vector, dtype=np.float32)
                    connection.execute(
                        "INSERT OR REPLACE INTO embeddings(key, dims, vec) VALUES (?, ?, ?)",
                        (key, self.dimensions, array.tobytes()),
                    )
                    cached[key] = array.tolist()
        return [list(cached[key]) for key in keys]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Nhúng chỉ những đoạn nguồn chưa có trong bộ đệm."""
        return self._embed(texts, "doc")

    def embed_query(self, text: str) -> list[float]:
        """Nhúng truy vấn bằng khoá độc lập với tài liệu."""
        return self._embed([text], "query")[0]

    def stats(self) -> dict[str, int]:
        """Trả số lần trúng và thiếu bộ đệm của đối tượng này."""
        return {"hits": self._hits, "misses": self._misses}
