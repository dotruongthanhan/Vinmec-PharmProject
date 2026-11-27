# TR2a – Ghi vết vào Postgres (bảng `nghiep_vu.vet_*`), ghi lô, dọn 30 ngày

Người làm: Codex `gpt-6.1-terra` xhigh (chạy được lệnh; **không cài gói, không gọi mạng, không chạm DB thật**).
Đọc trước: `AGENTS.md` (nhất là mục Bảo mật, quy tắc 10–14); `plan/plan-1.11-tracer-va-visualizer.md` **A.3, A.4, A.5, A.7, A.8**; `app/tracing/` (toàn bộ, đã xong ở TR1: `models.py` có `VetChay`, `SpanBanGhi`; `sink.py` có `JsonlTraceSink`, `don_vet_qua_han`; `context.py` khởi tạo sink); `app/storage/feedback_chat.py` (mẫu lấy URL bằng `get_secret`, kết nối ghi `psycopg`); `app/db/read_pool.py` (mẫu cầu dao và thời hạn kết nối); `db/schema.sql`, `db/roles.sql`, `db/README.md`.

Bối cảnh: TR1 đã ghi vết ra JSONL theo ngày. Đợt này thêm **đích ghi thứ hai là Postgres**. API quản trị và trang web là đợt sau (TR2b, TR3), **không làm ở đây**.

## Yêu cầu

1. **DDL** trong tệp mới `db/vet.sql` (chạy lại nhiều lần không lỗi, `IF NOT EXISTS`):
   - `nghiep_vu.vet_chay`: các trường ở plan A.3 (`ma_vet` UUID khoá chính, `bat_dau`, `ket_thuc` kiểu `timestamptz`, `thoi_gian_ms`, `loai`, `engine`, `nguoi_dung_id`, `vai_tro`, `phien_id`, `ca_bam`, `phien_ban` JSONB, `trang_thai_cuoi`, `tong_token_vao`, `tong_token_ra`, `chi_phi_uoc_tinh` numeric, `so_tool`, `so_bi_chan`, `ma_loi`, `muc_noi_dung`, `vet_bi_cat` boolean). Ràng buộc `CHECK` cho `loai`, `muc_noi_dung`. Lấy đúng tên trường từ `VetChay`; trường nào `VetChay` có mà A.3 không có thì giữ theo `VetChay` và ghi vào báo cáo.
   - `nghiep_vu.vet_buoc`: `ma_vet` (khoá ngoại tới `vet_chay`, `ON DELETE CASCADE`), `ma_buoc`, `ma_buoc_cha`, `loai` (`CHECK` 7 loại), `ten` (≤ 120 ký tự), `bat_dau`, `thoi_gian_ms`, `trang_thai`, `thuoc_tinh` JSONB (`CHECK` `pg_column_size` ≤ 4096 hoặc kiểm ở code, ghi rõ chọn cách nào), `noi_dung` text. Khoá chính `(ma_vet, ma_buoc)`.
   - Chỉ mục: `vet_chay(bat_dau DESC)`, `vet_chay(loai, engine, bat_dau DESC)`, `vet_chay(trang_thai_cuoi)`.
   - Quyền, chèn vào `db/roles.sql` theo đúng mẫu sẵn có: `bvienx_app` được `INSERT, SELECT, DELETE` **chỉ trên hai bảng này**, không có `UPDATE`. Không đổi quyền bảng khác.
   - Cập nhật `db/README.md`: một mục ngắn "Bảng vết (TR2a)" nói cách chạy `db/vet.sql` (chủ kho tự chạy, agent **không** chạy).
2. **Đích ghi `PostgresTraceSink`** trong `app/tracing/sink_db.py` (mới), cùng giao diện với `JsonlTraceSink` (nếu chưa có giao diện chung thì thêm `Protocol` `TraceSink` trong `sink.py`, `JsonlTraceSink` không đổi hành vi):
   - Hàng đợi có trần riêng (dùng `tracer.hang_doi_toi_da`) và **một luồng nền**; gom lô tối đa 50 vết hoặc mỗi 2 giây, ghi trong **một giao dịch** mỗi lô (`executemany`, tham số hoá; **cấm f-string/format trong SQL**). `ON CONFLICT (ma_vet) DO NOTHING`.
   - Kết nối riêng (không dùng `read_pool`, vì pool đó chỉ đọc). URL lấy bằng `get_secret(settings.database.url_env)`; thiếu URL thì sink tự tắt, log cảnh báo một lần, **không** làm app lỗi khởi động. `connect_timeout` lấy từ `db.thoi_han_ket_noi_giay`; `SET LOCAL statement_timeout = 5000`.
   - Lỗi DB (mất kết nối, hết thời gian, bảng chưa có): bỏ lô, tăng bộ đếm `so_vet_bo_db`, log cảnh báo một lần mỗi loại lỗi (không log thông điệp có chuỗi kết nối), **cầu dao** `db.cau_dao_giay` giây trước khi thử lại. Không bao giờ làm chậm hoặc làm hỏng lượt chạy.
   - Ghi đúng những gì vết đã có sau khi che PII ở TR1; **không** thêm văn bản mới. Mức `sieu_du_lieu` thì `noi_dung` luôn `NULL`.
   - Có `close()`/dừng sạch khi app tắt (xả nốt hàng đợi tối đa 3 giây).
3. **Cấu hình:** `tracer.dich` là danh sách đích, mặc định `["jsonl"]` ở `config/settings.yaml` và `settings.test.yaml` (bảng chưa được tạo trên RDS nên mặc định chưa bật DB). Giá trị hợp lệ `jsonl`, `db`; giá trị lạ → lỗi cấu hình khi khởi động. Khởi tạo các sink trong chỗ TR1 đang khởi tạo `JsonlTraceSink`; vết đóng thì đẩy vào **mọi** đích đang bật.
4. **Dọn quá hạn:**
   - `don_vet_db_qua_han(so_ngay, *, dong_ho=None)` xoá `vet_chay` có `bat_dau` cũ hơn `tracer.so_ngay_luu` ngày (span đi theo nhờ `CASCADE`), xoá theo lô ≤ 5.000 dòng mỗi câu lệnh cho tới hết, trả về số vết đã xoá.
   - Một bộ hẹn giờ nền chạy **cả** dọn JSONL (hàm có sẵn) **và** dọn DB (khi đích `db` bật) lúc khởi động và sau đó mỗi 24 giờ. Lỗi dọn thì log, không làm app lỗi.
5. **Không** thêm API, route, trường hợp đồng hay giao diện ở đợt này.

## Test (`tests/tracing/`, không cần DB thật)

Dùng kết nối giả (ghi lại câu SQL và tham số) hoặc mẫu SQLite giả đang có trong kho; không thêm gói.
- Vết của một lượt agent giả lập (dựng như test TR1) → đúng 1 lệnh chèn `vet_chay` và N lệnh chèn `vet_buoc`, giá trị khớp `VetChay`.
- Lô: 120 vết → 3 giao dịch (50/50/20); `ON CONFLICT` có mặt.
- Mọi câu SQL là chuỗi hằng; tham số đi riêng (test khẳng định không có giá trị canary nào nằm trong chuỗi SQL).
- **Canary:** họ tên, SĐT `0912345678`, CCCD 12 số giả, khoá `sk-test-canary-123` đặt trong câu hỏi và tham số tool → quét toàn bộ tham số đã gửi tới DB giả: 0 lần xuất hiện (kể cả chuỗi chữ số).
- Mức `sieu_du_lieu` → mọi `noi_dung` là `None`.
- DB giả ném `OperationalError` khi kết nối → lượt chạy vẫn trả lời, bộ đếm tăng, cầu dao chặn lần thử tiếp trong thời gian cấu hình (đồng hồ giả).
- Hàng đợi DB đầy (trần 1) → không chặn, bộ đếm tăng; đích JSONL vẫn ghi đủ.
- Thiếu URL → sink tắt, app khởi động bình thường.
- `tracer.dich: ["xyz"]` → lỗi cấu hình.
- `don_vet_db_qua_han` với đồng hồ giả: câu xoá dùng mốc đúng 30 ngày, lặp theo lô tới khi 0 dòng.
- Hiệu năng: 50 lượt agent giả lập với đích `db` trỏ tới kết nối giả luôn hết giờ → chênh p95 so với tắt tracer < 20 ms.
- `db/vet.sql` chỉ chứa `IF NOT EXISTS`; `db/roles.sql` không cấp `UPDATE` cho hai bảng vết (test đọc tệp).

## Tệp

Được tạo/sửa: `app/tracing/**`, `app/config/**` (đọc `tracer.dich`), `app/container.py` hoặc `app/api/main.py` (chỉ chỗ khởi tạo/dừng sink và bộ hẹn giờ), `config/settings.yaml`, `config/settings.test.yaml`, `db/vet.sql` (mới), `db/roles.sql` (chỉ thêm quyền hai bảng vết), `db/README.md` (chỉ thêm mục), `tests/tracing/**`. Báo cáo: `plan/briefs/TR2a-bao-cao.md` (đã làm gì, quyết định nào khác brief, lệnh đã chạy và kết quả).

**Cấm:** chạy SQL lên bất kỳ DB nào; đọc, in hay sửa `.env`; sửa `web/**`, `data/**`, `plan/plan-*`, `app/api/routes.py`, `app/api/schemas.py`, `app/agent/**`, `app/orchestration/**`; thêm gói; gọi mạng; commit. Không đổi hành vi trả lời.

## Nghiệm thu (Claude chạy)

```
uv run ruff check app tests/tracing/*.py && uv run ruff format --check app tests/tracing/*.py
# tests/tracing/.tmp-* bị khoá quyền, ruff panic nếu quét cả thư mục: chỉ định tệp .py
uv run pytest -q -p no:cacheprovider tests/tracing
uv run pytest -q -p no:cacheprovider tests/agent
uv run pytest -q -p no:cacheprovider tests/orchestration
uv run pytest -q -p no:cacheprovider tests/api
```

Claude kiểm độc lập:
- đọc diff tìm f-string trong SQL, chuỗi kết nối trong log, luồng nền không có trần;
- chạy `db/vet.sql` lên một Postgres tạm trong Docker (cổng khác 5433) để chắc DDL hợp lệ;
- sau khi chủ kho tạo bảng trên RDS và bật `tracer.dich: [jsonl, db]`: chạy thật 2 câu hỏi đáp, đối chiếu dòng `vet_chay` với dòng JSONL cùng `ma_vet`, quét bảng không có họ tên/SĐT của ca DEMO.
