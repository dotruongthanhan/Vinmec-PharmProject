# T24-fix-1 – Hỏi đáp trả `khong_co_nguon` cho câu hỏi chính của demo; thêm trường cho danh sách y lệnh

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort xhigh) · **Ngày:** 17/11/2026
**Đọc trước:** `AGENTS.md`; `plan/briefs/T24-hoi-dap-theo-ca.md`; `plan/api-hop-dong-v1.2-hoi-dap.md` (có mục 4 mới); `app/orchestration/ask.py`, `app/verify/`, `app/api/`, `config/prompts/hoi_them.v1.md`.

## 1. Kết quả review (người review đã chạy)

- Toàn kho: 656 test qua (1 test trượt ở `tests/db/` thuộc task T14 đang làm, không phải việc của bạn).
- Gọi thật trên `uvicorn` với LLM thật, ca DEMO-02:
  - `Vì sao cần xem lại liều meropenem ở ca này?` → **`khong_co_nguon`** sau 5,3 giây, `cong_cu_da_goi` có đủ `du_lieu_ca`, `bo_luat`, `truy_xuat`. **Đây là lỗi phải sửa:** ca này có nhận định của luật (CrCl 16,0 mL/phút, mức 10–25 của bảng liều) và đoạn nguồn nhãn meropenem; đây là câu hỏi chính của buổi demo.
  - Câu chèn lệnh kèm hỏi thời tiết → `ngoai_pham_vi` (đúng).
  - `Liều tối đa của vancomycin cho bệnh nhân này là bao nhiêu?` (thuốc không có trong ca) → `ngoai_pham_vi`. Chấp nhận được, nhưng đúng nghĩa hơn là `khong_co_nguon`; xem việc 3.
- `uv run ruff check app tests` còn 5 lỗi, trong đó có `E501` ở `tests/api/test_ask_routes.py:103`.

## 2. Việc 1 – tìm đúng nguyên nhân rồi mới sửa

1. Thêm ghi nhật ký nội bộ (mức `INFO`, không lộ ra API, không ghi câu hỏi chưa che định danh, không ghi khoá): mỗi lần `/ask` kết thúc khác `ok` thì ghi **bước nào loại** và **lý do cụ thể** (ví dụ: mã trích dẫn nào không có trong ngữ cảnh; con số nào không tìm thấy; câu trích nào không phải chuỗi con; LLM trả `pham_vi` gì; số đoạn truy xuất được).
2. Chạy `uvicorn` ở cổng 8011, gọi câu hỏi ở mục 1 ít nhất 3 lần, đọc nhật ký, ghi nguyên nhân thật vào báo cáo. Không đoán.
3. Sửa đúng nguyên nhân. Các hướng thường gặp cần kiểm (chỉ sửa cái thật sự xảy ra):
   - Bước kiểm con số coi dấu trích dẫn `[1]`, `[2]`, số thứ tự, hay số trong mã bản ghi là "con số lạ".
   - So khớp số quá cứng: `16` với `16.0` / `16,0`; `212` với `212.0`; dấu phẩy và dấu chấm thập phân; khoảng `10–25` với `10-25`.
   - Đơn vị và cách viết: `µmol/L` với `umol/L`.
   - Câu trích nguyên văn lệch khoảng trắng, xuống dòng, dấu gạch trong bảng (`10-25 | One-half recommended dose | Every 12 hours`).
   - Gói ngữ cảnh không chứa nhận định của luật hoặc không chứa đoạn nguồn mà job AI nền đã dùng cho ca này.
   - Prompt không yêu cầu rõ dạng mã trích dẫn nên LLM tự đặt mã.
4. **Không nới bất biến:** con số không có trong ngữ cảnh vẫn phải bị loại; trích dẫn mã lạ vẫn phải bị loại; câu trích không khớp vẫn phải bị loại. Chuẩn hoá cách viết số và khoảng trắng là được; bỏ bước kiểm là không được. Mỗi chỗ chuẩn hoá thêm một test cho chiều "vẫn bắt được số bịa".
5. Nếu câu trả lời hợp lệ nhưng chỉ một trích dẫn hỏng: loại riêng trích dẫn đó và câu chứa nó là **không** được (dễ sai nghĩa); cho LLM thử lại đúng 1 lần với thông báo lỗi cụ thể, vẫn hỏng thì `khong_co_nguon`.

**Đích:** câu hỏi ở mục 1 trả `ok` ở ít nhất 4 trong 5 lần gọi thật liên tiếp, có ít nhất một trích dẫn tài liệu (mở được qua `/sources/{doan_trich_id}`) và một trích dẫn dữ liệu ca hoặc tính toán; thời gian dưới 20 giây. Dán cả 5 kết quả vào báo cáo.

## 3. Việc 2 – phân biệt `ngoai_pham_vi` và `khong_co_nguon`

Câu hỏi về thuốc, liều, tương tác, xét nghiệm (đúng lĩnh vực) nhưng dữ liệu ca và kho nguồn không có căn cứ → `khong_co_nguon`. Chỉ trả `ngoai_pham_vi` khi câu hỏi không thuộc lĩnh vực, yêu cầu duyệt hay kê đơn thay, hoặc chứa chỉ thị cho hệ thống. Sửa ở prompt và ở nhánh xử lý; thêm test bằng LLM giả cho hai trường hợp.

## 4. Việc 3 – thêm bốn trường cho `GET /api/cases` (hợp đồng v1.2 mục 4)

`ma_y_lenh`, `thoi_diem_ke`, `nguoi_benh_tom_tat` (chỉ giới và tuổi, không họ tên), `thuoc`. Lấy từ dữ liệu ca sẵn có qua `presenter`; thêm test với 6 ca demo (DEMO-02: `YL-DEMO-02`, `Nữ, 75 tuổi`, một thuốc `Meropenem 1 g`).

## 5. Việc 4 – lint

`uv run ruff check app tests --exclude tests/architecture/.tmp --exclude tests/kb/.tmp` sạch đối với các file thuộc `app/api`, `app/orchestration`, `app/verify`, `tests/api`, `tests/orchestration`, `tests/verify`. Lỗi ở `app/db`, `app/kb`, `tests/db`, `tests/kb` thuộc task khác: không đụng.

## 6. Phạm vi file

`app/orchestration/ask.py`, `app/verify/**`, `app/api/**`, `app/llm/case_context.py`, `config/prompts/hoi_them.v1.md`, `tests/api/**`, `tests/orchestration/**`, `tests/verify/**`.
**Cấm đụng:** `web/`, `app/db/`, `db/`, `app/kb/`, `data/`, `pyproject.toml`, `plan/`.

## 7. Nghiệm thu

```bash
uv run ruff check app/api app/orchestration app/verify tests/api tests/orchestration tests/verify
uv run ruff format --check app/api app/orchestration app/verify tests/api tests/orchestration tests/verify
uv run pytest -q -p no:cacheprovider tests/api tests/orchestration tests/verify tests/llm
```

Rồi 5 lần gọi thật như mục 2, và một lần `GET /api/cases` (dán dòng DEMO-02). Dừng tiến trình `uvicorn` sau khi xong.

## 8. Cấm làm

Không bịa nội dung y khoa. Không in khoá. Không thêm thư viện. Không commit, không push. Trả lời theo mẫu trong `AGENTS.md`.
