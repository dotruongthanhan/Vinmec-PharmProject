"""Kiểm thử lệnh nhúng kho đoạn, dọn cache cũ và đường lui từ khoá khi thiếu khoá Gemini."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import httpx
import numpy as np
import pytest

from app.config.settings import Settings, load_settings
from app.container import Container
from app.domain.loader import load_case
from app.kb.dictionary import candidates
from app.kb.names import DrugNameIndex
from app.orchestration.evidence import EvidenceCollector, LazyRetrieverFactory
from app.pipeline import run_case
from app.providers.cached_embedder import CachedEmbedder
from app.providers.gemini_embed import GeminiEmbedder
from app.retrieval import embed_corpus as embed_corpus_mod
from app.retrieval import setup
from app.retrieval.query_builder import QueryBuilder
from tests.core.test_types import make_chunk

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def block_real_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("Không được gọi mạng thật")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)


def _gemini_settings(
    tmp_path: Path,
    *,
    batch_size: int = 2,
    dimensions: int = 4,
    rerank_provider: str = "noop",
) -> Settings:
    base = load_settings("test")
    return base.model_copy(
        update={
            "embedding": base.embedding.model_copy(
                update={
                    "provider": "gemini",
                    "active": "gemini-embedding-2",
                    "dimensions": dimensions,
                    "batch_size": batch_size,
                    "cache_path": str(tmp_path / "data/cache/embeddings.sqlite"),
                }
            ),
            "rerank": base.rerank.model_copy(update={"provider": rerank_provider}),
        }
    )


def _write_chunks(root: Path, count: int) -> Path:
    corpus_path = root / "data/kb_curated/chunks.jsonl"
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        make_chunk(
            f"C-{i}",
            f"meropenem renal dose {i}",
            drug="meropenem",
            muc="lieu_than",
            noi_dung_nhung=f"meropenem chỉnh liều suy thận đoạn {i}",
        ).model_dump_json()
        for i in range(count)
    ]
    corpus_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return corpus_path


def test_embed_corpus_limit_and_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_chunks(tmp_path, 5)
    settings = _gemini_settings(tmp_path, batch_size=2, dimensions=4)
    monkeypatch.setenv("GEMINI_API_KEY", "khoa-gemini-gia-lap")
    sent_batches: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        texts = [item["content"]["parts"][0]["text"] for item in payload["requests"]]
        sent_batches.append(texts)
        return httpx.Response(
            200,
            json={"embeddings": [{"values": [0.1, 0.2, 0.3, 0.4]} for _ in texts]},
        )

    monkeypatch.setattr(
        embed_corpus_mod,
        "create_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )
    code = embed_corpus_mod.main(["--limit", "3"], root=tmp_path, settings=settings)
    assert code == 0
    assert [len(batch) for batch in sent_batches] == [2, 1]
    out = capsys.readouterr().out
    assert "Tiến độ: 2/3 đoạn" in out
    assert "Tiến độ: 3/3 đoạn" in out
    assert "Tổng số đoạn: 3" in out
    assert "Số đoạn đã có vector: 3" in out
    assert "Số đoạn lỗi: 0" in out

    cache_path = Path(settings.embedding.cache_path)
    with closing(sqlite3.connect(cache_path)) as connection:
        assert connection.execute("SELECT count(*) FROM embeddings").fetchone() == (3,)


def test_embed_corpus_resumes_after_error_and_skips_cached(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_chunks(tmp_path, 4)
    settings = _gemini_settings(tmp_path, batch_size=2, dimensions=4)
    settings = settings.model_copy(
        update={"agent": settings.agent.model_copy(update={"max_attempts": 1})}
    )
    monkeypatch.setenv("GEMINI_API_KEY", "khoa-gemini-gia-lap")

    first_calls: list[list[str]] = []

    def fail_second_batch(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        texts = [item["content"]["parts"][0]["text"] for item in payload["requests"]]
        first_calls.append(texts)
        if len(first_calls) == 2:
            return httpx.Response(500, text="tam thoi loi")
        return httpx.Response(
            200,
            json={"embeddings": [{"values": [0.1, 0.2, 0.3, 0.4]} for _ in texts]},
        )

    monkeypatch.setattr(
        embed_corpus_mod,
        "create_client",
        lambda: httpx.Client(transport=httpx.MockTransport(fail_second_batch)),
    )
    assert embed_corpus_mod.main([], root=tmp_path, settings=settings) == 1
    first_out = capsys.readouterr().out
    assert "Tổng số đoạn: 4 | Số đoạn đã có vector: 2 | Số đoạn lỗi: 2" in first_out

    resumed_calls: list[list[str]] = []

    def resume_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        texts = [item["content"]["parts"][0]["text"] for item in payload["requests"]]
        resumed_calls.append(texts)
        return httpx.Response(
            200,
            json={"embeddings": [{"values": [0.5, 0.6, 0.7, 0.8]} for _ in texts]},
        )

    monkeypatch.setattr(
        embed_corpus_mod,
        "create_client",
        lambda: httpx.Client(transport=httpx.MockTransport(resume_handler)),
    )
    assert embed_corpus_mod.main([], root=tmp_path, settings=settings) == 0
    assert len(resumed_calls) == 1
    assert all("đoạn 2" in t or "đoạn 3" in t for t in resumed_calls[0])
    second_out = capsys.readouterr().out
    assert "Tổng số đoạn: 4 | Số đoạn đã có vector: 4 | Số đoạn lỗi: 0" in second_out

    monkeypatch.setattr(
        embed_corpus_mod,
        "create_client",
        lambda: httpx.Client(
            transport=httpx.MockTransport(
                lambda _req: pytest.fail("Không được gọi API khi mọi đoạn đã có trong cache")
            )
        ),
    )
    assert embed_corpus_mod.main([], root=tmp_path, settings=settings) == 0
    assert "Tổng số đoạn: 4 | Số đoạn đã có vector: 4 | Số đoạn lỗi: 0" in capsys.readouterr().out


def test_embed_corpus_deletes_old_cache_only_with_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_chunks(tmp_path, 2)
    settings = _gemini_settings(tmp_path, batch_size=2, dimensions=4)
    cache_path = Path(settings.embedding.cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    vec = np.ones(4, dtype=np.float32).tobytes()
    with closing(sqlite3.connect(cache_path)) as connection:
        connection.execute("CREATE TABLE embeddings (key TEXT PRIMARY KEY, dims INTEGER, vec BLOB)")
        for idx in range(3):
            connection.execute(
                "INSERT INTO embeddings VALUES (?, ?, ?)",
                (f"old-nemotron-key-{idx}", 4, vec),
            )
        connection.commit()

    monkeypatch.setenv("GEMINI_API_KEY", "khoa-gemini-gia-lap")
    monkeypatch.setattr(
        embed_corpus_mod,
        "create_client",
        lambda: httpx.Client(
            transport=httpx.MockTransport(
                lambda _r: httpx.Response(200, json={"embeddings": [{"values": [0.1] * 4}]})
            )
        ),
    )
    assert embed_corpus_mod.main(["--limit", "1"], root=tmp_path, settings=settings) == 0
    assert cache_path.is_file()
    with closing(sqlite3.connect(cache_path)) as connection:
        assert connection.execute("SELECT count(*) FROM embeddings").fetchone() == (4,)
    capsys.readouterr()

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert embed_corpus_mod.main(["--xoa-cache-cu"], root=tmp_path, settings=settings) == 0
    assert not cache_path.exists()
    out = capsys.readouterr().out
    assert "4" in out

    assert embed_corpus_mod.main(["--xoa-cache-cu"], root=tmp_path, settings=settings) == 0


@pytest.mark.parametrize("rerank_provider", ["noop", "openrouter"])
def test_missing_gemini_key_rag_falls_back_to_keyword_without_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rerank_provider: str,
) -> None:
    corpus_path = _write_chunks(tmp_path, 2)
    settings = _gemini_settings(
        tmp_path,
        batch_size=2,
        dimensions=4,
        rerank_provider=rerank_provider,
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(setup, "_ROOT", tmp_path)

    retriever = setup.build_retriever(Container(settings))
    query = QueryBuilder(settings.retrieval).for_finding(
        "meropenem", "meropenem", "meropenem", 6, None
    )
    outcome = retriever.retrieve_detailed(query)
    assert outcome.che_do == "tu_khoa"
    assert outcome.ket_qua
    assert any("từ khoá" in warning.lower() for warning in outcome.canh_bao)

    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    rule_result = run_case(case, Container(settings).renal_rules)
    names = DrugNameIndex.load(ROOT / "data/kb/hoat_chat.json")
    factory = LazyRetrieverFactory(Container(settings), corpus_path)
    try:
        chunks, warnings = EvidenceCollector(
            factory, QueryBuilder(settings.retrieval), names.resolve
        ).collect(case, rule_result)
        assert chunks
        assert "Không lấy được đoạn nguồn, AI chỉ dùng dữ liệu ca" not in warnings
    finally:
        factory.close()


def test_dictionary_open_embedder_accepts_gemini_and_rejects_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _gemini_settings(tmp_path, batch_size=10, dimensions=4)
    monkeypatch.setattr(candidates, "load_settings", lambda: settings)
    monkeypatch.setenv("GEMINI_API_KEY", "khoa-gemini-gia-lap")
    monkeypatch.setattr(
        candidates,
        "create_client",
        lambda: httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(200))),
    )
    with candidates.open_embedder(tmp_path, "that") as (embedder, model_name):
        assert isinstance(embedder, CachedEmbedder)
        assert isinstance(embedder.inner, GeminiEmbedder)
        assert model_name == "gemini-embedding-2"

    bad = settings.model_copy(
        update={"embedding": settings.embedding.model_copy(update={"provider": "khac"})}
    )
    monkeypatch.setattr(candidates, "load_settings", lambda: bad)
    with pytest.raises(ValueError):
        with candidates.open_embedder(tmp_path, "that"):
            pass
