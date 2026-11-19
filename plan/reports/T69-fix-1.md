# Báo cáo T69-fix-1 — Cập nhật test cũ theo bộ luật 14 luật (D4–D7) và sửa E501

> Phiên làm việc chỉ đọc và ghi tệp theo đúng chỉ thị của brief (không gọi công cụ shell, không gọi mạng; không sửa logic ứng dụng, `data/`, `web/`, `config/`).

## 1. Tệp đã sửa / tạo

### Ngắt dòng lỗi E501 (> 100 ký tự, không đổi logic)

- [app/rules/allergy.py](file:///D:/create/Vinmec-PharmProject/app/rules/allergy.py#L354-L357): ngắt dòng tham số `mo_ta` trong `_build_direct_overlap_finding` thành 2 chuỗi f-string trong ngoặc đơn (trước đó dài 101 ký tự).
- [app/rules/required_fields.py](file:///D:/create/Vinmec-PharmProject/app/rules/required_fields.py#L55-L58): ngắt dòng tham số `mo_ta` trong `check` thành 2 chuỗi f-string trong ngoặc đơn (trước đó dài 102 ký tự).

### Cập nhật kỳ vọng kiểm thử theo bộ 14 luật

- [tests/test_container.py](file:///D:/create/Vinmec-PharmProject/tests/test_container.py#L16-L63):
  - `test_test_container_protocols_and_caching` và `test_dev_container_is_lazy_and_independent_of_cwd`: thay `len(container.rules) == 6` bằng so sánh `len(container.rules) == len(default_rules())` và `[rule.ma_nhom for rule in container.rules] == _EXPECTED_RULE_GROUPS` (đầy đủ 14 nhóm từ `allergy` đến `stewardship`).
- [tests/api/test_interaction_runtime.py](file:///D:/create/Vinmec-PharmProject/tests/api/test_interaction_runtime.py):
  - `test_get_hs024_links_major_pair_and_reuses_evaluation` (dòng 89): cập nhật `so_luat_da_chay == len(default_rules())` (14).
  - `test_missing_index_keeps_five_rules_and_warns_once` (dòng 168–182):
    - Cập nhật `so_luat_da_chay == len(default_rules()) - 1` (13), khớp `app/api/presenter.py:394` (`len(default_rules()) - (0 if interaction_ran else 1)` — presenter chỉ trừ 1 khi yếu tố 4 chưa chạy, kể cả khi thiếu `tra_cuu`).
    - Bổ sung kiểm chứng hành vi thực tế: các luật không cần chỉ mục (`di_ung_khong_co`, `trung_hoat_chat_khong_co`, `lich_dung_phu_hop`) luôn chạy; khi `missing in {"tra_cuu", "both"}` (không có `resolver`), `"3. Chỉ định, liều, đường dùng"` nằm trong `yeu_to_chua_kiem` và các phát hiện cần resolver (`thuoc_benh_ddinter`, `lieu_toi_da_khong_co_nguon`) **không** xuất hiện; khi `missing == "tuong_tac"` (có `resolver`), hai phát hiện đó có mặt. Giữ nguyên kiểm tra `len(warnings) == 1`.
  - `test_pipeline_retains_old_rules_and_refreshes_matrix` (dòng 255–259) và `test_interaction_failure_keeps_old_findings` (dòng 298–302): đổi từ so khớp nguyên danh sách `yeu_to not in {2, 4}` sang kiểm **tập con** các phát hiện cũ (`yeu_to != 2`) vẫn có mặt nguyên vẹn trong `result.phat_hien`, đồng thời xác nhận `thuoc_benh_ddinter` xuất hiện.
- [tests/api/test_routes.py](file:///D:/create/Vinmec-PharmProject/tests/api/test_routes.py):
  - `test_demo02_detail` (dòng 90–99, 115): cập nhật `len(findings) == 3` với đúng thứ tự `["lieu_than_can_chinh", "khang_sinh_can_phe_duyet", "lieu_toi_da_khong_co_nguon"]`, giữ kiểm tra mục liều thận meropenem đứng đầu (`findings[0]`) cùng các mục yếu tố 7 và yếu tố 3; cập nhật `so_luat_da_chay == 14`.
  - `test_feedback_persists_latest_without_rerunning` (dòng 175–204): phản hồi `"dong_y"` cho mục đầu tiên rồi lặp phản hồi cho toàn bộ các mục cần chú ý còn lại (`findings[1:]`) trước khi kiểm `da_phan_hoi_het is True`; giữ kiểm `calls == 1` trước khi gọi danh sách hàng đợi và `calls == before` sau khi sửa phản hồi; cập nhật số dòng `phan_hoi.jsonl` thành `len(findings) + 1`.
- [tests/rules/test_engine_demo.py](file:///D:/create/Vinmec-PharmProject/tests/rules/test_engine_demo.py#L141-L151):
  - `test_engine_isolates_rule_runtime_error`: bỏ so nguyên danh sách thứ tự `ket_luan`, kiểm tra theo `ma_luat` (`loi_luat`, `di_ung_khong_co`, `lich_dung_thieu_lieu`, `y_lenh_thieu_truong`) và `ket_luan` tương ứng của từng luật.
- [tests/rules/test_engine_d4_d7.py](file:///D:/create/Vinmec-PharmProject/tests/rules/test_engine_d4_d7.py#L28-L117):
  - `test_engine_without_resolver_matches_pre_t69_except_antibiotic_factor`: bổ sung `*required_fields.check(ca)` vào `expected_legacy` (vì `required_fields` luôn chạy kể cả khi không có `resolver`), sửa `ma_luat` mong đợi của ca `DEMO-04` theo `app/rules/antibiotic.py` thành `"khang_sinh_vi_sinh_nhay"` và kiểm `yeu_to == 6` cho mọi phát hiện `khang_sinh_*`.

### Tệp không sửa

- `tests/architecture/test_notebook.py`: giữ nguyên theo chỉ thị brief.
- `tests/api/test_interaction_matrix.py`: quan sát thấy dòng 46 và 60 vẫn kỳ vọng `so_luat_da_chay == 6` và `5`, không sửa vì nằm ngoài phạm vi tệp của brief.

## 2. Lưu ý kiểm tra và nghiệm thu (Claude chạy)

Chưa chạy `ruff` hay `pytest` trong phiên này vì không dùng công cụ shell. Cần chạy để nghiệm thu:

```powershell
uv run ruff format --check app/rules/allergy.py app/rules/required_fields.py tests/test_container.py tests/api/test_interaction_runtime.py tests/api/test_routes.py tests/rules/test_engine_demo.py tests/rules/test_engine_d4_d7.py
uv run ruff check .
uv run pytest -q -p no:cacheprovider
```
