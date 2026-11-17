# T38 – Tiêu đề bảo mật ở Caddy và nhật ký truy cập ở backend (plan 1.5 mục 9, đợt 2)

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort high) · **Ngày:** 18/11/2026
**Đọc trước:** `AGENTS.md`; `plan/plan-1.5-bao-mat-xac-thuc-phan-quyen.md` (mục 6, 9); `Caddyfile`; `docker-compose.yml`; `app/api/main.py`, `app/api/routes.py`, `app/auth/dependencies.py`, `app/auth/errors.py`, `app/config/settings.py`; `.env.example`.

## 1. Bối cảnh

T28 và T29 đã xong (xác thực JWT, vai trò, sở hữu hội thoại). Còn hai việc bảo mật nhẹ, **không chạm cơ sở dữ liệu**: (a) Caddy chưa gửi tiêu đề bảo mật; (b) backend chưa có nhật ký truy cập (ai gọi gì, bị chặn gì). Giới hạn tốc độ vẫn **hoãn**, không làm.

## 2. Việc 1 – Caddyfile

Sửa `Caddyfile` (giữ `{$SITE_ADDRESS}`, `encode gzip`, `reverse_proxy api:8000`):

- Thêm khối `header` cho mọi phản hồi:
  - `Strict-Transport-Security "max-age=15552000; includeSubDomains"` (6 tháng; **không** `preload`).
  - `X-Content-Type-Options "nosniff"`
  - `X-Frame-Options "DENY"`
  - `Referrer-Policy "strict-origin-when-cross-origin"`
  - `Permissions-Policy "camera=(), microphone=(), geolocation=()"`
  - `-Server` (bỏ tiêu đề `Server`).
- Riêng đường dẫn `/api/*` (API chỉ trả JSON): thêm `Content-Security-Policy "default-src 'none'; frame-ancestors 'none'"` và `Cache-Control "no-store"`. **Không** áp CSP này lên các đường dẫn khác, vì ứng dụng cũng phục vụ bản web đóng gói ở `/` và CSP chặt sẽ làm hỏng nó.
- Thêm `log` ra stdout dạng JSON, **bỏ tiêu đề `Authorization` và `Cookie` khỏi nhật ký** bằng bộ lọc rõ ràng (`format filter` với `request>headers>Authorization delete` và `request>headers>Cookie delete`), và bỏ phần query của URI nếu cú pháp cho phép (`request>uri query` hoặc `uri` thay bằng đường dẫn; chọn cách đúng với Caddy 2).
- Ghi chú tiếng Việt ngắn trên từng khối.

Agent **không chạy được Caddy ở máy này** (Docker không bật). Hãy tự rà cú pháp theo tài liệu Caddy 2 đã biết, tránh chỉ thị không chắc chắn, và nêu rõ trong báo cáo dòng nào chưa chắc để người review chạy `caddy validate` trên EC2. **Không thêm chỉ thị nào ngoài danh sách trên.**

## 3. Việc 2 – nhật ký truy cập ở backend

Tạo `app/api/access_log.py` và nối vào `app/api/main.py` bằng middleware (Starlette `BaseHTTPMiddleware` hoặc ASGI thuần).

Mỗi yêu cầu kết thúc ghi **một dòng JSON** vào `data/runtime/nhat_ky_truy_cap-YYYY-MM-DD.jsonl` (theo ngày UTC), gồm đúng các trường:

| Trường | Giá trị |
| :--- | :--- |
| `thoi_diem` | ISO 8601 UTC |
| `nguoi_dung_id` | `sub` của người gọi, hoặc `null` nếu chưa xác thực được |
| `phien_id` | `session_id` hoặc `null` |
| `vai_tro` | vai trò hoặc `null` |
| `phuong_thuc` | `GET`, `POST`… |
| `duong_dan` | **đường dẫn không có query string** |
| `ma_trang_thai` | mã HTTP |
| `ma_loi` | `ma` trong thân lỗi API (`chua_dang_nhap`, `khong_co_quyen`…) hoặc `null` |
| `thoi_gian_ms` | số nguyên |

**Tuyệt đối không ghi:** token hay bất kỳ phần nào của tiêu đề `Authorization`, thân yêu cầu hay thân phản hồi, query string, địa chỉ IP, `User-Agent`, câu hỏi chat, nội dung phản hồi.

Yêu cầu hành vi:

- Không ghi `GET /api/health` (nhiễu).
- Để biết người gọi: `current_principal` (và `require_role`, `require_online_check`) gán danh tính vào `request.state` ngay khi xác thực được, **kể cả khi sau đó trả 403** (vai trò sai vẫn biết ai). Khi bị `401` thì danh tính là `null`.
- Để biết `ma_loi`: trình xử lý lỗi ở `main.py` gán mã vào `request.state` trước khi trả thân lỗi (hoặc cách tương đương, miễn không đọc lại thân phản hồi).
- **Ghi nhật ký lỗi không bao giờ làm hỏng yêu cầu:** mọi `OSError` hoặc ngoại lệ khi ghi bị nuốt (không ghi ra log chứa dữ liệu nhạy cảm), phản hồi vẫn trả đúng.
- An toàn đa luồng: dùng khoá khi ghi.
- **Giữ 90 ngày:** lúc khởi động ứng dụng (lifespan), xoá các tệp `nhat_ky_truy_cap-*.jsonl` cũ hơn 90 ngày tính theo ngày trong tên tệp. Hàm xoá chỉ đụng tệp đúng mẫu tên này.
- Cấu hình: biến môi trường `ACCESS_LOG` = `on` (mặc định) hoặc `off`; thư mục ghi lấy từ cùng gốc với `data/runtime` mà `CaseService` đang dùng, **tiêm được** để test dùng thư mục tạm. Thêm `ACCESS_LOG=on` kèm chú thích vào `.env.example`.
- Tên trường tiếng Việt không dấu, `snake_case` đúng như bảng trên.

## 4. Kiểm thử bắt buộc (`tests/api/test_access_log.py`)

Dùng bộ kiểm token giả có sẵn trong `tests/auth/support.py` và `tests/api/conftest.py`, không gọi mạng.

1. Yêu cầu `200` hợp lệ → có đúng một dòng với đủ trường, `nguoi_dung_id`, `phien_id`, `vai_tro` đúng.
2. Không token → `401`: dòng có `nguoi_dung_id = null`, `ma_loi = "chua_dang_nhap"`.
3. Vai trò sai → `403`: dòng có `nguoi_dung_id` của người gọi, `ma_loi = "khong_co_quyen"`.
4. **Không có chuỗi token** nào trong tệp nhật ký; **không có query string** (gọi với `?x=bi-mat`, chuỗi này không xuất hiện); không có thân yêu cầu (gọi `/ask` với câu hỏi có chuỗi đặc trưng, chuỗi đó không xuất hiện).
5. `GET /api/health` không sinh dòng.
6. Thư mục ghi không ghi được (tiêm đường dẫn là một tệp thường thay vì thư mục) → yêu cầu vẫn trả đúng mã, không ném lỗi.
7. Xoay vòng: tạo tệp giả tên cũ hơn 90 ngày và mới hơn; hàm dọn chỉ xoá tệp cũ, và không đụng tệp khác (ví dụ `hoi_thoai.jsonl`).
8. `ACCESS_LOG=off` → không ghi.
9. Tệp ghi theo ngày UTC (kiểm tên tệp với đồng hồ tiêm được).

Mọi test cũ phải qua; không sửa kỳ vọng, không `skip`.

## 5. Phạm vi file

**Được tạo hoặc sửa:** `Caddyfile`, `app/api/access_log.py`, `app/api/main.py`, `app/api/routes.py` (chỉ nếu cần), `app/auth/dependencies.py` (chỉ để gán `request.state`), `app/config/settings.py` (chỉ để đọc `ACCESS_LOG`), `tests/api/test_access_log.py`, `tests/api/conftest.py`, `.env.example`.
**Cấm đụng:** `web/`, `app/db/`, `db/`, `data/`, `plan/`, `.env`, `Dockerfile`, `docker-compose.yml`, `pyproject.toml`. Không thêm thư viện.

## 6. Nghiệm thu

```bash
uv run ruff check app/api app/auth tests/api tests/auth
uv run ruff format --check app/api app/auth tests/api tests/auth
uv run pytest -q -p no:cacheprovider tests/api tests/auth
uv run pytest -q -p no:cacheprovider --ignore=tests/architecture/.tmp --ignore=tests/db/.tmp --ignore=tests/kb/.tmp
```

Toàn kho **không có test trượt** (trước đó 764 qua). Rồi chạy `uvicorn` thật ở cổng 8031 với `AUTH_MODE=required`, gọi `GET /api/cases` không token, và dán một dòng nhật ký sinh ra (đã kiểm không chứa gì ngoài trường cho phép). Dừng `uvicorn` sau khi xong, xoá tệp nhật ký thử.

## 7. Cấm làm

Không đọc hay in `.env`. Không gọi Supabase thật. Không đổi cơ sở dữ liệu. Không làm giới hạn tốc độ. Không commit, không push. Báo cáo theo mẫu `AGENTS.md`, nêu rõ mọi chỗ lệch brief và các dòng Caddyfile chưa chắc.
