# T25-fix-3 – phân loại phản hồi sai cấu trúc và dọn 8 test trượt

Thay cho `T25-fix-2.md` (agent đã dừng đúng điều kiện dừng, chưa sửa gì). Đọc `T25-fix-2.md` trước: bảng 8 test ở mục 2 của nó vẫn dùng, trừ dòng #3–#4 được chốt lại dưới đây.

## 1. Quyết định của người review

Phản hồi HTTP 200 nhưng sai cấu trúc (ví dụ `{"results": [null]}`, thiếu `results`, phần tử không phải đối tượng) **không phải lỗi kết nối**. Chốt:

- Thêm kết cục thứ tư `phan_hoi_sai_cau_truc`, kèm `ly_do` nêu cụ thể.
- `loi_ket_noi` chỉ dùng cho lỗi mạng, hết thời gian chờ, HTTP 5xx / 429 sau khi đã thử lại.
- `khong_tim_thay` và `khong_co_ung_vien_hop_le` giữ nguyên nghĩa của T25-fix-1.
- Mã thoát: `phan_hoi_sai_cau_truc` dùng chung mã thoát với `loi_ket_noi` (cả hai đều là "chưa lấy được, cần chạy lại"); không thêm mã thoát mới.
- Báo cáo độ phủ (`report`) hiển thị kết cục mới thành một dòng riêng.
- Hoạt chất gặp kết cục này thì vẫn chạy tiếp hoạt chất kế, không ghi đè tệp nguồn cũ.

## 2. Phạm vi file

Được sửa:

- `app/kb/fetch/runner.py`, `app/kb/fetch/report.py`, `app/kb/fetch/__main__.py`, `app/kb/fetch/client.py` (chỉ phần liên quan phân loại trên).
- `tests/kb/test_fetch.py`, `tests/kb/test_openfda_fetch.py`, `tests/kb/test_names.py`, `tests/kb/test_openfda_source.py`, `tests/db/test_mapping.py`.
- `data/kb_sources/README.md`: chỉ thêm một dòng mô tả kết cục mới ở mục nói về mã thoát.

Cấm đụng: phần còn lại của `app/`, toàn bộ `web/` (một phiên agent khác đang sửa), `data/` (trừ dòng README trên), `config/`, `db/`, `plan/`. Không tạo, không xoá thư mục `.tmp` trong kho.

## 3. Yêu cầu

- Sửa 8 test theo bảng mục 2 của `T25-fix-2.md`; riêng #3–#4 mong đợi `phan_hoi_sai_cau_truc`.
- Thêm test mới cho kết cục thứ tư: cả nguồn `openfda` và `ndc`, kiểm `ly_do`, mã thoát, và việc tệp nguồn cũ không bị ghi đè.
- Không xoá test, không `skip` / `xfail`, không nới điều kiện kiểm.
- `tests/kb/test_build.py::test_build_records_before_after_and_preserves_unchanged_ids`: lần chạy trước của agent báo trượt (`assert 0 == 30`), người review chạy ngoài hộp cát thì **qua**. Nếu vẫn trượt trong môi trường của bạn, ghi nguyên nhân vào báo cáo, không sửa.
- Không cần mạng. Không gọi openFDA thật.

## 4. Nghiệm thu

```bash
uv run ruff check app/kb tests/kb tests/db --exclude tests/kb/.tmp --exclude tests/db/.tmp
uv run ruff format --check app/kb tests/kb tests/db --exclude tests/kb/.tmp --exclude tests/db/.tmp
uv run pytest -q -p no:cacheprovider --ignore tests/db/.tmp --ignore tests/kb/.tmp --ignore tests/architecture/.tmp --ignore tests/api/.tmp
```

Đích: 0 test trượt (ngoài hộp cát), số test lớn hơn 704.

## 5. Cấm làm

Không commit, không push. Không in giá trị trong `.env`. Trả lời theo mẫu trong `AGENTS.md`.
