# T11 – Khung kiến trúc: cấu hình, giao diện lõi, nơi lắp ráp, nhà cung cấp giả

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort high) · **Ngày:** 16/11/2026
**Đọc trước:** `AGENTS.md` (bắt buộc); `plan/plan-1.1-kien-truc-chi-tiet.md` mục 2, 3, 4, 8 (bắt buộc); **chỉ đọc** `app/domain/`, `app/calc/`, `app/rules/`, `app/pipeline.py`.
**Đang có task khác chạy song song (T13, giao diện).** Bạn **không** tạo hay sửa bất cứ gì trong `app/ui/`, `tests/ui/`, `app/feedback.py`, `data/`, `docs/`, `plan/`.

## 1. Mục tiêu

Dựng bộ khung để các task sau (kho tri thức, truy xuất, LLM, kiểm chứng, đồ thị) cắm vào mà không giẫm nhau. Task này **không đổi hành vi nào đang có**: 344 test hiện tại phải tiếp tục qua, `app/pipeline.py` và giao diện chạy như cũ. Không gọi mạng, không cần khoá API.

## 2. Phạm vi file được tạo hoặc sửa

```text
config/settings.yaml
config/settings.test.yaml
config/prompts/.gitkeep
app/config/__init__.py
app/config/settings.py
app/core/__init__.py
app/core/errors.py
app/core/types.py
app/core/interfaces.py
app/providers/__init__.py
app/providers/fakes.py
app/providers/memory_store.py
app/providers/bm25_index.py
app/rules/registry.py              (file MỚI; không sửa file luật đang có)
app/storage/__init__.py
app/storage/case_repo.py
app/container.py
notebooks/README.md
notebooks/00_cau_hinh.ipynb
tests/config/…  tests/core/…  tests/providers/…  tests/storage/…  tests/architecture/…
tests/rules/test_registry.py
tests/test_container.py
pyproject.toml                     (chỉ thêm phụ thuộc ở mục 3)
.env.example                       (file MỚI, chỉ tên biến, không có giá trị thật)
```

**Không đọc, không in, không sửa file `.env`.**

## 3. Phụ thuộc được thêm

`dependencies`: `pyyaml`, `python-dotenv`, `numpy`.
Nhóm `dev`: `ipykernel`, `nbformat`, `nbstripout`.
Không thêm gì khác (chưa thêm `langgraph`, `psycopg`, `httpx` ở task này).

## 4. Cấu hình

### 4.1 `config/settings.yaml`

Chép **đúng nguyên văn** khối YAML ở mục 8 của plan 1.1 (bản hiện tại trong file: `llm.provider: "deepseek"`, `llm.model: "deepseek-flash"`, `vector_store.provider: "pgvector"`, có khối `database`).

### 4.2 `config/settings.test.yaml`

Chỉ chứa phần ghi đè: `app.profile: "test"`, `llm.provider: "fake"`, `embedding.provider: "fake"`, `rerank.provider: "noop"`, `vector_store.provider: "memory"`.

### 4.3 `app/config/settings.py`

- Mô hình pydantic lồng nhau, mỗi khối YAML một lớp (`ChunkingSettings`, `RetrievalSettings` với `CollectionRetrieval`, `EvidenceSettings`, `CaseContextSettings`, `GenerationSettings`, `AgentSettings`, `LLMSettings`, `EmbeddingSettings`, `RerankSettings`, `DatabaseSettings`, `VectorStoreSettings`, `PromptSettings`, `AppSettings`, gốc là `Settings`). Mọi lớp `model_config = ConfigDict(extra="forbid", frozen=True)`: khoá lạ hoặc sai kiểu thì ném `ConfigError` nêu đường dẫn khoá.
- Ràng buộc: `min_chars < target_chars <= max_chars`; `k_rerank <= k_query`; `0 <= temperature <= 2`; các số đếm > 0.
- `load_settings(profile: str | None = None, config_dir: Path | None = None) -> Settings`: đọc `settings.yaml`; nếu có `settings.<profile>.yaml` thì **trộn sâu** đè lên. `profile` lấy từ tham số, không có thì từ biến môi trường `CDSS_PROFILE`, không có nữa thì `"dev"`. `config_dir` mặc định là thư mục `config/` ở gốc kho (tính từ vị trí file, không phụ thuộc thư mục đang đứng).
- `get_secret(name: str) -> str`: nạp `.env` bằng `python-dotenv` (không ghi đè biến đã có), trả giá trị biến môi trường; thiếu thì ném `ConfigError` **chỉ nêu tên biến**. Không hàm nào được in hay ghi log giá trị bí mật. `Settings` không chứa bí mật.

### 4.4 `.env.example`

```text
OPENROUTER_API_KEY=
OPENROUTER_API_KEY_2=
DEEPSEEK_API_KEY=
DATABASE_URL=
```

## 5. Lõi

### 5.1 `app/core/errors.py`

`CdssError(Exception)` gốc; `ConfigError`, `ProviderError` (thuộc tính `retryable: bool`), `RetrievalError`, `VerificationError` kế thừa nó. Không định nghĩa lại `DeidError` (đang ở `app/deid`).

### 5.2 `app/core/types.py` (pydantic, `frozen=True`)

```python
class Chunk:            doan_trich_id: str; tai_lieu_id: str; muc_cha_id: str | None; nhom_nguon: str
                        nguon: str; tang_tin_cay: int (1–4); hoat_chat_ids: list[str]; muc: str
                        duong_dan_muc: str; loai_noi_dung: Literal["van_ban","bang","danh_sach","dong_bang"]
                        ngon_ngu: Literal["vi","en"]; phien_ban_nguon: str | None; url_goc: str | None
                        noi_dung_goc: str; noi_dung_nhung: str
class SearchFilter:     nhom_nguon: str | None; hoat_chat_ids: list[str] = []; muc: list[str] = []
class RetrievalQuery:   van_ban: list[str]  # các cách diễn đạt, ví dụ bản Việt và bản Anh
                        bo_loc: SearchFilter; k_query: int; k_rerank: int
class ScoredChunk:      chunk: Chunk; diem: float; nguon_diem: Literal["tu_khoa","vec_to","rrf","xep_hang_lai"]
class ChatMessage:      role: Literal["system","user","assistant"]; content: str
class ToolResult:       ok: bool; du_lieu: dict | list | None; loi: str | None
```

Bộ lọc khớp khi: `nhom_nguon` trùng (nếu có); `hoat_chat_ids` của đoạn **giao** với danh sách lọc (danh sách lọc rỗng = không lọc); `muc` của đoạn nằm trong danh sách lọc (rỗng = không lọc). Viết thành một hàm thuần `matches(chunk, bo_loc) -> bool` ở file này, dùng chung cho mọi kho.

### 5.3 `app/core/interfaces.py`

`typing.Protocol` (có `@runtime_checkable`) cho đúng 12 giao diện ở bảng mục 3.1 của plan 1.1, chữ ký như sau:

```python
class LLMClient(Protocol):
    def complete_json(self, messages: list[ChatMessage], schema: dict) -> dict: ...
class Embedder(Protocol):
    dimensions: int
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
class Reranker(Protocol):
    def rerank(self, query: str, passages: list[str], top_n: int) -> list[tuple[int, float]]: ...  # (chỉ số, điểm) giảm dần
class VectorStore(Protocol):
    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None: ...
    def search(self, vector: list[float], k: int, bo_loc: SearchFilter) -> list[ScoredChunk]: ...
    def count(self) -> int: ...
class KeywordIndex(Protocol):
    def build(self, chunks: list[Chunk]) -> None: ...
    def search(self, query: str, k: int, bo_loc: SearchFilter) -> list[ScoredChunk]: ...
class Chunker(Protocol):
    def split(self, document: dict) -> list[Chunk]: ...
class Retriever(Protocol):
    def retrieve(self, query: RetrievalQuery) -> list[ScoredChunk]: ...
class Rule(Protocol):
    ma_nhom: str
    yeu_to: int
    def check(self, ca: CaBenh, ctx: RuleContext) -> list[PhatHien]: ...
class Tool(Protocol):
    name: str
    def run(self, args: dict, ca: CaBenh) -> ToolResult: ...
class Verifier(Protocol):
    def verify(self, nhan_dinh: dict, goi_can_cu: list[Chunk]) -> list[str]: ...  # danh sách lỗi, rỗng = đạt
class CaseRepository(Protocol):
    def list_ids(self) -> list[str]: ...
    def get(self, ca_id: str) -> CaBenh: ...
class AuditLog(Protocol):
    def record(self, event: dict) -> None: ...
```

`RuleContext` (dataclass đóng băng, ở `app/rules/registry.py`): `renal_rules: RenalRuleBook`.

## 6. Cài đặt không cần mạng

### 6.1 `app/providers/fakes.py`

- `FakeLLM(responses: list[dict])`: trả lần lượt; hết thì ném `ProviderError(retryable=False)`; ghi lại `calls` để test soi.
- `HashEmbedder(dimensions: int = 64)`: tất định, không mạng. Tách từ chữ thường theo `\w+`, mỗi từ băm (`hashlib.sha256`) về một chỉ số, cộng 1 vào chiều đó, chuẩn hoá L2. Chuỗi không có từ nào → véc-tơ 0. Hai văn bản trùng nhiều từ phải có cosine cao hơn hai văn bản không trùng từ nào (có test).
- `NoopReranker`: giữ nguyên thứ tự, điểm giảm dần từ 1.0, cắt `top_n`.

### 6.2 `app/providers/memory_store.py`

`InMemoryVectorStore`: giữ danh sách đoạn và ma trận `numpy`; `upsert` ghi đè theo `doan_trich_id`; `search` lọc bằng `matches` **trước**, rồi xếp theo cosine giảm dần, trả `k` đầu với `nguon_diem="vec_to"`. Số đoạn và số véc-tơ lệch nhau, hoặc số chiều lệch → `RetrievalError`.

### 6.3 `app/providers/bm25_index.py`

`Bm25Index`: tự cài BM25 Okapi (`k1=1.5`, `b=0.75`), không thêm thư viện. Lập chỉ mục trên `noi_dung_nhung`. Tách từ: chữ thường, theo `\w+` (Unicode), và với mỗi từ có dấu tiếng Việt thì thêm cả bản bỏ dấu (dùng `unicodedata`, đổi `đ` → `d`) để truy vấn không dấu vẫn trúng. `search` lọc bằng `matches` trước; đoạn điểm 0 không trả về; `nguon_diem="tu_khoa"`.

### 6.4 `app/rules/registry.py`

Lớp bọc mỏng theo giao diện `Rule` cho 5 module luật đang có (`allergy`, `duplicate`, `antibiotic`, `renal_dose`, `schedule`), gọi lại đúng hàm `check` hiện tại, không chép logic. `default_rules() -> list[Rule]` trả theo đúng thứ tự `app/rules/engine.py` đang gọi. `run_registered(ca, ctx, rules) -> list[PhatHien]` chạy các luật rồi sắp xếp bằng **chính hàm sắp xếp của `engine.py`** (import, không viết lại). Test bắt buộc: với cả 6 ca demo, `run_registered(...)` cho kết quả **bằng đúng** `run_rules(ca, renal_rules)`.

Nếu chữ ký `check` của module nào khác với mô tả, đọc code và bọc cho đúng; không sửa module luật.

### 6.5 `app/storage/case_repo.py`

`JsonCaseRepository(folder: Path)`: `list_ids()` trả `ca_id` đã sắp xếp; `get(ca_id)` nạp bằng `app.domain.loader.load_case`; không có thì ném `KeyError`. File JSON hỏng không làm `list_ids` sập: bỏ qua và ghi vào thuộc tính `errors: list[tuple[str, str]]`.

## 7. Nơi lắp ráp – `app/container.py`

```python
class Container:
    def __init__(self, settings: Settings) -> None
    settings: Settings
    llm / embedder / reranker / vector_store / keyword_index / case_repo / renal_rules / rules   # cached_property
def build_container(profile: str | None = None) -> Container
```

Chọn cài đặt theo `settings.*.provider` qua **bảng đăng ký** (`dict[str, Callable]`), không dùng chuỗi `if / elif`. Ở task này chỉ có: `llm: fake`, `embedding: fake`, `rerank: noop`, `vector_store: memory`. Gặp tên chưa có cài đặt (`deepseek`, `openrouter`, `pgvector`) → `ConfigError` với câu `"Chưa có cài đặt cho <khối>.provider=<tên>"`, và **chỉ ném khi thuộc tính đó được truy cập** (lười), để `build_container()` với hồ sơ `dev` vẫn dùng được `case_repo` và `rules`. Có hàm `register_provider(kind, name, factory)` để task sau thêm cài đặt mà không sửa file này.

## 8. Test kiến trúc – `tests/architecture/test_import_boundaries.py`

Dùng `ast` đọc mọi file `.py` trong `app/domain`, `app/core`, `app/calc`, `app/rules`, `app/deid`: không file nào được import các gói `streamlit`, `langgraph`, `langchain`, `psycopg`, `sqlalchemy`, `httpx`, `requests`, `openai`. Thêm: không file nào ngoài `app/config/` được gọi `os.environ` / `os.getenv` / `load_dotenv`, **trừ** `app/ui/streamlit_app.py` (đang đọc `CDSS_CASE_DIR`; không sửa file đó, ghi ngoại lệ có chú thích trong test).

## 9. Sổ tay

- `notebooks/README.md`: chép bảng 10 sổ tay và 4 quy tắc ở mục 9 của plan 1.1; cách chạy: `uv run jupyter lab` hoặc mở bằng VS Code với nhân của `.venv`.
- `notebooks/00_cau_hinh.ipynb`: tạo bằng `nbformat` (JSON hợp lệ, không có đầu ra). Các ô: (1) tiêu đề markdown; (2) thêm gốc kho vào `sys.path`; (3) `load_settings()` và in cấu hình hiệu lực bằng `model_dump()`; (4) với từng tên trong `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`, `DATABASE_URL` chỉ in **có / thiếu**, không in giá trị; (5) `build_container("test")`, in số ca và số luật. Test: mở sổ tay bằng `nbformat`, `nbformat.validate` đạt, không ô nào có đầu ra, không ô nào chứa chuỗi `sk-`.

## 10. Kiểm thử phải có (ngoài các test đã nêu)

- `load_settings()` đọc được file thật; `load_settings("test").llm.provider == "fake"` và các khối không ghi đè giữ nguyên giá trị gốc.
- YAML có khoá lạ → `ConfigError`; `k_rerank > k_query` → `ConfigError`; `min_chars >= target_chars` → `ConfigError` (dùng `tmp_path`).
- `get_secret("TEN_KHONG_CO")` → `ConfigError`, thông báo có tên biến.
- `matches`: đủ 3 chiều lọc và trường hợp bộ lọc rỗng.
- `InMemoryVectorStore` + `HashEmbedder`: nạp 4 đoạn (2 của meropenem, 2 của amlodipin), tìm "meropenem suy thận" có lọc `hoat_chat_ids=["meropenem"]` chỉ trả đoạn meropenem; `upsert` lại cùng mã không làm tăng `count()`.
- `Bm25Index`: truy vấn `"chinh lieu suy than"` (không dấu) trúng đoạn có `"chỉnh liều khi suy thận"`; truy vấn không trùng từ nào trả rỗng.
- `build_container("test")`: `isinstance` đúng với từng `Protocol`; `len(container.rules) == 5`; `container.case_repo.list_ids()` có 6 ca.
- `build_container("dev").llm` → `ConfigError`; `build_container("dev").case_repo` dùng được.

## 11. Nghiệm thu

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Cả ba sạch; toàn bộ 344 test cũ vẫn qua.

## 12. Cấm làm

- Không gọi mạng ngoài việc `uv sync` cài 6 gói ở mục 3. Không gọi API nào.
- Không đọc, in, sửa `.env`. Không ghi giá trị khoá ở bất kỳ đâu.
- Không sửa `app/pipeline.py`, `app/rules/*.py` đang có, `app/calc`, `app/domain`, `app/deid`, `app/ui`, `data/`.
- Không viết trước các lớp của task sau (bộ cắt đoạn, truy xuất lai, máy khách DeepSeek / OpenRouter, pgvector, đồ thị).
- Không commit, không push.
