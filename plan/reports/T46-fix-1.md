**TRẠNG THÁI: XONG**

**FILE ĐÃ TẠO / SỬA:** [service.py](/D:/create/Vinmec-PharmProject/app/api/service.py:214), [read_pool.py](/D:/create/Vinmec-PharmProject/app/db/read_pool.py:40), [test_case_source.py](/D:/create/Vinmec-PharmProject/tests/api/test_case_source.py:159), [test_read_pool.py](/D:/create/Vinmec-PharmProject/tests/db/test_read_pool.py:45) và [báo cáo T46-fix-1](/D:/create/Vinmec-PharmProject/plan/reports/T46-fix-1.md).

**KẾT QUẢ:** Khi làm mới lỗi, API giữ dữ liệu cũ và `lam_moi_luc`, trả HTTP 200 rồi cho phép thử lại sau 15 giây. Lỗi ở lần nạp đầu vẫn trả HTTP 503. Yêu cầu mở chi tiết ca có thể hoàn tất trong lúc yêu cầu khác đang làm mới. Pool thay kết nối rảnh bị lỗi đúng một lần ở bước mở giao dịch và giữ nguyên cách trả lỗi truy vấn cho bên gọi.

**LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:**

- `uv run ruff check .` — đạt.
- `uv run ruff format --check` trên 5 tệp đã sửa — đạt.
- `uv run pytest -q --basetemp=.pytest_t46f` — **980 test đạt** trong 54,32 giây.

**ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO:** Không có lệch về chức năng. Cache mặc định của `uv` bị từ chối truy cập, nên các lệnh nghiệm thu chạy ngoại tuyến với `.venv` có sẵn. Đã dọn toàn bộ thư mục `.pytest_t46f*`.

**VIỆC CHƯA LÀM / CÂU HỎI:** Không có.