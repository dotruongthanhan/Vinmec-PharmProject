# Báo cáo VZ1-fix-2

TRẠNG THÁI: XONG trong phạm vi brief.

- Cập nhật kỹ năng: hình chỉ tồn tại trong lượt tạo, cần vẽ lại nếu lượt hiện tại cần hình; không vẽ trùng trong cùng lượt; không đưa mã hình hoặc bộ dữ liệu vào chữ trả lời.
- Khi dựng prompt, thay `mh-` kèm chữ số trong lịch sử của trợ lý bằng `hình (không còn hiển thị)`; không thay lịch sử gốc hay lời người dùng.
- Thêm test đọc kỹ năng và test LLM giả kiểm tra prompt, vai trò và lịch sử gốc.
- Không có bước làm sạch chữ trả lời sẵn trong luồng tác tử để bổ sung quy tắc mục 3. Theo brief, không thêm bước mới vào luồng kiểm chứng. Vì vậy việc ngăn mã trong câu trả lời chỉ dựa trên chỉ dẫn prompt, không được bảo đảm bằng bước xử lý đầu ra.

## Kiểm tra

- `uv run ruff check app tests`: đạt.
- `uv run ruff format --check app tests/agent`: đạt, 236 tệp đúng định dạng.
- `uv run pytest -q -p no:cacheprovider <từng tệp> --basetemp <thư mục riêng trong %TEMP%>` cho toàn bộ `tests/agent` và `tests/orchestration`: đạt lần lượt 231 và 84 test. Chạy lại `tests/agent/test_minh_hoa_do_thi.py` sau sửa prompt: 21 test đạt.
- Các lệnh dùng `UV_OFFLINE=1`, `UV_NO_SYNC=1`, và cache uv trong `%TEMP%`. Lần đầu uv không truy cập được cache mặc định; đã đổi cache sang `%TEMP%`. Lượt orchestration đầu dùng nhầm đường dẫn `testS`, gây `ModuleNotFoundError: No module named 'testS'`; đã dừng và chạy lại đầy đủ với `tests` đúng.
- Không chạy DeepSeek thật do yêu cầu không dùng mạng; bước nghiệm thu hai lượt này do Claude thực hiện theo brief.
