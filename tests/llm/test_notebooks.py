"""Kiểm tra định dạng hợp lệ và không chứa đầu ra hay bí mật trong hai sổ tay."""

from pathlib import Path

import nbformat
import pytest

_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("filename", ["06_test_llm.ipynb", "07_test_verify.ipynb"])
def test_notebooks_are_valid_and_clean(filename: str) -> None:
    path = _ROOT / "notebooks" / filename
    raw_text = path.read_text(encoding="utf-8")
    assert "sk-" not in raw_text

    nb = nbformat.reads(raw_text, as_version=4)
    nbformat.validate(nb)
    for cell in nb.cells:
        if cell.cell_type == "code":
            assert cell.outputs == []
            assert cell.execution_count is None
