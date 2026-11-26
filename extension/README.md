# Chrome Extension — Trợ lý Thẩm định Y lệnh Độc lập (Zero-Retention)

Tiện ích Chrome Side Panel hoàn toàn độc lập với hệ thống EMR/OH và không đọc/ghi cơ sở dữ liệu hồ sơ bệnh án (`nghiep_vu`). Tiện ích đọc dữ liệu từ các tab bệnh án bạn đang mở trên trình duyệt, cho phép dán (`Ctrl+V`) và cắt ảnh chụp bảng y lệnh từ phần mềm OH, che toàn bộ thông tin định danh cá nhân (PII) tại trình duyệt trước khi gửi qua backend độc lập (cổng `8001`) để chạy 14 công thức + 14 luật lâm sàng và diễn giải DeepSeek Flash.

## Kiến trúc mô hình

- **Giai đoạn 0b (1 lần mỗi mẫu EMR, cache vĩnh viễn theo `schemaHash`):** `gemini-3.5-flash-lite` (chỉ nhận **tên nhãn trường**, không có giá trị bệnh nhân).
- **Giai đoạn 1 (4 worker song song):**
  - Worker 1 (Vision bảng y lệnh OH, PNG nguyên nét tới 8 MB): `gemini-3.6-flash`.
  - Workers 2–4 (Xét nghiệm/Sinh hiệu, Nhân khẩu/Chẩn đoán/Dị ứng, Thuốc nền/Diễn biến): `gemini-3.5-flash-lite`.
- **Giai đoạn 2 (Tất định):** 14 công thức + 14 luật qua `app/pipeline.py` (`< 300 ms`).
- **Giai đoạn 3 (Bất đồng bộ):** `deepseek-flash` + openFDA RAG + kiểm chứng trích dẫn + Agentic Q&A.

## Cài đặt & chạy cho đồng đội (Unpacked Extension)

Yêu cầu: **Node.js ≥ 22** và **Python ≥ 3.11 (`uv`)**.

### 1. Khởi động dịch vụ backend độc lập (cổng 8001)

```bash
# Tại thư mục gốc kho lưu trữ:
AUTH_MODE=off KB_SOURCE=auto uv run uvicorn app.extension_api.main:app --port 8001
```

> Lưu ý bảo mật: `AUTH_MODE=off` chỉ dành cho môi trường phát triển cục bộ trên máy cá nhân; khi chạy trong container (`docker-compose.extension.yml`), hệ thống luôn bắt buộc JWT Supabase (`AUTH_MODE=required`). Cần có `GEMINI_API_KEY` (và `DEEPSEEK_API_KEY` nếu muốn bật Giai đoạn 3) trong `.env`.

### 2. Build gói Extension (`extension/dist/`)

```bash
npm --prefix extension ci
npm --prefix extension run lint
npm --prefix extension run build
```

### 3. Nạp vào Google Chrome (`Load unpacked`)

1. Mở `chrome://extensions/` trong Google Chrome.
2. Bật **Developer mode** (góc trên bên phải).
3. Bấm **Load unpacked** và chọn thư mục `extension/dist/`.
4. Ghim biểu tượng tiện ích lên thanh công cụ Chrome và bấm để mở **Side Panel**.

### 4. Kiểm thử tự động

```bash
# Kiểm thử Extension (Vitest + kiểm tra manifest/icons/CSP):
cd extension && npx vitest run

# Kiểm thử Backend Extension:
uv run pytest -q -p no:cacheprovider tests/extension_api tests/architecture
```
