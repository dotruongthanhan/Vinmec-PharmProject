**TRẠNG THÁI: CHƯA XONG** — Đã triển khai T109, nhưng chưa chạy đủ hai lệnh pytest nghiệm thu vì chúng bao gồm các test ghi SQLite, trái với yêu cầu không ghi DB.

**FILE ĐÃ TẠO / SỬA:** Đã tạo [tinh_chi_so.py](/D:/create/Vinmec-PharmProject/app/agent/tools/tinh_chi_so.py), [test_tool_tinh_chi_so.py](/D:/create/Vinmec-PharmProject/tests/agent/test_tool_tinh_chi_so.py) và [báo cáo T109](/D:/create/Vinmec-PharmProject/plan/briefs/T109-bao-cao.md). Đã cập nhật đăng ký tool, chính sách quyền, prompt và kiểm chứng trích dẫn trong các tệp brief cho phép. Không sửa `tra_thuoc.py`.

**LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:**

- Ruff check và format check: đạt.
- Test riêng T109: **14 passed**.
- Test `agent`, `orchestration`, `calc`: **244 passed** khi chạy với thư mục tạm riêng. Lần đầu có 10 lỗi thiết lập do bị từ chối quyền truy cập thư mục pytest mặc định; chi tiết nằm trong báo cáo.

**ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO:** Chưa chạy hai lệnh pytest có `tests/api` và toàn bộ kho vì có test ghi DB giả lập.

**VIỆC CHƯA LÀM / CÂU HỎI:** Cần chạy hai lệnh nghiệm thu còn lại trong môi trường được phép ghi DB giả lập. Chưa thử LLM thật vì yêu cầu cấm gọi mạng.