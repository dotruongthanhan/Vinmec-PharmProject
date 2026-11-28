# T72 – Luật D7 (yếu tố 7): kháng sinh quản lý theo QĐ 5631, y lệnh thiếu trường bắt buộc

Agent: **agy Gemini 4 Hydrogen**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Claude tự chạy `ruff`, `pytest` khi review.

Chạy song song với T67, T68, T71 và sub dữ liệu T70 (đang dựng `data/kb/khang_sinh_quan_ly.json`; **tệp có thể chưa có**, test dùng config dựng tay). Không sửa `engine.py` / `registry.py`: việc nối để cho T69. Không sửa `schedule.py` (luật lịch dùng hiện có giữ nguyên).

## Đọc trước

- `AGENTS.md` (quy tắc 6, 7, 8); `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md` mục 2 và **Đợt D7**.
- `plan/briefs/T70-du-lieu-d6-d7-doc-tinh-khang-sinh.md` **việc 2**: lược đồ `data/kb/khang_sinh_quan_ly.json`.
- `app/rules/types.py`, `app/rules/schedule.py` (để không trùng), `app/rules/allergy.py` + `allergy_config.py` (mẫu nạp bảng lười, resolver, căn cứ tài liệu), `app/kb/names.py` (`normalize_key`), `app/domain/models.py` (`ChiTietYLenh`, `DienBien`, `Thuoc.la_khang_sinh`).

## Phạm vi tệp

Được tạo: `app/rules/stewardship.py`, `app/rules/required_fields.py`, `app/rules/d7_config.py`, `tests/rules/test_stewardship.py`, `tests/rules/test_required_fields.py`, `plan/reports/T72.md`.

**Cấm đụng:** `engine.py`, `registry.py`, `__init__.py`, `schedule.py`, `antibiotic.py`, mọi luật / test đã có, tệp của T67, T68, T71 (`toxicity.py`, `d6_config.py`), `data/`, `config/`, `web/`, `docs/`, `plan/` (trừ báo cáo của bạn).

## Luật 1 – `stewardship.py`: kháng sinh cần phê duyệt / ưu tiên quản lý

`check(ca, resolver, config=None) -> list[PhatHien]`, `yeu_to = 7`. `resolver is None` hoặc không nạp được bảng → `[]`.

- Với mỗi dòng **chờ duyệt**, hoạt chất (qua resolver) nằm trong `khang_sinh[].hoat_chat_ids`:
  - Tìm ghi nhận hội chẩn / phê duyệt trong hồ sơ: `ca.dien_bien` có `normalize_key(noi_dung)` hoặc `normalize_key(loai_ho_so)` chứa một trong các cụm `hoi chan`, `phe duyet`. Hồ sơ chưa có trường có cấu trúc cho việc này; đây là cách dò tạm, ghi rõ trong mô tả là "dò theo chữ trong diễn biến".
  - Nhóm `phe_duyet_truoc`: không thấy ghi nhận → `can_xem` `can_luu_y`, `ma_luat="khang_sinh_can_phe_duyet"`, mô tả gồm tên nhóm và `yeu_cau` nguyên văn của văn bản; thấy ghi nhận → `dat` `thong_tin`, `ma_luat="khang_sinh_da_co_hoi_chan"`, căn cứ `du_lieu` là `dien_bien_id` và đoạn chữ khớp (≤ 200 ký tự).
  - Nhóm khác (ví dụ `uu_tien_quan_ly`): `can_xem` `thong_tin`, `ma_luat="khang_sinh_uu_tien_quan_ly"`, mô tả `yeu_cau` nguyên văn.
- Căn cứ `tai_lieu` luôn có: `"QĐ 5631/QĐ-BYT (bản sao thứ cấp), trang <trang_pdf>: <ten_nhom_van_ban> — <url> (chờ dược sĩ duyệt)"`.
- Kháng sinh không có trong bảng: không sinh phát hiện. **Không** tự đặt ngưỡng thời gian dùng kháng sinh (plan: chưa có nguồn).

## Luật 2 – `required_fields.py`: y lệnh thiếu trường bắt buộc

`check(ca) -> list[PhatHien]`, `yeu_to = 7`, không cần bảng hay resolver.

- Với mỗi dòng **chờ duyệt** có `loai_san_pham == "thuoc"`: trường thiếu khi `None` hoặc chuỗi rỗng sau `strip()`:
  - `lieu_moi_lan`, `don_vi_lieu`, `duong_dung`;
  - tần suất: thiếu khi **cả ba** `tan_suat`, `so_lan_moi_ngay`, `khoang_cach_gio` đều trống (ghi tên trường là `tan_suat`).
- Có trường thiếu → **một** phát hiện cho dòng: `can_xem` `can_luu_y`, `ma_luat="y_lenh_thieu_truong"`, mô tả liệt kê trường thiếu bằng tiếng Việt (liều mỗi lần, đơn vị liều, đường dùng, tần suất), căn cứ `du_lieu` là `chi_tiet_y_lenh_id`.
- Không thiếu → không sinh phát hiện (luật này chỉ báo khi có vấn đề; các luật khác của yếu tố 7 lo phần "đạt").
- Đây là phát hiện về **y lệnh** (kê thiếu), không phải "không đủ dữ liệu của người bệnh", nên dùng `can_xem`, không dùng `khong_du_du_lieu`.

## Test

- `test_stewardship.py` (resolver giả, config dựng tay, ca dựng bằng pydantic): nhóm `phe_duyet_truoc` không có diễn biến hội chẩn → `can_xem`; có diễn biến "Hội chẩn khoa ... đồng ý dùng meropenem" → `dat` (kiểm có bỏ dấu); nhóm `uu_tien_quan_ly` → `thong_tin`; kháng sinh không trong bảng → không sinh; thuốc ở thuốc đang dùng (không chờ duyệt) → không sinh; test nạp tệp thật `pytest.skip` nếu chưa có.
- `test_required_fields.py`: thiếu từng trường; tần suất chỉ có `khoang_cach_gio` → không thiếu; `loai_san_pham="tpcn"` → bỏ qua; đủ trường → `[]`.

## Nghiệm thu (Claude chạy)

`uv run ruff check .`, `uv run ruff format --check` trên tệp bạn tạo, `uv run pytest -q -p no:cacheprovider tests/rules`.

## Khi xong

`plan/reports/T72.md`: tệp đã tạo, quyết định khi brief chưa rõ, nghi vấn, lệnh Claude cần chạy.
