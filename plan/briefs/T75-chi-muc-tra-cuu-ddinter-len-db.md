# T75 – Đưa chỉ mục tra cứu thuốc, DDInter và kho đoạn nguồn lên PostgreSQL; app đọc từ DB

Agent: **agy Gemini 4 Hydrogen xhigh**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Claude tự chạy `ruff`, `pytest`, nạp dữ liệu lên RDS.

## Bối cảnh

Deploy và máy thành viên khác không có các tệp bị `.gitignore` loại, nên thẩm định 7 yếu tố thiếu dữ liệu (resolver `None` → luật D3–D7 cần resolver không chạy; tương tác yếu tố 4 không chạy; hỏi đáp không có nguồn). App hiện đọc ba tệp cục bộ:

| Tệp | Lớp nạp | Dùng cho |
|:--|:--|:--|
| `data/kb_curated/tra_cuu/tra_cuu.sqlite` (11 MB) | `DrugResolver.from_index` (`app/kb/resolver/resolver.py`) | phân giải tên thuốc → hoạt chất, mọi luật cần resolver |
| `data/kb_curated/tuong_tac/ddinter.sqlite` (133 MB; `cap` 291.876, `thuoc` 1.971, `thuc_an` 805) | `InteractionStore.from_path` (`app/kb/interactions/store.py`) | yếu tố 4, thuốc–bệnh DDInter |
| `data/kb_curated/chunks.jsonl` (3.730 đoạn) | `load_corpus` (`app/retrieval/corpus.py`), `LazyRetrieverFactory` (`app/orchestration/evidence.py`), `container.case_asker` | RAG / hỏi đáp |

Kho đoạn đã có trên DB ở `tri_thuc.doan_trich` (cột trùng tên trường `Chunk`, kèm `embedding`). Hai sqlite chưa có trên DB. Bảng `tri_thuc.tuong_tac_sang_loc` cũ (từ CSV DDInter) **không đủ** trường cho `PairRecord` – để nguyên, không dùng.

Đọc trước: `AGENTS.md`, `app/container.py`, `app/config/settings.py` (khối `app`: `tra_cuu`, `tuong_tac`, `case_source`), `app/db/engine.py`, `app/db/cli.py`, `app/db/sources.py`, `app/db/mapping.py`, `db/schema.sql`, `app/kb/interactions/build.py`, `app/kb/resolver/build.py` (lược đồ sqlite), cách app hiện mở kết nối PostgreSQL khi `CASE_SOURCE=db` (repository ca bệnh) để dùng lại.

## Yêu cầu

### 1. Lược đồ – `db/schema.sql`

Thêm bảng trong `tri_thuc`, **cột và kiểu giữ đúng như sqlite** (cột `*_json` để `text`, số nguyên `integer`, `REAL` → `double precision`), có khoá chính như sqlite, `ENABLE ROW LEVEL SECURITY` và `REVOKE` theo đúng mẫu khối điều kiện vai trò đã có (T74):

- Từ `ddinter.sqlite`: `tri_thuc.ddinter_cap`, `tri_thuc.ddinter_thuoc`, `tri_thuc.ddinter_thuc_an` (thêm `id bigserial` làm khoá cho `thuc_an` vì sqlite không có khoá).
- Từ `tra_cuu.sqlite`: `tri_thuc.tra_cuu_hoat_chat`, `tri_thuc.tra_cuu_dong_nghia`, `tri_thuc.tra_cuu_thuoc` (+ chỉ mục `khoa_ten_thuoc, thuoc_id`), `tri_thuc.tra_cuu_thuoc_thanh_phan`, `tri_thuc.tra_cuu_chuyen_ma_ca`, `tri_thuc.tra_cuu_meta`.
- `CREATE TABLE IF NOT EXISTS`; chạy lại lược đồ không lỗi trên Supabase lẫn RDS.

### 2. Trình nạp – `app/db/cli.py` (+ hàm trong `app/db/engine.py` hoặc tệp mới `app/db/chi_muc.py`)

Lệnh mới `python -m app.db.cli load chi-muc [--tra-cuu PATH] [--tuong-tac PATH]` (mặc định theo settings):

- Mở sqlite chỉ đọc, chép **toàn bộ** từng bảng sang bảng PostgreSQL tương ứng trong **một giao dịch**: `TRUNCATE` rồi chèn theo lô (`COPY` qua `cursor.copy` của psycopg 3, hoặc `executemany` lô 5.000). Không đổi giá trị.
- In số dòng mỗi bảng nguồn và đích; lệch → rollback và thoát mã ≠ 0.
- Thêm `chi-muc` vào lệnh `verify` (so số dòng sqlite với DB) nếu cấu trúc `verify` cho phép; không thì in trong lệnh nạp là đủ.
- `all` **không** tự gọi `chi-muc` (tránh nạp nặng ngoài ý muốn) – ghi trong `--help`.

### 3. Đọc từ DB khi chạy

- `InteractionStore`: tách phần dựng bộ nhớ khỏi nguồn. Thêm `from_db(conn)` đọc 3 bảng `tri_thuc.ddinter_*` với **cùng câu SELECT/ORDER BY** như `from_path` và dựng đúng cùng cấu trúc. Giữ `from_path` như cũ.
- `DrugResolver`: tương tự, `from_db(conn)` đọc `tri_thuc.tra_cuu_*`. Giữ `from_index`.
- Kho đoạn: hàm `load_corpus_from_db(conn) -> list[Chunk]` đọc `tri_thuc.doan_trich` (bỏ cột `embedding`, `tu_khoa`, `nap_luc`, `nguon_tep`; `hoat_chat_ids` jsonb → list), sắp theo `doan_trich_id`. `LazyRetrieverFactory` và `container.case_asker` dùng nó khi nguồn là DB.
- Cấu hình: thêm `app.kb_source: "auto" | "file" | "db"` (biến môi trường `KB_SOURCE`, theo cách các biến khác như `CASE_SOURCE` đang được ánh xạ). `file` = như cũ. `db` = đọc DB, lỗi DB thì giữ hành vi hiện tại (trả `None` + một cảnh báo log, không làm sập app). `auto` (mặc định) = tệp có thì dùng tệp, không có và có `DATABASE_URL` thì đọc DB.
- Cảnh báo `"Không chạy yếu tố 4…"` trong `container.rule_context` ghi tên nguồn thiếu theo nguồn thực dùng (ví dụ `tri_thuc.ddinter_*`).
- Mỗi kho nạp **một lần** mỗi tiến trình như hiện nay (cached_property / `get_rule_context`). Không giữ kết nối mở sau khi nạp. Không ghi khoá, chuỗi kết nối vào log.

### 4. Test

- `tests/kb/test_store_from_db.py` (hoặc gần test hiện có của store/resolver): dựng sqlite nhỏ bằng hàm build có sẵn hoặc tay, chép sang một đối tượng kết nối giả (fake cursor trả hàng như psycopg) – kiểm `from_db` và `from_path` cho **cùng** kết quả `pair`, `drug_complete`, `foods`, `resolve` trên vài mã. Không cần PostgreSQL thật; nếu kho đã có fixture PostgreSQL (xem `tests/db/`) có thể thêm test đánh dấu bỏ qua khi không có `DATABASE_URL`.
- Test cấu hình `kb_source` (auto chọn tệp khi tệp có; chọn DB khi tệp vắng).
- Test lược đồ: các bảng mới có trong `db/schema.sql`, có RLS.

## Phạm vi

Sửa: `db/schema.sql`, `app/db/cli.py`, `app/db/engine.py` (hoặc tạo `app/db/chi_muc.py`), `app/kb/interactions/store.py`, `app/kb/resolver/resolver.py`, `app/retrieval/corpus.py`, `app/orchestration/evidence.py`, `app/container.py`, `app/config/settings.py`, `.env.example` (thêm `KB_SOURCE`, nếu tệp có). Tạo test ở mục 4 và `plan/reports/T75.md`.
Cấm: `data/`, `web/`, logic luật trong `app/rules/`, các tệp sqlite.

## Nghiệm thu (Claude chạy)

1. `uv run ruff check .`, `uv run ruff format --check`, `uv run pytest -q -p no:cacheprovider` toàn kho 0 trượt.
2. Lược đồ chạy trên RDS; `load chi-muc` lên RDS, số dòng khớp sqlite.
3. Đổi tạm tên hai sqlite + `chunks.jsonl`, `KB_SOURCE=auto`, `CASE_SOURCE=db` trỏ RDS: 66 ca ra đúng 577 nhận định như khi đọc tệp; không có cảnh báo "Không chạy yếu tố 4"; hỏi đáp trả nguồn.
