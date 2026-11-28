# FIX-CI-VA-HINH-TRUNG-fix-1 – `roles.sql` và SQL cho RDS không khớp chính sách SELECT trên bảng vết

Người làm: Codex `gpt-6.1-terra` high. Đọc `plan/briefs/FIX-CI-VA-HINH-TRUNG.md`, `plan/briefs/FIX-CI-VA-HINH-TRUNG-bao-cao.md`, `db/roles.sql`, `tests/db/test_roles_sql.py`, `app/tracing/sink_db.py`.

## Claude review

- `db/roles.sql` bật `ROW LEVEL SECURITY` cho `nghiep_vu.vet_chay`, `vet_buoc`, nhưng chỉ có chính sách INSERT và DELETE, **không có SELECT**.
- SQL cho RDS trong báo cáo lại có `bvienx_app_doc … FOR SELECT`. Hai nơi không khớp.
- Khi RLS bật mà thiếu chính sách SELECT, câu `DELETE … WHERE bat_dau < …` của `_don_vet_db` không thấy dòng nào, nên xoá 0 dòng (Postgres áp chính sách SELECT cho mệnh đề WHERE của DELETE). API admin đọc vết về sau (TR2b) cũng hỏng.
- Test được thêm ngoại lệ `("DELETE","nghiep_vu.vet_buoc")` vào tập so sánh, chấp nhận được nếu có lý do.

## Yêu cầu

1. `db/roles.sql`: thêm chính sách `FOR SELECT TO bvienx_app USING (true)` cho hai bảng vết, đúng như SQL trong báo cáo. `roles.sql` và SQL cho RDS phải **giống hệt** về tập chính sách.
2. `tests/db/test_roles_sql.py`: test phải chấp nhận chính sách SELECT cho bảng có RLS mà app đọc, và vẫn bắt lỗi "grant ghi không có chính sách". Thêm một kiểm: mọi bảng có `ENABLE ROW LEVEL SECURITY` mà `bvienx_app` có quyền SELECT thì phải có chính sách SELECT cho `bvienx_app`. Viết sao cho test **không** nới các kiểm cũ.
3. Thêm test (không DB) cho `sink_db`: câu SQL dọn vết dùng `WHERE`. Chỉ cần comment hoặc tài liệu kèm test chứng minh lý do cần chính sách SELECT; không cần DB thật.
4. Cập nhật mục "SQL cho RDS" trong báo cáo cho khớp `roles.sql` (một khối có thể chạy lại, trong `BEGIN … COMMIT`).

## Tệp

`db/roles.sql`, `tests/db/test_roles_sql.py`, `tests/tracing/**` (nếu thêm test), báo cáo. **Cấm:** như brief gốc.

## Nghiệm thu

```
PYTHON_DOTENV_DISABLED=1 uv run pytest -q -p no:cacheprovider tests/db tests/tracing
```
