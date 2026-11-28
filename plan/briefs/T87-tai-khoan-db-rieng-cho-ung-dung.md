# T87 – Tài khoản DB riêng cho ứng dụng, tách bí mật (sửa C3, kèm T5)

Nguồn: `docs/bao-cao-bao-mat-2026-11-20.md` mục C3 và T5 (đọc trước). Agent: agy `gemini-4-hydrogen-high`. **Không gọi shell, không gọi mạng, không kết nối DB, không gọi MCP; chỉ đọc và ghi tệp.**

## 1. Bối cảnh

API đang nối DB bằng tài khoản chủ RDS (`vinmec_admin`). Một lỗi SQL injection hay RCE là mất cả DB. `docker-compose.yml` nạp cả `.env` (có `SUPABASE_SERVICE_ROLE_KEY` mà ứng dụng không dùng). `sslmode=require` mã hoá nhưng không kiểm chứng chỉ.

Task này chỉ **viết** script và cấu hình; **chủ kho tự chạy** lên RDS. Không có mật khẩu nào trong tệp.

## 2. Phạm vi tệp

Được tạo:
- `db/roles.sql` – tạo vai trò và cấp quyền.
- `docs/van-hanh/tai-khoan-db.md` – sổ tay cho chủ kho (các bước chạy, thứ tự, cách quay lui).
- `.env.app.example` – biến môi trường **chỉ** API cần.
- `.env.loader.example` – biến cho script nạp dữ liệu (`DATABASE_URL_LOADER`).
- `tests/db/test_roles_sql.py`, `tests/config/test_db_url_security.py`.

Được sửa:
- `docker-compose.yml` – `env_file: .env.app`; gắn chứng chỉ gốc RDS chỉ đọc (xem 3.4).
- `app/config/settings.py` – thêm hàm kiểm URL (3.3) và hàm chọn URL cho loader (3.2). Không đổi hành vi hàm khác.
- `app/api/main.py` – **chỉ** thêm một lời gọi kiểm URL trong `_lifespan`.
- Các điểm vào script **ghi** dữ liệu (nạp, xuất bản, nhúng): `app/db/cli.py`, `app/kb/dictionary/publish.py` và các tệp khác bạn tìm thấy có câu ghi vào `tri_thuc` hay `nghiep_vu` mà **không** phải đường chạy của API (liệt kê hết trong báo cáo).
- `.gitignore` – thêm `.env.app`, `.env.loader`, `certs/`.

**Cấm đụng:** `app/api/service.py`, `app/api/routes.py`, `app/api/schemas.py`, `app/orchestration/`, `db/schema.sql`, `.env.example`, `app/auth/` (T86, T88 sửa), `web/`, `plan/`. Không đọc, không in `.env`, `important/`.

## 3. Yêu cầu

### 3.1 `db/roles.sql`

Chạy bằng `psql` dưới tài khoản chủ, chạy lại nhiều lần không lỗi (dùng `DO $$ … IF NOT EXISTS … $$`).

- `vinmec_app` (`LOGIN`, `NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT`, `CONNECTION LIMIT 20`): API chạy bằng tài khoản này.
  - `CONNECT` trên DB hiện tại (`current_database()` qua `EXECUTE format(...)`).
  - `USAGE` trên lược đồ `tri_thuc`, `nghiep_vu`; **không** `CREATE` trên lược đồ nào.
  - `SELECT` trên mọi bảng `tri_thuc` và `nghiep_vu`; `ALTER DEFAULT PRIVILEGES … GRANT SELECT` cho bảng tạo sau.
  - Ghi: **chỉ** đúng các bảng và thao tác mà đường chạy API dùng. Tìm bằng cách đọc mã (`app/feedback.py`, `app/storage/feedback_chat.py`, `app/storage/review_results.py` và mọi tệp API gọi tới): ghi cụ thể `INSERT`, `UPDATE` (nếu có `ON CONFLICT DO UPDATE`), `DELETE` cho từng bảng. Kèm `USAGE, SELECT` trên sequence của các bảng đó.
  - `nghiep_vu.phan_cong` (bảng T86 thêm, có thể chưa tồn tại lúc chạy): chỉ `SELECT`; bọc trong khối kiểm bảng tồn tại.
  - `ALTER ROLE vinmec_app SET statement_timeout = '15s'`; `SET idle_in_transaction_session_timeout = '30s'`.
- `vinmec_loader` (`LOGIN`, cùng cờ `NO…`): `SELECT, INSERT, UPDATE, DELETE, TRUNCATE` trên bảng `tri_thuc` và các bảng dữ liệu ca giả lập trong `nghiep_vu`; `USAGE, SELECT, UPDATE` sequence; **không** `CREATE`, không `DROP`. Đổi lược đồ (`schema.sql`) vẫn do tài khoản chủ chạy tay.
- `REVOKE CREATE ON SCHEMA public FROM PUBLIC;` `REVOKE ALL ON DATABASE … FROM PUBLIC` rồi cấp lại `CONNECT` cho hai vai trò trên và tài khoản chủ.
- Mật khẩu **không** nằm trong tệp. Cuối tệp là chú thích hướng dẫn đặt bằng `\password vinmec_app` trong psql.
- Không dùng tên người, không dùng `GRANT ALL`.

### 3.2 Script nạp dùng tài khoản loader

`settings.py`: `def loader_database_url() -> str` – trả `DATABASE_URL_LOADER` nếu có; không có thì trả `DATABASE_URL` và ghi log cảnh báo một lần (không in giá trị). Các điểm vào ghi ở mục 2 đổi sang hàm này. API vẫn dùng `DATABASE_URL`.

### 3.3 Kiểm URL lúc khởi động

`settings.py`: `def database_url_warnings(url: str) -> list[str]` – hàm thuần, trả danh sách cảnh báo **không chứa mật khẩu hay URL**:
- người dùng trong URL là `vinmec_admin` hoặc `postgres` → `"API đang dùng tài khoản chủ DB"`;
- host không phải `localhost` / `127.0.0.1` / `::1` mà `sslmode` khác `verify-full` → cảnh báo kiểm chứng chỉ;
- URL không phân tích được → một cảnh báo chung.

`main.py` `_lifespan`: nếu có `DATABASE_URL` thì ghi từng cảnh báo bằng `logger.warning`. Không chặn khởi động (máy local đi qua đường hầm `127.0.0.1:5433`).

### 3.4 `docker-compose.yml` và tệp mẫu

- `api.env_file: .env.app`. Giữ chú thích về bí mật, sửa cho đúng.
- `api.volumes` thêm `./certs/rds-global-bundle.pem:/srv/certs/rds-global-bundle.pem:ro`.
- `.env.app.example`: liệt kê đúng các biến API đọc (lấy từ `.env.example` hiện có + `CASE_SCOPE`, `PHAN_CONG_PATH`), `DATABASE_URL` mẫu dạng `postgresql://vinmec_app:<mật-khẩu>@<host>:5432/<db>?sslmode=verify-full&sslrootcert=/srv/certs/rds-global-bundle.pem`. **Không** có `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` chỉ khi còn dùng HS256 (giữ chú thích như `.env.example`).
- `.env.loader.example`: `DATABASE_URL_LOADER` mẫu với `vinmec_loader`.

### 3.5 Sổ tay `docs/van-hanh/tai-khoan-db.md`

Các bước chủ kho làm, theo thứ tự: tải chứng chỉ gốc RDS (ghi URL chính thức của AWS cho bundle toàn cầu, để chủ kho tự tải và kiểm), chạy `schema.sql` (nếu có bảng mới) rồi `roles.sql` bằng tài khoản chủ, đặt mật khẩu, tạo `.env.app` trên EC2, khởi động lại, kiểm (`/api/health`, xem log không còn cảnh báo, thử `SELECT` được và `DROP TABLE` bị từ chối bằng `vinmec_app`), đổi mật khẩu tài khoản chủ, lưu bí mật ở SSM Parameter Store `SecureString` thay vì truyền trong lệnh SSM, xoá `SUPABASE_SERVICE_ROLE_KEY` khỏi máy chủ. Mục quay lui: đổi `DATABASE_URL` về tài khoản cũ.

## 4. Bảo mật

- Nguyên tắc quyền tối thiểu; không mật khẩu, không host thật, không mã dự án thật trong tệp mới (dùng `<host>`, `<db>`).
- Hàm cảnh báo không bao giờ trả hay log URL, mật khẩu.

## 5. Test

- `tests/config/test_db_url_security.py`: các trường hợp 3.3, kể cả URL có mật khẩu đặc biệt — khẳng định mật khẩu **không** xuất hiện trong bất kỳ cảnh báo nào; `loader_database_url` ưu tiên biến loader (dùng `monkeypatch`, `PYTHON_DOTENV_DISABLED=1` để không đọc `.env` thật).
- `tests/db/test_roles_sql.py` (đọc tệp, không kết nối DB):
  - quét `app/` tìm mọi câu `INSERT INTO nghiep_vu.<bảng>`, `UPDATE nghiep_vu.<bảng>`, `DELETE FROM nghiep_vu.<bảng>` thuộc đường chạy API (danh sách mô-đun API khai báo trong test); với mỗi cặp (thao tác, bảng) phải có `GRANT` tương ứng cho `vinmec_app` trong `roles.sql`;
  - `roles.sql` không có `GRANT ALL`, không có `PASSWORD '`, không cấp `CREATE` cho `vinmec_app`;
  - `vinmec_app` không có quyền ghi trên bất kỳ bảng `tri_thuc` nào.

## 6. Nghiệm thu (Claude chạy)

```
uv run ruff check .
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider
docker compose config -q
```

## 7. Cấm

- Không kết nối DB, không chạy SQL, không gọi MCP, không cài gói, không tải chứng chỉ.
- Không đọc hay chép `.env`. Không sửa tệp ngoài mục 2.

## 8. Báo cáo

`plan/reports/T87.md` theo mẫu `AGENTS.md`, thêm bảng: bảng → thao tác cấp cho `vinmec_app`, kèm tệp:dòng mã dùng thao tác đó; danh sách điểm vào loader đã đổi.
