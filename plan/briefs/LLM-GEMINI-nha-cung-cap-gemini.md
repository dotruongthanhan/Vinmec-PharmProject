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

## Bổ sung của chủ kho (27/11, thay các chỗ mâu thuẫn ở trên)

### A. Bỏ tên nhà cung cấp khỏi mã

Mã không mang tên riêng của nhà cung cấp hay mô hình. Tên mô hình chỉ còn trong **cấu hình**.
- `app/providers/deepseek_llm.py` → `app/providers/llm_client.py`, lớp `DeepSeekLLM` → `ChatLLMClient`. URL **không** hằng trong mã: lấy từ cấu hình `llm.url` (bắt buộc `https://`).
- `llm.provider` chỉ còn `"chat_api"` (máy khách HTTP kiểu chat completions) và `"fake"`. Không còn giá trị `"deepseek"`/`"gemini"`. Cấu hình cũ có `provider: "deepseek"` thì báo lỗi rõ ràng, chỉ cách đổi.
- Các nhánh `provider == "deepseek"` và chuỗi `"DEEPSEEK_API_KEY"` trong `app/container.py`, `app/llm/setup.py` đổi sang logic chung: thiếu khoá → lùi về chế độ không có LLM như cũ.
- Đổi tên test `tests/providers/test_deepseek_llm.py` → `test_llm_client.py`. Sửa mọi test đang dựng `provider="deepseek"` hay import `DeepSeekLLM`. Danh sách tệp liên quan (Claude grep): `app/container.py`, `app/llm/setup.py`, `tests/agent/test_service_engine.py`, `tests/api/test_ai_progress.py`, `test_ai_routes.py`, `test_ask_progress.py`, `test_ask_routes.py`, `test_ask_server_history.py`, `test_body_limit_auth_first.py`, `test_llm_limits.py`, `tests/config/test_settings.py`, `tests/llm/test_case_context_deid.py`, `test_setup.py`, `test_synthesizer.py`, `tests/orchestration/test_ai_review.py`, `test_ask.py`, `test_ask_deid.py`, `test_ask_global_none_fields.py`, `test_graph.py`, `test_progress.py`, `test_prompt_single_pass.py`, `tests/test_container.py`.
- `config/settings.yaml`:
  ```yaml
  llm:
    provider: "chat_api"
    url: "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    model: "gemini-3.5-flash-lite"
    khoa_env: [GEMINI_API_KEY_1, …, GEMINI_API_KEY_8]
  ```
  Kèm khối chú thích cách quay về nhà cung cấp cũ (url + model + `khoa_env: [DEEPSEEK_API_KEY]`).
- Kiểm chặn khoá trả phí: `khoa_env` không được chứa `GEMINI_API_KEY` (đúng tên, không số) – áp dụng **bất kể url**.
- Nghiệm thu: `rg -i "deepseek" app tests` → **0 dòng**. Ngoài phạm vi: `config/` (chỉ chú thích quay về), `plan/`, `docs/`, và tệp nhúng `gemini_embed.py` (phần nhúng giữ nguyên, không đổi đợt này).

### B. Bộ định tuyến khoá (`app/providers/key_router.py`, lớp `KeyRouter`)

**Chỉ dùng cho dev.** Đầu tệp, và ở chỗ dùng trong `llm_client.py` và `setup.py`, ghi chú thích:
`# CHỈ DÙNG CHO DEV: xoay nhiều khoá miễn phí. Triển khai thật: xoá module này, dùng một khoá trả phí (khoa_env một phần tử).`
Thêm dòng tương tự ở `config/settings.yaml` cạnh `khoa_env`.

Hành vi:
- Giữ danh sách khoá (giá trị) và **số thứ tự** (1..n). Mọi log, vết, thông báo lỗi chỉ dùng số thứ tự, **không bao giờ giá trị**. `__repr__`/`__str__` không lộ khoá.
- `chon()` trả `(so_thu_tu, khoa)` theo vòng tròn, **bỏ qua khoá đang nghỉ**. An toàn luồng (`threading.Lock`).
- `bao_ket_qua(so_thu_tu, ma_http, retry_after_giay=None)`:
  - 200 → xoá trạng thái nghỉ;
  - 429 → nghỉ `retry_after` nếu có (đọc header `Retry-After` hoặc trường `retryDelay` trong thân lỗi nếu dễ lấy), không thì 60 s; lần 429 liên tiếp thứ 3 của cùng khoá → nghỉ 15 phút (hết hạn mức ngày của bản miễn phí);
  - 401/403 → tắt khoá đến hết tiến trình (khoá sai/bị thu hồi);
  - 5xx → không phạt khoá.
- Tất cả khoá đang nghỉ → `ProviderError(retryable=True)` với thông báo "tất cả khoá đang nghỉ, sớm nhất sau N giây", **không** ngủ chờ quá 2 s.
- Đồng hồ tiêm vào được (`monotonic`) để test không ngủ thật.
- `post_json` (hoặc lớp gọi) lấy khoá từ router **mỗi lần thử**, báo kết quả lại cho router. Một lần `complete_json` thử tối đa `min(số khoá, 8)` khoá khi gặp 429/401/403/5xx; 402 → lỗi ngay. Router cũng dùng được với một khoá (khi triển khai thật bỏ router thì vẫn chạy).
- Vết `llm`: thêm thuộc tính `khoa_so` (số thứ tự) và `so_khoa_da_thu`; thêm khoá thuộc tính vào danh sách cho phép của `app/tracing/models.py`.

Test `tests/providers/test_key_router.py` (đồng hồ giả, không mạng):
- vòng tròn 1→2→3→1;
- 429 khoá 2 → bỏ qua 2 trong 60 s, sau 60 s dùng lại;
- `Retry-After: 5` → nghỉ 5 s;
- 3 lần 429 liên tiếp → nghỉ 15 phút;
- 403 → tắt vĩnh viễn trong tiến trình;
- tất cả nghỉ → lỗi retryable, thông báo có số giây, không chứa khoá;
- 10 luồng gọi `chon()` đồng thời không lỗi, phân bố đều (±1);
- `repr(router)` và mọi thông báo lỗi không chứa giá trị khoá.

Tệp được sửa thêm: tất cả tệp test ở mục A, `app/container.py`, `app/providers/http.py`, `app/tracing/models.py`, `app/providers/key_router.py` (mới).
