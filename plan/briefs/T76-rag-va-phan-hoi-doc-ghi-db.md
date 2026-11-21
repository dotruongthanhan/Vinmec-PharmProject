# T76 – RAG dùng vector đã lưu trên DB; phản hồi và lịch sử hỏi đáp ghi vào DB

Agent: **agy Gemini 4 Hydrogen xhigh**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Chạy **sau T75** (cùng đụng `app/orchestration/evidence.py`, `app/container.py`); đọc `plan/reports/T75.md` trước.

## Bối cảnh (Claude kiểm 19/11 tối)

Mục tiêu: deploy / máy khác chỉ cần `DATABASE_URL`, không cần tệp trong `data/` bị `.gitignore` loại. Sau T75 còn hai chỗ phụ thuộc máy:

1. **RAG không dùng vector trên DB.** `tri_thuc.doan_trich.embedding` (halfvec 2048, gemini-embedding-2) đã nạp đủ, nhưng không có provider `pgvector`; `LazyRetrieverFactory.for_ingredients` (`app/orchestration/evidence.py`) lọc đoạn theo hoạt chất rồi `index_corpus` **nhúng lại** qua `CachedEmbedder` có bộ đệm `data/cache/embeddings.sqlite` (bị gitignore). Máy khác: bộ đệm rỗng → gọi API nhúng cho mọi đoạn ở mỗi tổ hợp hoạt chất (chậm, tốn quota, lỗi khi không có khoá).
2. **Phản hồi dược sĩ và lịch sử hỏi đáp ghi tệp cục bộ**: `data/runtime/phan_hoi.jsonl` (`app/feedback.py`, `app/api/service.py`), `data/runtime/hoi_thoai.jsonl` (`service.py` `_save_chat_log`, `list_conversations`, `clear_conversation`). Deploy nhiều máy / khởi động lại container → mất hoặc không thấy của nhau. Nhật ký truy cập (`app/api/access_log.py`) để nguyên tệp (log vận hành).

## Yêu cầu

### 0. Việc còn lại của T75 (Claude review 19/11)

- `tests/kb/test_store_from_db.py:25` import thừa `SourceError` (F401); `ruff format` báo 2 tệp lệch – định dạng lại (chạy được bằng mắt: chỉ khoảng trắng).
- `tests/db/test_mapping.py::test_mapping_matches_schema_and_rls`: loại 9 bảng `tri_thuc.ddinter_*`, `tri_thuc.tra_cuu_*` (danh sách `app/db/chi_muc.py::INDEX_TABLES`) khỏi phép so với `TABLES`, vẫn kiểm chúng có RLS.
- `tests/db/test_schema_rds_compat.py::test_schema_revokes_supabase_roles_only_conditionally`: 3 khối `DO` (không còn 2); giữ ý kiểm mọi `REVOKE … anon/authenticated` nằm trong khối điều kiện.

### 0b. DDInter từ DB: tra theo cặp, không nạp cả bảng (lỗi Claude đo trên RDS)

Đã nạp RDS, ẩn tệp sqlite và chạy 66 ca: resolver từ DB chạy đúng (mọi nhận định D1–D7 khác khớp), nhưng **DDInter không nạp được**: `InteractionStore.from_db` đọc toàn bộ 291.876 dòng `ddinter_cap` → `QueryCanceled` vì `statement_timeout=8000` của `read_pool`; bỏ giới hạn thì mất **144 giây** – không chấp nhận lúc khởi động. Hậu quả: mất 74 nhận định yếu tố 4.

Sửa: `InteractionStore` nguồn DB nạp sẵn `ddinter_thuoc` (1.971) và `ddinter_thuc_an` (805) như hiện nay, còn `pair(a, b)` **truy vấn theo khoá chính** `WHERE ddinter_id_a = %s AND ddinter_id_b = %s` (sau khi `sorted`), có bộ nhớ đệm trong tiến trình (kể cả kết quả "không có"), mỗi lần lấy kết nối từ `read_pool` (không giữ kết nối). Tốt hơn: thêm `pairs(ids) -> dict` một truy vấn cho mọi cặp của một ca (`WHERE (a,b) IN (...)`) và cho `app/rules/interaction.py` dùng nếu đổi nhỏ; nếu đổi luật thì chỉ đổi cách gọi, không đổi logic. Đường tệp (`from_path`) giữ nguyên. Test: nguồn DB giả đếm số truy vấn; `pair` cho cùng kết quả với `from_path`.

### 1. RAG lấy vector có sẵn

- Khi nguồn kho là DB (`KB_SOURCE` của T75 chọn DB) **hoặc** khi có DB: `for_ingredients(ids)` truy vấn `tri_thuc.doan_trich` các đoạn có `hoat_chat_ids ?| ids` **kèm `embedding`**, đưa thẳng vector vào `InMemoryVectorStore` (thêm hàm/tham số nạp vector có sẵn, không gọi embedder cho đoạn); BM25 dựng từ cùng tập đoạn như cũ. Chỉ **câu hỏi** được nhúng qua embedder.
- Đoạn có `embedding IS NULL` → nhúng như cũ (đường lui) và log một cảnh báo đếm số đoạn.
- Kiểm cùng mô hình: so `settings.embedding` (mô hình, số chiều 2048) với dữ liệu; lệch số chiều → báo lỗi rõ, không trộn vector.
- Đường tệp cũ (`chunks.jsonl` + bộ đệm) giữ nguyên khi nguồn là tệp.
- (Không bắt buộc) truy vấn trực tiếp `ORDER BY embedding <=> query` trên DB: **không làm** đợt này, giữ kết quả xếp hạng giống bản hiện tại.

### 2. Phản hồi và hỏi đáp vào DB

- Lược đồ `db/schema.sql`: `nghiep_vu.phan_hoi` thêm cột `nguoi_dung_id text` (sở hữu theo plan 1.5) nếu `service.py` đang lưu trường này trong jsonl; thêm `ALTER TABLE … ADD COLUMN IF NOT EXISTS`. Bảng mới `nghiep_vu.hoi_thoai` theo đúng các trường mà `_save_chat_log` đang ghi (đọc code để lấy danh sách; có `ca_id`, người dùng, thời điểm, vai trò, nội dung, nguồn…), khoá chính `id bigserial`, chỉ mục `(nguoi_dung_id, ca_id, thoi_diem)`; RLS + REVOKE theo mẫu khối điều kiện vai trò.
- Một lớp lưu trữ có hai cài đặt (tệp / DB) cho phản hồi và hỏi đáp; chọn DB khi `CASE_SOURCE=db` (cùng kết nối/pool mà repository ca bệnh dùng), ngược lại tệp như cũ. Giữ nguyên hợp đồng API và kiểm sở hữu (`_owns_conversation`). `clear_conversation` trên DB là `DELETE` theo người dùng + ca.
- Không làm `lan_tham_dinh` / `nhan_dinh` đợt này.

### 3. Test

- Retriever: với nguồn giả trả đoạn kèm vector, embedder giả đếm lần gọi → chỉ gọi cho câu hỏi; đoạn thiếu vector thì gọi cho đoạn đó.
- Lưu trữ phản hồi / hỏi đáp: cài đặt DB với kết nối giả (hoặc fixture PostgreSQL có sẵn, bỏ qua khi không có `DATABASE_URL`); các test API hiện có vẫn qua với cài đặt tệp.

## Phạm vi

Sửa: `app/kb/interactions/store.py`, `app/rules/interaction.py` (chỉ cách gọi kho, mục 0b), các test ở mục 0, `app/orchestration/evidence.py`, `app/providers/memory_store.py` (nạp vector có sẵn), `app/retrieval/corpus.py`, `app/feedback.py`, `app/api/service.py`, `app/container.py`, `db/schema.sql`; tạo module lưu trữ mới nếu cần (`app/storage/`), test, `plan/reports/T76.md`. Cấm: `data/`, `web/`, `app/rules/`.

## Nghiệm thu (Claude chạy)

`ruff check`, `ruff format --check`, `pytest` toàn kho 0 trượt. Trên RDS, với bộ đệm nhúng đổi tên tạm: hỏi một câu trong ca → log chỉ một lần gọi nhúng (câu hỏi), có nguồn trích; gửi phản hồi và hỏi đáp → có dòng trong `nghiep_vu.phan_hoi`, `nghiep_vu.hoi_thoai`; khởi động lại backend vẫn thấy lịch sử.
