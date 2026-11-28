# Báo cáo VZ1a-4

TRẠNG THÁI: CHƯA XONG

## Đã thực hiện

- Tách vòng chỉ vẽ khỏi số vòng công cụ thường, giới hạn ba vòng chỉ vẽ; sau hai lần Gateway từ chối, các lời gọi vẽ tiếp theo nhận `het_luot_ve`. Giữ hình hợp lệ đã tạo khi có lần vẽ sau bị từ chối.
- Bổ sung gợi ý mã căn cứ hợp lệ (tối đa mười mã), bộ dữ liệu và cột, hoặc tham chiếu ô tùy lý do từ chối. Vết của lời từ chối chỉ ghi mã lý do; sau khi có danh sách gợi ý, nội dung prompt và phản hồi LLM không được ghi vào vết để tránh chép danh sách đó.
- Sửa kỹ năng minh họa: thứ tự tính chỉ số, tra thuốc, vẽ; nguồn phải chép từ kết quả; giá trị ca tham chiếu ô; không vẽ lại sau thành công. Ví dụ đầu sử dụng lưới và giá trị ca từ công cụ tính cùng khoảng liều từ công cụ tra thuốc.
- Gắn mã căn cứ vào tóm tắt từng bộ dữ liệu. Bổ sung kiểm thử ngân sách, khối đã lưu, gợi ý, vết và ví dụ.

## Tệp tạo / sửa

- `app/agent/nodes.py`, `app/agent/state.py`, `app/agent/tools/gateway.py`
- `config/prompts/ky_nang_minh_hoa.v1.md`
- `tests/agent/test_minh_hoa_do_thi.py`, `tests/agent/test_tool_ve_bieu_do.py`
- `plan/briefs/VZ1a-4-bao-cao.md`

## Lệnh và kết quả

- `uv run --no-sync --offline ruff check app tests`: đạt.
- `uv run --no-sync --offline ruff format --check app tools tests/agent tests/api tests/orchestration`: đạt, 280 tệp đúng định dạng.
- `uv run --no-sync --offline pytest -q -p no:cacheprovider <tệp> --basetemp <thư mục riêng trong %TEMP%>`: chạy lần lượt đủ 47 tệp trong `tests/agent`, `tests/orchestration`, `tests/api`; không tệp nào thất bại, hai test bỏ qua.
- Trước khi sửa, test mới cho Gateway tái hiện năm lỗi thiếu gợi ý / thiếu chặn; sau sửa tệp này đạt 10 test. Lần lint đầu báo ba dòng quá dài; sau định dạng lint đạt.
- Đã đặt `UV_CACHE_DIR` trong `%TEMP%`; không cài gói, không dùng mạng, không commit. Lần đầu chạy `uv` không đặt cache thất bại do không có quyền truy cập cache mặc định, sau đó chạy lại với cache trong `%TEMP%`.

## Điểm lệch / việc chưa làm

- Khi đã hết ba vòng vẽ, nếu LLM vẫn tiếp tục yêu cầu một vòng chỉ vẽ sau lời nhắc trả lời bằng chữ, đồ thị chuyển dự phòng lỗi để tránh vòng lặp vô hạn. Đây là ngoại lệ chưa đáp ứng yêu cầu không chuyển dự phòng chỉ vì vẽ; không thể bảo đảm có câu trả lời do LLM tạo khi mô hình liên tục không làm theo chỉ dẫn và vẫn phải giữ vòng lặp hữu hạn.
- Chưa chạy DeepSeek thật và chưa đối chiếu số trên lưới trong phiên chạy thật: brief giao bước này cho Claude, còn phiên này bị cấm dùng mạng. Kiểm thử giả đã kiểm tra công thức các dòng lưới và ví dụ qua `kiem_dac_ta`.
