# T53 – Bộ phân giải tên thuốc → hoạt chất, bảng chuyển mã ca ↔ trục, nối DDInter (plan 1.8 D0.4 + D0.6)

Mô hình: Codex `gpt-6.2-sol`, effort `high`. Chạy nền, không dừng để hỏi. **Không có mạng, cũng không cần mạng**: mọi dữ liệu đã có trên đĩa. Điểm chưa rõ thì chọn cách ít rủi ro nhất và ghi vào báo cáo, mục "Lựa chọn đã làm".

Đọc trước:
- `AGENTS.md`
- `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md`: mục 3.2, 4.1, đợt D0
- `plan/reports/T50.md` (cả mục "T50-fix-1")
- `plan/reports/T51.md` (cả mục "T51-fix-1")
- `app/domain/models.py`: `CaBenh`, `Thuoc`, `ThanhPhan`, `HoatChat`, `ChiTietYLenh`
- `app/kb/names.py`

Task **T52** (Codex) đang chạy **song song**: nó sửa `app/kb/dictionary/**` và **dựng lại** `data/kb_curated/tu_dien/**`. Task này chỉ **đọc** các tệp đó và không sửa mã của T52.

## Mục tiêu

Cho các luật thẩm định (task sau: luật tương tác yếu tố 4, trùng nhóm yếu tố 2) một hàm duy nhất trả lời: **dòng thuốc này trong ca gồm những hoạt chất chuẩn nào, nhóm ATC gì, mã DDInter nào**.

- Có đủ lý do khi không trả lời được.
- **Không đổi dữ liệu ca, không đổi mã `HC-…` trong ca hay Supabase, không đổi luật hiện có.**

## Bối cảnh

- Ca giả lập (`data/mock/demo/*.json`, `data/mock/hoso_gia_lap/*.json`; ở chế độ DB thì đọc từ Supabase cùng mô hình `CaBenh`):
  - Mỗi ca có `danh_muc_thuoc` (thuốc → `thanh_phan[].hoat_chat_id`).
  - Mỗi ca có `danh_muc_hoat_chat` với `hoat_chat_id` dạng **`HC-CEFTRIAXONE`**, kèm `ten_hoat_chat` (Việt), **`ten_quoc_te`** (ví dụ `ceftriaxone`), `ma_atc`, `nhom_duoc_ly`.
  - Dòng y lệnh `ChiTietYLenh` có `thuoc_id` hoặc `ten_tu_do`.
- Trục hoạt chất T50 (`data/kb_curated/tu_dien/hoat_chat.jsonl`): khoá theo tên IN của RxNorm (`ceftriaxone`, `glyburide`…), có `rxcui`, `ma_atc[]` (mức 4), `ten_viet`, `loai`.
  - Cùng thư mục có `dong_nghia.jsonl`, `thuoc.jsonl`, `thuoc_thanh_phan.jsonl`, `anh_xa.jsonl`.
  - Các tệp lớn (~106 MB).
  - **Đã kiểm: mọi hoạt chất của ca giả lập đều có trên trục.**
- DDInter (`data/kb_staging/ddinter/thuoc.jsonl`): 1.971 thuốc, có `ddinter_id`, `ten`, `ma_atc[]`. Chưa có cột nối sang trục; T50 để trống cột `ddinter_id`.

## Phạm vi file

**Được tạo:**
- `app/kb/resolver/**` (mới)
- `tests/kb/test_resolver*.py`, `tests/kb/fixtures/resolver/**`
- `data/kb_curated/tra_cuu/**` (chỉ mục gọn cho lúc chạy)
- `data/kb_reports/T53_*`
- `plan/reports/T53.md`

**Cấm đụng:**
- `app/kb/dictionary/**`, `config/kb/tu_dien.yaml`, `db/tu_dien.sql` (của T52)
- `data/kb_curated/tu_dien/**`, `data/kb_staging/**`, `data/kb_sources/**`, `data/mock/**`, `data/kb/**`, `data/gold/**` (chỉ đọc)
- `app/rules/**`, `app/api/**`, `app/db/**`, `app/llm/**`, `app/orchestration/**`, `app/domain/**`, `web/**`
- `db/schema.sql`, `config/settings.yaml`, `.env`, `pyproject.toml`, `uv.lock` (không thêm thư viện; dùng `sqlite3` của thư viện chuẩn)

## Yêu cầu

### 1. Chỉ mục gọn cho lúc chạy (`python -m app.kb.resolver build-index`)

Đọc các tệp tầng 2 lớn **một lần**, ghi ra `data/kb_curated/tra_cuu/tra_cuu.sqlite`. Lúc chạy không được đọc lại các tệp ~100 MB.

Bảng:
- `hoat_chat(hoat_chat_id PK, ten_inn, ten_viet, rxcui, ma_atc_json, loai, ddinter_id, ddinter_cach_khop)`
- `dong_nghia(khoa_chuan_hoa, hoat_chat_id, loai, cach_khop)` có chỉ mục
- `thuoc(khoa_ten_thuoc, thuoc_id, ten_thuoc, so_dang_ky, dang_bao_che)` có chỉ mục; khoá tên đã bỏ hàm lượng / dạng
- `thuoc_thanh_phan(thuoc_id, hoat_chat_id, ham_luong, don_vi)`
- `chuyen_ma_ca(ma_ca, hoat_chat_id, cach_khop)`: bảng chuyển mục 3
- `meta(phien_ban, ngay_dung, nguon_tep_json, sha256_json)`

Yêu cầu chung:
- Ghi tệp mới rồi thay thế nguyên tử. Lệnh chạy lại được.
- **Chạy lại sau khi T52 dựng lại từ điển là bắt buộc:** viết rõ lệnh trong báo cáo.
- Chịu được giá trị `cach_khop` / `loai` mới mà T52 thêm (không liệt kê cứng mà báo lỗi).

### 2. Nối trục ↔ DDInter

Cột `ddinter_id` trong `hoat_chat`. Thứ tự khớp (ghi `ddinter_cach_khop`):
1. Tên DDInter chuẩn hoá (`app/kb/names.py`, bỏ muối) trùng `ten_inn` hoặc một đồng nghĩa `inn`/`muoi` của hoạt chất → `ten_chinh_xac`.
2. Không có thì không nối. Ghi vào `data/kb_reports/T53_ddinter_chua_noi.csv` kèm gợi ý theo ATC trùng; chỉ gợi ý, **không tự nối**.

Chặn ghép sai:
- Một `ddinter_id` khớp nhiều hoạt chất, hoặc một hoạt chất khớp nhiều `ddinter_id` → **không nối**, ghi danh sách xung đột.
- Ví dụ cần xử lý đúng: DDInter dùng `Acetaminophen`, `Valproic acid`, `Calcium gluconate`, `Sulfamethoxazole`; trục có thể dùng `acetaminophen`, `valproic_acid`…

Báo cáo: số hoạt chất trục có `ddinter_id`; **mọi hoạt chất của ca giả lập phải có `ddinter_id` hoặc có lý do rõ** (ví dụ sodium chloride không có trong DDInter).

### 3. Bảng chuyển mã ca ↔ trục (D0.4, không sửa dữ liệu ca)

- Với mỗi `hoat_chat_id` dạng `HC-…` xuất hiện trong mọi ca (`danh_muc_hoat_chat` của `data/mock/demo` và `data/mock/hoso_gia_lap`):
  - Khớp `ten_quoc_te` (chuẩn hoá, bỏ muối) với `ten_inn` hoặc đồng nghĩa trên trục.
  - Không có `ten_quoc_te` thì thử `ten_hoat_chat` (Việt) qua `dong_nghia`.
  - Ghi `chuyen_ma_ca`.
- Mã đã là khoá trục (không có tiền tố `HC-`) thì chuyển thẳng nếu tồn tại.
- Chế độ DB: cùng quy tắc, chạy lúc nạp từ `CaBenh` (không truy vấn DB riêng).
- Báo cáo `data/kb_reports/T53_chuyen_ma_ca.csv`: mọi mã `HC-…` → khoá trục, `cach_khop`. **Mục tiêu 0 mã không chuyển được**; mã nào không chuyển được thì ghi lý do.
- Đặc biệt kiểm phối hợp và tên dễ lệch:
  - Amoxicillin + clavulanic acid, sulfamethoxazole + trimethoprim, piperacillin + tazobactam, cefoperazone + sulbactam.
  - Colistimethate, insulin glargine, sodium chloride, benzylpenicillin.
  - Metoprolol tartrate (muối đổi dạng dùng: giữ hoạt chất `metoprolol`, ghi `dang_muoi`).

### 4. Bộ phân giải (`app/kb/resolver/`, API Python)

```python
class DrugResolver:
    @classmethod
    def from_index(cls, path: Path) -> "DrugResolver": ...
    def resolve_line(self, ca: CaBenh, line: ChiTietYLenh) -> KetQuaPhanGiai: ...
    def resolve_name(self, ten: str) -> KetQuaPhanGiai: ...
```

`KetQuaPhanGiai` (pydantic, `extra="forbid"`):
- `trang_thai`: `da_phan_giai` · `mot_phan` · `khong_nhan_dien` · `khong_ap_dung`
- `thanh_phan`: danh sách gồm `hoat_chat_id` (trục), `ma_ca` (mã `HC-…` nếu có), `ten_inn`, `ten_viet`, `ma_atc`, `ddinter_id`, `loai`, `ham_luong`, `don_vi`
- `nguon_khop`: `danh_muc_ca` · `ten_thuoc_dav` · `dong_nghia` · `tach_phoi_hop`
- `ly_do` (khi không đủ)
- `canh_bao`

Thứ tự phân giải dòng y lệnh, dừng ở bước đầu tiên ra kết quả:
1. `line.thuoc_id` có trong `ca.danh_muc_thuoc` → lấy `thanh_phan` → chuyển `HC-…` qua `chuyen_ma_ca`. Một thành phần không chuyển được thì `mot_phan`, kèm lý do.
2. Tên thuốc (`ten_thuoc` của thuốc trong ca, hoặc `line.ten_tu_do`), đã chuẩn hoá và bỏ hàm lượng / dạng:
   - Khớp `thuoc.khoa_ten_thuoc` (chế phẩm Cục Quản lý Dược) → `thuoc_thanh_phan`. Nhiều chế phẩm cùng tên nhưng thành phần khác nhau thì **không chọn**, trả `khong_nhan_dien` với lý do "tên ứng với nhiều công thức".
   - Hoặc khớp `dong_nghia` (tên hoạt chất).
3. Tách tên phối hợp theo `+`, `/`, ` và `, `;` rồi khớp từng phần theo bước 2.
4. Không khớp thì `khong_nhan_dien`. **Không dùng khớp gần đúng, không gọi LLM, không gọi mạng.**

Quy tắc thêm:
- `loai` ∈ {`dich_truyen_dien_giai`, `duoc_lieu`} thì `trang_thai = khong_ap_dung` cho các tra cứu tương tác, nhưng vẫn trả thành phần. Ví dụ "Natri clorid 0,9% 500 mL" → sodium chloride, `khong_ap_dung`.
- `resolve_name` dùng bước 2–4 (cho ô tra cứu sau này; không làm API HTTP trong task này).
- Hàm thuần sau khi nạp chỉ mục: không ghi tệp, không log tên thuốc kèm dữ liệu ca.
- Nạp chỉ mục một lần (lazy singleton hoặc truyền vào). Mỗi lần phân giải phải nhanh: đo và ghi thời gian trung bình.

### 5. Báo cáo chạy trên toàn bộ ca (`python -m app.kb.resolver report`)

Chạy `resolve_line` cho **mọi dòng** (`y_lenh_cho_duyet.chi_tiet` + `thuoc_dang_dung`) của mọi ca trong `data/mock/demo` và `data/mock/hoso_gia_lap`. Ghi `data/kb_reports/T53_phan_giai_ca.json`:
- Tổng số dòng; số dòng theo `trang_thai` và `nguon_khop`.
- Danh sách **mọi** dòng không `da_phan_giai` kèm ca, tên, lý do. Mục tiêu: chỉ còn `khong_ap_dung` có chủ đích.
- Số dòng có đủ `ddinter_id` cho mọi thành phần.
- Thời gian nạp chỉ mục và thời gian trung bình mỗi dòng.

Tra thử, ghi kết quả vào báo cáo:
- `resolve_name("Augmentin")`
- `"Ceftriaxon 1 g"`
- `"Cotrimoxazol 800/160 mg"`
- `"Amoxicilin + acid clavulanic 875 mg/125 mg"`
- `"Natri clorid 0,9% 500 mL"`
- `"Glibenclamid 5 mg"` (có thể `khong_nhan_dien` trước khi T52 xong; ghi đúng như thế)
- Một tên rác `"Thuốc XYZ 10 mg"`

### 6. Test

Test dùng **chỉ mục thu nhỏ** dựng từ fixture (không đọc tệp 100 MB). Phải có:
- Phân giải qua danh mục ca, có chuyển mã.
- Phối hợp 2 và 3 thành phần.
- Tên trùng nhiều công thức → không chọn.
- Dịch truyền → `khong_ap_dung`.
- Không khớp → `khong_nhan_dien`, không đoán.
- Xung đột DDInter (một-nhiều) → không nối.
- Chạy lại `build-index` cho kết quả giống hệt (xác định).

## Nghiệm thu (dán kết quả vào báo cáo)

- `uv run python -m app.kb.resolver build-index` và `report` chạy hết. Dán `T53_phan_giai_ca.json` (rút gọn) và kết quả tra thử.
- 0 mã `HC-…` không chuyển được (hoặc liệt kê lý do từng mã).
- Số hoạt chất của ca giả lập có `ddinter_id` trên tổng; liệt kê từng hoạt chất không có kèm lý do.
- `uv run ruff check app/kb/resolver tests/kb`, `ruff format --check` các tệp mới, `uv run pytest -q tests/kb --basetemp=.pytest_t53` qua; toàn bộ test cũ không đổi kỳ vọng.
- Báo cáo `plan/reports/T53.md`:
  - Có các mục "Lựa chọn đã làm", "Lệnh chạy lại sau T52", "Giới hạn còn lại".
  - Ghi dung lượng tệp `tra_cuu.sqlite`.

## Cấm làm

- Không sửa dữ liệu ca, luật, mô hình miền, lược đồ DB.
- Không ghép mờ; không gọi LLM hay mạng.
- Không commit. Không dùng `&`.
- Xoá `.pytest_t53*` khi xong.
