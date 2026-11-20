# Sổ tay vận hành: tách tài khoản DB và bí mật ứng dụng

Tài liệu hướng dẫn chủ kho thực hiện trên AWS RDS và máy chủ EC2 để chuyển ứng dụng từ tài khoản chủ (`vinmec_admin`) sang tài khoản quyền tối thiểu (`vinmec_app`), tách tài khoản nạp (`vinmec_loader`), bật kiểm tra chứng chỉ TLS (`sslmode=verify-full`) và bỏ `SUPABASE_SERVICE_ROLE_KEY` khỏi máy chủ.

---

## Trước khi kéo mã mới về EC2

- **Tạo `.env.app` trước khi kéo mã và dựng container:** mã mới dùng `env_file: .env.app`, nên nếu kéo mã rồi chạy `docker compose up` khi chưa có `.env.app`, Compose sẽ dừng với lỗi thiếu tệp. Hãy tạo `.env.app` trước (có thể tạm chép từ `.env` hiện có rồi **bỏ** `SUPABASE_SERVICE_ROLE_KEY`, giữ `DATABASE_URL` cũ cho tới khi hoàn thành bước chuyển tài khoản DB).
- **Có sẵn tệp `certs/rds-global-bundle.pem` trước khi `up`:** nếu tệp chưa tồn tại khi gắn volume, Docker sẽ tự tạo một **thư mục** cùng tên trên máy chủ và kết nối `sslmode=verify-full` sẽ lỗi. Kiểm tra trước bằng:
  ```bash
  test -f certs/rds-global-bundle.pem
  ```
- **Kiểm tra các tài khoản DB đang có quyền đăng nhập:** `db/roles.sql` chạy `REVOKE ALL ON DATABASE … FROM PUBLIC`, nên mọi tài khoản DB khác (nếu có, ngoài tài khoản chủ, `vinmec_app`, `vinmec_loader`) sẽ mất quyền kết nối. Liệt kê trước bằng:
  ```sql
  SELECT rolname FROM pg_roles WHERE rolcanlogin;
  ```

---

## 1. Tải chứng chỉ gốc RDS

Trên EC2 (trong thư mục dự án) và máy quản trị, tải bundle chứng chỉ gốc toàn cầu chính thức của AWS RDS về `./certs/rds-global-bundle.pem` (thư mục `certs/` đã nằm trong `.gitignore`):

```bash
mkdir -p certs
curl -fsSL "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem" -o certs/rds-global-bundle.pem
```

Kiểm tra nhanh tệp đã tải là chuỗi chứng chỉ X.509 hợp lệ (`-----BEGIN CERTIFICATE-----`) và chỉ đọc với user thường:

```bash
chmod 644 certs/rds-global-bundle.pem
openssl x509 -in certs/rds-global-bundle.pem -noout -subject -issuer -dates
```

---

## 2. Tạo bảng mới (nếu có) và phân quyền trong PostgreSQL

Mở đường hầm SSM (hoặc kết nối từ EC2 tới endpoint RDS) bằng `psql` dưới **tài khoản chủ RDS** (`vinmec_admin`):

```bash
psql "postgresql://vinmec_admin@127.0.0.1:5433/vinmec?sslmode=require"
```

Trong phiên `psql` (hoặc chạy `-f`), thực hiện **đúng thứ tự**:

1. Chạy `db/schema.sql` (nếu có bảng mới):
   ```sql
   \i db/schema.sql
   ```
2. Chạy `db/roles.sql` để tạo/cập nhật `vinmec_app` và `vinmec_loader` với quyền tối thiểu:
   ```sql
   \i db/roles.sql
   ```
3. Đặt mật khẩu mạnh cho từng vai trò trực tiếp trong `psql` (không gõ mật khẩu vào lịch sử shell hay tệp SQL):
   ```sql
   \password vinmec_app
   \password vinmec_loader
   ```
   > Mẹo: nếu mật khẩu có ký tự đặc biệt (`@`, `:`, `/`, `#`, `%`), hãy URL-encode khi ghép vào chuỗi `postgresql://...`.

---

## 3. Tạo `.env.app` trên EC2 và khởi động lại dịch vụ

1. Trên EC2, sao chép `.env.app.example` thành `.env.app` (chỉ chứa biến API cần, **không** có `SUPABASE_SERVICE_ROLE_KEY`, **không** có `DATABASE_URL_LOADER`):
   ```bash
   cp .env.app.example .env.app
   chmod 600 .env.app
   ```
2. Điền các giá trị thực tế vào `.env.app`, trong đó `DATABASE_URL` trỏ bằng tài khoản `vinmec_app` và chứng chỉ bên trong container:
   ```dotenv
   DATABASE_URL=postgresql://vinmec_app:<mat-khau-url-encoded>@<rds-endpoint>:5432/<db>?sslmode=verify-full&sslrootcert=/srv/certs/rds-global-bundle.pem
   ```
3. Khởi động lại container API để nạp `.env.app` và gắn `./certs/rds-global-bundle.pem` chỉ đọc vào `/srv/certs/rds-global-bundle.pem`:
   ```bash
   docker compose config -q
   docker compose up -d
   ```
4. Với máy quản trị dùng cho các lệnh nạp (`python -m app.db ...`, `python -m app.kb.dictionary publish --yes`), tạo tệp `.env.loader` riêng từ `.env.loader.example` với `DATABASE_URL_LOADER` của `vinmec_loader`.

---

## 4. Kiểm tra sau chuyển đổi

1. **Kiểm tra sức khoẻ API:**
   ```bash
   curl -fsS http://127.0.0.1:8000/api/health
   ```
   Xác nhận `"ok": true`.
2. **Kiểm tra log khởi động của API:**
   ```bash
   docker compose logs --tail=100 api
   ```
   Xác nhận **không còn** cảnh báo `"API đang dùng tài khoản chủ DB"` và **không còn** cảnh báo về `sslmode=verify-full`.
3. **Kiểm tra quyền thực tế của `vinmec_app` bằng `psql`:**
   ```bash
   psql "postgresql://vinmec_app@127.0.0.1:5433/vinmec?sslmode=verify-full&sslrootcert=certs/rds-global-bundle.pem"
   ```
   - Đọc bảng nghiệp vụ và tri thức phải **thành công** và trả về số dòng **> 0** (khi DB đã nạp dữ liệu):
     ```sql
     SELECT count(*) FROM nghiep_vu.dot_dieu_tri;
     SELECT count(*) FROM nghiep_vu.y_lenh;
     SELECT count(*) FROM tri_thuc.bang_luat_meta;
     ```
     > **Bắt buộc kiểm tra `SELECT count(*) FROM nghiep_vu.dot_dieu_tri;` > 0** (phải khớp số dòng của tài khoản chủ). Nếu lệnh chạy không lỗi nhưng trả về `0`, nguyên nhân là thiếu policy RLS trên bảng — chạy lại `db/roles.sql` bằng tài khoản chủ; **không** đổi `DATABASE_URL` về tài khoản chủ.
   - Thao tác phá huỷ hoặc ghi bảng ngoài phạm vi phải **bị từ chối** (`permission denied`):
     ```sql
     DROP TABLE nghiep_vu.y_lenh;
     DELETE FROM tri_thuc.hoat_chat;
     CREATE TABLE nghiep_vu.thu_nghiem (id int);
     ```

---

## 5. Đổi mật khẩu tài khoản chủ, lưu bí mật ở SSM Parameter Store và dọn máy chủ

1. **Đổi mật khẩu tài khoản chủ RDS (`vinmec_admin`):**
   - Vì mật khẩu cũ từng xuất hiện trong lịch sử lệnh SSM, hãy xoay vòng/đổi mật khẩu ngay trên AWS Secrets Manager / RDS Console (hoặc tắt xoay vòng tự động nếu dùng mật khẩu quản trị cố định) sau khi xác nhận `vinmec_app` chạy ổn định.
2. **Lưu bí mật bằng SSM Parameter Store (`SecureString`):**
   - Không truyền giá trị mật khẩu, API key trực tiếp trong tham số lệnh `aws ssm send-command` (vì AWS lưu lại lịch sử lệnh).
   - Lưu từng bí mật (hoặc nội dung `.env.app`) vào **AWS Systems Manager Parameter Store** dưới dạng **`SecureString`** (mã hoá KMS), cấp quyền IAM tối thiểu cho role EC2 đọc đúng đường dẫn tham số đó, rồi trên EC2 chạy lệnh kéo trực tiếp từ Parameter Store ghi ra `.env.app` (ví dụ `aws ssm get-parameter --with-decryption ...`).
3. **Xoá `SUPABASE_SERVICE_ROLE_KEY` khỏi máy chủ:**
   - Kiểm tra `.env` cũ và mọi tệp sao lưu trên EC2, xoá hoàn toàn `SUPABASE_SERVICE_ROLE_KEY` (hoặc xoá hẳn tệp `.env` cũ sau khi đã chuyển sang `.env.app`).
   - Kiểm tra biến môi trường trong container đang chạy không chứa `SUPABASE_SERVICE_ROLE_KEY`:
     ```bash
     docker compose exec api env | grep -i service_role || echo "OK: khong co service_role"
     ```

---

## 6. Quay lui (Rollback) khi có sự cố

Nếu ứng dụng gặp lỗi kết nối DB hoặc lỗi phân quyền sau khi chuyển sang `vinmec_app`:

1. Mở `.env.app` trên EC2 và tạm đổi `DATABASE_URL` về chuỗi kết nối tài khoản cũ (nếu lỗi chứng chỉ, kiểm tra đường dẫn `/srv/certs/rds-global-bundle.pem` trong container hoặc tạm đặt `sslmode=require` trong lúc chẩn đoán).
2. Khởi động lại container API:
   ```bash
   docker compose up -d api
   ```
3. Kiểm tra nhật ký lỗi SQL (`permission denied for table/sequence ...`) để bổ sung đúng quyền tối thiểu còn thiếu vào `db/roles.sql`, chạy lại `db/roles.sql` bằng tài khoản chủ rồi chuyển `DATABASE_URL` lại về `vinmec_app`.

---

## 7. Thử trước trên máy local bằng Docker

Trước khi áp dụng lên RDS thật, có thể dựng PostgreSQL tạm trên máy local (chỉ lắng nghe trên `127.0.0.1`) để kiểm tra `db/schema.sql`, `db/roles.sql`, đường nạp `vinmec_loader` và quyền đọc/ghi của `vinmec_app`:

1. **Khởi chạy container `pgvector/pgvector:pg17` chỉ nghe trên `127.0.0.1`:**
   ```bash
   docker run -d --name vinmec-pg-test \
     -e POSTGRES_USER=vinmec_admin \
     -e POSTGRES_PASSWORD='<mật-khẩu-tạm>' \
     -e POSTGRES_DB=vinmec \
     -p 127.0.0.1:55432:5432 \
     pgvector/pgvector:pg17
   ```
2. **Dựng lược đồ bằng tài khoản chủ (`PYTHON_DOTENV_DISABLED=1` để không đọc nhầm `.env`):**
   ```bash
   PYTHON_DOTENV_DISABLED=1 \
   DATABASE_URL='postgresql://vinmec_admin:<mật-khẩu-tạm>@127.0.0.1:55432/vinmec' \
     uv run python -m app.db schema
   ```
3. **Chạy `db/roles.sql` hai lần liên tiếp bằng tài khoản chủ (xác nhận chạy lại không lỗi):**
   ```bash
   psql "postgresql://vinmec_admin:<mật-khẩu-tạm>@127.0.0.1:55432/vinmec" -v ON_ERROR_STOP=1 -f db/roles.sql
   psql "postgresql://vinmec_admin:<mật-khẩu-tạm>@127.0.0.1:55432/vinmec" -v ON_ERROR_STOP=1 -f db/roles.sql
   ```
4. **Đặt mật khẩu tạm cho `vinmec_app` và `vinmec_loader` trực tiếp trong `psql`:**
   ```bash
   psql "postgresql://vinmec_admin:<mật-khẩu-tạm>@127.0.0.1:55432/vinmec"
   ```
   Trong phiên `psql`, nhập `<mật-khẩu-tạm>` cho từng vai trò:
   ```sql
   \password vinmec_app
   \password vinmec_loader
   ```
5. **Nạp ca giả lập bằng `vinmec_loader` qua `DATABASE_URL_LOADER`:**
   ```bash
   PYTHON_DOTENV_DISABLED=1 \
   DATABASE_URL_LOADER='postgresql://vinmec_loader:<mật-khẩu-tạm>@127.0.0.1:55432/vinmec' \
     uv run python -m app.db load cases
   ```
   (Có thể kiểm tiếp `uv run python -m app.db hanh-chinh` và `uv run python -m app.db phieu-dieu-tri` với cùng `DATABASE_URL_LOADER`.)
6. **Đếm dòng bằng `vinmec_app` và đối chiếu với tài khoản chủ (`> 0` và khớp số dòng):**
   ```bash
   psql "postgresql://vinmec_app:<mật-khẩu-tạm>@127.0.0.1:55432/vinmec" \
     -c "SELECT count(*) FROM nghiep_vu.dot_dieu_tri;"
   ```
7. **Dọn container tạm sau khi kiểm xong:**
   ```bash
   docker rm -f vinmec-pg-test
   ```
