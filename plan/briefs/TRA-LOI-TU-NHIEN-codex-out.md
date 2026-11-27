**TRẠNG THÁI: CHƯA XONG.** Phần cốt lõi của brief chưa được triển khai: lượt LLM trả lời trung thực, kiểm chứng và lọc câu chứa số, giới hạn lượt gọi, tracer và các test tương ứng cho cả hai engine.

**FILE ĐÃ TẠO / SỬA:**

- [Báo cáo thực hiện](D:/create/Vinmec-PharmProject/plan/briefs/TRA-LOI-TU-NHIEN-bao-cao.md)
- Bốn tool trong `app/agent/tools/`, hai prompt hiện có, nhãn và câu demo trên web, test cấu hình engine production.

**LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:**

- Ruff check và format check: đạt.
- Test theo từng thư mục: orchestration **86 đạt**; agent **283 đạt, 1 bỏ chọn**; eval **29 đạt**; verify **18 đạt**.
- Web: kiểm tra TypeScript đạt; **430 test đạt**; build đạt.
- Lượt test orchestration đầu gặp lỗi quyền thư mục tạm; chạy lại với thư mục tạm riêng đã đạt.

**ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO:** Chưa chạy `tests/api` và một test API trong thư mục agent vì chúng import `app.api.main`, nơi gọi `load_env_file()` khi import; bạn đã yêu cầu không gọi hàm này. Không mở `.env`, gọi mạng hay cài gói.

**VIỆC CHƯA LÀM:** Hoàn tất luồng trả lời và kiểm chứng theo brief, rà đầy đủ sáu tool, bổ sung test bao gồm canary PII, kiểm thử web thủ công và chấm lại 90 câu. Công việc hiện tại **chưa sẵn sàng triển khai**.