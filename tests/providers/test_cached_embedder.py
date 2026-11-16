import hashlib
import sqlite3
from pathlib import Path

import numpy as np
import pytest

from app.providers.cached_embedder import CachedEmbedder
from app.providers.fakes import HashEmbedder


class RecordingEmbedder(HashEmbedder):
    """Ghi nhận đầu vào của hai phương thức nhúng độc lập."""

    def __init__(self) -> None:
        super().__init__(8)
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(list(texts))
        return [super(RecordingEmbedder, self).embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return super().embed_query(text)


def test_cache_hits_mixed_order_duplicates_and_stats(tmp_path: Path) -> None:
    inner = RecordingEmbedder()
    cache = CachedEmbedder(inner, tmp_path / "nested" / "vectors.sqlite", "modele-a")
    first = cache.embed_documents(["nguồn a", "nguồn b"])
    assert cache.embed_documents(["nguồn a", "nguồn b"]) == first
    mixed = cache.embed_documents(["nguồn b", "nguồn c", "nguồn a", "nguồn c"])
    assert mixed == [first[1], mixed[1], first[0], mixed[1]]
    assert inner.document_calls == [["nguồn a", "nguồn b"], ["nguồn c"]]
    assert mixed[1] == pytest.approx(HashEmbedder(8).embed_query("nguồn c"), abs=1e-6)
    assert cache.stats() == {"hits": 4, "misses": 4}
    assert cache.embed_documents([]) == []


def test_query_doc_model_and_persistence_are_separate(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite"
    inner = RecordingEmbedder()
    cache = CachedEmbedder(inner, path, "modele-a")
    document = cache.embed_documents(["meropenem"])[0]
    query = cache.embed_query("meropenem")
    assert cache.embed_query("meropenem") == query
    assert inner.document_calls == [["meropenem"]]
    assert inner.query_calls == ["meropenem"]
    reopened = CachedEmbedder(inner, path, "modele-a")
    assert reopened.embed_documents(["meropenem"])[0] == pytest.approx(document, abs=1e-6)
    assert len(inner.document_calls) == 1
    CachedEmbedder(inner, path, "modele-b").embed_documents(["meropenem"])
    assert len(inner.document_calls) == 2
    with sqlite3.connect(path) as connection:
        rows = connection.execute("SELECT key, dims, vec FROM embeddings").fetchall()
    assert len(rows) == 3
    expected_key = hashlib.sha256(b"modele-a\ndoc\nmeropenem").hexdigest()
    row = next(row for row in rows if row[0] == expected_key)
    assert row[1] == 8
    assert len(row[2]) == 8 * 4
    assert np.frombuffer(row[2], dtype=np.float32).tolist() == pytest.approx(document, abs=1e-6)


def test_empty_text_is_not_sent_or_cached(tmp_path: Path) -> None:
    inner = RecordingEmbedder()
    cache = CachedEmbedder(inner, tmp_path / "cache.sqlite", "modele-a")
    with pytest.raises(ValueError):
        cache.embed_documents(["nguồn", " "])
    with pytest.raises(ValueError):
        cache.embed_query("")
    assert inner.document_calls == inner.query_calls == []
