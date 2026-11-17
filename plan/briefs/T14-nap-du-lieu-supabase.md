# T14 – Lược đồ và lệnh nạp dữ liệu vào Supabase (chạy lại được từ đầu)

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort xhigh) · **Ngày:** 17/11/2026
**Đọc trước (bắt buộc):** `AGENTS.md`; `docs/erd.md`; `plan/plan-1.1-kien-truc-chi-tiet.md` (phần cơ sở dữ liệu); `plan/plan-1.3-du-lieu-thu-thap-tong-hop-tien-xu-ly.md`; `app/domain/models.py`, `app/domain/loader.py`; `data/mock/demo/`, `data/gold/demo/`, `data/kb/`, `data/kb_curated/chunks.jsonl` (đọc vài dòng đầu), `data/kb_sources/README.md`.

## 1. Mục tiêu

Người dùng đã có một dự án Supabase (PostgreSQL), chuỗi kết nối nằm ở biến `DATABASE_URL` trong `.env`. Cần **một bộ lệnh nạp dùng lại được**: khi phát hiện dữ liệu sai trường, người dùng sửa file ánh xạ hoặc file lược đồ rồi chạy lại một lệnh là có cơ sở dữ liệu đúng từ đầu.

Task này **chỉ** làm lược đồ, lệnh nạp và lệnh kiểm. Chưa chuyển ứng dụng sang đọc từ cơ sở dữ liệu (ứng dụng vẫn đọc file như hiện nay).

## 2. Lược đồ (`db/schema.sql`)

- Hai lược đồ: `nghiep_vu` (dữ liệu thay đổi theo thời gian) và `tri_thuc` (ít đổi). Không tạo, sửa, xoá gì trong `public`, `auth`, `storage` hay lược đồ khác của Supabase.
- `nghiep_vu`: các bảng theo `docs/erd.md` mà dữ liệu ca demo có dữ liệu (người bệnh, dị ứng, đợt điều trị, chẩn đoán, sinh hiệu, kết quả xét nghiệm, diễn biến, y lệnh, chi tiết y lệnh, lịch dùng nếu có, vi sinh nếu có, lần thẩm định, nhận định, căn cứ, phản hồi). Tên bảng và tên cột lấy đúng theo ERD và theo trường của `app/domain/models.py`; hai nơi lệch nhau thì theo mô hình pydantic và ghi chỗ lệch vào báo cáo.
- `tri_thuc`: `hoat_chat`, `ten_thuoc` (tên gọi khác → hoạt chất), `tai_lieu` (một dòng cho mỗi nhãn: nguồn, tầng tin cậy, giấy phép, phiên bản, `set_id`, `url_goc`, mã băm), `doan_trich` (toàn bộ trường của một dòng trong `chunks.jsonl`), `quy_tac_lieu_than`, `tuong_tac_sang_loc` (DDInter).
- `doan_trich` có cột `embedding halfvec(2048)` cho phép rỗng, và cột `tsvector` sinh tự động cho tìm theo từ khoá. Dùng `halfvec` vì chỉ mục HNSW của kiểu `vector` giới hạn 2.000 chiều, còn mô hình nhúng của dự án cho 2.048 chiều. Tạo chỉ mục HNSW (`halfvec_cosine_ops`) và chỉ mục GIN.
- `CREATE EXTENSION IF NOT EXISTS vector` ở đầu file.
- Khoá chính, khoá ngoại, `NOT NULL`, `CHECK` cho các trường dạng mã (kết luận, mức độ, giới tính…) đúng với các giá trị trong mô hình pydantic.
- Mỗi bảng có cột `nap_luc timestamptz default now()` và `nguon_tep text` (tệp gốc của dòng).
- Bật `ROW LEVEL SECURITY` cho mọi bảng và **không** tạo chính sách nào (mặc định từ chối với khoá công khai; lệnh nạp chạy bằng kết nối trực tiếp nên không bị ảnh hưởng). Ghi điều này thành chú thích trong file.

## 3. Lệnh (`python -m app.db <lệnh>`)

| Lệnh | Việc |
| :--- | :--- |
| `check` | Kết nối, in phiên bản PostgreSQL, phần mở rộng `vector` có chưa, hai lược đồ có chưa. Không ghi gì |
| `schema` | Chạy `db/schema.sql` (chỉ tạo cái chưa có) |
| `reset --yes` | `DROP SCHEMA nghiep_vu CASCADE; DROP SCHEMA tri_thuc CASCADE;` rồi chạy lại `schema`. Thiếu `--yes` thì từ chối và in ra những gì sẽ bị xoá |
| `load cases` | Nạp ca demo từ `data/mock/demo/` (và đáp án từ `data/gold/demo/` nếu lược đồ có bảng tương ứng) |
| `load kb` | Nạp `data/kb/*.json` và `data/kb_curated/chunks.jsonl` |
| `load ddinter` | Nạp 14 tệp CSV của `data/kb_sources/ddinter/` (dùng `COPY`, gộp cặp trùng) |
| `load embeddings` | Điền cột `embedding` từ bộ đệm `data/cache/embeddings.sqlite` cho các đoạn đã có véc-tơ; in số đoạn có và chưa có. Không gọi mạng |
| `all [--reset --yes]` | `schema` → `load cases` → `load kb` → `load ddinter` → `load embeddings` → `verify` |
| `verify` | Với mỗi bảng: số dòng trong nguồn, số dòng trong cơ sở dữ liệu, khớp hay lệch; số khoá ngoại mồ côi; số đoạn thiếu `embedding`. Có lệch thì mã thoát khác 0 |

Yêu cầu chung:

- Mọi lệnh `load` nhận `--dry-run`: đọc nguồn, kiểm theo ánh xạ, in số dòng sẽ nạp của từng bảng và các dòng bị loại kèm lý do, **không kết nối cơ sở dữ liệu**.
- Nạp kiểu ghi đè theo khoá chính (`INSERT … ON CONFLICT … DO UPDATE`): chạy lại nhiều lần cho cùng kết quả, không sinh dòng trùng. Mỗi lệnh `load` chạy trong một giao dịch; lỗi giữa chừng thì không để lại dữ liệu dở.
- Thêm cờ `--replace` cho từng lệnh `load`: xoá dữ liệu của đúng nhóm bảng đó trước khi nạp (để dòng đã bỏ khỏi nguồn không còn sót lại).
- **Ánh xạ nguồn → cột đặt ở một nơi dễ sửa:** `app/db/mapping.py`, mỗi bảng một khối khai báo (tên bảng, khoá chính, danh sách cột, trường nguồn tương ứng, hàm chuyển đổi nếu có). Người dùng sửa sai trường ở đây và ở `db/schema.sql`, không phải sửa logic nạp.
- Dòng không qua được kiểm tra (thiếu trường bắt buộc, sai kiểu) bị loại, ghi vào `data/runtime/nap_loi.jsonl` kèm lý do; không dừng cả lượt nạp trừ khi tỉ lệ loại vượt 5% của một bảng.
- Đọc `DATABASE_URL` qua lớp cấu hình sẵn có (`config/settings.yaml` mục `database.url_env`). Không in chuỗi kết nối, mật khẩu; khi lỗi kết nối chỉ in tên máy chủ đã che và loại lỗi.
- Trình điều khiển: `psycopg[binary]` bản 3 (thêm vào `pyproject.toml` bằng `uv add`). Không dùng ORM.
- Viết `db/README.md` ngắn: các lệnh, thứ tự chạy lần đầu, cách sửa một trường rồi nạp lại, cách bật `vector` trên Supabase nếu lệnh `check` báo thiếu.

## 4. Giới hạn an toàn (bắt buộc)

- **Bạn không được chạy lệnh nào ghi vào cơ sở dữ liệu thật.** Chỉ được chạy `--dry-run`, test, và `check` (chỉ đọc). Người dùng tự chạy `all` lần đầu.
- `reset` chỉ được đụng hai lược đồ `nghiep_vu` và `tri_thuc`; tên lược đồ là hằng số trong code, không nhận từ tham số dòng lệnh.
- Dữ liệu nạp là dữ liệu giả lập sẵn có trong kho. Không tạo thêm dữ liệu người bệnh, không sửa nội dung y khoa.

## 5. Phạm vi file

Được tạo, sửa: `db/**`, `app/db/**`, `tests/db/**`, `pyproject.toml` và `uv.lock` (chỉ để thêm `psycopg`), `.env.example` (không cần đổi nếu đã có `DATABASE_URL`).
**Cấm đụng:** `web/`, `app/api/`, `app/orchestration/`, `app/kb/`, `app/retrieval/`, `data/kb_sources/`, `data/kb_curated/`, `config/`, `plan/`. Ba task khác đang chạy song song ở đó.

## 6. Kiểm thử phải có (không cần cơ sở dữ liệu thật)

- Ánh xạ: mọi cột khai báo trong `mapping.py` có trong `db/schema.sql` và ngược lại (phân tích file SQL bằng biểu thức chính quy là đủ).
- Chuyển 6 ca demo thành dòng: số dòng từng bảng đúng với số phần tử trong JSON; khoá ngoại của dòng con trỏ tới dòng cha có trong lượt nạp.
- Dòng thiếu trường bắt buộc bị loại và có lý do.
- `reset` thiếu `--yes` → từ chối, không mở kết nối.
- Câu SQL sinh ra dùng tham số, không ghép chuỗi giá trị.
- Thứ tự nạp tôn trọng khoá ngoại.
- Thông báo lỗi kết nối không chứa mật khẩu (thử với chuỗi kết nối giả có mật khẩu).

## 7. Nghiệm thu

```bash
uv run ruff check app/db tests/db
uv run ruff format --check app/db tests/db
uv run pytest -q tests/db -p no:cacheprovider
uv run python -m app.db all --dry-run
uv run python -m app.db check
```

Dán kết quả `all --dry-run` (số dòng từng bảng) và `check` vào báo cáo.

## 8. Cấm làm

Không ghi vào cơ sở dữ liệu thật. Không commit, không push. Không in giá trị trong `.env`. Trả lời theo mẫu trong `AGENTS.md`.
