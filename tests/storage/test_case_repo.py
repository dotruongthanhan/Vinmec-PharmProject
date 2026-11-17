from pathlib import Path

import pytest

from app.domain.loader import load_case
from app.storage.case_repo import JsonCaseRepository

ROOT = Path(__file__).resolve().parents[2]


def test_repository_uses_case_id_and_skips_invalid_files(tmp_path: Path) -> None:
    source = ROOT / "data/mock/demo"
    (tmp_path / "z.json").write_bytes((source / "DEMO-01.json").read_bytes())
    (tmp_path / "a.json").write_bytes((source / "DEMO-02.json").read_bytes())
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    (tmp_path / "invalid.json").write_text("{}", encoding="utf-8")
    repo = JsonCaseRepository(tmp_path)
    assert repo.list_ids() == ["DEMO-01", "DEMO-02"]
    assert repo.get("DEMO-01") == load_case(source / "DEMO-01.json")
    assert {Path(name).name for name, error in repo.errors if error} == {"bad.json", "invalid.json"}
    repo.list_ids()
    assert len(repo.errors) == 2
    with pytest.raises(KeyError):
        repo.get("missing")


def test_missing_folder_is_empty(tmp_path: Path) -> None:
    assert JsonCaseRepository(tmp_path / "absent").list_ids() == []
