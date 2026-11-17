"""Kiểm thử máy khách DeepSeekLLM với httpx.MockTransport (không gọi mạng thật)."""

import json

import httpx
import pytest

from app.core.errors import ProviderError
from app.core.interfaces import LLMClient
from app.core.types import ChatMessage
from app.providers.deepseek_llm import DeepSeekLLM


def _ok_body(content: str, finish_reason: str = "stop", usage: dict | None = None) -> dict:
    return {
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {
                    "content": content,
                    "reasoning_content": "suy luan noi bo bi bo qua",
                },
            }
        ],
        "usage": usage if usage is not None else {"prompt_tokens": 10, "completion_tokens": 20},
    }


@pytest.mark.parametrize("reasoning", [None, {"reasoning_effort": "low"}])
def test_deepseek_complete_json_success_and_request_payload(
    reasoning: dict[str, str] | None,
) -> None:
    captured: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        captured.append((str(request.url), request.headers.get("authorization", ""), body))
        return httpx.Response(200, json=_ok_body('  {"nhan_dinh": []}  '))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = DeepSeekLLM(
        model="deepseek-flash",
        api_key="key-test-123",
        client=client,
        temperature=0.0,
        max_tokens=4096,
        max_tokens_retry=8192,
        reasoning=reasoning,
        top_p=1.0,
        max_attempts=3,
        sleep=lambda _: None,
    )
    assert isinstance(llm, LLMClient)

    schema = {"type": "object", "properties": {"nhan_dinh": {"type": "array"}}}
    messages = [
        ChatMessage(role="system", content="Vai trò trợ lý."),
        ChatMessage(role="user", content="Dữ liệu ca"),
    ]
    result = llm.complete_json(messages, schema)

    assert result == {"nhan_dinh": []}
    assert llm.last_usage == {"prompt_tokens": 10, "completion_tokens": 20}
    assert len(captured) == 1
    url, auth, payload = captured[0]
    assert url == "https://api.deepseek.com/chat/completions"
    assert auth == "Bearer key-test-123"
    assert payload["model"] == "deepseek-flash"
    assert payload["temperature"] == 0.0
    assert payload["max_tokens"] == 4096
    if reasoning is None:
        assert "reasoning_effort" not in payload
        assert "thinking" not in payload
    else:
        assert payload["reasoning_effort"] == "low"
    assert "reasoning" not in payload
    assert payload["top_p"] == 1.0
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["messages"][0]["role"] == "system"
    assert "Chỉ trả về một đối tượng JSON đúng lược đồ sau." in payload["messages"][0]["content"]
    assert '"nhan_dinh"' in payload["messages"][0]["content"]


def test_deepseek_retries_429_then_succeeds() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, text="rate limited")
        return httpx.Response(200, json=_ok_body('{"ok": true}'))

    llm = DeepSeekLLM(
        model="deepseek-flash",
        api_key="key-test-123",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_tokens=16000,
        max_tokens_retry=32000,
        max_attempts=3,
        sleep=sleeps.append,
    )
    assert llm.complete_json([ChatMessage(role="user", content="hi")], {}) == {"ok": True}
    assert calls == 2
    assert sleeps == [0.5]


def test_deepseek_401_fails_immediately_without_leaking_key_or_message() -> None:
    calls = 0
    sleeps: list[float] = []
    secret_key = "secret-api-value-999"
    secret_msg = "noi dung benh an nhay cam"

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, text=f"unauthorized {secret_key} " + "x" * 300)

    llm = DeepSeekLLM(
        model="deepseek-flash",
        api_key=secret_key,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_tokens=16000,
        max_tokens_retry=32000,
        max_attempts=3,
        sleep=sleeps.append,
    )
    with pytest.raises(ProviderError) as exc_info:
        llm.complete_json([ChatMessage(role="user", content=secret_msg)], {})

    assert calls == 1
    assert sleeps == []
    assert exc_info.value.retryable is False
    err_text = str(exc_info.value)
    assert "401" in err_text
    assert secret_key not in err_text
    assert secret_msg not in err_text


@pytest.mark.parametrize(
    ("finish_reason", "content"),
    [
        ("stop", "not valid json"),
        ("stop", "[1, 2, 3]"),
    ],
)
def test_deepseek_invalid_output_raises_non_retryable(finish_reason: str, content: str) -> None:
    calls = 0
    usage = {"completion_tokens": 100, "completion_tokens_details": {"reasoning_tokens": 50}}

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_ok_body(content, finish_reason=finish_reason, usage=usage))

    llm = DeepSeekLLM(
        model="deepseek-flash",
        api_key="key-test-123",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_tokens=16000,
        max_tokens_retry=32000,
        max_attempts=3,
        sleep=lambda _: None,
    )
    secret_msg = "tin nhan khong duoc ro ri"
    with pytest.raises(ProviderError) as exc_info:
        llm.complete_json([ChatMessage(role="user", content=secret_msg)], {})

    assert exc_info.value.retryable is False
    assert calls == 1
    assert llm.last_usage == usage
    assert "dau_ra_khong_hop_le" in str(exc_info.value)
    assert secret_msg not in str(exc_info.value)
    assert "key-test-123" not in str(exc_info.value)


def test_deepseek_network_error_retries_then_raises() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("connection down", request=request)

    llm = DeepSeekLLM(
        model="deepseek-flash",
        api_key="key-test-123",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_tokens=16000,
        max_tokens_retry=32000,
        max_attempts=3,
        sleep=sleeps.append,
    )
    with pytest.raises(ProviderError) as exc_info:
        llm.complete_json([ChatMessage(role="user", content="noi dung bi mat")], {})

    assert calls == 3
    assert sleeps == [0.5, 1.0]
    assert exc_info.value.retryable is True
    assert "noi dung bi mat" not in str(exc_info.value)
    assert "key-test-123" not in str(exc_info.value)


@pytest.mark.parametrize("truncated_content", ["", '{"nhan_dinh": [', '{"ok": true}'])
def test_deepseek_retries_truncation_with_configured_budget(truncated_content: str) -> None:
    payloads: list[dict] = []
    usage = {"completion_tokens": 5000, "completion_tokens_details": {"reasoning_tokens": 1000}}

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        if len(payloads) == 1:
            return httpx.Response(200, json=_ok_body(truncated_content, finish_reason="length"))
        return httpx.Response(200, json=_ok_body('{"ok": true}', usage=usage))

    llm = DeepSeekLLM(
        model="deepseek-flash",
        api_key="key-test-123",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_tokens=12000,
        max_tokens_retry=24000,
        reasoning={"reasoning_effort": "low"},
    )
    messages = [ChatMessage(role="user", content="Dữ liệu giả lập")]
    assert llm.complete_json(messages, {}) == {"ok": True}
    assert len(payloads) == 2
    assert payloads[0]["max_tokens"] == 12000
    assert payloads[1] == {**payloads[0], "max_tokens": 24000}
    assert llm.last_usage == usage

    assert llm.complete_json(messages, {}) == {"ok": True}
    assert payloads[2]["max_tokens"] == 12000


def test_deepseek_truncated_twice_raises_token_limit_and_retains_usage() -> None:
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        payloads.append(payload)
        usage = {"completion_tokens": payload["max_tokens"]}
        return httpx.Response(200, json=_ok_body("", finish_reason="length", usage=usage))

    llm = DeepSeekLLM(
        model="deepseek-flash",
        api_key="key-test-123",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_tokens=16000,
        max_tokens_retry=32000,
    )
    with pytest.raises(ProviderError) as exc_info:
        llm.complete_json([ChatMessage(role="user", content="Dữ liệu giả lập")], {})

    assert str(exc_info.value) == "het_han_muc_token"
    assert exc_info.value.retryable is False
    assert len(payloads) == 2
    assert [payload["max_tokens"] for payload in payloads] == [16000, 32000]
    assert llm.last_usage == {"completion_tokens": 32000}


def test_deepseek_retains_truncated_usage_when_retry_fails_http() -> None:
    calls = 0
    usage = {"completion_tokens": 16000, "completion_tokens_details": {"reasoning_tokens": 16000}}

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json=_ok_body("", finish_reason="length", usage=usage))
        return httpx.Response(401)

    llm = DeepSeekLLM(
        model="deepseek-flash",
        api_key="key-test-123",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_tokens=16000,
        max_tokens_retry=32000,
    )
    with pytest.raises(ProviderError, match="401"):
        llm.complete_json([ChatMessage(role="user", content="Dữ liệu giả lập")], {})

    assert calls == 2
    assert llm.last_usage == usage
