# VZ5-fix-1 – Test dựng sai mô hình, định dạng ruff

Người làm: agy `gemini-4-neon-high`. **Chỉ ghi tệp, KHÔNG gọi shell.** Đọc `plan/briefs/VZ5-eval-minh-hoa.md`, `plan/briefs/VZ5-bao-cao.md`, `app/agent/minh_hoa/models.py`.

## Claude review VZ5 (27/11)

- `uv run ruff check app/eval tests/eval`: sạch.
- `uv run pytest tests/eval`: **4 trượt / 24 đạt.** Cả 4 trượt cùng một lỗi trong `tests/eval/test_cham_minh_hoa.py` (hàm dựng khối khoảng dòng 45–70): dựng `BoDuLieu`/`CotDuLieu` không khớp mô hình thật:
  - `CotDuLieu(kieu="chu")` và `kieu="so"`: kiểu hợp lệ chỉ là `dinh_luong | thu_tu | danh_muc | thoi_gian | logic` → dùng `danh_muc` và `dinh_luong`;
  - `BoDuLieu(ten="d1")`: trường đúng là `ma` (ví dụ `"ds-1"`), và `"du_lieu"` trong lớp phải trỏ cùng mã;
  - `ma_hoa` theo ngữ pháp `mh-1` là `{"x": {"cot": "moc"}, "y": {"cot": "gia_tri"}}`, không phải chuỗi;
  - `nguon` là mã căn cứ dạng `"ca:xet_nghiem"`/`"tinh:…"`, không phải nhãn "Xét nghiệm [1]".
  Rà mọi chỗ khác trong tệp test dựng `KhoiMinhHoa` theo cùng quy tắc.
- `uv run ruff format --check app/eval`: `app/eval/hoi_dap.py` cần định dạng lại 3 chỗ. Sửa đúng như ruff muốn (gộp thành một dòng vì vừa ≤ giới hạn độ dài dòng của kho):
  - dòng ~1027: `visual_passed = sum(\n        1 for row in visual_rows if row.tieu_chi.minh_hoa is not None and row.tieu_chi.minh_hoa.dat\n    )`;
  - dòng ~1533 và ~1640: `expected_has_visual = (\n                question.ky_vong.minh_hoa.co_hinh if question.ky_vong.minh_hoa is not None else None\n            )`.

Không đổi gì khác. Ghi tiếp mục "fix-1" vào `plan/briefs/VZ5-bao-cao.md`.

**Cấm:** như brief VZ5.
