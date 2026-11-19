# T76-fix-1 – Câu truy vấn lô cặp DDInter hỏng; E501; định dạng

Agent: **agy Gemini 4 Hydrogen high**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.**

## Lỗi (Claude review T76)

1. `app/kb/interactions/store.py` dòng ~43: `_SELECT_PAIRS_IN` ghép chuỗi f-string với chuỗi thường `"WHERE (ddinter_id_a, ddinter_id_b) IN ({{placeholders}})"`. Phần chuỗi thường giữ nguyên `{{`/`}}`, nên sau khi điền, câu SQL còn ký tự `{` → `sqlite3.OperationalError: unrecognized token: "{"` trong 3 test `tests/kb/test_store_from_db.py` (`test_interaction_store_and_resolver_from_db_match_sqlite[False/True]`, `test_interaction_rule_uses_single_batch_query_on_db_store`) và sẽ hỏng trên PostgreSQL thật. Sửa để câu cuối cùng là `... WHERE (ddinter_id_a, ddinter_id_b) IN ((%s, %s), (%s, %s), ...)` với đúng số cặp; tham số truyền qua psycopg, **không** nội suy giá trị vào chuỗi. Kiểm thêm một test: câu SQL sinh ra cho 2 cặp không chứa `{` hay `}` và có đúng 4 `%s`.
2. E501 (> 100 ký tự): `app/container.py:137`, `:163`, `app/storage/feedback_chat.py:91`, `tests/db/test_mapping.py:34`, `tests/kb/test_store_from_db.py:348`. Ngắt dòng, không đổi logic.
3. `ruff format --check` báo 8 tệp lệch (các tệp T75–T76 đã đụng): định dạng theo `pyproject.toml` (dòng 100), chỉ khoảng trắng / xuống dòng.

## Phạm vi

Chỉ các tệp nêu trên và các tệp T75–T76 bị lệch định dạng. Không đổi hành vi khác. Thêm mục "fix-1" vào `plan/reports/T76.md`.
