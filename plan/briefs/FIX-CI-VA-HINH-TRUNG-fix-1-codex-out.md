TRẠNG THÁI: **XONG**

FILE ĐÃ SỬA:

- [db/roles.sql](D:/create/Vinmec-PharmProject/db/roles.sql): thêm chính sách SELECT cho hai bảng vết.
- [tests/db/test_roles_sql.py](D:/create/Vinmec-PharmProject/tests/db/test_roles_sql.py): kiểm tra chính sách SELECT và giữ kiểm tra quyền ghi.
- [tests/tracing/test_sink_db.py](D:/create/Vinmec-PharmProject/tests/tracing/test_sink_db.py): kiểm tra câu dọn vết có điều kiện `WHERE`.
- [Báo cáo](D:/create/Vinmec-PharmProject/plan/briefs/FIX-CI-VA-HINH-TRUNG-bao-cao.md): xác nhận khối SQL cho RDS và ghi kết quả nghiệm thu.

LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:

- Lệnh pytest theo brief: **184 qua, 2 bỏ qua, 29 lỗi thiết lập** do `PermissionError` khi pytest dọn thư mục tạm cũ.
- Chạy lại cùng bộ test với `--basetemp` mới: **213 qua, 2 bỏ qua**.
- Ruff check và format check trên hai tệp test: **qua**.

ĐIỂM LỆCH SO VỚI BRIEF: Lượt pytest thành công dùng thêm `--basetemp`, chế độ offline và cache uv tạm do giới hạn quyền truy cập.

VIỆC CHƯA LÀM / CÂU HỎI: Không chạy SQL trên RDS, đúng phạm vi brief.