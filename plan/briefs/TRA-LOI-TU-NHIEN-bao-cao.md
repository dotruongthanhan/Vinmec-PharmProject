# Báo cáo TRA-LOI-TU-NHIEN – Lượt 2

Ngày: 28/11/2026.

## Đối chiếu yêu cầu

1. **Đạt:** Có prompt `tra_loi_trung_thuc.v1.md` và hàm dùng chung, gọi tối đa một lần khi cần trả lời trung thực; prompt nhận câu hỏi, công cụ, dữ liệu đã che và mã lý do, không nhận câu trả lời cũ. Không có LLM hoặc LLM lỗi vẫn dùng thông báo quy định.
2. **Đạt có giới hạn:** Câu trả lời theo ca được kiểm qua `kiem_chung_tra_loi`; số sai bị loại theo câu và phần còn lại được kiểm lại. Hỏi chung dùng các hàm kiểm số và đối chiếu trích dẫn hiện có, thêm kiểm tra mã trên bản tóm tắt; không gọi trực tiếp `kiem_chung_tra_loi` vì hàm này cần một ca cụ thể. Hết nội dung an toàn thì dùng câu dự phòng ngắn.
3. **Đạt:** Ngoài phạm vi chuyển qua lượt LLM và kiểm chứng; đầu vào bị chặn chèn lệnh vẫn trả câu cố định, không gọi LLM. Đầu ra bị phát hiện ép duyệt cũng giữ chốt an toàn hiện có.
4. **Đạt:** Giữ `ERROR_MESSAGE`, `NOT_READY_MESSAGE`.
5. **Đạt:** Áp dụng cho luồng ca cố định, hỏi chung và agent; agent hỏi chung vẫn chuyển cho CaseAsker. Giữ `_filter_missing_figure` và không sửa `app/verify/**`.
6. **Đạt:** Lượt bổ sung theo hạn chót, sử dụng ngân sách nhà cung cấp; agent kiểm số lượt còn lại. Span `tra_loi_trung_thuc` ghi trạng thái và số câu lọc, không ghi nội dung. Hết giờ/hết lượt trả dự phòng.
7. **Chưa rà:** Không rà `data/gold/hoi_dap/*.jsonl` và không liệt kê các cụm đáp án cũ; yêu cầu Lượt 2 chỉ làm phần lõi 1–6. Không sửa gold.
8. **Chưa kiểm lại:** Theo brief, Lượt 1 đã xử lý văn bản không có kết quả của bốn tool. Không rà hoặc sửa thêm sáu tool ở Lượt 2; chưa xác nhận toàn bộ yêu cầu 8.
9. **Theo Lượt 1:** Brief ghi prompt `tac_tu`/`hoi_them` đã xong; không sửa hoặc kiểm riêng lại ở Lượt 2.
10. **Theo Lượt 1:** Brief ghi nhãn web và mock đã xong; không sửa hoặc chạy lại test web ở Lượt 2.
11. **Đạt trong phạm vi Lượt 2:** Không sửa synthesizer, bộ luật hoặc `app/verify/**`.

## Tệp Lượt 2

- `app/orchestration/ask.py`, `app/agent/nodes.py`, `app/agent/graph.py`, `app/tracing/models.py`.
- `config/prompts/tra_loi_trung_thuc.v1.md`.
- `tests/orchestration/test_ask.py`, `tests/orchestration/test_ask_deid.py`, `tests/orchestration/test_tra_loi_trung_thuc.py`, `tests/agent/test_graph.py`, `tests/agent/test_tra_loi_trung_thuc.py`.
- Báo cáo này.

## Nghiệm thu

Đặt `UV_OFFLINE=1`, `UV_NO_SYNC=1`, `PYTHON_DOTENV_DISABLED=1`; dùng cache uv/ruff trong thư mục tạm. Không đọc `.env`, không gọi `load_env_file()`, không cài gói hoặc dùng mạng.

- `uv run ruff check app tests`: đạt.
- `uv run ruff format --check app tests/orchestration tests/agent tests/eval`: đạt, 322 tệp đã định dạng.
- `uv run pytest -q -p no:cacheprovider tests/orchestration --basetemp ...`: 93 đạt; sau đó bổ sung một test truy xuất chung không có kết quả và chạy `tests/orchestration/test_tra_loi_trung_thuc.py`: 8 đạt.
- `uv run pytest -q -p no:cacheprovider tests/agent -k 'not test_api_case_returns_block_without_saving_it' --basetemp ...`: 291 đạt, 1 bỏ qua. Test bị bỏ qua nhập `app.api.main`, nơi gọi `load_env_file()` ngay lúc import; chạy test này sẽ trái yêu cầu trực tiếp của người dùng.
- `uv run pytest -q -p no:cacheprovider tests/eval --basetemp ...`: 29 đạt.
- `uv run pytest -q -p no:cacheprovider tests/verify --basetemp ...`: 18 đạt.
- Không chạy `tests/api` theo chỉ dẫn Lượt 2. Không chạy web hoặc chấm lại 90 câu trong Lượt 2.
- Những lần chạy ban đầu có test cũ trượt vì hết phản hồi LLM giả/câu mẫu; đã cập nhật test liên quan. Một lần chạy đầu gặp lỗi quyền thư mục pytest tạm mặc định; dùng `--basetemp` trong thư mục test để chạy lại. Một test mới phát hiện trạng thái ngoài phạm vi của hỏi chung bị phân loại sai khi nội dung rỗng; đã sửa và chạy lại agent.
- Các thư mục `.tmp-luot2-test*` do các lượt pytest tạo còn lại: lệnh xóa các thư mục đã xác minh nằm trong workspace bị chính sách môi trường từ chối. Không xóa các thư mục tạm có sẵn trước đó.

## Điểm còn lại

Chưa chạy một test agent do ràng buộc không gọi `load_env_file()`. Chưa rà gold và chưa nghiệm thu lại phần Lượt 1 (yêu cầu 7–10). Không gọi web/API ngoài, không kiểm thử triển khai trực tiếp.

## fix-1 (28/11/2026)

- Đo `fake_llm.calls` trong test API cũ: trước câu tấn công 0, sau câu tấn công 0, sau câu PII 1. Đầu vào tấn công đã bị chặn trước LLM; không cần sửa mã sản phẩm.
- Câu PII nhận phản hồi giả đầu tiên “Đơn này đạt [1]”, bị bộ chặn đầu ra phát hiện là ép duyệt và trả `ngoai_pham_vi`. Test cũ giả định câu tấn công tiêu thụ phản hồi này; giả định đó trái với yêu cầu không gọi LLM khi chặn đầu vào. Đã bỏ phản hồi giả thừa, thêm kiểm tra số lượt gọi, giữ các kiểm tra 422/404, chưa sẵn sàng, nhận định không đổi và che PII trước LLM.
- Đặt `PYTHON_DOTENV_DISABLED=1`, `UV_OFFLINE=1`, `UV_NO_SYNC=1` và cache uv trong workspace. Lệnh nghiệm thu nguyên dạng bị dừng sau nhiều lỗi tạo thư mục tạm; chạy kiểm tra với `--maxfail=1` xác nhận `PermissionError: [WinError 5]` tại thư mục pytest tạm mặc định của Windows.
- Chạy lại `uv run pytest -q -p no:cacheprovider tests/api tests/orchestration tests/agent --basetemp=tests/api/.tmp-fix1-acceptance`: **604 đạt, 2 bỏ qua**. Không mở `.env`, không cài gói hoặc gọi mạng.

## fix-2 (28/11/2026)

- Đã kết thúc bước kiểm chứng bằng trạng thái `xong` khi chuyển sang trả lời thận trọng ở luồng ca và hỏi chung; giữ chi tiết theo brief. Trường hợp chặn đầu ra vẫn kết thúc bước kiểm chứng.
- Bổ sung bước `Trả lời thận trọng`: ghi `xong` khi đạt, khi lọc câu (kèm số câu) hoặc dùng dự phòng; lỗi gọi LLM và timeout trong lượt này ghi `loi` kèm gợi ý thử lại. Agent ghi nhãn kết thúc an toàn theo ngoài phạm vi hoặc thiếu nguồn; lỗi gọi LLM có gợi ý thử lại.
- Bổ sung kiểm thử tiến trình cho hai engine: kiểm chứng trượt hai lần rồi trả lời trung thực, ngoài phạm vi, lọc một câu, dự phòng và lỗi LLM thật.
- Nghiệm thu: đặt `UV_OFFLINE=1`, `UV_NO_SYNC=1`, `PYTHON_DOTENV_DISABLED=1`, cache uv/ruff trong workspace. `uv run ruff check app tests`: đạt. `uv run pytest -q -p no:cacheprovider tests/agent tests/orchestration tests/api --basetemp=tests/agent/.tmp-fix2-acceptance`: **611 đạt, 2 bỏ qua**. Dùng `--basetemp` trong workspace do lỗi quyền thư mục pytest mặc định đã xác nhận tại fix-1.
- Lần chạy test đầu không khởi tạo được cache uv mặc định vì bị từ chối quyền; đã chuyển cache vào workspace. Nhóm test mới trước khi sửa phát hiện trạng thái lỗi giả và thiếu tiến trình; sau sửa, nhóm liên quan đạt. Lần lint đầu báo sáu dòng quá dài, đã sửa và chạy lại đạt.
- Không mở `.env`, không cài gói, không dùng mạng. Các tệp sửa sẵn trước lượt này được giữ lại.
