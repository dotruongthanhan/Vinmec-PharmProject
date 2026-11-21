# T61 – Nhà cung cấp nhúng Gemini (`gemini-embedding-2`) và lệnh nhúng kho đoạn

Agent: agy `gemini-4-hydrogen-xhigh` (Codex hết quota tới 24/11). **Không gọi công cụ shell, không gọi mạng.** Chỉ ghi tệp. Claude tự chạy `uv`, `ruff`, `pytest` khi review.

Đọc: `AGENTS.md`, `app/core/interfaces.py` (`Embedder`), `app/providers/openrouter_embed.py`, `app/providers/cached_embedder.py`, `app/providers/http.py`, `app/config/settings.py` (`EmbeddingSettings`, `get_secret`), `config/settings.yaml` (khối `embedding`), ba nơi đang khởi tạo bộ nhúng thật: `app/retrieval/setup.py:46`, `app/orchestration/evidence.py:111`, `app/kb/dictionary/candidates.py:46`.

## Bối cảnh

Người dùng chốt ngày 19/11: bỏ `nvidia/nemotron-3.5-embed-1b:free` (OpenRouter, trả 429/504), chuyển sang **Google `gemini-embedding-2`**. Khoá nằm trong `.env` với tên `GEMINI_API_KEY`.

Claude đã thử thật trên 1.469 đoạn nhãn FDA, 20 câu hỏi Việt và Anh:
- recall@5 = 1,00 cho cả hai ngôn ngữ;
- MRR 0,88 (Việt), 0,92 (Anh);
- `outputDimensionality=2048`, có `taskType`.

Số chiều giữ **2048**, vì cột `embedding halfvec(2048)` trong `db/schema.sql` không phải đổi.

API: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents`, header `x-goog-api-key: <khoá>`. Thân yêu cầu:

```json
{"requests": [{"model": "models/{model}", "content": {"parts": [{"text": "..."}]}, "outputDimensionality": 2048, "taskType": "RETRIEVAL_DOCUMENT"}]}
```

- Tối đa 100 yêu cầu mỗi lần gọi.
- Phản hồi: `{"embeddings": [{"values": [...]}]}`, cùng thứ tự với yêu cầu.
- Truy vấn dùng `taskType: "RETRIEVAL_QUERY"`.

## Phạm vi

**Được tạo / sửa:**
- `app/providers/gemini_embed.py` (mới): lớp `GeminiEmbedder` cài `Embedder`.
- Một hàm dựng chung, ví dụ `app/providers/embedder_factory.py: build_embedder(settings, client)`, chọn theo `settings.embedding.provider` (`gemini` | `openrouter` | `fake`). Thay **cả ba** nơi đang gọi thẳng `OpenRouterEmbedder(...)` bằng hàm này. Riêng `candidates.py` dòng 36 đang bắt buộc `openrouter`: đổi thành chấp nhận `gemini`.
- `config/settings.yaml`: `embedding.provider: "gemini"`, `active: "gemini-embedding-2"`, `dimensions: 2048`, `batch_size: 100`. Giữ `cache_path`.
- Lệnh mới `uv run python -m app.retrieval.embed_corpus`:
  - nhúng mọi đoạn của `data/kb_curated/chunks.jsonl` qua `CachedEmbedder`;
  - chạy tiếp được sau khi dừng (đoạn đã có trong cache thì bỏ qua);
  - in tiến độ;
  - cuối cùng in: tổng số đoạn, số đoạn đã có vector, số đoạn lỗi.
  - Có `--limit N` để thử ít đoạn.
- Lệnh `uv run python -m app.retrieval.embed_corpus --xoa-cache-cu`: xoá tệp cache khi khoá cũ không thuộc mô hình hiện tại. Cache chỉ lưu băm nên không lọc được theo mô hình; vì vậy lệnh **chỉ xoá khi có cờ này**, và in số dòng trước khi xoá.
- Test mới trong `tests/providers/` và `tests/retrieval/`. Dùng `httpx.MockTransport`, **không gọi mạng**.
- `docs/du-lieu/openfda-rag.md`: mục cache nhúng, ghi mô hình mới và lệnh.
- `plan/reports/T61.md`.

**Cấm:**
- Sửa `db/**`, `data/**`.
- Đổi số chiều.
- In hay ghi khoá.
- Đổi hợp đồng API.
- Xoá lớp `OpenRouterEmbedder`: giữ làm dự phòng.

## Yêu cầu chi tiết

1. `GeminiEmbedder`:
   - `embed_documents` dùng `RETRIEVAL_DOCUMENT`, `embed_query` dùng `RETRIEVAL_QUERY`.
   - Chia lô theo `batch_size`, tối đa 100.
   - Kiểm mỗi vector đúng `dimensions` và hữu hạn; sai thì ném `ProviderError` (`retryable=False`).
   - Thử lại khi gặp 429 / 5xx, có chờ tăng dần. Tối đa `max_attempts`, lấy theo cách bộ OpenRouter đang làm.
   - Văn bản rỗng ném `ValueError`.
   - Khoá lấy bằng `get_secret("GEMINI_API_KEY")`, không đọc biến môi trường trực tiếp. Có test kiến trúc kiểm chuyện này.
2. **Khoá cache phải khác mô hình cũ.** `CachedEmbedder` đã băm `model_id`, nên chỉ cần truyền đúng `active`. Viết test chứng minh cùng văn bản nhưng khác mô hình thì ra khoá khác.
3. Thiếu `GEMINI_API_KEY`: RAG phải lùi về tìm theo từ khoá như hiện nay, không lỗi. Có test.
4. Mọi test cũ của OpenRouter vẫn qua.

## Nghiệm thu (Claude chạy khi review)

- `uv run ruff check .`
- `uv run pytest -q -p no:cacheprovider`: 0 trượt.
- Claude chạy thật `uv run python -m app.retrieval.embed_corpus --limit 20` với khoá thật.

## Cấm làm

Không chạy shell. Không gọi mạng. Không commit.
