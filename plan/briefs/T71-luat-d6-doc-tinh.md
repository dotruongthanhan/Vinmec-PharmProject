# T71 – Luật D6 (yếu tố 5): cộng dồn độc thận, cộng dồn kéo dài QT, khoảng điều trị hẹp, độc gan LiverTox, thuốc nguy cơ cao

Agent: **agy Gemini 4 Hydrogen**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Claude tự chạy `ruff`, `pytest` khi review.

Chạy song song với T67, T68, T72 (luật khác) và sub dữ liệu T70 (đang dựng `data/kb/doc_tinh.json`; **tệp có thể chưa có khi bạn chạy**, test dùng config dựng tay). Không sửa `engine.py` / `registry.py`: việc nối để cho T69.

## Đọc trước

- `AGENTS.md` (nhất là quy tắc 6, 7, 8); `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md` mục 2 và **Đợt D6**.
- `plan/briefs/T70-du-lieu-d6-d7-doc-tinh-khang-sinh.md` **việc 1**: lược đồ `data/kb/doc_tinh.json`.
- `app/rules/types.py` (`PhatHien`, `CanCu`, `pending_lines`, `effective_lines`, `line_label`), `app/rules/allergy.py` + `allergy_config.py` (mẫu nạp bảng lười `lru_cache` / `try_load_default_…`, resolver, `_extract_resolved_ids`, `_is_line_excluded`, căn cứ tài liệu), `app/rules/duplicate.py` (mẫu phát hiện cấp ca gom nhiều dòng), `app/domain/models.py` (`Thuoc.la_thuoc_nguy_co_cao`, `CoDia`, `KetQuaXetNghiem.nguong_tren`), `app/domain/loader.py`, `app/calc/renal.py`.

## Phạm vi tệp

Được tạo: `app/rules/toxicity.py`, `app/rules/d6_config.py`, `tests/rules/test_toxicity.py`, `plan/reports/T71.md`.

**Cấm đụng:** `app/rules/engine.py`, `registry.py`, `__init__.py`, mọi luật / test đã có, tệp của T67 (`renal_dose.py`, `hepatic.py`, `lab_threshold.py`, `drug_disease.py`, `d4_config.py`), T68 (`route.py`, `max_dose.py`, `d5_config.py`), T72 (`stewardship.py`, `required_fields.py`, `d7_config.py`), `data/`, `config/`, `web/`, `docs/`, `plan/` (trừ báo cáo của bạn).

## Quy ước

- `yeu_to = 5`. Một hàm chung `check(ca, resolver, config=None, renal_rules=None) -> list[PhatHien]` gọi năm hàm con dưới đây; mỗi hàm con cũng kiểm thử riêng được. `resolver is None` → `[]`; config không nạp được → chỉ chạy phần "thuốc nguy cơ cao" (không cần bảng).
- "Thuốc cùng lúc" = `effective_lines(ca)` (y lệnh chờ duyệt + thuốc đang dùng còn hiệu lực). Phát hiện cộng dồn chỉ sinh khi **ít nhất một** thuốc liên quan nằm trong y lệnh chờ duyệt (không báo lại tổ hợp cũ hoàn toàn). `chi_tiet_y_lenh_id` của phát hiện = các dòng liên quan.
- Bỏ dòng loại trừ theo resolver. Dòng không nhận diện được hoạt chất: không tính vào tổ hợp; nếu ca có dòng như vậy thì phát hiện "không có tổ hợp" ra `khong_du_du_lieu` `["hoat_chat"]` thay vì `dat`.
- Căn cứ `tai_lieu` cho mỗi nguồn: `'<Nhãn FDA TEN (set_id=…) | LiverTox chương …>: "<trich>" — <url> (chờ dược sĩ duyệt)'`.
- **Không đặt ngưỡng số mới.** Không lặp việc D4: không so khoảng nồng độ đích, không xét khuyến cáo suy gan.

## Năm luật

1. **`doc_than_cong_don`**: ≥ 2 hoạt chất khác nhau trong `doc_than` cùng lúc → `can_xem`; mức `nghiem_trong` nếu ca có `co_dia` `suy_than` `trang_thai="co"`, ngược lại `can_luu_y`. Thêm căn cứ `tinh_toan` CrCl Cockcroft-Gault nếu tính được (dùng `cockcroft_gault` như `renal_dose.py`; thiếu đầu vào thì ghi thiếu, không chặn phát hiện). Ít hơn 2 → không sinh phát hiện.
2. **`keo_dai_qt_cong_don`**: ≥ 2 hoạt chất trong `keo_dai_qt` cùng lúc → `can_xem` `can_luu_y`; mô tả nêu tên thuốc và mục nhãn. Ít hơn 2 → không sinh.
3. **`khoang_dieu_tri_hep`**: với mỗi dòng **chờ duyệt** có hoạt chất trong danh sách: có ít nhất một kết quả xét nghiệm với `ma_xet_nghiem` thuộc `ma_xet_nghiem_nong_do` → `dat` `thong_tin`, mô tả kết quả mới nhất và thời điểm, `ma_luat="nong_do_da_theo_doi"`; không có → `can_xem` `can_luu_y`, `ma_luat="nong_do_chua_theo_doi"`, mô tả "nhãn khuyến cáo theo dõi nồng độ; hồ sơ chưa có kết quả".
4. **`doc_gan_livertox`**: dòng chờ duyệt có hoạt chất với `likelihood_score` ∈ `A`, `B`: lấy ALT, AST mới nhất; giá trị > `nguong_tren` của chính kết quả đó (ngưỡng phòng xét nghiệm trong ca, không tự đặt) → `can_xem` `can_luu_y`, `ma_luat="doc_gan_men_gan_tang"`; có kết quả nhưng không vượt → `dat` `thong_tin`; không có ALT/AST hoặc thiếu `nguong_tren` → `khong_du_du_lieu` `["alt_ast"]` (hoặc `["nguong_tren_alt_ast"]`), `ma_luat="doc_gan_thieu_xet_nghiem"`. Điểm C, D, E, X: không sinh phát hiện. Mô tả luôn nêu điểm LiverTox.
5. **`thuoc_nguy_co_cao`**: dòng chờ duyệt có `Thuoc.la_thuoc_nguy_co_cao=True` (cờ danh mục của viện trong ca) → `can_xem` `thong_tin`, `ma_luat="thuoc_nguy_co_cao"`, mô tả "thuốc thuộc danh mục nguy cơ cao của viện: kiểm tra kép liều, đường dùng". Không cần bảng.

## Test (`tests/rules/test_toxicity.py`; ca dựng bằng pydantic, resolver giả, config dựng tay)

- Tình huống plan: gentamicin + vancomycin + CrCl khoảng 30 (tự tính trong test bằng `cockcroft_gault`) và `co_dia suy_than=co` → `doc_than_cong_don` `can_xem` `nghiem_trong`; không có cơ địa suy thận → `can_luu_y`.
- Hai thuốc độc thận đều nằm ở thuốc đang dùng (không có ở y lệnh chờ duyệt) → không sinh.
- Một thuốc độc thận → không sinh.
- QT: hai thuốc → `can_luu_y`; một thuốc → không.
- Nồng độ: có `digoxin` → `dat`; không → `nong_do_chua_theo_doi`.
- LiverTox A + ALT 120 (nguong_tren 40) → `can_xem`; ALT 30 → `dat`; không ALT/AST → `khong_du_du_lieu`; điểm C → không sinh.
- Nguy cơ cao: cờ true → `thong_tin`; false → không.
- Dòng không nhận diện được + một thuốc độc thận khác → phát hiện `khong_du_du_lieu` hoặc không có `dat`.
- Một test nạp `data/kb/doc_tinh.json` thật: `pytest.skip` nếu tệp chưa có.
- Mọi `khong_du_du_lieu` có `muc_do=None`.

## Nghiệm thu (Claude chạy)

`uv run ruff check .`, `uv run ruff format --check app/rules/toxicity.py app/rules/d6_config.py tests/rules/test_toxicity.py`, `uv run pytest -q -p no:cacheprovider tests/rules`.

## Khi xong

`plan/reports/T71.md`: tệp đã tạo, quyết định khi brief chưa rõ, nghi vấn, lệnh Claude cần chạy.
