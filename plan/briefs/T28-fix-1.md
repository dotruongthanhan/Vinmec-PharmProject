# T28-fix-1 – Một test của T14 trượt vì `PhanHoi` có thêm hai trường

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort high) · **Ngày:** 18/11/2026
**Đọc trước:** `AGENTS.md`; `plan/reports/T28.md`; `app/db/mapping.py` (dòng 284); `db/schema.sql` (bảng `nghiep_vu.phan_hoi`); `tests/db/test_mapping.py`.

## 1. Kết quả review T28

Đạt: lint và định dạng sạch, `tests/auth tests/api` 78 qua, `uvicorn` thật không token trả đúng `200` / `401` / `401`. Mã `app/auth/verifier.py` và `dependencies.py` đã đọc, đúng brief. Còn **1 test trượt**:

```text
tests/db/test_mapping.py::test_mapping_matches_schema_and_rls
AssertionError: nghiep_vu.phan_hoi  — thừa 'nguoi_dung_id', 'phien_id'
```

Nguyên nhân: `app/db/mapping.py` dùng `model_columns(PhanHoi)` nên tự lấy hai trường mới của `PhanHoi`, trong khi bảng DB `phan_hoi` chưa có hai cột này (sẽ thêm ở plan 1.6, task T33).

## 2. Việc phải làm

Chỉ sửa `app/db/mapping.py`: loại `nguoi_dung_id` và `phien_id` khỏi ánh xạ DB hiện tại bằng đối số loại trừ của `model_columns` (đã có tham số `*exclude`), kèm một dòng chú thích tiếng Việt nói hai trường này chỉ có ở tệp JSONL cho tới khi bảng `phan_hoi` được mở rộng (plan 1.6, T33).

**Không** sửa `db/schema.sql`, không thêm cột, không đổi test (`tests/db/test_mapping.py` giữ nguyên kỳ vọng).

## 3. Phạm vi file

Được sửa: `app/db/mapping.py`. Cấm đụng: mọi tệp khác, đặc biệt `db/`, `web/`, `app/auth/`, `app/api/`, `.env`.

## 4. Nghiệm thu

```bash
uv run ruff check app/db/mapping.py
uv run ruff format --check app/db/mapping.py
uv run pytest -q -p no:cacheprovider tests/db
uv run pytest -q -p no:cacheprovider --ignore=tests/architecture/.tmp --ignore=tests/db/.tmp --ignore=tests/kb/.tmp
```

Kết quả: **0 test trượt** toàn kho (763 + 1 = 764 qua). Không commit, không push. Báo cáo theo mẫu `AGENTS.md`.
