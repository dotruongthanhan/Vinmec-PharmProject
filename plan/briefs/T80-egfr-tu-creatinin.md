# T80 – Ngưỡng xét nghiệm: dùng eGFR ước tính từ creatinin khi ca không có eGFR

Agent: **agy Gemini 4 Hydrogen high**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Chạy song song với T79: **chỉ** sửa `app/rules/lab_threshold.py` và test của nó.

## Lỗi (Claude, hồ sơ thử TEST-CLAUDE-02)

Nam 72 tuổi, creatinin 230 µmol/L, đang kê metformin. `data/kb/nguong_xet_nghiem.json` có quy tắc metformin theo **eGFR** (nhãn FDA: eGFR < 30 → chống chỉ định). Ca chỉ có creatinin, không có xét nghiệm `egfr` → luật ra `khong_du_du_lieu` "thiếu … (egfr)" và **bỏ sót chống chỉ định**. Luật liều thận (`renal_dose`) đã tự tính CrCl Cockcroft-Gault từ creatinin; ngưỡng xét nghiệm thì chưa.

## Sửa

- Trong `app/rules/lab_threshold.py`: khi điều kiện cần `ma_xet_nghiem == "egfr"` và ca **không có** kết quả `egfr`, nhưng có creatinin (mới nhất), tuổi, giới → tính bằng hàm có sẵn `app/calc/renal.py` (CKD-EPI 2021, không chủng tộc; đọc hàm để biết tham số, đổi đơn vị creatinin bằng `app/calc/units.py`). Đơn vị kết quả mL/min/1,73 m².
- Ca có `egfr` đo được → dùng giá trị đo như cũ (ưu tiên).
- Nhận định ghi rõ nguồn số: ví dụ "eGFR ước tính 25,4 mL/phút/1,73 m² (CKD-EPI 2021 từ creatinin 230 µmol/L, …)". Thiếu tuổi / giới / creatinin → giữ `khong_du_du_lieu` như cũ, liệt kê đúng trường thiếu.
- Không thêm hằng số mới; không đổi `data/`.

## Test (`tests/rules/test_lab_threshold.py`)

1. Nam 72 tuổi, creatinin 230 µmol/L, metformin, không có `egfr` → eGFR ≈ 25,4 (Claude tự tính: 142 × (2,602/0,9)^−1,200 × 0,9938^72, creatinin 230/88,4 = 2,602 mg/dL → ≈ 25,4; dùng `approx(abs=0.5)`) → nhận định `can_xem`, theo dòng "eGFR < 30: chống chỉ định".
2. Ca có cả `egfr` đo = 50 và creatinin cao → dùng 50 (không cảnh báo < 30).
3. Thiếu giới tính → `khong_du_du_lieu`, nêu thiếu giới tính.

## Phạm vi

`app/rules/lab_threshold.py`, `tests/rules/test_lab_threshold.py`. Định dạng `ruff format`. Báo cáo `plan/reports/T80.md`.
