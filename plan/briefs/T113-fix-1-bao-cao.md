# Báo cáo T113-fix-1 – Thay tham chiếu `{pii:...}` trong câu hỏi + format

```text
TRẠNG THÁI: CHƯA XONG (đã hoàn tất sửa mã nguồn và bổ sung kiểm thử theo brief; chưa chạy lệnh Nghiệm thu vì phiên bị cấm gọi shell, Claude sẽ chạy)

FILE ĐÃ TẠO / SỬA:
- Sửa: app/eval/hoi_dap.py
- Sửa: tests/eval/test_cham_hoi_dap.py
- Tạo mới: plan/briefs/T113-fix-1-bao-cao.md
(Không chạm bất kỳ tệp nào khác; không chạm app/eval/__init__.py hay data/gold/hoi_dap/*; không cài gói; không gọi mạng; không commit.)

LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:
- CHƯA CHẠY bất kỳ lệnh shell/terminal nào theo yêu cầu phiên làm việc (KHÔNG gọi công cụ shell/terminal, không chạy lệnh, không gọi mạng, không commit).
- Các lệnh Nghiệm thu chờ Claude chạy:
  - uv run ruff check app tests tools/cham_hoi_dap.py
  - uv run ruff format --check app tests tools/cham_hoi_dap.py
  - uv run pytest -q -p no:cacheprovider tests/eval

ĐIỂM LỆCH SO VỚI BRIEF (nếu có) VÀ LÝ DO:
- Hàm dien_pii_cau_hoi(cau_hoi: str, dinh_danh: Sequence[GiaTriDinhDanh], cau_hoi_id: str | None = None) -> str có thêm tham số tuỳ chọn cau_hoi_id=None. Lý do: vẫn tương thích hoàn toàn khi gọi 2 đối số dien_pii_cau_hoi(cau_hoi, dinh_danh) như brief nêu, đồng thời cho phép run_evaluation truyền question.id để thông điệp QuestionLoadError có mã id câu khi thiếu loại định danh mà không lộ bất kỳ giá trị PII nào.
- Trong CauHoiDanhGia._validate_mode_case, ngoài chặn {pii: trong cau_hoi khi che_do="chung", bổ sung kiểm định dạng {pii:<LOAI>} (LOAI thuộc LoaiDinhDanh) trong cau_hoi khi che_do="ca" cho nhất quán với kiểm cum_cam ở KyVong; đồng thời run_evaluation kiểm trước các câu có {pii: trước khi gọi asker để tránh tốn lượt LLM nếu thiếu định danh.
- Tại _check_required_groups (dòng 591–595 cũ, nay 601–603), gộp biểu thức generator trong any(...) thành một dòng dài đúng 100 ký tự (line-length = 100) thay vì tách 3 dòng, khớp đúng quy tắc ruff format cho generator nằm trọn trong ngoặc lời gọi.

VIỆC CHƯA LÀM / CÂU HỎI:
- Chưa chạy 3 lệnh nghiệm thu (ruff check, ruff format --check, pytest tests/eval) do bị cấm gọi shell; Claude sẽ chạy nghiệm thu và xác nhận định dạng.
```

## Tóm tắt thay đổi

1. **`app/eval/hoi_dap.py`:**
   - Thêm hằng regex `_PII_INLINE_RE` và `_PII_TOKEN_SCAN_RE`.
   - Mở rộng `CauHoiDanhGia._validate_mode_case`: câu `che_do="chung"` chứa `{pii:` trong `cau_hoi` → `ValueError` (bị `load_questions` bắt thành `QuestionLoadError` kèm số dòng); câu `che_do="ca"` có `{pii:...` sai định dạng hoặc loại ngoài `LoaiDinhDanh` cũng bị chặn lúc nạp.
   - Thêm hàm thuần `dien_pii_cau_hoi(cau_hoi, dinh_danh, cau_hoi_id=None)`: thay mỗi `{pii:<LOAI>}` (`LOAI` thuộc `LoaiDinhDanh`) bằng giá trị không rỗng đầu tiên cùng loại trong `dinh_danh` theo thứ tự ổn định (dùng hàm thay thế cho `re.sub` để tránh lỗi ký tự thoát `\`); thiếu loại → ném `QuestionLoadError` kèm `cau_hoi_id` (nếu có) và tên loại thiếu, không kèm bất kỳ giá trị PII hay nội dung câu hỏi nào.
   - Cập nhật `run_evaluation`: kiểm sớm các câu có `{pii:` trước khi gọi asker; với câu `che_do="ca"`, điền `asked_text = dien_pii_cau_hoi(question.cau_hoi, dinh_danh, cau_hoi_id=question.id)` và truyền `active_text` vào `asker.ask`; câu đã điền chỉ sống trong bộ nhớ, không biến đổi `question.cau_hoi`, không ghi vào `chi_tiet.jsonl` (vẫn không có trường câu hỏi), `tong_hop.md` hay log.
   - Chỉnh định dạng `any(...)` trong `_check_required_groups` (quanh dòng 592 cũ) đúng chuẩn `ruff format` (`line-length = 100`).
2. **`tests/eval/test_cham_hoi_dap.py`:**
   - Thêm `test_dien_pii_cau_hoi_replaces_first_values_and_rejects_missing`: kiểm thay `TEN`, `SDT` theo giá trị đầu tiên trên ca giả lập; kiểm thiếu loại ném `QuestionLoadError` có `id` câu và không chứa giá trị PII nào.
   - Thêm `test_run_evaluation_fills_pii_in_question_only_in_memory`: dùng `_FakeAsker` ghi lại câu hỏi nhận được, xác nhận asker nhận họ tên và SĐT thật thay cho `{pii:TEN}`, `{pii:SDT}`, còn `chi_tiet.jsonl` (không có trường `cau_hoi`), `tong_hop.md` và `caplog` không chứa họ tên hay SĐT; kiểm thêm trường hợp thiếu định danh trong `run_evaluation` ném `QuestionLoadError` có `id` câu và không gọi asker.
   - Thêm `test_security_global_question_with_pii_placeholder_fails_load`: kiểm câu `che_do="chung"` có `{pii:TEN}` trong `cau_hoi` và câu `che_do="ca"` có `{pii:KHONG_TON_TAI}` đều báo `QuestionLoadError` kèm số dòng khi nạp.
