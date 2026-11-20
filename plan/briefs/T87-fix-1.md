# T87-fix-1 – Gỡ phần phân công (T86 hoãn), sửa lint, bổ sung cảnh báo triển khai

Agent: agy `gemini-4-hydrogen-high`. **Không gọi shell, không gọi mạng, không kết nối DB, không gọi MCP; chỉ đọc và ghi tệp.** Đọc `plan/briefs/T87-tai-khoan-db-rieng-cho-ung-dung.md` và `plan/reports/T87.md` để nắm bối cảnh.

T87 review: 1.607 test qua, `docker compose config -q` đạt, quyền ghi của `vinmec_app` khớp mã (Claude đã đối chiếu). Còn các điểm sau.

## Sửa

1. **T86 (phân quyền theo ca) đã hoãn**, không có bảng `nghiep_vu.phan_cong`:
   - `db/roles.sql`: xoá khối `DO $$ … to_regclass('nghiep_vu.phan_cong') … $$` và chú thích đi kèm.
   - `.env.app.example`: xoá 4 dòng `CASE_SCOPE`, `PHAN_CONG_PATH` và chú thích của chúng.
   - `tests/db/test_roles_sql.py`: bỏ khẳng định `to_regclass('nghiep_vu.phan_cong')`.
   - `docs/van-hanh/tai-khoan-db.md` dòng 35: bỏ ví dụ `nghiep_vu.phan_cong`.
2. **Lint:** `tests/db/test_roles_sql.py` dòng 132 dài 101 ký tự (E501) và tệp lệch `ruff format`. Ngắt dòng, định dạng đúng kiểu ruff (độ dài dòng 100, nháy kép).
3. **Sổ tay `docs/van-hanh/tai-khoan-db.md`** thêm mục "Trước khi kéo mã mới về EC2" đặt **đầu** tệp:
   - Mã mới dùng `env_file: .env.app`: kéo mã và `docker compose up` khi chưa có `.env.app` thì compose dừng với lỗi thiếu tệp. Tạo `.env.app` trước (có thể tạm chép từ `.env` hiện có rồi **bỏ** `SUPABASE_SERVICE_ROLE_KEY`, giữ `DATABASE_URL` cũ cho tới khi xong bước tài khoản).
   - Phải có tệp `certs/rds-global-bundle.pem` **trước** khi `up`: nếu thiếu, Docker tạo một **thư mục** cùng tên ở máy chủ và kết nối `verify-full` sẽ lỗi. Kiểm bằng `test -f certs/rds-global-bundle.pem`.
   - `roles.sql` chạy `REVOKE ALL ON DATABASE … FROM PUBLIC`: tài khoản DB khác (nếu có, ngoài tài khoản chủ, `vinmec_app`, `vinmec_loader`) sẽ mất quyền kết nối. Liệt kê trước bằng `SELECT rolname FROM pg_roles WHERE rolcanlogin;`.

## Phạm vi tệp

Chỉ 4 tệp: `db/roles.sql`, `.env.app.example`, `tests/db/test_roles_sql.py`, `docs/van-hanh/tai-khoan-db.md`. Cấm đụng tệp khác.

## Nghiệm thu (Claude chạy)

```
uv run ruff check .
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider tests/db/test_roles_sql.py tests/config/test_db_url_security.py
```

Ghi `plan/reports/T87-fix-1.md` theo mẫu `AGENTS.md`.
