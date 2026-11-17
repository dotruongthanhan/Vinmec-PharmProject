"""Giữ tệp thử tạm trong phạm vi task."""

from pathlib import Path

import psycopg
import pytest


def pytest_configure(config: pytest.Config) -> None:
    if config.option.basetemp is None:
        config.option.basetemp = str(Path(__file__).parent / ".tmp/pytest")


@pytest.fixture(autouse=True)
def forbid_real_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Không test nào được vô tình mở PostgreSQL thật."""

    def reject_connection(*args: object, **kwargs: object) -> None:
        raise AssertionError("Test không được kết nối cơ sở dữ liệu thật")

    monkeypatch.setattr(psycopg, "connect", reject_connection)
