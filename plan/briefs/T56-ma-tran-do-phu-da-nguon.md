# T56 – Ma trận độ phủ đa nguồn (plan 1.8 D0.8) và sửa truy cập biến môi trường của `publish.py`

Mô hình: Codex `gpt-6.1-sol`, effort `xhigh`. Không có mạng, không cần mạng.

Đọc trước:
- `AGENTS.md`
- `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md`: mục 3.2.3, **3.2.7**, 5.0
- `plan/reports/T52.md`, `plan/reports/T53.md`

**T55 đang chạy song song** (sửa `app/kb/interactions/**`, `app/rules/**`, `app/api/**`, `web/**`). Không đụng các tệp đó.

## 1. Sửa test kiến trúc đang trượt

`tests/architecture/test_import_boundaries.py::test_environment_access_only_in_config` trượt vì `app/kb/dictionary/publish.py:88` gọi `os.getenv("DATABASE_URL")`.

- Đổi sang cách các module khác đang dùng: `get_secret("DATABASE_URL")` của `app/config`, cùng `ConfigError` khi thiếu. Xem `app/db/reader.py:206` làm mẫu.
- Không đổi hành vi khác của `publish`.

## 2. Ma trận độ phủ đa nguồn: `python -m app.kb.coverage report`

Module mới `app/kb/coverage/`. Mỗi hoạt chất trên trục một dòng; trục đọc từ `data/kb_curated/tra_cuu/tra_cuu.sqlite`, bảng `hoat_chat`.

Ghi `data/kb_reports/do_phu_da_nguon.csv` (UTF-8 có BOM) và `data/kb_reports/do_phu_da_nguon.json` (tóm tắt).

| Cột | Cách lấy (chỉ đọc) |
|:--|:--|
| `hoat_chat_id`, `ten_inn`, `ten_viet`, `loai` | `tra_cuu.sqlite` |
| `so_che_pham_dav` | `thuoc_thanh_phan` trong `tra_cuu.sqlite` |
| `co_rxcui`, `ma_atc` | `tra_cuu.sqlite` |
| `ddinter_id`, `ddinter_cach_khop` | `tra_cuu.sqlite` |
| `ddinter_da_cao_du` | `data/kb_staging/ddinter/thuoc.jsonl`: số dòng thuốc–thuốc trong `tuong_tac_thuoc.jsonl` của thuốc đó bằng `tong_tuong_tac_tren_trang.tuong_tac_thuoc` |
| `so_doan_nhan_fda`, `set_id_nhan_fda` | **Đọc `hoat_chat_ids` của từng đoạn trong `data/kb_curated/chunks.jsonl`** (đoạn có `nguon == "openfda"`). **Không dò theo tên tệp nhãn**: đây chính là lỗi Claude mắc ở lần kiểm đầu, xem mục 3.2.7 |
| `co_ndc` | `data/kb_sources/openfda_ndc/*.json`: khớp `active_ingredients[].name` sau khi bỏ muối (`app/kb/names.py`) với `ten_inn` |
| `co_livertox`, `co_lactmed` | Nếu có `data/kb_sources/livertox/muc_luc.csv` / `data/kb_sources/lactmed/muc_luc.csv` (sub T54 đang tải; có thể chưa có) thì khớp tên chính xác sau chuẩn hoá. **Không có tệp thì để trống và ghi "chưa có nguồn"**, không báo lỗi |
| `trong_ca_gia_lap` | Hoạt chất xuất hiện qua bảng `chuyen_ma_ca` |
| `thieu` | Danh sách nguồn còn thiếu, theo bộ nguồn bắt buộc cấu hình được (mặc định: `dav`, `rxcui`, `atc`, `ddinter`, `nhan_fda`) |

Tóm tắt JSON:
- Đếm theo từng cột.
- Số hoạt chất đủ mọi nguồn bắt buộc.
- **Riêng nhóm `trong_ca_gia_lap`:** liệt kê từng hoạt chất thiếu, kèm nguồn thiếu.

Kết quả phải khớp số Claude đã kiểm tay ngày 19/11: trong 48 hoạt chất của ca, thiếu nhãn FDA đúng 4 (cefoperazone, sulbactam, gabapentin, penicillin_g); thiếu DDInter: penicillin_g, sulbactam; thiếu ATC: clavulanic_acid, valproic_acid. Lệch thì giải thích trong báo cáo, không ép cho khớp.

Hàm tính phải là hàm thuần trên dữ liệu đã nạp. Test dùng fixture nhỏ:
- Hoạt chất có nhãn qua thành phần của nhãn phối hợp → `so_doan_nhan_fda > 0`.
- Thiếu tệp LiverTox → cột trống, không lỗi.
- `ddinter_da_cao_du` đúng / sai.

## Phạm vi file

**Được tạo / sửa:**
- `app/kb/coverage/**` (mới)
- `app/kb/dictionary/publish.py` (chỉ dòng đọc `DATABASE_URL` và import cần thiết)
- `tests/kb/test_coverage*.py`, `tests/kb/fixtures/coverage/**`
- `data/kb_reports/do_phu_da_nguon.*`
- `plan/reports/T56.md`

**Cấm đụng:** mọi thứ khác, đặc biệt:
- `app/kb/interactions/**`, `app/rules/**`, `app/api/**`, `web/**` (T55)
- `app/kb/resolver/**`
- `data/kb_curated/**`, `data/kb_staging/**`, `data/kb_sources/**` (chỉ đọc)
- `.env`, `pyproject.toml`, `uv.lock`

## Nghiệm thu (dán kết quả vào báo cáo `plan/reports/T56.md`)

- `uv run python -m app.kb.coverage report`: dán tóm tắt.
- `uv run pytest -q tests/architecture tests/kb --basetemp=.pytest_t56` qua (test kiến trúc hết trượt).
- `uv run ruff check app/kb/coverage app/kb/dictionary/publish.py tests/kb` và `ruff format --check` các tệp đã sửa qua.

## Cấm làm

Không gọi mạng. Không commit. Không dùng `&`.
