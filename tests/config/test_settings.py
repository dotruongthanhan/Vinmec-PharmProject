from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.config import settings as settings_module
from app.config.settings import get_secret, load_settings
from app.core.errors import ConfigError

ROOT = Path(__file__).resolve().parents[2]


def test_real_settings_and_deep_overlay(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CDSS_PROFILE", raising=False)
    base = load_settings()
    test = load_settings("test")
    assert base.llm.provider == "deepseek"
    assert base.llm.model == "deepseek-flash"
    assert base.vector_store.provider == "pgvector"
    assert base.database.url_env == "DATABASE_URL"
    assert test.app.profile == "test"
    assert test.llm.provider == test.embedding.provider == "fake"
    assert test.rerank.provider == "noop"
    assert test.vector_store.provider == "memory"
    assert test.llm.model == base.llm.model
    assert test.retrieval == base.retrieval
    assert test.embedding.dimensions == base.embedding.dimensions
    monkeypatch.setenv("CDSS_PROFILE", "test")
    assert load_settings() == test
    assert load_settings("dev") == base
    with pytest.raises(ValidationError):
        test.llm.provider = "other"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("llm", "unknown"), True),
        (("retrieval", "nhan_thuoc", "k_rerank"), 21),
        (("chunking", "min_chars"), 1200),
        (("chunking", "target_chars"), 2001),
        (("generation", "temperature"), 2.1),
        (("generation", "temperature"), -0.1),
        (("embedding", "batch_size"), 0),
        (("agent", "max_turns"), "5"),
        (("generation", "stream"), "false"),
    ],
)
def test_invalid_settings_report_key(tmp_path: Path, path: tuple[str, ...], value: object) -> None:
    raw = yaml.safe_load((ROOT / "config/settings.yaml").read_text(encoding="utf-8"))
    block = raw
    for key in path[:-1]:
        block = block[key]
    block[path[-1]] = value
    (tmp_path / "settings.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ConfigError, match="\\.".join(path[:-1])):
        load_settings("dev", tmp_path)


def test_overlay_rejects_unknown_keys(tmp_path: Path) -> None:
    (tmp_path / "settings.yaml").write_bytes((ROOT / "config/settings.yaml").read_bytes())
    (tmp_path / "settings.test.yaml").write_text("llm:\n  typo: true\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="llm.typo"):
        load_settings("test", tmp_path)


@pytest.mark.parametrize("content", ["[]", "app: [", "null"])
def test_invalid_yaml_is_config_error(tmp_path: Path, content: str) -> None:
    (tmp_path / "settings.yaml").write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_settings("dev", tmp_path)


def test_secrets_never_read_real_dotenv(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[bool] = []
    monkeypatch.setattr(settings_module, "load_dotenv", lambda **kw: calls.append(kw["override"]))
    monkeypatch.delenv("TEN_KHONG_CO", raising=False)
    with pytest.raises(ConfigError) as error:
        get_secret("TEN_KHONG_CO")
    assert str(error.value) == "TEN_KHONG_CO"
    monkeypatch.setenv("T11_FAKE_SECRET", "gia-tri-gia-lap")
    assert get_secret("T11_FAKE_SECRET") == "gia-tri-gia-lap"
    assert calls == [False, False]
    assert capsys.readouterr() == ("", "")
