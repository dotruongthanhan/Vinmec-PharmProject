from pathlib import Path

import nbformat
import pytest

from app.config import settings as settings_module

ROOT = Path(__file__).resolve().parents[2]


def test_notebook_valid_clean_and_runs_without_reading_dotenv(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    notebook = nbformat.read(ROOT / "notebooks/00_cau_hinh.ipynb", as_version=4)
    nbformat.validate(notebook)
    assert len(notebook.cells) == 5
    namespace: dict = {}
    monkeypatch.setattr(settings_module, "load_dotenv", lambda **kw: None)
    for name in ("OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "gia-tri-gia-lap")
    monkeypatch.chdir(ROOT / "notebooks")
    for cell in notebook.cells:
        assert "sk-" not in cell.source
        if cell.cell_type == "code":
            assert cell.outputs == []
            assert cell.execution_count is None
            exec(compile(cell.source, "00_cau_hinh.ipynb", "exec"), namespace)
    output = capsys.readouterr().out
    assert "gia-tri-gia-lap" not in output
    assert "DEEPSEEK_API_KEY: có" in output
    assert "OPENROUTER_API_KEY: thiếu" in output
    assert "DATABASE_URL: thiếu" in output
    assert "Số ca: 6" in output
    assert "Số luật: 5" in output
