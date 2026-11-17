TRẠNG THÁI: CHƯA XONG

FILE ĐÃ TẠO / SỬA: Không. Không commit, không push.

LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:

- `uv run ruff check tests/kb tests/db --exclude tests/kb/.tmp --exclude tests/db/.tmp` → `All checks passed!`
- `uv run ruff format --check tests/kb tests/db --exclude tests/kb/.tmp --exclude tests/db/.tmp` → `12 files already formatted`
- Lệnh pytest toàn kho đúng brief → **`9 failed, 695 passed, 1 warning`**. Tám test trong brief vẫn trượt; thêm `tests/kb/test_build.py::test_build_records_before_after_and_preserves_unchanged_ids`, với đầu ra `assert 0 == 30`.

Các lệnh chạy offline, tắt cache; pytest dùng thư mục tạm ngoài kho.

ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO:

Đã dừng theo điều kiện ở mục 2, dòng #3–#4. Tái hiện bằng phản hồi giả lập HTTP 200, `{"results": [null]}`, cả nguồn `openfda` và `ndc` đều trả:

```text
trang_thai: loi_ket_noi
ly_do: Phản hồi openFDA có phần tử results không hợp lệ
```

Đây là lỗi cấu trúc phản hồi, nhưng [runner.py](/D:/create/Vinmec-PharmProject/app/kb/fetch/runner.py:323) gom vào lỗi kết nối. Đổi kỳ vọng test sẽ hợp thức hóa trạng thái sai nghĩa.

VIỆC CHƯA LÀM / CÂU HỎI:

Chưa sửa test vì đã gặp điều kiện dừng. Cần chốt cách phân loại phản hồi sai cấu trúc; lỗi bổ sung tại [test_build.py](/D:/create/Vinmec-PharmProject/tests/kb/test_build.py:358) cũng nằm ngoài phạm vi được sửa.