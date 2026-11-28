# EVAL-GEMINI-fix-2 – Nối chờ khoá vào luồng thật, tìm mã che sót; quy tắc "dược sĩ bảo vẽ thì vẽ"

Người làm: Codex `gpt-6.1-terra` high. Đọc `plan/briefs/EVAL-GEMINI-fix-1.md`, `plan/briefs/EVAL-GEMINI-fix-1-bao-cao.md`, `config/prompts/ky_nang_minh_hoa.v1.md`.

## Claude review fix-1 (28/11)

- ruff check + format sạch.
- pytest: providers 76, config 44, eval 29, agent 271, orchestration 85, api 218 (2 bỏ qua).
- `--nghi_giua_cau` và tiêu chí `con_ma_che` đã có.
- Chưa xong (bạn đã tự báo):
  - chờ khoá và `retryDelay` chưa nối vào luồng gọi thật, vì `app/llm/setup.py` và `app/providers/http.py` nằm ngoài phạm vi;
  - chưa tìm ra nguyên nhân `[MA_n]` sót trong câu trả lời chế độ chung.

## Yêu cầu

1. **Nối chờ khoá vào luồng thật.** Được sửa thêm `app/llm/setup.py`, `app/providers/http.py`.
   - `cho_khoa_toi_da_giay` đi từ cấu hình tới `KeyRouter` thật.
   - Đọc `retryDelay` (`error.details[].retryDelay`, dạng `"37s"`) và header `Retry-After` từ phản hồi 429, truyền vào `bao_ket_qua`.
   - Truyền hạn chót của lượt hỏi xuống máy khách. Nếu cách hiện có không cho phép thì dùng `contextvars` đặt ở nơi đồ thị gọi LLM; ghi cách chọn trong báo cáo.
   - Test tích hợp với `httpx.MockTransport` qua **`build_llm`** (không dựng tay `KeyRouter`):
     - 8 khoá đều 429 kèm `retryDelay: "2s"` → ngủ ≈ 2 s (đồng hồ/ngủ giả) rồi 200;
     - `retryDelay: "90s"` với trần 70 → lỗi ngay;
     - hạn chót còn 1 s → lỗi ngay.
2. **Tìm và sửa `[MA_n]` sót** ở chế độ chung (HD-CH-012, 013, 017, 021, 024, 025; engine agentic). Ví dụ câu trả lời thật: "ca liên quan đến warfarin là ca [MA_1] và ca [MA_2]".
   - Lần theo đường đi của câu trả lời agentic chế độ chung: `AgenticAsker.ask_global` → đồ thị → nút trả kết quả. Tìm chỗ khôi phục bằng phiên che bị bỏ qua (ví dụ: phiên che khác giữa lúc che kết quả tool và lúc khôi phục, hoặc chỉ khôi phục ở `co_dinh`).
   - Tái hiện bằng LLM giả trả đúng câu mẫu trên, dựa vào kết quả tool nhiều ca, khẳng định câu trả lời cuối **không** còn `[MA_` và có mã ca thật trong phạm vi.
   - Họ tên, SĐT, `NB-…` vẫn bị che.
3. **Quy tắc vẽ (chủ kho chốt 28/11):** giữ nguyên tiêu chí tự vẽ hiện có (so sánh nhiều nhóm, xu hướng thời gian, vị trí so với ngưỡng, nhiều cặp tương tác, "nếu… thì…"; không vẽ khi một con số, thiếu dữ liệu, hỏi định nghĩa). **Thêm:** khi dược sĩ **yêu cầu vẽ** thì phải vẽ.
   - Prompt `ky_nang_minh_hoa.v1.md`: thêm câu đầu đoạn tiêu chí: "Nếu dược sĩ yêu cầu vẽ, biểu đồ, minh hoạ hay hình thì phải lấy dữ liệu cần thiết và gọi `ve_bieu_do`, kể cả khi câu hỏi không thuộc các trường hợp dưới đây. Chỉ bỏ qua khi không có dữ liệu phù hợp, và khi đó nói rõ thiếu gì."
   - Máy chủ:
     - hàm thuần `nguoi_dung_yeu_cau_ve(cau_hoi)`: nhận các cụm "vẽ", "biểu đồ", "đồ thị", "minh hoạ", "minh họa", "hình", "chart", "plot"; có ranh giới từ, không bắt "hình thức", "hình ảnh học", "định hình";
     - khi yêu cầu vẽ mà sau vòng lập kế hoạch cuối chưa có lời gọi `ve_bieu_do` thành công, cho **thêm đúng một vòng** với nhắc ngắn cố định "Dược sĩ đã yêu cầu hình; hãy gọi ve_bieu_do với bộ dữ liệu đã có hoặc lấy dữ liệu cần thiết." Vẫn trong trần lượt tool và hạn chót;
     - vẫn không có hình thì giữ dòng "Chưa dựng được hình cho câu hỏi này." (fix-3).
   - Test:
     - nhận diện cụm, gồm các ca không được bắt;
     - LLM giả lần đầu không vẽ, có yêu cầu vẽ → thêm một vòng → vẽ → có `minh_hoa`;
     - LLM giả vẫn không vẽ → dòng dự phòng, không lặp quá một vòng;
     - câu không yêu cầu vẽ → không thêm vòng.
   - Bộ chấm: không đổi kỳ vọng 15 câu VZ5.

## Tệp

Như fix-1, thêm `app/llm/setup.py`, `app/providers/http.py`, `config/prompts/ky_nang_minh_hoa.v1.md`, `app/agent/graph.py` (nếu cần cho vòng thêm). Báo cáo: mục "fix-2" trong `plan/briefs/EVAL-GEMINI-fix-1-bao-cao.md`.
**Cấm:** như fix-1.

## Nghiệm thu

```
uv run ruff check app tests tools && uv run ruff format --check app tools tests/providers tests/eval tests/agent tests/orchestration
uv run pytest -q -p no:cacheprovider tests/providers tests/config tests/llm tests/eval tests/agent tests/orchestration
```
Claude chấm lại 90 + 15 câu với `--nghi_giua_cau 4`.
