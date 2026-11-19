"""Kiểm dữ liệu T45 và bộ nạp chỉ cập nhật bằng kết nối giả."""

import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_generator_is_deterministic_additive_and_preserves_originals() -> None:
    from tools.kiem_hanh_chinh import check_record
    from tools.sinh_hanh_chinh import enrich_record, source_paths

    paths = source_paths(ROOT)
    assert len(paths) == 66
    originals = ROOT / "data/mock/_goc_truoc_T45"
    content = b"".join((originals / p.name).read_bytes().replace(b"\r\n", b"\n") for p in paths)
    digest = hashlib.sha256(content)
    assert digest.hexdigest() == "24b6ad637a70b1b9cc3e77297948efb33aedeeeb839a63bc450bcfe9bda14d24"
    modified_content = content.replace(b"HS-001", b"HS-002", 1)
    assert hashlib.sha256(modified_content).digest() != digest.digest()
    for number, path in enumerate(paths, 1):
        original = json.loads((originals / path.name).read_text(encoding="utf-8"))
        untouched = copy.deepcopy(original)
        enriched = enrich_record(original, number)
        assert original == untouched
        assert enriched == enrich_record(original, number)
        assert enriched == enrich_record(enriched, number)
        assert check_record(enriched, original, number) == [], path.name


def test_checker_rejects_names_dictionary_age_and_nonadditive_changes() -> None:
    from tools.kiem_hanh_chinh import check_record
    from tools.sinh_hanh_chinh import enrich_record

    original = json.loads((ROOT / "data/mock/_goc_truoc_T45/HS-020.json").read_text("utf-8"))
    enriched = enrich_record(original, 20)
    enriched["hanh_chinh"].update(ho_ten="Sai", ngay_sinh="1900-01-01", dan_toc="Sai", bo_me=None)
    enriched["nguoi_benh"]["tuoi"] = 5
    errors = ";".join(check_record(enriched, original, 20))
    for field in ("ho_ten", "ngay_sinh", "dan_toc", "bo_me", "chỉ thêm"):
        assert field in errors


def test_administrative_sources_cover_every_record_and_encounter() -> None:
    from app.db.sources import prepare_administrative, prepare_cases
    from tools.sinh_hanh_chinh import source_paths

    batch = prepare_administrative(ROOT)
    assert not batch.rejected
    assert len(batch.rows["nghiep_vu.nguoi_benh"]) == 66
    assert sum("hoso_gia_lap" in r["nguon_tep"] for r in batch.rows["nghiep_vu.nguoi_benh"]) == 60
    count = 0
    for path in source_paths(ROOT):
        record = json.loads(path.read_text("utf-8"))
        encounters = record["dot_dieu_tri"]
        count += len(encounters) if isinstance(encounters, list) else 1
    assert len(batch.rows["nghiep_vu.dot_dieu_tri"]) == count
    full = prepare_cases(ROOT)
    assert not full.rejected
    assert all(row["ho_ten"] for row in full.rows["nghiep_vu.nguoi_benh"])
    assert all(row["so_luu_tru"] for row in full.rows["nghiep_vu.dot_dieu_tri"])
    child = next(
        row for row in batch.rows["nghiep_vu.nguoi_benh"] if row["nguoi_benh_id"] == "NB-HS-040"
    )
    assert child["can_nang_kg"] is None


def test_administrative_dry_run_never_reads_settings_secrets_or_connects(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app.db.cli import main

    with (
        patch("app.db.cli.load_settings", side_effect=AssertionError("Không đọc cấu hình")),
        patch("app.db.cli.get_secret", side_effect=AssertionError("Không đọc bí mật")),
        patch("psycopg.connect", side_effect=AssertionError("Không kết nối")),
    ):
        assert main(["hanh-chinh", "--dry-run"]) == 0
    assert "Tổng dòng bị loại: 0" in capsys.readouterr().out


def test_administrative_loader_updates_only_allowed_columns_and_rolls_back_missing() -> None:
    from app.db.engine import load_administrative
    from app.db.mapping import ADMINISTRATIVE_COLUMNS
    from app.db.sources import SourceError, prepare_administrative
    from tests.db.test_loading import RecordingConnection

    class ExistingConnection(RecordingConnection):
        def execute(self, query: object, params: object = None) -> "ExistingConnection":
            super().execute(query, params)
            self.rowcount = 1
            return self

    batch = prepare_administrative(ROOT)
    connection = ExistingConnection()
    load_administrative(connection, batch)
    assert connection.committed
    for statement, _ in connection.statements:
        assert statement.startswith("UPDATE ")
        name = next(
            name for name in ADMINISTRATIVE_COLUMNS if f'"{name.split(".")[1]}"' in statement
        )
        assignments = statement.split(" SET ")[1].split(" WHERE ")[0]
        assert set(part.split('"')[1] for part in assignments.split(", ")) == set(
            ADMINISTRATIVE_COLUMNS[name]
        )
        assert "nguon_tep" not in assignments and "nap_luc" not in assignments
    missing = RecordingConnection()
    with pytest.raises(SourceError, match="thiếu"):
        load_administrative(missing, batch)
    assert not missing.committed
