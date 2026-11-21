# T88-fix-1 – Sửa 3 test trượt sau T88

Agent: agy `gemini-4-hydrogen-high`. **Không gọi shell, không gọi mạng; chỉ đọc và ghi tệp.** Đọc `plan/briefs/T88-tran-chi-phi-llm.md`, `plan/reports/T88.md`.

Review T88: logic đạt (Claude kiểm độc lập: 200 lượt `chay_lai` đồng thời → runner chạy 1 lần; trần hàng đợi trả 429 `hang_doi_day` `Retry-After: 30`; `/ask` 20 qua / 5 bị 429; size 422). pytest: **3 trượt / 1.617 qua**.

## Sửa

1. **`app/api/rate_limit.py` `_read_positive_int_env`**: đang đọc bằng `get_secret`, hàm này nạp `.env` và bị chặn trong `tests/db/conftest.py` → `tests/db/test_bang_luat.py::test_container_service_asker_use_db_without_local_kb_files` trượt. Đây là cấu hình, không phải bí mật: đổi sang `os.environ.get(name)`. Bỏ import `get_secret`/`ConfigError` nếu không còn dùng. Giữ nguyên hành vi giá trị sai → mặc định + cảnh báo.
2. **`tests/api/test_llm_limits.py::test_sliding_window_and_daily_budget_thread_safety_and_header_preservation`**: route `/api/test-retry-after` thêm **sau** `create_app` nên bị route bắt-mọi-đường-dẫn của SPA nuốt → 404. Sửa test: tạo `APIRouter`, khai báo route trong đó, rồi chèn route lên đầu (`app.router.routes.insert(0, <route>)`) hoặc cách tương đương không đụng `main.py`. Khẳng định vẫn như cũ (429, `retry-after: 42`, `ma = vuot_gioi_han`).
3. **`tests/orchestration/test_jobs.py::test_job_manager_restart_ignores_stale_previous_run`**: khẳng định hành vi cũ (restart khi đang chạy thay việc mới) mà T88 cố ý bỏ. Viết lại theo hành vi mới: khi `slow_first` đang chạy, `start(..., restart=True)` trả trạng thái `dang_chay` hiện có, hàm `"moi"` **không** được gọi (đếm lượt), kết quả sau khi mở khoá là `"cu"`. Rồi sau khi xong, `restart=True` lần nữa → chạy `"moi"`, kết quả `"moi"`. Đổi tên test cho đúng nghĩa (ví dụ `test_job_manager_restart_while_running_keeps_current_job`).

## Phạm vi tệp

Chỉ: `app/api/rate_limit.py`, `tests/api/test_llm_limits.py`, `tests/orchestration/test_jobs.py`. Cấm tệp khác.

## Nghiệm thu (Claude chạy)

```
uv run ruff check .
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider
```

Ghi `plan/reports/T88-fix-1.md` theo mẫu `AGENTS.md`.
