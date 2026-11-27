# Báo cáo TR2a

## Trạng thái: CHƯA XONG

Đã bổ sung bảng, quyền, đích ghi PostgreSQL theo lô, cấu hình nhiều đích và bộ hẹn giờ dọn chung. Chưa bảo đảm luồng ghi hoặc luồng dọn dừng hẳn trong ba giây khi một lệnh kết nối hoặc truy vấn đồng bộ đang bị chặn: `close()` trả về trong giới hạn nhưng luồng daemon đang thực hiện I/O có thể tiếp tục tới khi thao tác đó kết thúc. Cần xử lý và kiểm thử vòng đời này trước khi coi brief hoàn tất.

## Quyết định và giới hạn

- `VetChay` có thêm `so_khoa_la_bi_bo` và `cac_buoc` so với bảng ở A.3: lưu `so_khoa_la_bi_bo` thành cột và lưu `cac_buoc` trong bảng con. `vet_bi_cat` được giữ theo mô hình và yêu cầu brief.
- Giới hạn thuộc tính 4.096 byte được kiểm tra trong code trên JSON UTF-8, theo cách đo của TR1; không dùng `pg_column_size` trong DDL. Giá trị vượt giới hạn làm bỏ lô và tăng bộ đếm.
- Ghi lô dùng kết nối riêng và câu lệnh tham số hóa; dọn DB xóa từng lô tối đa 5.000 bản ghi. Một bộ hẹn giờ nền dùng chung giữa các tracer trong tiến trình.
- Đã dùng kết nối giả, không chạy SQL lên DB, không gọi mạng và không cài gói. Chưa xác minh DDL trên PostgreSQL; việc này dành cho bước kiểm độc lập được mô tả trong brief.
- Các phép thử chạy với `PYTHON_DOTENV_DISABLED=1`, `UV_NO_SYNC=1`, `uv --offline`, đã bỏ `DATABASE_URL` khỏi môi trường tiến trình và dùng thư mục tạm riêng dưới `tests/tracing/`. Không đọc hoặc sửa `.env`.
- Đã lỡ đọc tệp `C:/Users/Admin/.codex/plugins/cache/openai-curated-remote/superpowers/7.0.1/skills/using-superpowers/SKILL.md` trước khi đối chiếu đầy đủ quy tắc cấm truy cập `~/.codex`. Không truy cập tiếp thư mục đó. Đây là sai lệch khỏi quy tắc bảo mật của dự án.

## Lệnh và kết quả

- `uv run --offline ruff check app tests/tracing/*.py`: đạt.
- `uv run --offline ruff format --check app tests/tracing/*.py`: đạt, 224 tệp đúng định dạng.
- `uv run --offline pytest -q -p no:cacheprovider --basetemp=tests/tracing/.tmp-tr2a-20261127-g tests/tracing`: 26 passed.
- Tương tự, chạy riêng `tests/agent`: 231 passed; `tests/orchestration`: 84 passed; `tests/api`: 218 passed, 2 skipped. Các bộ chạy sau khi đổi bộ hẹn giờ dùng chung; chỉ có thay đổi sau đó là xử lý URL trắng và bổ sung test DB giả.
- Lần đầu `uv run` thất bại do không có quyền vào cache uv mặc định; đổi `UV_CACHE_DIR` sang thư mục tạm được phép. Lần đầu `tests/tracing` có 7 passed, 12 lỗi setup do `PermissionError` ở thư mục tạm pytest mặc định; lần chạy lại với `--basetemp` riêng đã đạt như trên.
- `git diff --check` toàn kho báo khoảng trắng cuối dòng trong các thay đổi `docs/` đã có sẵn; kiểm tra giới hạn vào các tệp được phép đã đạt. Không sửa những thay đổi sẵn có đó.
