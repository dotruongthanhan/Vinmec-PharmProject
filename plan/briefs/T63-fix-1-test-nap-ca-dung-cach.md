# T63-fix-1 – Test T63 nạp ca đúng cách

Agent: agy `gemini-4-hydrogen-high`. **Không gọi shell, không gọi mạng.**

## Claude review T63 ngày 19/11

**Luật đúng.** Claude gọi `GET /api/cases/{id}` cho cả 66 ca, kết quả yếu tố 1:
- 58 `dat`, 5 `can_xem`, 3 `khong_du_du_lieu`.
- DEMO-06, HS-010, HS-013: dị ứng Penicillin ra `di_ung_cheo`.
- HS-011: Sulfonamid ra `di_ung_cheo`.
- HS-056: trùng hoạt chất sulfamethoxazole.
- DEMO-03, HS-012, HS-038: thiếu thông tin dị ứng ra `khong_du_du_lieu`.

**Test sai.** Pytest toàn kho có 1.352 qua và **7 trượt**, đều ở `tests/rules/test_allergy_runtime.py`.
- Lỗi: `ValidationError: 9 validation errors for CaBenh` (`ca_id` / `mo_ta_ngan` / `y_lenh_cho_duyet` missing; `ho_so_id`, `kich_ban_id`, `la_gia_lap`, `phien_ban_sinh` extra).
- Nguyên nhân: test nạp thẳng tệp `data/mock/hoso_gia_lap/HS-*.json` thành `CaBenh`. Tệp hồ sơ có nhiều đợt điều trị, phải đi qua `app.db.reader.load_source_cases(ROOT)` để ra khung nhìn `CaBenh`. Xem cách `tests/api/test_interaction_runtime.py` lấy HS-024. Ca demo (`data/mock/demo`) cũng lấy từ `load_source_cases`.

## Sửa

1. Trong `tests/rules/test_allergy_runtime.py`, lấy ca bằng `load_source_cases(ROOT)` rồi lọc theo `ca_id`. Tham số hoá theo `ca_id`, không theo đường dẫn tệp.
   - Giữ kỳ vọng như kết quả API ở trên.
   - Mã dòng dùng đúng `chi_tiet_y_lenh_id` mà khung nhìn trả về. Đọc chúng từ ca đã nạp, không đoán.
2. Đổi kỳ vọng HS-010 / HS-013 / DEMO-06: penicillin ↔ amoxicillin hay piperacillin ra `di_ung_cheo`, đúng như API đang trả.
3. Cập nhật bảng 66 ca trong `plan/reports/T63.md` theo kết quả trên. Ghi rõ bảng cũ là suy luận tĩnh, đã thay bằng kết quả API do Claude chạy.

## Phạm vi

- **Được sửa:** `tests/rules/test_allergy_runtime.py`, `plan/reports/T63.md` (thêm mục "## T63-fix-1").
- **Cấm:** sửa mã ứng dụng, sửa dữ liệu, commit.

## Nghiệm thu (Claude chạy)

`uv run pytest -q -p no:cacheprovider` toàn kho 0 trượt. Chạy thêm một lần với `CDSS_PROFILE=test`.
