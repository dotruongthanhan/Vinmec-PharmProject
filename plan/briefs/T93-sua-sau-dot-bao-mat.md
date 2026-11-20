# T93 – Sửa các lỗi nhỏ sau đợt bảo mật T89–T92

Agent: agy `gemini-4-hydrogen-high`. **Không gọi shell, không gọi mạng; chỉ đọc và ghi tệp.**

Review T89–T92 (20/11): logic đạt kiểm độc lập (T89 401/413/cấm `AUTH_MODE=off` trong container/prompt một lượt; T90 CSP chạy được trên trình duyệt, không lỗi console, bundle không còn chunk mock; T91 lịch sử đúng người, bỏ lượt bịa; T92 build Docker với digest). Còn 4 lỗi:

## 1. Vitest trượt: `src/__tests__/safety.test.ts` › "không tệp nào chứa liên kết mạng ngoài http/https"

Báo: `./securityConfig.test.tsx chứa URL ngoài: … not to contain 'http://'`. Tệp test mới của T90 `web/src/__tests__/securityConfig.test.tsx` có chuỗi `http://` nguyên văn ở đâu đó (đầu tệp đã ghép `HTTP = ['ht', 'tp://'].join('')` nhưng vẫn còn chỗ khác, có thể trong chú thích hoặc tên test). Sửa **tệp test đó** cho không còn chuỗi `http://` nguyên văn (dùng hằng đã ghép). **Không** sửa `safety.test.ts`.

## 2. Pytest trượt: `tests/api/test_feedback_chat_db.py::test_case_service_db_mode_uses_db_store_and_db_corpus_end_to_end`

`IndexError` ở dòng ~371: `client.get("/api/cases/DEMO-02").json()["nhan_dinh"]["can_chu_y"][0]` rỗng. Test đặt `KB_SOURCE=db` với `DATABASE_URL` giả (`db.invalid`); log cho thấy mọi bảng luật nạp từ DB đều lỗi `OperationalError` (`quy_tac_lieu_than`, `quy_tac_gan`, `lieu_toi_da`…) nên DEMO-02 không còn nhận định cần chú ý. Test này qua trong lượt chạy toàn bộ trước T89 và trượt cả khi chạy riêng → nhiều khả năng phụ thuộc thứ tự / bộ đệm bảng luật trong tiến trình.

- Đọc `app/db/bang_luat_store.py` (khoảng dòng 1020–1110, đường rơi về tệp khi DB lỗi) và `app/container.py` để tìm vì sao không rơi về tệp luật cục bộ.
- Nếu đúng là test phụ thuộc thứ tự: sửa **test** cho tự đủ (ví dụ `monkeypatch` bộ nạp bảng luật về nguồn tệp, hoặc chọn nhận định theo cách không giả định nhóm `can_chu_y` có phần tử — nhưng vẫn phải kiểm luồng phản hồi DB như ý đồ test).
- Nếu là lỗi mã (rơi về tệp hỏng): **dừng, không sửa mã**, ghi rõ nguyên nhân vào báo cáo để Claude quyết định.

## 3. `ruff format`: `app/storage/feedback_chat.py` lệch định dạng (khoảng dòng 467). Định dạng đúng kiểu ruff (dòng 100, nháy kép), không đổi logic.

## 4. `.github/dependabot.yml`: đổi `package-ecosystem: "pip"` thành `"uv"` (dự án dùng `uv.lock`; hệ `pip` không cập nhật lockfile).

## Phạm vi

Chỉ: `web/src/__tests__/securityConfig.test.tsx`, `tests/api/test_feedback_chat_db.py`, `app/storage/feedback_chat.py` (chỉ định dạng), `.github/dependabot.yml`. Cấm tệp khác.

## Nghiệm thu (Claude chạy)

```
uv run ruff check . && uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider
uv run pytest -q -p no:cacheprovider tests/api/test_feedback_chat_db.py   (chạy riêng cũng phải qua)
cd web && npx vitest run
```

Ghi `plan/reports/T93.md` theo mẫu `AGENTS.md`.
