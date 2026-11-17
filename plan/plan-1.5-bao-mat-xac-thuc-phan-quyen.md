# Plan 1.5 – Bảo mật: xác thực, phân quyền, phiên và hội thoại

Phiên bản 1 · 17/11/2026 · Người viết: Claude (theo thảo luận với chủ kho)

Plan này gom mọi quyết định bảo mật của hệ thống đã đưa lên mạng (web trên Vercel, API trên AWS EC2, tài khoản trên Supabase). Nó bổ sung cho plan 1.1 (kiến trúc) và hợp đồng API; phần thay đổi tên trường nằm ở `plan/api-hop-dong-v1.3-xac-thuc.md`. Brief giao việc: `plan/briefs/T28-xac-thuc-backend.md` và `plan/briefs/T29-xac-thuc-web.md`.

## 1. Vì sao phải làm

Hiện trạng kiểm ngày 17/11/2026:

| Phần | Hiện trạng |
| :--- | :--- |
| Đăng nhập trên web | Có. `web/src/features/auth/` dùng `signInWithPassword` của Supabase, có chế độ demo |
| Vai trò | Chưa có. Phiên chỉ giữ `email` |
| Web gửi token lên API | Chưa. `web/src/api/client.ts` không gắn `Authorization` |
| Backend kiểm token | Chưa. `app/api/` không xác thực, không kiểm vai trò |
| Hội thoại và phản hồi | Ghi vào `data/runtime/hoi_thoai.jsonl` và `phan_hoi.jsonl` **không có chủ sở hữu**. Ai gọi `/api/conversations` cũng đọc được hết, gọi `/clear` xoá được của người khác |
| Bảng người dùng | Không có; không cần, vì danh tính nằm ở Supabase Auth |

Hậu quả nếu để nguyên: địa chỉ `https://vinmec-pharm.duckdns.org/api/...` công khai, ai biết cũng (1) đọc ca bệnh giả lập, (2) gọi LLM bằng khoá DeepSeek / OpenRouter của dự án, tốn tiền, (3) ghi phản hồi rác, (4) đọc hoặc xoá lịch sử chat của dược sĩ. Đăng nhập ở giao diện chỉ khoá cửa trước, API là cửa sau đang mở.

Dữ liệu hiện là giả lập nên chưa vi phạm gì, nhưng **bắt buộc xong trước khi mời bất kỳ ai ngoài nhóm dùng**, và trước khi có dữ liệu thật (Nghị định 13/2023/NĐ-CP coi dữ liệu sức khoẻ là dữ liệu nhạy cảm).

## 2. Các quyết định đã chốt

| Mã | Quyết định | Lý do |
| :-: | :--- | :--- |
| Q-B1 | Giữ **Supabase Auth** làm nơi cấp danh tính. Không tự viết hệ thống đăng nhập, không tự sinh token | Tự làm token dễ sai; Supabase đã cấp sẵn đủ cơ chế bên dưới |
| Q-B2 | **Access token (JWT) ngắn hạn**, mặc định 1 giờ. Backend kiểm bằng khoá công khai JWKS của Supabase, chạy cục bộ | Nhanh, không gọi Supabase mỗi yêu cầu |
| Q-B3 | **Refresh token dài hạn, xoay vòng** (dùng một lần rồi đổi). Do `supabase-js` giữ và tự đổi trước khi access token hết hạn. Backend **không** nhận refresh token | Refresh token chỉ cần đi giữa trình duyệt và Supabase; càng ít nơi giữ càng an toàn |
| Q-B4 | "Mã định danh" mà chủ kho nhớ từ dự án thương mại điện tử có hai nghĩa; hệ thống này dùng cả hai: (a) **mã phiên** `session_id` có sẵn trong JWT và cặp refresh token tương ứng, để biết đang là phiên đăng nhập nào; (b) **mã chủ sở hữu** `sub` (id người dùng) lưu cùng mọi hội thoại và phản hồi, để biết của ai | Cho phép phân biệt tài khoản với phiên khi chat, và chặn đọc chéo |
| Q-B5 | Kiểm thu hồi trực tuyến (gọi Supabase `/auth/v1/user` với token) **chỉ cho thao tác ghi phản hồi và thao tác admin**, có đệm 60 giây. Không gọi mọi yêu cầu | Bắt được tài khoản vừa bị khoá hoặc đăng xuất khỏi mọi thiết bị, mà không làm chậm và không phụ thuộc Supabase ở mọi nơi |
| Q-B6 | **Hai vai trò**: `duoc_si_ls` (dược sĩ lâm sàng) và `admin`. Lưu ở `app_metadata.role` của người dùng Supabase | `app_metadata` chỉ sửa được từ phía máy chủ. `user_metadata` do người dùng tự sửa được nên **tuyệt đối không dùng** để cấp quyền |
| Q-B7 | **Mặc định từ chối** (fail closed): thiếu token, token sai, thiếu vai trò, vai trò lạ, không lấy được JWKS → không cho qua | Lỗi cấu hình không được mở cửa |
| Q-B8 | Chế độ demo (vào không cần tài khoản) **chỉ tồn tại ở bản phát triển hoặc khi dùng dữ liệu giả `VITE_USE_MOCK=1`**; bản production (Vercel) không có nút này | Khi API đã đòi token, demo gọi API thật sẽ không còn nghĩa; để lại là cửa vào giả |
| Q-B9 | **Giới hạn tốc độ: tạm hoãn.** Chỉ ghi thiết kế ở mục 8 | Người dùng chốt hoãn 17/11/2026 |
| Q-B10 | Tắt đăng ký tự do ở Supabase (*Allow new users to sign up* = tắt). Tài khoản do admin tạo trong bảng điều khiển | Nếu ai cũng tự tạo được tài khoản thì xác thực mất tác dụng; vai trò thiếu vẫn bị chặn nhưng không nên để ngỏ |

## 3. Phân quyền

### 3.1 Vai trò

| Vai trò | Mã trong token | Ai |
| :--- | :--- | :--- |
| Dược sĩ lâm sàng | `duoc_si_ls` | Người dùng chính của hệ thống |
| Quản trị | `admin` | Chủ kho và người được chủ kho cấp. Có mọi quyền của dược sĩ, cộng quyền quản trị |

Quyền sẽ mở rộng về sau (ví dụ `quan_ly_khoa`, `chi_xem`). Mã vai trò là chuỗi, danh sách hợp lệ nằm ở **một chỗ** trong code (`app/auth/roles.py`) để thêm không phải sửa nhiều nơi.

### 3.2 Bảng quyền theo điểm cuối

`D` = `duoc_si_ls`, `A` = `admin`. "Của mình" = chỉ bản ghi do chính tài khoản đó tạo ra.

| Điểm cuối | Công khai | D | A | Ghi chú |
| :--- | :-: | :-: | :-: | :--- |
| `GET /api/health` | có | có | có | Chỉ trả `ok`, `che_do`, `xac_thuc` (không lộ dữ liệu); Caddy và giám sát gọi được |
| `GET /api/me` (mới) | | có | có | Trả `id`, `email`, `vai_tro`, `phien_id`; web dùng để xác nhận vai trò từ máy chủ |
| `GET /api/cases`, `/cases/{id}`, `/records/...` | | có | có | Danh sách ca dùng chung cho mọi dược sĩ |
| `POST /api/cases/{id}/feedback` | | có | có | Ghi kèm người gửi. Kiểm thu hồi trực tuyến (Q-B5) |
| `POST /api/cases/{id}/ai`, `GET .../ai`, `GET .../sources/...` | | có | có | Gọi LLM, tốn tiền |
| `POST /api/ask`, `POST /api/cases/{id}/ask` | | có | có | Gọi LLM, tốn tiền; ghi hội thoại kèm chủ sở hữu |
| `GET /api/conversations` | | của mình | của mình | Admin cũng chỉ thấy của mình ở bản này |
| `POST /api/conversations/{id}/clear` | | của mình | của mình | Chỉ xoá lượt của chính tài khoản |
| Điểm cuối quản trị (chưa có, `require_role("admin")` đã sẵn) | | cấm | có | Ví dụ xem phản hồi toàn hệ thống; làm sau |

Vai trò không có trong danh sách, hoặc không có vai trò: `403`.

### 3.3 Dữ liệu cũ

Các dòng đã ghi trong `hoi_thoai.jsonl` và `phan_hoi.jsonl` trước khi có xác thực **không có chủ sở hữu**. Quy ước: dược sĩ không thấy dòng không chủ; chỉ `admin` thấy. Không tự gán chủ cho dòng cũ.

## 4. Phiên, token và hội thoại

### 4.1 Luồng

```
Trình duyệt ──đăng nhập (email, mật khẩu)──▶ Supabase Auth
     ▲                                          │
     │◀── access token (JWT, ~1 giờ) + refresh token ──┘
     │
     ├─ gọi API: Authorization: Bearer <access token>
     │        Vercel viết lại /api/* ─▶ Caddy ─▶ FastAPI
     │        FastAPI: kiểm chữ ký bằng JWKS, kiểm hạn, iss, aud, vai trò
     │
     └─ sắp hết hạn: supabase-js tự dùng refresh token đổi cặp mới (xoay vòng)
```

Nếu API trả `401` vì token hết hạn giữa chừng: web gọi `refreshSession()` **một lần** (các yêu cầu đồng thời dùng chung một lần đổi), gắn token mới và gửi lại đúng một lần. Đổi thất bại hoặc vẫn `401` → đăng xuất và về `/dang-nhap`.

### 4.2 Mã phiên và mã chủ sở hữu

Từ JWT, backend lấy:

| Trường JWT | Tên trong hệ thống | Dùng để |
| :--- | :--- | :--- |
| `sub` | `nguoi_dung_id` | Chủ sở hữu hội thoại, phản hồi. Kiểm quyền "của mình" |
| `session_id` | `phien_id` | Phân biệt các phiên đăng nhập của cùng một tài khoản (hai thiết bị, hai tab sau khi đăng nhập lại). Ghi vào nhật ký để truy vết |
| `app_metadata.role` | `vai_tro` | Kiểm quyền |
| `email` | `email` | Hiển thị; **không** dùng để kiểm quyền |

Quy ước ghi: mỗi dòng `hoi_thoai.jsonl` và `phan_hoi.jsonl` thêm `nguoi_dung_id`, `phien_id`. Hội thoại vẫn theo phạm vi `ca_id` như hợp đồng v1.2, nhưng mỗi tài khoản có lịch sử riêng trong cùng một ca. Khoá của một cuộc hội thoại là cặp (`nguoi_dung_id`, `ca_id`).

Ghi chú về phản hồi: trạng thái "Đã phản hồi" trên hàng đợi hiện tính chung cho mọi người; bản này **chỉ ghi thêm người gửi**, chưa tách trạng thái theo người. Tách theo người sẽ làm cùng lúc với bước chuyển dữ liệu lên PostgreSQL.

### 4.3 Việc Supabase đã lo và việc chủ kho phải bật trong bảng điều khiển

Trong Supabase → Authentication:

1. **Sign In / Providers → Allow new users to sign up: tắt** (Q-B10).
2. **Sessions**: bật *Detect and revoke potentially compromised refresh tokens*; để *Refresh token reuse interval* mặc định (10 giây). Thời hạn access token (*JWT expiry*): giữ 3600 giây; có thể giảm xuống 1800.
3. **URL Configuration**: Site URL = `https://vinmec-pharm-web.vercel.app`; thêm cùng URL vào Redirect URLs.
4. Gói trả phí mới có *time-box sessions* và *inactivity timeout*; gói miễn phí không có. Ghi nhận, làm khi nâng gói.

### 4.4 Loại khoá ký JWT

Dự án Supabase có thể dùng **khoá bất đối xứng** (ES256 / RS256, kiểm bằng JWKS) hoặc **bí mật dùng chung cũ** (HS256). Bản này làm theo thứ tự: JWKS trước; chỉ nhận HS256 khi đặt `SUPABASE_JWT_SECRET` (đường lùi). Chống tấn công nhầm thuật toán: **chỉ nhận danh sách thuật toán định sẵn**, không đọc thuật toán từ tiêu đề token để quyết định cách kiểm; từ chối `none`.

## 5. Cấu hình

Biến môi trường mới cho backend (đưa vào `.env.example` với giá trị giữ chỗ; **không đọc, không in giá trị thật trong `.env`**):

| Biến | Ý nghĩa | Mặc định |
| :--- | :--- | :--- |
| `SUPABASE_URL` | Gốc dự án; từ đó suy ra `iss` (`.../auth/v1`) và địa chỉ JWKS | đã có sẵn trong `.env` |
| `SUPABASE_ANON_KEY` | Dùng cho gọi kiểm thu hồi trực tuyến | đã có sẵn |
| `SUPABASE_JWT_SECRET` | Chỉ khi dự án còn dùng HS256 | trống |
| `AUTH_MODE` | `required` hoặc `off` | `required` (từ chối khi thiếu cấu hình) |
| `CORS_ORIGINS` | Danh sách nguồn được phép, phân tách dấu phẩy | `http://localhost:5173,http://127.0.0.1:5173` |

`AUTH_MODE=off` chỉ dành cho phát triển cục bộ và test cũ; khi bật, API ghi cảnh báo lúc khởi động và `GET /api/health` trả `"xac_thuc": "off"` để lộ ra ngay. **Bản triển khai trên EC2 không được đặt `off`.**

Biến cho web (Vercel, công khai): `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` đã có; thêm `VITE_ENABLE_DEMO` (mặc định tắt ở bản dựng production).

## 6. Ảnh hưởng đến chức năng

| Chức năng | Thay đổi | Task |
| :--- | :--- | :-: |
| Đăng nhập của dược sĩ | Phiên giữ thêm `accessToken`, `vai_tro`, `phien_id`; có bộ lấy token; tự gia hạn; hết hạn thì về đăng nhập; không có vai trò → trang "Không có quyền" | T29 |
| Mọi lời gọi API của web | Gắn `Authorization: Bearer`; xử lý `401` (gia hạn rồi gửi lại một lần) và `403` (thông báo không đủ quyền) | T29 |
| Chế độ demo | Ẩn ở bản production | T29 |
| Hàng đợi, chi tiết ca, bản ghi | Phải có token hợp lệ và vai trò hợp lệ | T28 |
| Bước AI nền, mở đoạn nguồn | Như trên; ghi `nguoi_dung_id` khi cần truy vết | T28 |
| **Trợ lý AI (chat)** | Mỗi lượt hỏi ghi `nguoi_dung_id` + `phien_id`; xem và xoá lịch sử chỉ của mình; đăng nhập tài khoản khác thấy lịch sử khác | T28 + T29 |
| Phản hồi của dược sĩ | Ghi kèm người gửi; kiểm thu hồi trực tuyến trước khi ghi | T28 |
| Điểm cuối `/api/me` | Mới | T28 |
| CORS | Thêm `Authorization` vào tiêu đề cho phép; nguồn lấy từ biến môi trường | T28 |
| Triển khai (Docker, Caddy, Vercel) | Truyền biến mới; Caddy thêm tiêu đề bảo mật; chạy thử đầu cuối | Đợt 2 |

## 7. Kiểm thử

### 7.1 Kiểm thử JWT ở backend (không gọi mạng)

Test tự sinh một cặp khoá, dựng JWKS giả và ký token thử. Phải có đủ:

| # | Tình huống | Kỳ vọng |
| :-: | :--- | :-: |
| 1 | Token hợp lệ, vai trò `duoc_si_ls` | 200 |
| 2 | Token hợp lệ, vai trò `admin` | 200 |
| 3 | Không có tiêu đề `Authorization` | 401 `chua_dang_nhap` |
| 4 | Tiêu đề sai dạng (`Basic ...`, `Bearer` rỗng) | 401 |
| 5 | Token hết hạn | 401 `phien_het_han` |
| 6 | Chữ ký sai (ký bằng khoá khác) | 401 |
| 7 | `iss` sai | 401 |
| 8 | `aud` khác `authenticated` | 401 |
| 9 | `alg=none` | 401 |
| 10 | Nhầm thuật toán: HS256 ký bằng khoá công khai làm bí mật | 401 |
| 11 | Token là khoá ẩn danh (`is_anonymous: true`) | 403 |
| 12 | Không có `app_metadata.role` | 403 `khong_co_quyen` |
| 13 | Vai trò chỉ có trong `user_metadata` | 403 |
| 14 | Vai trò lạ (`superuser`) | 403 |
| 15 | `kid` lạ → làm mới JWKS một lần (có giới hạn tần suất); vẫn lạ → 401 | |
| 16 | Không lấy được JWKS | 503 `xac_thuc_khong_san_sang`, không cho qua |
| 17 | `GET /api/health` không cần token | 200 |
| 18 | Log và lỗi không chứa token | |
| 19 | Kiểm thu hồi trực tuyến: Supabase trả 401 → ghi phản hồi bị từ chối; đệm 60 giây; Supabase lỗi mạng → từ chối ghi (fail closed) | |

### 7.2 Kiểm thử phiên và refresh token ở web

Dùng máy khách API giả và đồng hồ giả:

1. Mọi yêu cầu gửi `Authorization: Bearer <token hiện tại>`.
2. API trả `401` → gọi gia hạn đúng một lần → gửi lại đúng một lần với token mới → thành công.
3. Gia hạn thất bại → đăng xuất, về `/dang-nhap`, xoá trạng thái phiên.
4. Gửi lại vẫn `401` → không lặp vô hạn; đăng xuất.
5. Nhiều yêu cầu `401` cùng lúc → chỉ **một** lần gia hạn (dùng chung).
6. `403` → thông báo "không đủ quyền", **không** đăng xuất.
7. Đăng xuất xoá token khỏi bộ nhớ; không còn gửi `Authorization`.
8. Token không xuất hiện trong URL, `console`, thông báo lỗi.

### 7.3 Kiểm thử quyền và sở hữu

1. Dược sĩ A hỏi trợ lý → dòng log có `nguoi_dung_id` của A và `phien_id`.
2. Dược sĩ B gọi `GET /api/conversations` → không thấy lượt của A.
3. B gọi `POST /api/conversations/{ca}/clear` → lượt của A còn nguyên.
4. `admin` xem hội thoại → chỉ thấy của mình, và thấy các dòng cũ không chủ.
5. Dược sĩ không thấy dòng cũ không chủ.
6. Phản hồi ghi kèm `nguoi_dung_id`, `phien_id`.
7. Đọc được tệp cũ không có hai trường mới (tương thích ngược).
8. Điểm cuối `require_role("admin")` thử bằng một tuyến chỉ có trong test: D bị `403`, A được `200`.

### 7.4 Kiểm thử đầu cuối (Claude và chủ kho, sau triển khai)

1. Gọi `https://vinmec-pharm.duckdns.org/api/cases` **không token** → `401` (Claude chạy bằng `curl`).
2. Đăng nhập bằng tài khoản admin trên `vinmec-pharm-web.vercel.app` → hàng đợi hiện đủ ca (chủ kho làm).
3. Đăng nhập tài khoản chưa gán vai trò → thấy trang "Không có quyền" (chủ kho làm).
4. Chờ token hết hạn hoặc ép hết hạn → thao tác tiếp theo vẫn chạy nhờ gia hạn (chủ kho làm).
5. Mở tab ẩn danh, thử gọi API bằng token cũ đã đăng xuất → bị chặn ở thao tác ghi (Q-B5).

## 8. Hoãn lại: giới hạn tốc độ

**Trạng thái: tạm hoãn** (người dùng chốt 17/11/2026). Không có trong T28 và T29.

Thiết kế dự kiến để khỏi nghĩ lại:

- Đặt **theo `nguoi_dung_id`**, không theo địa chỉ IP, vì sau Vercel và Caddy địa chỉ IP thật bị che.
- Chỉ áp cho điểm cuối tốn tiền: `POST /api/ask`, `POST /api/cases/{id}/ask`, `POST /api/cases/{id}/ai` (ví dụ 20 lượt hỏi / phút, 5 lần chạy AI / 10 phút / người).
- Thêm **trần chi tiêu ngày** cho khoá LLM (đếm token mỗi ngày; vượt thì từ chối), vì giới hạn tốc độ đơn thuần không ngăn được một tài khoản bị chiếm.
- Cài bằng phần mềm trung gian trong FastAPI (bộ đếm trong bộ nhớ đủ cho một tiến trình `uvicorn`); chuyển sang Redis khi chạy nhiều tiến trình.
- Trả `429` kèm `Retry-After`; web hiện thông báo thân thiện.

Khi nào làm lại: trước khi mời người dùng ngoài nhóm, hoặc khi thấy chi phí LLM bất thường.

## 9. Các việc khác để sau (không thuộc T28, T29)

| Việc | Khi nào |
| :--- | :--- |
| Tiêu đề bảo mật ở Caddy (`Strict-Transport-Security`, `X-Content-Type-Options`, `Referrer-Policy`, `Content-Security-Policy`) | Đợt 2, cùng triển khai |
| Nhật ký truy cập có cấu trúc (ai, vai trò, đường dẫn, kết quả; không token) | Đợt 2 |
| Giao diện quản trị người dùng (tạo, khoá, gán vai trò) | Sau demo; tạm làm trong bảng điều khiển Supabase |
| Xác thực hai bước (MFA) cho `admin` | Trước khi có dữ liệu thật |
| Tách trạng thái "Đã phản hồi" theo người | Cùng lúc chuyển dữ liệu lên PostgreSQL |
| Gói Supabase Pro (sao lưu, không tự tạm dừng, time-box session) | Trước khi có người dùng thật |
| Soát pháp lý và IT về nơi lưu dữ liệu (Nghị định 13/2023/NĐ-CP) | Trước khi có dữ liệu thật |
| Rà `.env` và khoá trên EC2 (quyền tệp `600`); xoay vòng khoá nếu nghi lộ | Đợt 2 |

## 10. Phân đợt và theo dõi

### 10.1 Các đợt

| Đợt | Nội dung | Ai |
| :-: | :--- | :--- |
| 0 | Tạo tài khoản admin trong Supabase; gán `app_metadata.role`; tắt đăng ký; thêm URL Vercel | Chủ kho (Claude cung cấp lệnh SQL) |
| 1 | T28 backend xác thực + T29 web xác thực, chạy **song song** (hai tập tệp rời nhau) | Codex `gpt-6.1-sol` high; Claude review |
| 2 | Triển khai lên EC2 và Vercel; tiêu đề bảo mật Caddy; kiểm thử đầu cuối mục 7.4 | Claude chạy lệnh, chủ kho đăng nhập thử |
| 3 (hoãn) | Giới hạn tốc độ và trần chi tiêu (mục 8) | — |

### 10.2 Bảng theo dõi

Trạng thái: `chờ giao` · `đang giao` · `chờ review` · `cần sửa` · `xong` · `hoãn`. Cập nhật mỗi khi đổi trạng thái; bản gốc cũng ghi ở `plan/TRACKING.md`.

| Mã | Việc | Đợt | Giao cho | Trạng thái | Bằng chứng / ghi chú |
| :-: | :--- | :-: | :--- | :-: | :--- |
| B-0a | Tạo tài khoản admin Supabase, gán vai trò `admin` | 0 | Chủ kho | chờ chủ kho | Lệnh SQL ở mục 4.3 của cuộc trao đổi 17/11 và ở brief T28 phụ lục A |
| B-0b | Tắt đăng ký tự do; thêm URL Vercel; bật phát hiện refresh token bị lộ | 0 | Chủ kho | chờ chủ kho | Mục 4.3 |
| T28 | Backend: xác minh JWT bằng JWKS, vai trò, `/api/me`, sở hữu hội thoại và phản hồi, kiểm thu hồi trực tuyến, CORS | 1 | Codex `gpt-6.1-sol` high | xong (qua T28-fix-1) | 18/11: toàn kho 764 test qua; `uvicorn` thật không token: 401. Brief `briefs/T28-xac-thuc-backend.md` |
| T29 | Web: phiên có token và vai trò, gắn `Authorization`, tự gia hạn và gửi lại một lần, trang không có quyền, ẩn demo ở production | 1 | Codex `gpt-6.1-sol` high | xong | 18/11: `vitest` 193/193, build đạt. Brief `briefs/T29-xac-thuc-web.md` |
| B-2a | Triển khai bản mới lên EC2 và Vercel | 2 | Claude (lệnh), chủ kho (cho phép) | chờ T28, T29 | Cần chủ kho cho phép commit, push |
| B-2b | Tiêu đề bảo mật Caddy; nhật ký truy cập | 2 | Claude viết brief | chờ | |
| B-2c | Kiểm thử đầu cuối mục 7.4 | 2 | Claude + chủ kho | chờ | |
| B-3 | Giới hạn tốc độ, trần chi tiêu | 3 | — | hoãn | Mục 8 |
| T38 | Tiêu đề bảo mật Caddy + nhật ký truy cập | 2 | Codex (hết hạn mức), Claude hoàn tất | xong | 18/11: 784 test qua; đã triển khai EC2, `caddy validate` đạt, tiêu đề có thật; nhật ký ghi `nguoi_dung_id`, `phien_id`, `vai_tro` thật của tài khoản admin |
| B-2a' | Triển khai T28, T29, T38 lên EC2 và Vercel | 2 | Claude | xong | 18/11: `/api/cases` không token → 401 (cả qua Vercel); trang đăng nhập không còn nút demo; chủ kho đăng nhập admin, danh sách và chat chạy, nhật ký thấy `vai_tro: admin` |
| T39 | Đăng xuất, thu hồi, hết hạn phiên (mục 11): `POST /api/dang-xuat`, danh sách chặn phiên đã đăng xuất, kiểm trực tuyến mọi điểm cuối, vai trò sống, đăng xuất khi không hoạt động, đa tab, sửa nhãn vai trò | 1b | Codex `gpt-6.1-sol` high | xong ở mức test | 18/11: Python 809 qua, web 231 qua. Brief `briefs/T39-dang-xuat-thu-hoi-het-han-phien.md` |

## 11. Đăng xuất, thu hồi quyền và hết hạn phiên (bổ sung 18/11/2026)

### 11.1 Kiểm hiện trạng

Kiểm bằng đọc mã (`authClient.ts`, `AuthProvider.tsx`, `app/auth/online.py`) và nhật ký truy cập thật trên EC2:

| Câu hỏi | Hiện trạng | Đánh giá |
| :--- | :--- | :-: |
| Bấm "Đăng xuất" thì web làm gì | Xoá trạng thái giao diện ngay, rồi gọi `supabase.auth.signOut()` (mặc định phạm vi `global`: đăng xuất **mọi** thiết bị và thu hồi mọi refresh token) | Chạy, nhưng chưa có lựa chọn và chưa báo backend |
| Sau đăng xuất, access token cũ còn dùng được không | **Còn, tới khi hết hạn (tới 1 giờ)** cho mọi điểm cuối đọc. Chỉ `POST .../feedback` có kiểm trực tuyến (đệm 60 giây, nên vẫn còn tới 60 giây) | **Thiếu** |
| Đổi vai trò hoặc khoá tài khoản thì sao | Token cũ mang vai trò cũ tới khi hết hạn; kiểm trực tuyến chỉ xem token còn hợp lệ, **không** đối chiếu vai trò hiện tại | **Thiếu** |
| Tự đăng xuất khi không hoạt động | Không có | **Thiếu** (gói Supabase miễn phí không có *inactivity timeout*) |
| Đăng xuất ở tab này, tab kia thế nào | `onAuthStateChange` nhận `SIGNED_OUT`; chưa có test cho trường hợp nhiều tab | Cần kiểm thử |
| Nhãn vai trò ở thanh bên | **Lỗi:** `SidebarNav.tsx` gắn cứng `'Dược sĩ'`, không đọc vai trò. Nhật ký xác nhận `vai_tro: admin` ở backend nên chỉ là lỗi hiển thị | Lỗi |
| Lý do bị đăng xuất | Không báo người dùng | Thiếu |

### 11.2 Quyết định

| Mã | Quyết định | Lý do |
| :-: | :--- | :--- |
| Q-L1 | Nút "Đăng xuất" mặc định đăng xuất **thiết bị này** (`scope: 'local'`: thu hồi refresh token của phiên hiện tại). Thêm lựa chọn "Đăng xuất mọi thiết bị" (`scope: 'global'`) | Không bất ngờ đẩy người dùng khỏi thiết bị khác; vẫn có đường thoát khi nghi lộ |
| Q-L2 | Thêm `POST /api/dang-xuat`: backend đưa phiên (`session_id`, hoặc băm token nếu thiếu) vào **danh sách chặn trong bộ nhớ** tới khi token hết hạn; mọi yêu cầu sau đó dùng token này bị `401`. Web gọi nó **trước** khi gọi Supabase, nhưng chỉ khi tự đăng xuất (không gọi khi đăng xuất vì `401`) | JWT là không trạng thái nên không thu hồi được; danh sách chặn làm đăng xuất có hiệu lực ngay |
| Q-L3 | Kiểm trực tuyến (gọi Supabase `/auth/v1/user`, đệm 60 giây theo băm token) áp cho **mọi điểm cuối** (trừ `/api/health`). Khi Supabase báo `401`, `403` hoặc `404` (đã đăng xuất, bị khoá, đã xoá) → `401`. Khi Supabase lỗi mạng hoặc `5xx`: **thao tác ghi và gọi LLM** (`feedback`, `ask`, `ai`) từ chối `503`; **điểm cuối chỉ đọc** tạm tin chữ ký JWT và ghi cảnh báo vào nhật ký | Thu hồi có hiệu lực trong tối đa 60 giây mà không để Supabase gián đoạn làm sập việc xem |
| Q-L4 | **Vai trò sống:** vai trò dùng để kiểm quyền lấy từ `app_metadata.role` trong **phản hồi kiểm trực tuyến**, không chỉ từ token. Hai giá trị khác nhau thì dùng giá trị sống; giá trị sống không hợp lệ → `403` | Hạ quyền hay thu quyền có hiệu lực trong ≤ 60 giây, không phải chờ token hết hạn |
| Q-L5 | Rút **hạn access token** (JWT expiry trong Supabase) từ 3600 xuống **900 giây** (15 phút). Việc này làm trong bảng điều khiển, không đổi mã | Thu hẹp cửa sổ lộ token; gia hạn tự động nên không ảnh hưởng người dùng |
| Q-L6 | **Tự đăng xuất khi không hoạt động 30 phút** và **tối đa 12 giờ kể từ lúc đăng nhập**, ở phía web (hạn mức Supabase miễn phí không có tính năng này). Hằng số nằm một chỗ, dễ đổi. Báo lý do ở trang đăng nhập | Máy dùng chung ở khoa; giảm rủi ro bỏ quên phiên |
| Q-L7 | Đăng xuất ở một tab thì mọi tab cùng trình duyệt cũng thoát | Hành vi người dùng mong đợi |
| Q-L8 | Chưa làm: quản trị viên thu hồi phiên của người khác từ giao diện (cần khoá `service_role` ở phía máy chủ); tạm làm trong bảng điều khiển Supabase (Users → xoá hoặc khoá tài khoản; người dùng bị khoá mất quyền tối đa sau 60 giây nhờ Q-L3) | Để sau demo, cùng giao diện quản trị |

### 11.3 Kiểm thử

Backend: đăng xuất rồi dùng lại token → `401` ngay (cùng tiến trình); danh sách chặn tự dọn khi token hết hạn và có trần kích thước; kiểm trực tuyến trả `401` / `403` / `404` → `401`; Supabase `5xx` → đọc vẫn qua, ghi `503`; đổi vai trò sống từ `admin` xuống `duoc_si_ls` → quyền admin bị bỏ ở yêu cầu kế (sau hết đệm); vai trò sống không hợp lệ → `403`; đệm 60 giây; không ghi token vào nhật ký.

Web: nhãn vai trò theo `vaiTro` (`admin` → "Quản trị", `duoc_si_ls` → "Dược sĩ lâm sàng", demo → "Demo"); đăng xuất gọi `POST /api/dang-xuat` đúng một lần rồi Supabase `signOut` với `scope` đúng; không gọi `POST /api/dang-xuat` khi đăng xuất do `401`; hủy yêu cầu đang chạy; xoá bộ nhớ chat; hết 30 phút không hoạt động thì tự đăng xuất (đồng hồ giả); vượt 12 giờ thì tự đăng xuất; `SIGNED_OUT` từ tab khác dọn phiên; trang đăng nhập hiện đúng lý do.

### 11.4 Kiểm thử đầu cuối sau triển khai

1. Đăng xuất rồi gọi lại API bằng token cũ (Claude chạy bằng `curl` với token do chủ kho dán tạm vào, hoặc kiểm qua nhật ký) → `401`.
2. Trong bảng điều khiển Supabase đổi vai trò của một tài khoản thử, chờ 60 giây, thao tác → bị chặn.
3. Để tab nhàn rỗi 30 phút (hoặc hạ hằng số khi thử) → tự đăng xuất, trang đăng nhập có thông báo.
4. Hai tab cùng đăng nhập, đăng xuất ở một tab → tab kia thoát.
