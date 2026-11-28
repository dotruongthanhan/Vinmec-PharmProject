# TRA-LOI-TU-NHIEN – Bỏ câu trả lời mẫu cố định; thiếu nguồn hoặc câu hỏi chung chung thì agent vẫn trả lời tự nhiên

Người làm: Codex `gpt-6.1-terra` xhigh. Đọc `app/orchestration/ask.py` (hằng `NO_SOURCE_MESSAGE`, `OUT_OF_SCOPE_MESSAGE`, `ERROR_MESSAGE`, `NOT_READY_MESSAGE` và mọi chỗ dùng), `app/agent/nodes.py` (nút dự phòng `agent_du_phong`, `_filter_missing_figure`), `app/verify/**` (chỉ đọc), `config/prompts/tac_tu.v1.md`, `config/prompts/hoi_them.v1.md`, `app/eval/hoi_dap.py`, `tests/orchestration/**`, `tests/agent/**`, `tests/eval/**`.

## Yêu cầu của chủ kho (28/11)

> Nếu câu hỏi chung chung, agent vẫn trả lời bình thường, không trả lời bằng câu mẫu. Bỏ phần trả lời mẫu. Nếu không có nguồn thì tool báo kết quả về, agent trả lời tự nhiên, mạch lạc.

**Ví dụ thật** (vết `1cfcaab1`, bản deploy): ca DEMO-02, câu "cho tôi bảng thống kê". Gemini trả lời 2 lần, đều bị bộ kiểm chứng chặn (`so_khong_co_nguon:1.73`, đang sửa riêng ở `VERIFY-don-vi-1-73`). Dược sĩ chỉ thấy câu mẫu "Không đủ căn cứ trong dữ liệu ca bệnh và kho nguồn hiện có…". Lẽ ra phải là: hệ thống có những gì cho ca này (xét nghiệm, thuốc, nhận định), lập được bảng nào, và hỏi lại dược sĩ muốn thống kê gì nếu câu quá rộng.

## Nguyên tắc không đổi

- **LLM không tự tính.** Mọi số hiển thị vẫn phải có nguồn và qua kiểm chứng số như hiện nay.
- Không nới `app/verify`.
- Phát hiện của luật không bị hạ mức.

## Yêu cầu

1. **Thay câu mẫu "không đủ căn cứ" bằng một lượt trả lời tự nhiên có kiểm chứng.** Khi kiểm chứng trượt hết số lần cho phép, hoặc truy xuất không ra nguồn, **không** trả `NO_SOURCE_MESSAGE`. Thay vào đó gọi LLM thêm **đúng một lượt** "trả lời trung thực", với prompt mới `config/prompts/tra_loi_trung_thuc.v1.md` (≤ 400 từ). Prompt yêu cầu:
   - nói tự nhiên, mạch lạc, đúng vai trợ lý cho dược sĩ;
   - nêu đã xem những gì (tên tool / loại dữ liệu đã tra, ví dụ "đã xem xét nghiệm và y lệnh của ca");
   - nêu điều tìm được, **có trích dẫn**;
   - nói rõ điều chưa xác nhận được và vì sao (thiếu dữ liệu, ngoài kho nguồn…);
   - câu hỏi quá rộng hoặc mơ hồ ("cho tôi bảng thống kê"): đề xuất 2–4 hướng cụ thể dựa trên dữ liệu ca hoặc kho thực có, và hỏi lại;
   - **không đưa số nào** ngoài số có trong kết quả tool kèm trích dẫn; không tính toán.

   Đầu vào cho lượt này: câu hỏi đã che PII, danh sách tool đã gọi và **tóm tắt kết quả tool** (đã che), lý do kiểm chứng trượt (mã lý do, không kèm câu trả lời cũ).
2. **Kiểm chứng lượt trả lời trung thực bằng đúng bộ kiểm hiện có.**
   - Đạt thì trả về. `trang_thai` giữ `khong_co_nguon` (để giao diện và bộ chấm hiểu đúng), `noi_dung` là câu tự nhiên.
   - Trượt vì số thì **bỏ đúng các câu chứa số trượt** (tách câu theo dấu chấm/xuống dòng). Nếu còn ≥ 1 câu có nội dung thì trả phần còn lại, kèm dòng cuối "(Đã lược phần chưa kiểm chứng được.)".
   - Không còn gì thì mới dùng một câu dự phòng ngắn, viết lại cho tự nhiên hơn, ví dụ "Mình chưa tìm thấy dữ liệu đủ chắc để trả lời câu này. Dược sĩ có thể nói rõ hơn cần xem gì cho ca này không?". Đây là chốt chặn cuối, phải hiếm.
3. **Ngoài phạm vi:** thay `OUT_OF_SCOPE_MESSAGE` cố định bằng câu từ chối lịch sự do LLM viết. Câu đó phải nói hệ thống làm được gì cho câu hỏi tương tự trong phạm vi, và vẫn qua kiểm chứng như trên.
   - **Ngoại lệ, giữ câu cố định:** đầu vào bị bộ chặn chèn lệnh/tấn công chặn (`chan_dau_vao`, `su_kien_bao_mat`). Không gọi LLM cho các trường hợp này.
4. **Giữ** `ERROR_MESSAGE` (LLM không gọi được, hết giờ) và `NOT_READY_MESSAGE` (chưa có LLM). Khi đó không có LLM nào để viết câu tự nhiên.
5. Áp dụng cho cả `co_dinh` (`CaseAsker.ask`, `ask_global`) và `agentic` (`AgenticAsker`, nút dự phòng trong `nodes.py`). Giữ `_filter_missing_figure`.
6. **Ngân sách:** lượt trả lời trung thực tính vào trần lời gọi LLM và hạn chót của câu hỏi. Hết hạn chót thì dùng câu dự phòng ngắn ở mục 2. Ghi span tracer `tra_loi_trung_thuc` (đạt/lược/dự phòng, số câu bị lược), không ghi nội dung.
7. **Bộ chấm:** câu kỳ vọng `khong_co_nguon` vẫn chấm theo `trang_thai`. Rà các câu có `cum_bat_buoc` là chuỗi trong câu mẫu cũ ("không đủ căn cứ"…) trong `data/gold/hoi_dap/*.jsonl` và **liệt kê** trong báo cáo, không sửa tệp đáp án.

## Test

- LLM giả: kiểm chứng trượt 2 lần → lượt trung thực trả câu tự nhiên có trích dẫn hợp lệ → `trang_thai = khong_co_nguon`, `noi_dung` không phải `NO_SOURCE_MESSAGE`, không chứa số ngoài nguồn.
- Lượt trung thực có 1 câu chứa số không nguồn → câu đó bị lược, phần còn lại trả về kèm dòng "(Đã lược…)".
- Lượt trung thực toàn số không nguồn → câu dự phòng ngắn mới.
- Câu "cho tôi bảng thống kê" (LLM giả trả đề xuất hướng + câu hỏi lại) → đạt.
- Ngoài phạm vi → câu do LLM viết; đầu vào bị chặn tấn công → câu cố định, LLM không được gọi.
- LLM lỗi → `ERROR_MESSAGE` như cũ.
- Cả hai engine.
- Canary PII: tóm tắt tool có họ tên → không lọt vào câu trả lời.

## Tệp

`app/orchestration/ask.py`, `app/agent/nodes.py`, `app/agent/asker.py`, `app/agent/graph.py` (nếu cần), `config/prompts/tra_loi_trung_thuc.v1.md` (mới), `app/tracing/models.py` (chỉ khoá span), `tests/orchestration/**`, `tests/agent/**`, `tests/eval/**` (chỉ nếu cần cập nhật test cũ dựa vào câu mẫu; giữ ý test). Báo cáo: `plan/briefs/TRA-LOI-TU-NHIEN-bao-cao.md`.
**Cấm:** sửa `app/verify/**` (đợt `VERIFY-don-vi-1-73` đang sửa); đọc `.env`; gọi `load_env_file()`; mạng; cài gói; commit; sửa `data/gold/**`.

## Nghiệm thu

```
uv run ruff check app tests && uv run ruff format --check app tests/orchestration tests/agent tests/eval
uv run pytest -q -p no:cacheprovider tests/orchestration tests/agent tests/eval tests/api tests/verify
```
Claude hỏi trên web: "cho tôi bảng thống kê" (DEMO-02), một câu ngoài phạm vi, một câu tấn công; chấm lại 90 câu.

## Bổ sung của chủ kho (28/11): mọi phần khác thiếu nguồn cũng trả lời mạch lạc như vậy

Phạm vi mở rộng, áp dụng cùng nguyên tắc ở mọi đường hỏi đáp:
- chế độ ca và chế độ chung;
- hỏi thêm từ thẻ nhận định (`nhan_dinh_id`);
- cả `co_dinh` lẫn `agentic`;
- lịch sử hội thoại: chỉ hiển thị, không đổi.

Thêm yêu cầu:

8. **Kết quả tool "không tìm thấy" phải là dữ liệu dùng được, không phải ngõ cụt.** Rà `tra_thuoc`, `tra_tuong_tac`, `tim_doan_nguon`, `doc_doan_mo_rong`, `tinh_chi_so`, `lay_du_lieu_ca`. Khi không có kết quả, văn bản tool trả LLM phải nói rõ:
   - đã tra gì (tên hoạt chất đã chuẩn hoá, cặp thuốc, chỉ số);
   - vì sao không có (ngoài kho, thiếu dữ liệu đầu vào như cân nặng/creatinin, chưa có quy tắc đã duyệt…);
   - còn có thể tra gì khác.

   Agent dùng các thông tin đó để viết câu tự nhiên. Không thêm số nào.
9. **Prompt `tac_tu.v1.md` và `hoi_them.v1.md`:** thêm hướng dẫn ngắn. Khi tool không có kết quả, hoặc câu hỏi mơ hồ, trả lời bằng lời: đã xem gì, thiếu gì, đề xuất hướng hỏi tiếp. Không trả lời cụt "không có dữ liệu".
10. **Web** (`web/src/features/assistant/AssistantPanel.tsx`): nhãn trạng thái `khong_co_nguon` đổi "Không có nguồn phù hợp" → "Chưa đủ nguồn để kết luận" (nội dung bên dưới giờ là câu tự nhiên). Nhãn ngoài phạm vi tương tự, giọng nhẹ hơn. Cập nhật test web liên quan. `web/src/api/mock.ts` (chế độ demo) cũng bỏ câu mẫu tương ứng, thay bằng một câu ví dụ tự nhiên.
11. Bảng nhận định (bước AI, `synthesizer`) **không** đổi trong đợt này: phát hiện của luật vẫn hiển thị khi diễn giải AI trượt kiểm chứng.

Tệp thêm: `app/agent/tools/**` (chỉ văn bản khi không có kết quả), `config/prompts/tac_tu.v1.md`, `config/prompts/hoi_them.v1.md`, `web/src/features/assistant/**`, `web/src/api/mock.ts`, test web liên quan. Nghiệm thu thêm: `cd web && npx tsc -b --noEmit && npx vitest run && npx vite build`.

## Bổ sung 3 (28/11): engine mặc định chuyển sang `agentic`

Chủ kho chốt bản deploy chạy như local: `config/settings.yaml` → `ask.engine: "agentic"`. Claude đã sửa cấu hình. Test `tests/agent/test_service_engine.py::test_production_config_defaults_to_co_dinh_engine` đang trượt: đổi tên và kỳ vọng thành mặc định `agentic`, giữ ý "cấu hình production phải là engine đã chốt". Không đổi `config/settings.test.yaml`. Đợt `VERIFY-don-vi-1-73` đã xong (chỉ sửa `app/verify/number.py` + test), không đụng lại.

## Lượt 2 (28/11) – CHỈ làm phần lõi, không làm lại phần đã xong

Lượt 1 đã xong: văn bản tool khi không có kết quả (4 tool), prompt `tac_tu`/`hoi_them`, nhãn web + `mock.ts`, test engine mặc định agentic. **Chưa có gì** của yêu cầu 1–6. Lượt này bắt buộc làm hết 1–6:

- Tạo `config/prompts/tra_loi_trung_thuc.v1.md`.
- Trong `app/orchestration/ask.py`, viết **một** hàm dùng chung, ví dụ `tra_loi_trung_thuc(llm, cau_hoi_che, tom_tat_tool, ma_ly_do, kiem_chung_fn, han_chot) -> AskResult`. Hàm gọi LLM một lần, kiểm chứng bằng đúng bộ kiểm hiện có, lược câu có số trượt, rơi về câu dự phòng ngắn mới. Gọi hàm này ở **mọi** chỗ đang trả `NO_SOURCE_MESSAGE`/`OUT_OF_SCOPE_MESSAGE`:
  - `ask.py` các dòng ~833, 862, 880, 1539, 1731, 1891 (Claude đã grep);
  - nút `agent_du_phong` trong `app/agent/nodes.py` (~dòng 825) và chỗ trả `OUT_OF_SCOPE_MESSAGE` (~dòng 259).

  Giữ câu cố định khi bị chặn tấn công. Giữ `ERROR_MESSAGE`/`NOT_READY_MESSAGE`.
- Span tracer `tra_loi_trung_thuc`.
- Toàn bộ mục Test của brief cho **cả hai** engine (LLM giả).
- Không dừng để hỏi. Thiếu gì thì chọn phương án an toàn, ghi vào báo cáo.
- `tests/api`: Claude sẽ chạy, bạn không cần.

Ghi đè `plan/briefs/TRA-LOI-TU-NHIEN-bao-cao.md`, đối chiếu từng yêu cầu 1–11: đạt / thiếu.
