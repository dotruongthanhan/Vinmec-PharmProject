# T69 – Nối luật D4–D7 vào engine và registry; chuyển luật kháng sinh đồ sang yếu tố 6

Agent: **agy Gemini 4 Hydrogen xhigh**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Claude tự chạy `ruff`, `pytest`, gọi API thật khi review.

Chạy song song với T71-fix-1 (chỉ sửa `toxicity.py` + test của nó; bạn **không** đụng hai tệp đó).

## Đọc trước

- `AGENTS.md`; `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md` mục 5.0, Đợt D4–D7.
- `app/rules/engine.py` (`run_rules_with_matrix`: bước nào cũng bọc try/except thành `loi_luat`), `app/rules/registry.py`, `app/rules/__init__.py`, `app/pipeline.py`.
- Chữ ký các luật mới (đã review đạt): `renal_dose.check(ca, rules, resolver=None)`, `hepatic.check`, `lab_threshold.check`, `drug_disease.check`, `route.check`, `max_dose.check` (đều `(ca, resolver, config=None)`), `toxicity.check(ca, resolver, config=None, renal_rules=None)`, `stewardship.check(ca, resolver, config=None)`, `required_fields.check(ca)`. Đọc docstring từng tệp để chắc.
- Test hiện có nhắc yếu tố của luật kháng sinh: `tests/rules/test_registry.py`, `tests/rules/test_antibiotic.py` (dòng ~123), `tests/domain/test_demo_cases.py` (dòng ~123).

## Phạm vi tệp

Được sửa: `app/rules/engine.py`, `app/rules/registry.py`, `app/rules/__init__.py`, `app/rules/antibiotic.py` (chỉ hằng `_YEU_TO`), `tests/rules/test_registry.py`, `tests/rules/test_antibiotic.py`, `tests/domain/test_demo_cases.py`, các tệp `data/gold/*.json` **chỉ** để đổi `yeu_to` 3 → 6 cho phát hiện kỳ vọng thuộc luật kháng sinh – kháng sinh đồ (nhận ra qua `mo_ta` nói về kháng sinh đồ / vi khuẩn kháng; liệt kê từng dòng đã đổi trong báo cáo; không chắc thì **không đổi** và ghi vào báo cáo).
Định dạng (chỉ khoảng trắng, xuống dòng, không đổi logic) cho các tệp đang lệch `ruff format`: `app/rules/allergy.py`, `allergy_config.py`, `drug_disease.py`, `hepatic.py` (cả lỗi E501 dòng ~223), `max_dose.py`, `required_fields.py`, `tests/rules/test_allergy_resolver.py`, `test_allergy_runtime.py`, `test_lab_threshold.py`, `test_renal_dose_d4.py`.
Được tạo: `tests/rules/test_engine_d4_d7.py`, `tests/api/test_d4_d7_api.py`, `plan/reports/T69.md`.

**Cấm:** `app/rules/toxicity.py`, `tests/rules/test_toxicity.py` (T71-fix-1), logic của các luật mới, `data/kb/`, `data/mock/`, `web/`, `config/`, `docs/`.

## Việc

1. **`antibiotic.py`:** `_YEU_TO = 6` (plan D5: luật kháng sinh – kháng sinh đồ thuộc "cơ địa, xét nghiệm, vi sinh", không phải yếu tố 3). Sửa test cũ kỳ vọng `yeu_to == 3` thành 6.
2. **`engine.py` – `run_rules_with_matrix`**, danh sách bước theo thứ tự yếu tố:
   - 1 `allergy`, 2 `duplicate` (giữ nguyên);
   - 3 `route`, 3 `max_dose` (**chỉ khi `resolver is not None`**);
   - 4 `interaction` (giữ điều kiện cũ);
   - 5 `toxicity` (chỉ khi có resolver; truyền `renal_rules=renal_rules`);
   - 6 `antibiotic` (đổi số yếu tố), `renal_dose` (**truyền `resolver`**), `hepatic`, `lab_threshold`, `drug_disease` (ba luật cuối chỉ khi có resolver);
   - 7 `schedule`, `required_fields` (luôn chạy), `stewardship` (chỉ khi có resolver).
   - Mỗi bước vẫn qua khối try/except hiện có (lỗi → `loi_luat` `khong_du_du_lieu` đúng yếu tố). Không đổi `_priority_key`, không đổi chữ ký `run_rules` / `run_rules_with_matrix`.
3. **`registry.py`:** thêm lớp bọc cho tám luật mới (`ma_nhom`: `route`, `max_dose`, `toxicity`, `hepatic`, `lab_threshold`, `drug_disease`, `stewardship`, `required_fields`), `RenalDoseRule` truyền `ctx.resolver`, `AntibioticRule.yeu_to = 6`; `default_rules()` trả đủ luật theo đúng thứ tự ở việc 2. Luật cần resolver trả `[]` khi `ctx.resolver is None` (các hàm luật đã làm vậy). Cập nhật `tests/rules/test_registry.py` cho danh sách mới.
4. **`__init__.py`:** xuất thêm các hàm nạp cấu hình nếu `registry` / `engine` cần; không thêm gì khác.
5. **Test engine** `tests/rules/test_engine_d4_d7.py` (resolver giả trả `KetQuaPhanGiai` dựng tay, config dựng tay truyền qua `monkeypatch` hàm `try_load_default_…` của từng module nếu cần):
   - không có resolver: kết quả giống hệt trước T69 trừ số yếu tố của luật kháng sinh (so trên một ca demo);
   - một luật mới ném ngoại lệ (monkeypatch) → phát hiện `loi_luat` đúng yếu tố, các luật khác vẫn chạy;
   - **ca tổng hợp** gentamicin + vancomycin chờ duyệt, `co_dia suy_than=co`, đủ tuổi / giới / cân nặng / creatinin cho CrCl khoảng 30 → có `doc_than_cong_don` `can_xem` `nghiem_trong` ở yếu tố 5;
   - **ca tổng hợp** hai thuốc trong `keo_dai_qt` (dùng config dựng tay) → `keo_dai_qt_cong_don` `can_luu_y`.
6. **Test API** `tests/api/test_d4_d7_api.py`: theo cách các test API hiện có dựng `TestClient` (đọc `tests/api/` để theo đúng mẫu: `AUTH_MODE=off`, `CASE_SOURCE=file`; ca lấy qua `app.db.reader.load_source_cases`, **không** nạp thẳng `HS-*.json`, không đếm `_kich_ban.json`). Bỏ qua (`pytest.skip`) nếu không có `tra_cuu.sqlite` (CI không có dữ liệu). Kiểm:
   - HS-019: có nhận định yếu tố 3 vượt liều tối đa (mô tả chứa `6000` và `4000`);
   - DEMO-02: yếu tố 6 có `lieu_than_can_chinh`;
   - HS-028: yếu tố 5 có cộng dồn độc thận;
   - không ca nào có kết luận `dat` mà `thong_tin_con_thieu` khác rỗng.
   Dùng đúng tên trường của hợp đồng API (`plan/api-hop-dong-v1.md` và bổ sung); đọc schema trong `app/api/schemas.py` trước khi viết assert.

## Nghiệm thu (Claude chạy)

- `uv run ruff check .` sạch; `uv run ruff format --check app tests` sạch (trừ `toxicity.py` do T71-fix-1 lo).
- `uv run pytest -q -p no:cacheprovider` toàn kho: không thêm test trượt.
- Claude gọi API thật 66 ca: mỗi yếu tố 1–7 có luật chạy; bất biến "không `dat` khi thiếu dữ liệu".

## Khi xong

`plan/reports/T69.md`: tệp đã sửa, dòng gold đã đổi, quyết định khi brief chưa rõ, lệnh Claude cần chạy.
