# Báo cáo thực hiện T87-fix-1 – Gỡ phần phân công (T86 hoãn), sửa lint, bổ sung cảnh báo triển khai

```text
TRẠNG THÁI: CHƯA XONG (đã sửa đủ 4 tệp theo brief; chưa chạy lệnh nghiệm thu do ràng buộc không gọi shell/mạng/DB/MCP)
FILE ĐÃ TẠO / SỬA:
- Sửa: db/roles.sql
- Sửa: .env.app.example
- Sửa: tests/db/test_roles_sql.py
- Sửa: docs/van-hanh/tai-khoan-db.md
- Tạo mới: plan/reports/T87-fix-1.md
LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:
- Không chạy lệnh shell nào theo đúng ràng buộc "KHÔNG gọi shell, không gọi mạng, không kết nối DB, không gọi MCP; chỉ đọc và ghi tệp".
ĐIỂM LỆCH SO VỚI BRIEF (nếu có) VÀ LÝ DO:
- Không có.
VIỆC CHƯA LÀM / CÂU HỎI:
- Cần Claude / chủ kho chạy bộ lệnh nghiệm thu:
  - uv run ruff check .
  - uv run ruff format --check app tests
  - uv run pytest -q -p no:cacheprovider tests/db/test_roles_sql.py tests/config/test_db_url_security.py
```

## Chi tiết các thay đổi đã thực hiện

1. **Gỡ phần phân công (`nghiep_vu.phan_cong`, T86 hoãn):**
   - `db/roles.sql`: xoá khối `DO $$ ... to_regclass('nghiep_vu.phan_cong') ... $$;` và chú thích đi kèm.
   - `.env.app.example`: xoá 4 dòng `CASE_SCOPE=phan_cong`, `PHAN_CONG_PATH=` và 2 dòng chú thích của chúng.
   - `tests/db/test_roles_sql.py`: bỏ khẳng định `assert "to_regclass('nghiep_vu.phan_cong')" in sql_clean`.
   - `docs/van-hanh/tai-khoan-db.md`: bỏ ví dụ `nghiep_vu.phan_cong` ở mục 2 bước 1 (`1. Chạy db/schema.sql (nếu có bảng mới):`).

2. **Sửa lint & định dạng `tests/db/test_roles_sql.py`:**
   - Ngắt dòng khẳng định `REVOKE CREATE ON SCHEMA tri_thuc, nghiep_vu FROM vinmec_app, vinmec_loader;` (trước đây 101 ký tự, lỗi `E501`) thành khối `assert (...)` chuẩn `ruff format` (98 ký tự tại dòng giữa, dưới ngưỡng 100 ký tự, nháy kép).

3. **Bổ sung mục đầu sổ tay `docs/van-hanh/tai-khoan-db.md`:**
   - Thêm mục `## Trước khi kéo mã mới về EC2` ở đầu tệp (ngay sau đoạn giới thiệu) với 3 cảnh báo triển khai:
     - Tạo `.env.app` trước khi kéo mã và chạy `docker compose up` (có thể tạm chép từ `.env`, bỏ `SUPABASE_SERVICE_ROLE_KEY`, giữ `DATABASE_URL` cũ cho tới khi xong bước tài khoản DB).
     - Kiểm tra tệp `certs/rds-global-bundle.pem` tồn tại trước khi `up` bằng `test -f certs/rds-global-bundle.pem` để tránh Docker tạo nhầm thư mục cùng tên.
     - Liệt kê các tài khoản DB có quyền đăng nhập trước khi chạy `db/roles.sql` (`REVOKE ALL ON DATABASE … FROM PUBLIC`) bằng `SELECT rolname FROM pg_roles WHERE rolcanlogin;`.
