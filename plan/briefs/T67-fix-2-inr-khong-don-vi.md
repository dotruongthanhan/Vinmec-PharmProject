# T67-fix-2 – Ngưỡng xét nghiệm: INR không đơn vị bị báo "chưa quy đổi được đơn vị"; ghi chú công thức có dấu

Agent: **agy Gemini 4 Hydrogen high**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.**

## Lỗi (người dùng thấy trên web, HS-042)

"warfarin: thiếu hoặc chưa quy đổi được đơn vị xét nghiệm (inr_don_vi)". INR là tỷ số, không có đơn vị: trong ca `don_vi` của INR là `""` hoặc `null`; trong `data/kb/nguong_xet_nghiem.json` điều kiện INR có `don_vi_nhan: null`, `don_vi_ca: null`, `he_so_ca_sang_nhan: 1`. Brief T67 ghi "điều kiện không có `don_vi_ca` → không đổi được đơn vị", nên luật hiểu `null` là thiếu. Sai: với dữ liệu hiện có, `don_vi_ca: null` **kèm** `he_so_ca_sang_nhan` có số nghĩa là **xét nghiệm không đơn vị**.

## Sửa – `app/rules/lab_threshold.py`

- Điều kiện có khoá `he_so_ca_sang_nhan` là số và `don_vi_ca` là `null` / `""`: chấp nhận khi đơn vị trong ca là `None` hoặc chuỗi rỗng (sau `strip()`); đơn vị ca khác rỗng → vẫn là "không đổi được đơn vị".
- Điều kiện thiếu hẳn khoá `he_so_ca_sang_nhan` → giữ hành vi cũ (không đổi được).
- Test mới trong `tests/rules/test_lab_threshold.py`: INR 4,5 với `don_vi=""` → `can_xem` (vượt 4,0); INR 2,5 với `don_vi=None` → không cảnh báo theo dòng `> 4` và trong khoảng 2–3; INR có `don_vi="mmol/L"` (sai) → `khong_du_du_lieu` hậu tố `_don_vi`.

## Sửa nhỏ – `app/calc/hepatic.py`, `cardiac.py`, `electrolyte.py`

Chuỗi `ghi_chu` đang viết không dấu ("Hang B", "Thanh phan", "Gia tri theo mg/dL", "Dung albumin_binh_thuong mac dinh"). Viết lại bằng tiếng Việt có dấu ("Hạng B", "Thành phần", …); sửa assert tương ứng trong `tests/calc/`.

## Phạm vi

Sửa: `app/rules/lab_threshold.py`, `tests/rules/test_lab_threshold.py`, `app/calc/hepatic.py`, `app/calc/cardiac.py`, `app/calc/electrolyte.py`, test tương ứng trong `tests/calc/`. Tạo `plan/reports/T67-fix-2.md`. Cấm đụng tệp khác (một agent khác đang sửa các test API / engine cũ).

## Nghiệm thu (Claude chạy)

`uv run ruff check`, `uv run pytest -q -p no:cacheprovider tests/rules/test_lab_threshold.py tests/calc`; Claude mở HS-042 trên web: hết dòng `inr_don_vi`, INR được so với ngưỡng.

## Bổ sung (Claude, 19/11 16:20) – 3 test cũ còn giả định bộ luật trước T69

Cùng loại với T69-fix-1; chỉ cập nhật kỳ vọng, không sửa logic ứng dụng. Được sửa thêm hai tệp test này.

- `tests/api/test_ai_routes.py::test_ai_endpoints_lifecycle_sources_and_ai_feedback`: kỳ vọng DEMO-02 có 2 mục, nay 4 (thêm `khang_sinh_can_phe_duyet`, `lieu_toi_da_khong_co_nguon`). Kiểm theo `ma_luat` cần thiết cho luồng AI, không so số lượng cứng.
- `tests/api/test_interaction_matrix.py::test_matrix_links_to_presented_findings_without_mutating_inputs`: `so_luat_da_chay == 6`, nay 14.
- `tests/api/test_interaction_matrix.py::test_matrix_is_null_without_running_factor_four`: `so_luat_da_chay == 5`, nay 13 (không có chỉ mục tương tác). Tính số từ danh sách luật thật thay vì số cứng nếu được.
