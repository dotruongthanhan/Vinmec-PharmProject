# T107 – Tool `tim_doan_nguon` (chính xác · ngữ nghĩa · kết hợp)

Người làm: sub Claude Sonnet (medium). Người review: Claude chính. Làm **sau khi T106 đạt** (cùng sửa `container.py`, `tool_policy.yaml`).
Đọc trước: `AGENTS.md`, `plan/plan-1.9-agentic-rag-cong-cu-va-phan-quyen.md` mục 4.2, 4.3, 5.2, **5.10**, Phụ lục A; `plan/briefs/T106-bao-cao.md` (mẫu tool đã đạt).

## 1. Bối cảnh

Khung agent hiện **không có RAG**: luồng cũ `CaseAsker` tự gọi `EvidenceCollector`, còn đồ thị agent chỉ có những gì tool trả. Đoạn nguồn nằm ở `tri_thuc.doan_trich` (3.730 đoạn nhãn openFDA tiếng Anh, 50 tài liệu, nhúng `gemini-embedding-2` 2048 chiều; cột lọc `hoat_chat_ids`, `muc`). Hạ tầng đã có: `app/orchestration/evidence.py` `LazyRetrieverFactory.for_ingredients()` nạp đoạn theo tập hoạt chất (kèm vector từ DB, hoặc từ tệp `data/kb_curated/chunks.jsonl`) vào `InMemoryVectorStore`; bộ nhúng có cache (`data/cache/embeddings.sqlite`). Số đo T64: **chỉ vector trong bộ lọc hoạt chất tốt hơn đường lai BM25 + rerank**.

## 2. Thiết kế (người dùng yêu cầu: tra chính xác bằng Postgres khi dữ liệu có cấu trúc, vector khi cần ngữ nghĩa, và kết hợp)

Tham số (`extra="forbid"`, không có `ca_id`):
- `cau_hoi`: str 1–300 ký tự (câu tìm, đã che PII từ trước).
- `hoat_chat`: list[str] 0–5, mỗi phần tử ≤ 120 ký tự, tên tự do hoặc mã; phân giải bằng bộ phân giải tên đang dùng cho `CaseAsker` (`resolve_name` / `names.resolve` trong `app/container.py`). Chế độ `ca` mà để trống → dùng hoạt chất của các thuốc trong ca (`ctx.ca`). Chế độ `chung` mà để trống → `trang_thai="loi"`, `ma_loi="sai_tham_so"`, nói cần nêu thuốc. (Tìm toàn kho không lọc hoạt chất: hoãn.)
- `muc`: list[str] 0–4, giá trị trong tập mục có thật của `doan_trich` (`lieu`, `lieu_than`, `lieu_gan`, `chong_chi_dinh`, `canh_bao`, `tuong_tac`, `tac_dung_phu`, `thai_ky_cho_bu`, `nhi_cao_tuoi`, `qua_lieu`, `chi_dinh`, `duoc_ly`, `khac`): khai báo `Literal` để LLM thấy danh sách.
- `so_doan`: int 1–6, mặc định 4.

Ba cách tra, chọn tự động, ghi cách đã dùng vào `chi_tiet_tien_trinh`:
1. **Chính xác** – có `hoat_chat` và `muc`, tập đoạn sau lọc ≤ `so_doan`: trả hết theo thứ tự tài liệu, **không gọi dịch vụ nhúng**.
2. **Kết hợp** – có bộ lọc nhưng tập lọc > `so_doan`: xếp hạng bằng cosine vector câu hỏi trong tập đã lọc (hoạt chất, và mục nếu có).
3. **Ngữ nghĩa** – có hoạt chất, không có mục: vector trong tập đoạn của các hoạt chất đó.
- Không dùng BM25, không rerank. Dùng lại `LazyRetrieverFactory` để nạp đoạn và vector (hoặc thêm vào nó một hàm công khai nhỏ trả danh sách đoạn + vector cho tập hoạt chất); không tự viết lại đường nạp DB. Nếu phải viết SQL thì tham số hoá, không f-string.
- Nhúng lỗi (`ProviderError`) → lùi về cách 1 với `so_doan` đoạn đầu theo thứ tự tài liệu, ghi cảnh báo vào `chi_tiet_tien_trinh` ("nhúng lỗi, trả theo thứ tự tài liệu").
- Hoạt chất không có đoạn nào → dòng "không có nhãn trong kho cho …", `trang_thai="khong_co"` nếu không còn gì.

Kết quả:
- Mỗi đoạn: mã `doan_trich_id`, nhãn nguồn (tên tài liệu, mục), tầng tin cậy, rồi `noi_dung_goc` (cắt ≤ 1.200 ký tự, cắt ở ranh giới câu nếu được; LLM chỉ được trích phần hiển thị). Tổng nội dung ≤ 7.500 ký tự (Gateway cắt ở 8.000).
- Mỗi đoạn một `CanCu(loai="doan", ma=doan_trich_id, nhan=..., doan=<Chunk>)` để `KiemChung` dùng đường kiểm trích nguyên văn hiện có.
- `chi_tiet_tien_trinh`: ví dụ "Nhãn FDA, 4 đoạn (kết hợp)". Không chứa câu hỏi.
- `thoi_gian_toi_da`: 20 s.

Prompt `config/prompts/tac_tu.v1.md`: thêm một câu hướng dẫn khi nào gọi tool này (câu hỏi cần trích nhãn thuốc: liều, chống chỉ định, cảnh báo…) và nhắc ưu tiên truyền `muc` khi rõ mục. Không đổi quy tắc khác.

## 3. Tệp

Tạo: `app/agent/tools/tim_doan_nguon.py`, `tests/agent/test_tool_tim_doan_nguon.py`.
Sửa: `app/container.py` (đăng ký; truyền factory/resolver qua hàm dựng, không gọi global), `config/tool_policy.yaml`, `config/prompts/tac_tu.v1.md`, `app/orchestration/evidence.py` (chỉ thêm hàm công khai nếu cần), `app/agent/tools/__init__.py`.
Cấm: `graph.py`, `gateway.py`, `web/`, `data/`, hợp đồng API, ghi DB, cài gói, commit, push, chạy nhúng hàng loạt.

## 4. Bảo mật (có test)

- Tham số lạ bị từ chối; không `ca_id`.
- Câu hỏi đi ra dịch vụ nhúng ngoài: chỉ là `cau_hoi` đã qua Gateway quét PII; test xác nhận tham số có họ tên người bệnh của ca bị Gateway chặn trước khi tool chạy (không gọi embedder).
- Đoạn nguồn có câu kiểu chỉ thị ("ignore previous instructions…") → Gateway đã chặn (`nghi_chen_lenh`); viết một test với đoạn giả xác nhận.

## 5. Nghiệm thu (Claude chính tự chạy)

```
uv run ruff check app tests
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider tests/agent tests/orchestration
uv run pytest -q -p no:cacheprovider
```

Test bằng embedder giả (`HashEmbedder` hoặc fake), không gọi mạng: (a) chính xác không gọi `embed_query`; (b) kết hợp gọi đúng 1 lần, trả ≤ `so_doan`; (c) nhúng lỗi lùi về thứ tự tài liệu; (d) chế độ chung không có hoạt chất → lỗi tham số; (e) trích nguyên văn một đoạn trả về qua `kiem_chung_tra_loi` đạt, trích sai một chữ bị chặn.

## 6. Báo cáo

`plan/briefs/T107-bao-cao.md`: tệp sửa, thiết kế, kết quả lệnh, điểm ngờ.

## 7. Bài học từ T106 (đọc trước khi viết)

- Gateway đã che PII, bỏ ký hiệu khối, quét chèn lệnh và cắt 8.000 ký tự: tool không làm lại các bước này.
- LLM thật (DeepSeek) hay chép mã căn cứ sai dạng. Đoạn nguồn trích bằng `loai="tai_lieu"` với `ma=<doan_trich_id>`: trong nội dung kết quả, ghi mã ở dạng dễ chép (ví dụ dòng đầu `[doan_trich_id: xxx]`) và kiểm bằng LLM giả rằng chép đúng mã đó thì `kiem_chung_tra_loi` đạt.
- Lần đầu nạp đoạn từ RDS chậm (qua đường hầm); đo thời gian tool ở lượt đầu và lượt sau, ghi vào báo cáo. Nếu lượt đầu > 20 s thì nêu cách nạp sẵn (warmup) nhưng **không** tự thêm vào `app/api/main.py` khi chưa hỏi.
