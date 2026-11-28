**TRẠNG THÁI: CHƯA XONG** — đã thực hiện các thay đổi và test theo brief, nhưng chưa đủ bằng chứng xác định nguyên nhân duy nhất của mã `[MA_n]` sót trong sáu câu chấm thực tế.

**FILE ĐÃ TẠO / SỬA:** Luồng nhà cung cấp và cấu hình LLM, luồng agent và hỏi đáp chung, prompt minh hoạ, các test tương ứng và [báo cáo fix-2](D:/create/Vinmec-PharmProject/plan/briefs/EVAL-GEMINI-fix-1-bao-cao.md).

**LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:** Ruff check và format check đều qua. Pytest chạy riêng từng thư mục: providers 79, config 44, llm 35, eval 29, agent 284, orchestration 86 — đều qua. Đã thay hàm `load_env_file` bằng hàm rỗng trước khi nạp pytest; không gọi hàm gốc hoặc đọc `.env`.

**ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO:** Đã tái hiện và xử lý một trường hợp thứ tự mã ca bị xen với định danh khác; test qua `AgenticAsker.ask_global` khôi phục được hai mã ca và giữ các định danh khác được che. Chưa xác nhận được đây là nguyên nhân của toàn bộ sáu câu trong lần chấm thật.

**VIỆC CHƯA LÀM:** Claude cần chạy lại bộ chấm 90 + 15 câu như brief giao. Tôi không chạy bộ chấm thật vì brief cấm mạng.