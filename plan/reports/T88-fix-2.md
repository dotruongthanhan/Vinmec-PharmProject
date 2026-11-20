# T88-fix-2 – Báo cáo: Đưa việc đọc biến môi trường giới hạn LLM về `app/config`

```text
TRẠNG THÁI: CHƯA XONG
FILE ĐÃ TẠO / SỬA:
- Sửa: app/config/settings.py
- Sửa: app/api/rate_limit.py
- Sửa: tests/api/test_llm_limits.py
- Tạo: plan/reports/T88-fix-2.md
LỆNH ĐÃ CHẠY VÀ KẾT QUẢ: Không chạy lệnh nào (phiên này bị ràng buộc KHÔNG gọi shell, không gọi mạng; chỉ đọc và ghi tệp).
ĐIỂM LỆCH SO VỚI BRIEF (nếu có) VÀ LÝ DO: Không có điểm lệch về mã nguồn; chỉ chưa chạy các lệnh nghiệm thu ở mục "Nghiệm thu (Claude chạy)" do ràng buộc không dùng shell của phiên.
VIỆC CHƯA LÀM / CÂU HỎI: Cần chạy các lệnh nghiệm thu để xác nhận lint, format và toàn bộ bộ test (đặc biệt là `tests/architecture/test_import_boundaries.py::test_environment_access_only_in_config` và `tests/api/test_llm_limits.py`).
```

## Chi tiết các thay đổi đã thực hiện

1. **[settings.py](file:///D:/create/Vinmec-PharmProject/app/config/settings.py#L26-L56)**:
   - Thêm các hằng mặc định `DEFAULT_LLM_ASK_PER_5MIN = 20`, `DEFAULT_LLM_AI_PER_HOUR = 15`, `DEFAULT_LLM_DAILY_CALLS = 600`.
   - Thêm `_read_positive_int_env(name: str, default: int) -> int` dùng `os.getenv(name)` (không gọi `load_dotenv`, không gọi `get_secret`): giá trị `None` hoặc rỗng sau `strip()` trả về mặc định; giá trị không phải số nguyên hoặc `< 1` ghi `_LOGGER.warning` (chỉ nêu tên biến và mặc định, không in giá trị) rồi trả về mặc định.
   - Thêm `load_llm_rate_limits() -> tuple[int, int, int]` trả `(ask_per_5min, ai_per_hour, daily_calls)` từ `LLM_ASK_PER_5MIN`, `LLM_AI_PER_HOUR`, `LLM_DAILY_CALLS`.
2. **[rate_limit.py](file:///D:/create/Vinmec-PharmProject/app/api/rate_limit.py#L12-L26)**:
   - Bỏ `import os`, `import logging`, `_LOGGER`, và hàm `_read_positive_int_env` để không truy cập biến môi trường ngoài `app/config`.
   - Gán lại `DEFAULT_ASK_PER_5MIN`, `DEFAULT_AI_PER_HOUR`, `DEFAULT_DAILY_CALLS` từ các hằng trong `app/config/settings.py`.
   - Cập nhật `LlmRateLimits.from_env()` gọi `load_llm_rate_limits()`.
3. **[test_llm_limits.py](file:///D:/create/Vinmec-PharmProject/tests/api/test_llm_limits.py#L604-L628)**:
   - Cập nhật `test_invalid_env_limits_fallback_to_defaults_with_warning` để kiểm tra giá trị rỗng/thiếu qua `load_llm_rate_limits()` không ghi cảnh báo, và khi giá trị sai thì bắt log từ logger `app.config.settings`, xác nhận giữ mặc định, có tên biến trong log và không lộ giá trị sai (`abc`, `-10`).

## Lệnh nghiệm thu cần chạy

```powershell
uv run ruff check .
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider
```
