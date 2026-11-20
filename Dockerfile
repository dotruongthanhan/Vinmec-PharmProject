# syntax=docker/dockerfile:1
# Một image duy nhất: FastAPI phục vụ cả API (/api) lẫn bản web đã build (/).
# Cùng một địa chỉ nên trình duyệt không gặp vấn đề CORS.

# --- 1. Build bản web (Vite + React) ---
FROM node:24-alpine@sha256:116b800c3754b440ee0aa3ed2f20f5bf3d99a554bfd9adeea09ea8017f6e85f5 AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# Khoá Supabase là khoá công khai (anon) của trình duyệt, nên được nhúng lúc build.
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
# Tắt dữ liệu giả: bản đưa lên phải gọi API thật.
ENV VITE_USE_MOCK=0
RUN npm run build

# --- 2. Môi trường Python và ứng dụng ---
FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CDSS_RUNTIME=container \
    PATH="/srv/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.12.15@sha256:62f8c047d0a0e9ece6b53fc63df902585a67a47a7f318ddec4a37db586edc8e3 /uv /usr/local/bin/uv

WORKDIR /srv
# Cài thư viện trước để tận dụng cache khi chỉ sửa mã.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Chỉ mang dữ liệu mà ứng dụng thực sự đọc khi chạy.
COPY app ./app
COPY config ./config
COPY data/kb ./data/kb
COPY data/kb_curated ./data/kb_curated
COPY data/mock ./data/mock
COPY data/gold ./data/gold
COPY --from=web /web/dist ./web/dist

# Thư mục ghi phản hồi và nhật ký; trên máy chủ sẽ gắn volume vào đây.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p data/runtime \
    && chown -R appuser:appuser data/runtime
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status==200 else 1)"

# Một worker duy nhất: trạng thái chạy nền AI nằm trong bộ nhớ của tiến trình.
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
