# Báo cáo VZ1a-3

## Trạng thái: XONG

1. Đăng ký `VeBieuDo` trong container; kiểm thử xác nhận `duoc_si_ls` được phép gọi ở chế độ ca.
2. Bộ kiểm chuẩn hoá NFKC khi kiểm tra chữ; từ chối token số tự do trong chữ hiển thị, `www.`, các mẫu chèn lệnh không dấu và thẻ vai trò. Bổ sung năm ca từ brief, kiểm tra mã chữ-số và chạy lại ba mẫu VZ0.
3. Sau kiểm chứng đạt và trạng thái `ok`, chuyển khối của Gateway vào `AskResult` và API chế độ ca agentic. Bỏ hình đã tạo trước lần kiểm chứng trượt; lần sửa chỉ có hình được tạo lại. Quét JSON từng khối bằng phiên che định danh, bỏ toàn khối và ghi lý do vào vết nếu có định danh hoặc lỗi che. Không ghi hình vào lịch sử; chế độ chung và engine cố định trả danh sách rỗng.
4. Bổ sung kỹ năng vẽ, chỉ nạp khi tool được phép; ba ví dụ JSON được kiểm thử với các bộ dữ liệu và mã căn cứ phù hợp.
5. Kiểm thử đồ thị với LLM giả gọi lần lượt tính chỉ số, tra thuốc và vẽ; đối chiếu lưới CrCl bằng công thức viết tay, kiểm thử hai lần kiểm chứng, canary họ tên và điện thoại giả, và POST API với LLM giả. Kiểm thử engine cố định và lịch sử.

## Tệp tạo hoặc sửa trong lượt này

- `app/container.py`, `app/agent/minh_hoa/kiem.py`, `app/agent/tools/gateway.py`, `app/agent/nodes.py`, `app/api/service.py`.
- `config/prompts/ky_nang_minh_hoa.v1.md`.
- `tests/agent/test_minh_hoa_kiem.py`, `tests/agent/test_minh_hoa_do_thi.py`, `tests/agent/test_service_engine.py`.
- `plan/briefs/VZ1a-3-bao-cao.md`.

Các thay đổi đã có trước trong cây làm việc được giữ lại.

## Lệnh và kết quả

- `uv run --no-sync ruff check app tests tools`: đạt.
- `uv run --no-sync ruff format --check app tests tools`: đạt, 452 tệp đúng định dạng.
- Chạy lần lượt từng tệp `test_*.py` trong `tests/agent`, `tests/orchestration`, `tests/tracing`, `tests/eval`, `tests/api` bằng `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider <tệp> --basetemp <thư mục riêng trong %TEMP%>`: 49 tệp, không tệp nào thất bại; hai kiểm thử DB được đánh dấu bỏ qua.
- Sau khi tăng cường canary, chạy lại `uv run --no-sync pytest -q -p no:cacheprovider tests/agent/test_minh_hoa_do_thi.py --basetemp <thư mục trong %TEMP%>`: 10 đạt.
- `UV_OFFLINE=1`, cache uv chuyển vào `%TEMP%`. Lần đầu chạy `uv run --no-sync pytest` với cache uv mặc định bị từ chối quyền truy cập; chạy bằng Python trong `.venv`, sau đó xác nhận lại uv với cache trong `%TEMP%`.

## Điểm lệch và việc còn lại

- Không chạy DeepSeek hay kiểm thử DEMO-02 qua API ngoài vì brief giao bước đó cho Claude và cấm mạng. Không cài gói, không commit.
