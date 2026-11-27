# Báo cáo TR1 – tracer lõi

**TRẠNG THÁI: CHƯA XONG.** Các điểm móc chính và test tracer đã có, nhưng còn các giới hạn và kết quả nghiệm thu chưa đạt dưới đây.

## Phần đã làm

- Hoàn thiện `app/tracing/`: vết UUID, ContextVar, span lồng nhau, danh sách khóa, giới hạn kích thước, HMAC mã ca bằng khóa từ biến môi trường, hàng đợi và ghi JSONL theo ngày giờ Việt Nam, dọn vết cũ.
- Móc tiến trình, Gateway, LLM DeepSeek, kiểm chứng, hỏi đáp, rà AI và eval; thêm `ma_vet` vào kết quả và header API, giữ LangSmith tắt. Thêm cấu hình và test `tests/tracing/`; cập nhật test hợp đồng API cho trường mới.
- Chuyển tuần tự hóa JSON sang luồng ghi nền. Thuộc tính và nội dung được che trước khi ghi. Mức có nội dung chỉ ghi khi có bản sao phiên che định danh; thiếu phiên thì chỉ lưu siêu dữ liệu, để tránh ghi tên hoặc mã định danh chưa được che. Bản sao phiên không thay đổi bảng ánh xạ của ứng dụng.
- Giữ các thay đổi chưa commit có sẵn của T108–T114; không commit, cài gói hay gọi mạng. Kiểm thử dùng dữ liệu giả lập và thư mục tạm. `PYTHON_DOTENV_DISABLED=1` được đặt khi chạy pytest.

## Kết quả kiểm tra

- `uv run --no-sync ruff ...` thất bại trước khi chạy Ruff vì cache `C:\Users\Admin\AppData\Local\uv\cache` bị từ chối truy cập. Không cài gói; dùng trực tiếp công cụ có sẵn trong `.venv`.
- `.venv\Scripts\ruff.exe check app tests`: đạt. `.venv\Scripts\ruff.exe format --check app tests`: đạt.
- Chạy pytest bằng `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`, lần lượt từng thư mục với `--basetemp tests/tracing/.tmp-*`; không chạy song song:
  - `tests/tracing`: 14 đạt. Bao gồm đồ thị agent với LLM giả, Gateway thật, token, hàng đợi đầy, ba mức canary, che mã lý do, giới hạn span, dọn vết, API và eval.
  - `tests/agent`: 149 đạt; `tests/orchestration`: 83 đạt; `tests/eval`: 21 đạt.
  - `tests/api`: 216 đạt, 2 bỏ qua, 2 trượt ban đầu. `test_interface_field_sets_match_contract` trượt vì trường `ma_vet`; đã cập nhật test và chạy lại đạt. `test_suggest_index_build_and_query_latency` trượt vì dựng chỉ mục mất 4,168 giây so với giới hạn 3 giây; chạy riêng lại mất 3,540 giây và vẫn trượt. Không sửa phần tra cứu ngoài phạm vi TR1.
  - Các thư mục khác: `architecture` 4 đạt sau khi sửa và chạy lại; `auth` 57; `calc` 51; `config` 38; `core` 10; `db` 183 đạt, 2 bỏ qua; `deid` 297; `domain` 22; `kb` 278; `llm` 35; `providers` 64; `retrieval` 38; `rules` 234; `storage` 10; `ui` 54; `verify` 10. Bốn tệp test ở gốc `tests/`: 12 đạt.
  - Sau thay đổi cuối về phiên che, chạy lại chọn lọc test đồ thị agent, khử định danh hỏi đáp và DeepSeek: 28 đạt; test tracer: 14 đạt.
- Lần chạy `tests/agent` đầu dùng thư mục tạm mặc định thất bại ở bước setup: 139 đạt, 10 lỗi `PermissionError` với thư mục pytest hệ thống. Lần chạy lại bằng `--basetemp` riêng đạt 149 test.
- Bộ test đầy đủ được chia theo thư mục theo yêu cầu hạn chế RAM, không chạy nguyên một lệnh pytest toàn bộ. Test hiệu năng chỉ mục nói trên còn trượt.

## Điểm lệch và việc còn lại

1. Hỏi đáp agentic qua API và eval có vết. Tuy nhiên, gọi trực tiếp `AgenticAsker.ask()` hoặc nhánh agentic `ask_global()` khi chưa có vết bên ngoài không tự mở vết; cần sửa `app/agent/asker.py`, tệp không nằm trong phạm vi brief cho phép. Không tự mở rộng phạm vi sửa.
2. Các mức có nội dung chỉ ghi nội dung khi đã đăng ký được phiên che. Nhánh rà AI hiện không cung cấp phiên đó cho tracer, nên chỉ có siêu dữ liệu. Đây là lựa chọn bảo mật chưa đáp ứng đầy đủ mục nội dung đã che của plan.
3. Chưa đo chênh lệch p95 của 50 lượt agent. Chưa chạy hai câu DeepSeek thật `HD-CA-015`, `HD-CA-011`, vì yêu cầu phiên này cấm mạng; chưa đối chiếu token với nhà cung cấp thật.
4. Log hiện có `ask rejected ... reason=` dùng lớp che mẫu, nhưng vẫn có thể ghi nguyên số dài không khớp mẫu nhận diện. Cần áp dụng quy tắc che chữ số sau dấu `:` như tracer trong đợt khác. Không sửa log này trong TR1.
5. Các thư mục `.tmp-*` do pytest tạo trong `tests/tracing/` còn lại. Lệnh dọn đã bị hệ thống tự động chặn theo chính sách; công cụ không cung cấp lý do chi tiết. Chủ kho có thể tự xóa các thư mục tạm đó.
