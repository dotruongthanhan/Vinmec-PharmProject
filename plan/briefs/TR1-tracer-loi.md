# TR1 – Tracer lõi: mã vết, span, ghi JSONL (chưa có DB)

Người làm: agy Gemini 4 Neon xhigh (**không gọi công cụ shell**; Claude chạy ruff, pytest khi review).
Đọc trước: `AGENTS.md`; `plan/plan-1.11-tracer-va-visualizer.md` **phần A (A.1–A.8)**; `app/core/progress.py` (`tien_trinh_hien_tai`, `ghi_buoc`); `app/agent/tools/gateway.py` (`goi`, `_audit`); `app/providers/deepseek_llm.py` (`last_usage`); `app/verify/number.py`; `app/orchestration/ask.py`, `app/orchestration/ai_review.py`; `app/api/service.py` (chỗ dựng `TraLoi`), `app/api/schemas.py`; `app/eval/hoi_dap.py`.

Bối cảnh: các tệp trên đang có thay đổi chưa commit của đợt T108–T114 (đã review đạt). Sửa chồng lên bản hiện tại trong thư mục làm việc, không hoàn tác gì.

## Phạm vi đợt này

Làm A.1 mục 1–6 và 8, A.3 (mô hình span, **chỉ ra JSONL**), A.4, A.5 (trừ Postgres), A.7. **Chưa làm:** bảng `nghiep_vu.vet_*`, API quản trị, trang web (TR2, TR3).

## Yêu cầu

1. **Module `app/tracing/`** (mới):
   - `ma_vet` = UUID v4; ContextVar `vet_hien_tai`, giống `tien_trinh_hien_tai`.
   - `bat_dau_vet(loai, engine, ...)` trả về context manager; `span(loai, ten, **thuoc_tinh)` là context manager lồng nhau (`ma_buoc`, `ma_buoc_cha` theo khái niệm OTel), tự đo `thoi_gian_ms` và `trang_thai` (lỗi thì `loi` + tên lớp ngoại lệ, không ghi thông điệp).
   - `loai` span: `node | llm | tool | kiem_chung | che_pii | chan_dau_vao | su_kien_bao_mat`.
   - `thuoc_tinh` chỉ nhận **khoá trong danh sách cho phép của từng loại span** (khai báo trong code), ≤ 4 KB sau `json.dumps`; khoá lạ bị bỏ và đếm.
   - Không có vết hiện hành thì mọi hàm là no-op, không ném lỗi.
   - Trần: 200 span và 256 KB mỗi vết; vượt thì gắn `vet_bi_cat=true` và bỏ span thêm.
2. **Đích ghi JSONL** `data/runtime/vet/vet-YYYY-MM-DD.jsonl` (giờ Việt Nam), **một dòng một vết** khi vết đóng (gồm tổng hợp + mảng span).
   - Ghi qua hàng đợi có trần (mặc định 1.000) + luồng nền; đầy thì bỏ vết, tăng bộ đếm, log cảnh báo một lần. **Không bao giờ** làm chậm hoặc làm hỏng lượt chạy.
   - Tệp > 200 MB trong ngày thì ngừng ghi ngày đó.
   - Hàm `don_vet_qua_han(so_ngay)` xoá tệp cũ hơn `tracer.so_ngay_luu` (mặc định 30); gọi một lần khi app khởi động. Có tham số đồng hồ để test.
3. **Cấu hình** trong `config/settings.yaml` (và `settings.test.yaml` nếu cần): `tracer.bat` (mặc định true), `tracer.muc_noi_dung` (mặc định `sieu_du_lieu`), `tracer.so_ngay_luu` (30), `tracer.thu_muc`. Mức `day_du` khi `APP_ENV=production` → app **từ chối khởi động** với thông báo rõ.
4. **Điểm móc:**
   - `ghi_buoc` → span `node` (bat_dau/xong/loi).
   - `ToolGateway.goi` → span `tool`: tên tool, trạng thái, `ma_loi`, kích thước kết quả, cờ bị cắt, **mã căn cứ**, thời gian; tham số chỉ ghi **bản đã che PII** (lấy sau bước che của Gateway) + băm SHA-256 tham số gốc; ở mức `sieu_du_lieu` chỉ ghi tên khoá tham số, không ghi giá trị.
   - LLM: lớp bọc hoặc móc trong `DeepSeekLLM` → span `llm`: mô hình, token vào/ra (từ `last_usage`), độ trễ, số lần thử lại, lý do kết thúc, số ký tự prompt, băm prompt. Không ghi nội dung prompt ở mức `sieu_du_lieu`.
   - Bộ kiểm chứng → span `kiem_chung`: số câu/nhận định bị chặn, danh sách mã lý do.
   - Phát hiện chèn lệnh, PII trong tham số → span `su_kien_bao_mat`.
5. **Che chữ số trong mã lý do (bảo mật, bắt buộc):** mã như `so_khong_co_nguon:63` hiện chép nguyên con số từ câu trả lời; nếu LLM nhắc lại số điện thoại/CCCD thì chữ số lọt vào vết. Trong vết, phần sau dấu `:` của mã lý do phải thay bằng: số có ≤ 4 chữ số giữ nguyên, dài hơn thì thay bằng `#<n chữ số>` (ví dụ `so_khong_co_nguon:#10`). Ghi rõ trong báo cáo nếu log hiện có (`ask rejected ... reason=`) cũng cần che như vậy — **không sửa log hiện có ở đợt này**, chỉ báo.
6. **Mở vết:** `ask` (cả `co_dinh` và `agentic`), `ai_review`, và từng câu của eval (`loai=danh_gia`). `TraLoi` thêm trường tuỳ chọn `ma_vet: str | None`; API hỏi đáp trả thêm header `X-Ma-Vet`. `chi_tiet.jsonl` của eval thêm `ma_vet` (trường tuỳ chọn để `--cham_lai` vẫn đọc được tệp cũ có `trich_dan`). Tổng hợp theo vết: trạng thái cuối, thời gian, tổng token, chi phí ước tính (bảng giá trong cấu hình, để 0 nếu không có), số tool, số lần bị chặn.
7. Mã ca trong vết là **HMAC-SHA256** với khoá `TRACER_HMAC_KEY` trong `.env`; thiếu khoá thì dùng khoá ngẫu nhiên theo tiến trình và log cảnh báo. **Không** đọc hay in giá trị khoá. Không thêm khoá vào `.env` (Claude/chủ kho thêm).
8. LangSmith giữ tắt: test khẳng định `tracing_context(enabled=False)` vẫn còn ở `asker.py` và `ai_review.py`.

## Test `tests/tracing/`

- Cây span đúng cho một lượt agent giả lập (LLM giả + 2 tool giả qua Gateway thật): node → llm → tool → kiem_chung, `ma_buoc_cha` đúng.
- Token lấy đúng từ `last_usage` giả.
- Hàng đợi đầy (trần 1) vẫn trả lời bình thường, bộ đếm tăng.
- `day_du` + `APP_ENV=production` → lỗi khởi động.
- **Canary:** họ tên, HN, SĐT `0912345678`, CCCD 12 số giả đặt trong câu hỏi và tham số tool, khoá giả `sk-test-canary-123`; quét toàn bộ tệp JSONL sinh ra → 0 lần xuất hiện (kể cả chuỗi chữ số của SĐT/CCCD).
- Mã lý do `so_khong_co_nguon:0912345678` → trong vết là `so_khong_co_nguon:#10`.
- `don_vet_qua_han` với đồng hồ giả xoá đúng tệp > 30 ngày, giữ tệp mới.
- `TraLoi.ma_vet` có giá trị và khớp `ma_vet` trong JSONL; header `X-Ma-Vet` có ở API hỏi đáp.
- Không có vết hiện hành: gọi `span(...)` không lỗi.

## Tệp

Được tạo/sửa: `app/tracing/**`, `app/core/progress.py`, `app/agent/tools/gateway.py`, `app/providers/deepseek_llm.py`, `app/verify/*.py` (chỉ chỗ cần móc span), `app/orchestration/ask.py`, `app/orchestration/ai_review.py`, `app/agent/nodes.py` (nếu cần móc), `app/api/service.py`, `app/api/schemas.py` (chỉ thêm `ma_vet`), router API hỏi đáp (chỉ header), `app/container.py` (khởi tạo tracer), `app/config/**` (đọc cấu hình mới), `config/settings*.yaml`, `app/eval/hoi_dap.py` (chỉ thêm `ma_vet`), `tests/tracing/**`, sửa test có sẵn **chỉ khi** cần vì trường mới. Báo cáo: `plan/briefs/TR1-bao-cao.md`.
**Cấm:** sửa `web/**`, `data/**` (trừ thư mục do tracer tự tạo khi chạy test, phải dùng `tmp_path`), `plan/plan-1.11-*`, `.env`; thêm gói; gọi mạng; gọi shell; commit; đổi hành vi trả lời (chỉ thêm quan sát).

## Nghiệm thu (Claude chạy)

```
uv run ruff check app tests && uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider tests/tracing tests/agent tests/orchestration tests/eval tests/api
uv run pytest -q -p no:cacheprovider
```
Claude kiểm độc lập: chạy thật 2 câu (`HD-CA-015`, `HD-CA-011`) bằng `tools/cham_hoi_dap.py`, mở dòng vết tương ứng, đối chiếu token với DeepSeek, quét tệp vết không có họ tên/SĐT của DEMO-03 (tên giả có chữ số "63").
