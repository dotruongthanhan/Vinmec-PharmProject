# T46 – Ổn định backend đọc DB, làm mới dữ liệu và các lỗi nhỏ backend

Mô hình: Codex `gpt-6.2-sol`, effort `high` (đã kiểm chạy được trên Codex CLI 0.170.0). Chạy bằng chế độ nền của app, không dùng `&`. **Không dừng giữa chừng để hỏi**: gặp điểm chưa rõ thì chọn cách ít rủi ro nhất, ghi vào báo cáo mục "Lựa chọn đã làm".

## Phạm vi file
Được sửa/tạo: `app/api/service.py`, `app/api/schemas.py`, `app/api/presenter.py`, `app/api/routes.py` (nếu cần), `app/api/main.py` (đóng pool), `app/db/*`, `db/schema.sql`, `db/README.md`, `tests/`, `plan/api-hop-dong-v1.4-ho-so-y-lenh-phieu.md`, `plan/reports/T46.md`.
Cấm đụng: `web/`, `data/mock`, `data/gold`, pipeline AI (`app/pipeline.py`, `app/orchestration`, `app/llm`, `config/prompts`), `.env`. Hợp đồng API chỉ thêm trường, không đổi tên hay xóa trường (trừ mục 9).

## Việc cần làm

### A. Độ ổn định khi đọc Supabase
1. `service.py` `list_cases` (khoảng dòng 227–235) đang giữ `self._lock` trong lúc gọi `administrative.read_administrative` (chờ mạng). Chụp danh sách ca trong khóa, **đọc DB ngoài khóa**. `get_case` cũng không được giữ khóa chung khi chờ mạng.
2. Thêm hạn thời gian truy vấn: kết nối chỉ-đọc dùng `options="-c default_transaction_read_only=on -c statement_timeout=8000"` ở cả ba chỗ đọc (`reader.py`, `administrative.py`, `medical_record.py`). Quá hạn thì trả `DatabaseReadError` như hiện nay (thông báo tiếng Việt, không lộ chuỗi kết nối). Lưu ý: bộ gộp kết nối của Supabase có thể bỏ qua tùy chọn lúc kết nối; nếu vậy thêm `SET statement_timeout` ngay sau khi mở kết nối.
3. Gộp kết nối: tạo **một bộ dùng chung nhỏ** (tối đa 3 kết nối cùng lúc, chỉ-đọc) trong `app/db`. Dùng `psycopg_pool` nếu đã có trong `pyproject.toml`; nếu chưa có thì **không thêm thư viện mới**, dùng semaphore giới hạn đồng thời kèm tái dùng kết nối an toàn theo luồng. Mục tiêu: nhiều tab cùng mở không vượt hạn mức kết nối của Supabase pooler (2–5). Đóng gọn khi API tắt (`_lifespan` ở `app/api/main.py`).
4. Dữ liệu hành chính (họ tên, ngày sinh, địa chỉ, SĐT) **vẫn không được vào bộ đệm** (có test `test_http_admin_is_uncached_and_never_logged`, giữ nguyên). Chỉ cache y lệnh và phiếu như hiện nay.

### B. Làm mới dữ liệu
5. `service.py`/`reader.py`: danh sách ca (`_cases`) và kết quả thẩm định (`_results`) đang giữ vĩnh viễn, không ai gọi `DbReviewService.refresh()`. Thêm **TTL** cho nguồn DB (mặc định 60 giây; biến môi trường tùy chọn `CASE_CACHE_TTL_SECONDS`, kẹp trong 10–600, đọc qua `app/config/settings.py`). Khi hết hạn và có yêu cầu tới: làm mới danh sách ca từ DB (ngoài khóa), **xóa kết quả thẩm định luật của ca có dữ liệu đổi**, nhưng **không xóa kết quả AI đang chạy hoặc đã xong của ca mà `CaBenh` không đổi** (so sánh `model_dump` của ca trước và sau). Ca mới xuất hiện tự có, ca bị xóa khỏi DB trả 404 đúng hợp đồng.
6. Chế độ `CASE_SOURCE=file` giữ nguyên (không TTL, không đổi hành vi).
7. `GET /api/cases` thêm trường tùy chọn `lam_moi_luc` (ISO có +07:00) chỉ ở chế độ DB: thời điểm danh sách ca được làm mới gần nhất. Chỉ thêm trường.

### C. Lỗi nhỏ backend
8. Giờ phản hồi hiện UTC: `PhanHoi.thoi_diem = datetime.now(UTC)` (khoảng `service.py:534`) đi qua `format_dt` (`presenter.py` ~108, ~179) không đổi múi giờ. Đổi **hiển thị** về `Asia/Ho_Chi_Minh` (dùng `app/db/timezone.VN_TZ`), không đổi giá trị lưu.
9. `schemas.TreatmentSheet` (và mọi mô hình API) không được trả `nguon_tep` và `nap_luc`. Bỏ hai trường này khỏi phản hồi; cập nhật `plan/api-hop-dong-v1.4-ho-so-y-lenh-phieu.md` ghi rõ đã bỏ. (Giao diện web sửa ở task khác; ở đây chỉ bỏ ở backend và nêu trong báo cáo.)
10. `engine.load_treatment_sheets`: trong cùng một giao dịch, **xóa** các dòng `phieu_y_lenh` và `phieu_dieu_tri` của các đợt có trong lô nạp rồi mới ghi lại, để sinh lại phiếu không để sót dòng cũ. `--dry-run` giữ nguyên. Thêm test.
11. `db/schema.sql`: sửa ghi chú "áp dụng lại an toàn" cho đúng (chỉ đúng cho cột T45); thêm vào `db/README.md` mục "Nâng cấp từ DB cũ" nêu rõ phải `reset --yes` nếu DB còn lược đồ trước T40.
12. `app/db/cli.py`: ở đầu `main`, `sys.stdout.reconfigure(encoding="utf-8")` (và stderr) như `reader.main`, để không báo "UnicodeEncodeError" giả khi chuyển hướng đầu ra trên Windows.
13. `administrative.py` (~43–50): thêm `ORDER BY chan_doan_id` khi lấy `chan_doan_chinh`, và chọn chẩn đoán chính ổn định, cùng quy tắc với `list_cases`.
14. `medical_record.py`: nhánh `patient_ids is None` phải qua `to_vn_time`; `verify_ho_so` bỏ phần cứng `HS-022 == 7`, thay bằng đối chiếu số y lệnh với dữ liệu nguồn của từng ca.

## Nghiệm thu (chạy và dán kết quả)
- `uv run ruff check .`, `uv run ruff format --check` (các tệp T46), `uv run pytest -q --basetemp=.pytest_t46` đều qua (hiện 962 test; thêm test cho: đọc DB ngoài khóa, TTL làm mới, giữ kết quả AI khi ca không đổi, xóa kết quả luật khi ca đổi, bỏ trường `nguon_tep`, xóa phiếu cũ khi nạp lại, giờ phản hồi +07:00).
- `uv run python -m app.db.reader verify-read` (kết nối thật, chỉ đọc) vẫn **66/66 ca khớp**. Codex có thể không kết nối được DB thật từ môi trường của nó; khi đó ghi rõ và Claude sẽ chạy.
- `uv run python -m app.db all --dry-run`, `hanh-chinh --dry-run`, `phieu-dieu-tri --dry-run` đều 0 dòng loại.
- Báo cáo `plan/reports/T46.md`.

## Cấm làm
- Không commit/push, không ghi DB thật, không `--reset`, không đụng `.env`, không in giá trị bí mật.
- Không thêm thư viện. Không dùng `&`. Xóa tệp tạm của bạn (`.pytest_t46*`).
