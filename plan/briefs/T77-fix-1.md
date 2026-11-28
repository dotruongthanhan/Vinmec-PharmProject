# T77-fix-1 – Import vòng `app.db.bang_luat` ↔ `app.rules.*`; test lọt ra DB thật; streamlit import luật; E501

Agent: **agy Gemini 4 Hydrogen xhigh**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.**

## Lỗi (Claude review T77: 1.511 qua, 5 trượt)

1. **Import vòng – lỗi thật, CLI hỏng:** `uv run python -m app.db.cli load bang-luat --dry-run` →
   `ImportError: cannot import name 'BangLuatReadError' from partially initialized module 'app.db.bang_luat'` (đi qua `app/rules/allergy_config.py:13`). `app.db.bang_luat` import các mô hình trong `app.rules.*_config` để kiểm tài liệu, còn `app.rules.*_config` import `app.db.bang_luat` để nạp. Sửa bằng cách tách: phần **đọc dữ liệu thô từ DB** (`load_rule_data`, `load_document`, `BangLuatReadError`, `register_cache_clear`, `clear_all_caches`, định nghĩa bảng) sang module không import `app.rules` (ví dụ `app/db/bang_luat_store.py`); phần **kiểm bằng mô hình + nạp** (`validate_document`, `load_bang_luat`, CLI) giữ ở `app/db/bang_luat.py` và chỉ import mô hình **bên trong hàm** nếu cần. `app.rules.*` chỉ import module đọc. Test `tests/db/test_cli.py::test_windows_encoding_does_not_leak_connection_traceback` phải qua lại (nó đang trượt vì lỗi import này). Thêm một test chạy `python -m app.db.cli load bang-luat --dry-run` bằng `subprocess` → mã thoát 0.
2. **Test lọt ra DB thật:** `tests/db/test_bang_luat.py::test_runtime_loaders_db_and_auto_match_file`, `::test_db_failure_returns_safe_fallback_and_logs_single_warning_without_dsn`, `::test_container_service_asker_use_db_without_local_kb_files` gặp chốt chặn `conftest` "Test không được kết nối cơ sở dữ liệu thật". Đường đọc DB ở runtime phải đi qua **một điểm tiêm được** (một hàm lấy kết nối trong module đọc ở mục 1) mà test thay bằng kết nối giả; không gọi thẳng `read_pool.connection` / `psycopg.connect` ở nhiều chỗ. Xoá các `lru_cache` giữa test (`clear_all_caches`) trong fixture.
3. `tests/ui/test_static_safety.py::test_only_services_imports_pipeline_or_rules_at_runtime`: `app/ui/streamlit_app.py` không được import `app.rules.renal_dose`. Hoàn lại cách cũ của streamlit (chỉ qua `app/ui/services.py`), chuyển phần cần thiết vào `services.py`.
4. E501 `app/db/bang_luat.py:1729` và `ruff format --check` báo 4 tệp lệch: định dạng lại.

## Phạm vi

`app/db/bang_luat.py`, module đọc mới, `app/rules/*_config.py`, `app/rules/renal_dose.py`, `app/kb/names.py` (chỉ dòng import / cách lấy kết nối), `app/ui/streamlit_app.py`, `app/ui/services.py`, `tests/db/test_bang_luat.py`, `tests/db/test_cli.py` (thêm test), các tệp lệch định dạng. Không đổi logic luật, không đổi lược đồ. Thêm mục "fix-1" vào `plan/reports/T77.md`.
