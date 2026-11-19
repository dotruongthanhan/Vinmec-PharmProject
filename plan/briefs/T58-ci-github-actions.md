# T58 – CI trên GitHub Actions và chạy được trên máy mới

Agent: sub Sonnet (cần mạng để kiểm phiên bản action). Đọc `AGENTS.md`, `CLAUDE.md` mục 8.

## Bối cảnh

Kho chạy được trên máy của Khải nhưng máy thành viên khác thì không. Mục tiêu là có một máy sạch (CI) chạy lại mọi kiểm tra, để biết ngay thứ gì chỉ có trên một máy.

Một số thứ chỉ có trên máy Khải:
- Từ 19/11, các thư mục sau **không còn trên git** (người dùng tự quản lý dữ liệu): `data/kb_curated/` (gồm `tra_cuu/tra_cuu.sqlite`, `tuong_tac/ddinter.sqlite`, `chunks.jsonl`), `data/kb_reports/`, `data/kb_sources/`, `data/cache/`, `data/runtime/`, `data/kb_staging/`.
- `.env` không có trên git: chứa các khoá `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY*`, `DATABASE_URL`.
- Ứng dụng có cơ chế lùi:
  - thiếu chỉ mục tra cứu thì chạy 5 luật;
  - thiếu khoá thì `CDSS_AI=off`;
  - `CASE_SOURCE=file` đọc `data/mock`;
  - `AUTH_MODE=off` tắt xác thực.
- Còn trên git: `data/mock/`, `data/gold/`, `data/kb/`.

Ngăn xếp:
- Python, quản lý bằng `uv` (`pyproject.toml`, `uv.lock`, `.python-version`); test `uv run pytest`; lint `uv run ruff check .`.
- Web trong `web/`: `npm ci`, `npx vitest run`, `npx tsc -b`, `npx oxlint`, `npm run build`.

## Phạm vi

**Được tạo / sửa:**
- `.github/workflows/ci.yml` (mới)
- `tests/conftest.py`: chỉ thêm cơ chế bỏ qua test cần dữ liệu cục bộ, xem mục 2
- Đánh dấu `@pytest.mark.can_du_lieu` (hoặc tên tương đương) cho các test cần tệp dữ liệu đã bỏ khỏi git
- `pyproject.toml`: chỉ phần `[tool.pytest.ini_options]` để khai báo marker
- `docs/chay-tren-may-moi.md` (mới)
- `plan/reports/T58.md` (mới)

**Cấm:**
- Sửa mã ứng dụng trong `app/**`, `web/src/**`.
- Sửa `.env`, đưa khoá hay `DATABASE_URL` vào workflow.
- Sửa `uv.lock`, `package-lock.json`.
- Xoá test.
- Commit, push.

## Yêu cầu

1. **Workflow `ci.yml`**
   - Chạy khi push và khi có pull request vào `main` và `vukhai248`.
   - Job `backend`, ma trận `ubuntu-latest` và `windows-latest`:
     - `astral-sh/setup-uv`, ghim phiên bản đã phát hành.
     - Python lấy từ `.python-version`.
     - `uv sync --frozen`.
     - `uv run ruff check .`.
     - `uv run pytest -q -p no:cacheprovider`.
     - Biến môi trường: `CDSS_PROFILE=test`, `CDSS_AI=off`, `CASE_SOURCE=file`, `AUTH_MODE=off`, `PYTHONIOENCODING=utf-8`.
   - Job `web`, chạy trên `ubuntu-latest`:
     - `actions/setup-node`, phiên bản Node theo `web/package.json` (`engines`) nếu có, không có thì Node 22 LTS.
     - Cache npm.
     - Chạy `npm ci`, `npx tsc -b`, `npx oxlint`, `npx vitest run`, `npm run build` (thư mục làm việc `web`).
   - Ghim action theo phiên bản chính đã phát hành. Kiểm trên trang phát hành của action, ghi link vào báo cáo.
   - Không dùng secret nào.
2. **Test cần dữ liệu cục bộ**
   - Tìm mọi test cần các tệp đã bỏ khỏi git. Cách tìm: tạm đổi tên `data/kb_curated`, `data/kb_reports`, `data/kb_sources`, `data/cache` rồi chạy pytest. **Nhớ đổi tên lại** trước khi kết thúc, kể cả khi lỗi.
   - Đánh dấu các test đó bằng marker.
   - Trong `conftest.py`, tự `skip` test có marker khi tệp cần thiếu, kèm lý do rõ ("thiếu data/kb_curated/tra_cuu/tra_cuu.sqlite, xem docs/chay-tren-may-moi.md").
   - Có đủ dữ liệu thì test vẫn chạy như cũ: số test qua trên máy này không được giảm.
   - Ghi danh sách test bị skip khi thiếu dữ liệu vào báo cáo.
3. **Kiểm cục bộ trước khi báo xong**
   - Đủ dữ liệu: `uv run pytest -q -p no:cacheprovider --basetemp=<thư mục trong %TEMP%>`. Kỳ vọng 1.301 qua, 0 trượt.
   - Thiếu dữ liệu (đổi tên tạm như mục 2): 0 trượt, chỉ có skip.
   - Nếu có `actionlint` thì chạy; không có thì kiểm cú pháp YAML bằng Python.
4. **`docs/chay-tren-may-moi.md`**
   - Các bước cho thành viên mới: cài `uv` và Node, `uv sync`, `npm ci`.
   - Tạo `.env` từ danh sách tên biến (không có giá trị). Xem `app/config` để lấy đúng tên biến.
   - Cách chạy backend và web ở chế độ không khoá, không dữ liệu.
   - Dữ liệu nào thiếu thì mất tính năng nào (ví dụ thiếu `tra_cuu.sqlite` thì không có yếu tố 4 và trùng nhóm D2).
   - Các lỗi hay gặp trên Windows: mã hoá UTF-8, CRLF, đường dẫn.
5. **Báo cáo `plan/reports/T58.md`**
   - Danh sách tệp đã tạo hoặc sửa.
   - Kết quả các lệnh ở mục 3.
   - Danh sách test có marker.
   - Những gì CI chưa kiểm được: Supabase, LLM, dữ liệu lớn.

## Cấm làm

- Không commit, không push.
- Không dùng `&`.
- Không in giá trị trong `.env`.
- Không tải hay đẩy dữ liệu đi đâu.
