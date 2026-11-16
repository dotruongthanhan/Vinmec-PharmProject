# T05-fix-1 – Bước LLM bị cắt vì hết hạn mức token

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort xhigh) · **Ngày:** 16/11/2026 (phiên 3)
**Đọc trước:** `AGENTS.md`; `app/providers/deepseek_llm.py`, `app/llm/setup.py`, `app/llm/synthesizer.py`, `app/config/settings.py`, `config/settings.yaml` (mục `llm`), `tests/providers/test_deepseek_llm.py`.

## 1. Lỗi đã đo được (người review chạy thật với DeepSeek)

Ca DEMO-02, 3 lần gọi liên tiếp đều trả `trang_thai="loi_llm"`, cảnh báo `Lỗi LLM: dau_ra_khong_hop_le`, mỗi lần khoảng 22 giây. Đo một lần gọi:

```text
max_tokens: 4096 | finish_reason: length | completion_tokens: 4096 | reasoning_tokens: 4096 | content_len: 0
```

Mô hình `deepseek-flash` dùng hết 4096 token cho phần suy luận, không còn token cho câu trả lời. Ca DEMO-06 (ngắn hơn) thì qua. Hệ quả: ca dài một chút là mất toàn bộ phần AI, và mã lỗi không cho biết nguyên nhân.

## 2. Phạm vi file

```text
app/providers/deepseek_llm.py
app/llm/setup.py              (chỉ phần truyền tham số cho lớp gọi DeepSeek)
app/llm/synthesizer.py        (chỉ phần xử lý ProviderError, mục 3.4)
app/config/settings.py        (chỉ lớp cấu hình llm)
config/settings.yaml          (chỉ mục llm)
tests/providers/test_deepseek_llm.py
tests/llm/test_setup.py
tests/llm/test_synthesizer.py
```

Ngoài ra chạy `ruff format` cho đúng các thư mục `app/llm`, `app/verify`, `tests/llm`, `tests/verify`, `tests/providers` (đang có file lệch định dạng). Không đụng `app/api`, `app/kb`, `app/retrieval`, `app/orchestration`, `web/`.

## 3. Yêu cầu

1. **Hạn mức:** thêm vào cấu hình `llm` hai giá trị đọc từ `config/settings.yaml`: `max_tokens: 16000` và `max_tokens_retry: 32000`. Không viết cứng số trong code.
2. **Giảm suy luận nếu API cho phép:** trước khi viết, gọi thử thật (được dùng mạng cho đúng việc này; khoá lấy qua `get_secret`, không in khoá) để xác định `https://api.deepseek.com/chat/completions` với mô hình `deepseek-flash` có nhận tham số điều khiển suy luận hay không (ví dụ `reasoning_effort`, `thinking`). Nếu có tham số được chấp nhận, làm giảm `reasoning_tokens` mà vẫn trả JSON đúng: thêm khoá cấu hình `llm.reasoning` và gửi kèm. Nếu không có: không gửi gì, và ghi trong báo cáo đã thử tham số nào, phản hồi ra sao. Không đoán.
3. **Thử lại khi bị cắt:** `finish_reason == "length"` → lỗi riêng mã `het_han_muc_token`, không dùng chung `dau_ra_khong_hop_le`. Trong `complete_json`: gặp lỗi này thì gọi lại **đúng một lần** với `max_tokens_retry`; vẫn bị cắt mới ném lỗi ra ngoài.
4. **Thông báo:** trong `synthesizer.py`, cảnh báo viết bằng câu tiếng Việt theo mã lỗi:
   - `het_han_muc_token` → `Bước AI bị cắt vì vượt hạn mức độ dài; đang hiển thị kết quả của bộ luật.`
   - mã khác → `Bước AI gặp lỗi (<mã>); đang hiển thị kết quả của bộ luật.`
   Không đưa nội dung ca hay nội dung phản hồi của mô hình vào cảnh báo.
5. Lưu `last_usage` cả khi lỗi (để đo). Không ghi log nội dung tin nhắn.

## 4. Kiểm thử phải có (không gọi mạng trong test)

- Phản hồi giả bị cắt lần 1, hợp lệ lần 2 → trả kết quả; lần gọi thứ hai có `max_tokens == max_tokens_retry`.
- Bị cắt cả hai lần → lỗi mã `het_han_muc_token`; đúng 2 lần gọi HTTP.
- `Synthesizer.run` với LLM giả ném `het_han_muc_token` → `trang_thai="loi_llm"`, mọi phát hiện của luật còn nguyên, cảnh báo đúng câu ở mục 3.4.
- `load_settings().llm.max_tokens == 16000` và `max_tokens_retry == 32000`.
- Toàn bộ test hiện có vẫn qua.

## 5. Nghiệm thu

```bash
uv run ruff check app/llm app/verify app/providers tests/llm tests/verify tests/providers
uv run ruff format --check app/llm app/verify app/providers/deepseek_llm.py tests/llm tests/verify tests/providers
uv run pytest -q tests/llm tests/verify tests/providers tests/architecture -p no:cacheprovider
```

Người review sẽ chạy thật 3 lần trên DEMO-02 và DEMO-06: cả hai phải có phần AI ở cả 3 lần.

## 6. Cấm làm

Không đổi prompt, lược đồ đầu ra, bước kiểm chứng. Không đổi mô hình mặc định. Không thêm thư viện. Không commit, không push. Trả lời theo mẫu trong `AGENTS.md`, kèm số đo `reasoning_tokens` và thời gian trước, sau.
