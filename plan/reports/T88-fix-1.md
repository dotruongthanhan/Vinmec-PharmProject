# T88-fix-1 – Báo cáo: Sửa 3 test trượt sau T88

```text
TRẠNG THÁI: CHƯA XONG
FILE ĐÃ TẠO / SỬA:
- Sửa: app/api/rate_limit.py
- Sửa: tests/api/test_llm_limits.py
- Sửa: tests/orchestration/test_jobs.py
- Tạo: plan/reports/T88-fix-1.md
LỆNH ĐÃ CHẠY VÀ KẾT QUẢ: Không chạy lệnh nào (phiên này bị ràng buộc KHÔNG gọi shell, không gọi mạng; chỉ đọc và ghi tệp).
ĐIỂM LỆCH SO VỚI BRIEF (nếu có) VÀ LÝ DO: Không có điểm lệch về mã nguồn; chỉ chưa chạy các lệnh nghiệm thu ở mục "Nghiệm thu (Claude chạy)" do ràng buộc không dùng shell của phiên.
VIỆC CHƯA LÀM / CÂU HỎI: Cần chạy các lệnh nghiệm thu để xác nhận lint, format và toàn bộ bộ test.
```

## Chi tiết các thay đổi đã thực hiện

1. **[rate_limit.py](file:///D:/create/Vinmec-PharmProject/app/api/rate_limit.py#L5-L42)**:
   - Đổi `_read_positive_int_env` từ `get_secret(name)` sang `os.environ.get(name)` để không gọi `load_dotenv()` (vốn bị chặn trong `tests/db/conftest.py`).
   - Bỏ import `get_secret` và `ConfigError` không còn dùng; giữ nguyên hành vi trả mặc định và ghi cảnh báo khi giá trị không hợp lệ hoặc `< 1`.
2. **[test_llm_limits.py](file:///D:/create/Vinmec-PharmProject/tests/api/test_llm_limits.py#L648-L666)**:
   - Trong `test_sliding_window_and_daily_budget_thread_safety_and_header_preservation`, khai báo route `/api/test-retry-after` qua `APIRouter` riêng rồi chèn lên đầu `app.router.routes.insert(0, test_router.routes[0])` để không bị route SPA bắt mọi đường dẫn nuốt thành `404`.
   - Giữ nguyên khẳng định `429`, `retry-after: 42`, `loi.ma == "vuot_gioi_han"`.
3. **[test_jobs.py](file:///D:/create/Vinmec-PharmProject/tests/orchestration/test_jobs.py#L70-L114)**:
   - Đổi tên `test_job_manager_restart_ignores_stale_previous_run` thành `test_job_manager_restart_while_running_keeps_current_job`.
   - Kiểm thử đúng hành vi T88: khi `slow_first` đang chạy, `start(..., restart=True)` trả trạng thái `dang_chay` hiện có, hàm `second_job` không được gọi (`new_calls == 0`), sau khi mở khoá kết quả là `"cu"`; sau khi xong gọi lại `start(..., restart=True)` mới chạy `second_job` (`new_calls == 1`) và cho kết quả `"moi"`.

## Lệnh nghiệm thu cần chạy

```powershell
uv run ruff check .
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider
```
