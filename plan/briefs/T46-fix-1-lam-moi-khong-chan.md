# T46-fix-1 – Làm mới dữ liệu không chặn và không báo lỗi oan

Mô hình: Codex `gpt-6.2-sol`, effort `high`. Chạy nền, không dừng để hỏi; điểm chưa rõ thì chọn cách ít rủi ro nhất và ghi vào báo cáo mục "Lựa chọn đã làm".

## Bối cảnh (Claude review T46)
T46 đạt nghiệm thu (972 test, verify-read 66/66). Đo trên DB thật: làm mới danh sách mất 5–6 giây. Hai lỗi:
1. `CaseService._ensure_cases` (`app/api/service.py`): khi hết TTL mà `loader.list_cases()` ném `DatabaseReadError` (mạng chập chờn, đã tái hiện được một lần), yêu cầu đó lỗi dù đã có `self._cases` cũ trong bộ nhớ.
2. Trong lúc một luồng làm mới (5–6 giây), mọi yêu cầu khác chờ `_refresh_lock`, kể cả mở chi tiết ca.
3. (nhỏ) `app/db/read_pool.py`: kết nối rảnh có thể đã bị pooler cắt; lần dùng lại đầu tiên lỗi.

## Phạm vi file
Được sửa: `app/api/service.py` (chỉ phần `_ensure_cases` và trạng thái liên quan), `app/db/read_pool.py`, `tests/api/test_case_source.py`, `tests/db/` (test mới cho pool), `plan/reports/T46-fix-1.md`.
Cấm đụng: `web/`, `app/orchestration/`, `app/llm/`, `app/deid/`, `app/pipeline.py`, `pyproject.toml`, `.env`. Có hai task khác đang sửa các thư mục đó song song.

## Yêu cầu
1. **Giữ dữ liệu cũ khi làm mới lỗi:** nếu đã có `self._cases` và làm mới ném `DatabaseReadError`, ghi log cảnh báo (không có dữ liệu người bệnh, không có chuỗi kết nối), giữ nguyên ca và kết quả cũ, đặt lần thử lại sau 15 giây (không đợi hết một TTL đầy đủ), trả dữ liệu cũ. Chỉ khi **chưa từng nạp được** mới ném lỗi như hiện nay. `lam_moi_luc` giữ giá trị lần thành công gần nhất.
2. **Không chặn khi đã có dữ liệu:** khi hết TTL và đã có dữ liệu cũ, chỉ một luồng đi làm mới (`_refresh_lock.acquire(blocking=False)`); luồng khác lấy được dữ liệu cũ ngay. Lần nạp đầu tiên (chưa có dữ liệu) vẫn chờ như hiện nay. Làm mới vẫn chạy trên luồng của yêu cầu (không thêm luồng nền dài hạn), trừ khi cách nền đơn giản hơn và đóng gọn trong `shutdown`.
3. **Pool thử lại một lần:** trong `ReadPool.connection`, nếu kết nối **lấy từ hàng rảnh** lỗi `psycopg.OperationalError` ngay ở lệnh đầu (`SET LOCAL ...`) thì đóng nó và mở kết nối mới một lần. Không thử lại khi lỗi xảy ra trong thân `yield` (không chạy lại truy vấn của người gọi).
4. Giữ nguyên mọi hành vi T46 khác (chế độ `file`, giữ kết quả AI khi ca không đổi, PII hành chính không cache).

## Nghiệm thu (dán kết quả)
- Test mới: làm mới lỗi giữ dữ liệu cũ và trả 200; lỗi ở lần nạp đầu vẫn báo lỗi; thử lại sau 15 giây; luồng thứ hai không bị chặn khi luồng thứ nhất đang làm mới (dùng `threading.Event` trong loader giả); pool thay kết nối rảnh hỏng.
- `uv run ruff check .`, `uv run ruff format --check` (tệp đã sửa), `uv run pytest -q --basetemp=.pytest_t46f` đều qua.
- Báo cáo `plan/reports/T46-fix-1.md`.

## Cấm làm
Không commit/push, không ghi DB thật, không thêm thư viện, không dùng `&`, xóa `.pytest_t46f*` sau khi chạy.
