# Báo cáo thực hiện T87-fix-2 – Bổ sung policy RLS trong `db/roles.sql`, kiểm Docker và test tĩnh

```text
TRẠNG THÁI: CHƯA XONG (đã sửa đủ 3 tệp theo brief; chưa chạy ruff/pytest/Docker do ràng buộc không gọi shell/mạng/DB/MCP)
FILE ĐÃ TẠO / SỬA:
- Sửa: db/roles.sql
- Sửa: docs/van-hanh/tai-khoan-db.md
- Sửa: tests/db/test_roles_sql.py
- Tạo mới: plan/reports/T87-fix-2.md
LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:
- Không chạy lệnh shell nào theo đúng ràng buộc "KHÔNG gọi shell, không gọi mạng, không kết nối DB, không gọi MCP; chỉ đọc và ghi tệp".
ĐIỂM LỆCH SO VỚI BRIEF (nếu có) VÀ LÝ DO:
- Không có.
VIỆC CHƯA LÀM / CÂU HỎI:
- Cần Claude / chủ kho chạy kiểm tra tĩnh và kiểm tra Docker thực tế theo mục 6 của brief:
  - uv run ruff check .
  - uv run ruff format --check app tests
  - uv run pytest -q -p no:cacheprovider tests/db/test_roles_sql.py tests/config/test_db_url_security.py
  - Chạy lại toàn bộ kiểm Docker trên pgvector/pgvector:pg17: vinmec_app thấy cùng số dòng với chủ bảng, ghi được hội thoại/phản hồi/kết quả, bị từ chối các lệnh nguy hiểm; vinmec_loader nạp được load cases, hanh-chinh, phieu-dieu-tri.
```

## 1. Chi tiết thay đổi

1. **`db/roles.sql`:**
   - Thêm chú thích đầu tệp nhắc khi thêm bảng mới vào `db/schema.sql` cần chạy lại `db/roles.sql` để cấp `GRANT` và tạo policy RLS (`ALTER DEFAULT PRIVILEGES` không tự tạo policy).
   - Thêm khối `DO $$ ... $$` duyệt `pg_tables` với `schemaname IN ('tri_thuc', 'nghiep_vu')`, chạy `DROP POLICY IF EXISTS` trước khi `CREATE POLICY` để chạy lại nhiều lần không lỗi:
     - `vinmec_app_doc`: `FOR SELECT TO vinmec_app USING (true)` trên **mọi** bảng thuộc `tri_thuc` và `nghiep_vu`.
     - `vinmec_loader_nap`: `FOR ALL TO vinmec_loader USING (true) WITH CHECK (true)` trên mọi bảng `tri_thuc` và đúng 20 bảng `nghiep_vu` đã cấp `GRANT` cho `vinmec_loader` (`nguoi_benh` đến `can_cu`, khớp danh sách dòng 87–106).
   - Thêm các cặp `DROP POLICY IF EXISTS` + `CREATE POLICY` cho phần ghi của `vinmec_app` khớp đúng `GRANT` đã có:
     - `nghiep_vu.phan_hoi`: `vinmec_app_them` (`FOR INSERT ... WITH CHECK (true)`) và `vinmec_app_cap_nhat` (`FOR UPDATE ... USING (true) WITH CHECK (true)`).
     - `nghiep_vu.hoi_thoai`: `vinmec_app_them` (`FOR INSERT ... WITH CHECK (true)`) và `vinmec_app_xoa` (`FOR DELETE ... USING (true)`).
     - `nghiep_vu.ket_qua_tham_dinh` và `nghiep_vu.ket_qua_nhan_dinh`: `vinmec_app_them` (`FOR INSERT ... WITH CHECK (true)`).
   - Giữ nguyên RLS trên tất cả bảng; không dùng `BYPASSRLS`, không tạo policy cho `PUBLIC`/`anon`/`authenticated`.

2. **`docs/van-hanh/tai-khoan-db.md`:**
   - Mục `## 4. Kiểm tra sau chuyển đổi` (bước 3): bổ sung lệnh `SELECT count(*) FROM nghiep_vu.dot_dieu_tri;` bằng `vinmec_app` với yêu cầu bắt buộc **> 0** (trả về `0` là dấu hiệu thiếu policy RLS, khắc phục bằng cách chạy lại `db/roles.sql`, không đổi `DATABASE_URL` về tài khoản chủ).
   - Thêm mục `## 7. Thử trước trên máy local bằng Docker` với đầy đủ các bước: container `pgvector/pgvector:pg17` chỉ nghe `127.0.0.1`, chạy `uv run python -m app.db schema` bằng tài khoản chủ (kèm `PYTHON_DOTENV_DISABLED=1`), chạy `psql ... -f db/roles.sql` hai lần liên tiếp, đặt mật khẩu tạm bằng `\password` với ví dụ `<mật-khẩu-tạm>`, nạp `load cases` (và tuỳ chọn `hanh-chinh`, `phieu-dieu-tri`) qua `DATABASE_URL_LOADER`, đếm dòng bằng `vinmec_app` và dọn container.

3. **`tests/db/test_roles_sql.py`:**
   - Thêm `_extract_loader_nghiep_vu_grant_tables`, `_extract_direct_policies` và test tĩnh `test_roles_sql_has_rls_policies_matching_grants` kiểm tra:
     - Mọi `(thao tác, bảng)` ghi của `vinmec_app` đã có `GRANT` (khớp `_extract_api_writes()`) đều có `DROP POLICY IF EXISTS` + `CREATE POLICY` tương ứng `TO vinmec_app` với đúng điều kiện `USING` / `WITH CHECK` cho `INSERT`/`UPDATE`/`DELETE`, và không có policy ghi thừa ngoài danh sách GRANT.
     - Khối `DO $$` duyệt `pg_tables` cho `('tri_thuc', 'nghiep_vu')` tạo `vinmec_app_doc` (`FOR SELECT TO vinmec_app`) và `vinmec_loader_nap` (`FOR ALL TO vinmec_loader`) trên `tri_thuc` cùng đúng tập 20 bảng `nghiep_vu` đã cấp GRANT cho `vinmec_loader`.
     - Mọi tên policy có tiền tố `vinmec_app_` hoặc `vinmec_loader_`.
     - Không có `BYPASSRLS`, không có `DISABLE ROW LEVEL SECURITY`, không có `CREATE POLICY ... TO public|anon|authenticated`.

## 2. Kết quả kiểm tra phần sequence trong `db/schema.sql`

- Đã đọc toàn bộ phần lược đồ `nghiep_vu` trong `db/schema.sql` (24 bảng tại dòng 30–438).
- Bảng duy nhất trong `nghiep_vu` có cột `bigserial`/sequence là `nghiep_vu.hoi_thoai` (`id bigserial PRIMARY KEY` ở `db/schema.sql:372`, sequence `nghiep_vu.hoi_thoai_id_seq`). Đây là bảng lưu hội thoại runtime của API (đã cấp `USAGE, SELECT` trên sequence cho `vinmec_app` tại `db/roles.sql:73`), **không** nằm trong các bảng `vinmec_loader` nạp.
- Toàn bộ 20 bảng `nghiep_vu` mà `vinmec_loader` nạp (`nguoi_benh`, `dot_dieu_tri`, `di_ung`, `thuoc`, `thuoc_hoat_chat`, `chan_doan`, `sinh_hieu`, `ket_qua_xet_nghiem`, `vi_sinh`, `khang_sinh_do`, `dien_bien`, `y_lenh`, `phieu_dieu_tri`, `phieu_y_lenh`, `chi_tiet_y_lenh`, `lich_dung`, `lan_tham_dinh`, `nhan_dinh`, `nhan_dinh_thuoc`, `can_cu`) đều dùng khoá chính `text` hoặc khoá kép, không có cột `serial`/`bigserial`/`IDENTITY`.
- **Quyết định:** giữ nguyên phần sequence hiện tại (chỉ cấp `USAGE, SELECT, UPDATE` trên sequence `tri_thuc` cho `vinmec_loader`), không mở thêm quyền sequence trên `nghiep_vu` cho `vinmec_loader`.

## 3. Ghi chú thêm cho lần chạy Docker nghiệm thu

- `db/roles.sql:50-52` thực hiện `REVOKE ALL ON DATABASE ... FROM PUBLIC` rồi chỉ cấp `CONNECT` cho `vinmec_loader` (chưa cấp `TEMP` trên database). Hiện mục 6 chỉ yêu cầu `load cases`, `hanh-chinh`, `phieu-dieu-tri` (không dùng bảng tạm), nhưng nếu sau này chạy `load ddinter` bằng `vinmec_loader` (`app/db/engine.py:105` dùng `CREATE TEMP TABLE ...`), cần lưu ý kiểm tra quyền `TEMP` trên database khi chạy thật.
