# T08-fix-1 – Sửa 4 lỗi của cổng che định danh + định dạng 2 file

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort high) · **Ngày:** 16/11/2026
**Đọc trước:** `AGENTS.md` (bắt buộc), `plan/briefs/T08-cong-che-dinh-danh.md` (brief gốc, vẫn còn hiệu lực trừ chỗ brief này sửa).
**Đang có task khác chạy song song (T07).** Bạn **không** tạo hay sửa `pyproject.toml`, `.gitignore`, `app/pipeline.py`, `app/feedback.py`, `app/ui/`, `tests/ui/`, `tests/test_pipeline.py`, `tests/test_feedback.py`, kể cả khi thấy chúng lỗi hoặc dở dang.

## 1. Phạm vi file được sửa

```text
app/deid/scrubber.py
tests/deid/test_scrubber.py
app/rules/renal_dose.py            (chỉ chạy ruff format, xem mục 4)
tests/rules/test_engine_demo.py    (chỉ chạy ruff format, xem mục 4)
```

## 2. Bốn lỗi phải sửa

Người review đã chạy `scrub_text` với câu tự đặt và thấy:

| # | Đầu vào | Hiện tại | Phải thành |
| :-: | :--- | :--- | :--- |
| 1 | `báo BS lúc 5/11, CCCD 001099012345` | `5/11,` không bị che | `báo BS lúc [NGAY_1], CCCD [CCCD_1]` |
| 1b | `BS. Đức khám lúc 5/11.` | không đổi | `BS. [TEN_1] khám lúc [NGAY_1].` |
| 2 | `chị Hoa nhà ở Hà Nội` | `Hoa` không bị che | `chị [TEN_1] nhà ở Hà Nội` |
| 2b | `anh Nam đau bụng` | không đổi | `anh [TEN_1] đau bụng` |
| 3 | `liều 1/2 viên; tỉ lệ 3/4` | `liều [NGAY_1] viên; tỉ lệ [NGAY_2]` | không đổi, `thay_the == []` |
| 3b | `uống 1/2 viên ngày 5/11` | `uống [NGAY_1] viên ngày [NGAY_2]` | `uống 1/2 viên ngày [NGAY_1]` |
| 4 | `mạch 123456789 mmHg` | `mạch [HN_1] mmHg` | không đổi |
| 4b | `tiểu cầu 150000000 /L, HN 123456789` | `tiểu cầu [HN_1] /L, HN [HN_2]` | `tiểu cầu 150000000 /L, HN [HN_1]` |

### 2.1 Quy tắc `NGAY` dạng `dd/mm` (thay câu tương ứng ở mục 4 brief gốc)

- Ngay **sau** ngày được phép có một dấu câu trong `, . ; : )` **miễn là ký tự kế tiếp dấu câu đó không phải chữ số**. Ví dụ `5/11,` và `5/11.` (cuối câu) là ngày; `5/11,5` và `5/11.2` không phải ngày.
- Ngay **trước** ngày được phép có `(`.
- Vẫn giữ: không có chữ số hay dấu `/` dính liền hai bên; ngày 1–31; tháng 1–12.
- **Không** coi là ngày (chỉ áp dụng cho dạng `dd/mm` không có năm) khi:
  - ngay sau (cách 0 hoặc 1 dấu cách) là một đơn vị liều, khớp nguyên từ, không phân biệt hoa thường: `viên`, `ống`, `lọ`, `gói`, `liều`, `mg`, `mcg`, `ml`, `g`; hoặc
  - ngay trước (cách 0 hoặc 1 dấu cách, có thể kèm dấu `:`) là một trong các từ: `liều`, `tỉ lệ`, `tỷ lệ`.
- Không có dấu hiệu nào ở trên thì vẫn che (thà che thừa).

### 2.2 Quy tắc `TEN`

- Sau danh xưng nhận **1–4** từ viết hoa chữ đầu (trước đây 2–4).
- Ngoại lệ duy nhất: sau `BN`, `bệnh nhân`, `người bệnh`, nếu phần tên chỉ gồm đúng một từ và từ đó là `Nam` hoặc `Nữ` thì **không che** (đó là giới tính: `BN Nam, 65 tuổi`). Sau các danh xưng khác (`anh Nam`) vẫn che.
- Chấp nhận che thừa địa danh kiểu `Bà Rịa` → `Bà [TEN_1]`. Không cần xử lý.

### 2.3 Quy tắc `HN`

Dãy đúng 9 chữ số **không** là `HN` khi ngay sau (cách 0 hoặc 1 dấu cách) là một đơn vị đo trong danh sách đóng sau, phân biệt đúng như viết, và sau đơn vị không dính thêm chữ cái:

```text
mmHg  /L  /l  /uL  /µL  /mm3  G/L  T/L  U/L  IU/mL  IU/ml  copies/mL  copies/ml  mg  ml  mL  umol/L  µmol/L  mmol/L
```

Không mở rộng danh sách này. Các trường hợp khác vẫn che.

## 3. Kiểm thử

- Thêm đủ 8 dòng ở bảng mục 2 thành test, so sánh **nguyên văn** `van_ban` đầu ra.
- Thêm:
  - `ngày 5/11; 6/11: sốt (7/11)` → `ngày [NGAY_1]; [NGAY_2]: sốt ([NGAY_3])`
  - `tỉ số 5/11,5` → không đổi
  - `BN Nam, 65 tuổi` → không đổi; `bệnh nhân Nữ 40 tuổi` → không đổi
  - `HBV DNA 123456789 IU/mL` → không đổi
  - `mã 123456789 mgx` → `mã [HN_1] mgx`
  - `tỷ lệ: 3/4` → không đổi; `dùng 1/2 ống` → không đổi
- Khứ hồi `restore_text(scrub_text(x).van_ban, scrub_text(x).anh_xa) == x` cho toàn bộ câu mới ở trên.
- **Các test hiện có ở `tests/deid` phải tiếp tục qua mà không sửa kỳ vọng, trừ đúng một ngoại lệ đã được người review duyệt (bổ sung sau lần chạy 1):** trong `test_preserves_non_identifiers_and_clinical_numbers`, ca `"BS An"` trước đây kỳ vọng giữ nguyên; theo quy tắc 2.2 nay phải thành `"BS [TEN_1]"`. Chuyển ca này sang nhóm test dương của `TEN` với kỳ vọng mới. Mọi ca tên một từ sau danh xưng khác trong test cũ (nếu có) xử lý y như vậy và **liệt kê từng ca đã đổi** trong báo cáo. Mâu thuẫn thuộc loại khác (ngày, HN, …) thì vẫn dừng lại và báo, không tự sửa kỳ vọng.

## 4. Định dạng hai file ngoài deid

Chạy đúng lệnh sau, không sửa tay và không đổi logic:

```bash
uv run ruff format app/rules/renal_dose.py tests/rules/test_engine_demo.py
```

## 5. Nghiệm thu

```bash
uv run ruff check app/deid tests/deid app/rules tests/rules
uv run ruff format --check app/deid tests/deid app/rules tests/rules
uv run pytest -q tests/deid tests/rules
```

Không chạy `uv sync`, không chạy `ruff format .` trên cả kho (task khác đang ghi file).

## 6. Cấm làm

- Không thêm thư viện. Không ghi log nội dung văn bản.
- Không đổi chữ ký `scrub_text`, `restore_text`, `ScrubResult`, `ThayThe`, `DeidError`.
- Không nới quy tắc nào ngoài ba mục 2.1–2.3.
- Không commit, không push.
