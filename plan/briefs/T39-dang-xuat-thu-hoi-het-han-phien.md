# T39 – Đăng xuất, thu hồi quyền, hết hạn phiên; sửa nhãn vai trò

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort high) · **Ngày:** 18/11/2026
**Đọc trước, theo thứ tự:** `AGENTS.md`; `plan/plan-1.5-bao-mat-xac-thuc-phan-quyen.md` **mục 11** (quyết định Q-L1…Q-L8, kiểm thử 11.3); `plan/api-hop-dong-v1.3-xac-thuc.md` mục 7; `app/auth/` (`verifier.py`, `online.py`, `dependencies.py`, `errors.py`, `principal.py`); `app/api/main.py`, `app/api/routes.py`; `web/src/features/auth/` (`authClient.ts`, `AuthProvider.tsx`, `useAuth.ts`, `LoginPage.tsx`, `authEvents.ts`), `web/src/api/client.ts`, `web/src/features/sidebar/SidebarNav.tsx`, `web/src/app/WorkspacePage.tsx`, `web/src/state/useChat.ts`.

## 1. Bối cảnh

T28, T29, T38 đã xong và đã triển khai. Review 18/11 thấy bốn thiếu sót (plan 1.5 mục 11.1): (1) đăng xuất không làm access token cũ mất hiệu lực ở backend; (2) kiểm thu hồi chỉ có ở `feedback`, và không đối chiếu vai trò hiện tại; (3) không có tự đăng xuất khi nhàn rỗi và không rõ hành vi nhiều tab; (4) thanh bên **gắn cứng nhãn "Dược sĩ"** cho mọi tài khoản, kể cả admin. Giới hạn tốc độ vẫn **hoãn**.

## 2. Backend (`app/`, `tests/`)

### 2.1 Kiểm trực tuyến cho mọi điểm cuối (Q-L3, Q-L4)

Sửa `app/auth/online.py` và `app/auth/dependencies.py`:

- `current_principal` gọi kiểm trực tuyến cho **mọi điểm cuối trừ `GET /api/health`**. Bộ đệm giữ nguyên: 60 giây, khoá là SHA-256 của token (không giữ token thô), dọn mục hết hạn, **đặt trần kích thước** (ví dụ 2.000 mục).
- Kết quả đệm giờ gồm cả **vai trò sống**: phản hồi `200` của Supabase `/auth/v1/user` có `app_metadata.role`. Vai trò hiệu lực của `Principal` = vai trò sống (nếu có và hợp lệ). Vai trò sống thiếu hoặc không nằm trong `VALID_ROLES` → `403 khong_co_quyen`. Vai trò sống khác vai trò trong token → dùng vai trò sống.
- Phân loại phản hồi Supabase: `401`, `403`, `404` → `AuthError()` (`401 chua_dang_nhap`). `5xx`, hết thời gian, lỗi mạng, JSON hỏng → coi là **Supabase không sẵn sàng**:
  - điểm cuối **ghi hoặc gọi LLM** (`POST .../feedback`, `POST /api/ask`, `POST /api/cases/{id}/ask`, `POST /api/cases/{id}/ai`): `503 xac_thuc_khong_san_sang`;
  - điểm cuối **chỉ đọc** (`GET ...`): bỏ qua kiểm trực tuyến, dùng vai trò trong token, ghi một dòng cảnh báo qua `logging` (không chứa token).
  Cách phân loại điểm cuối: dùng một tham số rõ ràng khi khai báo phụ thuộc (ví dụ `require_role(..., strict=True)` cho điểm cuối ghi), không đoán theo phương thức HTTP trong mã dùng chung.
- Bỏ phụ thuộc `require_online_check` riêng của `feedback` nếu thành thừa; giữ hành vi (không để mất kiểm tra ở `feedback`).
- Biến môi trường `AUTH_ONLINE_TTL` (giây, mặc định 60, kẹp trong 10–300), thêm vào `.env.example` kèm chú thích tiếng Việt.
- Khi `AUTH_MODE=off`: bỏ qua mọi kiểm trực tuyến và danh sách chặn như hiện nay.

### 2.2 Danh sách chặn phiên đã đăng xuất (Q-L2)

- Tạo `app/auth/revocation.py`: lớp `RevocationList` an toàn đa luồng, giữ trong bộ nhớ các khoá đã bị chặn kèm hạn (thời điểm `exp` của token, cộng độ lệch 30 giây). Khoá = `session_id` nếu có, ngược lại SHA-256 của token. Tự dọn mục hết hạn; trần kích thước (ví dụ 10.000), vượt thì bỏ mục cũ nhất.
- `Principal` hoặc luồng xác thực phải cho biết khoá phiên và hạn `exp` (thêm trường tuỳ chọn, giữ tương thích test cũ).
- `current_principal` từ chối bằng `401 chua_dang_nhap` mọi yêu cầu có khoá nằm trong danh sách chặn, **trước** khi gọi kiểm trực tuyến.
- Điểm cuối mới `POST /api/dang-xuat` (hợp đồng v1.3 mục 7): cần vai trò hợp lệ; đưa phiên vào danh sách chặn; trả `{"ok": true}`. Không có thân yêu cầu. Không kiểm trực tuyến riêng (để người dùng vẫn đăng xuất được khi Supabase lỗi).
- Nhật ký truy cập hiện có tự ghi điểm cuối này; không thêm trường.

### 2.3 `GET /api/me`

Trả vai trò hiệu lực (sống) theo 2.1.

## 3. Web (`web/src/`)

### 3.1 Nhãn vai trò (lỗi)

`SidebarNav.tsx` dòng `accountTierLabel` gắn cứng. Sửa theo `vaiTro` từ `useAuth()` (truyền qua props từ nơi dựng): `admin` → **"Quản trị"**, `duoc_si_ls` → **"Dược sĩ lâm sàng"**, demo → **"Demo"**, không có vai trò → "Chưa cấp quyền". Nhãn `accountLabel` mặc định "Tài khoản dược sĩ" khi thiếu email cũng đổi thành "Tài khoản". Thêm test.

### 3.2 Hành vi đăng xuất (Q-L1, Q-L2)

Một hàm `signOut(options?: { scope?: 'local' | 'global'; reason?: SignOutReason })` trong `AuthProvider`:

1. Huỷ mọi yêu cầu API đang chạy (dùng `AbortController` chung do `ApiClient` giữ; thêm phương thức `abortAll()`).
2. Nếu đăng xuất do người dùng chủ động (`reason` là `nguoi_dung`, `khong_hoat_dong`, `het_han_phien`) **và còn token**: gọi `POST /api/dang-xuat` một lần, hạn chờ 3 giây, **lỗi thì bỏ qua**. **Không gọi** khi lý do là `401` (token đã vô hiệu).
3. Xoá trạng thái giao diện ngay (như hiện nay, **không chờ mạng**), xoá bộ nhớ chat và kết quả AI trong bộ nhớ.
4. Gọi `supabase.auth.signOut({ scope })`: mặc định `'local'`.
5. Chuyển về `/dang-nhap` kèm `state.reason`.

Giao diện:
- Menu tài khoản: mục **"Đăng xuất"** (`local`) và mục **"Đăng xuất mọi thiết bị"** (`global`).
- `LoginPage` hiện một dòng thông báo theo `reason`: `het_han_phien` → "Phiên đã hết hạn. Vui lòng đăng nhập lại."; `khong_hoat_dong` → "Bạn đã bị đăng xuất vì không hoạt động."; `nguoi_dung` → không hiện; `da_dang_xuat_noi_khac` → "Bạn đã đăng xuất ở một thẻ hoặc thiết bị khác."

### 3.3 Hết hạn phiên ở phía web (Q-L6)

- Hằng số ở một chỗ (`web/src/features/auth/sessionPolicy.ts`): `IDLE_LIMIT_MS = 30 * 60_000`, `MAX_SESSION_MS = 12 * 60 * 60_000`.
- Đo "không hoạt động" bằng sự kiện người dùng (`pointerdown`, `keydown`, `wheel`, `touchstart`), **giới hạn tần suất** ghi nhận (ví dụ 1 lần mỗi 5 giây). Hết hạn mức → `signOut({ reason: 'khong_hoat_dong' })`.
- Mốc 12 giờ tính từ lúc đăng nhập (lưu mốc trong bộ nhớ và `sessionStorage` dưới khoá riêng; không lưu token). Hết → `signOut({ reason: 'het_han_phien' })`.
- Chỉ chạy khi đã đăng nhập thật (không chạy ở chế độ demo). Dọn bộ hẹn giờ và sự kiện khi đăng xuất.
- Đồng hồ **tiêm được** để test dùng đồng hồ giả.

### 3.4 Nhiều tab (Q-L7)

Khi `onAuthStateChange` báo `SIGNED_OUT` mà tab này **không** tự khởi xướng đăng xuất: dọn phiên và về `/dang-nhap` với `reason = 'da_dang_xuat_noi_khac'`. Không gọi `POST /api/dang-xuat` trong trường hợp này.

## 4. Kiểm thử bắt buộc

Theo mục 11.3 của plan 1.5, tối thiểu:

**Backend** (`tests/auth/`, `tests/api/`; bộ kiểm token và máy chủ Supabase giả, **không gọi mạng**):
1. Đăng xuất (`POST /api/dang-xuat`) rồi dùng lại cùng token → `401`.
2. Danh sách chặn tự dọn mục hết hạn; trần kích thước hoạt động; khoá `session_id` và khoá băm đều chạy.
3. Kiểm trực tuyến áp cho điểm cuối đọc (ví dụ `GET /api/cases`): Supabase `401`/`403`/`404` → `401`.
4. Supabase `5xx` hoặc hết thời gian: `GET /api/cases` vẫn `200` (có cảnh báo), `POST /api/ask` và `POST .../feedback` → `503`.
5. Vai trò sống `duoc_si_ls` trong khi token ghi `admin` → điểm cuối chỉ cho admin (tuyến thử) trả `403`; `GET /api/me` trả vai trò sống.
6. Vai trò sống thiếu hoặc lạ → `403`.
7. Bộ đệm: hai yêu cầu liên tiếp chỉ gọi Supabase một lần; sau khi hết TTL gọi lại; `AUTH_ONLINE_TTL` được kẹp trong 10–300.
8. Không có token trong nhật ký truy cập, thông báo lỗi, cảnh báo `logging`.
9. `GET /api/health` không kiểm trực tuyến; `AUTH_MODE=off` bỏ qua cả kiểm trực tuyến và danh sách chặn.

**Web** (Vitest, đồng hồ giả, không gọi mạng):
1. Nhãn vai trò đúng bốn trường hợp (mục 3.1).
2. Đăng xuất chủ động gọi `POST /api/dang-xuat` **đúng một lần**, rồi `signOut` Supabase với `scope` đúng; thứ tự: backend trước, Supabase sau; lỗi backend không chặn việc đăng xuất.
3. Đăng xuất do `401`: **không** gọi `POST /api/dang-xuat`.
4. Hủy yêu cầu đang chạy; xoá bộ nhớ chat; trạng thái giao diện xoá ngay cả khi mạng treo.
5. Nhàn rỗi 30 phút → tự đăng xuất với `reason = 'khong_hoat_dong'`; có hoạt động thì đặt lại; sự kiện bị giới hạn tần suất.
6. Quá 12 giờ → tự đăng xuất; không chạy ở chế độ demo; dọn hẹn giờ khi đăng xuất.
7. `SIGNED_OUT` từ tab khác → dọn phiên, `reason = 'da_dang_xuat_noi_khac'`, không gọi backend.
8. `LoginPage` hiện đúng dòng thông báo theo từng `reason`.
9. Menu tài khoản có hai mục; "Đăng xuất mọi thiết bị" dùng `scope: 'global'`.

Mọi test cũ phải qua; không sửa kỳ vọng, không `skip`.

## 5. Phạm vi file

**Được tạo hoặc sửa:** `app/auth/**`, `app/api/**`, `app/config/settings.py` (chỉ để đọc `AUTH_ONLINE_TTL`), `tests/auth/**`, `tests/api/**`, `.env.example`, `web/src/**` (chủ yếu `features/auth/`, `features/sidebar/`, `app/WorkspacePage.tsx`, `api/client.ts`, `state/useChat.ts`, `__tests__/`).
**Cấm đụng:** `app/db/`, `db/`, `app/kb/`, `app/orchestration/`, `data/`, `plan/`, `.env`, `Dockerfile`, `docker-compose.yml`, `Caddyfile`, `web/package.json` (không thêm gói), `pyproject.toml`.

## 6. Nghiệm thu

```bash
uv run ruff check app/auth app/api tests/auth tests/api
uv run ruff format --check app/auth app/api tests/auth tests/api
uv run pytest -q -p no:cacheprovider --ignore=tests/architecture/.tmp --ignore=tests/db/.tmp --ignore=tests/kb/.tmp
```

Rồi trong `web/`:

```bash
npm run lint
npx tsc -b
npx vitest run
npm run build
```

Kết quả: toàn kho Python **không có test trượt** (trước đó 784 qua); web 0 cảnh báo lint, build đạt, mọi test qua (trước đó 193). Rồi chạy `uvicorn` thật ở cổng 8032 với `AUTH_MODE=required` và dán kết quả `curl`: `/api/health` 200; `/api/cases` không token 401; `POST /api/dang-xuat` không token 401. Dừng `uvicorn` và xoá tệp nhật ký thử sau khi xong.

## 7. Cấm làm

Không đọc hay in `.env`. Không gọi Supabase thật. Không tạo khoá hay người dùng. Không làm giới hạn tốc độ. Không thêm thư viện. Không commit, không push. Báo cáo theo mẫu `AGENTS.md`, ghi rõ mọi chỗ lệch brief.
