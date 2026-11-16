# T07-fix-1 – Chỉnh nhỏ giao diện sau khi review T07

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort high) · **Ngày:** 16/11/2026
**Đọc trước:** `AGENTS.md` (bắt buộc), `plan/briefs/T07-pipeline-va-giao-dien.md` (brief gốc, vẫn còn hiệu lực).

T07 đã chạy được trên cả 6 ca demo. Brief này chỉ sửa 5 điểm người review thấy khi mở giao diện. Không làm gì ngoài 5 điểm này.

## 1. Phạm vi file được sửa

```text
app/pipeline.py                    (chỉ ruff format)
app/ui/view_model.py
app/ui/streamlit_app.py
tests/ui/test_view_model.py
data/kb/quy_tac_lieu_than.json     (chỉ thêm dấu tiếng Việt, xem mục 2.4)
tests/rules/test_renal_dose.py     (chỉ đổi chuỗi kỳ vọng tương ứng mục 2.4)
```

Không sửa `app/rules/`, `app/calc/`, `app/domain/`, `app/deid/`, `data/mock/`, `data/gold/`, `pyproject.toml`.

## 2. Năm điểm phải sửa

### 2.1 Định dạng

`uv run ruff format --check .` đang báo `app/pipeline.py` và `app/ui/view_model.py`. Chạy `uv run ruff format` trên các file trong phạm vi; không đổi logic `app/pipeline.py`.

### 2.2 BSA hiển thị 2 chữ số thập phân

Ô `bsa_mosteller` đang hiện `1,8`; phải hiện `1,82` (DEMO-01) và `1,47` (DEMO-02). Thêm vào `view_model.py`:

```python
SO_THAP_PHAN: dict[str, int] = {"bsa_mosteller": 2}   # công thức khác mặc định 1
def metric_text(cong_thuc: str, ket_qua: float | None) -> str
```

`streamlit_app.py` dùng `metric_text` cho giá trị `st.metric`.

### 2.3 Nhãn nút ở thanh bên không được diễn giải markdown

Nhãn `st.sidebar.button` đang ghép `mo_ta_ngan` và tên khoa từ dữ liệu ca; Streamlit diễn giải nhãn nút như markdown. Thêm vào `view_model.py`:

```python
def plain_label(text: str) -> str
```

thêm `\` trước mỗi ký tự trong ``\ ` * _ [ ] ( ) # ~ < > | ! $ :`` và thay xuống dòng trong đầu vào bằng dấu cách. Áp dụng cho từng phần lấy từ dữ liệu ca (`ca_id`, khoa, `mo_ta_ngan`) trước khi ghép nhãn; ký tự xuống dòng do chính code ghép giữa dòng tiêu đề và mô tả thì giữ.

### 2.4 Bảng luật thận: thêm dấu tiếng Việt

Trong `data/kb/quy_tac_lieu_than.json`, các chuỗi `ghi_chu`, `nguon`, `khuyen_cao` đang viết không dấu nên hiện lên giao diện là `Mot nua lieu khuyen cao, moi 12 gio`. Đổi thành đúng các chuỗi sau, **không đổi con số, ngưỡng, cấu trúc hay thứ tự**:

| Cũ | Mới |
| :--- | :--- |
| `Ban MVP. Chua duoc duoc si duyet.` | `Bản MVP. Chưa được dược sĩ duyệt.` |
| `Nhan thuoc FDA: MERREM IV (meropenem for injection), muc Dosage and Administration - Use in Adult Patients with Renal Impairment` | `Nhãn thuốc FDA: MERREM IV (meropenem for injection), mục Dosage and Administration - Use in Adult Patients with Renal Impairment` |
| `Lieu khuyen cao, moi 8 gio` | `Liều khuyến cáo, mỗi 8 giờ` |
| `Lieu khuyen cao, moi 12 gio` | `Liều khuyến cáo, mỗi 12 giờ` |
| `Mot nua lieu khuyen cao, moi 12 gio` | `Một nửa liều khuyến cáo, mỗi 12 giờ` |
| `Mot nua lieu khuyen cao, moi 24 gio` | `Một nửa liều khuyến cáo, mỗi 24 giờ` |

File lưu UTF-8 không BOM. Trong `tests/rules/test_renal_dose.py` (và test khác nếu có so chuỗi này) chỉ đổi các chuỗi kỳ vọng tương ứng. Nếu code trong `app/rules/` so sánh với chuỗi không dấu thì **dừng lại và báo**, không sửa `app/rules/`.

### 2.5 Mã nội bộ hiện thô trên giao diện

Thêm vào `view_model.py` ba bảng nhãn và hàm tra có dự phòng (không có trong bảng thì trả nguyên mã):

```python
NHAN_DAU_VAO: dict[str, str]    # can_nang_kg "cân nặng", chieu_cao_cm "chiều cao", creatinin "creatinin máu",
                                # tuoi "tuổi", gioi_tinh "giới tính", creatinin_don_vi "đơn vị creatinin",
                                # so_lieu_hop_le "số liệu hợp lệ"
NHAN_LOAI_CAN_CU: dict[str, str]  # du_lieu "Dữ liệu ca", tinh_toan "Tính toán", tai_lieu "Tài liệu"
NHAN_LUONG_DUYET: dict[str, str]  # lấy đúng các giá trị Literal của trường luong_duyet trong app/domain/models.py
def label_of(table: dict[str, str], code: str) -> str
```

Dùng ở: dòng `Thiếu: …` dưới ô chỉ số, tên đầu vào trong expander "Đầu vào và công thức", loại căn cứ trong expander "Căn cứ", và `Luồng:` ở mục y lệnh chờ duyệt. Tên khoá của `thieu_dau_vao` và `CalcInput.ten` lấy theo đúng những gì `app/calc` trả ra (đọc `app/calc`, không sửa); khoá nào chưa có trong bảng trên thì thêm nhãn tương ứng.

## 3. Kiểm thử thêm (trong `tests/ui/test_view_model.py`)

- `metric_text("bsa_mosteller", 1.8182) == "1,82"`; `metric_text("bmi", 24.221) == "24,2"`; `metric_text("bmi", None) == "—"`.
- `plain_label("a*b_[c](d)")` có `\` trước cả 7 ký tự đặc biệt; `plain_label("x\ny") == "x y"`; chuỗi tiếng Việt có dấu không đổi.
- `label_of(NHAN_LOAI_CAN_CU, "tinh_toan") == "Tính toán"`; `label_of(NHAN_LOAI_CAN_CU, "la") == "la"`.
- Mọi giá trị Literal của `luong_duyet` đều có trong `NHAN_LUONG_DUYET`.
- Chạy `run_case` trên DEMO-02: `mo_ta` của phát hiện yếu tố 6 chứa `Một nửa liều khuyến cáo, mỗi 12 giờ`.
- Test tĩnh cũ (không có `unsafe_allow_html`) giữ nguyên.

## 4. Nghiệm thu

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Cả ba phải sạch; hiện đang có 332 test qua, không test cũ nào được xoá.

## 5. Cấm làm

- Không đổi ngưỡng, liều, công thức, dữ liệu ca.
- Không thêm thư viện, trang, tính năng.
- Không dùng `unsafe_allow_html`; văn bản từ dữ liệu ca vẫn hiển thị qua `st.text` / `st.dataframe`.
- Không commit, không push.
