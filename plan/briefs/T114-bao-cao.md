# Báo cáo T114

TRẠNG THÁI: XONG

## File đã tạo / sửa

- Tạo `app/calc/hien_thi.py`: bảng công thức hiển thị cho bảy công thức.
- Sửa `app/calc/__init__.py`: xuất bảng công thức.
- Sửa `app/llm/case_context.py`: hiển thị công thức của chỉ số tính được và thêm các số trong công thức đó vào danh sách số được phép.
- Sửa `app/agent/tools/tinh_chi_so.py`: đưa công thức vào nội dung căn cứ của công cụ.
- Tạo `tests/calc/test_hien_thi.py` và sửa `tests/agent/test_tool_tinh_chi_so.py`: kiểm tra công thức, hằng số, gói ca và căn cứ công cụ, kể cả chặn số 3700.

## Lệnh đã chạy và kết quả

Chạy `uv` ngoại tuyến với `UV_NO_SYNC=1`, `UV_OFFLINE=1` và cache riêng trong thư mục tạm; không cài thư viện.

- `uv run ruff check app tests`: đạt, `All checks passed!`.
- `uv run ruff format --check app tests`: đạt, `388 files already formatted`.
- `uv run pytest -q -p no:cacheprovider tests/calc tests/llm tests/agent tests/orchestration`: lượt đầu 306 đạt, 12 lỗi khởi tạo vì `PermissionError: [WinError 5] Access is denied` tại thư mục tạm mặc định của pytest. Chạy lại với `TEMP` và `TMP` trỏ tới thư mục tạm riêng: **318 passed in 58.54s**.
- Test mới được chạy trước khi thêm bảng công thức: thất bại dự kiến do `app.calc` chưa có `CONG_THUC_HIEN_THI`.

## Điểm lệch và việc chưa làm

- Người dùng cho phép chạy shell và tự nghiệm thu, thay cho phân công trong brief không gọi shell và để Claude chạy nghiệm thu.
- Chưa chạy lại `HD-CA-011` với LLM thật: brief giao bước này cho Claude và yêu cầu của người dùng cấm gọi mạng.
- Không sửa hàm tính hay bộ kiểm chứng; không cài gói, gọi mạng hoặc commit.
