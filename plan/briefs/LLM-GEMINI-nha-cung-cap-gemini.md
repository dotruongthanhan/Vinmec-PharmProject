# LLM-GEMINI – Thêm nhà cung cấp LLM Gemini (cổng tương thích OpenAI), xoay 8 khoá miễn phí

Người làm: Codex `gpt-6.1-terra` high. Được chạy ruff, pytest. **Không** đọc `.env`, không gọi `load_env_file()`, không mạng, không cài gói, không commit.

## Bối cảnh

Tài khoản DeepSeek hết số dư (HTTP 402, 27/11). Chủ kho thêm 8 khoá Gemini **miễn phí** vào `.env`: `GEMINI_API_KEY_1` … `GEMINI_API_KEY_8`. **`GEMINI_API_KEY` (không số) là khoá trả phí**, đang dùng cho nhúng (`embedding.provider: gemini`). LLM **không bao giờ** được dùng khoá này.

Claude đã thử ngoài kho (27/11), dùng `DeepSeekLLM` sẵn có, chỉ đổi URL thành `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` và dùng khoá số 1:
- mô hình `gemini-3.5-flash-lite` có trong danh sách (`models/gemini-3.5-flash-lite`, vào 1.048.576 / ra 65.536 token);
- `complete_json` với `response_format: json_object` + `reasoning_effort: low` trả JSON đúng, có `usage` dạng OpenAI;
- 4 câu agentic DEMO-02/DEMO-04 đều `ok` trong 2–14 giây.

## Yêu cầu

1. **Lớp máy khách:** tách phần chung của `app/providers/deepseek_llm.py` thành máy khách "tương thích OpenAI" nhận `url` (hoặc thêm tham số `url` có mặc định DeepSeek). Thêm cài đặt `gemini` dùng URL trên. **Giữ nguyên hành vi DeepSeek**: mọi test DeepSeek cũ vẫn qua, vết `llm` vẫn ghi như cũ. Tên mô hình trên vết là tên thật (`gemini-3.5-flash-lite`).
2. **Cấu hình** (`app/config/settings.py` `LLMSettings` + `config/settings.yaml`):
   - `llm.provider: "deepseek" | "gemini"` (giữ `fake`);
   - `llm.khoa_env: list[str]`: tên biến môi trường chứa khoá, theo thứ tự. Mặc định theo nhà cung cấp: deepseek → `["DEEPSEEK_API_KEY"]`; gemini → `GEMINI_API_KEY_1` … `GEMINI_API_KEY_8`.
   - **Kiểm khi nạp cấu hình:** provider `gemini` mà `khoa_env` chứa đúng `GEMINI_API_KEY` thì báo lỗi cấu hình (khoá trả phí); tên biến chỉ nhận mẫu `^[A-Z][A-Z0-9_]{0,63}$`.
   - Khoá đọc bằng `get_secret` sẵn có. Biến trống hoặc thiếu thì **bỏ qua khoá đó**, ghi cảnh báo chỉ có **tên biến** (không ghi giá trị). Không còn khoá nào → `ConfigError`.
   - `config/settings.yaml`: đổi sang `provider: "gemini"`, `model: "gemini-3.5-flash-lite"`. Giữ dòng chú thích cách quay về DeepSeek (`provider: "deepseek"`, `model: "deepseek-flash"`). `reasoning.reasoning_effort: "low"` giữ nguyên (Gemini nhận).
   - `config/settings.test.yaml` không đổi hành vi test (vẫn `fake` nếu đang là `fake`).
3. **Xoay khoá:** mỗi lần gọi `complete_json` **bắt đầu ở khoá kế tiếp** (vòng tròn, an toàn luồng bằng khoá `threading.Lock`), để chia đều hạn mức theo phút của bản miễn phí.
   - Gặp 429 hoặc 5xx thì chuyển khoá kế (`post_json` đã làm việc này theo `attempt % len(keys)`; truyền danh sách khoá **đã xoay** để khoá đầu là khoá của lượt).
   - Số lần thử khi gặp 429 phải ≥ số khoá (tối đa 8), để thử hết khoá trước khi báo lỗi. Lỗi khác 429/5xx giữ hành vi cũ.
   - HTTP 402/403 của một khoá: báo lỗi như cũ, không thử khoá khác.
   - Thông báo lỗi không chứa khoá: kiểm `_error_message` đã che mọi khoá trong danh sách.
4. **Bảng giá tracer:** `tracer.bang_gia` thêm `gemini-3.5-flash-lite` giá 0 (bản miễn phí) nếu cấu trúc bảng giá cho phép; không thì ghi chú trong báo cáo.
5. **Embedding không đổi:** `embedding.provider: gemini` vẫn đọc `GEMINI_API_KEY` như cũ. Không đụng `gemini_embed.py`.

## Test

`tests/providers/test_gemini_llm.py` (hoặc nơi test DeepSeek đang nằm), dùng `httpx.MockTransport`, **không mạng**:
- gửi đúng URL Gemini, header `Authorization: Bearer <khoá>`, `model`, `response_format`, `reasoning_effort`;
- 3 lần gọi liên tiếp dùng khoá 1, 2, 3 (xoay vòng); gọi thứ 9 quay về khoá 1;
- khoá 1 trả 429, khoá 2 trả 200 → thành công, tổng 2 yêu cầu;
- cả 8 khoá trả 429 → `ProviderError` retryable, đúng 8 yêu cầu, thông báo **không** chứa chuỗi khoá nào;
- 402 → lỗi ngay, 1 yêu cầu;
- nạp cấu hình: gemini + `khoa_env: ["GEMINI_API_KEY"]` → lỗi; tên biến sai mẫu → lỗi; thiếu 3 biến → dùng 5 khoá còn lại, cảnh báo chỉ có tên biến; thiếu hết → `ConfigError`;
- `build_llm` với provider `deepseek` vẫn trả máy khách DeepSeek, URL DeepSeek (test cũ qua);
- vết `llm` của Gemini ghi `mo_hinh = gemini-3.5-flash-lite`, token từ `usage`.

## Tệp

Được sửa/tạo: `app/providers/deepseek_llm.py` (hoặc tách `openai_compat_llm.py` + giữ `DeepSeekLLM` làm tên tương thích), `app/llm/setup.py`, `app/config/settings.py`, `config/settings.yaml`, `config/settings.test.yaml` (chỉ nếu bắt buộc), `.env.example` (thêm tên `GEMINI_API_KEY_1…8` **không giá trị**, kèm chú thích "khoá miễn phí cho LLM; GEMINI_API_KEY là khoá trả phí cho nhúng"), `tests/providers/**`, `tests/config/**`. Báo cáo: `plan/briefs/LLM-GEMINI-bao-cao.md`.

**Cấm:** đọc `.env`; gọi `load_env_file()`; mạng; đổi `app/verify`, `app/agent/**` (trừ khi bắt buộc để truyền máy khách, ghi lý do); đổi `gemini_embed.py`; cài gói; commit.

## Nghiệm thu (Claude chạy)

```
uv run ruff check app tests && uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider tests/providers tests/config tests/agent tests/orchestration tests/tracing
```
Claude chạy thật 4 câu VZ2 và 15 câu VZ5 với `gemini-3.5-flash-lite`, kiểm xoay khoá qua vết (`mo_hinh`), và dò log, vết không chứa giá trị khoá.
