# T89 – Cứng hoá backend: chặn thân trước xác thực (T1), khoá `AUTH_MODE=off` (T4), mẫu prompt thay một lượt (L7)

Nguồn: `docs/bao-cao-bao-mat-2026-11-20.md` mục T1, T4, L7. Agent: agy `gemini-4-hydrogen-xhigh`. **Không gọi shell, không gọi mạng; chỉ đọc và ghi tệp.**

Song song có T90 (web), T91 (lịch sử chat, sửa `service.py`, `schemas.py`, `feedback_chat.py`, `useChat.ts`), T92 (Dockerfile, CI). Không đụng tệp của các task đó.

## Phạm vi tệp

Sửa: `Caddyfile`, `app/api/main.py`, `app/config/settings.py` (chỉ thêm), `app/orchestration/ask.py` (chỉ hàm dựng prompt). Tạo: `tests/api/test_body_limit_auth_first.py`, `tests/config/test_auth_off_guard.py`, `tests/orchestration/test_prompt_single_pass.py`. Sửa test cũ chỉ khi hỏng vì thay đổi này, ghi lý do.

## 1. T1 – Thân yêu cầu bị đọc trước khi xác thực, không có trần

Hiện: `POST /api/ask` không token, thân JSON hỏng → **422** (đã đọc thân); không có trần kích thước.

- `Caddyfile`, trong khối site: `request_body /api/* { max_size 256KB }` (cú pháp Caddy 2: matcher đường dẫn rồi khối; đọc kỹ cú pháp sẵn có của tệp, giữ nguyên mọi phần khác).
- `main.py`: thêm middleware HTTP thuần (ASGI hoặc `@app.middleware("http")`) chạy **trước** định tuyến, cho mọi `/api/*` trừ `GET /api/health` và `OPTIONS` (preflight CORS):
  1. `Content-Length` > 262144 → **413** thân lỗi chuẩn `{"loi": {"ma": "than_qua_lon", "thong_bao": …}}`. Không có `Content-Length` mà có thân (chunked) → đọc tối đa 262144 byte, vượt thì 413 (hoặc từ chối 411; chọn một, ghi lý do).
  2. Khi `AUTH_MODE` khác `off`: thiếu tiêu đề `Authorization: Bearer <chuỗi không rỗng>` → **401** ngay, mã lỗi giống mã 401 hiện có của `app/auth` (đọc `app/auth/errors.py`), **không** đọc thân. Kiểm chữ ký JWT vẫn để nguyên ở phụ thuộc hiện có.
- Thứ tự middleware: CORS vẫn phải trả tiêu đề cho preflight như cũ (test CORS cũ phải qua).

## 2. T4 – `AUTH_MODE=off` là mở toàn quyền admin

- `settings.py`: `def assert_auth_mode_allowed() -> None` – nếu `AUTH_MODE=off` **và** biến `CDSS_RUNTIME` bằng `container` → ném `ConfigError("AUTH_MODE=off bị cấm khi chạy trong container")`. (T92 đặt `ENV CDSS_RUNTIME=container` trong Dockerfile.) Đọc môi trường bằng `os.getenv` như `load_case_source`.
- `main.py` `create_app`: gọi hàm trên trước khi dựng ứng dụng.

## 3. L7 – Mẫu prompt thay chỗ bằng `.replace` nối tiếp

`app/orchestration/ask.py` khoảng dòng 528: `part.replace("{{van_ban_ca}}", …).replace("{{doan_nguon}}", …)…` → văn bản ca chứa `{{cau_hoi}}` sẽ bị thay tiếp bằng câu hỏi (dữ liệu không tin cậy chèn vào chỗ khác của prompt).

- Thay bằng **một lượt**: `re.sub(r"\{\{(van_ban_ca|doan_nguon|lich_su|cau_hoi|loi_lan_truoc)\}\}", lambda m: values[m.group(1)], part)`. Kết quả không bị quét lại.
- Tìm mọi chỗ khác trong `app/orchestration/` và `app/llm/` dùng `.replace("{{` nối tiếp cho dữ liệu người dùng/ca; sửa cùng cách nếu nằm trong `ask.py`, nằm tệp khác thì chỉ ghi vào báo cáo.

## 4. Test

- `test_body_limit_auth_first.py` (`AUTH_MODE` bắt buộc, `Authenticator` giả như `tests/api/test_auth_ownership.py`):
  - không token + thân JSON hỏng → **401** (không phải 422);
  - có token hợp lệ + `Content-Length` 300000 → 413; thân 1 KB → xử lý bình thường;
  - `GET /api/health` không token → 200; `OPTIONS` preflight từ origin được phép → như cũ;
  - `AUTH_MODE=off`: không token vẫn qua, nhưng thân quá lớn vẫn 413.
- `test_auth_off_guard.py`: `off` + `CDSS_RUNTIME=container` → `create_app` ném lỗi; `off` không có `CDSS_RUNTIME` → chạy; `required` + `container` → chạy.
- `test_prompt_single_pass.py`: văn bản ca chứa chuỗi `{{cau_hoi}}` và `{{doan_nguon}}` → prompt cuối vẫn giữ nguyên hai chuỗi đó trong phần văn bản ca, câu hỏi chỉ xuất hiện đúng chỗ của nó.

## 5. Nghiệm thu (Claude chạy)

```
uv run ruff check .
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider
docker compose config -q   (cần .env.app tạm)
```
Claude kiểm thêm cú pháp Caddyfile bằng `docker run --rm -v …/Caddyfile:/etc/caddy/Caddyfile caddy:2 caddy validate`.

## 6. Cấm

Không cài gói. Không sửa tệp ngoài phạm vi. Ghi `plan/reports/T89.md` theo mẫu `AGENTS.md`.
