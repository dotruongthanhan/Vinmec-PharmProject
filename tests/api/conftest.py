"""Giữ nguyên test API cũ trong chế độ phát triển tường minh."""

import pytest


@pytest.fixture(autouse=True)
def legacy_auth_mode(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test v1.3 tự dựng môi trường required riêng."""
    if request.module.__name__ != "tests.api.test_auth_ownership":
        monkeypatch.setenv("AUTH_MODE", "off")
