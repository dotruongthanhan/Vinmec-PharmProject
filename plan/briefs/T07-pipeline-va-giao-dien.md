# T07 – Đường chạy (pipeline) và giao diện Streamlit

**Giao cho:** agy CLI (`gemini-4-hydrogen-high`) · **Ngày:** 16/11/2026
**Đọc trước:** `AGENTS.md` (bắt buộc); **chỉ đọc**: `app/domain/models.py`, `app/domain/loader.py`, `app/calc/`, `app/rules/types.py`, `app/rules/engine.py`, `app/rules/renal_dose.py`, một ca ở `data/mock/demo/`.

## 1. Mục tiêu

Lát cắt dọc đầu tiên trên giao diện: dược sĩ mở web app, chọn một ca, thấy thẻ tóm tắt bệnh nhân, các chỉ số đã tính, bảng nhận định 3 cột có căn cứ, và bấm phản hồi trên từng nhận định. Bản này **chưa có LLM**: bảng nhận định lấy từ bộ luật.

## 2. Phạm vi file được tạo hoặc sửa

```text
app/pipeline.py
app/feedback.py
app/ui/__init__.py
app/ui/view_model.py
app/ui/streamlit_app.py
tests/test_pipeline.py
tests/test_feedback.py
tests/ui/__init__.py
tests/ui/test_view_model.py
pyproject.toml     (chỉ thêm "streamlit" vào dependencies)
.gitignore         (chỉ thêm 1 dòng cuối file: data/runtime/)
```

Không sửa `app/domain/`, `app/calc/`, `app/rules/`, `data/`.

## 3. Đường chạy – `app/pipeline.py`

```python
class KetQuaThamDinh(BaseModel):
    ca_id: str
    chi_so: list[CalcResult]
    phat_hien: list[PhatHien]
    thoi_gian_ms: float

def run_case(ca: CaBenh, renal_rules) -> KetQuaThamDinh: ...
```

- `chi_so` gồm đúng 4 kết quả theo thứ tự: `cockcroft_gault` (cân nặng `thuc_te`), `egfr_ckd_epi_2021`, `bmi`, `bsa_mosteller`. Đầu vào lấy từ `ca.nguoi_benh`, `latest_vital(ca, "can_nang")`, `latest_vital(ca, "chieu_cao")`, `latest_lab(ca, "creatinin")`.
- Sau khi tính, **bổ sung nguồn gốc** cho từng `CalcInput` trong `dau_vao`: mục tên `creatinin` nhận `ban_ghi_id` = `xet_nghiem_id` và `thoi_diem` = `thoi_diem_ket_qua`; mục `can_nang_kg` và `chieu_cao_cm` nhận `sinh_hieu_id` và `thoi_diem_do`. Dùng `model_copy(update=...)`, không sửa `app/calc`.
- Thiếu số liệu thì truyền `None` để hàm tính trả `thieu_dau_vao`. Nếu hàm tính ném `ValueError` (số liệu ngoài miền, hoặc tuổi dưới 18 với CKD-EPI): tạo `CalcResult` có `ket_qua=None`, `thieu_dau_vao=["so_lieu_hop_le"]`, `ghi_chu=[thông báo lỗi]`, giữ đúng `cong_thuc`, `don_vi`, `tham_khao`; **không để ngoại lệ thoát ra**.
- `phat_hien = run_rules(ca, renal_rules)`.
- `thoi_gian_ms` đo bằng `time.perf_counter()`.

## 4. Phản hồi – `app/feedback.py`

```python
class PhanHoi(BaseModel):
    thoi_diem: AwareDatetime
    ca_id: str
    ma_luat: str
    yeu_to: int
    chi_tiet_y_lenh_id: list[str]
    phan_hoi: Literal["dong_y", "bac_bo", "can_sua"]
    ly_do: str | None = None

def save_feedback(item: PhanHoi, path: Path = Path("data/runtime/phan_hoi.jsonl")) -> None
def load_feedback(path: Path = ...) -> list[PhanHoi]
```

Ghi nối thêm một dòng JSON (UTF-8) mỗi lần; tự tạo thư mục nếu chưa có. File chưa tồn tại thì `load_feedback` trả danh sách rỗng.

## 5. Chuẩn bị dữ liệu hiển thị – `app/ui/view_model.py`

Hàm thuần, không import `streamlit`, để kiểm thử được.

- `TEN_YEU_TO: dict[int, str]`:
  1 "Dị ứng, quá mẫn" · 2 "Trùng lặp thuốc" · 3 "Chỉ định, liều, đường dùng" · 4 "Tương tác thuốc" · 5 "Độc tính" · 6 "Cơ địa và xét nghiệm" · 7 "Yếu tố khác (lịch dùng…)"
- `NHAN_KET_LUAN: dict[str, str]`: `dat` "Đạt" · `can_xem` "Cần xem" · `khong_du_du_lieu` "Không đủ dữ liệu" · `ngoai_hdsd` "Ngoài HDSD / phác đồ"
- `allergy_text(ca) -> str`: ba câu khác hẳn nhau cho ba trạng thái:
  - `co_di_ung`: `"Có dị ứng: <tác nhân> (<phản ứng>)"`, nhiều dị ứng nối bằng `"; "`
  - `khong_di_ung_da_hoi`: `"Đã hỏi, không ghi nhận dị ứng"`
  - `chua_co_thong_tin`: `"CHƯA CÓ THÔNG TIN DỊ ỨNG"`
- `drug_label(ca, chi_tiet_y_lenh_id) -> str`: tên thuốc (hoặc `ten_tu_do`) kèm liều và đường dùng, ví dụ `"Meropenem 1 g – truyền tĩnh mạch – 3 lần/ngày"`.
- `lab_rows(ca) -> list[dict]`: mỗi xét nghiệm một dòng, mới nhất trước, có cột `ngoai_nguong: bool` (đúng khi `gia_tri_so` nằm ngoài `nguong_duoi`/`nguong_tren`; ngưỡng nào `None` thì bỏ qua ngưỡng đó).
- `finding_rows(ca, phat_hien) -> list[dict]`: mỗi phát hiện một dòng với khoá `thuoc` (các nhãn thuốc nối bằng `" + "`), `yeu_to` (dạng `"6. Cơ địa và xét nghiệm"`), `nhan_xet` (= `mo_ta`), `ket_luan` (nhãn tiếng Việt), `muc_do`, `can_cu`, `thong_tin_con_thieu`, `ma_luat`, `chi_tiet_y_lenh_id`.
- `split_findings(rows) -> tuple[list, list]`: tách `(cần chú ý, đạt)`; nhóm "cần chú ý" là mọi dòng có `ket_luan` khác "Đạt", giữ nguyên thứ tự đầu vào.
- `count_serious(phat_hien) -> int`: số phát hiện `can_xem` + `nghiem_trong`.
- `format_number(x: float | None, digits: int = 1) -> str`: `None` → `"—"`; còn lại làm tròn và dùng dấu phẩy thập phân kiểu Việt (ví dụ `16.0` → `"16,0"`).

## 6. Giao diện – `app/ui/streamlit_app.py`

Chạy bằng `uv run streamlit run app/ui/streamlit_app.py`. Thư mục ca mặc định `data/mock/demo`, đổi được bằng biến môi trường `CDSS_CASE_DIR`. `st.set_page_config(layout="wide", page_title="Hỗ trợ thẩm định y lệnh")`.

**Thanh bên:** tiêu đề "Y lệnh chờ thẩm định"; mỗi ca một nút chọn hiển thị `ca_id`, `mo_ta_ngan`, khoa, và số mục nghiêm trọng (nếu > 0). Ca đang chọn lưu trong `st.session_state`.

**Vùng chính, từ trên xuống:**

1. Dải thông báo cố định (`st.info`): `Kết quả tham khảo từ dữ liệu giả lập. Dược sĩ kiểm chứng và quyết định.`
2. **Thẻ tóm tắt bệnh nhân** (3 cột):
   - Cột 1: tuổi, giới, cân nặng, chiều cao, khoa, nội trú / ngoại trú, thời điểm vào viện.
   - Cột 2: chẩn đoán (chính trước, kèm mã ICD-10), cơ địa đặc biệt nếu có, và dòng dị ứng từ `allergy_text`. Trạng thái `chua_co_thong_tin` hiển thị bằng `st.warning`; `co_di_ung` bằng `st.error`; còn lại chữ thường.
   - Cột 3: diễn biến mới nhất (thời điểm + nội dung).
3. **Chỉ số đã tính:** 4 ô (`st.metric`): giá trị qua `format_number`, đơn vị. Chỉ số thiếu đầu vào hiện `"—"` và ghi `"Thiếu: <danh sách>"`. Dưới mỗi ô một `st.expander("Đầu vào và công thức")` liệt kê từng đầu vào (tên, giá trị, đơn vị, mã bản ghi, thời điểm), ghi chú, và trích dẫn `tham_khao`.
4. **Xét nghiệm:** bảng từ `lab_rows`; dòng ngoài ngưỡng có dấu `▲` hoặc `▼` ở cột giá trị. Vi sinh (nếu có) liệt kê bên dưới: bệnh phẩm, vi khuẩn, kháng sinh đồ.
5. **Y lệnh chờ duyệt:** bảng các dòng thuốc (thuốc, liều, tần suất, đường dùng, các mốc lịch dùng). Thuốc đang dùng (nếu có) ở bảng thứ hai kèm trạng thái.
6. **Bảng nhận định:** tiêu đề phụ nêu số mục cần chú ý. Mỗi mục "cần chú ý" là một khối có viền (`st.container(border=True)`) gồm 3 cột **Thuốc | Yếu tố kiểm tra | Nhận xét**, nhãn kết luận (nghiêm trọng dùng `st.error`, cần lưu ý dùng `st.warning`, không đủ dữ liệu dùng `st.info`), dòng "Còn thiếu: …" nếu có, và `st.expander("Căn cứ")` liệt kê theo thứ tự từng căn cứ (loại, mã bản ghi, mô tả). Bên dưới mỗi khối: 3 nút **Đồng ý · Bác bỏ · Cần sửa** và ô nhập lý do; bấm thì gọi `save_feedback` và hiện `st.toast("Đã ghi phản hồi")`. Mỗi widget có `key` duy nhất ghép từ `ca_id`, `ma_luat`, và các `chi_tiet_y_lenh_id`.
7. Các mục "Đạt" gom trong một `st.expander("Các mục đạt (n)")`, dạng bảng gọn.
8. Chân trang: thời gian chạy (ms) và dòng `Chưa có bước LLM: bảng nhận định hiện do bộ luật sinh ra.`

**An toàn hiển thị (bắt buộc):**

- Không dùng `unsafe_allow_html=True` ở bất kỳ đâu.
- Mọi văn bản đến từ dữ liệu ca (diễn biến, chẩn đoán, tên thuốc gõ tay, mô tả dị ứng, ghi chú) hiển thị bằng `st.text(...)` hoặc trong `st.dataframe` / `st.table`, **không** qua `st.markdown` / `st.write` (để nội dung không được diễn giải thành markdown, liên kết hay ảnh).
- Nạp ca lỗi (JSON sai lược đồ) thì hiện `st.error` nêu tên file, không làm sập cả trang; các ca khác vẫn mở được.
- Nạp dữ liệu và bảng luật qua hàm có `@st.cache_data` hoặc `@st.cache_resource`.

## 7. Kiểm thử phải có

- `run_case` trên DEMO-02: `chi_so[0].cong_thuc == "cockcroft_gault"`, kết quả ≈ 15.9988 (`rel=1e-3`); đầu vào `creatinin` có `ban_ghi_id` trỏ đúng kết quả 212 và có `thoi_diem`; đầu vào `can_nang_kg` có `ban_ghi_id`.
- `run_case` trên một ca bị xoá hết sinh hiệu (dựng bằng `model_copy`): Cockcroft-Gault có `ket_qua is None` và `can_nang_kg` trong `thieu_dau_vao`; không ném lỗi.
- `run_case` trên ca có người bệnh 10 tuổi: mục eGFR có `ket_qua is None`, `thieu_dau_vao == ["so_lieu_hop_le"]`; không ném lỗi.
- `run_case` trên cả 6 ca demo đều chạy, `thoi_gian_ms >= 0`.
- `allergy_text` cho đủ 3 trạng thái (dùng DEMO-01, DEMO-03, DEMO-06).
- `lab_rows` DEMO-04: WBC và CRP có `ngoai_nguong == True`, creatinin `False`.
- `finding_rows` + `split_findings` trên DEMO-02: đúng 1 dòng cần chú ý, cột `yeu_to` bắt đầu bằng `"6."`, cột `thuoc` chứa "Meropenem".
- `format_number(None) == "—"`, `format_number(15.9988) == "16,0"`.
- `save_feedback` rồi `load_feedback` với `tmp_path`: đọc lại đúng 2 mục đã ghi, giữ dấu tiếng Việt trong `ly_do`.
- Kiểm tra tĩnh: nội dung file `app/ui/streamlit_app.py` không chứa chuỗi `unsafe_allow_html`.

## 8. Nghiệm thu

Người review sẽ chạy (bạn không cần chạy lệnh shell):

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run streamlit run app/ui/streamlit_app.py --server.headless true
```

rồi mở trình duyệt xem cả 6 ca.

## 9. Cấm làm

- Không gọi LLM, không gọi mạng.
- Không thêm thư viện ngoài `streamlit`.
- Không thêm trang, biểu đồ, đăng nhập, chế độ nhanh.
- Không sửa luật, công thức, mô hình, dữ liệu ca.
- Không commit.
