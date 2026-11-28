# T96 – Đưa `streamlit` ra khỏi image API (HT12 / L8)

Nguồn: `docs/bao-cao-bao-mat-2026-11-20.md` mục L8 và HT12. Agent: agy `gemini-4-hydrogen-xhigh` hoặc Codex `xhigh`; quy tắc chung ở `AGENTS.md`. **Không tự cài gói, không gọi mạng.** Agent chỉ sửa tệp; Claude chạy `uv lock`, `uv sync`, `pytest`, `ruff`, build Docker.

## Bối cảnh

Giao diện chính là bản web React (`web/`) gọi API FastAPI (`app/api/`). Bản Streamlit (`app/ui/streamlit_app.py` và các thành phần dùng `streamlit`) chỉ còn để tham khảo, người dùng không dùng nữa. Nhưng `streamlit` đang nằm trong `dependencies` của `pyproject.toml`, nên bị cài vào image API (Dockerfile chạy `uv sync --frozen --no-dev`) cùng nhiều gói phụ (tornado, pandas, pyarrow…). Mục tiêu: giảm bề mặt CVE và dung lượng image.

## Việc phải làm

1. Trong `pyproject.toml`: bỏ `"streamlit"` khỏi `[project].dependencies`, thêm vào nhóm `[dependency-groups].dev` (nhóm này `--no-dev` của Docker đã bỏ qua, CI `uv sync --frozen` vẫn cài nên `tests/ui/` vẫn chạy được).
2. **Không** xoá `app/ui/`, không sửa nội dung `app/ui/`, không đổi Dockerfile, không đổi CI.
3. Rà: tìm mọi chỗ trong `app/api/`, `app/orchestration/`, `app/` (ngoài `app/ui/`) có `import streamlit` hoặc `from streamlit`. Có thì **dừng và báo** (khi đó phải tách mã dùng chung, không làm trong brief này).
4. Rà các module `app/ui/*` mà `app/api/` hoặc `tests/api/`, `tests/orchestration/` đang import (ví dụ `app.ui.services`, `app.ui.state`…): liệt kê ra báo cáo và xác nhận chúng **không** import `streamlit` (nếu có thì báo).
5. Sửa ghi chú liên quan trong `README.md` / `CLAUDE.md` nếu có câu nói Streamlit là phụ thuộc chính (chỉ sửa chữ, giữ ngắn).
6. Ghi báo cáo vào `plan/briefs/T96-bao-cao.md`: các tệp đã sửa, kết quả rà ở bước 3 và 4.

## Phạm vi file

Được sửa: `pyproject.toml`, `README.md`, `CLAUDE.md` (chỉ câu nhắc Streamlit), `plan/briefs/T96-bao-cao.md`.
Cấm đụng: `uv.lock` (Claude tự `uv lock`), `Dockerfile`, `.github/`, `app/`, `web/`, `tests/`, `.env*`.

## Nghiệm thu (Claude chạy)

```bash
uv lock
uv sync --frozen
uv run ruff check .
uv run pytest -q -p no:cacheprovider        # số test qua không giảm so với trước (1.621 + vitest không đổi)
uv sync --frozen --no-dev && uv run python -c "import app.api.main"   # API import được khi không có streamlit
uv run python -c "import streamlit" 2>&1 | grep -q ModuleNotFoundError && echo "OK: streamlit vắng ở nhóm chạy"
docker compose build api && docker run --rm --entrypoint python vinmec-pharm-api:latest -c "import streamlit" 2>&1 | grep -q ModuleNotFoundError && echo "OK: image không có streamlit"
```

Kiểm dung lượng: `docker images vinmec-pharm-api` trước và sau, ghi vào báo cáo.

## Bảo mật

- Không thêm gói mới; chỉ chuyển nhóm. Sau `uv lock`, kiểm diff `uv.lock` chỉ có việc bỏ gói, không thêm gói nào.
- Quét CVE: job `security` của CI (OSV-Scanner trên `uv.lock`) phải vẫn xanh.

## Việc cấm làm

Xoá hoặc đổi tên `app/ui/`; đổi phiên bản bất kỳ gói nào; sửa Dockerfile hoặc CI; commit, push.
