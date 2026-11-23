# T105 – Gợi ý tên thuốc khi gõ (Tra tương tác + Tra cứu thuốc)

Đọc `AGENTS.md` trước. Hợp đồng tra cứu hiện có: `plan/api-hop-dong-v1.8-tra-cuu.md`. Hệ thống thiết kế: `plan/plan-1.4-he-thong-thiet-ke.md`.

## Bối cảnh

- Trang **Tra tương tác** (`web/src/features/lookup/InteractionLookupPage.tsx`, thành phần `DrugChipInput`) nhận tên tự do. Gõ sai ("parecetamo") hoặc gõ tên lạ thì chỉ biết là hỏng sau khi bấm Kiểm tra.
- Trang **Tra cứu thuốc** (`DrugSearchPage.tsx`) gọi `GET /api/thuoc?q=`. Backend `app/api/lookup.py::search_drugs` chỉ so `LIKE` trên khoá đã bỏ dấu, nên gõ sai một ký tự là ra 0 kết quả.
- **Dữ liệu tên** (đọc bằng `_query("tra_cuu", ...)` trong `lookup.py`; cùng cấu trúc trên DB `tri_thuc.tra_cuu_*` và SQLite `data/kb_curated/tra_cuu/tra_cuu.sqlite`, các bảng `hoat_chat`, `dong_nghia`, `thuoc`, `thuoc_thanh_phan`):
  - `hoat_chat` (1.255 dòng): `hoat_chat_id` (INN tiếng Anh, ví dụ `acetaminophen`), `ten_inn` (ví dụ `paracetamol`), `ten_viet`.
  - `dong_nghia` (4.543 dòng): `khoa_chuan_hoa` → `hoat_chat_id`, `loai` ∈ {`inn`, `viet`, `muoi`}. Đã có các cặp như `paracetamol → acetaminophen`, `amiodaron → amiodarone`, `acetaminofen → acetaminophen`.
  - `thuoc` (54.910 chế phẩm, 39.242 khoá khác nhau): `khoa_ten_thuoc` (đã chuẩn hoá, bỏ hàm lượng, ví dụ `cordarone`, `panadol extra`), `ten_thuoc` (tên gốc có dấu và hàm lượng). 15.680 chế phẩm **không có** dòng trong `thuoc_thanh_phan` → không quy được về hoạt chất → **không đưa vào gợi ý**.
  - `thuoc_thanh_phan`: `thuoc_id` → `hoat_chat_id` (thuốc phối hợp có nhiều dòng).
- Hàm chuẩn hoá có sẵn: `app/kb/names.py::normalize_key` (bỏ dấu, chữ thường, bỏ dấu câu) và `strip_salt`.
- **Không có** thư viện so khớp mờ trong dự án; Postgres chưa bật `pg_trgm`. **Không thêm thư viện, không đổi DB.** Tự cài so khớp trigram bằng Python thuần.

## Yêu cầu backend

1. **Module mới `app/kb/suggest.py`** (thuần, không I/O): lớp `DrugSuggestIndex`.
   - Dựng từ danh sách mục `(khoa, nhan_hien_thi, loai, hoat_chat_ids, gia_tri_gui)`.
   - `loai` ∈ `hoat_chat` | `dong_nghia` | `biet_duoc`.
   - `gia_tri_gui` là chuỗi gửi đi khi người dùng chọn: hoạt chất → `ten_inn`; đồng nghĩa → tên đồng nghĩa; biệt dược → `ten_thuoc` tiêu biểu.
   - Phương thức `goi_y(q: str, gioi_han: int = 8) -> KetQuaGoiY`.
2. **Chuẩn hoá truy vấn:** `normalize_key`, rồi bỏ phần hàm lượng ở cuối (số kèm đơn vị như `200 mg`, `500mg`, `1 g`, `5%`, `mg/ml`). Dưới 2 ký tự sau chuẩn hoá → trả rỗng.
3. **Xếp hạng theo tầng** (tầng nhỏ đứng trước):
   - tầng 0: khoá trùng khớp hoàn toàn;
   - tầng 1: khoá bắt đầu bằng truy vấn;
   - tầng 2: một từ bên trong khoá bắt đầu bằng truy vấn (ví dụ `extra` khớp `panadol extra`);
   - tầng 3 (gần đúng): độ giống trigram (Jaccard trên tập trigram có đệm khoảng trắng hai đầu) ≥ 0,3 **hoặc** khoảng cách sửa (Damerau–Levenshtein, có trần) ≤ `max(1, len(q) // 4)`. Sắp theo độ giống giảm dần.
   - Trong cùng tầng: `hoat_chat` > `dong_nghia` > `biet_duoc`, rồi khoá ngắn hơn, rồi theo chữ cái.
   - Tạo ứng viên tầng 3 bằng chỉ mục ngược trigram → khoá. Chỉ chấm điểm tối đa khoảng 300 khoá có nhiều trigram chung nhất, không quét toàn bộ 45k khoá.
4. **Gộp trùng:** các mục quy về **cùng tập** `hoat_chat_ids` chỉ giữ mục có hạng tốt nhất, trừ biệt dược: mỗi tập hoạt chất được tối đa 2 mục biệt dược. Mục `dong_nghia` có khoá trùng `ten_inn` của hoạt chất thì bỏ.
5. **`KetQuaGoiY`:**
   - `ket_qua`: danh sách mục `{nhan, loai, hoat_chat_ids, ten_hoat_chat (danh sách ten_inn), gia_tri_gui, khop: "chinh_xac" | "tien_to" | "gan_dung"}`.
   - `goi_y_sua`: tên hiện thị của mục đầu tiên khi **không** có mục tầng 0–2 mà có mục tầng 3, ngược lại `None`.
6. **Nạp chỉ mục trong `app/api/lookup.py`:** hàm `_suggest_index()` dựng từ `_query("tra_cuu", ...)` (chạy được cả chế độ DB lẫn tệp), lưu trong `_CACHE` như `_catalog()`.
   - Mỗi khoá biệt dược lấy `ten_thuoc` xuất hiện nhiều nhất làm nhãn; bỏ hàm lượng khỏi nhãn nếu `ten_thuoc` có.
   - Chỉ nạp biệt dược có thành phần.
   - Dựng chỉ mục ≤ 3 s trên SQLite cục bộ; mỗi truy vấn ≤ 30 ms trung bình.
7. **Điểm cuối mới `GET /api/thuoc/goi-y?q=&gioi_han=`** trong `app/api/routes.py`:
   - Bắt buộc đăng nhập (`principal: Caller` như các route tra cứu khác).
   - `q` bắt buộc, `max_length=100`; `gioi_han` từ 1 đến 15, mặc định 8.
   - Đặt header `Cache-Control: private, no-store`.
   - Schema pydantic mới trong `app/api/schemas.py` (`GoiYThuoc`, `KetQuaGoiYThuoc`, các trường như mục 5).
   - **Khai báo route này TRƯỚC `GET /thuoc/{hoat_chat_id}`**, nếu không `goi-y` sẽ bị hiểu là một `hoat_chat_id`.
   - **Không ghi `q` vào log** ở bất kỳ mức nào.
8. **`search_drugs`:** khi `q` có giá trị mà truy vấn `LIKE` hiện tại trả 0 hoạt chất, lấy `hoat_chat_ids` từ `_suggest_index().goi_y(q, 30)` (giữ thứ tự) làm kết quả. Thêm trường tuỳ chọn `goi_y_sua: str | None` vào `DanhSachThuoc` (mặc định `None`, không phá hợp đồng cũ). Có kết quả `LIKE` thì giữ nguyên hành vi cũ.
9. **Cập nhật hợp đồng** `plan/api-hop-dong-v1.8-tra-cuu.md`: thêm mục cho `GET /api/thuoc/goi-y` và trường `goi_y_sua`.

## Yêu cầu giao diện

10. **Kiểu và client:**
    - Thêm kiểu vào `web/src/api/types.ts`.
    - Thêm `suggestDrugs(q, options?: { signal })` vào `web/src/api/client.ts` (giao diện và bản HTTP) và `web/src/api/index.ts`.
    - Bản giả trong `web/src/api/mock.ts` lọc theo tiền tố trên dữ liệu thuốc giả sẵn có.
11. **Thành phần dùng chung `web/src/features/lookup/DrugNameCombobox.tsx`** theo mẫu combobox WAI-ARIA 1.2:
    - Ô nhập có `role="combobox"`, `aria-expanded`, `aria-controls`, `aria-autocomplete="list"`, `aria-activedescendant`; danh sách có `role="listbox"`, mỗi dòng `role="option"`.
    - Gõ ≥ 2 ký tự, chờ 150 ms sau phím cuối mới gọi. Huỷ yêu cầu cũ bằng `AbortController`. Nhớ kết quả trong bộ nhớ theo truy vấn (Map, tối đa 100 khoá; **không** dùng `localStorage`).
    - Mỗi dòng: nhãn với phần khớp được tô đậm (tách chuỗi bằng React, **không** dùng `innerHTML`), nhãn loại nhỏ (Hoạt chất / Tên khác / Biệt dược), và `→ ten_hoat_chat` khi nhãn khác tên hoạt chất. Thuốc phối hợp nối bằng ` + `.
    - Phím: ↑/↓ di chuyển, Enter chọn dòng đang sáng, Esc đóng, Tab đóng mà không chọn. Bấm chuột chọn được (dùng `onMouseDown` + `preventDefault` để ô không mất focus trước).
    - Tự sáng dòng đầu **chỉ khi** dòng đầu là `chinh_xac` hoặc `tien_to`. Không có dòng nào khớp chính xác hoặc tiền tố mà có `goi_y_sua` → hiện dòng "Có phải ý bạn là **…**?"; bấm vào thì chọn mục đó.
    - Không có kết quả → dòng "Không tìm thấy trong danh mục".
    - Lỗi mạng → đóng danh sách lặng lẽ; ô nhập vẫn dùng được như cũ.
    - Props đề xuất: `value`, `onValueChange`, `onSelect(item)`, `onEnterFreeText()`, `placeholder`, `id`, `disabled`, `ariaDescribedBy`.
12. **Tra tương tác (`DrugChipInput`):** dùng `DrugNameCombobox` cho ô gõ.
    - Chọn gợi ý → thêm thẻ với giá trị `gia_tri_gui`. Thẻ hiện `nhan`, kèm chú thích nhỏ `→ ten_hoat_chat` nếu khác.
    - Enter khi không có dòng sáng → giữ hành vi cũ (thêm chữ tự do). Thẻ tự do có viền nét đứt và `title="Chưa đối chiếu danh mục"`.
    - Giữ đủ: dấu phẩy/chấm phẩy tách thẻ, Backspace bỏ thẻ cuối, Enter khi ô trống thì kiểm tra, giới hạn 2–12 thuốc, báo trùng (`addDrugName`).
    - Mảng gửi lên `POST /api/tuong-tac` vẫn là danh sách chuỗi; **không đổi hợp đồng**.
13. **Tra cứu thuốc:** ô tìm dùng `DrugNameCombobox`.
    - Chọn gợi ý → mở thẳng `/app/thuoc/{hoat_chat_id}` (với phối hợp nhiều hoạt chất: hoạt chất đầu).
    - Gõ rồi Enter khi không có dòng sáng → giữ hành vi cũ (lọc bảng qua `?q=`).
    - Bảng kết quả có `goi_y_sua` → hiện dòng "Không có kết quả khớp đúng. Đang hiện kết quả gần đúng cho **…**".

## Phạm vi tệp

- **Được sửa:**
  - `app/kb/suggest.py` (mới), `app/api/lookup.py`, `app/api/routes.py`, `app/api/schemas.py`;
  - `tests/kb/test_suggest.py` (mới), `tests/api/test_tra_cuu.py`;
  - `web/src/api/{types,client,index,mock}.ts`, `web/src/features/lookup/**`, `web/src/lib/lookup.ts`, `web/src/__tests__/**`;
  - `plan/api-hop-dong-v1.8-tra-cuu.md`.
- **Cấm:**
  - `pyproject.toml`, `uv.lock`, `web/package.json` và lockfile (không thêm thư viện);
  - `db/**` (không đổi lược đồ, không bật extension);
  - `app/rules/**`, `app/kb/resolver/**`, `app/kb/names.py` (chỉ được import);
  - `web/src/features/order-detail/**`, `web/src/features/sidebar/**`, `web/src/app/WorkspacePage.tsx` (đang có thay đổi T104 chưa commit).
- **Không gọi công cụ shell** (không chạy uv, npm, git hay lệnh nào). Claude sẽ tự chạy kiểm tra.

## Tiêu chí nghiệm thu (Claude chạy)

1. `uv run pytest` toàn bộ qua; `uv run ruff check .` và `uv run ruff format --check app tests` sạch. Trong `web/`: `npx tsc -b`, `npm run lint`, `npx vitest run`, `npm run build` qua.
2. **`tests/kb/test_suggest.py`** (dữ liệu nhỏ dựng tay, không cần tệp):
   - `parecetamo` → mục đầu thuộc `acetaminophen`, `khop="gan_dung"`, và `goi_y_sua` khác `None`;
   - `amiodaron 200 mg` → `amiodarone`, `khop="chinh_xac"`;
   - `cordar` → biệt dược `Cordarone` (`tien_to`);
   - `extra` khớp `Panadol Extra` (tầng 2);
   - `a` hoặc `"  "` → rỗng;
   - gộp trùng: `paracetamol` và `acetaminophen` không cùng xuất hiện như hai hoạt chất riêng;
   - mỗi tập hoạt chất ≤ 2 biệt dược;
   - thứ tự tầng đúng.
3. **`tests/api/test_tra_cuu.py`** (chế độ tệp, theo mẫu fixture `local_only` và marker `needs_index` sẵn có):
   - `GET /api/thuoc/goi-y?q=parecetamo` → 200, có `acetaminophen`;
   - `q` dài 101 ký tự → 422; thiếu `q` → 422; chưa đăng nhập → 401;
   - `GET /api/thuoc/goi-y` không rơi vào route chi tiết thuốc;
   - `GET /api/thuoc?q=parecetamo` → `tong > 0` và `goi_y_sua` có giá trị;
   - **kiểm chéo:** lấy 5 mục gợi ý cho `amiod`, `parac`, `cordar`; gửi `gia_tri_gui` của từng mục kèm `meropenem` vào `POST /api/tuong-tac`; mục `phan_giai` tương ứng phải là `da_phan_giai` với đúng `hoat_chat_ids` của gợi ý;
   - dựng chỉ mục từ SQLite < 3 s, 50 truy vấn trung bình < 30 ms.
4. **Web (vitest):**
   - `DrugNameCombobox` đủ thuộc tính ARIA;
   - ↓ rồi Enter gọi `onSelect` đúng mục;
   - Esc đóng;
   - phần tô đậm không chứa HTML thô khi `nhan` có ký tự `<`;
   - `DrugChipInput` chọn gợi ý thì thêm thẻ bằng `gia_tri_gui`, Enter chữ tự do vẫn thêm thẻ nét đứt;
   - trang Tra cứu hiện dòng gần đúng khi có `goi_y_sua`.

## Bảo mật

- Điểm cuối chỉ đọc, bắt buộc đăng nhập, giới hạn độ dài `q` và `gioi_han`. Chỉ trả dữ liệu danh mục, không trả dữ liệu ca bệnh.
- Không ghi chuỗi tìm vào log hay `localStorage`: người dùng có thể dán nhầm thông tin người bệnh vào ô tìm.
- Hiển thị gợi ý bằng nút React; không dùng `innerHTML` / `dangerouslySetInnerHTML`.
- Truy vấn SQL dùng tham số `%s`, không f-string với dữ liệu người dùng (các truy vấn nạp chỉ mục không có tham số người dùng).
- Chặn chi phí: gọi ≥ 150 ms/lần mỗi ô, huỷ yêu cầu cũ, cache phía client; phía máy chủ chỉ chấm tối đa khoảng 300 ứng viên mỗi truy vấn.

## Báo cáo

Ghi `plan/briefs/T105-bao-cao.md`: tệp đã đổi, thuật toán xếp hạng đã cài (tham số ngưỡng), số đo thời gian dựng chỉ mục và truy vấn nếu tự ước được, test đã thêm, việc chưa làm.
