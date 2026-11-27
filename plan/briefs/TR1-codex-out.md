**TRẠNG THÁI: CHƯA XONG**

**FILE ĐÃ TẠO / SỬA:** Hoàn thiện [app/tracing/](D:/create/Vinmec-PharmProject/app/tracing), các điểm móc tracer trong `app/`, cấu hình `config/settings*.yaml`, [tests/tracing/](D:/create/Vinmec-PharmProject/tests/tracing), test hợp đồng API và [báo cáo TR1](D:/create/Vinmec-PharmProject/plan/briefs/TR1-bao-cao.md). Các thay đổi T108–T114 được giữ nguyên.

**LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:** Ruff check và format check đạt. Test tracer: **14 đạt**; agent: **149 đạt**; orchestration: **83 đạt**; eval: **21 đạt**. Các thư mục còn lại được chạy tuần tự; kết quả chi tiết có trong báo cáo. Test hiệu năng chỉ mục tra cứu vẫn trượt khi chạy lại: **3,540 giây**, so với ngưỡng **3 giây**.

**ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO:** Gọi `AgenticAsker` trực tiếp khi chưa có vết bên ngoài chưa tự mở vết; phần này cần sửa `app/agent/asker.py`, ngoài phạm vi brief cho phép. Nhánh rà AI hiện chỉ ghi siêu dữ liệu vì chưa cung cấp phiên che định danh cho tracer.

**VIỆC CHƯA LÀM / CÂU HỎI:** Chưa đo p95 của 50 lượt agent và chưa chạy hai câu DeepSeek thật vì yêu cầu cấm mạng. Log `ask rejected ... reason=` hiện có cũng cần áp dụng quy tắc che số dài trong một đợt khác; tôi giữ nguyên log theo brief.

Hệ thống tự động chặn lệnh dọn các thư mục tạm `.tmp-*` do pytest tạo trong `tests/tracing/`; công cụ không nêu lý do chi tiết. Các thư mục này vẫn còn để chủ kho tự dọn.