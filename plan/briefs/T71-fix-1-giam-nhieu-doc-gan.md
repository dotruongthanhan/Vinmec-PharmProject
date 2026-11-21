# T71-fix-1 – Luật D6: bỏ nhận định "thiếu ALT/AST" thừa, sửa định dạng

Agent: **agy Gemini 4 Hydrogen high**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.**

Chạy song song với T69 (T69 không đụng `toxicity.py`).

## Bối cảnh (Claude chạy luật thật trên 66 ca với `data/kb/doc_tinh.json`)

Đúng: HS-028 methotrexat + ibuprofen `doc_than_cong_don` `nghiem_trong`; HS-029 valproat ALT 280 > 40 `doc_gan_men_gan_tang`. Nhiễu: **39** phát hiện `doc_gan_thieu_xet_nghiem` (`khong_du_du_lieu`) cho mọi thuốc LiverTox A/B (ceftriaxon, metformin, insulin…) ở ca không có ALT/AST. Nhãn không bắt buộc xét nghiệm men gan trước khi dùng các thuốc này, nên đây không phải "thiếu dữ liệu để thẩm định" mà là thiếu căn cứ để báo.

## Phạm vi tệp

Sửa: `app/rules/toxicity.py`, `tests/rules/test_toxicity.py`. Tạo `plan/reports/T71-fix-1.md`. Cấm đụng mọi tệp khác.

## Việc

1. Luật `doc_gan_livertox`: ca **không có** kết quả ALT lẫn AST dạng số → **không sinh phát hiện** (bỏ mã `doc_gan_thieu_xet_nghiem` cho trường hợp này). Có kết quả nhưng thiếu `nguong_tren` → giữ `khong_du_du_lieu` `["nguong_tren_alt_ast"]` (vì có số mà không so được). Các nhánh khác giữ nguyên.
2. Sửa test tương ứng (test "không ALT/AST" giờ kỳ vọng không có phát hiện `doc_gan_*`).
3. Định dạng theo `ruff format` (dòng tối đa 100, ngoặc kép, dấu phẩy cuối theo cấu hình `pyproject.toml`): `toxicity.py` quanh dòng 169 đang lệch.

## Nghiệm thu (Claude chạy)

`uv run ruff check app/rules/toxicity.py tests/rules/test_toxicity.py`, `uv run ruff format --check` hai tệp đó, `uv run pytest -q -p no:cacheprovider tests/rules/test_toxicity.py`; chạy trên 66 ca: `doc_gan_thieu_xet_nghiem` = 0, HS-029 vẫn `doc_gan_men_gan_tang`.
