**TRẠNG THÁI: CHƯA XONG** — phần triển khai Lượt 2 đã được thực hiện, nhưng còn một giới hạn kiểm chứng và một test không thể chạy theo ràng buộc của bạn.

**FILE ĐÃ TẠO / SỬA:** Phần hỏi đáp, agent, tracer, prompt và test liên quan đã được cập nhật. Báo cáo đối chiếu yêu cầu 1–11 ở [TRA-LOI-TU-NHIEN-bao-cao.md](D:/create/Vinmec-PharmProject/plan/briefs/TRA-LOI-TU-NHIEN-bao-cao.md).

**LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:**

- Ruff kiểm tra mã và định dạng: đạt.
- `tests/orchestration`: 93 đạt; sau khi bổ sung test truy xuất chung, chạy riêng tệp test mới: 8 đạt.
- `tests/agent`: 291 đạt, **1 bỏ qua**.
- `tests/eval`: 29 đạt. `tests/verify`: 18 đạt.
- Không chạy `tests/api` theo chỉ dẫn Lượt 2. Không đọc `.env`, không gọi `load_env_file()`.

**ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO:** Lượt trả lời trung thực ở chế độ hỏi chung dùng các hàm kiểm số và trích dẫn hiện có cùng kiểm tra mã nguồn riêng; chưa gọi trực tiếp `kiem_chung_tra_loi`, vì hàm đó cần một ca cụ thể. Test agent bị bỏ qua vì test nhập `app.api.main`, nơi tự gọi `load_env_file()`.

**VIỆC CHƯA LÀM:** Chưa rà các cụm đáp án cũ trong gold và chưa nghiệm thu lại phần Lượt 1; báo cáo ghi rõ trạng thái từng yêu cầu.

Lệnh dọn các thư mục tạm do pytest tạo đã bị chính sách môi trường từ chối, nên các thư mục đó vẫn còn trong workspace.