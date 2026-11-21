# Báo cáo T99 – Tiến trình hỏi đáp: backend

## File đã tạo / sửa

- `app/core/progress.py`: thêm hằng số `MAX_ASK_PROGRESS_ENTRIES = 200`, `ASK_PROGRESS_RETENTION_SECONDS = 60.0`, kiểu `AskProgressKey` và lớp `AskProgressRegistry` (`RLock`, `bat_dau`, `ket_thuc`, `doc`, bảo vệ bằng `token`, dọn mục quá 60 giây theo `time.monotonic()`, đẩy mục tạo sớm nhất khi vượt 200 mục).
- `app/orchestration/ask.py`: thêm các lời gọi `ghi_buoc` (và helper nội bộ `_summarize_sources`, `_ask_error_reason`, `_safe_step_error_message`, `_mark_running_step_error`) trong `CaseAsker.ask` và `CaseAsker.ask_global`; giữ nguyên toàn bộ chữ ký, logic che định danh, truy xuất, kiểm chứng và nội dung `AskResult`. Mọi lời gọi `ghi_buoc` đều nằm ngoài lambda truyền vào `_run_with_deadline`.
- `app/api/schemas.py`: thêm `TienTrinhHoiDap(ApiModel)` dùng lại `BuocAI`.
- `app/api/service.py`: thêm `self._ask_progress = AskProgressRegistry()`, bọc `CaseService.ask` (cả `__global__` và theo ca) để mở mục sổ đăng ký, gắn/reset ContextVar `tien_trinh_hien_tai` trong `try`/`finally`, xử lý riêng 429 (`ly_do="Vượt giới hạn lượt hỏi"`, `goi_y="Chờ ít giây rồi hỏi lại"`), chốt `ket_thuc(..., result.trang_thai == "ok")`; thêm `get_ask_progress(case_id, principal)` và tách helper `_present_progress_steps`.
- `app/api/routes.py`: thêm `GET /api/ask/tien-trinh` (trước các route có tham số) và `GET /api/cases/{ca_id}/ask/tien-trinh` (quyền `Caller`, `Path(min_length=1, max_length=128)`, `Cache-Control: private, no-store`, `response_model=s.TienTrinhHoiDap`).
- `plan/api-hop-dong-v1.2-hoi-dap.md`: thêm mục 5 ngắn `v1.10 – tiến trình hỏi đáp` trỏ về `plan/plan-1.10-tien-trinh-ai-ui.md` mục 10.
- `tests/orchestration/test_progress.py`: bổ sung test cho `AskProgressRegistry` (vòng đời, 60 giây, token thay thế, cách ly user, trần 200 mục) và các bước `ghi_buoc` trong `CaseAsker.ask` / `ask_global`.
- `tests/api/test_ask_progress.py`: test API tiến trình hỏi đáp (rỗng khi không có mục, validation độ dài `ca_id` ≤ 128, vòng đời ca và `__global__`, giữ 60s rồi dọn, cách ly người dùng A/B, bảo mật không rò dữ liệu/log, 429 vẫn chốt mục, hai lượt liên tiếp không để mục cũ xoá mục mới).
- `tests/api/test_contract.py`: thêm `"TienTrinhHoiDap": {"dang_chay", "cac_buoc", "da_chay_ms"}` vào `INLINE_FIELDS` để khớp kiểm tra toàn bộ model trong `app/api/schemas.py` (ngoài danh sách file brief liệt kê nhưng cần thiết để `test_interface_field_sets_match_contract` không trượt khi có model mới trong `schemas.py`).

## Quyết định tự chọn

1. **Nhánh chung (`__global__`) bỏ `truy_xuat` khỏi danh sách bước đăng ký sẵn**: dùng 3 bước `chuan_bi` ("Tổng hợp danh sách y lệnh"), `goi_mo_hinh` ("Soạn câu trả lời"), `kiem_chung` ("Kiểm chứng trích dẫn và số liệu"); nếu `ask_global` có truy xuất nguồn thì tóm tắt số đoạn vào `chi_tiet` của `chuan_bi` (chỉ số đếm, không tên thuốc).
2. **Truy xuất ở `CaseAsker.ask`**: khi `used_retrieval=True`, ghi `chi_tiet` dạng `"N đoạn từ M nguồn"` kèm danh sách `nguon` nhóm theo `Chunk.nguon` công khai qua `_source_label` (tối đa 8 nhóm); khi `used_retrieval=False`, ghi `"Không dùng tra cứu nguồn"`.
3. **Bắt ngoại lệ ngoài `HTTPException` 429 trong `service.ask`**: đánh dấu bước đang chạy (hoặc `"chuan_bi"`) là `loi` với thông điệp cố định `"Không soạn được câu trả lời"` và gợi ý `"Bấm Thử lại sau ít phút"` trước khi `raise`, không dùng `str(exc)`.
4. **Cập nhật `tests/api/test_contract.py`**: bổ sung `TienTrinhHoiDap` vào `INLINE_FIELDS` (tương tự `BuocAI`, `NguonTomTat` đã làm ở T97).

## Điều chưa chắc / Ghi chú nghiệm thu

- Theo yêu cầu không gọi shell và không gọi mạng, chưa chạy `pytest` hay `ruff` trực tiếp trong phiên này; cần chạy lại bộ lệnh nghiệm thu:
  - `uv run pytest tests/orchestration tests/api tests/llm -q`
  - `uv run pytest -q`
  - `uv run ruff check .`
  - `uv run ruff format --check app tests`
- Nếu `ruff format --check` có chênh lệch định dạng nhỏ (ví dụ ngắt dòng ở `tests/api/test_ask_progress.py` hoặc `tests/orchestration/test_progress.py`), có thể chạy `uv run ruff format app tests` khi nghiệm thu.
