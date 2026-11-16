import json
from pathlib import Path

import httpx
import nbformat
import pytest

from app.config.settings import load_settings
from app.container import Container
from app.core.errors import ConfigError, RetrievalError
from app.core.types import SearchFilter
from app.providers.bm25_index import Bm25Index
from app.providers.cached_embedder import CachedEmbedder
from app.providers.fakes import HashEmbedder
from app.providers.memory_store import InMemoryVectorStore
from app.retrieval import setup
from app.retrieval.corpus import index_corpus, load_corpus
from tests.core.test_types import make_chunk


def test_missing_corpus_gives_rebuild_command(tmp_path: Path) -> None:
    path = tmp_path / "missing.jsonl"
    with pytest.raises(RetrievalError) as error:
        load_corpus(path)
    assert str(path) in str(error.value)
    assert "python -m app.kb.build" in str(error.value)


def test_load_and_index_source_embedding_content(tmp_path: Path) -> None:
    path = tmp_path / "chunks.jsonl"
    chunk = make_chunk("a", "văn bản hiển thị", noi_dung_nhung="meropenem nguồn nhúng")
    path.write_text("\n" + chunk.model_dump_json() + "\n", encoding="utf-8")
    chunks = load_corpus(path)
    assert chunks == [chunk]
    embedder, vector, keyword = HashEmbedder(8), InMemoryVectorStore(), Bm25Index()
    index_corpus(chunks, embedder, vector, keyword)
    assert vector.count() == 1
    assert vector.search(embedder.embed_query(chunk.noi_dung_nhung), 1, SearchFilter())[
        0
    ].diem == pytest.approx(1.0)
    assert keyword.search("meropenem", 1, SearchFilter())[0].chunk == chunk
    assert keyword.search("hiển thị", 1, SearchFilter()) == []


def test_invalid_corpus_identifies_line(tmp_path: Path) -> None:
    path = tmp_path / "chunks.jsonl"
    path.write_text("\n{}\n", encoding="utf-8")
    with pytest.raises(RetrievalError, match="dòng 2"):
        load_corpus(path)


@pytest.mark.parametrize("provider", ["memory", "pgvector"])
def test_setup_fake_profile_and_memory_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    path = tmp_path / "data" / "kb_curated" / "chunks.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(make_chunk().model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(setup, "_ROOT", tmp_path)

    def unexpected(*args: object, **kwargs: object) -> None:
        pytest.fail("Không được lấy bí mật hoặc tạo máy khách khi dùng fake")

    monkeypatch.setattr(setup, "get_secret", unexpected)
    monkeypatch.setattr(setup, "create_client", unexpected)
    settings = load_settings("test")
    settings = settings.model_copy(
        update={"vector_store": settings.vector_store.model_copy(update={"provider": provider})}
    )
    container = Container(settings)
    warnings: list[str] = []
    retriever = setup.build_retriever(container, warnings)
    assert retriever.embedder is container.embedder
    assert retriever.reranker is container.reranker
    assert isinstance(retriever.vector_store, InMemoryVectorStore)
    assert retriever.vector_store.count() == 1
    assert bool(warnings) is (provider == "pgvector")
    assert retriever.canh_bao == warnings


@pytest.mark.parametrize("second_key", [False, True])
def test_setup_openrouter_uses_shared_mock_client_and_optional_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, second_key: bool
) -> None:
    path = tmp_path / "data" / "kb_curated" / "chunks.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(make_chunk().model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(setup, "_ROOT", tmp_path)
    secret_calls: list[str] = []

    def secret(name: str) -> str:
        secret_calls.append(name)
        if name.endswith("_2") and not second_key:
            raise ConfigError(name)
        return "cle-factice-deux" if name.endswith("_2") else "cle-factice-un"

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["input"] == [make_chunk().noi_dung_nhung]
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]})

    monkeypatch.setattr(setup, "get_secret", secret)
    settings = load_settings("test")
    settings = settings.model_copy(
        update={
            "embedding": settings.embedding.model_copy(
                update={
                    "provider": "openrouter",
                    "dimensions": 2,
                    "cache_path": "cache/vectors.sqlite",
                }
            ),
            "rerank": settings.rerank.model_copy(update={"provider": "openrouter"}),
        }
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(setup, "create_client", lambda: client)
        retriever = setup.build_retriever(Container(settings))
        assert isinstance(retriever.embedder, CachedEmbedder)
        assert retriever.embedder.inner.client is retriever.reranker.client is client
        assert len(retriever.reranker.keys) == (2 if second_key else 1)
        assert retriever.embedder.model_id == settings.embedding.active
        assert retriever.vector_store.count() == 1
    assert secret_calls == ["OPENROUTER_API_KEY", "OPENROUTER_API_KEY_2"]


def test_notebooks_are_valid_and_have_no_saved_outputs() -> None:
    root = Path(__file__).resolve().parents[2]
    for name in ("03_test_embedding.ipynb", "04_test_retriever.ipynb"):
        notebook = nbformat.read(root / "notebooks" / name, as_version=4)
        nbformat.validate(notebook)
        for cell in notebook.cells:
            if cell.cell_type == "code":
                assert cell.outputs == []
                assert cell.execution_count is None
                compile(cell.source, name, "exec")


def test_notebooks_execute_with_fake_embedding_without_network_or_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import app.container as container_module

    def unexpected(*args: object, **kwargs: object) -> None:
        pytest.fail("Sổ tay kiểm thử không được gọi mạng hoặc đọc bí mật")

    monkeypatch.setattr(setup, "get_secret", unexpected)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", unexpected)
    root = Path(__file__).resolve().parents[2]
    path = tmp_path / "data" / "kb_curated" / "chunks.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        make_chunk("a", "meropenem chỉnh liều suy thận", muc="lieu_than").model_dump_json(),
        encoding="utf-8",
    )
    monkeypatch.setattr(setup, "_ROOT", tmp_path)
    container = Container(load_settings("test"))
    retriever = setup.build_retriever(container)
    retriever.embedder = CachedEmbedder(container.embedder, tmp_path / "cache.sqlite", "fake")
    monkeypatch.setattr(container_module, "build_container", lambda: container)
    monkeypatch.setattr(setup, "build_retriever", lambda value: retriever)
    monkeypatch.chdir(root / "notebooks")
    for name in ("03_test_embedding.ipynb", "04_test_retriever.ipynb"):
        namespace: dict = {}
        notebook = nbformat.read(root / "notebooks" / name, as_version=4)
        for cell in notebook.cells:
            if cell.cell_type == "code":
                exec(compile(cell.source, name, "exec"), namespace)
    output = capsys.readouterr().out
    for label in (
        "Số chiều:",
        "Chuẩn véc-tơ:",
        "Ma trận cosine:",
        "Bộ đệm sau lần hai:",
        "Từ khoá:",
        "Véc-tơ:",
        "Sau RRF",
        "Sau xếp hạng lại",
    ):
        assert label in output
