# Báo cáo VZ1a-3-fix-1

- Đã chặn số bắt đầu token, kể cả số dính đơn vị sau chuẩn hoá NFKC; vẫn cho phép mã bắt đầu bằng chữ.
- Đã thêm kiểm thử số dính đơn vị, chữ số toàn độ rộng và các mã được phép. Kiểm thử hiện có xác nhận ba mẫu VZ0 và các ví dụ trong prompt.
- Trước khi sửa, kiểm thử mới cho thấy 5 trường hợp lọt qua, 2 trường hợp đã bị chặn.
- Nghiệm thu offline với `uv run --offline --no-sync`: `ruff check app tests/agent` đạt; `ruff format --check app tests/agent` đạt (236 tệp); pytest hai tệp brief chỉ định đạt 46 kiểm thử, dùng `--basetemp` trong `%TEMP%`.
- Lần chạy đầu không khởi tạo được cache uv mặc định do bị từ chối quyền; đã đặt `UV_CACHE_DIR` trong `%TEMP%` để chạy lại. Không cài gói, không dùng mạng.
- Không có việc chưa làm.
