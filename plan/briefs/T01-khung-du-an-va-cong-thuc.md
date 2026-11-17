# T01 – Khung dự án và mô-đun công thức lâm sàng

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort high) · **Ngày:** 16/11/2026
**Đọc trước:** `AGENTS.md` (bắt buộc). Không cần đọc toàn bộ plan.

## 1. Mục tiêu

Dựng khung dự án Python và mô-đun `app/calc` gồm các công thức lâm sàng dưới đây, có kiểm thử. Đây là bước B3 của hệ thống: tính chỉ số bằng code, nêu rõ đầu vào đã dùng và đầu vào còn thiếu.

## 2. Phạm vi file được tạo

```text
pyproject.toml
uv.lock                      (do uv sinh ra)
.python-version              (nội dung: 3.13)
app/__init__.py
app/calc/__init__.py
app/calc/types.py
app/calc/units.py
app/calc/renal.py
app/calc/body.py
tests/__init__.py
tests/calc/__init__.py
tests/calc/test_units.py
tests/calc/test_renal.py
tests/calc/test_body.py
```

Không tạo file nào khác. Không sửa file đã có trong kho.

## 3. Thiết lập

- `uv init` không phù hợp vì kho đã có file; hãy viết `pyproject.toml` tay.
- Tên dự án: `vinmec-pharm-cdss`, `requires-python = ">=3.11"`.
- Phụ thuộc chạy: `pydantic>=2`. Phụ thuộc phát triển (nhóm `dev`): `pytest`, `ruff`.
- Cấu hình `ruff`: `line-length = 100`, bật luật `E`, `F`, `I`, `UP`, `B`.
- Cấu hình `pytest`: `testpaths = ["tests"]`.
- `app` là gói cài được (để `from app.calc import ...` chạy trong test).

## 4. Kiểu dữ liệu chung – `app/calc/types.py`

```python
class CalcInput(BaseModel):
    ten: str                    # ví dụ "creatinin_huyet_thanh"
    gia_tri: float
    don_vi: str                 # ví dụ "umol/L"
    ban_ghi_id: str | None = None      # mã bản ghi nguồn, ví dụ "XN-0142"
    thoi_diem: datetime | None = None  # thời điểm lấy mẫu / đo

class CalcResult(BaseModel):
    cong_thuc: str              # mã công thức, ví dụ "cockcroft_gault"
    phien_ban: str              # ví dụ "1.0"
    ket_qua: float | None       # None khi thiếu đầu vào
    don_vi: str                 # ví dụ "mL/min"
    dau_vao: list[CalcInput]    # những đầu vào thực sự đã dùng
    thieu_dau_vao: list[str]    # tên các đầu vào còn thiếu; rỗng khi tính được
    ghi_chu: list[str]          # ví dụ "dùng cân nặng hiệu chỉnh"
    tham_khao: str              # trích dẫn bài báo gốc (mục 6)
```

Quy tắc chung cho mọi hàm công thức:

- Tham số lâm sàng đều là `X | None`. Thiếu tham số nào thì **không ném lỗi**: trả `ket_qua=None` và liệt kê tên tham số thiếu trong `thieu_dau_vao` (dùng đúng tên tham số của hàm).
- Giá trị ngoài miền hợp lệ (mục 7) thì ném `ValueError` với thông báo tiếng Việt nêu tên tham số và giá trị.
- Không làm tròn `ket_qua`.
- `dau_vao` ghi lại giá trị và đơn vị **như người gọi đưa vào** (trước khi quy đổi).

## 5. Quy đổi đơn vị – `app/calc/units.py`

- `creatinine_to_mg_dl(gia_tri: float, don_vi: str) -> float`
  - Chấp nhận `"mg/dL"` và `"umol/L"` (chấp nhận thêm cách viết `"µmol/L"`, `"μmol/L"`; không phân biệt hoa thường).
  - `mg/dL = µmol/L ÷ 88.4`.
  - Đơn vị khác → `ValueError`.
- `cm_to_inch(cm: float) -> float` với `1 inch = 2.54 cm`.

## 6. Công thức

Giới tính dùng `Literal["nam", "nu"]`.

### 6.1. `app/calc/body.py`

**a) `bmi(can_nang_kg, chieu_cao_cm) -> CalcResult`**
`BMI = cân nặng / (chiều cao tính bằng mét)²`. Đơn vị `kg/m2`. `cong_thuc="bmi"`.
Tham khảo: `"WHO. Body mass index (BMI)."`

**b) `bsa_mosteller(can_nang_kg, chieu_cao_cm) -> CalcResult`**
`BSA = sqrt(chiều cao cm × cân nặng kg / 3600)`. Đơn vị `m2`. `cong_thuc="bsa_mosteller"`.
Tham khảo: `"Mosteller RD. N Engl J Med 1987;317:1098."`

**c) `bsa_dubois(can_nang_kg, chieu_cao_cm) -> CalcResult`**
`BSA = 0.007184 × cân nặng^0.425 × chiều cao cm^0.725`. Đơn vị `m2`. `cong_thuc="bsa_dubois"`.
Tham khảo: `"Du Bois D, Du Bois EF. Arch Intern Med 1916;17:863-871."`

**d) `ibw_devine(gioi_tinh, chieu_cao_cm) -> CalcResult`**
Nam: `50 + 2.3 × (chiều cao inch − 60)`. Nữ: `45.5 + 2.3 × (chiều cao inch − 60)`. Đơn vị `kg`. `cong_thuc="ibw_devine"`.
Nếu chiều cao dưới 60 inch (152,4 cm): **vẫn tính theo công thức** (ra số nhỏ hơn mức gốc) và thêm ghi chú `"chieu cao duoi 152.4 cm: cong thuc Devine kem tin cay"`.
Tham khảo: `"Devine BJ. Drug Intell Clin Pharm 1974;8:650-655."`

**e) `adjusted_body_weight(gioi_tinh, chieu_cao_cm, can_nang_kg) -> CalcResult`**
`AdjBW = IBW + 0.4 × (cân nặng thực − IBW)`, IBW theo Devine. Đơn vị `kg`. `cong_thuc="adjusted_body_weight"`.
Tham khảo: `"Bauer LA. Applied Clinical Pharmacokinetics. Hệ số hiệu chỉnh 0.4."`

### 6.2. `app/calc/renal.py`

**f) `cockcroft_gault(tuoi, gioi_tinh, can_nang_kg, creatinin, creatinin_don_vi, loai_can_nang="thuc_te", chieu_cao_cm=None) -> CalcResult`**

`CrCl (mL/min) = (140 − tuổi) × cân nặng / (72 × creatinin mg/dL)`, nhân `0.85` nếu là nữ.

- `loai_can_nang: Literal["thuc_te", "ly_tuong", "hieu_chinh"]`.
  - `"thuc_te"`: dùng `can_nang_kg`.
  - `"ly_tuong"`: dùng IBW Devine; cần thêm `chieu_cao_cm`.
  - `"hieu_chinh"`: dùng AdjBW; cần `chieu_cao_cm` và `can_nang_kg`.
- Đầu vào cần mà thiếu thì vào `thieu_dau_vao` (ví dụ chọn `"ly_tuong"` mà không có chiều cao → thiếu `chieu_cao_cm`).
- `ghi_chu` luôn có một dòng nêu loại cân nặng đã dùng và giá trị cân nặng đó.
- Đơn vị `mL/min`. `cong_thuc="cockcroft_gault"`.
- Tham khảo: `"Cockcroft DW, Gault MH. Nephron 1976;16:31-41."`
- **Không tự chọn loại cân nặng.** Việc chọn là của người gọi; chính sách chọn sẽ do dược sĩ quyết định sau.

**g) `egfr_ckd_epi_2021(tuoi, gioi_tinh, creatinin, creatinin_don_vi) -> CalcResult`**

`eGFR = 142 × min(Scr/κ, 1)^α × max(Scr/κ, 1)^(−1.200) × 0.9938^tuổi × (1.012 nếu nữ)`

- `Scr` là creatinin tính bằng mg/dL.
- Nữ: `κ = 0.7`, `α = −0.241`. Nam: `κ = 0.9`, `α = −0.302`.
- Đơn vị `mL/min/1.73m2`. `cong_thuc="egfr_ckd_epi_2021"`.
- Tuổi dưới 18: ném `ValueError` (công thức chỉ dùng cho người lớn).
- Tham khảo: `"Inker LA, et al. N Engl J Med 2021;385:1737-1749."`

## 7. Miền hợp lệ (ngoài miền → `ValueError`)

| Tham số | Miền |
| :--- | :--- |
| `tuoi` | 0 < tuổi ≤ 120 (riêng CKD-EPI: ≥ 18) |
| `can_nang_kg` | 0.3 ≤ cân nặng ≤ 400 |
| `chieu_cao_cm` | 20 ≤ chiều cao ≤ 250 |
| creatinin sau khi đổi sang mg/dL | 0.05 ≤ giá trị ≤ 40 |

Lý do của chặn creatinin: bắt lỗi nhập nhầm đơn vị (ví dụ 212 ghi là mg/dL trong khi thực ra là µmol/L).

## 8. Kiểm thử phải có

Dùng `pytest.approx` với `rel=1e-3` cho các giá trị dưới đây. Đây là giá trị người giao việc đã tự tính; nếu code của bạn ra khác, **đừng sửa giá trị kỳ vọng**, hãy kiểm lại code và ghi vào báo cáo nếu bạn cho rằng giá trị kỳ vọng sai.

| # | Hàm | Đầu vào | Kỳ vọng |
| :-: | :--- | :--- | :--- |
| 1 | `creatinine_to_mg_dl` | 88.4 µmol/L | 1.0 |
| 2 | `creatinine_to_mg_dl` | 212 umol/L | 2.39819 |
| 3 | `bmi` | 70 kg, 170 cm | 24.2215 |
| 4 | `bsa_mosteller` | 70 kg, 170 cm | 1.81812 |
| 5 | `bsa_dubois` | 70 kg, 170 cm | 1.80971 |
| 6 | `ibw_devine` | nam, 170 cm | 65.9370 |
| 7 | `ibw_devine` | nữ, 160 cm | 52.3819 |
| 8 | `adjusted_body_weight` | nam, 170 cm, 100 kg | 79.5622 |
| 9 | `cockcroft_gault` | 60 tuổi, nam, 72 kg, 1.0 mg/dL, thực tế | 80.0 |
| 10 | `cockcroft_gault` | 60 tuổi, nữ, 72 kg, 1.0 mg/dL, thực tế | 68.0 |
| 11 | `cockcroft_gault` | 75 tuổi, nữ, 50 kg, 212 µmol/L, thực tế | 15.9988 |
| 12 | `cockcroft_gault` | 60 tuổi, nam, 100 kg, 170 cm, 1.0 mg/dL, hiệu chỉnh | 88.4024 |
| 13 | `egfr_ckd_epi_2021` | 60 tuổi, nam, 1.0 mg/dL | 86.1626 |
| 14 | `egfr_ckd_epi_2021` | 60 tuổi, nữ, 1.0 mg/dL | 64.4950 |
| 15 | `egfr_ckd_epi_2021` | 50 tuổi, nữ, 0.6 mg/dL | 109.283 |

Kiểm thử hành vi (mỗi ý ít nhất một test):

- Thiếu `can_nang_kg` ở `cockcroft_gault` → `ket_qua is None`, `thieu_dau_vao == ["can_nang_kg"]`.
- Thiếu cả `can_nang_kg` và `creatinin` → cả hai tên có trong `thieu_dau_vao`.
- `loai_can_nang="ly_tuong"` mà không có `chieu_cao_cm` → thiếu `chieu_cao_cm`.
- Creatinin `212` với đơn vị `"mg/dL"` → `ValueError`.
- Đơn vị creatinin lạ (`"g/L"`) → `ValueError`.
- `egfr_ckd_epi_2021` với tuổi 10 → `ValueError`.
- `dau_vao` của test 11 ghi creatinin `212` và đơn vị người gọi đưa vào, không phải giá trị đã quy đổi.
- `ghi_chu` của test 12 có nêu loại cân nặng "hieu_chinh".
- `ibw_devine` nam 150 cm → vẫn có kết quả và có ghi chú cảnh báo.
- Mọi `CalcResult` tính được đều có `tham_khao` không rỗng và `thieu_dau_vao == []`.

## 9. Nghiệm thu (phải chạy và dán kết quả vào báo cáo)

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Cả bốn lệnh phải thành công.

## 10. Cấm làm

- Không thêm công thức khác (Child-Pugh, MELD, QTc… để task sau).
- Không viết giao diện, cơ sở dữ liệu, lớp gọi LLM.
- Không tự chọn loại cân nặng cho Cockcroft-Gault.
- Không làm tròn kết quả trong hàm.
- Không commit.
