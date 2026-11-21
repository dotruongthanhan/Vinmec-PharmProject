# T61-fix-1 – Đóng SQLite trước khi xoá cache; điều kiện bỏ qua test CSV DDInter

Agent: agy `gemini-4-hydrogen-xhigh`. **Không gọi shell, không gọi mạng.** Claude chạy test khi review.

Đọc: `AGENTS.md`, `plan/reports/T61.md`, `tests/conftest.py`.

## Claude review T61 ngày 19/11

Pytest toàn kho: 1.324 qua, **3 trượt**.

1. `tests/retrieval/test_embed_corpus.py::test_embed_corpus_deletes_old_cache_only_with_flag`
   - Lỗi: `--xoa-cache-cu` trả 1 với thông báo `[WinError 32] The process cannot access the file because it is being used by another process`.
   - Nguyên nhân: trên Windows, kết nối SQLite (của lệnh hoặc của `CachedEmbedder`) còn mở khi gọi `unlink`.
   - Sửa trong `app/retrieval/embed_corpus.py`:
     - Đếm dòng bằng một kết nối đóng ngay (`contextlib.closing`). Lưu ý `with sqlite3.connect()` **không** tự đóng.
     - Đảm bảo không còn đối tượng nào giữ tệp trước khi xoá.
   - Không đổi test cho dễ qua.
2. `tests/db/test_cli.py::test_dry_run_never_connects[ddinter]` và `tests/db/test_loading.py::test_ddinter_counts_copy_and_upsert`
   - Hai test cần các CSV ở `data/kb_sources/ddinter/*.csv`.
   - Ngày 19/11 Claude đã chuyển thư mục đó sang `data/_luu_tru/ddinter_csv_2026-11-16/`.
   - Marker `can_du_lieu` trong `tests/conftest.py` đang chỉ kiểm thư mục `data/kb_sources` (biến `_NGUON`), nên không bỏ qua hai test này.
   - Sửa `tests/conftest.py`: hai test này phải kiểm đúng `data/kb_sources/ddinter`, có ít nhất một `*.csv`.
   - **Không** sửa `app/db/**`, **không** chuyển dữ liệu.
3. `ruff format`: `app/providers/gemini_embed.py` chưa đúng định dạng. Định dạng lại.

## Phạm vi

- **Được sửa:** `app/retrieval/embed_corpus.py`, `app/providers/gemini_embed.py` (chỉ định dạng), `tests/conftest.py`, `tests/retrieval/test_embed_corpus.py` (chỉ khi cần đóng kết nối trong test), mục "## T61-fix-1" cuối `plan/reports/T61.md`.
- **Cấm:** tệp khác, `data/**`, commit.
