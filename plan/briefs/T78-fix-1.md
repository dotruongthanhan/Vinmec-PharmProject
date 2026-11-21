# T78-fix-1 – Trùng tên bảng `tri_thuc.tu_dien_hoat_chat` (T77) với từ điển D1

Agent: **agy Gemini 4 Hydrogen xhigh**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Chạy sau T78 (cùng sửa `db/schema.sql`).

## Lỗi (Claude review T77)

T77 tạo `tri_thuc.tu_dien_hoat_chat` và `tri_thuc.tu_dien_hoat_chat_nhan` trong `db/schema.sql` cho `data/kb/hoat_chat.json`. Tên `tri_thuc.tu_dien_hoat_chat` **đã dùng** trong `db/tu_dien.sql` (từ điển D1, cột khác hẳn: `phien_ban`, `rxcui`, `ma_atc text[]`…) và bảng D1 đó đang có trên Supabase. `CREATE TABLE IF NOT EXISTS` sẽ bỏ qua → `load bang-luat` ghi vào bảng sai cột.

## Sửa

- Đổi tên hai bảng của T77 thành `tri_thuc.danh_muc_hoat_chat_demo` và `tri_thuc.danh_muc_hoat_chat_demo_nhan` (hoặc tên khác **không trùng** bất kỳ bảng nào trong `db/schema.sql`, `db/tu_dien.sql`), ở mọi nơi: `db/schema.sql` (bảng, chỉ mục, REVOKE, khối `DO`, RLS), `app/db/bang_luat.py` và module đọc, test.
- Thêm test: tập tên bảng `CREATE TABLE` trong `db/schema.sql` và `db/tu_dien.sql` **không giao nhau**.

## Phạm vi

`db/schema.sql`, `app/db/bang_luat*.py`, `tests/db/`. Thêm mục "fix-1" vào `plan/reports/T78.md`.

## Bổ sung sau review T78 (Claude: 1.523 qua, 2 trượt)

1. `tests/api/test_contract.py::test_interface_field_sets_match_contract`: 4 mô hình mới (`KetLuanCounts`, `TomTatThamDinh`, `LanThamDinhLichSu`, `LichSuThamDinh`) không có trong hợp đồng mà test đọc. Chuyển mục T78 khỏi `plan/api-hop-dong-v1.md` sang tệp mới `plan/api-hop-dong-v1.7-lich-su-tham-dinh.md` (khối `interface` TypeScript đúng định dạng các tệp v1.4/v1.5 để `_parse_contract_interfaces` đọc được), và cho test đọc thêm tệp đó như các tệp bổ sung khác. Giữ `len(...) == 15` của v1.md.
2. `tests/api/test_review_results_db.py::test_rule_version_matches_between_file_and_db_meta`: `phien_ban_luat` khác nhau giữa chế độ tệp và DB (`a544…` ≠ `b830…`). Hai chế độ phải ra **cùng một** giá trị cho cùng bộ tệp luật: tính từ cùng nguồn (ví dụ sha256 của từng tệp, sắp theo `ma`, nối rồi băm; ở DB đọc `sha256_tep` trong `bang_luat_meta` theo cùng thứ tự). Sửa `compute_rule_version`, không sửa kỳ vọng của test.
3. `ruff format --check` báo 4 tệp lệch: định dạng lại.

Phạm vi thêm: `app/storage/review_results.py`, `app/api/schemas.py` (nếu cần), `plan/api-hop-dong-v1.md`, `plan/api-hop-dong-v1.7-lich-su-tham-dinh.md`, `tests/api/test_contract.py`, các tệp lệch định dạng.
