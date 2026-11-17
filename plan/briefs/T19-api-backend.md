# T19 – API backend (FastAPI) cho bản web

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort high) · **Ngày:** 16/11/2026
**Đọc trước (bắt buộc):** `AGENTS.md`; `plan/api-hop-dong-v1.md` (**nguồn sự thật**, làm đúng từng tên trường và kiểu); **chỉ đọc**: `app/ui/view_model.py`, `app/ui/labels.py`, `app/ui/services.py`, `app/feedback.py`, `app/pipeline.py`, `app/container.py`, `app/config/settings.py`, `app/domain/models.py`.

**Nhiều task khác đang chạy song song.** Bạn chỉ tạo và sửa các file ở mục 2. Không sửa `pyproject.toml` (FastAPI, uvicorn, httpx đã cài sẵn), `app/ui/`, `app/container.py`, `app/config/`, `app/core/`, `app/providers/`, `app/rules/`, `app/kb/`, `app/retrieval/`, `app/llm/`, `app/verify/`, `web/`, `data/`, `config/`. Không đọc `.env`.

**Thư mục tạm:** không tạo thư mục tạm trong kho. Chạy `pytest` với `--basetemp` trỏ ra thư mục tạm của hệ điều hành và `-p no:cacheprovider`. Thư mục `tests/architecture/.tmp` đang bị khoá quyền: không đụng vào; chạy `ruff` với `--exclude tests/architecture/.tmp`.

## 1. Mục tiêu

Mở các điểm cuối ở mục 3 của hợp đồng để bản web React dùng. Dữ liệu vẫn từ `app.pipeline.run_case` (chưa có LLM, chưa có kho nguồn). Giao diện Streamlit giữ nguyên, không sửa.

## 2. Phạm vi file

```text
app/api/__init__.py
app/api/main.py          # create_app(), app = create_app(); gắn router, xử lý lỗi, phục vụ web/dist nếu có
app/api/schemas.py       # mô hình pydantic khớp từng interface trong hợp đồng (tên lớp giống tên interface)
app/api/presenter.py     # hàm thuần: CaBenh + KetQuaThamDinh + phản hồi → ChiTietCa, DongHangDoi, BanGhi
app/api/service.py       # CaseService: nạp ca, lưu đệm kết quả, ghi phản hồi, hỏi thêm
app/api/routes.py        # các điểm cuối
tests/api/__init__.py
tests/api/test_presenter.py
tests/api/test_routes.py
tests/api/test_contract.py
```

## 3. Yêu cầu

1. **Dùng lại, không viết lại.** `presenter.py` gọi các hàm sẵn có của `app/ui/view_model.py` và nhãn ở `app/ui/labels.py` (`queue_rows`, `header_info`, `count_by_level`, `lab_trends`, `labs_without_range`, `length_of_stay_days`, `finding_rows`, `split_findings`, `sort_attention_rows`, `evidence_rows`, `record_detail`, `unchecked_factors`, `suggested_questions`, `feedback_status`, `order_table_rows`, `lab_rows`, `metric_text`, `format_dt`, `format_number`, `format_ref_range`, `allergy_text`, `label_of`, `prescribed_active_ingredient_ids`, …) rồi **đổi tên khoá cho khớp hợp đồng**. Thiếu hàm nào thì viết trong `presenter.py`, không sửa `app/ui/`. Câu chữ hiển thị (ví dụ `bat_thuong_ghi_chu`, `nam_vien_text`) phải giống hệt câu đang hiện ở giao diện Streamlit (đọc `app/ui/components/summary.py` để lấy đúng câu).
2. **`CaseService`** nhận `case_dir: Path`, `renal_rules_path: Path`, `feedback_path: Path` qua hàm khởi tạo. `create_app(service: CaseService | None = None)`: không truyền thì dựng từ `load_settings()` (`settings.app.case_dir`, `data/kb/quy_tac_lieu_than.json`, `data/runtime/phan_hoi.jsonl`), đường dẫn tính từ gốc kho. Kết quả `run_case` của từng ca được lưu đệm trong bộ nhớ; ghi phản hồi **không** chạy lại đường chạy.
3. **`che_do`** hôm nay: `co_llm=False`, `truy_xuat="chua_co"`, `hoi_them=False`, `thong_bao=["Đang chạy không có bước AI: bảng nhận định do bộ luật sinh ra"]`.
4. **`nhan_dinh_id`** đúng công thức trong hợp đồng. `so_luat_da_chay` = số luật đang đăng ký (5).
5. **`can_cu`:** `mo_duoc` theo `evidence_rows`; với `tinh_toan` điền `cong_thuc` (khoá công thức để web tìm `ChiSo`; hôm nay căn cứ tính toán của luật thận ứng với `cockcroft_gault`; không xác định được thì `null` và `mo_duoc=false`); với `tai_lieu` điền `ghi_chu` đúng câu trong hợp đồng.
6. **Phản hồi:** kiểm theo hợp đồng (404, 422), ghi bằng `app.feedback.save_feedback` (trường `nhom_ly_do` đã có), trả `PhanHoiDaGhi`. `da_phan_hoi_het` và `NhanDinh.phan_hoi` lấy phản hồi **mới nhất** qua `feedback_status`.
7. **Hỏi thêm:** dùng `NotReadyAskService` sẵn có, trả `TraLoi` theo hợp đồng.
8. **Lỗi:** mọi lỗi trả đúng dạng `{"loi": {"ma", "thong_bao"}}`, kể cả 404 và 422 mặc định của FastAPI (ghi đè bộ xử lý). Lỗi không lường trước → 500 `loi_he_thong`, **không** lộ dấu vết ngăn xếp hay nội dung ca trong thân trả về.
9. **An toàn:** không có điểm cuối nào ghi ngoài `feedback`. `ca_id` và `ban_ghi_id` trên đường dẫn chỉ dùng để tra trong danh sách đã nạp, **không** ghép vào đường dẫn tệp. CORS chỉ cho `http://localhost:5173` và `http://127.0.0.1:5173`.
10. **Phục vụ web:** nếu `web/dist/index.html` tồn tại thì gắn `web/dist` ở `/` (sau các router `/api`), đường dẫn không khớp tệp nào và không bắt đầu bằng `/api` thì trả `index.html`. Không tồn tại thì bỏ qua, `/api` vẫn chạy.

## 4. Kiểm thử phải có (`fastapi.testclient.TestClient`, `feedback_path` dùng `tmp_path`)

- `GET /api/health` → 200, `ok is True`.
- `GET /api/cases` → 6 ca; hai ca đầu là DEMO-02 và DEMO-06 (thứ tự giữa hai ca theo thời điểm kê); DEMO-05 đứng trước DEMO-03; `loi_nap == []`.
- `GET /api/cases/DEMO-02`: `dinh_danh.gioi_tuoi == "Nữ 75 tuổi"`, `dinh_danh.crcl == "16,0 mL/phút"`, `dinh_danh.dem.nghiem_trong == 1`; `chi_so` có đúng 4 mục, mục đầu `cong_thuc == "cockcroft_gault"` và `gia_tri_text == "16,0"`, mục cuối `gia_tri_text == "1,47"`; `nhan_dinh.can_chu_y` có 1 mục với `yeu_to` bắt đầu `"6."`, `muc_do_ma == "nghiem_trong"`, `nguon_goc_ma == "luat"`, 3 căn cứ theo thứ tự `du_lieu`, `tinh_toan`, `tai_lieu`; `tom_tat.bat_thuong[0]` có `huong == "▲"` và `so_voi_truoc` chứa `"150"`; `tom_tat.nam_vien_text` bắt đầu bằng `"3 ngày"`; `nhan_dinh.yeu_to_chua_kiem` có `"4. Tương tác thuốc"`.
- `GET /api/cases/DEMO-03`: `dinh_danh.di_ung_ma == "chua_co_thong_tin"`; có nhận định `ket_luan_ma == "khong_du_du_lieu"` với `thong_tin_con_thieu` khác rỗng.
- `GET /api/cases/DEMO-04`: `chi_tiet.vi_sinh` khác rỗng; có ít nhất một dòng kháng sinh đồ `dang_ke is True`.
- `GET /api/cases/KHONG-CO` → 404, thân có `loi.ma == "khong_tim_thay"`.
- `GET /api/cases/DEMO-02/records/XN-DEMO02-01` → 200, có dòng chứa `212`; mã lạ → 404; mã bản ghi của ca khác → 404.
- `POST feedback` `dong_y` → 200; sau đó `GET` ca đó có `phan_hoi.phan_hoi == "dong_y"` và `GET /api/cases` có `da_phan_hoi_het is True` cho ca đó; `bac_bo` thiếu `nhom_ly_do` → 422; `nhom_ly_do` lạ → 422; `nhan_dinh_id` lạ → 404; hai phản hồi liên tiếp thì trả cái mới hơn; file JSONL có đúng số dòng đã ghi và giữ dấu tiếng Việt.
- `POST ask` → 200, `trang_thai == "chua_san_sang"`.
- Ghi phản hồi không gọi lại `run_case` (dùng `monkeypatch` đếm số lần gọi).
- **Hợp đồng** (`test_contract.py`): với cả 6 ca, thân trả về của `GET /api/cases/{id}` kiểm được bằng `ChiTietCa.model_validate` với `extra="forbid"`; tập tên trường của từng lớp trong `schemas.py` bằng đúng tập tên trong hợp đồng (đọc `plan/api-hop-dong-v1.md`, tách khối ```ts``` bằng biểu thức chính quy; lớp nào tách không được thì liệt kê trường bằng tay trong test).
- Không còn mã nội bộ lộ ra ở các trường hiển thị: với cả 6 ca, không chuỗi nào trong các trường `*_text`, `*_nhan`, `nhan`, `yeu_to`, `huy_hieu` chứa dấu gạch dưới `_`.
- Thân lỗi 500 (ép `service` ném lỗi bằng `monkeypatch`) không chứa `Traceback`.

## 5. Nghiệm thu

```bash
uv run ruff check . --exclude tests/architecture/.tmp
uv run ruff format --check app/api tests/api
uv run pytest -q tests/api -p no:cacheprovider --basetemp <thư mục tạm ngoài kho>
```

Chỉ định dạng các file của task này (task khác đang ghi file). Toàn bộ test cũ không được vỡ.

## 6. Cấm làm

- Không thêm thư viện. Không gọi mạng, LLM. Không đọc `.env`.
- Không thêm điểm cuối ngoài hợp đồng. Không đổi tên trường của hợp đồng; thấy hợp đồng thiếu hoặc mâu thuẫn thì làm theo cách hợp lý nhất và **ghi rõ trong báo cáo**.
- Không sửa giao diện Streamlit, luật, công thức, dữ liệu.
- Không commit, không push.
