# T69-fix-1 – Cập nhật test cũ theo bộ luật D4–D7 đã nối; sửa E501

Agent: **agy Gemini 4 Hydrogen xhigh**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.**

## Bối cảnh

T69 đã nối 8 luật mới vào `engine.py` / `registry.py` (review đạt: API thật 66 ca, 0 lỗi luật, 0 "đạt" khi thiếu dữ liệu; web hiện đủ 7 yếu tố). Toàn kho Claude chạy: **1.457 qua, 17 trượt**. Claude đã đọc lý do: các test cũ còn giả định bộ luật trước T69. **Không sửa code ứng dụng** để test qua; chỉ cập nhật kỳ vọng của test cho đúng bộ luật mới, giữ nguyên ý nghĩa mỗi test kiểm.

## Test trượt và lý do (Claude đã xác minh)

| Test | Lý do | Cách sửa |
|:--|:--|:--|
| `tests/test_container.py::test_test_container_protocols_and_caching`, `::test_dev_container_is_lazy_and_independent_of_cwd` | `assert len(container.rules) == 6`, nay 14 | So với `len(default_rules())` hoặc danh sách `ma_nhom` mong đợi đầy đủ |
| `tests/api/test_interaction_runtime.py::test_missing_index_keeps_five_rules_and_warns_once[tra_cuu / tuong_tac / both]` | Đếm "5 luật" còn chạy khi thiếu chỉ mục, nay 13 (hoặc theo cấu hình) | Đếm lại theo bộ luật mới; ý nghĩa test: thiếu chỉ mục thì luật không cần chỉ mục vẫn chạy và chỉ cảnh báo một lần. Khi thiếu `tra_cuu` (không có resolver) thì các luật cần resolver **không** chạy: tính đúng số đó |
| `tests/api/test_interaction_runtime.py::test_pipeline_retains_old_rules_and_refreshes_matrix`, `::test_interaction_failure_keeps_old_findings`, `::test_get_hs024_links_major_pair_and_reuses_evaluation[file / db]` | So nguyên danh sách phát hiện; nay HS-024 có thêm `thuoc_benh_ddinter` (amiodaron × rung nhĩ) và các nhận định D4–D7 khác | So **tập con**: các phát hiện cũ vẫn có mặt nguyên vẹn (cùng `ma_luat`, `ket_luan`, `muc_do`, dòng y lệnh), hoặc lọc theo các `ma_luat` mà test đó nhắm tới |
| `tests/api/test_routes.py::test_demo02_detail` | Kỳ vọng DEMO-02 có 1 mục cần chú ý, nay 3 (thêm `khang_sinh_can_phe_duyet` yếu tố 7, `lieu_toi_da_khong_co_nguon` yếu tố 3) | Kiểm mục liều thận meropenem vẫn đứng đầu và có đủ trường; số mục = 3 hoặc kiểm theo `ma_luat` |
| `tests/api/test_routes.py::test_feedback_persists_latest_without_rerunning` | Phản hồi một mục rồi kỳ vọng `da_phan_hoi_het is True`; nay DEMO-02 có 3 mục | Phản hồi **mọi** mục cần chú ý rồi mới kiểm `da_phan_hoi_het`; vẫn kiểm không chạy lại luật (`calls == 1`) |
| `tests/rules/test_engine_demo.py::test_engine_isolates_rule_runtime_error` | Kỳ vọng thứ tự `["can_xem","khong_du_du_lieu","dat"]`; nay có thêm `y_lenh_thieu_truong` / `can_xem` khác | Giữ ý: luật ném lỗi sinh đúng một `loi_luat`, các luật khác vẫn có kết quả; bỏ so nguyên thứ tự, kiểm theo `ma_luat` |
| `tests/rules/test_engine_d4_d7.py::test_engine_without_resolver_matches_pre_t69_except_antibiotic_factor` (test T69 tự viết) | Phần so `findings == expected_legacy` qua, nhưng `assert len(abx) == 1` với `ma_luat == "khang_sinh_co_vi_sinh_phu_hop"` sai: DEMO-04 không sinh mã đó | Đọc `app/rules/antibiotic.py` và `data/mock/demo/DEMO-04.json` để lấy đúng `ma_luat` mà ca sinh ra, rồi kiểm `yeu_to == 6` cho mọi phát hiện của luật kháng sinh. Lưu ý: **không có resolver** thì `required_fields` vẫn chạy (luôn chạy) — nếu ca có dòng thiếu trường, cộng nó vào `expected_legacy` |

**Không sửa** `tests/architecture/test_notebook.py` (trượt do biến môi trường `.env` trên máy, không liên quan).

## Ruff

- `app/rules/allergy.py:354` và `app/rules/required_fields.py:55`: E501 (dòng > 100 ký tự). Ngắt dòng, không đổi logic.
- Các tệp lệch `ruff format` (chỉ khoảng trắng, xuống dòng; dòng tối đa 100; theo `pyproject.toml`): làm nếu bạn chắc; không chắc thì bỏ qua, Claude sẽ xử lý định dạng riêng.

## Phạm vi tệp

Sửa: các tệp test ở bảng trên, `app/rules/allergy.py` và `app/rules/required_fields.py` (chỉ ngắt dòng). Tạo `plan/reports/T69-fix-1.md`. Cấm sửa logic trong `app/`, cấm sửa `data/`, `web/`, `config/`.

## Nghiệm thu (Claude chạy)

`uv run ruff check .` sạch; `uv run pytest -q -p no:cacheprovider` toàn kho: chỉ còn `test_notebook` trượt (nếu `.env` vẫn như cũ).
