# T79 – Tốc độ khi app đọc dữ liệu từ DB xa (RDS qua đường hầm)

Agent: **agy Gemini 4 Hydrogen xhigh**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Chạy song song với T80 (T80 chỉ sửa `app/rules/lab_threshold.py` + test của nó: **không đụng tệp đó**).

## Số đo (Claude, cProfile, RDS Singapore qua SSM, mỗi truy vấn ~80–230 ms)

`list_cases` lần đầu **25,8 s** (lần 2: 1,3 s); `get_case` **2,8 s**; web: `/api/cases` 24,7 s, `/api/cases/HS-024` 5,0 s.

| Chỗ tốn | Thời gian | Nguyên nhân |
|:--|--:|:--|
| `DrugResolver.from_db` (`container.drug_resolver`) | 7,8 s | Nạp ~107k dòng `tra_cuu_*` khi có yêu cầu đầu tiên |
| `InteractionStore.pairs` → `_query_pairs` | 7,3 s | **31 truy vấn** (mỗi ca một lần) khi `list_cases` chạy 67 ca |
| `bang_luat_store.load_rule_data` | 4,7 s | 11 tài liệu, 32 truy vấn, **22 lần mở kết nối** (`open_read_connection`) |
| `reader.read_case_rows` | 2,5 s | 14 truy vấn |
| `get_case` → `_persist_review_if_needed` → `save_review` | 1,6 s | Mở kết nối ghi mới + chèn từng dòng, **chặn phản hồi API** |
| `get_case` → hành chính + hồ sơ | 1,7 s | 12 truy vấn tuần tự |

## Yêu cầu (không đổi kết quả thẩm định)

1. **Làm nóng khi khởi động:** trong `lifespan` của `app/api/main.py`, khi `KB_SOURCE` chọn DB, chạy nền (thread, không chặn khởi động) việc nạp `drug_resolver`, `interaction_store`, mọi bảng luật (`load_rule_data` cho 11 tài liệu), `renal_rules`. Lỗi làm nóng chỉ log cảnh báo. Yêu cầu đến trong lúc đang nạp thì chờ cùng một lần nạp (không nạp hai lần – khoá đã có ở `cached_property` / `lru_cache` phải an toàn luồng).
2. **Bảng luật: một kết nối cho mọi tài liệu:** `load_rule_data` lần đầu nạp **tất cả** tài liệu trong một kết nối (và nếu được một giao dịch chỉ đọc), thay vì mở kết nối cho từng tài liệu / bảng.
3. **DDInter gom cặp toàn danh sách:** `list_cases` (đường chạy nhiều ca) thu cặp `ddinter_id` của **mọi** ca trước, gọi `store.pairs(...)` **một lần** (chia lô ≤ 1.000 cặp mỗi truy vấn), sau đó mới chạy luật từng ca (kết quả đã có trong bộ đệm của store). Không đổi `app/rules/interaction.py` ngoài cách gọi nếu cần.
4. **Ghi kết quả thẩm định không chặn API:** `save_review` chạy nền (một `ThreadPoolExecutor` 1 luồng của service, hoặc hàng đợi), API trả ngay. Dùng `executemany` / `COPY` cho `ket_qua_nhan_dinh`. Lỗi vẫn chỉ log. Test hiện có về "ghi một lần" phải qua (chờ hàng đợi rỗng trong test).
5. **`get_case`: hành chính và hồ sơ đọc song song** (đã có `ThreadPoolExecutor` cho hồ sơ – đưa hành chính vào cùng lúc), hoặc gộp vào một kết nối.

## Test

Kết nối giả đếm số lần mở kết nối và số truy vấn: bảng luật ≤ 1 lần mở kết nối cho cả 11 tài liệu; `list_cases` 67 ca → `ddinter_cap` ≤ 1 truy vấn (một lô); `get_case` trả về trước khi `save_review` xong (mock chậm). Toàn kho 0 trượt.

## Phạm vi

`app/api/main.py`, `app/api/service.py`, `app/container.py`, `app/db/bang_luat_store.py`, `app/kb/interactions/store.py`, `app/storage/review_results.py`, `app/db/administrative.py` / `medical_record.py` (chỉ nếu gộp kết nối), test. Cấm: `app/rules/lab_threshold.py`, `data/`, `web/`, logic luật. Định dạng `ruff format` cho mọi tệp đụng tới. Báo cáo `plan/reports/T79.md`.

## Nghiệm thu (Claude chạy trên RDS)

`list_cases` lần đầu sau khi làm nóng xong **< 5 s**; `get_case` **< 1,5 s**; 66 ca vẫn 577 nhận định khớp 100%.
