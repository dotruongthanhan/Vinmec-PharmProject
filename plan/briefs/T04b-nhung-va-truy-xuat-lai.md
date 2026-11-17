# T04b – Nhúng, xếp hạng lại, truy xuất lai

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort high) · **Ngày:** 16/11/2026
**Đọc trước (bắt buộc):** `AGENTS.md`; `plan/plan-1.1-kien-truc-chi-tiet.md` mục 6 (toàn bộ) và mục 3; **chỉ đọc**: `app/core/types.py`, `app/core/interfaces.py`, `app/core/errors.py`, `app/config/settings.py`, `app/providers/` (các lớp đã có), `app/container.py`.

**Nhiều task khác đang chạy song song.** Chỉ tạo và sửa file ở mục 2. Không sửa `pyproject.toml` (`httpx`, `numpy` đã cài), `app/container.py`, `app/core/`, `app/config/`, các file đã có trong `app/providers/`, `app/kb/`, `app/llm/`, `app/verify/`, `app/api/`, `app/ui/`, `web/`, `config/`, `data/`. **Không đọc, không in `.env`.** Test không được gọi mạng thật.

**Thư mục tạm:** không tạo thư mục tạm trong kho; `pytest` chạy với `--basetemp` ngoài kho và `-p no:cacheprovider`; `ruff` chạy với `--exclude tests/architecture/.tmp`.

## 1. Mục tiêu

Cài đặt thật cho `Embedder`, `Reranker` qua OpenRouter, bộ đệm véc-tơ, và `HybridRetriever` (BM25 + véc-tơ → RRF → xếp hạng lại → ngưỡng → sắp theo tầng tin cậy), cùng `QueryBuilder` sinh truy vấn theo mẫu. Kho đoạn đọc từ `data/kb_curated/chunks.jsonl` (task T04a đang sinh; mỗi dòng là một `Chunk` dạng JSON).

## 2. Phạm vi file

```text
app/providers/openrouter_embed.py
app/providers/openrouter_rerank.py
app/providers/cached_embedder.py
app/providers/http.py               # hàm gọi HTTP dùng chung: thử lại, đổi khoá, ánh xạ lỗi
app/retrieval/__init__.py
app/retrieval/fusion.py             # RRF
app/retrieval/corpus.py             # nạp chunks.jsonl, dựng chỉ mục
app/retrieval/hybrid.py             # HybridRetriever
app/retrieval/query_builder.py
app/retrieval/setup.py              # build_retriever(container) – nơi duy nhất lắp các phần của task này
tests/providers/test_openrouter_embed.py  test_openrouter_rerank.py  test_cached_embedder.py
tests/retrieval/__init__.py  test_fusion.py  test_hybrid.py  test_query_builder.py  test_corpus.py
notebooks/03_test_embedding.ipynb  notebooks/04_test_retriever.ipynb
```

## 3. Nhà cung cấp OpenRouter

Đã thử tay ngày 16/11, hai lời gọi sau chạy được:

```text
POST https://openrouter.ai/api/v1/embeddings
  {"model": "nvidia/llama-nemotron-embed-vl-1b-v2:free", "input": ["...", "..."]}
  → {"data": [{"embedding": [2048 số], "index": 0}, …], "usage": {...}}      véc-tơ đã chuẩn hoá L2

POST https://openrouter.ai/api/v1/rerank
  {"model": "nvidia/llama-nemotron-rerank-vl-1b-v2:free", "query": "...", "documents": ["...", "..."]}
  → {"results": [{"index": 1, "relevance_score": 0.994, "document": {...}}, …]}   sắp giảm dần theo điểm
```

Tiêu đề `Authorization: Bearer <khoá>`. Thân trả về có thể có khoảng trắng hoặc dòng trống ở đầu: dùng `response.text.strip()` rồi mới đọc JSON.

- `app/providers/http.py`: `post_json(client: httpx.Client, url, payload, keys: list[str], max_attempts: int, timeout: float = 60) -> dict`. Mã 429 hoặc 5xx hoặc lỗi mạng → thử lại tối đa `max_attempts` lần, mỗi lần **xoay sang khoá kế tiếp** trong `keys`, chờ lũy tiến (0,5 s, 1 s, 2 s; hàm `sleep` tiêm được để test không chờ thật). Mã 401 / 403 → `ProviderError(retryable=False)` ngay. Hết lượt → `ProviderError(retryable=True)`. **Thông báo lỗi không bao giờ chứa khoá hay tiêu đề `Authorization`**; chỉ ghi mã trạng thái và tối đa 200 ký tự đầu của thân.
- `OpenRouterEmbedder(model, dimensions, batch_size, keys, client, max_attempts)`: `embed_documents` chia lô theo `batch_size`, giữ đúng thứ tự theo `index`; số véc-tơ trả về lệch số đầu vào hoặc số chiều lệch `dimensions` → `ProviderError(retryable=False)`. `embed_query` gọi một phần tử. Chuỗi rỗng không gửi đi: ném `ValueError`.
- `OpenRouterReranker(model, keys, client, max_attempts)`: `rerank(query, passages, top_n) -> list[tuple[int, float]]` giảm dần theo điểm, cắt `top_n`; `passages` rỗng trả `[]` không gọi mạng.
- Khoá lấy bằng `get_secret("OPENROUTER_API_KEY")` và, nếu có, `OPENROUTER_API_KEY_2` (thiếu khoá thứ hai thì bỏ qua, không lỗi). Việc lấy khoá chỉ diễn ra trong `setup.py`, các lớp nhận `keys` qua hàm khởi tạo.

## 4. Bộ đệm – `app/providers/cached_embedder.py`

`CachedEmbedder(inner: Embedder, cache_path: Path, model_id: str)`: bọc một `Embedder`. Lưu SQLite (thư viện chuẩn `sqlite3`), bảng `embeddings(key TEXT PRIMARY KEY, dims INTEGER, vec BLOB)`, `key = sha256(model_id + "\n" + loai + "\n" + văn bản)` với `loai` là `doc` hoặc `query`; véc-tơ lưu `float32` bằng `numpy.tobytes`. `embed_documents` chỉ gửi phần **chưa có** trong bộ đệm xuống `inner`, một lô, rồi trả đúng thứ tự ban đầu. Có `stats() -> dict` (`hits`, `misses`). Tự tạo thư mục cha. Đổi `model_id` thì không dùng lại véc-tơ cũ.

## 5. Truy xuất

### 5.1 `fusion.py`

`rrf(rankings: list[list[str]], k: int) -> list[tuple[str, float]]`: điểm của một mã = tổng `1 / (k + hạng)` (hạng bắt đầu từ 1) trên các danh sách có mã đó; trả giảm dần theo điểm, hoà thì theo thứ tự xuất hiện đầu tiên.

### 5.2 `corpus.py`

`load_corpus(path: Path) -> list[Chunk]` (tệp không tồn tại → `RetrievalError` nêu đường dẫn và nhắc chạy `python -m app.kb.build`). `index_corpus(chunks, embedder, vector_store, keyword_index) -> None`: nhúng `noi_dung_nhung` của mọi đoạn, `upsert` vào kho véc-tơ, `build` chỉ mục từ khoá.

### 5.3 `hybrid.py`

```python
class RetrievalOutcome(BaseModel):
    ket_qua: list[ScoredChunk]            # đã xếp hạng lại, đã lọc ngưỡng, đã sắp theo tầng
    che_do: Literal["lai", "tu_khoa"]     # "tu_khoa" khi nhúng hoặc xếp hạng lại lỗi
    canh_bao: list[str]

class HybridRetriever:
    def __init__(self, embedder, reranker, vector_store, keyword_index, rrf_k: int, rerank_min_score: float) -> None
    def retrieve(self, query: RetrievalQuery) -> list[ScoredChunk]        # giao diện Retriever
    def retrieve_detailed(self, query: RetrievalQuery) -> RetrievalOutcome
```

Luồng cho một `RetrievalQuery` (có nhiều cách diễn đạt trong `van_ban`):

1. Với **mỗi** cách diễn đạt: tìm từ khoá `k_query` và tìm véc-tơ `k_query`, cùng `bo_loc`. Mỗi lần tìm cho một danh sách mã.
2. Trộn tất cả danh sách bằng `rrf(…, rrf_k)`, giữ `k_query` đầu.
3. Xếp hạng lại bằng `reranker.rerank(van_ban[0], [noi_dung_nhung…], k_rerank)`.
4. Bỏ đoạn có điểm dưới `rerank_min_score`. Không còn đoạn nào → trả rỗng (nghĩa là "không tìm thấy nguồn"), **không** hạ ngưỡng.
5. Sắp ổn định theo `tang_tin_cay` tăng dần (tầng 1 trước), trong cùng tầng giữ thứ tự điểm. `nguon_diem="xep_hang_lai"`.
6. **Đường lui:** `ProviderError` ở bước nhúng → bỏ nhánh véc-tơ, chỉ dùng từ khoá. `ProviderError` ở bước xếp hạng lại → dùng thứ tự RRF, cắt `k_rerank`, bỏ qua ngưỡng. Cả hai trường hợp `che_do="tu_khoa"` và thêm câu vào `canh_bao`. Truy xuất không bao giờ ném `ProviderError` ra ngoài.

### 5.4 `query_builder.py`

```python
class QueryBuilder:
    def __init__(self, settings: RetrievalSettings) -> None
    def for_finding(self, hoat_chat_id: str, ten_inn: str, ten_viet: str, yeu_to: int, ma_luat: str | None) -> RetrievalQuery
    def baseline(self, hoat_chat_id: str, ten_inn: str, ten_viet: str) -> list[RetrievalQuery]
```

Bảng mẫu theo yếu tố, mỗi mẫu có `muc` cần lọc và hai câu (Việt, Anh) có chỗ điền tên thuốc:

| Yếu tố | `muc` | Mẫu tiếng Việt | Mẫu tiếng Anh |
| :-: | :--- | :--- | :--- |
| 1 | `chong_chi_dinh`, `canh_bao` | `{vi} dị ứng quá mẫn chống chỉ định phản ứng chéo` | `{en} hypersensitivity contraindication cross-reactivity allergy` |
| 3 | `chi_dinh`, `lieu` | `{vi} chỉ định liều dùng đường dùng` | `{en} indications dosage and administration` |
| 4 | `tuong_tac` | `{vi} tương tác thuốc` | `{en} drug interactions` |
| 5 | `canh_bao`, `tac_dung_phu` | `{vi} cảnh báo độc tính tác dụng không mong muốn` | `{en} warnings toxicity adverse reactions` |
| 6 | `lieu_than`, `lieu_gan`, `lieu`, `thai_ky_cho_bu`, `nhi_cao_tuoi` | `{vi} chỉnh liều suy thận độ thanh thải creatinin` | `{en} renal impairment dosage adjustment creatinine clearance` |

Yếu tố 2 và 7 không có mẫu → `for_finding` trả truy vấn với `muc = []` và câu chỉ gồm tên thuốc. Thứ tự `van_ban` theo `settings.query_languages`. `bo_loc.hoat_chat_ids = [hoat_chat_id]`, `bo_loc.nhom_nguon = "nhan_thuoc"`, `k_query` và `k_rerank` lấy từ `settings.nhan_thuoc`. `baseline` trả hai truy vấn (yếu tố 1 và 4) cho mọi hoạt chất, kể cả khi luật không báo gì.

### 5.5 `setup.py`

`build_retriever(container) -> HybridRetriever`: đọc `container.settings`; tạo `httpx.Client` dùng chung; `embedding.provider == "openrouter"` → `CachedEmbedder(OpenRouterEmbedder(…), cache_path, model_id=embedding.active)`, `"fake"` → `container.embedder`; `rerank.provider == "openrouter"` → `OpenRouterReranker`, `"noop"` → `container.reranker`; kho véc-tơ: **luôn dùng `InMemoryVectorStore`** ở task này, kể cả khi cấu hình ghi `pgvector` (ghi một dòng cảnh báo vào `canh_bao` của hàm trả về hoặc qua tham số `warnings: list[str]`); chỉ mục từ khoá `Bm25Index`; nạp `data/kb_curated/chunks.jsonl` và `index_corpus`. Không sửa `app/container.py`.

## 6. Sổ tay (tạo bằng `nbformat`, không có đầu ra, không in khoá)

- `03_test_embedding.ipynb`: nhúng 4 câu (2 cặp Việt – Anh cùng nghĩa), in số chiều, chuẩn của véc-tơ, ma trận cosine; chạy lần hai và in `stats()` của bộ đệm.
- `04_test_retriever.ipynb`: `build_retriever(build_container())`; một truy vấn `for_finding("meropenem", "meropenem", "meropenem", 6, None)`; in lần lượt 5 kết quả đầu của từ khoá, của véc-tơ, sau RRF, sau xếp hạng lại (mã, điểm, `duong_dan_muc`, 120 ký tự đầu).

## 7. Kiểm thử phải có (dùng `httpx.MockTransport`, không mạng thật)

- Nhúng: 5 văn bản với `batch_size=2` → 3 lời gọi, kết quả đúng thứ tự dù máy chủ trả `index` đảo; thân có dòng trống ở đầu vẫn đọc được; số chiều lệch → `ProviderError`.
- Thử lại: 429 rồi 200 → thành công, lời gọi thứ hai dùng **khoá thứ hai**; 401 → lỗi ngay không thử lại; 3 lần 500 → `ProviderError(retryable=True)`; chuỗi thông báo lỗi không chứa khoá.
- Xếp hạng lại: trả đúng `(chỉ số, điểm)` giảm dần, cắt `top_n`; danh sách rỗng không gọi mạng.
- Bộ đệm: lần hai không gọi `inner`; trộn văn bản cũ và mới chỉ gửi phần mới và trả đúng thứ tự; `query` và `doc` cùng văn bản là hai khoá khác nhau; đổi `model_id` → gọi lại; véc-tơ đọc lại bằng véc-tơ đã ghi (sai số `1e-6`).
- RRF: ví dụ tính tay 2 danh sách 3 phần tử; mã chỉ có ở một danh sách vẫn có điểm.
- Lai (dùng `HashEmbedder`, `InMemoryVectorStore`, `Bm25Index`, bộ xếp hạng lại giả điều khiển được điểm): bộ lọc hoạt chất được áp ở cả hai nhánh; đoạn dưới ngưỡng bị loại; mọi đoạn dưới ngưỡng → kết quả rỗng; hai đoạn tầng 3 và một đoạn tầng 1 → tầng 1 đứng đầu dù điểm thấp hơn; bộ nhúng ném `ProviderError` → vẫn có kết quả, `che_do == "tu_khoa"`; bộ xếp hạng lại ném `ProviderError` → vẫn có kết quả theo thứ tự RRF.
- `QueryBuilder`: yếu tố 6 cho meropenem có `muc` chứa `lieu_than`, hai câu Việt và Anh đều chứa tên thuốc, `k_query` và `k_rerank` đúng cấu hình; yếu tố 2 có `muc == []`; `baseline` trả 2 truy vấn.
- `load_corpus` với tệp không tồn tại → `RetrievalError`.

## 8. Nghiệm thu

```bash
uv run ruff check . --exclude tests/architecture/.tmp
uv run ruff format --check app/providers app/retrieval tests/providers tests/retrieval
uv run pytest -q tests/providers tests/retrieval tests/architecture -p no:cacheprovider --basetemp <thư mục tạm ngoài kho>
```

Chỉ định dạng file của task này. Test kiến trúc phải tiếp tục qua (`httpx` chỉ được import trong `app/providers/`).

## 9. Cấm làm

- Không gọi mạng thật trong test. Không đọc `.env`. Không ghi khoá ở bất kỳ đâu, kể cả thông báo lỗi và sổ tay.
- Không gửi văn bản ca bệnh qua bước nhúng: bộ nhúng chỉ nhận đoạn nguồn và truy vấn do `QueryBuilder` sinh.
- Không thêm thư viện. Không viết pgvector, không viết bộ cắt đoạn, không viết LLM.
- Không commit, không push.
