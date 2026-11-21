# T28 – Backend: xác thực JWT Supabase, phân quyền, sở hữu hội thoại và phản hồi

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort high; người dùng chốt 17/11/2026) · **Ngày:** 17/11/2026
**Đọc trước, theo thứ tự:** `AGENTS.md`; `plan/plan-1.5-bao-mat-xac-thuc-phan-quyen.md` (nguồn quyết định, đọc hết); `plan/api-hop-dong-v1.3-xac-thuc.md` (hợp đồng bạn phải theo); `app/api/main.py`, `app/api/routes.py`, `app/api/service.py`, `app/api/schemas.py`, `app/feedback.py`, `app/config/settings.py`, `.env.example`.
**Chạy song song với** T29 (web). T29 sửa `web/`; bạn **không đụng** `web/`.

## 1. Bối cảnh

API FastAPI hiện không xác thực. Web đã đăng nhập bằng Supabase Auth và sẽ gửi `Authorization: Bearer <access token>`. Việc của bạn: backend kiểm token, kiểm vai trò, ghi chủ sở hữu cho hội thoại và phản hồi. Giới hạn tốc độ **tạm hoãn, không làm**.

## 2. Việc phải làm

### 2.1 Gói `app/auth/` mới

Tạo `app/auth/` (tên module tiếng Anh theo quy ước):

- `roles.py`: hằng số vai trò `duoc_si_ls`, `admin`; **một danh sách hợp lệ duy nhất**.
- `principal.py`: mô hình dữ liệu bất biến `Principal` (`nguoi_dung_id`, `email | None`, `vai_tro`, `phien_id | None`).
- `verifier.py`: lớp kiểm JWT. Yêu cầu:
  - Thư viện: thêm `pyjwt[crypto]` bằng `uv add` (được phép sửa `pyproject.toml` và `uv.lock` chỉ để thêm gói này).
  - Khoá công khai lấy từ `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`; `iss` hợp lệ là `{SUPABASE_URL}/auth/v1`; `aud` là `authenticated`.
  - **Chỉ nhận thuật toán định sẵn**: `ES256`, `RS256` (và `EdDSA` nếu thư viện hỗ trợ sẵn); `HS256` chỉ khi có `SUPABASE_JWT_SECRET`. Không để token quyết định cách kiểm; từ chối `none`; chống nhầm thuật toán (HS256 ký bằng khoá công khai phải bị từ chối).
  - Kiểm `exp` (độ lệch cho phép 30 giây), `iss`, `aud`, chữ ký, `sub` bắt buộc.
  - Đệm JWKS trong bộ nhớ. Gặp `kid` lạ thì làm mới JWKS **một lần**, có giới hạn tần suất (không quá 1 lần mỗi 30 giây) để kẻ gửi token rác không làm sập hay chặn máy chủ.
  - Vai trò chỉ lấy từ `app_metadata.role`. **Tuyệt đối không đọc `user_metadata`.** `is_anonymous: true` → từ chối quyền.
  - Phân biệt lỗi: hết hạn → `phien_het_han`; mọi lỗi token khác → `chua_dang_nhap`; không lấy được JWKS hoặc thiếu cấu hình → `xac_thuc_khong_san_sang` (503); thiếu hoặc lạ vai trò, ẩn danh → `khong_co_quyen` (403). Đúng mã ở mục 2 của hợp đồng v1.3.
  - Mặc định từ chối (fail closed) ở mọi nhánh lỗi, kể cả ngoại lệ bất ngờ.
  - Không bao giờ ghi token, một phần token hay chữ ký vào log, thông báo lỗi hay ngoại lệ. Có thể ghi `nguoi_dung_id` và vai trò.
- `online.py`: kiểm thu hồi trực tuyến. Gọi `GET {SUPABASE_URL}/auth/v1/user` với `Authorization: Bearer <token>` và `apikey: <SUPABASE_ANON_KEY>` bằng `httpx` (có hạn chờ ngắn, 3 giây). Kết quả đúng được đệm 60 giây theo băm của token (đừng giữ token thô làm khoá; dùng SHA-256). Trả 401 từ Supabase → từ chối; lỗi mạng hoặc 5xx → **từ chối** (fail closed) với `xac_thuc_khong_san_sang`. Chỉ dùng cho thao tác ghi phản hồi (và điểm cuối admin sau này).
- `dependencies.py`: hàm phụ thuộc FastAPI: `current_principal` (lấy tiêu đề, kiểm token, trả `Principal`), `require_role(*roles)`, `require_online_check`. Điểm cuối thường dùng `require_role("duoc_si_ls", "admin")`.

### 2.2 Cấu hình

Theo mục 5 của plan 1.5: `AUTH_MODE` (`required` mặc định, `off`), `CORS_ORIGINS`, và đọc `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET` từ môi trường. Thêm vào `.env.example` các tên biến với **giá trị giữ chỗ**, kèm chú thích tiếng Việt ngắn. **Không đọc, không in giá trị thật của `.env`.**

- Khi `AUTH_MODE=required` mà thiếu `SUPABASE_URL`: ứng dụng vẫn khởi động, nhưng mọi điểm cuối ngoài `/api/health` trả `503 xac_thuc_khong_san_sang`. Không bao giờ mặc định mở.
- Khi `AUTH_MODE=off`: ghi cảnh báo lúc khởi động; coi người gọi là một `Principal` giả vai `admin` với `nguoi_dung_id = "dev-local"`; `GET /api/health` trả `"xac_thuc": "off"`.
- Giá trị `AUTH_MODE` lạ (gõ sai) → coi là `required`.

### 2.3 Nối vào API

- `create_app(service=None, auth=None)`: nhận bộ kiểm token tiêm được để test dùng khoá thử và không gọi mạng. Mọi điểm cuối trong `app/api/routes.py` dùng `require_role("duoc_si_ls", "admin")`, **trừ `GET /api/health`**.
- Điểm cuối mới `GET /api/me` đúng hợp đồng v1.3 mục 3.
- `GET /api/health` thêm `xac_thuc`.
- `POST /api/cases/{id}/feedback` dùng thêm kiểm thu hồi trực tuyến (`online.py`) trước khi ghi.
- CORS: nguồn lấy từ `CORS_ORIGINS`; thêm `Authorization` vào tiêu đề cho phép; giữ phương thức `GET, POST`.
- Lỗi của gói auth phải đi qua cùng trình xử lý lỗi hiện có để thân lỗi đúng dạng `{"loi": {"ma", "thong_bao"}}`. Thêm đúng các mã mới của hợp đồng v1.3 mục 2.

### 2.4 Sở hữu hội thoại và phản hồi

Theo hợp đồng v1.3 mục 5 và 6, và mục 4.2 của plan 1.5:

- Mỗi lượt hỏi đáp ghi thêm `nguoi_dung_id` và `phien_id` vào dòng `hoi_thoai.jsonl`.
- `PhanHoi` (`app/feedback.py`) thêm hai trường tuỳ chọn `nguoi_dung_id`, `phien_id`; đọc được dòng cũ không có chúng (tương thích ngược, không làm hỏng `load_feedback`).
- `list_conversations` và `clear_conversation` nhận người gọi: chỉ lượt của mình; `admin` thêm thấy và xoá được dòng cũ không có chủ. Dược sĩ không thấy dòng không có chủ.
- Hình dạng phản hồi JSON của hai điểm cuối này **không đổi**.
- Trong `CaseService`, truyền `Principal` xuống bằng tham số rõ ràng, không dùng biến toàn cục. Giữ khoá `_lock` hiện có.

## 3. Kiểm thử bắt buộc

Viết trong `tests/auth/` và `tests/api/`. Test **không gọi mạng**: tự sinh cặp khoá (ES256 và RS256), dựng JWKS giả, ký token thử, và tiêm bộ kiểm vào `create_app`.

1. Đủ 19 tình huống ở mục 7.1 của plan 1.5 (mỗi tình huống một test, tên test nêu rõ số).
2. Đủ 8 tình huống ở mục 7.3 của plan 1.5 (sở hữu, quyền, tương thích ngược, tuyến thử `require_role("admin")` chỉ có trong test).
3. Mọi test cũ trong `tests/api/` **giữ nguyên khẳng định**. Cho phép sửa phần dựng (`conftest`) để chạy với `AUTH_MODE=off` hoặc với bộ kiểm giả. Nghiêm cấm sửa kỳ vọng, xoá hay đánh dấu `skip`/`xfail` để cho qua.
4. Một test xác nhận **không tìm thấy chuỗi token** trong log và trong thân lỗi khi token sai.
5. Một test xác nhận `create_app()` dựng từ môi trường không có `AUTH_MODE` thì ở chế độ `required`.

## 4. Phạm vi file

**Được tạo hoặc sửa:** `app/auth/**`, `app/api/**`, `app/feedback.py`, `app/config/**` (chỉ để đọc biến mới), `tests/auth/**`, `tests/api/**`, `tests/conftest.py` (nếu có), `.env.example`, `pyproject.toml` và `uv.lock` (chỉ để thêm `pyjwt[crypto]`).
**Cấm đụng:** `web/`, `app/db/`, `db/`, `app/kb/`, `app/orchestration/`, `app/verify/`, `data/`, `plan/`, `.env`, `Dockerfile`, `docker-compose.yml`, `Caddyfile`.
Nếu phải sửa tệp ngoài danh sách thì dừng lại, ghi rõ vào báo cáo và không sửa.

## 5. Nghiệm thu

```bash
uv run ruff check app/auth app/api app/feedback.py tests/auth tests/api
uv run ruff format --check app/auth app/api app/feedback.py tests/auth tests/api
uv run pytest -q -p no:cacheprovider tests/auth tests/api
uv run pytest -q -p no:cacheprovider --ignore=tests/architecture/.tmp --ignore=tests/db/.tmp --ignore=tests/kb/.tmp
```

Toàn kho **không được có test trượt mới** so với trước khi bạn làm (trước đó: 723 qua). Rồi chạy `uvicorn` thật ở cổng 8030 với `AUTH_MODE=required` và **không có token**: dán kết quả `curl` của `/api/health` (200, có `xac_thuc`), `/api/cases` (401 `chua_dang_nhap`) và `/api/me` (401). Rồi `AUTH_MODE=off` để xác nhận cảnh báo lúc khởi động và `"xac_thuc": "off"`. Dừng tiến trình `uvicorn` sau khi xong.

## 6. Cấm làm

Không đọc hay in `.env`. Không tạo khoá, không tạo người dùng Supabase, không gọi Supabase thật (kể cả để thử). Không dùng `user_metadata` để cấp quyền. Không làm giới hạn tốc độ. Không commit, không push. Không thêm thư viện ngoài `pyjwt[crypto]`. Không đổi tên trường nào ngoài những gì hợp đồng v1.3 nêu. Báo cáo theo mẫu trong `AGENTS.md`, nêu rõ: tệp đã tạo, tệp đã sửa, kết quả từng lệnh nghiệm thu, và mọi chỗ lệch brief.

## Phụ lục A – Lệnh SQL cấp vai trò (chủ kho chạy trong Supabase SQL Editor; agent không chạy)

```sql
update auth.users
set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || '{"role":"admin"}'::jsonb
where email = 'EMAIL-CUA-BAN';
```

Dược sĩ lâm sàng: thay `"admin"` bằng `"duoc_si_ls"`. Người dùng phải đăng xuất rồi đăng nhập lại để token mới mang vai trò.
