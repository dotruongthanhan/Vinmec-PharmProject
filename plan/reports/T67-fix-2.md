# Báo cáo T67-fix-2

Trạng thái: xong (do Claude làm thay agent code hết hạn mức, theo cho phép của người dùng).

## Đã sửa
- `app/rules/lab_threshold.py`: chỉ coi là thiếu đơn vị khi điều kiện thiếu `he_so_ca_sang_nhan`. `don_vi_ca` null/rỗng kèm hệ số nghĩa là xét nghiệm không đơn vị (INR): chấp nhận đơn vị ca `None` hoặc rỗng; đơn vị ca khác rỗng vẫn trả `<ma>_don_vi`.
- `tests/rules/test_lab_threshold.py`: thêm 3 test INR (4,5 đơn vị rỗng -> can_xem; 2,5 đơn vị None -> trong ngưỡng; đơn vị mmol/L -> khong_du_du_lieu `inr_don_vi`).
- `app/calc/hepatic.py`, `app/calc/electrolyte.py`: ghi_chu tiếng Việt có dấu; `cardiac.py` không có ghi_chu không dấu nên không đổi. Sửa assert trong `tests/calc/test_hepatic.py`, `test_electrolyte.py`.
- `tests/api/test_interaction_matrix.py`: `so_luat_da_chay` tính từ `len(default_rules())` (và trừ 1 khi không chạy tương tác).
- `tests/api/test_ai_routes.py`: không so số lượng cứng; chọn dòng luật và dòng `ai|...` theo thuộc tính, phản hồi tìm theo `nhan_dinh_id`.
