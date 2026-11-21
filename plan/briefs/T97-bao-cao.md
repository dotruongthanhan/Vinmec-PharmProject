# Báo cáo T97 – Tiến trình phân tích AI (backend)

## File đã tạo / sửa

- Tạo `app/orchestration/progress.py`: định nghĩa `NguonTomTat`, `BuocTienTrinh` (pydantic v2, `extra="forbid"`, cắt mọi chuỗi ở 160 ký tự), `TienTrinh` (an toàn đa luồng bằng `RLock`, tối đa 40 bước, `dang_ky`, `them`, `bat_dau`, `xong`, `loi`, `chot`, `chup`, `tong_ms`), `ContextVar` `tien_trinh_hien_tai` và hàm `ghi_buoc` an toàn khi không có bộ ghi.
- Sửa `app/orchestration/jobs.py`: thêm `tien_trinh`, `bat_dau`, `ket_thuc` vào `AiJobState`; khởi tạo sẵn 3 bước (`thu_thap_nguon`, `tong_hop_1`, `kiem_chung_1`), gán và reset `tien_trinh_hien_tai` trong `_run_job`, chốt khi kết thúc (`chot(True)` khi xong và kết quả AI không phải `loi_llm`, ngược lại `chot(False)`), lưu tối đa 20 thời lượng lượt xong và cung cấp `thuong_le_ms()` (trung vị khi đủ ≥ 3 mẫu).
- Sửa `app/orchestration/graph/nodes.py`: `ThuThapNguon.__call__` ghi sự kiện bắt đầu/kết thúc, tóm tắt `"N đoạn từ M nguồn"` hoặc `"Không tìm thấy đoạn nguồn phù hợp"`, nhóm tối đa 8 nhãn nguồn giảm dần theo `Chunk.nguon`; `an_toan` đánh dấu bước lỗi khi nút ném ngoại lệ (không kèm `str(exc)`).
- Sửa `app/llm/synthesizer.py`: `Synthesizer._run_with_llm` ghi các bước `tong_hop_n`, `kiem_chung_n` (từ lần 2 dùng `them`), lỗi nhà cung cấp (`het_han_muc_token` → `"Vượt hạn mức độ dài"`, còn lại → `"Nhà cung cấp mô hình báo lỗi"`), sai lược đồ và tỷ lệ `x/y dòng đạt` qua `ghi_buoc`.
- Sửa `app/api/schemas.py`: thêm `NguonTomTat`, `BuocAI` và 3 trường tuỳ chọn có mặc định vào `KetQuaAI` (`cac_buoc`, `da_chay_ms`, `thuong_le_ms`).
- Sửa `app/api/service.py`: `_present_job_state` (dùng bởi cả `start_ai` và `get_ai`) gắn `cac_buoc`, `da_chay_ms`, `thuong_le_ms` cho các trạng thái `dang_chay`, `xong`, `loi`; trạng thái `tat` giữ mặc định.
- Sửa `plan/api-hop-dong-v1.1-bo-sung.md`: thêm mục 4 `"v1.10 – tiến trình"` trỏ về `plan/plan-1.10-tien-trinh-ai-ui.md` mà không làm đổi cấu trúc khối `ts` đầu tiên.
- Sửa `tests/api/test_contract.py`: bổ sung `NguonTomTat`, `BuocAI` và 3 trường mới của `KetQuaAI` vào đối chiếu hợp đồng.
- Tạo `tests/orchestration/test_progress.py` và `tests/api/test_ai_progress.py`.

## Quyết định tự chọn

- **Nhãn nguồn trong `nodes.py`**: dùng bảng ánh xạ công khai `_SOURCE_LABELS` (đồng bộ với `app/api/presenter.py`) ngay trong `app/orchestration/graph/nodes.py` với fallback `nguon.replace("_", " ")` để không tạo phụ thuộc ngược từ `app/orchestration` sang `app/api` và đảm bảo không chứa dấu `_` trong trường `nhan`. Không cần sửa `app/orchestration/evidence.py`.
- **Chi tiết khi xong bước tổng hợp**: khi `bat_dau` bước `tong_hop_n` đặt `chi_tiet="Đang gọi mô hình"`; khi `KetQuaTongHop.model_validate` đạt thì gọi `xong` với `chi_tiet=None` để không giữ chữ "Đang gọi mô hình" sau khi bước đã hoàn tất, còn khi sai lược đồ thì đặt `chi_tiet="Đầu ra sai định dạng, thử lại"`.
- **Trạng thái `dau_ra_khong_hop_le`**: theo đúng brief, `AiJobManager._run_job` dùng điều kiện `llm_status != "loi_llm"` khi gọi `chot(...)`; khi `dau_ra_khong_hop_le` xảy ra ở cuối vòng lặp, các bước `tong_hop_n` đã xong và `kiem_chung_n` còn ở `cho` sẽ được `chot` chuyển thành `bo_qua`.
- **Đường tuần tự `AiReviewer._run_sequential`**: giữ nguyên `app/orchestration/ai_review.py` không sửa theo đúng phạm vi file của brief.

## Điều chưa chắc

- Do tuân thủ quy tắc không gọi công cụ shell trong tác vụ này, toàn bộ bộ test (`uv run pytest ...`) và linter (`uv run ruff check .`) chưa được chạy trực tiếp; cần Claude chạy các lệnh nghiệm thu để xác nhận xanh toàn bộ.
- Chưa kiểm tra trực tiếp xem có file test nào khác ngoài `tests/api/test_contract.py` kiểm tra tập trường chính xác của `KetQuaAI` hay `AiJobState` bằng so sánh tuyệt đối (`==`) hay không.
