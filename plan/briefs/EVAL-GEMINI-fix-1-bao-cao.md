# Báo cáo EVAL-GEMINI-fix-1

## TRẠNG THÁI: CHƯA XONG

Đã thêm tham số cấu hình chờ (mặc định 0, cấu hình dev 70) và khả năng chờ có giới hạn, đồng hồ và hàm ngủ tiêm được trong KeyRouter. Test độc lập kiểm tra chờ 5 giây, trần 70 giây và hạn chót. Chưa nối được tham số chờ hoặc hạn chót vào lời gọi thực tế: app/llm/setup.py dựng ChatLLMClient, còn app/providers/http.py gọi router.chon() và đọc phản hồi 429; hai tệp này không nằm trong phạm vi được phép sửa. Vì vậy cấu hình dev 70 hiện chưa có tác dụng; retryDelay trong thân 429 cũng chưa được đọc, chưa có test 37 giây. Không dùng mẹo lách phạm vi. Cần mở rộng phạm vi cho hai tệp trên và đường truyền hạn chót tới lời gọi máy khách.

Đã thêm --nghi_giua_cau (0–120 giây), nghỉ giữa các câu, và báo cáo số trạng thái loi theo từng engine. AskResult không có ma_loi nên số này là toàn bộ lỗi thực thi, không thể khẳng định từng lỗi do nhà cung cấp. Đã tách tiêu chí con_ma_che khỏi ro_pii; mã ca HS-* và DEMO-* đúng mẫu không tính là rò ở chế độ chung, mã NB và họ tên vẫn tính. Mã che còn sót làm trượt tiêu chí hiển thị.

Luồng agentic chung chuyển sang CaseAsker.ask_global. Mã trước đó đã gọi restore_text với toàn bộ ánh xạ phiên, bao gồm cả họ tên; test hiện có xác nhận khôi phục mã ca. Chưa tái hiện được nguyên nhân chính xác các mã [MA_n] còn sót trong lần chấm thật. Nay chỉ khôi phục từ ánh xạ phiên với mã ca HS-* hoặc DEMO-* có trong danh sách ca được truyền, vì đó là mã ca giả lập được giao diện hiển thị; không khôi phục tên, số điện thoại, NB hoặc mã y lệnh. Test hai ca và canary tên đã qua. Mã tạm chưa có trong phiên vẫn giữ nguyên, được tiêu chí con_ma_che phát hiện.

## Kiểm tra

- Ruff check app tests tools: qua; ruff format --check app tools tests/providers tests/eval tests/agent tests/orchestration: qua.
- Pytest chạy riêng từng thư mục, -q -p no:cacheprovider: providers 76 qua; config 44 qua; eval 29 qua; agent 271 qua; orchestration 85 qua.
- Trước đó providers có một lỗi do mã hóa trong đoạn vừa sửa; đã sửa và chạy lại qua. Orchestration trước đó có một test cũ đòi khôi phục họ tên, đã cập nhật theo brief và chạy lại qua.
- Dùng uv --no-cache, UV_NO_SYNC=1 và PYTHON_DOTENV_DISABLED=1; thay hàm load_env_file bằng hàm rỗng trước khi pytest được nạp. Không đọc .env, không gọi hàm gốc, không mạng, không cài gói.
- Chưa chạy bộ chấm thật 90 + 15 câu: brief giao Claude chạy và cấm mạng.

## fix-2

Đã nối `cho_khoa_toi_da_giay` từ cấu hình qua `build_llm` đến bộ chọn khoá; đọc `retryDelay` trong JSON 429 và `Retry-After` dạng số. Số lần gọi HTTP vẫn có giới hạn. Hạn chót được đặt trong `ContextVar` tại hàm chạy công việc có hạn chót của đồ thị và luồng hỏi đáp cũ, trong chính luồng con gọi LLM; máy khách lấy giá trị này khi chọn khoá. Test `MockTransport` qua `build_llm` xác nhận tám khoá nghỉ 2 giây rồi thành công với đồng hồ giả, nghỉ 90 giây vượt trần 70 và hạn chót còn 1 giây đều lỗi ngay.

`AgenticAsker.ask_global` thực tế chuyển sang `CaseAsker.ask_global`, không đi qua đồ thị ca. Phiên che ở đó dùng chung cho tóm tắt và khôi phục, nhưng thứ tự cấp mã `MA` có thể xen mã ca, mã y lệnh và mã người bệnh, khiến câu mẫu dùng hai mã liên tiếp không nhất thiết chỉ hai ca. Nay cấp mã cho ca trong phạm vi trước các định danh khác; chỉ khôi phục mã ca HS-* hoặc DEMO-* trong danh sách ca; mã `MA` còn lại thay bằng `[đã che]`. Test qua `AgenticAsker.ask_global` tái hiện câu hai ca và kiểm tra định danh khác vẫn che. Đây là trường hợp đã tái hiện, chưa đủ bằng chứng khẳng định là nguyên nhân duy nhất của sáu câu trong lần chấm thật.

Đã bổ sung quy tắc prompt và nhận diện yêu cầu vẽ có ranh giới từ, loại các cụm loại trừ trong brief. Khi kế hoạch định kết thúc mà chưa có hình và còn lượt, đồ thị nhắc một lần; không có hình thì thông báo dự phòng. Test bao gồm nhận diện, nhắc rồi vẽ, nhắc nhưng không vẽ và câu không yêu cầu vẽ.

Kiểm tra sau sửa: ruff check và format --check đều qua; pytest chạy từng thư mục: providers 79, config 44, llm 35, eval 29, agent 284, orchestration 86 đều qua. Lượt providers đầu có 3 lỗi do tăng số lần thử lỗi kết nối và 401; đã sửa giới hạn rồi chạy lại thành công. Một lượt format --check báo một tệp test chưa đúng định dạng; đã format và chạy lại qua. Dùng `UV_NO_SYNC=1`, `PYTHON_DOTENV_DISABLED=1`, `uv run --no-cache`; thay `load_env_file` bằng hàm rỗng trước khi nạp pytest, không gọi hàm gốc, không đọc `.env`, không cài gói hay dùng mạng. Chưa chạy bộ chấm thật vì brief giao Claude chạy và cấm mạng.
