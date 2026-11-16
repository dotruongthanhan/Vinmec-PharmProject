# T13 – Giao diện đợt 1 theo plan 1.2

**Giao cho:** agy CLI (`gemini-4-hydrogen-xhigh`) · **Ngày:** 16/11/2026
**Đọc trước (bắt buộc):** `AGENTS.md`; `plan/plan-1.2-giao-dien-ui-ux.md` (toàn bộ, đây là bản thiết kế); **chỉ đọc**: `app/ui/` hiện có, `app/pipeline.py`, `app/feedback.py`, `app/domain/models.py`, `app/domain/loader.py`, `app/rules/types.py`, `app/calc/types.py`, một ca ở `data/mock/demo/` và đáp án tương ứng ở `data/gold/demo/`.

**Không gọi công cụ shell / terminal / command dưới bất kỳ hình thức nào** (kể cả `ls`, `cat`, `python`, `uv`, `git`): phiên này không có quyền đó và gọi là mất toàn bộ kết quả. Chỉ dùng công cụ đọc file, liệt kê thư mục, ghi và sửa file. Người review sẽ tự chạy lệnh nghiệm thu.

**Đang có task khác chạy song song (T11).** Bạn **không** tạo hay sửa: `pyproject.toml`, `config/`, `app/config/`, `app/core/`, `app/providers/`, `app/storage/`, `app/container.py`, `app/rules/`, `app/calc/`, `app/domain/`, `app/deid/`, `app/pipeline.py`, `notebooks/`, `data/`, `tests/` ngoài các file ở mục 2. Không thêm thư viện: chỉ dùng `streamlit` (bản 1.67) và thư viện chuẩn.

## 1. Mục tiêu

Dựng lại giao diện Streamlit theo **đợt 1** ở mục 9 của plan 1.2: bố cục mục 3, tổ chức code mục 6, ngôn ngữ mục 5, trạng thái mục 4. Dữ liệu vẫn lấy từ `app.pipeline.run_case` (chưa có LLM, chưa có kho nguồn). Mọi thứ đang chạy đúng ở giao diện hiện tại phải tiếp tục chạy đúng.

## 2. Phạm vi file được tạo hoặc sửa

```text
app/ui/streamlit_app.py            (viết lại: chỉ lắp bố cục)
app/ui/view_model.py               (mở rộng; giữ nguyên tên và hành vi các hàm đang có)
app/ui/labels.py                   (mới; chuyển các bảng nhãn từ view_model sang, view_model xuất lại tên cũ để test cũ không vỡ)
app/ui/services.py                 (mới)
app/ui/state.py                    (mới)
app/ui/components/__init__.py      (mới)
app/ui/components/queue.py  case_header.py  summary.py  findings.py
app/ui/components/evidence_dialog.py  feedback.py  chat.py  detail_tabs.py  status.py
app/feedback.py                    (chỉ thêm 1 trường tuỳ chọn, mục 5)
.streamlit/config.toml             (mới: chủ đề sáng, font mặc định)
tests/ui/test_view_model.py        (giữ test cũ, thêm test mới)
tests/ui/test_labels.py  tests/ui/test_services.py  tests/ui/test_state.py  tests/ui/test_static_safety.py   (mới)
tests/test_feedback.py             (thêm test cho trường mới)
```

## 3. Lớp dịch vụ – `app/ui/services.py`

```python
class TrichDan(BaseModel):   so: int; loai: Literal["du_lieu","tinh_toan","tai_lieu"]; nhan: str; ban_ghi_id: str | None
class TraLoi(BaseModel):     trang_thai: Literal["chua_san_sang","ok","khong_co_nguon","ngoai_pham_vi","loi"]
                             noi_dung: str; trich_dan: list[TrichDan] = []; cong_cu_da_goi: list[str] = []

class ReviewService(Protocol):
    def list_cases(self) -> tuple[list[CaBenh], list[tuple[str, str]]]: ...   # (ca hợp lệ, [(tên file, lỗi)])
    def review(self, ca: CaBenh) -> KetQuaThamDinh: ...
class AskService(Protocol):
    def ask(self, ca: CaBenh, cau_hoi: str, lich_su: list[tuple[str, str]]) -> TraLoi: ...

class PipelineReviewService:          # dùng load_case + run_case như giao diện hiện tại
    def __init__(self, case_dir: Path, renal_rules_path: Path) -> None
class NotReadyAskService:             # luôn trả trang_thai="chua_san_sang", noi_dung cố định:
    # "Chức năng hỏi thêm chưa được nối với hệ thống. Bảng nhận định bên trái vẫn dùng được."
```

File này không import `streamlit`. Giao diện chỉ gọi hai dịch vụ này, không import `app.pipeline` hay `app.rules` ở nơi khác trong `app/ui/` (trừ kiểu dữ liệu để chú thích).

## 4. Chuẩn bị dữ liệu hiển thị – `app/ui/view_model.py` (hàm thuần, không import `streamlit`)

Giữ mọi hàm đang có. Thêm:

- `priority_of(phat_hien: list[PhatHien]) -> int`: 0 nếu có mục `can_xem` + `nghiem_trong`; 1 nếu có `can_xem` khác; 2 nếu có `ngoai_hdsd`; 3 nếu có `khong_du_du_lieu`; 4 nếu toàn `dat`.
- `queue_rows(cases, results) -> list[dict]`: mỗi ca một dòng `{ca_id, khoa, mo_ta, uu_tien, huy_hieu, so_nghiem_trong, so_can_luu_y, so_thieu_du_lieu}`, sắp theo `uu_tien` tăng dần rồi `thoi_diem_ke` của y lệnh chờ duyệt tăng dần. `huy_hieu` là chuỗi như `"⛔ 1 nghiêm trọng"`, `"⚠ 1 cần lưu ý"`, `"? 1 thiếu dữ liệu"`, `"✓ Đạt"` (luôn có chữ, không chỉ biểu tượng).
- `count_by_level(phat_hien) -> dict[str, int]` với khoá `nghiem_trong`, `can_luu_y`, `thieu_du_lieu`, `ngoai_hdsd`, `dat`.
- `header_info(ca, result) -> dict`: `ca_id`, `gioi_tuoi` (`"Nữ 75 tuổi"`), `can_nang` (`"50,0 kg"` hoặc `"chưa có cân nặng"`), `khoa_loai` (`"Hô hấp, nội trú"`), `crcl` (`"16,0 mL/phút"` hoặc `"—"`), `crcl_bat_thuong: bool` (đúng khi CrCl < 60), `di_ung_trang_thai`, `di_ung_text`.
- `length_of_stay_days(ca, now: datetime) -> int | None`: số ngày từ `thoi_diem_bat_dau` tới `now` (tham số, để test được).
- `lab_trends(ca, limit: int = 5) -> list[dict]`: xét nghiệm **ngoài ngưỡng** mới nhất của từng loại, mới nhất trước, tối đa `limit`; mỗi dòng `{ten, gia_tri_text, don_vi, huong: "▲"|"▼", thoi_diem, so_voi_truoc}` trong đó `so_voi_truoc` là `"từ 150,0, sau 3 ngày"` khi cùng xét nghiệm đó có kết quả trước, ngược lại `None`. Nhóm theo đúng trường định danh loại xét nghiệm trong mô hình (đọc `models.py`; không đoán).
- `evidence_rows(can_cu: list[CanCu]) -> list[dict]`: `{so, loai_nhan, mo_ta, ban_ghi_id, mo_duoc: bool}`; `mo_duoc` đúng với `du_lieu` có `ban_ghi_id` và với `tinh_toan`; `tai_lieu` ở đợt này `mo_duoc=False`.
- `record_detail(ca, ban_ghi_id) -> dict | None`: tìm bản ghi theo mã trong xét nghiệm, sinh hiệu, dị ứng, chẩn đoán, dòng y lệnh, diễn biến; trả `{loai, tieu_de, dong: list[tuple[str, str]]}` để hộp thoại hiển thị; không thấy thì `None`.
- `unchecked_factors(phat_hien) -> list[str]`: tên các yếu tố (trong 7 yếu tố) **không có phát hiện nào** ở ca này, ví dụ `"4. Tương tác thuốc"`, để giao diện ghi rõ phần chưa được kiểm.
- `suggested_questions(ca) -> list[str]`: 4 câu cố định ở mục 3.7 của plan 1.2; câu về kháng sinh chỉ có khi ca có vi sinh hoặc có thuốc thuộc nhóm kháng sinh (nếu mô hình không có thông tin nhóm thì chỉ dựa vào `ca.vi_sinh`).
- `feedback_status(ca_id, row, feedbacks: list[PhanHoi]) -> PhanHoi | None`: phản hồi **mới nhất** khớp `ca_id`, `ma_luat`, và đúng tập `chi_tiet_y_lenh_id`.

## 5. `app/feedback.py`

Thêm vào `PhanHoi` đúng một trường: `nhom_ly_do: str | None = None`. Không đổi gì khác; dòng JSONL cũ không có trường này vẫn đọc được (có test).

## 6. Nhãn – `app/ui/labels.py`

Chứa mọi bảng nhãn (`TEN_YEU_TO`, `NHAN_KET_LUAN`, `NHAN_DAU_VAO`, `NHAN_LOAI_CAN_CU`, `NHAN_LUONG_DUYET`, thêm `NHAN_MUC_DO`, `NHAN_TRANG_THAI_DONG`, `NHAN_LOAI_DIEU_TRI`, `NHAN_LOAI_HO_SO`, `NHOM_LY_DO` gồm đúng 5 lý do ở mục 3.5 của plan 1.2) và `label_of`. Các giá trị Literal lấy **đúng theo `app/domain/models.py` và `app/rules/types.py`**; test duyệt từng Literal và trượt nếu thiếu nhãn. `view_model.py` import lại và xuất các tên cũ.

## 7. Trạng thái phiên – `app/ui/state.py`

Hàm thuần thao tác trên một `MutableMapping` (truyền `st.session_state` vào), để test bằng `dict`:

`get_selected(state, valid_ids)`, `select_case(state, ca_id)`, `get_chat(state, ca_id) -> list[tuple[str, TraLoi | str]]`, `append_chat(state, ca_id, vai, noi_dung)`, `clear_chat(state, ca_id)`, `get_queue_filter(state)`, `set_queue_filter(state, value)`. Hội thoại tách theo `ca_id`.

## 8. Thành phần – `app/ui/components/`

Mỗi file một hàm `render_*`, nhận dữ liệu đã chuẩn bị, làm đúng phần tương ứng của plan 1.2:

| File | Mục plan 1.2 | Điểm bắt buộc |
| :--- | :-: | :--- |
| `queue.py` | 3.1 | Bộ lọc 3 lựa chọn; sắp theo `queue_rows`; nhãn nút đi qua `plain_label` |
| `case_header.py` | 3.2 | Một hàng; dị ứng 3 trạng thái hiển thị khác hẳn nhau (`st.error` / chữ thường / `st.warning`); 3 con số đếm |
| `summary.py` | 3.3 | 3 cột; số ngày nằm viện; `lab_trends`; 4 chỉ số, mỗi chỉ số có khối mở xem đầu vào, công thức, trích dẫn |
| `findings.py` | 3.4 | Thẻ có viền; 3 cột Thuốc · Yếu tố kiểm tra · Nhận xét; nhãn mức độ có **chữ + biểu tượng**; nhãn nguồn gốc `Luật`; "Căn cứ" mở sẵn với mục nghiêm trọng; khối "Các mục đạt (n)"; khi không có mục cần chú ý thì ghi số luật đã chạy và liệt kê `unchecked_factors` |
| `evidence_dialog.py` | 3.6 | `st.dialog`: với `du_lieu` hiện `record_detail`; với `tinh_toan` hiện đầu vào (tên, giá trị, đơn vị, mã bản ghi, thời điểm), công thức, trích dẫn bài báo; với `tai_lieu` hiện mô tả nguồn và dòng `Nguyên văn đoạn nguồn sẽ có khi nối kho tri thức.` |
| `feedback.py` | 3.5 | "Đồng ý" ghi ngay; "Bác bỏ" / "Cần sửa" bắt chọn `NHOM_LY_DO` rồi mới ghi; sau khi ghi hiện trạng thái và thời điểm; ghi lỗi thì báo tại chỗ |
| `chat.py` | 3.7 | `st.chat_message`, `st.chat_input`; câu gợi ý bấm được; gọi `AskService.ask`; hiển thị theo `trang_thai`; dải chú thích cố định; nút xoá hội thoại |
| `detail_tabs.py` | 3.8 | 4 thẻ: Y lệnh · Xét nghiệm · Vi sinh · Diễn biến |
| `status.py` | 4 | Dải thông báo cố định; dải `Đang chạy không có bước AI…`; chân trang thời gian chạy |

`streamlit_app.py`: `set_page_config(layout="wide", page_title="Hỗ trợ thẩm định y lệnh")`; nạp dịch vụ qua hàm có `@st.cache_resource`; **kết quả `review` của từng ca lưu đệm** (`@st.cache_data` hoặc trạng thái phiên) để bấm phản hồi hay gõ câu hỏi không chạy lại đường chạy; bố cục: thanh bên hàng đợi, vùng chính chia hai cột tỉ lệ 5 : 3 (trái: A, B, C, E; phải: D). Biến môi trường `CDSS_CASE_DIR` vẫn chỉ được đọc ở file này.

## 9. An toàn hiển thị (bắt buộc, có test tĩnh)

- Không có `unsafe_allow_html` ở bất kỳ file nào trong `app/ui/`.
- Không có `st.markdown(` hay `st.write(` nhận biến chứa văn bản từ dữ liệu ca. Để test được: trong `app/ui/components/` **không dùng `st.write` ở đâu cả**, và `st.markdown` chỉ được gọi với **hằng chuỗi** (không f-string, không biến). Văn bản từ ca dùng `st.text`, `st.dataframe`, `st.table`, `st.caption` với chuỗi đã qua `plain_label`, hoặc nhãn widget đã qua `plain_label`.
- `st.chat_message` hiển thị nội dung bằng `st.text`.
- Nội dung thông báo `st.error` / `st.warning` / `st.info` có chứa văn bản từ ca phải đi qua `plain_label`.

## 10. Kiểm thử phải có

- Mọi test cũ trong `tests/ui/` và `tests/test_feedback.py` vẫn qua không sửa kỳ vọng.
- `queue_rows` trên 6 ca demo: hai ca có mục nghiêm trọng (DEMO-02, DEMO-06) đứng đầu; DEMO-05 (cần lưu ý) đứng trước DEMO-03 (thiếu dữ liệu); DEMO-01 và DEMO-04 đứng cuối.
- `header_info` DEMO-02: `gioi_tuoi == "Nữ 75 tuổi"`, `crcl == "16,0 mL/phút"`, `crcl_bat_thuong is True`; DEMO-03: `di_ung_trang_thai == "chua_co_thong_tin"`.
- `lab_trends` DEMO-02: dòng creatinin có `huong == "▲"` và `so_voi_truoc` chứa `"150"`.
- `evidence_rows` trên phát hiện yếu tố 6 của DEMO-02: 3 dòng, thứ tự `Dữ liệu ca`, `Tính toán`, `Tài liệu`.
- `record_detail(ca, "XN-DEMO02-01")` trả đúng xét nghiệm 212; mã lạ trả `None`.
- `unchecked_factors` DEMO-01 có `"4. Tương tác thuốc"`.
- `feedback_status`: hai phản hồi cùng nhận định thì trả cái mới hơn; khác tập dòng y lệnh thì không khớp.
- `state`: hội thoại của hai ca không lẫn nhau; `get_selected` với mã không còn hợp lệ trả mã đầu danh sách.
- `NotReadyAskService().ask(...)` trả `trang_thai == "chua_san_sang"`.
- `labels`: mọi Literal của kết luận, mức độ, loại căn cứ, luồng duyệt, trạng thái dòng, loại điều trị đều có nhãn.
- **Test tĩnh** (`tests/ui/test_static_safety.py`, dùng `ast`): toàn `app/ui/` không có chuỗi `unsafe_allow_html`; trong `app/ui/components/` không có lời gọi `st.write`; mọi lời gọi `st.markdown` có đối số đầu là hằng chuỗi; chỉ `streamlit_app.py` có `os.environ` / `os.getenv`; `view_model.py`, `labels.py`, `services.py`, `state.py` không import `streamlit`.

## 11. Nghiệm thu (người review chạy)

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run streamlit run app/ui/streamlit_app.py --server.headless true
```

rồi mở trình duyệt xem cả 6 ca theo tiêu chí U1–U6 ở mục 8 của plan 1.2. Viết code đúng định dạng `ruff format` (dòng tối đa 100 ký tự, nháy kép).

## 12. Cấm làm

- Không gọi LLM, không gọi mạng, không thêm thư viện.
- Không giả câu trả lời ở khung hỏi thêm; không giả đoạn nguồn.
- Không thêm nút "duyệt đơn", không thêm đăng nhập, biểu đồ, trang phụ, chế độ nhanh.
- Không sửa luật, công thức, mô hình, dữ liệu ca, `pyproject.toml`.
- Không commit, không push.

Xong thì trả lời theo mẫu báo cáo trong `AGENTS.md`, ghi rõ là chưa chạy lệnh nào.
