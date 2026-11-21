# Chạy dự án trên máy mới

Dùng cho thành viên mới hoặc máy sạch (CI). Không cần khoá API, không cần dữ liệu tri thức: ứng dụng tự lùi về chế độ không khoá, không dữ liệu.

## 1. Cài công cụ

- `uv` (quản lý Python): <https://docs.astral.sh/uv/>. Phiên bản Python lấy từ `.python-version` (3.13), `uv` tự tải.
- Node.js 22 LTS trở lên (có `npm`).
- Git.

## 2. Cài thư viện

```powershell
uv sync --frozen
cd web
npm ci
```

## 3. Tạo `.env`

Sao `.env.example` thành `.env` rồi điền giá trị nếu có (tệp `.env` không nằm trên git, không dán vào chat hay log). Tên biến:

| Biến | Ý nghĩa |
| :--- | :--- |
| `DEEPSEEK_API_KEY` | khoá LLM (DeepSeek) |
| `OPENROUTER_API_KEY`, `OPENROUTER_API_KEY_2` | khoá nhúng và xếp hạng lại |
| `DATABASE_URL` | chuỗi nối Supabase PostgreSQL |
| `CASE_SOURCE` | `file` (đọc `data/mock`) hoặc `db` (đọc Supabase) |
| `AUTH_MODE` | `off` tắt xác thực (chỉ khi phát triển cục bộ) |
| `AUTH_ONLINE_TTL` | thời gian đệm kiểm thu hồi, giây |
| `ACCESS_LOG` | nhật ký truy cập, `off` để tắt |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET` | xác thực Supabase |
| `CORS_ORIGINS` | nguồn web được phép, ngăn cách bằng dấu phẩy |

Biến khác do mã đọc: `CDSS_PROFILE` (`test` cho kiểm thử), `CDSS_AI` (`off` tắt bước AI), `CDSS_CASE_DIR` (thư mục ca bệnh).

## 4. Chạy ở chế độ không khoá, không dữ liệu

Backend (PowerShell):

```powershell
$env:CDSS_AI = "off"; $env:CASE_SOURCE = "file"; $env:AUTH_MODE = "off"
uv run uvicorn app.api.main:app --reload --port 8000
```

Web (cửa sổ khác):

```powershell
cd web
npm run dev
```

Kiểm tra:

```powershell
uv run ruff check .
uv run pytest -q -p no:cacheprovider
cd web; npx tsc -b; npx oxlint; npx vitest run; npm run build
```

## 5. Dữ liệu nào thiếu thì mất gì

Các thư mục sau không nằm trên git, người dùng tự quản lý: `data/kb_curated/`, `data/kb_reports/`, `data/kb_sources/`, `data/cache/`, `data/runtime/`, `data/kb_staging/`. Còn trên git: `data/mock/`, `data/gold/`, `data/kb/`.

| Thiếu | Hậu quả |
| :--- | :--- |
| `data/kb_curated/tra_cuu/tra_cuu.sqlite` | không phân giải tên thuốc về hoạt chất: mất yếu tố 4 và kiểm trùng nhóm điều trị (D2); chạy 5 luật |
| `data/kb_curated/tuong_tac/ddinter.sqlite` | không sàng lọc tương tác thuốc |
| `data/kb_curated/chunks.jsonl` | không truy xuất đoạn nguồn; `che_do.truy_xuat` = `chua_co` |
| `data/kb_sources/` | không chạy lại được các lệnh dựng dữ liệu, nạp Supabase từ nguồn |
| `.env` thiếu khoá LLM | bước AI tắt (`CDSS_AI=off`), bảng nhận định do luật sinh |

Test cần các tệp trên được gắn marker `can_du_lieu` (bảng trong `tests/conftest.py`) và tự bỏ qua khi thiếu, kèm lý do. Xem danh sách: `uv run pytest -q -rs`.

## 6. Lỗi hay gặp trên Windows

- **Mã hoá UTF-8:** đặt `$env:PYTHONIOENCODING = "utf-8"` khi in tiếng Việt; mở và ghi tệp luôn chỉ rõ `encoding="utf-8"`. Lỗi `UnicodeEncodeError` trong console là do mã trang cp1252.
- **CRLF:** Git trên Windows đổi LF thành CRLF; cảnh báo "LF will be replaced by CRLF" vô hại. Không so sánh byte của tệp dữ liệu giữa hai hệ điều hành; nếu cần, đặt `git config core.autocrlf input`.
- **Đường dẫn:** dùng `pathlib`, không nối chuỗi bằng `\`. Trong Git Bash dùng `/d/...`, trong PowerShell `D:\...`. Đường dẫn dài hơn 260 ký tự có thể lỗi: đặt kho ở thư mục ngắn.
- **`--basetemp`:** nếu `pytest` báo thư mục tạm bị khoá, thêm `--basetemp=%TEMP%\pytest-cdss`.
- **Sao liên kết cứng của `uv`:** cảnh báo "Failed to hardlink" khi kho và cache `uv` ở ổ khác nhau là vô hại; đặt `UV_LINK_MODE=copy` để tắt.
