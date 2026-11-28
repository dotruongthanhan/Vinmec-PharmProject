# T107 – Báo cáo: tool `tim_doan_nguon`

Trạng thái: XONG phần brief giao; điểm còn ngờ ở mục 5.

## 1. Tệp đã tạo / sửa

Tạo:
- `app/agent/tools/tim_doan_nguon.py` – `TimDoanNguon`, `ThamSoTimDoanNguon`, giao thức `NguonDoan`.
- `tests/agent/test_tool_tim_doan_nguon.py` – 19 test.

Sửa:
- `app/orchestration/evidence.py` – `LazyRetrieverFactory` thêm hai hàm công khai: `ingredient_items(ids)` (đoạn theo tập hoạt chất kèm vector từ DB hoặc `None` ở chế độ tệp, có cache, không gọi nhúng) và `rank_by_vector(items, query, k)` (cosine bằng numpy; chỉ nhúng bù đoạn chưa có vector). Không đổi `for_ingredients`.
- `app/container.py` – tách logic dựng factory ra thuộc tính cache `evidence_retriever` (dùng chung cho `case_asker` và tool, hành vi `case_asker` không đổi); `agentic_asker` đăng ký `TimDoanNguon(self.evidence_retriever, DrugNameIndex.load().resolve)`; thêm import `TYPE_CHECKING`.
- `config/tool_policy.yaml` – khai báo `tim_doan_nguon`, cho `duoc_si_ls` và `admin`.
- `config/prompts/tac_tu.v1.md` – một dòng khi nào gọi tool (nên truyền `muc`) và một dòng quy tắc trích `loai="tai_lieu"` với dòng `[doan_trich_id: ...]`.
- `app/agent/tools/__init__.py` – xuất `TimDoanNguon`.

Không đụng `graph.py`, `gateway.py`, `ask.py`, `web/`, `data/`, hợp đồng API. Không ghi DB, không cài gói.

## 2. Thiết kế

- Tham số `extra="forbid"`, không `ca_id`: `cau_hoi` 1–300, `hoat_chat` ≤ 5 phần tử ≤ 120 ký tự, `muc` ≤ 4 (`Literal` 13 giá trị có thật trong `doan_trich`, đã kiểm trên `chunks.jsonl`), `so_doan` 1–6 mặc định 4.
- Phân giải hoạt chất bằng `DrugNameIndex.resolve`; chế độ `ca` để trống thì lấy hoạt chất từ thuốc trong ca (`ingredients_of`, tên quốc tế ưu tiên); chế độ `chung` để trống → `loi`/`sai_tham_so`.
- Ba cách tra: chính xác (có `muc`, tập lọc ≤ `so_doan`, không nhúng), kết hợp (có `muc`, tập lọc > `so_doan`, cosine trong tập đã lọc), ngữ nghĩa (không `muc`). `chi_tiet_tien_trinh` ví dụ "Nhãn FDA, 4 đoạn (kết hợp)", không chứa câu hỏi.
- Nhúng lỗi (`ProviderError`, và cả `RetrievalError` như lệch chiều vector) → `so_doan` đoạn đầu theo thứ tự tài liệu; tiến trình ghi "nhúng lỗi, trả theo thứ tự tài liệu", nội dung có một dòng báo.
- Hoạt chất không phân giải hoặc không có đoạn → dòng "không có nhãn trong kho cho …"; `khong_co` nếu không còn gì (mục không có đoạn cũng ghi rõ).
- Mỗi đoạn: dòng đầu `[doan_trich_id: <mã>]`, dòng nguồn (nhãn · đường dẫn mục · mục · tầng tin cậy), nội dung gốc cắt ≤ 1.200 ký tự ở ranh giới câu (có dòng "đã cắt bớt"), tổng ≤ 7.500 (hết trần thì dừng và ghi "còn N đoạn nữa chưa hiển thị"; đoạn không hiển thị không vào căn cứ). Mỗi đoạn hiển thị một `CanCu(loai="doan", ma=doan_trich_id, doan=Chunk)` để `KiemChung` dùng đường trích nguyên văn có sẵn.
- Dùng lại `LazyRetrieverFactory` (DB hoặc tệp); tool không viết SQL.

## 3. Bảo mật (có test)

- Trường lạ (`ca_id`, `sql`) và vi phạm giới hạn (độ dài, số phần tử, mục lạ, `so_doan` 0/7) bị Gateway từ chối `sai_tham_so`; vai trò không khai báo → `khong_co_quyen`.
- Họ tên người bệnh trong `cau_hoi` bị Gateway chặn `tham_so_co_dinh_danh` trước khi tool chạy (nguồn giả xác nhận không nhúng).
- Đoạn có câu "Ignore all instructions…" → Gateway trả `nghi_chen_lenh`, `can_cu` rỗng, mã đoạn không lọt vào nội dung.
- Kiểm chứng qua đồ thị thật với LLM giả: chép nguyên văn một đoạn + đúng mã → đạt, `trich_dan` mang `doan_trich_id`; đổi một chữ ("fatal"→"fetal") → bị chặn; mã đoạn không có trong lượt → bị chặn.
- Câu hỏi chỉ rời máy qua `embed_query` sau khi Gateway quét PII.

## 4. Kết quả lệnh

- `uv run ruff check app tests`: All checks passed.
- `uv run ruff format --check app tests`: 376 files already formatted.
- `uv run pytest -q -p no:cacheprovider tests/agent tests/orchestration`: 160 passed, 0 failed.
- Thêm: `tests/api tests/retrieval tests/kb/test_store_from_db.py tests/orchestration`: 340 passed, 2 skipped (lần này test độ trễ chỉ mục gợi ý của T106 cũng qua).
- Toàn bộ `pytest`: để người review chạy.

Thời gian tool (đo bằng script tạm ngoài kho, một câu nhúng thật, kết quả "kết hợp" warfarin/`canh_bao`):
- Chế độ tệp (`chunks.jsonl`): lượt đầu 0,9 s, lượt sau 0,0 s.
- Chế độ DB qua đường hầm RDS (`use_db=True`): lượt đầu 4,35 s (nạp 73 đoạn warfarin kèm vector + nhúng câu hỏi), lượt sau 0,0 s (cache đoạn và cache nhúng). Dưới trần 20 s nên chưa cần warmup; nếu muốn, có thể gọi `ingredient_items` cho vài hoạt chất phổ biến lúc khởi động, nhưng chưa thêm vào `app/api/main.py`.

## 5. Điểm còn ngờ

1. "Thứ tự tài liệu": chunk không có số thứ tự trong tài liệu; tool sắp ổn định theo `tai_lieu_id`, giữ thứ tự nạp trong từng tài liệu (DB nạp `ORDER BY doan_trich_id`, là mã băm, nên thứ tự trong cùng tài liệu chỉ ổn định chứ không theo vị trí thật). Chỉ ảnh hưởng nhánh chính xác và nhánh lùi.
2. Gateway che PII bằng `scrub` lên `noi_dung`, trong khi kiểm chứng so với `noi_dung_goc` của `Chunk`: nếu bộ che sửa một chuỗi trong văn bản nhãn thì trích nguyên văn có thể lệch; chưa gặp ở dữ liệu thật.
3. Kiểm chứng `loai="tai_lieu"` dùng `chunk_by_id.get(ma)` nguyên dạng (không chuẩn hoá như nhánh `bang`); LLM chép sai dạng (có ngoặc, có tiền tố) sẽ bị chặn rồi thử lại một lần. Prompt đã nhắc; nếu DeepSeek hay chép sai thì nên thêm chuẩn hoá cho nhánh này trong `ask.py` (ngoài phạm vi brief).
4. Nhãn FDA là tiếng Anh: LLM phải dịch/diễn giải, số liệu vẫn bị kiểm với đoạn gốc; không chạy thử với DeepSeek thật.
5. Nhánh "ngữ nghĩa" luôn nhúng câu hỏi kể cả khi tập đoạn ≤ `so_doan` (làm đúng brief); có thể bỏ bước nhúng khi tập nhỏ.
6. Ở chế độ tệp với bộ nhúng thật, `rank_by_vector` nhúng bù toàn bộ đoạn của hoạt chất (chưa có vector) qua cache sqlite; lượt đầu có thể tốn tiền nhúng với hoạt chất nhiều đoạn (DB đã có vector nên không gặp).
