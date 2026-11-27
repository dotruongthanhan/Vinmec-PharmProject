# Báo cáo T113 – Công cụ chấm điểm ô hỏi đáp

```text
TRẠNG THÁI: CHƯA XONG (đã hoàn tất mã nguồn và kiểm thử; chưa chạy lệnh Nghiệm thu mục 8 theo yêu cầu, Claude sẽ chạy)

FILE ĐÃ TẠO / SỬA:
- Tạo mới: app/eval/__init__.py
- Tạo mới: app/eval/hoi_dap.py
- Tạo mới: tools/cham_hoi_dap.py
- Tạo mới: tests/eval/__init__.py
- Tạo mới: tests/eval/test_cham_hoi_dap.py
- Tạo mới: plan/briefs/T113-bao-cao.md
(Không sửa tests/conftest.py vì dùng trực tiếp @pytest.mark.can_du_lieu("data/gold/hoi_dap/cau_hoi_v1.jsonl"); không tạo/sửa data/gold/hoi_dap/* hay bất kỳ tệp nào trong vùng cấm.)

LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:
- CHƯA CHẠY bất kỳ lệnh shell/terminal nào theo yêu cầu phiên làm việc (không gọi công cụ shell, không chạy lệnh, không gọi mạng, không commit).
- Các lệnh mục 8 Nghiệm thu chưa chạy (Claude sẽ chạy):
  - uv run ruff check app tests tools/cham_hoi_dap.py
  - uv run ruff format --check app tests tools/cham_hoi_dap.py
  - uv run pytest -q -p no:cacheprovider tests/eval tests/agent tests/orchestration

ĐIỂM LỆCH SO VỚI BRIEF (nếu có) VÀ LÝ DO:
- Hàm phân tích tham số (build_parser) và điểm vào CLI (main) đặt trong app/eval/hoi_dap.py, còn tools/cham_hoi_dap.py là lớp gọi mỏng 6 dòng (`from app.eval.hoi_dap import main`). Lý do: giữ tools/cham_hoi_dap.py đúng nghĩa CLI mỏng và giúp tests/eval/test_cham_hoi_dap.py nhập thẳng hàm CLI từ gói app mà không phụ thuộc namespace package tools/.
- Bổ sung tham số tuỳ chọn `--tep` (mặc định `data/gold/hoi_dap/cau_hoi_v1.jsonl`) bên cạnh các cờ trong brief (`--engine`, `--loai`, `--id`, `--gioi_han`, `--tat_ca`, `--ra`) để kiểm thử CLI với tệp tạm trong `tmp_path` mà không chạm `data/gold/hoi_dap/`.
- Trong `KyVong.dung_sai`, chấp nhận giá trị `null` chuyển về mặc định `0.05` để tương thích nếu bộ câu hỏi T112 ghi `"dung_sai": null` cho các câu không có `so_bat_buoc`.

VIỆC CHƯA LÀM / CÂU HỎI:
- Chưa chạy các lệnh nghiệm thu mục 8 (ruff check, ruff format --check, pytest) và chưa chạy thử trên bộ câu hỏi T112 với DeepSeek (Claude sẽ thực hiện).
```

## Tóm tắt triển khai

1. **Lược đồ và nạp tệp (`app/eval/hoi_dap.py`):**
   - Mô hình pydantic v2 `KyVong` và `CauHoiDanhGia` (`extra="forbid"`, giới hạn độ dài chuỗi/danh sách, kiểm `che_do="ca"` bắt buộc có `ca_id` không rỗng, `che_do="chung"` bắt buộc `ca_id=None`, kiểm tham chiếu `{pii:<LOAI>}` trong `cum_cam` thuộc `LoaiDinhDanh`).
   - `load_questions` kiểm từng dòng JSONL, báo lỗi kèm số dòng (không phản chiếu giá trị đầu vào), chặn trùng `id` và dừng trước khi chạy.
2. **Chấm thuần 6 tiêu chí (`score_answer`):**
   - Không I/O, không làm tròn số thực trong hàm tính.
   - Tiêu chí 1 (`trang_thai`), 2 (`so_bat_buoc` dùng `mask_citation_markers` + `numbers_in_text` nhận `15,31` và `15.31`, so theo `dung_sai`), 3 (`nhom_cum_bat_buoc` chuẩn hoá NFC, bỏ ký tự rộng 0, `casefold`, gộp khoảng trắng), 4 (`cum_cam` mở rộng `{pii:<LOAI>}` trong bộ nhớ, loại `NGAY` so cả ISO lẫn `dd/mm/yyyy`, lý do chỉ ghi mã `{pii:<LOAI>}` chứ không ghi giá trị thật), 5 (`can_trich_dan` & `loai_trich_dan`), 6 (`ro_pii` kiểm `noi_dung`, `trich_dan[].nhan`, `trich_dan[].trich_nguyen_van` với định danh ca hoặc mọi ca ở chế độ chung; lý do chỉ ghi loại định danh và vị trí trường).
3. **Chạy bộ và báo cáo (`run_evaluation`, `summarize_results`, `render_summary_markdown`, `write_reports`):**
   - Nạp ca bằng `load_source_cases`, chạy bộ luật bằng `run_case` với `container.renal_rules` và `container.rule_context` như `app/api/service.py::_review`, dùng `vai_tro="duoc_si_ls"` cho asker hỗ trợ tham số vai trò (`AgenticAsker`).
   - Trần mặc định `--gioi_han 20` (muốn chạy hết dùng `--gioi_han 90` hoặc `--tat_ca`); chạy tuần tự, trần cứng 120 s/câu, cô lập ngoại lệ từng câu sang trạng thái `loi` (không lộ nội dung ngoại lệ), dừng sớm với mã thoát 2 khi thiếu khoá LLM hoặc asker trả `chua_san_sang`.
   - Ghi `tong_hop.md` (tổng theo engine, chi tiết `engine × loai × che_do`, bảng các câu hai engine khác kết quả) và `chi_tiet.jsonl` (`noi_dung` đã che PII qua `DeidSession.scrub` và cắt 2.000 ký tự). Log chỉ ghi `id`, `engine`, `trang_thai`/`error_type`, `thoi_gian_ms`.
4. **Kiểm thử (`tests/eval/test_cham_hoi_dap.py`):**
   - Đủ 8 test bảo mật mục 6 (lược đồ báo số dòng, `{pii:TEN}` không lộ vào báo cáo/log, phát hiện rò SĐT trong `noi_dung` và `trich_dan[].trich_nguyen_van` cùng chế độ chung, che CCCD và cắt 2.000 ký tự trong `chi_tiet.jsonl`, trần mặc định 20 câu, ngoại lệ một câu ghi `loi` không dừng bộ, `chua_san_sang` dừng sớm mã thoát khác 0, chặn `psycopg.connect` và `read_pool.connection`).
   - Đủ 3 nhóm test chức năng mục 7 (6 tiêu chí đủ nhánh đạt/trượt, chạy bộ 3 câu qua `ca_hai` đối chiếu chỉ số tính tay, kiểm lược đồ tệp thật gắn `@pytest.mark.can_du_lieu("data/gold/hoi_dap/cau_hoi_v1.jsonl")`).
