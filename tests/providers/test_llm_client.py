"""Kiểm thử máy khách ChatLLMClient với httpx.MockTransport (không gọi mạng thật)."""

import json

import httpx
import pytest

from app.core.errors import ProviderError
from app.core.interfaces import LLMClient
from app.core.types import ChatMessage
from app.providers.llm_client import ChatLLMClient


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


def test_rotation_and_payload_with_eight_keys() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=_ok_body('{"ok": true}'))

    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    llm = ChatLLMClient(
        model="gemini-3.5-flash-lite",
        url=url,
        keys=[f"key-{i}" for i in range(1, 9)],
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_tokens=100,
        max_tokens_retry=200,
        reasoning={"reasoning_effort": "low"},
    )
    for _ in range(9):
        assert llm.complete_json([], {}) == {"ok": True}
    assert [r.headers["authorization"] for r in calls] == [
        *(f"Bearer key-{i}" for i in range(1, 9)),
        "Bearer key-1",
    ]
    assert str(calls[0].url) == url
    body = json.loads(calls[0].content)
    assert body["model"] == "gemini-3.5-flash-lite"
    assert body["reasoning_effort"] == "low"
    assert body["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_first_key_failure_moves_to_second(status: int) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["authorization"])
        if len(seen) == 1:
            return httpx.Response(status, headers={"Retry-After": "5"})
        return httpx.Response(200, json=_ok_body('{"ok": true}'))

    llm = ChatLLMClient(
        model="model-test",
        url="https://example.invalid",
        keys=["key-a", "key-b"],
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_tokens=10,
        max_tokens_retry=20,
    )
    assert llm.complete_json([], {}) == {"ok": True}
    assert seen == ["Bearer key-a", "Bearer key-b"]


@pytest.mark.parametrize("status, expected", [(429, 8), (402, 1)])
def test_all_rate_limited_or_payment_error(status: int, expected: int) -> None:
    keys = [f"very-secret-key-{i}" for i in range(8)]
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers["authorization"])
        return httpx.Response(status, text=" ".join(keys))

    llm = ChatLLMClient(
        model="model-test",
        url="https://example.invalid",
        keys=keys,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_tokens=10,
        max_tokens_retry=20,
    )
    with pytest.raises(ProviderError) as error:
        llm.complete_json([], {})
    assert len(calls) == expected
    assert error.value.retryable is (status == 429)
    assert all(key not in str(error.value) for key in keys)


def test_trace_records_model_usage_and_key_numbers(tmp_path) -> None:
    from app.config.settings import TracerSettings
    from app.tracing import Tracer

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers["authorization"] == "Bearer key-a":
            return httpx.Response(429)
        return httpx.Response(200, json=_ok_body('{"ok": true}'))

    llm = ChatLLMClient(
        model="gemini-3.5-flash-lite",
        url="https://example.invalid",
        keys=["key-a", "key-b"],
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_tokens=10,
        max_tokens_retry=20,
    )
    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path)))
    with tracer.bat_dau_vet("hoi_dap", "agentic"):
        llm.complete_json([], {})
    assert tracer.flush()
    record = json.loads(next(tmp_path.glob("vet-*.jsonl")).read_text(encoding="utf-8"))
    attrs = record["cac_buoc"][0]["thuoc_tinh"]
    assert (attrs["mo_hinh"], attrs["token_vao"], attrs["token_ra"]) == (
        "gemini-3.5-flash-lite",
        10,
        20,
    )
    assert (attrs["khoa_so"], attrs["so_khoa_da_thu"]) == (2, 2)
    assert "key-a" not in str(record) and "key-b" not in str(record)
    tracer.close()


@pytest.mark.parametrize("reasoning", [None, {"reasoning_effort": "low"}])
def test_chat_api_complete_json_success_and_request_payload(
    reasoning: dict[str, str] | None,
) -> None:
    captured: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        captured.append((str(request.url), request.headers.get("authorization", ""), body))
        return httpx.Response(200, json=_ok_body('  {"nhan_dinh": []}  '))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = ChatLLMClient(
        model="model-test",
        url="https://example.invalid/chat/completions",
        keys=["key-test-123"],
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
    assert url == "https://example.invalid/chat/completions"
    assert auth == "Bearer key-test-123"
    assert payload["model"] == "model-test"
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


def test_chat_api_retries_429_then_succeeds() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, text="rate limited")
        return httpx.Response(200, json=_ok_body('{"ok": true}'))

    llm = ChatLLMClient(
        model="model-test",
        url="https://example.invalid/chat/completions",
        keys=["key-test-123", "key-test-456"],
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_tokens=16000,
        max_tokens_retry=32000,
        max_attempts=3,
        sleep=sleeps.append,
    )
    assert llm.complete_json([ChatMessage(role="user", content="hi")], {}) == {"ok": True}
    assert calls == 2
    assert sleeps == []


def test_chat_api_401_fails_immediately_without_leaking_key_or_message() -> None:
    calls = 0
    sleeps: list[float] = []
    secret_key = "secret-api-value-999"
    secret_msg = "noi dung benh an nhay cam"

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, text=f"unauthorized {secret_key} " + "x" * 300)

    llm = ChatLLMClient(
        model="model-test",
        url="https://example.invalid/chat/completions",
        keys=[secret_key],
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
    assert exc_info.value.retryable is True
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
def test_chat_api_invalid_output_raises_non_retryable(finish_reason: str, content: str) -> None:
    calls = 0
    usage = {"completion_tokens": 100, "completion_tokens_details": {"reasoning_tokens": 50}}

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_ok_body(content, finish_reason=finish_reason, usage=usage))

    llm = ChatLLMClient(
        model="model-test",
        url="https://example.invalid/chat/completions",
        keys=["key-test-123"],
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


def test_chat_api_network_error_retries_then_raises() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("connection down", request=request)

    llm = ChatLLMClient(
        model="model-test",
        url="https://example.invalid/chat/completions",
        keys=["key-test-123", "key-test-456", "key-test-789"],
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_tokens=16000,
        max_tokens_retry=32000,
        max_attempts=3,
        sleep=sleeps.append,
    )
    with pytest.raises(ProviderError) as exc_info:
        llm.complete_json([ChatMessage(role="user", content="noi dung bi mat")], {})

    assert calls == 3
    assert sleeps == []
    assert exc_info.value.retryable is True
    assert "noi dung bi mat" not in str(exc_info.value)
    assert "key-test-123" not in str(exc_info.value)


@pytest.mark.parametrize("truncated_content", ["", '{"nhan_dinh": [', '{"ok": true}'])
def test_chat_api_retries_truncation_with_configured_budget(truncated_content: str) -> None:
    payloads: list[dict] = []
    usage = {"completion_tokens": 5000, "completion_tokens_details": {"reasoning_tokens": 1000}}

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        if len(payloads) == 1:
            return httpx.Response(200, json=_ok_body(truncated_content, finish_reason="length"))
        return httpx.Response(200, json=_ok_body('{"ok": true}', usage=usage))

    llm = ChatLLMClient(
        model="model-test",
        url="https://example.invalid/chat/completions",
        keys=["key-test-123"],
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


def test_chat_api_truncated_twice_raises_token_limit_and_retains_usage() -> None:
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        payloads.append(payload)
        usage = {"completion_tokens": payload["max_tokens"]}
        return httpx.Response(200, json=_ok_body("", finish_reason="length", usage=usage))

    llm = ChatLLMClient(
        model="model-test",
        url="https://example.invalid/chat/completions",
        keys=["key-test-123"],
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


def test_chat_api_retains_truncated_usage_when_retry_fails_http() -> None:
    calls = 0
    usage = {"completion_tokens": 16000, "completion_tokens_details": {"reasoning_tokens": 16000}}

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json=_ok_body("", finish_reason="length", usage=usage))
        return httpx.Response(401)

    llm = ChatLLMClient(
        model="model-test",
        url="https://example.invalid/chat/completions",
        keys=["key-test-123"],
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_tokens=16000,
        max_tokens_retry=32000,
    )
    with pytest.raises(ProviderError, match="401"):
        llm.complete_json([ChatMessage(role="user", content="Dữ liệu giả lập")], {})

    assert calls == 2
    assert llm.last_usage == usage
