# T49 – Chuyển luồng thẩm định AI sang LangGraph (luồng thẳng, có cờ)

Mô hình: Codex `gpt-6.2-sol`, effort `high`. Chạy nền, không dừng để hỏi; điểm chưa rõ thì chọn cách ít rủi ro nhất, ghi vào báo cáo mục "Lựa chọn đã làm".

## Bối cảnh
Luồng AI hiện là hàm Python tuần tự: `AiReviewer.run` (`app/orchestration/ai_review.py`) gọi `EvidenceCollector.collect` rồi `Synthesizer.run` (trong đó: dựng ngữ cảnh, gọi LLM, kiểm chứng, thử lại, ghép với luật). Người dùng (18/11) muốn chuyển sang LangGraph **dạng luồng thẳng** để sau này chèn thêm nút (tra openFDA, tìm web, dược sĩ xác nhận...) dễ dàng. Người dùng đồng ý thêm thư viện `langgraph`.

## Phạm vi file
Được sửa/tạo: `app/orchestration/graph/**` (mới), `app/orchestration/ai_review.py`, `app/orchestration/__init__.py`, `pyproject.toml`, `uv.lock`, `config/settings.yaml` (thêm cờ), `app/config/settings.py` (chỉ thêm trường cờ vào mô hình settings), `tests/orchestration/**` (test mới), `plan/reports/T49.md`, và một mục ngắn trong `plan/plan-1.1-kien-truc-chi-tiet.md` mô tả đồ thị.
Cấm đụng (task khác đang sửa song song): `app/llm/**`, `app/deid/**`, `app/orchestration/ask.py`, `app/api/service.py`, `app/db/**`, `app/container.py`, `web/`, `config/prompts/`, `.env`, `data/`.

## Yêu cầu
1. Thêm `langgraph` (bản ổn định mới nhất tương thích Python của dự án) bằng `uv add`; ghi phiên bản vào báo cáo.
2. **Đồ thị luồng thẳng** `StateGraph` với trạng thái kiểu (TypedDict hoặc pydantic) gồm: `ca`, `ket_qua_luat`, `doan`, `canh_bao`, `ket_qua_llm`, `thoi_gian_bat_dau`. Các nút:
   - `thu_thap_nguon`: gọi `EvidenceCollector.collect`.
   - `tong_hop`: gọi `Synthesizer.run` (giữ nguyên bên trong; **không** tách vòng thử lại của Synthesizer ở task này vì `app/llm` đang được task khác sửa).
   - `hoan_tat`: gộp cảnh báo (bỏ trùng, giữ thứ tự như hiện nay), tính `thoi_gian_ms`, dựng `AiRunResult`.
   Cạnh: `START → thu_thap_nguon → tong_hop → hoan_tat → END`. Biên dịch đồ thị **một lần** khi khởi tạo `AiReviewer`, không biên dịch lại mỗi ca.
3. **Mở rộng dễ:** mỗi nút là một lớp/hàm riêng trong `app/orchestration/graph/nodes.py`, danh sách nút và cạnh khai báo ở một chỗ (`builder.py`); có docstring hướng dẫn chèn nút mới (ví dụ nút `tra_cuu_ngoai` giữa `thu_thap_nguon` và `tong_hop`, đi khi không đủ đoạn nguồn). Không cài nút đó ở task này.
4. **Cờ chuyển đổi:** `orchestration.engine: "langgraph" | "tuan_tu"` trong `config/settings.yaml`, **mặc định `langgraph`** chỉ khi toàn bộ nghiệm thu dưới đây qua; nếu không chắc, để `tuan_tu` và nêu trong báo cáo. `AiReviewer.run` chọn đường theo cờ; đường `tuan_tu` giữ nguyên mã hiện tại.
5. **Bất biến an toàn giữ nguyên:** mọi ngoại lệ trong bất kỳ nút nào phải cho ra kết quả chỉ-luật y hệt nhánh `except` hiện tại (`trang_thai="loi_llm"`, cảnh báo "Bước AI gặp lỗi không mong muốn (...)"); không có nút nào được xóa/hạ phát hiện luật; không ghi log dữ liệu ca hay prompt.
6. Không bật checkpoint/persistence của LangGraph (không lưu trạng thái chứa dữ liệu ca), không bật tracing gửi ra ngoài (LangSmith); ghi rõ trong báo cáo cách đảm bảo (biến môi trường, tham số).

## Nghiệm thu (dán kết quả)
- Test mới: hai đường cho **kết quả giống hệt** (`AiRunResult` trừ `thoi_gian_ms`) trên tất cả ca `data/mock/demo` và `data/mock/hoso_gia_lap` với LLM giả xác định và collector giả/thật không gọi mạng; ngoại lệ ở từng nút cho ra kết quả chỉ-luật; đồ thị đúng thứ tự nút; biên dịch một lần.
- `uv run ruff check .`, `uv run ruff format --check` (tệp đã sửa), `uv run pytest -q --basetemp=.pytest_t49` đều qua (toàn bộ test cũ không sửa kỳ vọng).
- Báo cáo `plan/reports/T49.md`.

## Cấm làm
Không commit/push, không gọi LLM thật, không dùng `&`, xóa `.pytest_t49*`.
