# T74 – Sửa lỗi hỏi đáp chung; chuẩn bị lược đồ cho AWS RDS; dọn test và định dạng

Agent: **agy Gemini 4 Hydrogen high**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Claude tự chạy `ruff`, `pytest`.

## Việc 1 – Lỗi chatbot "Đã xảy ra lỗi hệ thống" (người dùng gặp trên web)

Log backend (Claude đọc):

```
File "app/orchestration/ask.py", line 1180, in <genexpr>
    f"{line.ten_tu_do or line.thuoc_id} {line.lieu_moi_lan:g} "
TypeError: unsupported format string passed to NoneType.__format__
```

`ask_global` dựng chuỗi tóm tắt mọi ca; HS-040 có dòng `lieu_moi_lan = None` (paracetamol siro kê theo mg/kg) nên mọi câu hỏi ở chế độ "Hỏi đáp chung" đều lỗi.

- Sửa chỗ dựng chuỗi để chịu được `lieu_moi_lan`, `don_vi_lieu`, `tan_suat`, `duong_dung` là `None` (ví dụ ghi "liều chưa ghi"). Tìm trong `app/orchestration/ask.py` mọi chỗ định dạng tương tự (`:g`, `:.1f` trên trường có thể `None` của `ChiTietYLenh`, `SinhHieu`, `KetQuaXetNghiem`) và sửa cùng cách.
- Test mới `tests/orchestration/test_ask_global_none_fields.py` (hoặc thêm vào tệp test hỏi đáp có sẵn): ca dựng bằng pydantic có một dòng `lieu_moi_lan=None` → hàm dựng tóm tắt không ném lỗi, chuỗi có chữ thay thế. Không gọi LLM thật (dùng stub như các test `ask` hiện có).

## Việc 2 – Lược đồ chạy được trên PostgreSQL thường (AWS RDS), vẫn chạy được trên Supabase

Claude đã chạy thử lược đồ trên RDS (19/11): hai lỗi.

1. `db/schema.sql` dòng ~247 và ~279: `REVOKE ALL ON … FROM PUBLIC, anon, authenticated;`. Vai trò `anon`, `authenticated` chỉ có trên Supabase. Đổi thành khối `DO $$ … $$` chỉ thu quyền của từng vai trò **khi vai trò đó tồn tại** (`IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN EXECUTE 'REVOKE …'`), giữ `REVOKE … FROM PUBLIC` vô điều kiện. Hành vi trên Supabase không đổi.
2. `db/tu_dien.sql` có BOM UTF-8 ở 3 byte đầu: bỏ BOM (ghi lại tệp UTF-8 không BOM, nội dung giữ nguyên).
- Nếu `app/db/engine.py::apply_schema` đọc tệp SQL bằng `encoding="utf-8"`, đổi sang `"utf-8-sig"` để chịu được BOM nếu tái xuất hiện.
- Test: thêm vào `tests/db/` một test đọc `db/schema.sql` kiểm không còn câu `REVOKE … anon` nằm ngoài khối điều kiện, và `db/tu_dien.sql` không bắt đầu bằng BOM.

## Việc 3 – Dọn

- `tests/architecture/test_notebook.py`: đang kỳ vọng notebook in `Số luật: 6`, nay là 14 sau khi nối luật D4–D7 (T69). Sửa kỳ vọng theo `len(default_rules())` nếu được, không thì 14. Không sửa notebook.
- Định dạng (chỉ khoảng trắng / xuống dòng, không đổi logic; dòng tối đa 100 theo `pyproject.toml`) các tệp `ruff format --check` đang báo lệch trong `app/rules/` và `tests/rules/`: `allergy.py`, `allergy_config.py`, `drug_disease.py`, `hepatic.py`, `max_dose.py`, `required_fields.py`, `toxicity.py`, và các test `test_allergy_resolver.py`, `test_allergy_runtime.py`, `test_lab_threshold.py`, `test_renal_dose_d4.py`. Không chắc thì bỏ qua tệp đó và ghi vào báo cáo.

## Phạm vi

Sửa: `app/orchestration/ask.py`, `db/schema.sql`, `db/tu_dien.sql`, `app/db/engine.py` (chỉ encoding), `tests/architecture/test_notebook.py`, các tệp định dạng ở việc 3. Tạo test mới ở việc 1, 2 và `plan/reports/T74.md`. Cấm: `data/`, `web/`, `config/`, logic luật.

## Nghiệm thu (Claude chạy)

`uv run ruff check .`, `uv run pytest -q -p no:cacheprovider` toàn kho 0 trượt; gửi câu "xin chào" ở chế độ hỏi đáp chung trên web không còn lỗi; chạy lược đồ trên RDS trong giao dịch không lỗi.
