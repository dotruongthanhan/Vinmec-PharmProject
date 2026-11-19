# T51-fix-1 – Sửa bộ phân tích DDInter theo phản hồi thật

Mô hình: Codex `gpt-6.2-sol`, effort `medium`. Không cần mạng: mọi phản hồi thật đã có trên đĩa. Đọc `AGENTS.md`, `plan/briefs/T51-cao-ddinter-day-du-truong.md`, `plan/reports/T51.md`.

## Bối cảnh

Ở lượt T51, Codex không có mạng. Claude đã tự chạy `uv run python -m app.kb.fetch.ddinter thuoc --ids DDInter1951,DDInter83`:
- Bộ cào chạy đúng: 10 yêu cầu, 0 lỗi; warfarin có 936 dòng thuốc–thuốc, khớp `recordsTotal`.
- Thân POST kiểu DataTables được máy chủ chấp nhận.
- **Bộ phân tích sai vì viết theo cấu trúc đoán.**

Phản hồi thật nằm ở:
- `data/kb_sources/ddinter_web/{thuoc,tuong_tac_thuoc,tuong_tac_benh,tuong_tac_thuc_an,che_pham_phoi_hop}/DDInter1951.*.gz` và `DDInter83.*.gz`
- `data/kb_sources/ddinter_web/mau_that/interact_3039.html` (warfarin–acalabrutinib), `interact_24300.html` (warfarin–amoxicillin, Moderate), `interact_21901.html` (warfarin–amiodarone, Major)
- `data/kb_sources/ddinter_web/mau_that/linkmarker_3039.txt`

### Cấu trúc thật Claude đã đọc

**`interact-with`**, mỗi dòng:

```json
{"drug_id": "DDInter9", "drug_name": "Acalabrutinib", "interaction_id": 3039, "level": 3,
 "excretion": "0", "absorption": "0", "others": "0", "antagonistic_effect": "0",
 "distribution": "0", "metabolism": "0", "synergistic_effect": "1"}
```

- `level` là số nguyên: **3 = Major, 2 = Moderate, 1 = Minor, 0 = Unknown**. Warfarin có 138 / 429 / 71 / 298; dòng 3039 hiện "Major" trên web.
- Cơ chế là cờ `"0"` / `"1"`: `antagonistic_effect`→Antagonism, `synergistic_effect`→Synergy, `absorption`→Absorption, `distribution`→Distribution, `metabolism`→Metabolism, `excretion`→Excretion, `others`→Others.
- `interaction_id` là mã trang cặp `/server/interact/<n>/`.

**`interact-with-dis`**: `interaction_id`, `level` (chuỗi `"3"`…), `diseaseName`, `text` (kiểm xem là văn bản đủ hay bị cắt), `references` (nối bằng `|`).

**`interact-with-food`**: `interaction_id`, `level`, `foodName`, `newInteraction` (mô tả / hậu quả), `newManagement` (xử trí), `references` (`|`). Cơ chế nằm ở khoá tên lạ **`magnesium`** (ví dụ `"Synergy"`). Lấy giá trị đó làm `co_che` và ghi rõ trong báo cáo.

**`interact-with-multi`**: warfarin và amoxicillin đều trả `recordsTotal: 0`. Giữ bộ phân tích theo cột hiện có; khi chạy đầy đủ, Claude sẽ tìm thuốc có dữ liệu.

**Trang cặp**: xem ba tệp HTML thật.

**`linkmarker`**: trả **xác suất CYP do mô hình dự đoán** (ví dụ `"CYP2C9-sub": 0.966`). Đây không phải dữ kiện từ tài liệu: **bỏ khỏi bộ cào**, không tải, không đưa vào tầng 1.

## Phạm vi file

Được sửa:
- `app/kb/sources/ddinter_web.py`, `app/kb/fetch/ddinter.py`
- `tests/kb/test_ddinter_web*.py`, `tests/kb/fixtures/ddinter/**`
- Tầng 1 `data/kb_staging/ddinter/**` (dựng lại)
- `plan/reports/T51.md` (thêm mục "T51-fix-1")

Cấm đụng: như brief T51. **Không** xoá hay sửa tệp tầng 0 trong `data/kb_sources/ddinter_web/`.

## Yêu cầu

1. **Thuốc–thuốc:**
   - `muc_do` theo bảng số → `Major` / `Moderate` / `Minor` / `Unknown`; giữ thêm `muc_do_so`. Số lạ ngoài 0–3 thì ghi lỗi, không đoán.
   - `co_che[]` từ các cờ `"1"`.
   - `ma_trang_cap` = `interaction_id`.
   - Giữ `cot_goc` (dòng thô).
2. **Thuốc–bệnh:**
   - `ten_benh` = `diseaseName`; `noi_dung` = `text`; `tai_lieu` tách theo `|` và bỏ khoảng trắng thừa; `ma_trang` = `interaction_id`.
   - Kiểm `text` của warfarin có bị cắt không (có dấu "…" / "..." ở cuối hay không) và ghi kết quả.
3. **Thuốc–thức ăn:** `thuc_an` = `foodName`, `mo_ta` = `newInteraction`, `xu_tri` = `newManagement`, `co_che` = [`magnesium`] nếu khác rỗng, `tai_lieu` tách `|`.
4. **Mức độ dùng chung một bảng ánh xạ** cho cả ba loại. Bệnh và thức ăn trả chuỗi `"3"`: ép kiểu an toàn.
5. **Trang cặp:** phân tích đúng trên ba tệp HTML thật:
   - `ten_a`, `ten_b`, `muc_do`, `co_che[]`, `ddinter_id_a/b`
   - `hau_qua` (Interaction), `xu_tri` (Management), `tai_lieu[]` (đúng số mục trên trang)
   - `thay_the_a` / `thay_the_b` (`ma_atc` + danh sách tên, gồm cả phần ẩn sau "More" nếu có trong HTML)
   - `cyp_tho` (nguyên văn mục "Potential metabolism interactions", nếu có)
6. **Trang thuốc:** giữ phân tích hiện tại (đã đúng: warfarin ATC `B01AA03`, tổng 936 / 8 / 2 / 0). Kiểm lại trên tệp thật.
7. **Bỏ `linkmarker`** khỏi mọi pha.
8. **Fixture:**
   - Thay fixture giả bằng bản sao **thật** lấy từ các tệp trên. Được cắt bớt mảng `data` (ví dụ 20 dòng đầu) và chỉnh `recordsTotal` tương ứng, ghi chú trong test.
   - Thêm test phân trang bằng phản hồi thật đã cắt làm hai phần.
   - Giữ test chạy tiếp sau khi dừng.
9. Dựng lại tầng 1 từ tầng 0 hiện có (lệnh phân tích lại mà **không gọi mạng**, ví dụ `python -m app.kb.fetch.ddinter phan-tich`). Chạy `kiem`.

## Nghiệm thu (dán kết quả)

- Sau `phan-tich`:
  - Warfarin có 936 dòng thuốc–thuốc (138 Major, 429 Moderate, 71 Minor, 298 Unknown).
  - Dòng acalabrutinib có `co_che == ["Synergy"]`, `ma_trang_cap == 3039`.
  - Thức ăn `alcohol` có `mo_ta`, `xu_tri`, `co_che == ["Synergy"]`.
  - 8 dòng bệnh, dòng đầu `ten_benh == "Hemorrhage"`.
- Trang 24300: `muc_do == "Moderate"`, `co_che == ["Synergy"]`, `hau_qua` bắt đầu bằng "Penicillins may occasionally potentiate".
- Trang 21901: `muc_do == "Major"`, `co_che == ["Metabolism"]`.
- Trang 3039: 3 tài liệu, `thay_the_a.ma_atc == "B01A"`.
- `kiem` trên 2 thuốc: lệch đếm = 0; dán đầu ra.
- `uv run ruff check app/kb/sources/ddinter_web.py app/kb/fetch/ddinter.py tests/kb`, `ruff format --check` các tệp đó, `uv run pytest -q tests/kb --basetemp=.pytest_t51f1` qua.

## Cấm làm

- Không gọi mạng. Không commit. Không dùng `&`.
- Không sửa tệp của T50.
- Xoá `.pytest_t51f1*` khi xong.
