# T88 – Trần chi phí LLM: chống nộp trùng, trần hàng đợi, giới hạn tốc độ, giới hạn kích thước (sửa C4, kèm L6)

Nguồn: `docs/bao-cao-bao-mat-2026-11-20.md` mục C4 và L6; `plan/plan-1.5-bao-mat-xac-thuc-phan-quyen.md` mục 8 (giới hạn tốc độ đang hoãn). Agent: agy `gemini-4-hydrogen-xhigh`. **Không gọi shell, không gọi mạng; chỉ đọc và ghi tệp.**

T86 (phân quyền theo ca) **đã hoãn**: mọi dược sĩ vẫn thấy chung danh sách ca, không thêm kiểm phạm vi. Brief này gộp thêm L5 (mục 3.5). Đọc mã hiện tại, đừng giả định theo báo cáo.

## 1. Bối cảnh

- `POST /api/cases/{id}/ai` với `{"chay_lai": true}`: `AiJobManager.start` (`app/orchestration/jobs.py`) mỗi lần đều `submit` thêm một việc; việc cũ không huỷ, vẫn gọi LLM. 1.000 lần gọi = 1.000 lượt LLM xếp hàng, hàng đợi không trần.
- `POST /ask`: `lich_su` không giới hạn phần tử, `ChatMessage.noi_dung` không giới hạn độ dài.
- Không có giới hạn theo người dùng hay trần theo ngày.

## 2. Phạm vi tệp

Được tạo: `app/api/rate_limit.py`, `tests/api/test_llm_limits.py`, `tests/orchestration/test_jobs_limits.py`.

Được sửa: `app/orchestration/jobs.py`, `app/api/schemas.py`, `app/api/service.py`, `app/api/routes.py`, `app/api/main.py` (chỉ phần xử lý lỗi để giữ tiêu đề `Retry-After`), `.env.example` (thêm biến mục 3.3), `web/src/state/useChat.ts`, test web tương ứng của `useChat` nếu có (tìm trong `web/src`), `plan/api-hop-dong-v1.md` **không** sửa — ghi thay đổi hợp đồng vào báo cáo để Claude cập nhật.

**Cấm đụng:** `app/auth/`, `db/`, `docker-compose.yml`, `app/config/settings.py`, mọi tệp khác.

## 3. Yêu cầu

### 3.1 `AiJobManager`

- `start(..., restart=True)` khi ca đang `dang_chay` → trả trạng thái hiện có, **không** `submit` thêm. `restart` chỉ có tác dụng khi việc trước đã `xong` hoặc `loi`.
- Đếm số việc chưa xong (đang chạy + chờ). Vượt `max_pending` (mặc định 6, tham số khởi tạo) → ném `AiQueueFullError` (lớp mới trong `jobs.py`), không đổi trạng thái ca.
- Giữ cơ chế thế hệ hiện có.

### 3.2 Giới hạn kích thước (`schemas.py`)

- `ChatMessage.noi_dung`: `max_length=4000`. `GuiCauHoi.lich_su`: tối đa **6** phần tử (`Field(max_length=6)`).
- `GuiCauHoi.nhan_dinh_id`, `GuiPhanHoi.nhan_dinh_id`: `max_length=128`. `GuiPhanHoi.nhom_ly_do`: 64. `GuiPhanHoi.ly_do`: 1000.
- `TinhCongThucYeuCau.dau_vao`: tối đa 30 khoá, mỗi khoá ≤ 64 ký tự, giá trị chuỗi ≤ 200 ký tự (validator).
- Vượt → 422 theo xử lý lỗi kiểm dữ liệu hiện có.

### 3.3 Giới hạn tốc độ và trần ngày (`app/api/rate_limit.py`)

- `class SlidingWindowLimiter` thuần Python, an toàn luồng, đồng hồ tiêm được: `def hit(self, key: str) -> float | None` – trả `None` nếu được phép (và ghi nhận), hoặc số giây phải chờ.
- `class DailyBudget`: đếm lượt LLM theo ngày giờ Việt Nam (`app/db/timezone.py`), toàn hệ thống; `def take(self) -> bool`. Qua ngày mới thì đặt lại.
- Cấu hình bằng biến môi trường (đọc một lần khi dựng `CaseService`, giá trị sai → dùng mặc định và log cảnh báo):
  - `LLM_ASK_PER_5MIN` mặc định 20 (theo người dùng, cho `/ask` và `/cases/{id}/ask`).
  - `LLM_AI_PER_HOUR` mặc định 15 (theo người dùng, chỉ tính khi thực sự nộp việc AI mới).
  - `LLM_DAILY_CALLS` mặc định 600 (toàn hệ thống, cả hỏi đáp và AI).
- Áp trong `CaseService`, **sau** khi đã kiểm ca tồn tại (`_get_case`) và **chỉ** khi sắp gọi LLM thật (khi AI tắt, câu trả lời "chưa sẵn sàng", hay trả trạng thái AI đã có thì không tính). `CaseService` nhận tham số tiêm `limits` cho test.
- Vượt → `HTTPException(429, detail={"ma": "vuot_gioi_han", "thong_bao": "…"}, headers={"Retry-After": "<giây làm tròn lên>"})`. Trần ngày → `ma: "het_ngan_sach_ngay"`. `AiQueueFullError` → 429 `ma: "hang_doi_day"`, `Retry-After: 30`.
- `main.py`: trình xử lý `HTTPException` hiện có phải giữ `exc.headers` (hiện đang dựng lại thân lỗi; kiểm và sửa để `Retry-After` không mất).
- Ghi log mỗi lần chặn: chỉ `ma`, đường dẫn mẫu, 8 ký tự đầu của `nguoi_dung_id`; không log câu hỏi.

### 3.4 Web (`useChat.ts`)

`toHistory` chỉ gửi **6 tin cuối**, mỗi `noi_dung` cắt còn 4000 ký tự. Nhận 429 thì hiện thông báo thân thiện có số giây chờ (đọc cách hàm khách API hiện có trả lỗi; không thêm thư viện, không `innerHTML`).

### 3.5 Đoạn nguồn hỏi đáp tách theo người dùng (L5)

- Hiện `_ask_sources["__global__"]` dùng chung: đoạn nguồn A hỏi được thì B mở được qua `GET /cases/__global__/sources/{id}`. Đổi khoá thành `f"__global__:{principal.nguoi_dung_id}"` cả khi ghi (trong `ask`) lẫn khi đọc (`get_source` nhận thêm `principal`, `routes.py` truyền xuống).
- Giữ tối đa 200 đoạn mỗi khoá (cả khoá theo ca), bỏ đoạn cũ nhất khi vượt.

## 4. Bảo mật

- Không vòng lặp, không hàng đợi không trần. Không nộp việc LLM trùng cho cùng ca.
- Bộ đếm trong RAM (một worker) là chấp nhận được; ghi trong báo cáo hạn chế khi chạy nhiều worker.
- Không log nội dung câu hỏi, token, khoá.

## 5. Test

`tests/orchestration/test_jobs_limits.py` (dùng `threading.Event` để giữ việc đang chạy, không `sleep` dài):
1. Gọi `start(restart=True)` 50 lần khi ca đang chạy → hàm giả chạy đúng **1** lần.
2. Sau khi xong, `restart=True` → chạy lần 2.
3. 7 ca khác nhau với `max_pending=6` → ca thứ 7 ném `AiQueueFullError`.

`tests/api/test_llm_limits.py` (TestClient, `AUTH_MODE=off`, `CASE_SOURCE=file`, `asker`/`ai_runner` giả đếm lượt, đồng hồ giả):
4. `lich_su` 7 phần tử → 422; `noi_dung` 4001 ký tự → 422; `ly_do` 1001 ký tự → 422; `dau_vao` 31 khoá → 422.
5. `LLM_ASK_PER_5MIN=3`: lượt 4 → 429, có `Retry-After`, thân `ma = vuot_gioi_han`; asker giả đếm đúng 3. Tiến đồng hồ 5 phút → lại được.
6. Hai người dùng khác nhau có hạn mức riêng (dựng `AUTH_MODE` bắt buộc với `Authenticator` giả trả hai `Principal` theo token, làm theo `tests/api/test_auth_ownership.py`).
10. L5: A hỏi `POST /api/ask` (asker giả trả 1 đoạn) → A mở `GET /api/cases/__global__/sources/{id}` được 200, B mở → 404. Ghi 201 đoạn vào một khoá → còn 200, đoạn đầu tiên đã bị bỏ.
7. `LLM_DAILY_CALLS=2` → lượt 3 → 429 `het_ngan_sach_ngay`.
8. `POST /ai` `chay_lai=true` lặp 20 lần khi đang chạy → `ai_runner` giả chạy 1 lần, không 429.
9. Khi AI tắt, gọi `/ask` 50 lần → không 429 (không tính lượt).

Web: test `toHistory` cắt 6 tin và 4000 ký tự (vitest, đặt cạnh test hiện có của `useChat` nếu có).

## 6. Nghiệm thu (Claude chạy)

```
uv run ruff check .
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider
cd web && npx tsc -b --noEmit && npx oxlint && npx vitest run
```

## 7. Cấm

- Không cài gói (không `slowapi`, không Redis). Không sửa tệp ngoài mục 2.

## 8. Báo cáo

`plan/reports/T88.md` theo mẫu `AGENTS.md`, kèm mục "Thay đổi hợp đồng API" (trường giới hạn mới, mã lỗi 429 mới) để Claude cập nhật `plan/api-hop-dong-v1*.md`.
