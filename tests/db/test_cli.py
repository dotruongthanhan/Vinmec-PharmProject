"""Các chốt an toàn của CLI được thử bằng kết nối giả."""

import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.parametrize("args", [["reset"], ["all", "--reset"]])
def test_reset_requires_yes_before_connect(
    args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    from app.db.cli import main

    with patch("psycopg.connect", side_effect=AssertionError("Không được kết nối")):
        assert main(args) != 0
    output = capsys.readouterr().out
    assert "nghiep_vu" in output and "tri_thuc" in output


@pytest.mark.parametrize("group", ["cases", "kb", "ddinter", "embeddings"])
def test_dry_run_never_connects(group: str) -> None:
    from app.db.cli import main

    with patch("psycopg.connect", side_effect=AssertionError("Không được kết nối")):
        assert main(["load", group, "--dry-run"]) == 0


def test_connection_error_never_prints_password(capsys: pytest.CaptureFixture[str]) -> None:
    from app.db.cli import main

    url = "postgresql://demo:mat-khau-gia@private.example:5432/postgres"
    with (
        patch("app.db.cli.get_secret", return_value=url),
        patch("psycopg.connect", side_effect=RuntimeError(url)),
    ):
        assert main(["check"]) != 0
    output = capsys.readouterr()
    assert "mat-khau-gia" not in output.out + output.err
    assert "private.example" not in output.out + output.err
    assert "RuntimeError" in output.out + output.err


def test_upsert_values_are_parameters() -> None:
    from app.db.engine import upsert_statement
    from app.db.mapping import TABLES

    statement = upsert_statement(TABLES["nghiep_vu.nguoi_benh"])
    text = statement.as_string()
    assert "%s" in text
    assert "ON CONFLICT" in text and "DO UPDATE" in text
    assert "DROP" not in text
    assert text.count("%s") == len(TABLES["nghiep_vu.nguoi_benh"].column_names)


def test_check_uses_read_only_connection() -> None:
    from app.db.cli import main

    with (
        patch("app.db.cli.get_secret", return_value="postgresql://demo:fake@localhost/db"),
        patch("psycopg.connect", side_effect=RuntimeError("fake")) as connect,
    ):
        assert main(["check"]) != 0
    assert "default_transaction_read_only=on" in connect.call_args.kwargs["options"]


def test_sql_schema_only_targets_allowed_namespaces() -> None:
    root = Path(__file__).resolve().parents[2]
    schema = re.sub(r"--[^\n]*", "", (root / "db/schema.sql").read_text(encoding="utf-8"))
    assert "public." not in schema
    assert "auth." not in schema
    assert "storage." not in schema


def test_windows_encoding_does_not_leak_connection_traceback() -> None:
    fake = "invalid-driver://demo:mat-khau-kiem-thu@private.example/db"
    env = {**os.environ, "DATABASE_URL": fake, "PYTHONIOENCODING": "cp1252"}
    result = subprocess.run(
        [sys.executable, "-m", "app.db", "check"],
        env=env,
        capture_output=True,
        check=False,
    )
    combined = result.stdout + result.stderr
    assert result.returncode == 1
    assert b"ProgrammingError" in combined
    assert b"mat-khau-kiem-thu" not in combined
    assert b"private.example" not in combined
    assert b"Traceback" not in combined
