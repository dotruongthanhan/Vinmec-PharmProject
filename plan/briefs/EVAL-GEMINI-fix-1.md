# EVAL-GEMINI-fix-1 – Chờ khoá khi hết hạn mức phút, nhịp chạy bộ chấm, mã che `[MA_n]` lọt ra câu trả lời chế độ chung

Người làm: Codex `gpt-6.1-terra` high. Đọc `plan/briefs/LLM-GEMINI-nha-cung-cap-gemini.md`, `plan/briefs/LLM-GEMINI-bao-cao.md`, `app/providers/key_router.py`, `app/providers/llm_client.py`, `app/eval/hoi_dap.py`, `app/orchestration/ask.py` (phần `ask_global`), `app/agent/asker.py`, `app/agent/nodes.py`, `app/deid/**` (chỉ đọc).

## Claude chấm thật (28/11 0h, `CDSS_PROFILE=e2e`, agentic, `gemini-3.5-flash-lite`, 8 khoá miễn phí, DB RDS)

| Bộ | Kết quả |
| :--- | :--- |
| 15 câu minh hoạ (`cau_hoi_minh_hoa_v1.jsonl`) | Đạt 4/15. Đạt hình 6/15, vẽ khi không nên 0. Trạng thái: ok 10, khong_co_nguon 3, ngoai_pham_vi 1, loi 1 |
| 90 câu (`cau_hoi_v1.jsonl`) | Đạt 22/90. **55 câu `loi`, đều thuộc chế độ ca, mỗi câu ~0,5 s.** "Rò PII" 6 câu chế độ chung |

**Nguyên nhân 55 `loi`** (Claude tái hiện 8 câu liên tiếp): cả 8 khoá trả HTTP 429 trong 2,5 giây. `KeyRouter` cho tất cả nghỉ 60 s rồi ném `ProviderError("tất cả khoá đang nghỉ, sớm nhất sau 54 giây")` ngay, nên câu hỏi lỗi tức thì. Vài phút sau, gọi lại khoá 1 và 5 đều 200. Kết luận: chạm **hạn mức theo phút** (yêu cầu/phút hoặc token/phút) của bản miễn phí, do bộ chấm chạy liên tục và prompt agent dài. Có thể 8 khoá dùng chung một dự án Google nên chung hạn mức; chưa kiểm được.

**"Rò PII"** (HD-CH-012, 013, 017, 021, 024, 025): câu trả lời chế độ chung hiện nguyên mã che, ví dụ "ca liên quan đến warfarin là ca [MA_1] và ca [MA_2]". Không lộ định danh thật, nhưng dược sĩ không đọc được và bộ chấm đếm là rò.

## Yêu cầu

1. **KeyRouter chờ thay vì lỗi ngay** (vẫn là mã chỉ dùng cho dev, giữ ghi chú cũ).
   - Thêm cấu hình `llm.cho_khoa_toi_da_giay` (mặc định 0 = hành vi cũ; `config/settings.yaml` dev đặt 70).
   - Khi mọi khoá đang nghỉ và thời gian chờ ngắn nhất ≤ trần, ngủ tới lúc khoá sớm nhất hết nghỉ rồi thử. Không vượt `han_chot` của lượt hỏi: nếu chờ sẽ vượt hạn chót thì lỗi như cũ. Hàm ngủ tiêm vào được để test.
   - Đọc `retryDelay` trong thân lỗi 429 của Gemini (`error.details[].retryDelay`, dạng `"37s"`) nếu có, để đặt thời gian nghỉ đúng hơn 60 s.
   - Test: mọi khoá nghỉ 5 s, trần 70 → ngủ 5 s rồi thành công; nghỉ 90 s, trần 70 → lỗi ngay; hạn chót còn 3 s → lỗi ngay; đọc `retryDelay: "37s"` → nghỉ 37 s.
2. **Nhịp chạy bộ chấm:** `tools/cham_hoi_dap.py`/`app/eval/hoi_dap.py` thêm `--nghi_giua_cau GIAY` (mặc định 0, tối đa 120). Báo cáo `tong_hop.md` ghi số câu `loi` do nhà cung cấp, tách khỏi trượt nội dung: thêm dòng đếm theo `ma_loi` nếu `AskResult` có; nếu không có thì đếm theo `trang_thai == "loi"`.
3. **Mã che `[MA_n]` trong chế độ chung:** tìm vì sao câu trả lời `ask_global`/agentic chung không được khôi phục mã ca trước khi trả.
   - Mã ca giả lập (`HS-xxx`, `DEMO-xx`) là mã nội bộ mà giao diện đang hiện. Nếu chính sách che coi nó là định danh thì phải **khôi phục bằng phiên che** trước khi trả, như chế độ ca.
   - Không được bỏ che họ tên, SĐT, mã người bệnh `NB-…`. Ghi rõ trong báo cáo mã nào được khôi phục và vì sao.
   - Test: câu trả lời chung nhắc 2 ca → không còn chuỗi `[MA_`; canary họ tên vẫn bị che.
   - Bộ chấm: tiêu chí `ro_pii` không coi mã ca (đúng mẫu mã ca trong phạm vi) là rò, nhưng vẫn coi `[MA_n]` còn sót là lỗi hiển thị. Thêm tiêu chí phụ `con_ma_che`, không tính vào rò PII.

## Tệp

`app/providers/key_router.py`, `app/providers/llm_client.py`, `app/config/settings.py`, `config/settings.yaml`, `app/eval/hoi_dap.py`, `tools/cham_hoi_dap.py`, `app/orchestration/ask.py`, `app/agent/asker.py`, `app/agent/nodes.py` (chỉ chỗ khôi phục), `tests/providers/**`, `tests/eval/**`, `tests/agent/**`, `tests/orchestration/**`. Báo cáo: `plan/briefs/EVAL-GEMINI-fix-1-bao-cao.md`.
**Cấm:** đọc `.env`, gọi `load_env_file()`, mạng, đổi `app/verify`, đổi `app/deid` (chỉ đọc), cài gói, commit.

## Nghiệm thu

```
uv run ruff check app tests tools && uv run ruff format --check app tools tests/providers tests/eval tests/agent tests/orchestration
uv run pytest -q -p no:cacheprovider tests/providers tests/config tests/eval tests/agent tests/orchestration
```
Claude chấm lại 90 + 15 câu với `--nghi_giua_cau 4`.
