# T63-fix-2 – Hai test còn sai kỳ vọng

Agent: agy `gemini-4-hydrogen-high`. **Không gọi shell, không gọi mạng.**

Claude chạy toàn kho: 1.357 qua, 2 trượt. Cả hai là **lỗi trong test**; luật và bộ phân giải đúng. Claude chạy lại `python -m app.kb.resolver report`, số dòng ca vẫn 117 phân giải / 0 một phần / 3 không nhận diện / 47 không áp dụng.

1. `tests/rules/test_allergy_resolver.py::test_multiple_matching_groups_take_highest_risk_and_merge_once`
   - Test kỳ vọng mã nhóm `BL04_PEN_AMINOCEPH_KHAC`, mã này **không có** trong bảng.
   - Mã thật trong `data/kb/di_ung_cheo.json`: `BL01_PENICILLIN_NOI_NHOM`, `BL02_AMINOPEN_AMINOCEPH_AMOX`, `BL03_AMINOPEN_AMINOCEPH_AMP`, `BL04_PEN_CEPH_R1_TUONG_TU`, `BL05_PEN_CEPH_R1_KHAC`, `BL06_PEN_CEFAZOLIN`…
   - Sửa kỳ vọng theo mã thật. Tốt hơn nữa: đọc mã từ bảng thay vì gõ cứng.
2. `tests/kb/test_resolver_d3.py::test_real_index_resolves_cephalexin_paracetamol_and_keeps_66_case_counts`
   - Lỗi `assert 67 == 66`: test đếm tệp `*.json`, gồm cả `data/mock/hoso_gia_lap/_kich_ban.json`.
   - Dùng `load_source_cases(ROOT)` (66 ca), hoặc bỏ tệp tên bắt đầu bằng `_`.
   - Giữ kỳ vọng 117 / 0 / 3 / 47.

**Được sửa:** hai tệp test trên, mục "## T63-fix-2" trong `plan/reports/T63.md`.

**Cấm:** mã ứng dụng, dữ liệu, commit.
