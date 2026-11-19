"""Lệnh nhúng kho đoạn nguồn vào bộ đệm SQLite và dọn cache cũ khi đổi mô hình."""

from __future__ import annotations

import argparse
import gc
import hashlib
import sqlite3
import sys
import time
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict

from app.config.settings import Settings, load_settings
from app.core.errors import ConfigError, ProviderError, RetrievalError
from app.core.types import Chunk
from app.providers.cached_embedder import CachedEmbedder
from app.providers.embedder_factory import build_embedder
from app.providers.http import create_client
from app.retrieval.corpus import load_corpus

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CORPUS = Path("data/kb_curated/chunks.jsonl")
_MAX_GEMINI_BATCH = 100


class EmbedCorpusResult(BaseModel):
    """Số liệu tổng hợp sau khi chạy lệnh nhúng kho đoạn."""

    model_config = ConfigDict(frozen=True)

    tong_so_doan: int
    so_doan_da_co_vector: int
    so_doan_loi: int
    so_doan_bo_qua_cache: int = 0
    so_doan_moi_nhung: int = 0


def _resolve_path(raw: Path, root: Path) -> Path:
    """Giữ nguyên đường dẫn tuyệt đối, còn lại nối vào thư mục gốc."""
    return raw if raw.is_absolute() else root / raw


def _count_cache_rows(cache_path: Path) -> int:
    """Đếm số dòng hiện có trong bảng embeddings rồi đóng kết nối SQLite."""
    if not cache_path.is_file():
        return 0
    with closing(sqlite3.connect(cache_path)) as connection:
        with closing(
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'embeddings'"
            )
        ) as cursor:
            exists = cursor.fetchone()
        if exists is None:
            return 0
        with closing(connection.execute("SELECT count(*) FROM embeddings")) as cursor:
            row = cursor.fetchone()
        return int(row[0]) if row is not None else 0


def _count_cached_texts(
    cache_path: Path, model_id: str, texts: Sequence[str], dimensions: int
) -> int:
    """Đếm số văn bản trong lô đã có sẵn véc-tơ hợp lệ trong cache."""
    if not cache_path.is_file() or not texts:
        return 0
    keys = [hashlib.sha256(f"{model_id}\ndoc\n{text}".encode()).hexdigest() for text in texts]
    with closing(sqlite3.connect(cache_path)) as connection:
        with closing(
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'embeddings'"
            )
        ) as cursor:
            exists = cursor.fetchone()
        if exists is None:
            return 0
        found = 0
        for key in keys:
            with closing(
                connection.execute(
                    "SELECT dims, length(vec) FROM embeddings WHERE key = ?",
                    (key,),
                )
            ) as cursor:
                row = cursor.fetchone()
            if row is not None and row[0] == dimensions and row[1] == dimensions * 4:
                found += 1
        return found


def _unlink_cache_file(cache_path: Path, *, attempts: int = 10, delay: float = 0.05) -> None:
    """Giải phóng tay cầm SQLite còn sót rồi xoá tệp cache cũ."""
    for attempt in range(attempts):
        gc.collect()
        try:
            cache_path.unlink()
            return
        except PermissionError as exc:
            if getattr(exc, "winerror", None) != 32 or attempt + 1 >= attempts:
                raise
            time.sleep(delay)


def clear_old_cache(cache_path: Path) -> tuple[bool, int]:
    """In số dòng hiện có rồi xoá tệp cache cũ; trả về (đã_xoá, số_dòng)."""
    if not cache_path.is_file():
        print(f"Chưa có tệp cache để xoá: {cache_path} (0 dòng).")
        return False, 0
    rows = _count_cache_rows(cache_path)
    print(f"Số dòng trong cache cũ ({cache_path}): {rows}")
    _unlink_cache_file(cache_path)
    print(f"Đã xoá tệp cache cũ: {cache_path}")
    return True, rows


def embed_corpus(
    corpus_path: Path,
    cache_path: Path,
    settings: Settings,
    client: httpx.Client | None = None,
    *,
    limit: int | None = None,
) -> EmbedCorpusResult:
    """Nhúng từng lô qua CachedEmbedder; tự bỏ qua đoạn đã có và lưu sau mỗi lô."""
    if limit is not None and limit <= 0:
        raise ValueError("--limit phải > 0")
    chunks: list[Chunk] = load_corpus(corpus_path)
    if limit is not None:
        chunks = chunks[:limit]
    total = len(chunks)
    if total == 0:
        print("Tổng số đoạn: 0 | Số đoạn đã có vector: 0 | Số đoạn lỗi: 0")
        return EmbedCorpusResult(tong_so_doan=0, so_doan_da_co_vector=0, so_doan_loi=0)

    batch_size = settings.embedding.batch_size
    if settings.embedding.provider == "gemini":
        batch_size = min(batch_size, _MAX_GEMINI_BATCH)
    batch_size = max(1, batch_size)

    inner = build_embedder(settings, client)
    cached = CachedEmbedder(inner, cache_path, model_id=settings.embedding.active)

    total_batches = (total + batch_size - 1) // batch_size
    with_vector = 0
    errors = 0
    skipped_cache = 0
    newly_embedded = 0

    try:
        for batch_idx, start in enumerate(range(0, total, batch_size), start=1):
            batch = chunks[start : start + batch_size]
            texts = [chunk.noi_dung_nhung for chunk in batch]
            hits_before = cached.stats()["hits"]
            misses_before = cached.stats()["misses"]
            done = min(start + len(batch), total)
            try:
                cached.embed_documents(texts)
            except (ProviderError, ValueError) as exc:
                batch_ok = _count_cached_texts(
                    cache_path,
                    settings.embedding.active,
                    texts,
                    settings.embedding.dimensions,
                )
                batch_err = len(batch) - batch_ok
                with_vector += batch_ok
                skipped_cache += batch_ok
                errors += batch_err
                print(
                    f"Tiến độ: {done}/{total} đoạn "
                    f"(lô {batch_idx}/{total_batches}: cache={batch_ok}, "
                    f"lỗi={batch_err}, {type(exc).__name__})"
                )
            else:
                hits = cached.stats()["hits"] - hits_before
                added = cached.stats()["misses"] - misses_before
                with_vector += len(batch)
                skipped_cache += hits
                newly_embedded += added
                print(
                    f"Tiến độ: {done}/{total} đoạn "
                    f"(lô {batch_idx}/{total_batches}: cache={hits}, nhúng mới={added}, lỗi=0)"
                )
    finally:
        del cached
        gc.collect()

    result = EmbedCorpusResult(
        tong_so_doan=total,
        so_doan_da_co_vector=with_vector,
        so_doan_loi=errors,
        so_doan_bo_qua_cache=skipped_cache,
        so_doan_moi_nhung=newly_embedded,
    )
    print(
        f"Tổng số đoạn: {result.tong_so_doan} | "
        f"Số đoạn đã có vector: {result.so_doan_da_co_vector} | "
        f"Số đoạn lỗi: {result.so_doan_loi}"
    )
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Nhúng kho đoạn RAG qua CachedEmbedder theo cấu hình hiện hành."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Chỉ nhúng N đoạn đầu tiên để kiểm tra nhanh.",
    )
    parser.add_argument(
        "--xoa-cache-cu",
        action="store_true",
        help="In số dòng rồi xoá tệp cache cũ khi đổi mô hình.",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=_DEFAULT_CORPUS,
        help="Đường dẫn tới tệp chunks.jsonl.",
    )
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    *,
    root: Path = _ROOT,
    settings: Settings | None = None,
) -> int:
    """Điểm vào CLI cho python -m app.retrieval.embed_corpus."""
    args = _parse_args(argv)
    try:
        resolved_settings = settings if settings is not None else load_settings()
        cache_path = _resolve_path(Path(resolved_settings.embedding.cache_path), root)
        if args.xoa_cache_cu:
            clear_old_cache(cache_path)
            return 0
        corpus_path = _resolve_path(args.corpus, root)
        if resolved_settings.embedding.provider == "fake":
            result = embed_corpus(
                corpus_path,
                cache_path,
                resolved_settings,
                None,
                limit=args.limit,
            )
        else:
            with create_client() as client:
                result = embed_corpus(
                    corpus_path,
                    cache_path,
                    resolved_settings,
                    client,
                    limit=args.limit,
                )
        return 0 if result.so_doan_loi == 0 else 1
    except (ConfigError, RetrievalError, OSError, ValueError) as exc:
        print(f"Lỗi nhúng kho đoạn: {exc}")
        return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(main())
