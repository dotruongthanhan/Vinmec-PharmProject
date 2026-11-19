# T79-fix-1 – Test lô DDInter dùng dữ liệu giả sai kiểu; định dạng

Agent: **agy Gemini 4 Hydrogen high**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.**

1. `tests/kb/test_store_from_db.py::test_interaction_store_pairs_splits_queries_into_batches_of_1000` trượt: dữ liệu giả của test đặt `ma_trang_cap_json` là `["P1"]` trong khi `PairRecord.ma_trang_cap` là danh sách số nguyên (`ValidationError` tại `app/kb/interactions/store.py:77`). Sửa **dữ liệu giả trong test** cho đúng kiểu như dữ liệu thật (ví dụ `[1]`); không sửa `store.py` / mô hình.
2. `ruff format --check` báo 4 tệp lệch: định dạng lại (chỉ khoảng trắng / xuống dòng). Các tệp: chạy theo danh sách mà các báo cáo T76–T79 đã đụng (`app/api/service.py` dòng ~200 biểu thức `has_db = (...)` là một ví dụ).

Phạm vi: chỉ tệp test trên và các tệp lệch định dạng. Thêm mục "fix-1" vào `plan/reports/T79.md`.
