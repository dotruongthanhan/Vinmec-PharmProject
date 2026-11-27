"""Bọc và hỗ trợ ghi span LLM: mô hình, token từ last_usage, độ trễ, thử lại và băm prompt."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from typing import Any

from app.core.errors import ProviderError
from app.core.interfaces import LLMClient
from app.core.types import ChatMessage
from app.tracing.context import span, vet_hien_tai
from app.tracing.sanitize import bam_du_lieu

phien_ban_prompt_hien_tai: ContextVar[str | None] = ContextVar(
    "phien_ban_prompt_hien_tai",
    default=None,
)

_HTTP_STATUS_RE = re.compile(r"HTTP (\d{3}):")


def chuan_bi_thong_tin_prompt(
    messages: Sequence[ChatMessage],
) -> tuple[int, str, list[dict[str, str]]]:
    """Đo số ký tự, tính băm SHA-256 và lập bản tuần tự hoá của danh sách tin nhắn prompt."""
    serialized = [{"role": msg.role, "content": msg.content} for msg in messages]
    char_count = sum(len(msg.content) for msg in messages)
    return char_count, bam_du_lieu(serialized), serialized


def trich_usage(usage: Mapping[str, Any] | None) -> dict[str, int]:
    """Đọc số token vào, ra, suy luận và cache trúng từ từ điển last_usage."""
    if not isinstance(usage, Mapping):
        return {"token_vao": 0, "token_ra": 0, "tong_token": 0}

    def _as_int(value: Any) -> int:
        if isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return max(0, value)
        return 0

    token_vao = _as_int(usage.get("prompt_tokens", usage.get("input_tokens")))
    token_ra = _as_int(usage.get("completion_tokens", usage.get("output_tokens")))
    tong_token = _as_int(usage.get("total_tokens")) or (token_vao + token_ra)
    out: dict[str, int] = {
        "token_vao": token_vao,
        "token_ra": token_ra,
        "tong_token": tong_token,
    }
    details = usage.get("completion_tokens_details")
    if isinstance(details, Mapping):
        reasoning = _as_int(details.get("reasoning_tokens"))
        if reasoning > 0:
            out["token_suy_luan"] = reasoning
    cache_hit = _as_int(usage.get("prompt_cache_hit_tokens"))
    if cache_hit > 0:
        out["token_cache_trung"] = cache_hit
    return out


def ma_loi_nha_cung_cap_an_toan(exc: Exception) -> str:
    """Rút gọn ngoại lệ nhà cung cấp thành mã ngắn không chứa thân lỗi hay bí mật."""
    if isinstance(exc, ProviderError):
        msg = str(exc)
        if msg in {"het_han_muc_token", "dau_ra_khong_hop_le"}:
            return msg
        if msg == "Lỗi kết nối nhà cung cấp":
            return "provider_connection_error"
        match = _HTTP_STATUS_RE.match(msg)
        if match is not None:
            return f"provider_http_{match.group(1)}"
        return "provider_error"
    return type(exc).__name__


class TracingLLMClient:
    """Lớp bọc LLMClient ghi span loại llm từ last_usage mà không đổi hành vi gốc."""

    _tu_ghi_vet: bool = True

    def __init__(self, inner: LLMClient, *, model: str | None = None) -> None:
        self._inner = inner
        self._model = model

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    @property
    def model_name(self) -> str:
        """Tên mô hình ưu tiên truyền vào hoặc lấy từ thuộc tính `model` của máy khách gốc."""
        if self._model:
            return self._model
        inner_model = getattr(self._inner, "model", None)
        return str(inner_model) if inner_model else type(self._inner).__name__

    def complete_json(self, messages: list[ChatMessage], schema: dict) -> dict:
        """Gọi máy khách gốc trong một span loại llm, đọc last_usage và cập nhật tổng vết."""
        if getattr(self._inner, "_tu_ghi_vet", False):
            return self._inner.complete_json(messages, schema)
        return _invoke_with_llm_span(
            self._inner,
            messages,
            schema,
            mo_hinh=self.model_name,
            phien_ban_prompt=phien_ban_prompt_hien_tai.get(),
        )


def _invoke_with_llm_span(
    llm: LLMClient,
    messages: list[ChatMessage],
    schema: dict,
    *,
    mo_hinh: str | None,
    phien_ban_prompt: str | None,
) -> dict:
    """Thực thi complete_json bên trong span llm và gom số đo token vào vết hiện hành."""
    vet = vet_hien_tai.get()
    if vet is None:
        return llm.complete_json(messages, schema)

    model_label = mo_hinh or str(getattr(llm, "model", "") or type(llm).__name__)
    char_count, prompt_hash, prompt_payload = chuan_bi_thong_tin_prompt(messages)
    init_attrs: dict[str, Any] = {
        "mo_hinh": model_label,
        "so_ky_tu_prompt": char_count,
        "bam_prompt": prompt_hash,
    }
    if phien_ban_prompt:
        init_attrs["phien_ban_prompt"] = phien_ban_prompt
    vet.cap_nhat_phien_ban(mo_hinh=model_label, prompt=phien_ban_prompt or "")

    with span("llm", model_label, **init_attrs) as llm_span:
        if vet.muc_noi_dung != "sieu_du_lieu":
            llm_span.dat_noi_dung({"prompt": prompt_payload})
        try:
            result = llm.complete_json(messages, schema)
        except Exception as exc:
            usage = trich_usage(getattr(llm, "last_usage", None))
            cost = vet.cong_token(
                usage["token_vao"],
                usage["token_ra"],
                mo_hinh=model_label,
            )
            retries = int(getattr(llm, "last_retries", 0) or 0)
            finish_reason = getattr(llm, "last_finish_reason", None) or "loi"
            llm_span.dat_thuoc_tinh(
                **usage,
                chi_phi_uoc_tinh=cost,
                so_lan_thu_lai=retries,
                ly_do_ket_thuc=str(finish_reason),
                ma_loi=ma_loi_nha_cung_cap_an_toan(exc),
            )
            raise

        usage = trich_usage(getattr(llm, "last_usage", None))
        cost = vet.cong_token(
            usage["token_vao"],
            usage["token_ra"],
            mo_hinh=model_label,
        )
        retries = int(getattr(llm, "last_retries", 0) or 0)
        finish_reason = getattr(llm, "last_finish_reason", None) or "stop"
        llm_span.dat_thuoc_tinh(
            **usage,
            chi_phi_uoc_tinh=cost,
            so_lan_thu_lai=retries,
            ly_do_ket_thuc=str(finish_reason),
        )
        if vet.muc_noi_dung != "sieu_du_lieu":
            llm_span.dat_noi_dung({"phan_hoi": json.dumps(result, ensure_ascii=False, default=str)})
        return result


def goi_llm_co_vet(
    llm: LLMClient,
    messages: list[ChatMessage],
    schema: dict,
    *,
    phien_ban_prompt: str | None = None,
    mo_hinh: str | None = None,
) -> dict:
    """Gọi LLM kèm ngữ cảnh phiên bản prompt; tự tạo span nếu máy khách chưa tự ghi vết."""
    token = phien_ban_prompt_hien_tai.set(phien_ban_prompt)
    try:
        if getattr(llm, "_tu_ghi_vet", False):
            return llm.complete_json(messages, schema)
        return _invoke_with_llm_span(
            llm,
            messages,
            schema,
            mo_hinh=mo_hinh,
            phien_ban_prompt=phien_ban_prompt,
        )
    finally:
        phien_ban_prompt_hien_tai.reset(token)
