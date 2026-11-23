# Báo cáo thực hiện T105 – Gợi ý tên thuốc khi gõ

**Trạng thái:** Đã hoàn tất sửa/tạo mã nguồn và test theo brief; **chưa chạy kiểm tra tự động** (tuân thủ yêu cầu tuyệt đối không gọi công cụ shell).

---

## 1. Tệp đã tạo / sửa

### Tạo mới
- `app/kb/suggest.py`: module thuần (không I/O) chứa `DrugSuggestIndex`, `MucGoiY`, `KetQuaGoiY`, `normalize_suggest_query`, hàm trigram/Jaccard và Damerau–Levenshtein có trần.
- `tests/kb/test_suggest.py`: bộ test đơn vị thuần cho `DrugSuggestIndex` trên dữ liệu nhỏ dựng tay.
- `web/src/features/lookup/DrugNameCombobox.tsx`: thành phần combobox WAI-ARIA 1.2 dùng chung cho Tra tương tác và Tra cứu thuốc.
- `plan/briefs/T105-bao-cao.md`: báo cáo này.

### Đã sửa
- `app/api/schemas.py`: thêm `GoiYThuoc`, `KetQuaGoiYThuoc` (`extra="forbid"`) và trường tuỳ chọn `goi_y_sua: str | None = None` vào `DanhSachThuoc`.
- `app/api/lookup.py`: thêm `_strip_product_strength`, `_suggest_index` (nạp từ `_query("tra_cuu", ...)`, lưu `_CACHE`), `suggest_drugs`, và fallback trong `search_drugs` sang `_suggest_index().goi_y(q, 30)` khi truy vấn `LIKE` trả 0 hoạt chất.
- `app/api/routes.py`: thêm `GET /api/thuoc/goi-y` (khai báo trước `GET /thuoc/{hoat_chat_id}`, bắt buộc đăng nhập qua `Caller`, `q` bắt buộc `max_length=100`, `gioi_han` 1–15 mặc định 8, header `Cache-Control: private, no-store`, không ghi `q` vào log).
- `plan/api-hop-dong-v1.8-tra-cuu.md`: cập nhật giao diện `DanhSachThuoc`, bổ sung `GoiYThuoc`, `KetQuaGoiYThuoc` và mục bảng cho `GET /api/thuoc/goi-y`.
- `tests/api/test_tra_cuu.py`: bổ sung kiểm thử đăng nhập cho `/api/thuoc/goi-y`, xác thực `q` 101 ký tự / thiếu `q`, thứ tự route, fallback `/api/thuoc?q=parecetamo`, kiểm chéo `gia_tri_gui` với `POST /api/tuong-tac` và kiểm tra ngưỡng thời gian dựng chỉ mục / truy vấn.
- `web/src/api/types.ts`: bổ sung `LoaiGoiYThuoc`, `KieuKhopGoiYThuoc`, `GoiYThuoc`, `KetQuaGoiYThuoc` và `goi_y_sua?: string | null` trên `DanhSachThuoc`.
- `web/src/api/client.ts`: thêm `suggestDrugs` vào `ReviewApiClient` và `ApiClient` (`GET /thuoc/goi-y`).
- `web/src/api/index.ts`: chuyển tiếp `suggestDrugs` trên `createLazyMockClient`.
- `web/src/api/mock.ts`: cài `suggestDrugs` lọc theo tiền tố trên `MOCK_DRUGS` và cập nhật `goi_y_sua: null` trong `searchDrugs`.
- `web/src/lib/lookup.ts`: thêm các hàm thuần `splitHighlightSegments`, `formatIngredientSummary`, `setBoundedCache`, `comboboxInitialActiveIndex`, `resolveComboboxKeyDown`, `applyChipSuggestion` và hằng số `SUGGEST_CACHE_MAX_KEYS`, `SUGGEST_KIND_LABELS`.
- `web/src/features/lookup/InteractionLookupPage.tsx`: cập nhật `DrugChipInput` dùng `DrugNameCombobox`, thẻ từ gợi ý hiện `nhan` + `→ ten_hoat_chat`, thẻ tự do giữ viền nét đứt và `title="Chưa đối chiếu danh mục"`.
- `web/src/features/lookup/DrugSearchPage.tsx`: dùng `DrugNameCombobox` cho ô tìm kiếm (chọn gợi ý mở `/app/thuoc/{hoat_chat_id}`, Enter tự do lọc bảng qua `?q=`), `DrugResultsTable` hiển thị thông báo gần đúng khi có `goi_y_sua`.
- `web/src/__tests__/lookup.test.tsx`: bổ sung các ca kiểm thử cho `ApiClient.suggestDrugs`, `MockClient.suggestDrugs`, thuộc tính ARIA và chống chèn HTML thô của `DrugNameCombobox`, điều hướng bàn phím, bộ nhớ đệm 100 khoá, `DrugChipInput` và `DrugResultsTable`.

*(Đã giữ nguyên toàn bộ tệp cấm sửa, bao gồm `web/src/features/order-detail/**`, `web/src/features/sidebar/**`, `web/src/app/WorkspacePage.tsx`, `app/rules/**`, `app/kb/resolver/**`, `app/kb/names.py`, `db/**`, `pyproject.toml`, `web/package.json` và lockfile.)*

---

## 2. Thuật toán xếp hạng và tham số ngưỡng

1. **Chuẩn hoá truy vấn (`normalize_suggest_query`)**:
   - Đổi hậu tố `%` sau chữ số (ví dụ `5%`, `0,9%`) sang dấu hiệu nội bộ trước khi gọi `app.kb.names.normalize_key`.
   - Loại bỏ hàm lượng ở cuối (`mg`, `mcg`, `ug`, `microgam`, `g`, `gam`, `kg`, `ml`, `lit`, `l`, `mmol`, `meq`, `miu`, `iu`, `ui`, `dvqt`, `%`, kể cả dạng ghép `mg/ml`, `875/125 mg`).
   - Sau chuẩn hoá có `< 2` ký tự → trả danh sách rỗng.
2. **Xếp hạng theo 4 tầng** (nhỏ hơn đứng trước):
   - **Tầng 0 (`khop="chinh_xac"`)**: `khoa == norm_q` (tra cứu bảng băm $O(1)$).
   - **Tầng 1 (`khop="tien_to"`)**: `khoa.startswith(norm_q)` (tìm nhị phân `bisect_left` trên danh sách khoá đã sắp xếp).
   - **Tầng 2 (`khop="tien_to"`)**: từ thứ hai trở đi của `khoa` bắt đầu bằng `norm_q` (tìm nhị phân trên chỉ mục ngược từ → khoá).
   - **Tầng 3 (`khop="gan_dung"`)**:
     - Chỉ mục ngược trigram có đệm 1 khoảng trắng hai đầu (`f" {s} "`).
     - Giới hạn chấm điểm tối đa **`_MAX_CANDIDATES = 300`** khoá (kết hợp top theo số trigram chung và top theo cận trên Jaccard để tránh khoá phối hợp dài đẩy mất tên ngắn).
     - Ngưỡng nhận: độ giống Jaccard trigram **`>= 0.3`** (`_TRIGRAM_THRESHOLD = 0.3`) **hoặc** khoảng cách sửa Damerau–Levenshtein (OSA) có trần **`<= max(1, len(norm_q) // 4)`**.
     - Sắp tầng 3 theo Jaccard giảm dần (float thô, không làm tròn), rồi khoảng cách sửa tăng dần.
   - **Đồng hạng trong cùng tầng**: `hoat_chat` (0) < `dong_nghia` (1) < `biet_duoc` (2), rồi độ dài `khoa` tăng dần, rồi thứ tự chữ cái.
3. **Gộp trùng và `goi_y_sua`**:
   - Loại mục `dong_nghia` có khoá trùng `normalize_key(ten_inn)` của hoạt chất đích.
   - Với cùng tập `frozenset(hoat_chat_ids)`: giữ tối đa 1 mục không phải biệt dược (`hoat_chat` hoặc `dong_nghia`), và tối đa **2** mục `biet_duoc`.
   - Khi nạp trong `app/api/lookup.py::_suggest_index`, chỉ nạp biệt dược có thành phần và có cùng công thức hoạt chất duy nhất trên một `khoa_ten_thuoc` (tránh gợi ý tên mâu thuẫn không phân giải được ở `/api/tuong-tac`); lấy `ten_thuoc` xuất hiện nhiều nhất làm nhãn sau khi bỏ hàm lượng.
   - `goi_y_sua`: gán bằng `nhan` của mục đầu tiên chỉ khi không có mục tầng 0–2 và có ít nhất 1 mục tầng 3; ngược lại `None`.

---

## 3. Ước lượng hiệu năng (chưa đo thực tế)

- Do bị cấm chạy shell nên chưa có số đo thực tế trên `tra_cuu.sqlite`.
- **Ước tính thiết kế:**
  - Dựng chỉ mục: 1 truy vấn danh mục (`_catalog()`), 1 truy vấn `dong_nghia` (~4.543 dòng), 1 truy vấn join `thuoc` × `thuoc_thanh_phan` (~46.360 dòng) + dựng cấu trúc trong RAM dự kiến **~0,5–1,2 s** (mục tiêu `< 3 s`), giữ trong `_CACHE` (TTL 600 s).
  - Truy vấn: tầng 0–2 dùng bảng băm + `bisect_left` (`< 1 ms`), tầng 3 chỉ chấm tối đa 300 ứng viên nên dự kiến **< 5–10 ms** trung bình (mục tiêu `< 30 ms`).

---

## 4. Test đã thêm

- `tests/kb/test_suggest.py`:
  - `test_normalize_suggest_query_strips_trailing_strength`
  - `test_fuzzy_typo_returns_acetaminophen_and_spelling_suggestion`
  - `test_exact_match_after_stripping_dosage`
  - `test_prefix_matches_brand_cordarone`
  - `test_tier2_internal_word_prefix_matches_panadol_extra`
  - `test_short_or_empty_query_returns_empty`
  - `test_deduplicates_non_brand_ingredients_and_caps_brands_at_two`
  - `test_tier_ordering_is_strict`
- `tests/api/test_tra_cuu.py`:
  - Cập nhật `test_lookup_endpoints_require_login` với `/api/thuoc/goi-y?q=amiod` (401 khi chưa đăng nhập).
  - `test_suggest_endpoint_typo_validation_and_route_order` (`parecetamo`, 422 khi thiếu `q` hoặc `q` dài 101 ký tự, không rơi vào `/api/thuoc/{hoat_chat_id}`).
  - `test_search_drugs_falls_back_to_fuzzy_suggest_with_goi_y_sua` (`/api/thuoc?q=parecetamo`).
  - `test_suggest_gia_tri_gui_resolves_in_interaction_lookup` (kiểm chéo `amiod`, `parac`, `cordar` qua `POST /api/tuong-tac`).
  - `test_suggest_index_build_and_query_latency` (kiểm thời gian dựng `< 3 s`, 50 truy vấn `< 30 ms`).
- `web/src/__tests__/lookup.test.tsx`:
  - `ApiClient.suggestDrugs` + `MockClient.suggestDrugs`.
  - `DrugNameCombobox` (WAI-ARIA 1.2, nhãn loại, thành phần `→ ...`, chống XSS khi `nhan` chứa `<script>`).
  - Điều hướng bàn phím (`↓` + `Enter`, `Esc`, không tự sáng khi chỉ có `gan_dung`).
  - Bộ nhớ đệm `Map` giới hạn 100 khoá (`setBoundedCache`).
  - `DrugChipInput` (chọn gợi ý bằng `gia_tri_gui`, thẻ tự do viền nét đứt `title="Chưa đối chiếu danh mục"`).
  - `DrugResultsTable` hiển thị thông báo gần đúng khi có `goi_y_sua`.

---

## 5. Việc chưa làm / cần Claude kiểm tra

1. Chạy bộ kiểm tra backend:
   - `uv run pytest`
   - `uv run ruff check .`
   - `uv run ruff format --check app tests`
2. Chạy bộ kiểm tra frontend trong `web/`:
   - `npx tsc -b`
   - `npm run lint`
   - `npx vitest run`
   - `npm run build`
3. Kiểm tra bằng tay / trình duyệt nếu cần: độ rộng popover của `DrugNameCombobox` trong `DrugChipInput`, trải nghiệm `↑/↓`, `Enter`, `Esc`, `Tab`, click chuột bằng `onMouseDown`, và thời gian phản hồi thực tế trên `tra_cuu.sqlite`.
