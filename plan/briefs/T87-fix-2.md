# T87-fix-2 – `roles.sql` thiếu policy RLS: `vinmec_app` đọc ra 0 dòng, `vinmec_loader` không nạp được

Agent: agy `gemini-4-hydrogen-xhigh`. **Không gọi shell, không gọi mạng, không kết nối DB, không gọi MCP; chỉ đọc và ghi tệp.**

## 1. Lỗi Claude phát hiện khi chạy thật

Claude dựng Postgres tạm (`pgvector/pgvector:pg17` trong Docker), chạy `db/schema.sql` bằng tài khoản chủ, chạy `db/roles.sql` hai lần (đều không lỗi), rồi:

| Kiểm | Kết quả |
| :-- | :-- |
| `vinmec_app`: DROP / INSERT `tri_thuc` / DELETE `y_lenh` / TRUNCATE / CREATE TABLE / CREATE ROLE | Đều bị từ chối ✅ |
| Chủ bảng nạp ca → `SELECT count(*) FROM nghiep_vu.dot_dieu_tri` | chủ thấy **93**, `vinmec_app` thấy **0** ❌ |
| `vinmec_app` `INSERT INTO nghiep_vu.hoi_thoai` | `new row violates row-level security policy` ❌ |
| `vinmec_loader` `load cases` | `InsufficientPrivilege` (RLS trên `tri_thuc.hoat_chat`, `nghiep_vu.phieu_dieu_tri`) ❌ |

Nguyên nhân: `db/schema.sql` dòng ~1061 trở đi `ENABLE ROW LEVEL SECURITY` cho **63/63** bảng `tri_thuc` + `nghiep_vu` (để chặn Data API Supabase), không có `CREATE POLICY` nào. Chủ bảng bỏ qua RLS; vai trò mới thì bị lọc hết dòng.

## 2. Sửa `db/roles.sql`

Thêm phần policy sau phần GRANT, chạy lại nhiều lần không lỗi (`DROP POLICY IF EXISTS` rồi `CREATE POLICY`, trong khối `DO $$` duyệt `pg_tables` của hai lược đồ). **Không** tắt RLS, **không** dùng `BYPASSRLS`, **không** tạo policy cho `PUBLIC`/`anon`/`authenticated`.

- `vinmec_app`, **mọi** bảng `tri_thuc` và `nghiep_vu`: `CREATE POLICY vinmec_app_doc ON <bảng> FOR SELECT TO vinmec_app USING (true)`.
- `vinmec_app`, đúng các bảng ghi (khớp GRANT đã có):
  - `nghiep_vu.phan_hoi`: `FOR INSERT … WITH CHECK (true)` và `FOR UPDATE … USING (true) WITH CHECK (true)` (vì `ON CONFLICT DO UPDATE`).
  - `nghiep_vu.hoi_thoai`: `FOR INSERT … WITH CHECK (true)`, `FOR DELETE … USING (true)`.
  - `nghiep_vu.ket_qua_tham_dinh`, `nghiep_vu.ket_qua_nhan_dinh`: `FOR INSERT … WITH CHECK (true)`.
- `vinmec_loader`: `FOR ALL TO vinmec_loader USING (true) WITH CHECK (true)` trên mọi bảng `tri_thuc` và đúng danh sách bảng `nghiep_vu` đã GRANT cho loader.
- Tên policy cố định, có tiền tố `vinmec_app_` / `vinmec_loader_`.
- Chú thích đầu tệp: bảng mới thêm vào `schema.sql` cần **chạy lại `roles.sql`** để có GRANT và policy (default privileges không tạo policy).
- Kiểm lại phần sequence: bảng `nghiep_vu` nào loader nạp mà có cột `bigserial`/identity thì loader cần `USAGE, SELECT, UPDATE` trên sequence đó (hiện chỉ cấp sequence `tri_thuc`). Đọc `db/schema.sql` để quyết định, ghi trong báo cáo.

## 3. Sửa `docs/van-hanh/tai-khoan-db.md`

- Mục kiểm sau chuyển đổi: thêm bước bắt buộc `SELECT count(*) FROM nghiep_vu.dot_dieu_tri;` bằng `vinmec_app` phải **> 0** (bằng 0 là thiếu policy RLS, không đổi `DATABASE_URL`).
- Thêm mục "Thử trước trên máy local bằng Docker" ghi các lệnh Claude đã dùng (container `pgvector/pgvector:pg17` nghe `127.0.0.1`, `python -m app.db schema` bằng tài khoản chủ, `psql -f db/roles.sql` hai lần, đặt mật khẩu tạm, `python -m app.db load cases` với `DATABASE_URL_LOADER`, đếm dòng bằng `vinmec_app`). Mật khẩu ví dụ dạng `<mật-khẩu-tạm>`.

## 4. Sửa `tests/db/test_roles_sql.py`

Thêm test tĩnh: với mỗi (thao tác, bảng) ghi của `vinmec_app` đã có GRANT thì phải có policy tương ứng `TO vinmec_app`; có policy `FOR SELECT TO vinmec_app`; có policy `FOR ALL TO vinmec_loader`; không có `BYPASSRLS`, không có `DISABLE ROW LEVEL SECURITY`, không có policy `TO public|anon|authenticated`.

## 5. Phạm vi

Chỉ: `db/roles.sql`, `docs/van-hanh/tai-khoan-db.md`, `tests/db/test_roles_sql.py`. Cấm `db/schema.sql` và mọi tệp khác.

## 6. Nghiệm thu

Claude chạy `ruff`, `pytest`, và **chạy lại toàn bộ kiểm Docker ở mục 1**: `vinmec_app` phải thấy cùng số dòng với chủ bảng, ghi được hội thoại/phản hồi/kết quả, vẫn bị từ chối mọi lệnh nguy hiểm; `vinmec_loader` nạp được `load cases`, `hanh-chinh`, `phieu-dieu-tri`.

Ghi `plan/reports/T87-fix-2.md` theo mẫu `AGENTS.md`.
