# T86 – Phân quyền theo ca bệnh (sửa C1: IDOR / BOLA)

> **HOÃN (20/11/2026, người dùng chốt).** Chưa rõ cách khoa Dược phân công thật: dược sĩ có thể làm ca của người khác khi quá tải. Giữ chính sách plan 1.5 mục 3.2 (mọi dược sĩ thấy chung danh sách ca), nhật ký truy cập vẫn ghi ai xem ca nào. Phần L5 (đoạn nguồn hỏi đáp chung dùng chung giữa người dùng) chuyển sang T88. Không giao brief này cho đến khi có câu trả lời của dược sĩ về phân công; khi đó cân nhắc lại 3 cách: bảng `phan_cong`, `app_metadata` Supabase, hoặc giữ chung.

Nguồn: `docs/bao-cao-bao-mat-2026-11-20.md` mục C1 (đọc mục đó trước). Agent: agy `gemini-4-hydrogen-xhigh`. **Không gọi shell, không gọi mạng; chỉ đọc và ghi tệp.** Claude tự chạy test khi review.

## 1. Bối cảnh

Sau đăng nhập, backend chỉ kiểm **vai trò** (`duoc_si_ls` / `admin`), không kiểm **ca có thuộc phạm vi người gọi không**. Đổi `DEMO-02` thành `DEMO-03` trên URL là xem được người bệnh khác, ghi phản hồi, chạy AI trên ca đó.

Mục tiêu: mỗi người dùng chỉ thấy và thao tác các ca được **phân công** (theo khoa điều trị hoặc theo từng ca). Ca ngoài phạm vi trả **404** giống ca không tồn tại.

## 2. Phạm vi tệp

Được tạo:
- `app/auth/scope.py` – mô hình phân công, nguồn phân công, hàm kiểm.
- `tests/api/test_case_scope.py` – test truy cập chéo.
- `tests/auth/test_scope.py` – test đơn vị cho `scope.py`.
- `data/mock/demo/phan_cong.example.json` – tệp mẫu (dữ liệu giả, không tên người thật).

Được sửa:
- `app/api/service.py`, `app/api/routes.py`.
- `db/schema.sql` – chỉ **thêm** bảng `nghiep_vu.phan_cong` ở cuối khối `nghiep_vu`, không sửa bảng khác.
- `.env.example` – thêm `CASE_SCOPE`, `PHAN_CONG_PATH` kèm chú thích.
- Test cũ trong `tests/api/` **chỉ khi** chúng hỏng vì thay đổi này; ghi rõ trong báo cáo từng test đã sửa và lý do.

**Cấm đụng:** `app/api/main.py`, `app/api/schemas.py`, `app/orchestration/jobs.py`, `docker-compose.yml`, `app/config/settings.py` (T87, T88 đang/ sẽ sửa các tệp này), `web/`, `docs/`, `plan/`.

## 3. Yêu cầu

### 3.1 Bảng phân công (`db/schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS nghiep_vu.phan_cong (
    phan_cong_id bigserial PRIMARY KEY,
    nguoi_dung_id text NOT NULL,          -- sub của JWT Supabase
    khoa_dieu_tri text,                   -- khớp CaBenh.dot_dieu_tri.khoa_dieu_tri
    ca_id text,                           -- hoặc một ca cụ thể
    tu_ngay date,                         -- NULL = không giới hạn đầu
    den_ngay date,                        -- NULL = không giới hạn cuối, tính cả ngày den_ngay
    ghi_chu text,
    tao_luc timestamptz NOT NULL DEFAULT now(),
    CHECK ((khoa_dieu_tri IS NOT NULL) <> (ca_id IS NOT NULL)),
    CHECK (den_ngay IS NULL OR tu_ngay IS NULL OR den_ngay >= tu_ngay)
);
CREATE INDEX IF NOT EXISTS phan_cong_nguoi_dung ON nghiep_vu.phan_cong (nguoi_dung_id);
```

### 3.2 `app/auth/scope.py`

- `class Assignment(BaseModel)`: `nguoi_dung_id`, `khoa_dieu_tri: str | None`, `ca_id: str | None`, `tu_ngay: date | None`, `den_ngay: date | None`; validator bắt đúng một trong `khoa_dieu_tri` / `ca_id`.
- `class AssignmentSource(Protocol)`: `def for_user(self, nguoi_dung_id: str) -> list[Assignment]`.
- Ba cài đặt:
  - `DbAssignmentSource` – `SELECT … FROM nghiep_vu.phan_cong WHERE nguoi_dung_id = %s` (tham số hoá, **không** f-string). Dùng cùng cách lấy kết nối mà `app/db/reader.py` đang dùng (đọc `app/db/read_pool.py`). Lỗi DB → ném lỗi đọc DB hiện có của dự án (`DatabaseReadError`), **không** coi là "thấy tất cả".
  - `FileAssignmentSource(path)` – đọc JSON dạng `{"phan_cong": [ {…Assignment…} ]}`; tệp không có → danh sách rỗng (không thấy ca nào), ghi log cảnh báo một lần, không in đường dẫn tuyệt đối của máy.
  - `StaticAssignmentSource(list[Assignment])` – cho test.
- `class CaseScope` bọc nguồn + bộ đệm theo người dùng, TTL 60 giây (đồng hồ tiêm được cho test):
  - `def allows(self, principal: Principal, case: CaBenh, today: date) -> bool` – đúng khi có ít nhất một phân công còn hiệu lực ngày `today` (giờ Việt Nam, dùng `app/db/timezone.py`) khớp `case.ca_id` hoặc `case.dot_dieu_tri.khoa_dieu_tri` (so sánh chính xác sau `strip()`).
  - `def filter(self, principal, cases) -> list[CaBenh]`.
- Chế độ (`CASE_SCOPE` trong môi trường):
  - `phan_cong` (mặc định) – áp phân công như trên. **Vai trò `admin` cũng chỉ thấy ca được phân công**, không tự động thấy tất cả.
  - `tat_ca` – không lọc. **Chỉ được nhận khi `AUTH_MODE=off`**; nếu `AUTH_MODE` khác `off` mà đặt `tat_ca` thì ghi log cảnh báo và dùng `phan_cong`. Khi `AUTH_MODE=off` và không đặt `CASE_SCOPE` thì mặc định `tat_ca` (để test cũ và chạy cục bộ không đổi hành vi).
  - Giá trị khác → lỗi cấu hình lúc khởi tạo.
- Chọn nguồn: `CASE_SOURCE=db` → `DbAssignmentSource`; ngược lại `FileAssignmentSource(PHAN_CONG_PATH hoặc data/runtime/phan_cong.json)`.

### 3.3 `CaseService` (`app/api/service.py`)

- Thêm tham số khởi tạo `case_scope: CaseScope | None = None`; `None` → tự dựng theo 3.2. Không sửa `main.py`.
- Một hàm duy nhất `_authorize(self, principal, case_id) -> CaBenh`: gọi `_get_case`, rồi nếu `not scope.allows(...)` → `HTTPException(404, "Không tìm thấy ca bệnh.")` **giống hệt** thông báo ca không tồn tại. Không phân biệt 403.
- Mọi phương thức công khai có `case_id` nhận thêm `principal` và gọi `_authorize` **trước** mọi việc khác (trước `_review`, trước nộp AI, trước đọc DB): `get_case`, `list_review_history`, `get_record`, `feedback`, `start_ai`, `get_ai`, `get_source`, `ask`, `clear_conversation` (với `case_id != "__global__"`).
- `list_cases(principal)`: chỉ trả ca trong phạm vi; `_review` chỉ chạy cho ca trong phạm vi.
- `ask("__global__", …)`: chỉ đưa vào LLM các ca trong phạm vi người gọi. Không có ca nào → vẫn trả lời bằng kho tài liệu như hiện tại nhưng **không** dùng `all_cases[0]` của người khác làm `fallback_case`.
- Đoạn nguồn hỏi đáp chung (`_ask_sources["__global__"]`) hiện dùng chung giữa người dùng (báo cáo mục L5): đổi khoá thành `f"__global__:{principal.nguoi_dung_id}"` cả khi ghi lẫn khi `get_source("__global__", …)` đọc. Giữ tối đa 200 đoạn mỗi khoá (bỏ đoạn cũ nhất khi vượt), áp cho cả khoá theo ca.
- `list_conversations(principal)`: bỏ các phạm vi là ca mà người gọi không còn quyền (giữ `__global__`).

### 3.4 `routes.py`

Truyền `principal` xuống mọi lời gọi trên. Không đổi đường dẫn, mã trạng thái thành công hay thân trả về.

### 3.5 Tệp mẫu `phan_cong.example.json`

Hai người dùng giả `user-a` (khoa của `DEMO-01`) và `user-b` (một `ca_id` khác khoa). Đọc khoa thật của ca từ `data/mock/demo` qua tài liệu `docs/du-lieu/` trước, không đoán.

## 4. Bảo mật (bắt buộc)

- Ai gọi: `duoc_si_ls`, `admin` (giữ như cũ) **và** phải có phân công.
- Ca ngoài phạm vi: 404, cùng thân lỗi với ca không tồn tại; không tốn lượt LLM, không chạy luật, không đọc DB hồ sơ.
- Lỗi đọc bảng phân công → đóng (từ chối), không mở.
- Không ghi `nguoi_dung_id` đầy đủ vào log ở mức INFO mới; log hiện có của `access_log.py` giữ nguyên.
- SQL tham số hoá.

## 5. Test bắt buộc

`tests/api/test_case_scope.py` (dùng `create_app(service=…, auth=…)` với `Authenticator` giả trả hai `Principal` khác nhau theo token; xem cách `tests/api/test_auth_ownership.py` dựng môi trường `AUTH_MODE` bắt buộc và làm theo; nạp ca qua `app.db.reader.load_source_cases(ROOT)` hoặc thư mục `data/mock/demo`, **không** nạp thẳng `HS-*.json`, không đếm tệp `_kich_ban.json`; `ai_runner`, `asker` là bản giả không gọi mạng):

1. A chỉ thấy ca của mình trong `GET /api/cases`; B thấy ca của B.
2. Với một ca của B, A gọi **từng** điểm cuối sau → đều 404 và thân lỗi giống ca không tồn tại: `GET /cases/{id}`, `GET /cases/{id}/lich-su-tham-dinh`, `GET /cases/{id}/records/{ban_ghi_id}`, `POST /cases/{id}/feedback`, `POST /cases/{id}/ai`, `GET /cases/{id}/ai`, `GET /cases/{id}/sources/{x}`, `POST /cases/{id}/ask`, `POST /conversations/{id}/clear`. Viết dạng `pytest.mark.parametrize`.
3. Bản giả `ai_runner` / `asker` đếm số lần gọi: sau bước 2 vẫn **0**.
4. `POST /api/ask` của A: danh sách ca truyền vào `asker.ask_global` chỉ gồm ca của A.
5. Đoạn nguồn hỏi đáp chung của A: B gọi `GET /cases/__global__/sources/{id}` → 404.
6. `admin` không có phân công → `GET /api/cases` rỗng.
7. Phân công hết hạn (`den_ngay` hôm qua) → không thấy.
8. `AUTH_MODE` bắt buộc + `CASE_SCOPE=tat_ca` → vẫn lọc theo phân công.
9. Nguồn phân công ném lỗi DB → `GET /api/cases` không trả ca nào của ai (lỗi 503 theo cách xử lý `DatabaseReadError` hiện có, hoặc rỗng; ghi rõ chọn cách nào).

`tests/auth/test_scope.py`: khớp khoa, khớp ca, ranh giới ngày (`tu_ngay` = hôm nay thấy, `den_ngay` = hôm nay thấy), bộ đệm TTL, validator đúng-một-trong-hai.

## 6. Nghiệm thu (Claude chạy)

```
uv run ruff check .
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider
uv run pytest -q -p no:cacheprovider tests/api/test_case_scope.py tests/auth/test_scope.py
```

Toàn bộ test cũ phải qua (với `AUTH_MODE=off` mặc định `tat_ca`).

## 7. Cấm

- Không cài gói, không thêm phụ thuộc.
- Không sửa tệp ngoài mục 2. Không tự chạy `schema.sql` lên DB; không gọi MCP.
- Không đổi mã ca hiển thị sang mã ngẫu nhiên (việc phụ, làm sau).

## 8. Báo cáo

Ghi `plan/reports/T86.md` theo mẫu "Khi xong" của `AGENTS.md`, thêm danh sách mọi phương thức đã gắn `_authorize` và mọi test cũ đã sửa.
