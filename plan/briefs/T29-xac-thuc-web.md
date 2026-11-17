# T29 – Web: phiên có token và vai trò, gắn `Authorization`, tự gia hạn, trang không có quyền

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort high; người dùng chốt 17/11/2026) · **Ngày:** 17/11/2026
**Đọc trước, theo thứ tự:** `AGENTS.md`; `plan/plan-1.5-bao-mat-xac-thuc-phan-quyen.md` (đọc hết, nhất là mục 4 và 7.2); `plan/api-hop-dong-v1.3-xac-thuc.md`; `web/src/features/auth/` (`authClient.ts`, `AuthProvider.tsx`, `useAuth.ts`, `ProtectedRoute.tsx`, `LoginPage.tsx`), `web/src/lib/routeGuard.ts`, `web/src/lib/demoSession.ts`, `web/src/api/client.ts`, `web/src/api/index.ts`, `web/src/api/mock.ts`.
**Chạy song song với** T28 (backend). T28 sửa `app/`, `tests/`; bạn **không đụng** chúng.

## 1. Bối cảnh

Web đã đăng nhập bằng Supabase (`signInWithPassword`), nhưng phiên chỉ giữ `email`, API client không gửi token, và có chế độ demo. Backend (T28) sắp đòi `Authorization: Bearer <access token>` ở mọi điểm cuối trừ `/api/health`. Hợp đồng ở `plan/api-hop-dong-v1.3-xac-thuc.md`. Refresh token do `supabase-js` giữ và tự đổi; **web không tự lưu refresh token và không gửi nó cho backend**.

## 2. Việc phải làm

### 2.1 Phiên có token và vai trò (`authClient.ts`, `AuthProvider.tsx`, `useAuth.ts`)

- Mở rộng `AuthSession`: thêm `vaiTro` (`'duoc_si_ls' | 'admin' | null`, lấy từ `session.user.app_metadata.role`; **không bao giờ đọc `user_metadata`**; giá trị lạ → `null`) và `phienId` (từ claim `session_id` của token nếu đọc được; giải mã phần giữa của JWT chỉ để đọc, không kiểm chữ ký ở web, và phải chịu được token hỏng mà không ném lỗi).
- `AuthClient` thêm:
  - `getAccessToken(): Promise<string | null>`: dùng `client.auth.getSession()` (cái này tự gia hạn khi token sắp hết hạn).
  - `refreshSession(): Promise<AuthSession | null>`: dùng `client.auth.refreshSession()`; trả `null` khi thất bại.
- **Dùng chung một lần gia hạn** khi nhiều lời gọi cùng cần (single-flight): lời gọi thứ hai trở đi chờ chung một Promise đang chạy.
- Khởi tạo `createClient` với `auth: { persistSession: true, autoRefreshToken: true }` (nếu chưa tường minh).
- `useAuth` bổ sung: `vaiTro`, `phienId`, `getAccessToken`, `refreshSession`. Giữ nguyên các trường cũ để không vỡ chỗ khác.
- Token **không** được vào URL, `console`, thông báo lỗi, hay `localStorage` do mã của bạn tự ghi thêm. (Phần `supabase-js` tự lưu thì giữ mặc định.)

### 2.2 Gắn token vào mọi lời gọi API (`web/src/api/client.ts`)

- `ApiClient` nhận một bộ cung cấp xác thực tiêm được (ví dụ `AuthHooks` có `getAccessToken`, `refreshSession`, `onUnauthorized`, `onForbidden`). Giữ cách dựng cũ `new ApiClient('/api')` chạy được với test cũ (không có bộ cung cấp thì không gắn tiêu đề).
- Mọi yêu cầu gắn `Authorization: Bearer <token>` nếu có token (kể cả `GET /api/health`: không hại, nhưng không bắt buộc).
- Khi nhận `401`:
  1. Gọi `refreshSession()` đúng một lần (dùng chung nếu nhiều yêu cầu cùng `401`).
  2. Có token mới → gửi lại **đúng một lần** với token mới.
  3. Gia hạn thất bại, hoặc gửi lại vẫn `401` → gọi `onUnauthorized()` (đăng xuất và đưa về `/dang-nhap`), ném `ApiError` với `ma` từ thân lỗi (`chua_dang_nhap` / `phien_het_han`). **Không lặp vô hạn.**
- Khi nhận `403 khong_co_quyen`: ném `ApiError` giữ nguyên `ma`, gọi `onForbidden()` nếu có; **không đăng xuất**.
- Giữ nguyên hành vi `AbortError`, định dạng `ApiError`, `getAi` trả `null` ở `404 chua_chay`.
- Thêm `getMe(): Promise<{ id: string; email: string | null; vai_tro: string; phien_id: string | null }>` gọi `GET /api/me` (kiểu thêm vào `types.ts`). Sau khi đăng nhập, web gọi `getMe()` **một lần** để xác nhận vai trò từ máy chủ; nếu lệch với vai trò đọc từ token thì **tin máy chủ**; nếu `403` thì chuyển sang trang không có quyền.
- `web/src/api/index.ts`: dựng `apiClient` mặc định, nối với `defaultAuthClient`, không phá `VITE_USE_MOCK=1`. `MockClient` không cần token.

### 2.3 Tuyến được bảo vệ và trang "Không có quyền"

- `evaluateProtectedRoute` (và `ProtectedRoute`): thêm nhánh **đã đăng nhập nhưng không có vai trò hợp lệ** → trang `/khong-co-quyen` (hoặc hiển thị ngay trong khung, miễn có nút "Đăng xuất"). Trang này tiếng Việt, ngắn: nói tài khoản chưa được cấp quyền và hướng dẫn liên hệ quản trị, **không lộ chi tiết kỹ thuật**. Có nút "Đăng xuất" và nút "Thử lại" (gọi lại `getMe()`).
- Giữ tính chất cũ: tải thẳng `/app/y-lenh/DEMO-02` khi đã có phiên không bị đá về đăng nhập; đường dẫn quay lại chỉ cho `/app*` (không mở chuyển hướng ngoài).
- Khi `onUnauthorized` chạy: xoá trạng thái phiên, về `/dang-nhap` kèm `state.from`.

### 2.4 Chế độ demo (Q-B8)

- Nút "Vào bản demo" và `enterDemoMode` **chỉ hoạt động khi** `import.meta.env.DEV` là đúng, hoặc `VITE_USE_MOCK === '1'`, hoặc `VITE_ENABLE_DEMO === '1'`. Ở bản dựng production mặc định: không hiện nút; `loadDemoMode` bỏ qua giá trị cũ còn trong bộ nhớ trình duyệt (xoá nó đi).
- Ở chế độ demo hợp lệ mà không có `VITE_USE_MOCK`, các lời gọi API vẫn đi không token (chạy với backend `AUTH_MODE=off`); không phải sửa gì thêm.
- Thêm `VITE_ENABLE_DEMO` vào `web/.env.example` (nếu có) hoặc tài liệu cạnh đó; giá trị mặc định tắt.

### 2.5 Trợ lý AI (chat) – phân biệt tài khoản

- Lịch sử hội thoại do backend trả theo từng tài khoản (T28). Web **không** đệm lịch sử chat trong `localStorage` dưới khoá dùng chung giữa các tài khoản. Nếu hiện có đệm như vậy: khoá đệm phải kèm `id` người dùng, và **xoá khi đăng xuất**. Kiểm `web/src` rồi ghi kết quả (có hay không) vào báo cáo.
- Sau đăng xuất rồi đăng nhập tài khoản khác: trợ lý không được hiện lịch sử của tài khoản trước (xoá trạng thái trong bộ nhớ khi đăng xuất).

## 3. Kiểm thử bắt buộc (Vitest)

Tuân theo mục 7.2 của plan 1.5. Dùng máy khách API giả và đồng hồ giả, **không gọi mạng**:

1. Mọi yêu cầu gửi `Authorization: Bearer <token>` đúng.
2. `401` → gia hạn đúng 1 lần → gửi lại đúng 1 lần với token mới → thành công.
3. Gia hạn thất bại → `onUnauthorized` được gọi, phiên bị xoá.
4. Gửi lại vẫn `401` → không lặp; `onUnauthorized` được gọi.
5. Nhiều yêu cầu `401` cùng lúc → chỉ **một** lần gia hạn.
6. `403 khong_co_quyen` → `ApiError` giữ mã, `onForbidden` gọi, **không** `onUnauthorized`.
7. Đăng xuất xoá token và không còn gắn tiêu đề; lịch sử chat trong bộ nhớ bị xoá.
8. Token không có trong URL, trong `ApiError.message`, và không bị `console.*` in ra (spy kiểm).
9. Vai trò đọc từ `app_metadata.role`; có `user_metadata.role = 'admin'` mà `app_metadata` trống → `vaiTro` là `null`.
10. Giải mã `session_id` từ token thử; token hỏng không ném lỗi.
11. `evaluateProtectedRoute`: đã đăng nhập nhưng không có vai trò → trang không có quyền; có vai trò → `allow`; chưa đăng nhập → chuyển hướng như cũ.
12. Demo mode: bản dựng "production" giả lập (`DEV=false`, không cờ) → không có nút, và giá trị cũ trong bộ nhớ không bật được demo.

Mọi test cũ phải qua; không sửa kỳ vọng, không `skip`.

## 4. Phạm vi file

**Được tạo hoặc sửa:** `web/src/**` (chủ yếu `features/auth/`, `api/`, `lib/routeGuard.ts`, `lib/demoSession.ts`, `app/`, `__tests__/`), `web/.env.example` nếu có.
**Cấm đụng:** `app/`, `tests/`, `db/`, `data/`, `plan/`, `.env*` thật, `Dockerfile`, `docker-compose.yml`, `Caddyfile`, `vercel.json`, `web/package.json` (không thêm gói; `@supabase/supabase-js` đã có). Nếu thấy phải thêm gói thì dừng và ghi vào báo cáo.

## 5. Nghiệm thu

Chạy trong `web/`:

```bash
npm run lint
npx tsc -b
npx vitest run
npm run build
```

Kết quả phải: 0 cảnh báo lint, build đạt, **mọi test qua** (trước đó 153 test, 22 tệp), cộng test mới. Báo số liệu thật. Không có `dangerouslySetInnerHTML` mới. Không chạy thử với Supabase thật.

## 6. Cấm làm

Không đọc hay in khoá hay `.env`. Không đổi mật khẩu hay tạo người dùng. Không gửi refresh token đến backend. Không lưu token ở nơi mới. Không làm giới hạn tốc độ. Không commit, không push. Báo cáo theo mẫu trong `AGENTS.md`, nêu rõ tệp đã tạo, đã sửa, kết quả từng lệnh nghiệm thu, và mọi chỗ lệch brief.
