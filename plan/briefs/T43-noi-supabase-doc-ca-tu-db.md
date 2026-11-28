# T43 – Backend đọc ca bệnh từ Supabase (thay tệp mock)

## Bối cảnh
Supabase đã có dữ liệu (nạp bằng `uv run python -m app.db all --reset --yes`): 66 người bệnh (6 ca demo + 60 hồ sơ giả lập), 93 đợt điều trị, 228 y lệnh, 233 dòng chi tiết, 217 lịch dùng, v.v. Lược đồ ở `db/schema.sql`, ánh xạ ghi ở `app/db/mapping.py`, `sources.py`, `engine.py`, `cli.py`.

Hiện `app/api/service.py` (`CaseService`) lấy ca từ `PipelineReviewService(case_dir, ...)` trong `app/ui/services.py` (hàm `list_cases() -> (list[CaBenh], list[(tên, lỗi)])` đọc tệp JSON trong `config/settings.yaml: app.case_dir` = `data/mock/demo`). Cần chuyển nguồn sang DB, giữ nguyên hợp đồng API.

## Một "ca" là gì (giữ đúng định nghĩa đang dùng)
Mỗi y lệnh có `ca_id` khác rỗng trong `nghiep_vu.y_lenh` là một ca (1 ca mỗi hồ sơ: mã `HS-xxx` hoặc `DEMO-xx`). `CaBenh` của ca được dựng từ: người bệnh; **đợt điều trị chứa y lệnh đó** (đợt cuối của hồ sơ); chẩn đoán, sinh hiệu, xét nghiệm, vi sinh (kèm kháng sinh đồ), diễn biến của đợt đó; `thuoc_dang_dung` = các dòng chi tiết `active` của **các y lệnh khác** trong đợt (xem view `nghiep_vu.v_thuoc_dang_dung`, hoặc tự chọn bằng join); `y_lenh_cho_duyet` = chính y lệnh có `ca_id`; `danh_muc_thuoc`/`danh_muc_hoat_chat` suy từ các thuốc xuất hiện. Tham chiếu cách dựng ngược lại ở hàm `_nap_ca_benh` trong `tools/kiem_ho_so_gia_lap.py` (hồ sơ JSON → khung nhìn `CaBenh`) và cách nạp xuôi ở `app/db/mapping.py`.

## Phạm vi file
Được tạo/sửa:
- `app/db/reader.py` (mới): lớp đọc DB, hàm thuần dựng `CaBenh` từ các hàng DB (tách thành hàm dễ test, không cần kết nối), và hàm truy vấn chỉ-đọc.
- `app/api/service.py`, `app/api/main.py`, `app/config/settings.py`: chọn nguồn bằng biến môi trường `CASE_SOURCE` = `db` hoặc `file`. **Mặc định `file`** (giữ nguyên hành vi hiện tại khi chưa đặt). Khi `db`, dùng `DbReviewService` (cùng giao diện `ReviewService`: `list_cases`, `review`).
- `tests/db/test_reader.py` (mới), `tests/api/` (thêm test chọn nguồn).
- `.env.example` (thêm dòng `CASE_SOURCE=file`, chú thích), `db/README.md` (một mục ngắn về nguồn đọc).

Cấm đụng: `db/schema.sql`, `app/db/mapping.py`, `app/db/sources.py`, `app/db/engine.py`, `app/db/cli.py` (có việc khác sau), `data/`, `web/`, `config/settings.yaml`, `.env`.

## Yêu cầu
1. `DbReviewService.list_cases()` đọc DB một lần mỗi tiến trình (hoặc bộ nhớ đệm có thể làm mới), trả ra 66 ca, sắp theo `ca_id`; lỗi dựng từng ca gom vào danh sách lỗi như loader tệp, không làm hỏng cả danh sách.
2. Đọc chỉ-đọc: mở kết nối với `default_transaction_read_only`, chỉ SELECT. Chuỗi kết nối lấy qua `get_secret("DATABASE_URL")` (không đọc `os.environ` ngoài `app/config/`, có test kiến trúc cấm). Không ghi log chuỗi kết nối hay dữ liệu người bệnh.
3. Dùng `psycopg` đã có trong `pyproject.toml`; tránh N+1 truy vấn (mỗi bảng một truy vấn theo danh sách `dot_dieu_tri_id`, rồi gom trong bộ nhớ).
4. Khi `CASE_SOURCE=db` mà thiếu `DATABASE_URL` hoặc không kết nối được: `/api/health` vẫn trả 200, các API ca trả lỗi thống nhất của API (không lộ thông tin kết nối), có thông điệp tiếng Việt rõ.
5. Tính đúng đắn: với mỗi ca, `CaBenh` dựng từ DB phải **bằng** `CaBenh` dựng từ tệp nguồn tương ứng (`data/mock/demo/*.json` và khung nhìn của `data/mock/hoso_gia_lap/*.json` như `_nap_ca_benh`), so bằng `model_dump(mode="json")`. Viết test không cần kết nối DB: dùng `app/db/mapping.py` biến tệp thành hàng DB trong bộ nhớ rồi qua hàm dựng của `reader.py`, so với `CaBenh` từ tệp. Khác biệt chấp nhận được (thứ tự danh sách, chuẩn hóa mã hoạt chất `HC-…`, đường dùng/đơn vị chuẩn hóa khi nạp) phải nêu rõ trong báo cáo và được test cố định.
6. Thêm lệnh kiểm trực tiếp trên Supabase thật (chỉ đọc), ví dụ `uv run python -m app.db verify-read`: dựng 66 ca từ DB và so với dựng từ tệp (cùng quy tắc mục 5), in số ca khớp/lệch. Dùng được ngay khi `DATABASE_URL` có trong `.env`. Chạy lệnh này và dán kết quả vào báo cáo.
7. Hợp đồng API và schema Pydantic (`app/api/schemas.py`, `plan/api-hop-dong-*.md`) không đổi. Giao diện web không đổi trong task này.
8. Đường lui: `CASE_SOURCE=file` cho đúng hành vi cũ (840 test hiện có vẫn qua).

## Nghiệm thu
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -q --basetemp=.pytest_tmp` đều sạch (hiện 840 test qua; thêm test mới).
- `uv run python -m app.db verify-read`: 66/66 ca khớp (hoặc liệt kê rõ các khác biệt được chấp nhận).
- Chạy thử thật: `CASE_SOURCE=db AUTH_MODE=off uv run uvicorn app.api.main:app --port 8010`, gọi `GET /api/cases` (cần `AUTH_MODE=off` chỉ cho kiểm cục bộ), xác nhận trả 66 ca và `GET /api/cases/HS-022` trả chi tiết đủ; ghi vào báo cáo rồi tắt tiến trình.
- Báo cáo `plan/reports/T43.md`.

## Cấm làm
- Không commit, không push, không ghi vào DB, không `--reset`.
- Không in/chép giá trị trong `.env` ra báo cáo hay log.
- Không thêm thư viện mới. Xóa tệp tạm (`.pytest_tmp*`).
