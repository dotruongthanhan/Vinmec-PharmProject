# T106 – Tool `tra_tuong_tac` và trích dẫn dòng bảng

Người làm: sub Claude Sonnet (medium). Người review: Claude chính.
Đọc trước: `AGENTS.md`, `plan/plan-1.9-agentic-rag-cong-cu-va-phan-quyen.md` mục 5.9, **5.10**, 6.6, 7, 8.

## 1. Bối cảnh

Khung agent LangGraph đã chạy (`app/agent/`), danh mục tool đang rỗng (`app/container.py` → `agentic_asker`, `config/tool_policy.yaml`). Đây là tool đầu tiên. Thêm tool chỉ cần: một lớp trong `app/agent/tools/`, một dòng đăng ký trong `container.agentic_asker`, một dòng trong `config/tool_policy.yaml`. **Không sửa đồ thị** (`graph.py`), không sửa `gateway.py` trừ khi bắt buộc và phải nói rõ lý do trong báo cáo.

## 2. Phạm vi

### 2.1. Tool `tra_tuong_tac` (`app/agent/tools/tra_tuong_tac.py`)

- `ten="tra_tuong_tac"`, `ten_hien_thi="Tra tương tác"`, chế độ `ca` và `chung`.
- Tham số (pydantic, `extra="forbid"`):
  - `loai`: `"thuoc_thuoc" | "thuoc_thuc_an" | "thuoc_benh"`, mặc định `thuoc_thuoc`.
  - `ten_thuoc`: list[str], 1–10 phần tử, mỗi phần tử 1–120 ký tự (`thuoc_thuoc` cần ≥ 2: kiểm trong `chay`, trả `trang_thai="loi"`, `ma_loi="sai_tham_so"` kèm câu giải thích ngắn).
  - `benh`: list[str] tuỳ chọn, ≤ 5 phần tử, mỗi phần tử ≤ 120 ký tự (tên bệnh hoặc ICD-10), chỉ dùng cho `thuoc_benh`.
  - **Không có `ca_id`.**
- `thuoc_thuoc`: gọi lại đúng logic `app.api.lookup.lookup_interactions` (đang phục vụ trang Tra tương tác: phân giải tên tự do → DDInter, phân biệt "không có mã DDInter / thiếu dữ liệu" với "không có tương tác"). Nếu hàm đó ném `HTTPException`, tách phần lõi ra hàm không phụ thuộc FastAPI hoặc bắt và chuyển thành `KetQuaCongCu(trang_thai="loi")`. Không viết lại logic DDInter.
- `thuoc_thuc_an`: dùng dữ liệu thức ăn mà `app/kb/interactions/store.py` đã nạp (`ddinter_thuc_an`). Không viết SQL mới nếu store đã có.
- `thuoc_benh`: dùng bảng luật `thuoc_benh_icd` đã nạp (xem `_rules_for` trong `app/api/lookup.py`, nhóm `thuoc_benh`); khớp theo tên bệnh hoặc mã ICD-10 tiền tố. Không có `benh` mà đang ở chế độ `ca` thì dùng `chan_doan` của `ctx.ca`.
- Nội dung trả (`noi_dung`) là văn bản ngắn, có cấu trúc, tiếng Việt, mỗi dòng bảng một dòng, mở đầu bằng mã căn cứ, ví dụ:
  `[bang:ddinter_cap:<khoa>] amiodarone – warfarin · mức: nặng · hậu quả: … · xử trí: …`
  Thuốc không phân giải được hoặc không có mã DDInter: ghi riêng một dòng "không có dữ liệu DDInter cho …", **không** được ghi "không có tương tác".
- Mỗi dòng bảng sinh một `CanCu(loai="bang", ma="bang:<ten_bang>:<khoa>", nhan=<nhãn nguồn hiển thị>, noi_dung=<chuỗi dòng đó>)`. Khoá phải ổn định, không chứa ký tự xuống dòng, ≤ 120 ký tự.
- `chi_tiet_tien_trinh`: chỉ số đếm, ví dụ "4 hoạt chất, 2 cặp có tương tác". Không chứa tên thuốc hay nội dung câu hỏi.
- Giới hạn: tối đa 20 dòng; vượt thì cắt và ghi "còn N cặp nữa".

### 2.2. Trích dẫn dòng bảng (plan 1.9 mục 5.10)

- `app/agent/tools/base.py`: `CanCu` thêm trường `noi_dung: str | None = None`.
- `app/orchestration/ask.py`: `AskCitationRaw.loai` thêm `"bang"`. `kiem_chung_tra_loi` thêm tham số tuỳ chọn `bang_by_ma: dict[str, CanCu-like] | None = None` (dùng kiểu nhẹ để `app/orchestration` không phụ thuộc `app/agent`; ví dụ `Mapping[str, tuple[str, str]]` = mã → (nhãn, nội dung)). Với `loai="bang"`:
  - `ma` không có trong `bang_by_ma` → `_reject("unknown_table_row:...")`.
  - Số trong nội dung dòng được cộng vào `effective_numbers` (giống cách làm với đoạn nguồn).
  - Ra `AskCitation(loai_ma="tai_lieu", nhan=<nhãn>, ban_ghi_id=None, doan_trich_id=None, trich_nguyen_van=None)`.
- `app/agent/nodes.py` `KiemChung`: dựng `bang_by_ma` từ `state["can_cu"]` loại `bang` rồi truyền vào.
- `CaseAsker` (luồng cũ) không truyền tham số mới; hành vi không đổi.
- `config/prompts/tac_tu.v1.md`: thêm quy tắc trích `loai="bang"` (`ma` chép đúng mã trong ngoặc vuông ở kết quả công cụ, `trich_nguyen_van=null`) và cập nhật dòng lược đồ JSON ở quy tắc 6. Không đổi các quy tắc khác.

### 2.3. Đăng ký và quyền

- `app/container.py`: đăng ký `TraTuongTac()` vào `danh_muc`.
- `config/tool_policy.yaml`: khai báo tool, cho `duoc_si_ls` và `admin`; giữ `mac_dinh: tu_choi`. Đọc `app/agent/tools/policy.py` để viết đúng cú pháp khoá `cong_cu`.

## 3. Tệp được sửa / tạo

Tạo: `app/agent/tools/tra_tuong_tac.py`, `tests/agent/test_tool_tra_tuong_tac.py`.
Sửa: `app/agent/tools/base.py`, `app/agent/tools/__init__.py` (nếu cần export), `app/agent/nodes.py` (chỉ `KiemChung`), `app/orchestration/ask.py` (chỉ `AskCitationRaw` và `kiem_chung_tra_loi`), `app/container.py` (chỉ `agentic_asker`), `config/tool_policy.yaml`, `config/prompts/tac_tu.v1.md`, `app/api/lookup.py` (chỉ khi cần tách lõi khỏi `HTTPException`), test hiện có nếu chúng khẳng định danh mục rỗng.

Cấm: sửa `graph.py`, `web/`, hợp đồng API, dữ liệu `data/`, ghi DB, cài gói, commit, push.

## 4. Bảo mật (bắt buộc có test)

- Lược đồ tham số từ chối trường lạ (`ca_id`, `sql`…) → Gateway trả `sai_tham_so`.
- Không có SQL tự viết bằng f-string; nếu cần SQL thì tham số hoá.
- Vai trò không được khai báo trong chính sách → `khong_co_quyen`.
- Tham số chứa định danh người bệnh của ca (tên trong `nguoi_benh`) → Gateway từ chối `tham_so_co_dinh_danh` (đã có sẵn ở Gateway: viết test xác nhận với tool này).
- Bộ kiểm chứng: câu trả lời trích `bang:...` không có trong lượt → bị chặn; nêu một con số không có trong dòng → bị chặn.

## 5. Nghiệm thu (Claude chính sẽ tự chạy)

```
uv run ruff check app tests
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider tests/agent tests/orchestration tests/api
uv run pytest -q -p no:cacheprovider
```

Test riêng của tool phải có: cặp có tương tác (dùng cặp có thật trong dữ liệu DDInter của kho, ví dụ amiodarone + warfarin; kiểm trước bằng dữ liệu, không đoán); một tên không phân giải được → dòng "không có dữ liệu DDInter", không có chữ "không có tương tác"; `thuoc_thuoc` chỉ 1 tên → `loi`; một test thức ăn; một test thuốc–bệnh. Test chạy được khi không có DB (dùng nguồn tệp như test `tests/api/test_tra_cuu.py` đang làm).

## 6. Báo cáo

Ghi `plan/briefs/T106-bao-cao.md`: tệp đã sửa, quyết định thiết kế, kết quả các lệnh nghiệm thu (bạn được chạy lệnh), điểm còn ngờ.
