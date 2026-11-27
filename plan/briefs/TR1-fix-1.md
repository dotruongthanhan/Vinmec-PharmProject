# TR1-fix-1 – Che số dài trong log lý do chặn; ngắt sớm khi DB không trả lời

Người làm: Codex gpt-6.1-terra high (được chạy ruff, pytest; không cài gói, không mạng, không commit).
Đọc: `AGENTS.md`, `plan/briefs/TR1-bao-cao.md`, `app/tracing/sanitize.py`, `app/orchestration/ask.py`, `app/deid/known.py`, `app/db/administrative.py`, `app/db/reader.py`, mô-đun `read_pool` mà hai tệp này dùng.

## 1. Log lý do chặn (bảo mật)

`app/orchestration/ask.py:177` ghi `ask rejected step=%s reason=%s` với `reason` như `so_khong_co_nguon:<số>`, chép nguyên số trong câu trả lời của LLM; nếu LLM nhắc lại SĐT/CCCD thì chữ số lọt vào log. Áp đúng quy tắc của tracer (số ≤ 4 chữ số giữ nguyên, dài hơn → `#<n>`), **dùng lại hàm của `app/tracing/sanitize.py`**, cho mọi chỗ log mã lý do chặn/kiểm chứng trong `app/` (tìm bằng `grep -rn "reason=\|ly_do=" app`). Test: log có `so_khong_co_nguon:0912345678` → bản ghi log chứa `#10`, không chứa `0912345678` (dùng `caplog`).

## 2. Ngắt sớm khi DB không trả lời (hiệu năng)

Tracer đo được: khi đường hầm RDS đóng, bước che PII mất **10,2 s / 12,5 s** mỗi câu vì đọc hành chính qua DB chờ hết thời hạn kết nối rồi mới rơi về đường lui. Yêu cầu:
- Thời hạn kết nối của các lần **đọc** DB trong luồng hỏi đáp (hành chính, đọc ca) cấu hình được, mặc định **3 s** (`db.thoi_han_ket_noi_giay` trong `config/settings.yaml`).
- **Cầu dao:** lỗi kết nối (không phải lỗi truy vấn) thì ghi nhớ "DB không sẵn" trong **60 s** (`db.cau_dao_giay`); trong thời gian đó các lần đọc ném ngay lỗi như cũ (để đường lui hiện có chạy) mà không thử kết nối. Hết 60 s thì thử lại một lần. Thread-safe.
- Không đổi hành vi khi DB sẵn; không đổi thứ tự đường lui; không nuốt lỗi truy vấn.
- Log cảnh báo một lần khi cầu dao bật, một lần khi đóng lại; không log URL hay mật khẩu.
- Test (không cần DB thật): kết nối giả ném `OperationalError` → lần 1 gọi kết nối, lần 2 trong 60 s không gọi (đồng hồ giả), sau 60 s gọi lại; lỗi truy vấn không bật cầu dao; thời hạn đọc từ cấu hình.

## Tệp

Được sửa: `app/orchestration/ask.py` (chỉ chỗ log), các tệp `app/**` khác có log mã lý do, `app/tracing/sanitize.py` (nếu cần xuất hàm), `app/db/read_pool*` hoặc nơi tạo kết nối đọc, `app/db/administrative.py`, `app/db/reader.py`, `app/config/settings.py`, `config/settings*.yaml`, test mới trong `tests/db/`, `tests/orchestration/`. Báo cáo `plan/briefs/TR1-fix-1-bao-cao.md`.
Cấm: đổi logic trả lời, sửa `web/**`, `data/**`, `.env`; cài gói; mạng; commit. Dùng `--basetemp` trong `%TEMP%`, **không** tạo thư mục tạm trong `tests/`.

## Nghiệm thu (Claude chạy)

```
uv run ruff check app tests && uv run ruff format --check app tests/db tests/orchestration tests/tracing
uv run pytest -q -p no:cacheprovider tests/db tests/orchestration tests/tracing tests/deid tests/agent
```
Claude kiểm độc lập: đường hầm RDS đóng, chạy 2 câu `HD-CA-011`, `HD-CA-015` hai lần liên tiếp; span `che_pii` lượt đầu ≤ 3,5 s, các lượt sau < 0,5 s; log không có chuỗi số > 4 chữ số sau `reason=`.
