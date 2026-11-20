# T08 – Cổng che định danh cho văn bản tự do (bản tối giản)

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort high) · **Ngày:** 16/11/2026
**Đọc trước:** `AGENTS.md` (bắt buộc).
**Chạy song song với T01 và T02.** Bạn **không** tạo hay sửa `pyproject.toml`, `app/__init__.py`, `tests/__init__.py`, `app/calc/`, `app/domain/`, `data/`, kể cả khi chưa thấy chúng. Không chạy `uv sync`; nếu muốn tự thử, dùng `python -m pytest tests/deid` khi môi trường đã sẵn.

## 1. Mục tiêu

Bước B2: trước khi văn bản bệnh án đi tới LLM, thay mọi thông tin định danh bằng mã tạm; bảng ánh xạ giữ tại chỗ để giao diện ghép lại. Chỉ dùng thư viện chuẩn và pydantic.

## 2. Phạm vi file được tạo

```text
app/deid/__init__.py
app/deid/scrubber.py
tests/deid/__init__.py
tests/deid/test_scrubber.py
```

## 3. Giao diện

```python
class ThayThe(BaseModel):
    loai: str        # HN, CCCD, SDT, BHYT, EMAIL, NGAY, TEN
    ma_tam: str      # ví dụ "[SDT_1]"

class ScrubResult(BaseModel):
    van_ban: str                 # văn bản đã che
    thay_the: list[ThayThe]      # theo thứ tự xuất hiện lần đầu
    anh_xa: dict[str, str]       # ma_tam -> giá trị gốc

class DeidError(Exception): ...

def scrub_text(van_ban: str) -> ScrubResult: ...
def restore_text(van_ban: str, anh_xa: dict[str, str]) -> str: ...
```

## 4. Quy tắc che

Áp dụng theo đúng thứ tự dưới đây (mẫu dài và đặc hiệu trước, để số 12 chữ số không bị bắt nhầm thành mã 9 chữ số).

| Thứ tự | Loại | Mẫu | Ví dụ |
| :-: | :--- | :--- | :--- |
| 1 | `EMAIL` | địa chỉ email thông thường | `a.b@example.com` |
| 2 | `BHYT` | 2 chữ cái + 13 chữ số, liền nhau, không phân biệt hoa thường | `DN4010123456789` |
| 3 | `CCCD` | đúng 12 chữ số, không dính chữ số khác hai bên | `001099012345` |
| 4 | `SDT` | `0` hoặc `+84` hoặc `84`, tiếp theo một trong `3 5 7 8 9`, rồi 8 chữ số; cho phép dấu cách, chấm hoặc gạch giữa các nhóm | `0912 345 678`, `+84912345678` |
| 5 | `HN` | đúng 9 chữ số, không dính chữ số khác hai bên | `123456789` |
| 6 | `NGAY` | `dd/mm/yyyy`, `dd-mm-yyyy`, `dd.mm.yyyy`, và `dd/mm` (ngày 1–31, tháng 1–12) | `05/11/2026`, `5/11` |
| 7 | `TEN` | sau một danh xưng, 2–4 từ liền nhau đều viết hoa chữ đầu (chữ cái tiếng Việt có dấu). Giữ danh xưng, chỉ thay phần tên. Danh xưng (không phân biệt hoa thường, có thể kèm dấu chấm hoặc dấu hai chấm): `BN`, `bệnh nhân`, `người bệnh`, `BS`, `bác sĩ`, `ĐD`, `điều dưỡng`, `DS`, `dược sĩ`, `ông`, `bà`, `anh`, `chị` | `BS Nguyễn Văn An` → `BS [TEN_1]` |

Quy tắc khác:

- Mã tạm dạng `[LOAI_n]`, `n` đếm từ 1 riêng cho từng loại.
- Cùng một giá trị gốc (so sánh nguyên văn) xuất hiện nhiều lần → cùng một mã tạm.
- **Không che số liệu lâm sàng:** số thập phân, số kèm đơn vị, phân số kiểu `120/80` không được thành `NGAY`. Để phân biệt: `NGAY` dạng `dd/mm` chỉ nhận khi không có chữ số, dấu `/`, dấu `,` hoặc dấu `.` dính liền ngay trước hoặc ngay sau, và phần "tháng" ≤ 12; huyết áp `120/80` có phần đầu > 31 nên không khớp. Trường hợp mơ hồ thật sự như `5/10` được phép che (thà che thừa).
- Văn bản đã có sẵn chuỗi dạng `[TEN_1]` thì không được làm hỏng `restore_text`: nếu văn bản đầu vào chứa chuỗi khớp `\[(HN|CCCD|SDT|BHYT|EMAIL|NGAY|TEN)_\d+\]` → ném `DeidError` (đầu vào đáng ngờ).
- **Đóng khi lỗi:** mọi ngoại lệ không lường trước bên trong `scrub_text` phải được bọc thành `DeidError`. Không bao giờ trả về văn bản gốc khi lỗi. Đầu vào không phải `str` → `DeidError`.
- Chuỗi rỗng → trả `van_ban=""`, hai danh sách rỗng.
- `restore_text(scrub_text(x).van_ban, scrub_text(x).anh_xa) == x` với mọi `x` hợp lệ.

## 5. Kiểm thử phải có

Mỗi loại ở mục 4 ít nhất 2 ca dương và 1 ca âm. Bắt buộc có đúng các ca sau:

| Đầu vào | Kỳ vọng |
| :--- | :--- |
| `BN Trần Thị Bình, HN 123456789, sđt 0912 345 678` | Không còn `Trần Thị Bình`, `123456789`, `0912 345 678`; còn chữ `BN`; có `[TEN_1]`, `[HN_1]`, `[SDT_1]` |
| `CCCD 001099012345` | `[CCCD_1]`, không có `[HN_` |
| `Thẻ BHYT DN4010123456789` | `[BHYT_1]` |
| `Huyết áp 120/80 mmHg, creatinin 212 umol/L, K 4.5` | Văn bản không đổi, `thay_the == []` |
| `Vào viện 05/11/2026, tái khám 12-11-2026` | `[NGAY_1]`, `[NGAY_2]` |
| `BS Nguyễn Văn An hội chẩn. BS Nguyễn Văn An đồng ý.` | Cả hai chỗ đều là `[TEN_1]`; `anh_xa` có đúng 1 mục |
| `bệnh nhân sốt cao, ăn kém` | Không đổi (sau danh xưng không phải tên viết hoa) |
| `Liên hệ a.b@example.com` | `[EMAIL_1]` |
| `Ghi chú [TEN_1] có sẵn` | `DeidError` |
| `scrub_text(None)` | `DeidError` |

Thêm: test khứ hồi `restore_text` trên ít nhất 5 câu; test `scrub_text("")`.

## 6. Nghiệm thu

Người review sẽ chạy:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q tests/deid
```

## 7. Cấm làm

- Không thêm thư viện (không spaCy, không Presidio ở bản này).
- Không ghi log nội dung văn bản.
- Không commit.
