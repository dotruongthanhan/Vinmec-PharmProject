"""Kiểm phiếu và liên kết bằng nguồn cục bộ, không mở DB thật."""

import copy
import json
import sqlite3
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import pytest

from app.db import cli, engine, sources
from app.db.mapping import TABLES

ROOT = Path(__file__).resolve().parents[2]
SHEET = "nghiep_vu.phieu_dieu_tri"
LINK = "nghiep_vu.phieu_y_lenh"


@pytest.fixture(scope="module")
def batch() -> sources.Batch:
    return sources.prepare_cases(ROOT)


def test_all_sheets_and_links_preserve_source(batch: sources.Batch) -> None:
    assert SHEET in TABLES
    sheets = batch.rows[SHEET]
    assert len(sheets) == 333
    assert not batch.rejected and not batch.orphans()
    encounters = {row["dot_dieu_tri_id"]: row for row in batch.rows["nghiep_vu.dot_dieu_tri"]}
    assert len({encounters[row["dot_dieu_tri_id"]]["nguoi_benh_id"] for row in sheets}) == 60
    actual = {row["phieu_dieu_tri_id"]: row for row in sheets}
    for path in (ROOT / "data/mock/hoso_gia_lap").glob("HS-*.json"):
        raw = json.loads(path.read_text("utf-8"))
        for encounter in raw["dot_dieu_tri"]:
            for sheet in encounter["phieu_dieu_tri"]:
                row = actual[sheet["phieu_dieu_tri_id"]]
                assert {key: row[key] for key in sheet if key != "y_lenh_trong_ngay"} == {
                    key: value for key, value in sheet.items() if key != "y_lenh_trong_ngay"
                }
                assert {
                    link["y_lenh_id"]
                    for link in batch.rows[LINK]
                    if link["phieu_dieu_tri_id"] == row["phieu_dieu_tri_id"]
                } == set(sheet["y_lenh_trong_ngay"])


def test_missing_field_and_invalid_role_are_rejected(batch: sources.Batch) -> None:
    assert SHEET in TABLES
    for field, value in (("vai_tro_nguoi_lap", "khong_hop_le"), ("ngay_dieu_tri", 0)):
        row = {**batch.rows[SHEET][0], field: value}
        candidate = sources.Batch()
        assert not candidate.add(SHEET, row, "gia_lap.json")
        assert field in candidate.rejected[0].ly_do
    row = dict(batch.rows[SHEET][0])
    del row["dien_bien"]
    candidate = sources.Batch()
    assert not candidate.add(SHEET, row, "gia_lap.json")
    assert "dien_bien: thiếu" in candidate.rejected[0].ly_do


def test_links_require_existing_order_in_same_encounter(batch: sources.Batch) -> None:
    assert LINK in TABLES
    candidate = copy.deepcopy(batch)
    link = candidate.rows[LINK][0]
    link["y_lenh_id"] = next(
        row["y_lenh_id"]
        for row in candidate.rows["nghiep_vu.y_lenh"]
        if row["dot_dieu_tri_id"] != link["dot_dieu_tri_id"]
    )
    assert any(LINK in error and "y_lenh" in error for error in candidate.orphans())


def test_sheet_reload_replaces_old_rows_only_in_target_encounters(batch: sources.Batch) -> None:
    from tests.db.test_loading import RecordingConnection

    assert SHEET in TABLES
    selected = sources.prepare_treatment_sheets(ROOT)
    assert selected.tables == {SHEET, LINK}
    assert len(selected.rows[SHEET]) == 333 and not selected.rejected
    # Chạy lệnh của engine trên bảng trong bộ nhớ có FK kép tương đương.
    with sqlite3.connect(":memory:") as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("ATTACH DATABASE ':memory:' AS nghiep_vu")
        connection.execute("CREATE TABLE nghiep_vu.dot_dieu_tri (dot_dieu_tri_id TEXT PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE nghiep_vu.y_lenh (y_lenh_id TEXT PRIMARY KEY, "
            "dot_dieu_tri_id TEXT, UNIQUE(y_lenh_id, dot_dieu_tri_id))"
        )
        for name in (SHEET, LINK):
            table = TABLES[name]
            columns = [f'"{key}" TEXT' for key in table.column_names]
            columns.append("PRIMARY KEY (" + ",".join(table.primary_key) + ")")
            for fk in table.foreign_keys:
                columns.append(
                    f"FOREIGN KEY ({','.join(fk.columns)}) REFERENCES "
                    f"{fk.table.split('.')[1]} ({','.join(fk.target)})"
                )
            if name == SHEET:
                columns.append("UNIQUE(phieu_dieu_tri_id, dot_dieu_tri_id)")
            connection.execute(f"CREATE TABLE {name} ({','.join(columns)})")
        connection.executemany(
            "INSERT INTO nghiep_vu.dot_dieu_tri VALUES (?)",
            [(row["dot_dieu_tri_id"],) for row in batch.rows["nghiep_vu.dot_dieu_tri"]],
        )
        connection.executemany(
            "INSERT INTO nghiep_vu.y_lenh VALUES (?, ?)",
            [(row["y_lenh_id"], row["dot_dieu_tri_id"]) for row in batch.rows["nghiep_vu.y_lenh"]],
        )

        def apply(selected_batch: sources.Batch) -> None:
            statements = RecordingConnection()
            engine.load_treatment_sheets(statements, selected_batch)
            with connection:
                for statement, params in statements.committed:
                    if statement.endswith("FOR NO KEY UPDATE"):
                        continue
                    if statement.startswith("DELETE"):
                        params = params[0]
                        placeholders = ", ".join("?" for _ in params)
                        statement = statement.replace("= ANY(%s)", f"IN ({placeholders})")
                    else:
                        table = (
                            TABLES[SHEET]
                            if f'"{SHEET.split(".")[1]}"' in statement
                            else TABLES[LINK]
                        )
                        params = tuple(
                            json.dumps(value.obj)
                            if key in table.json_columns and value is not None
                            else value
                            for key, value in zip(table.column_names, params, strict=True)
                        )
                    connection.execute(statement.replace("%s", "?"), params)

        apply(selected)
        apply(selected)
        assert connection.execute(f"SELECT count(*) FROM {SHEET}").fetchone()[0] == 333
        sheet_counts = Counter(row["dot_dieu_tri_id"] for row in selected.rows[SHEET])
        stale_link = next(
            row for row in selected.rows[LINK] if sheet_counts[row["dot_dieu_tri_id"]] > 1
        )
        dot_id = stale_link["dot_dieu_tri_id"]
        empty_dot_id = next(
            row["dot_dieu_tri_id"]
            for row in selected.rows[SHEET]
            if row["dot_dieu_tri_id"] != dot_id
        )
        stale_sheet = next(
            row
            for row in selected.rows[SHEET]
            if row["dot_dieu_tri_id"] == dot_id
            and row["phieu_dieu_tri_id"] != stale_link["phieu_dieu_tri_id"]
        )
        reload = copy.deepcopy(selected)
        reload.rows["nghiep_vu.dot_dieu_tri"] = [
            row
            for row in selected.rows["nghiep_vu.dot_dieu_tri"]
            if row["dot_dieu_tri_id"] in {dot_id, empty_dot_id}
        ]
        reload.rows[SHEET] = [
            row
            for row in selected.rows[SHEET]
            if row["dot_dieu_tri_id"] == dot_id and row != stale_sheet
        ]
        reload.rows[LINK] = [
            row
            for row in selected.rows[LINK]
            if row["phieu_dieu_tri_id"]
            in {sheet["phieu_dieu_tri_id"] for sheet in reload.rows[SHEET]}
            and row != stale_link
        ]
        apply(reload)
        for name in (SHEET, LINK):
            keys = TABLES[name].primary_key
            remaining = set(connection.execute(f"SELECT {', '.join(keys)} FROM {name}"))
            expected_rows = [
                *reload.rows[name],
                *(
                    row
                    for row in selected.rows[name]
                    if row["dot_dieu_tri_id"] not in {dot_id, empty_dot_id}
                ),
            ]
            assert remaining == {tuple(row[key] for key in keys) for row in expected_rows}
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(f"UPDATE {LINK} SET y_lenh_id='KHONG_TON_TAI'")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(f"UPDATE {SHEET} SET dot_dieu_tri_id='KHONG_TON_TAI'")


def test_sheet_cli_dry_run_never_loads_secrets(capsys: pytest.CaptureFixture[str]) -> None:
    with patch.object(cli, "load_settings", side_effect=AssertionError("Không đọc bí mật")):
        assert cli.main(["phieu-dieu-tri", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert f"{SHEET}: 333" in output
    assert "Tổng dòng bị loại: 0" in output
    assert "không kết nối" in output


def test_sheet_cli_forbids_reset() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.parser().parse_args(["phieu-dieu-tri", "--reset"])
    assert exc.value.code == 2


def test_sheet_loader_writes_only_sheet_tables_and_rolls_back() -> None:
    from tests.db.test_loading import RecordingConnection

    selected = sources.prepare_treatment_sheets(ROOT)
    connection = RecordingConnection()
    engine.load_treatment_sheets(connection, selected)
    assert connection.committed
    statements = [statement for statement, _ in connection.statements]
    assert statements[0].endswith("FOR NO KEY UPDATE")
    assert statements[1:3] == [
        f'DELETE FROM "nghiep_vu"."{table}" WHERE dot_dieu_tri_id = ANY(%s)'
        for table in ("phieu_y_lenh", "phieu_dieu_tri")
    ]
    for statement in statements[3:]:
        assert statement.startswith('INSERT INTO "nghiep_vu"."phieu_')
        assert "ON CONFLICT" in statement
    failing = RecordingConnection('INSERT INTO "nghiep_vu"."phieu_y_lenh"')
    with pytest.raises(RuntimeError):
        engine.load_treatment_sheets(failing, selected)
    assert not failing.committed
