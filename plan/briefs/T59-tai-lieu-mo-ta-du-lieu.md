# T59 – Viết tệp mô tả cho từng bộ dữ liệu (`docs/du-lieu/`)

Mô hình: Codex `gpt-6.1-sol`, effort `xhigh`. Không có mạng.

Đọc: `AGENTS.md`, `docs/du-lieu/README.md` (quy tắc), **`docs/du-lieu/ddinter.md` (mẫu bắt buộc theo)**.

## Việc

Viết các tệp còn thiếu trong bảng danh mục của `docs/du-lieu/README.md`:
- `dav.md`
- `rxnav.md`
- `tu-dien-tra-cuu.md`
- `openfda-rag.md`
- `livertox.md`
- `lactmed.md`
- `van-ban-byt.md`
- `ca-gia-lap.md`

Mỗi tệp có cùng các mục như mẫu:
1. Bảng thông tin: nguồn, giấy phép, tầng, cách lấy, ngày lấy, lệnh.
2. Đơn vị dữ liệu: một dòng là gì.
3. Ba tầng tệp kèm kích thước.
4. **Từng trường** của từng tệp: ý nghĩa, app có dùng không (✅ / ❌), dùng ở đâu.
5. Bộ tra (nếu có): bảng, cột, số dòng.
6. Kết quả kiểm đã có.
7. Việc còn mở.

## Cách lấy thông tin

- **Đọc trực tiếp dữ liệu.** Mở dòng đầu, đếm dòng, liệt kê khoá; với SQLite thì đọc `PRAGMA table_info` và `count(*)`. Đọc thêm `manifest.json`.
- Đọc các báo cáo `plan/reports/T25*.md`, `T50.md` → `T56.md`, `T54-tai-nguon-van-ban.md`, và `data/kb_reports/*`.
- Đọc `data/kb_sources/README.md` (cũ, 16–17/11): **chỉ lấy phần còn đúng**, ghi rõ chỗ đã đổi.
- Xác định "app có dùng không" bằng cách tìm trong `app/`: tên trường, tên tệp, đường dẫn.
- Thư mục có hàng chục nghìn tệp thì **không** chạy `du` hay `find` trên cả thư mục (rất chậm). Đếm bằng `ls | wc -l` hoặc đọc manifest.
- Không in và không chép dữ liệu người bệnh. Dữ liệu ca đều là giả lập, nhưng vẫn chỉ mô tả cấu trúc, không dán nội dung ca.

## Phạm vi

- **Được tạo / sửa:** `docs/du-lieu/*.md`. Riêng `README.md` chỉ được đổi cột trạng thái thành "✅ cập nhật <ngày>".
- **Cấm:** sửa `data/**`, code, test; sửa `docs/du-lieu/ddinter.md`.

## Nghiệm thu

- Đủ 8 tệp.
- Mỗi con số (số dòng, kích thước) phải lấy từ lệnh đã chạy. Ghi lệnh ở cuối mỗi tệp, mục "Cách kiểm lại".

## Cấm làm

Không gọi mạng. Không commit. Không dùng `&`.
