"""Kiểm tra thời gian chờ qua máy khách được lắp thật."""

from types import SimpleNamespace

import httpx
import pytest

from app.core.errors import ProviderError
from app.llm.setup import build_llm
from app.providers.http import han_chot_llm


@pytest.mark.parametrize(
    "delay,deadline,success", [(2, None, True), (90, None, False), (2, 1, False)]
)
def test_build_llm_wait(monkeypatch, delay, deadline, success):
    now = [100.0]
    waits = []
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) <= 8:
            return httpx.Response(429, json={"error": {"details": [{"retryDelay": f"{delay}s"}]}})
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("app.llm.setup.create_client", lambda: client)
    monkeypatch.setattr("app.llm.setup.get_secret", lambda name: name)
    llm_settings = SimpleNamespace(
        provider="chat_api",
        khoa_env=[f"key{i}" for i in range(8)],
        model="test",
        url="https://example.invalid",
        max_tokens=10,
        max_tokens_retry=20,
        reasoning=None,
        cho_khoa_toi_da_giay=70,
    )
    container = SimpleNamespace(
        settings=SimpleNamespace(
            llm=llm_settings,
            generation=SimpleNamespace(temperature=0, top_p=1),
            agent=SimpleNamespace(max_attempts=3),
        )
    )
    llm = build_llm(container)
    llm.router._clock = lambda: now[0]

    def sleep(seconds):
        waits.append(seconds)
        now[0] += seconds

    llm.router._sleep = sleep
    token = han_chot_llm.set(now[0] + deadline if deadline else None)
    try:
        if success:
            assert llm.complete_json([], {}) == {}
            assert waits == [2]
            assert len(calls) == 9
        else:
            with pytest.raises(ProviderError):
                llm.complete_json([], {})
            assert waits == []
            assert len(calls) == 8
    finally:
        han_chot_llm.reset(token)
