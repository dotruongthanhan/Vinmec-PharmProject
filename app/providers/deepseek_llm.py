"""Máy khách gọi API DeepSeek trả về đối tượng JSON theo lược đồ."""

import json
import time
from collections.abc import Callable

import httpx

from app.core.errors import ProviderError
from app.core.types import ChatMessage
from app.providers.http import post_json
from app.tracing import (
    chuan_bi_thong_tin_prompt,
    ma_loi_nha_cung_cap_an_toan,
    phien_ban_prompt_hien_tai,
    span,
    trich_usage,
    vet_hien_tai,
)

_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


class DeepSeekLLM:
    """Cài đặt giao diện LLMClient cho API tương thích OpenAI của DeepSeek."""

    _tu_ghi_vet: bool = True

    def __init__(
        self,
        model: str,
        api_key: str,
        client: httpx.Client,
        max_tokens: int,
        max_tokens_retry: int,
        temperature: float = 0.0,
        top_p: float = 1.0,
        max_attempts: int = 3,
        sleep: Callable[[float], None] = time.sleep,
        reasoning: dict[str, str] | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("api_key không được rỗng")
        if max_attempts <= 0:
            raise ValueError("max_attempts phải > 0")
        self.model = model
        self.api_key = api_key
        self.client = client
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_tokens_retry = max_tokens_retry
        self.reasoning = dict(reasoning) if reasoning is not None else None
        self.top_p = top_p
        self.max_attempts = max_attempts
        self.sleep = sleep
        self.last_usage: dict | None = None
        self.last_finish_reason: str | None = None
        self.last_retries: int = 0

    def complete_json(self, messages: list[ChatMessage], schema: dict) -> dict:
        """Nối lược đồ vào tin nhắn hệ thống, gọi DeepSeek và đọc JSON đối tượng."""
        self.last_usage = None
        self.last_finish_reason = None
        self.last_retries = 0
        schema_block = (
            "Chỉ trả về một đối tượng JSON đúng lược đồ sau.\n"
            f"{json.dumps(schema, ensure_ascii=False)}"
        )
        payload_messages: list[dict[str, str]] = []
        appended = False
        for msg in messages:
            if msg.role == "system" and not appended:
                sep = "\n\n" if msg.content else ""
                payload_messages.append(
                    {"role": msg.role, "content": f"{msg.content}{sep}{schema_block}"}
                )
                appended = True
            else:
                payload_messages.append({"role": msg.role, "content": msg.content})
        if not appended:
            payload_messages.insert(0, {"role": "system", "content": schema_block})

        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "response_format": {"type": "json_object"},
            "messages": payload_messages,
        }
        if self.reasoning is not None:
            payload.update(self.reasoning)

        retry_counter = [0]
        usages: list[dict[str, int]] = []
        vet = vet_hien_tai.get()
        if vet is None:
            return self._execute_with_retry(payload, retry_counter, usages)

        char_count, prompt_hash, prompt_payload = chuan_bi_thong_tin_prompt(messages)
        prompt_version = phien_ban_prompt_hien_tai.get()
        init_attrs: dict[str, object] = {
            "mo_hinh": self.model,
            "so_ky_tu_prompt": char_count,
            "bam_prompt": prompt_hash,
        }
        if prompt_version:
            init_attrs["phien_ban_prompt"] = prompt_version
        vet.cap_nhat_phien_ban(mo_hinh=self.model, prompt=prompt_version or "")

        with span("llm", self.model, **init_attrs) as llm_span:
            if vet.muc_noi_dung != "sieu_du_lieu":
                llm_span.dat_noi_dung({"prompt": prompt_payload})
            error_code: str | None = None
            try:
                parsed = self._execute_with_retry(payload, retry_counter, usages)
            except Exception as exc:
                error_code = ma_loi_nha_cung_cap_an_toan(exc)
                raise
            finally:
                total_in = sum(item["token_vao"] for item in usages)
                total_out = sum(item["token_ra"] for item in usages)
                total_reasoning = sum(item.get("token_suy_luan", 0) for item in usages)
                total_cache = sum(item.get("token_cache_trung", 0) for item in usages)
                total_tokens = sum(item["tong_token"] for item in usages) or (total_in + total_out)
                cost = vet.cong_token(total_in, total_out, mo_hinh=self.model)
                self.last_retries = retry_counter[0]
                attrs: dict[str, object] = {
                    "token_vao": total_in,
                    "token_ra": total_out,
                    "tong_token": total_tokens,
                    "chi_phi_uoc_tinh": cost,
                    "so_lan_thu_lai": retry_counter[0],
                    "ly_do_ket_thuc": self.last_finish_reason or "loi",
                }
                if total_reasoning > 0:
                    attrs["token_suy_luan"] = total_reasoning
                if total_cache > 0:
                    attrs["token_cache_trung"] = total_cache
                if error_code is not None:
                    attrs["ma_loi"] = error_code
                llm_span.dat_thuoc_tinh(**attrs)

            if vet.muc_noi_dung != "sieu_du_lieu":
                llm_span.dat_noi_dung(
                    {"phan_hoi": json.dumps(parsed, ensure_ascii=False, default=str)}
                )
            return parsed

    def _execute_with_retry(
        self,
        payload: dict,
        retry_counter: list[int],
        usages: list[dict[str, int]],
    ) -> dict:
        """Gọi API và thử lại đúng một lần với max_tokens_retry khi phản hồi bị cắt."""
        try:
            return self._request_json(payload, retry_counter=retry_counter, usages=usages)
        except ProviderError as exc:
            if str(exc) != "het_han_muc_token":
                self.last_retries = retry_counter[0]
                raise
        retry_counter[0] += 1
        payload["max_tokens"] = self.max_tokens_retry
        try:
            return self._request_json(payload, retry_counter=retry_counter, usages=usages)
        finally:
            self.last_retries = retry_counter[0]

    def _request_json(
        self,
        payload: dict,
        *,
        retry_counter: list[int] | None = None,
        usages: list[dict[str, int]] | None = None,
    ) -> dict:
        """Gọi API, lưu số đo và phân biệt phản hồi bị cắt với JSON sai."""

        def _counted_sleep(seconds: float) -> None:
            if retry_counter is not None:
                retry_counter[0] += 1
            self.sleep(seconds)

        data = post_json(
            self.client,
            _DEEPSEEK_URL,
            payload,
            [self.api_key],
            self.max_attempts,
            sleep=_counted_sleep,
        )

        usage = data.get("usage")
        self.last_usage = usage if isinstance(usage, dict) else None
        if usages is not None and isinstance(usage, dict):
            usages.append(trich_usage(usage))

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError("dau_ra_khong_hop_le", retryable=False)
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ProviderError("dau_ra_khong_hop_le", retryable=False)
        raw_finish = choice.get("finish_reason")
        self.last_finish_reason = str(raw_finish) if raw_finish is not None else None
        if raw_finish == "length":
            raise ProviderError("het_han_muc_token", retryable=False)

        message = choice.get("message")
        if not isinstance(message, dict):
            raise ProviderError("dau_ra_khong_hop_le", retryable=False)
        content = message.get("content")
        if not isinstance(content, str):
            raise ProviderError("dau_ra_khong_hop_le", retryable=False)

        try:
            parsed = json.loads(content.strip())
        except ValueError:
            raise ProviderError("dau_ra_khong_hop_le", retryable=False) from None
        if not isinstance(parsed, dict):
            raise ProviderError("dau_ra_khong_hop_le", retryable=False)
        return parsed
