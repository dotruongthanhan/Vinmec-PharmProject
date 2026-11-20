# T88-fix-2 – Đưa việc đọc biến môi trường giới hạn LLM về `app/config`

Agent: agy `gemini-4-hydrogen-high`. **Không gọi shell, không gọi mạng; chỉ đọc và ghi tệp.**

Sau T88-fix-1: 1.619 qua, **1 trượt**: `tests/architecture/test_import_boundaries.py::test_environment_access_only_in_config`. Lý do: `app/api/rate_limit.py` gọi `os.environ.get`, quy tắc kiến trúc chỉ cho đọc môi trường trong `app/config`.

## Sửa

1. `app/config/settings.py`: thêm `def load_llm_rate_limits() -> tuple[int, int, int]` trả `(ask_per_5min, ai_per_hour, daily_calls)`, đọc `LLM_ASK_PER_5MIN`, `LLM_AI_PER_HOUR`, `LLM_DAILY_CALLS` bằng `os.getenv` **giống `load_case_source`** (không gọi `load_dotenv`, không gọi `get_secret`). Mặc định 20, 15, 600. Giá trị rỗng → mặc định; không phải số nguyên dương → mặc định + `logger.warning` (không in giá trị). Đặt hằng mặc định trong `settings.py`.
2. `app/api/rate_limit.py`: bỏ `os` và `_read_positive_int_env`; `LlmRateLimits.from_env()` gọi `load_llm_rate_limits()`. Giữ hằng `DEFAULT_*` nếu test đang import (đọc `tests/api/test_llm_limits.py`), có thể gán lại từ `settings`.
3. Sửa test nếu cần cho khớp (test biến môi trường sai vẫn phải có, chuyển sang gọi `load_llm_rate_limits` hoặc `from_env`).

## Phạm vi

Chỉ: `app/config/settings.py` (chỉ thêm hàm và hằng), `app/api/rate_limit.py`, `tests/api/test_llm_limits.py`. Cấm tệp khác.

## Nghiệm thu (Claude chạy)

```
uv run ruff check .
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider
```

Ghi `plan/reports/T88-fix-2.md` theo mẫu `AGENTS.md`.
