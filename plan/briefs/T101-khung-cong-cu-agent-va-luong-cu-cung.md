# T101 – Lớp công cụ của agent, chính sách quyền, ToolGateway và tool `luong_cu_cung`

Giao: agy `gemini-4-hydrogen-high` (trượt review thì giao lại `gemini-4-hydrogen-xhigh`). Ngày 21/11/2026.

Đọc trước: `AGENTS.md`, `plan/plan-1.9-agentic-rag-cong-cu-va-phan-quyen.md` mục 5.1, 6.1, 6.4, 6.6, 7, 8.

**Không được gọi công cụ shell.** Chỉ đọc và ghi tệp. Người review sẽ tự chạy `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`.

## 1. Bối cảnh

Ô hỏi đáp hiện chạy luồng cứng `CaseAsker` (`app/orchestration/ask.py`). Plan 1.9 chuyển sang agent theo đồ thị LangGraph. Brief này **chỉ làm lớp công cụ**, chưa làm đồ thị (T102 làm sau):
- lớp nền cho mọi tool;
- danh mục tool;
- chính sách quyền đọc từ YAML;
- `ToolGateway`, chốt an toàn duy nhất giữa LLM và tool;
- một tool duy nhất `luong_cu_cung`, bọc nguyên vẹn `CaseAsker` làm tool chuyển tiếp và đường lui;
- marker pytest để skip test của luồng cũ khi tool bị tắt.

**Hành vi hiện tại của ứng dụng không được đổi.** Không tệp nào trong `app/api/`, `app/orchestration/`, `web/` bị sửa.

## 2. Phạm vi tệp

**Được tạo:**
- `app/agent/__init__.py`
- `app/agent/tools/__init__.py`
- `app/agent/tools/base.py`
- `app/agent/tools/registry.py`
- `app/agent/tools/policy.py`
- `app/agent/tools/gateway.py`
- `app/agent/tools/luong_cu_cung.py`
- `config/tool_policy.yaml`
- `tests/agent/__init__.py`
- `tests/agent/test_registry.py`
- `tests/agent/test_policy.py`
- `tests/agent/test_gateway.py`
- `tests/agent/test_luong_cu_cung.py`

**Được sửa (chỉ đúng phần nêu):**
- `app/config/settings.py`: thêm `AskSettings` và trường `ask` (mục 3.6).
- `config/settings.yaml`: thêm khối `ask` (mục 3.6).
- `pyproject.toml`: thêm một marker vào `[tool.pytest.ini_options].markers`.
- `tests/conftest.py`: thêm việc skip theo marker `luong_cu_cung` (mục 3.7). Giữ nguyên logic `can_du_lieu` hiện có.
- Thêm marker `luong_cu_cung` vào các test dựng `CaseAsker` trực tiếp (mục 3.7). **Chỉ thêm marker, không đổi nội dung test.**

**Cấm:**
- sửa `app/orchestration/ask.py`, `app/api/*`, `app/container.py`, `web/*`, prompt trong `config/prompts/`;
- cài hay thêm thư viện;
- ghi nội dung câu hỏi, câu trả lời, dữ liệu ca hay tham số tool vào log.

## 3. Yêu cầu

Tên lớp, hàm bằng tiếng Anh hoặc tiếng Việt không dấu theo mẫu dưới. Docstring tiếng Việt. Kiểu đầy đủ (`from __future__ import annotations`).

### 3.1. `app/agent/tools/base.py`

```python
CheDo = Literal["ca", "chung"]

class CanCu(BaseModel):            # frozen, extra="forbid"
    ma: str                         # "doan:<doan_trich_id>" | "bang:<bang>:<khoa>" | "tinh:<cong_thuc>" | "ca:<R..>"
    loai: Literal["doan", "bang", "tinh", "ca"]
    nhan: str                       # nhãn công khai, ví dụ "Nhãn FDA"
    doan: Chunk | None = None       # có khi loai == "doan"

class KetQuaCongCu(BaseModel):     # extra="forbid"
    trang_thai: Literal["ok", "khong_co", "loi", "tu_choi"]
    noi_dung: str = ""              # văn bản đưa cho LLM (Gateway sẽ che PII, bọc dấu, cắt cỡ)
    can_cu: list[CanCu] = []
    chi_tiet_tien_trinh: str | None = None   # chỉ số đếm, ví dụ "5 đoạn nguồn"; không nội dung
    ma_loi: str | None = None       # mã máy đọc: khong_co_cong_cu, khong_co_quyen, het_ngan_sach,
                                    # het_gio, sai_tham_so, tham_so_co_dinh_danh, nghi_chen_lenh, loi_cong_cu

@dataclass(frozen=True)
class ToolContext:
    vai_tro: str                    # "duoc_si_ls" | "admin" (lấy từ Principal ở T102)
    che_do: CheDo
    han_chot: float                 # time.monotonic() tuyệt đối
    cau_hoi_goc: str                # câu hỏi gốc CHƯA che; không bao giờ đưa cho LLM
    lich_su_goc: tuple[tuple[str, str], ...] = ()
    ca: CaBenh | None = None
    ket_qua_luat: KetQuaThamDinh | None = None
    ai_result: AiRunResult | None = None
    nhan_dinh_id: str | None = None
    cac_ca: tuple[CaBenh, ...] = ()                 # chế độ chung
    cac_ket_qua: Mapping[str, KetQuaThamDinh] = field(default_factory=dict)
    deid_session: DeidSession | None = None

class Tool(ABC):
    ten: ClassVar[str]              # snake_case, khớp tên trong config/tool_policy.yaml
    ten_hien_thi: ClassVar[str]     # tên bước hiện trên giao diện tiến trình
    mo_ta: ClassVar[str]            # mô tả cho LLM
    LuocDoThamSo: ClassVar[type[BaseModel]]  # BẮT BUỘC model_config extra="forbid"
    che_do_cho_phep: ClassVar[frozenset[str]] = frozenset({"ca", "chung"})
    goi_ra_ngoai: ClassVar[bool] = False
    thoi_gian_toi_da: ClassVar[float] = 20.0
    so_can_cu_toi_da: ClassVar[int] = 20

    @abstractmethod
    def chay(self, tham_so: BaseModel, ctx: ToolContext) -> KetQuaCongCu: ...
```

Không có tool nào nhận `ca_id` từ tham số. Phạm vi ca chỉ đến từ `ToolContext`.

### 3.2. `app/agent/tools/registry.py`

`DanhMucCongCu`:
- `dang_ky(tool: Tool) -> None`. Báo `ValueError` khi:
  - trùng tên;
  - `LuocDoThamSo` không có `extra="forbid"`;
  - lược đồ tham số có trường tên `ca_id`.
- `lay(ten) -> Tool | None`.
- `ten_da_dang_ky() -> list[str]`, giữ thứ tự đăng ký.
- `mo_ta_cho_llm(cac_ten: Sequence[str]) -> list[dict]`. Mỗi phần tử `{"ten", "mo_ta", "tham_so": <JSON schema của LuocDoThamSo>}`, chỉ cho các tên được truyền vào và đã đăng ký.

### 3.3. `config/tool_policy.yaml` và `app/agent/tools/policy.py`

Nội dung YAML ban đầu:

```yaml
# Chính sách công cụ của agent hỏi đáp (plan 1.9 mục 7). Mặc định từ chối.
mac_dinh: tu_choi
cong_cu:
  luong_cu_cung:
    bat: true          # Luồng cũ cứng (RAG cố định). Tắt: luồng cũ tắt hẳn, test của nó bị skip.
vai_tro:
  duoc_si_ls:
    cho_phep: [luong_cu_cung]
  admin:
    cho_phep: [luong_cu_cung]
che_do:
  chung:
    cam: []
```

`ChinhSachCongCu`:
- `tu_tep(path: Path | None = None)`: mặc định đọc `config/tool_policy.yaml` tính từ gốc kho. YAML sai cấu trúc hoặc khoá lạ báo `ConfigError` (`app/core/errors.py`). Dùng pydantic `extra="forbid"` cho lược đồ.
- `cong_cu_bat(ten) -> bool`:
  - tool không khai báo trong `cong_cu` thì coi là bật;
  - riêng `luong_cu_cung`, biến môi trường `CDSS_LUONG_CU_CUNG` có giá trị `0`, `false`, `off`, `khong` (không phân biệt hoa thường) thì tắt, ưu tiên hơn YAML.
- `cho_phep(vai_tro, che_do, ten) -> bool`: đúng khi tool bật, vai trò có tên trong `cho_phep`, và tên không nằm trong `che_do.<che_do>.cam`. Vai trò lạ thì `False` (mặc định từ chối).
- `cac_cong_cu_duoc_phep(vai_tro, che_do, danh_muc) -> list[str]`: các tên vừa đã đăng ký vừa được phép, theo thứ tự đăng ký.

Hàm cấp module `luong_cu_cung_dang_bat(path: Path | None = None) -> bool`. Đọc chính sách và trả `cong_cu_bat("luong_cu_cung")`. Tệp thiếu hoặc lỗi thì trả `True`, để không âm thầm tắt luồng đang chạy production. conftest dùng hàm này.

### 3.4. `app/agent/tools/gateway.py`

`ToolGateway(danh_muc, chinh_sach, so_lan_goi_toi_da: int)`. Một thực thể cho **một lượt hỏi**; đếm số lần gọi trong lượt.

`goi(ten: str, tham_so_tho: dict, ctx: ToolContext) -> KetQuaCongCu` chạy đúng thứ tự dưới. Bước nào từ chối thì trả `KetQuaCongCu(trang_thai="tu_choi", ma_loi=..., noi_dung=<câu tiếng Việt ngắn cố định>)` và **không gọi tool**.

1. Tên không có trong danh mục → `khong_co_cong_cu`.
2. `chinh_sach.cho_phep(ctx.vai_tro, ctx.che_do, ten)` sai, hoặc `ctx.che_do` không thuộc `che_do_cho_phep` của tool → `khong_co_quyen`.
3. Đã gọi đủ `so_lan_goi_toi_da` lần → `het_ngan_sach`. `time.monotonic() >= ctx.han_chot` → `het_gio`.
4. `LuocDoThamSo.model_validate(tham_so_tho)` lỗi → `sai_tham_so`. Câu báo chỉ nêu tên trường lỗi, **không lặp lại giá trị đầu vào**.
5. Quét PII tham số: với mọi giá trị chuỗi (kể cả lồng trong list/dict), dùng `ctx.deid_session` hoặc một `DeidSession()` rỗng nếu `None`. Giá trị chứa định danh thì từ chối với `tham_so_co_dinh_danh`. Cách nhận biết:
   - `mask_known(s) != s`;
   - hoặc chuỗi **không** chứa mã tạm (regex `TOKEN_PATTERN` trong `app/deid/scrubber.py`) và `scrub(s) != s`.

   Mã tạm như `[TEN_1]` là hợp lệ.
6. Chạy tool:
   - giới hạn thời gian `min(tool.thoi_gian_toi_da, ctx.han_chot - now)`, chạy trong luồng phụ như `CaseAsker._run_with_deadline`;
   - quá giờ thì trả `loi` với `het_gio`;
   - tool ném ngoại lệ thì trả `loi` với `loi_cong_cu`. `noi_dung` là câu cố định, **không chứa chữ của ngoại lệ**.
7. Hậu xử lý `noi_dung` của kết quả:
   1. che PII: chuỗi có mã tạm thì `mask_known`, không có thì `scrub`. `DeidError` thì thay bằng `"[không đưa được kết quả vào vì lỗi che định danh]"` và `trang_thai="loi"`;
   2. loại chuỗi phân tách khối: các chuỗi trong `_BLOCK_MARKERS` của `ask.py` cùng `<<<KET_QUA_CONG_CU` và `KET_QUA_CONG_CU>>>`. Viết lại hằng trong gateway, không import hàm riêng tư;
   3. quét chèn lệnh bằng `_has_injection_directive` (được import từ `app.orchestration.ask`, không sửa tệp đó). Trúng thì `noi_dung` thay bằng câu cố định "Kết quả công cụ có câu giống chỉ thị nên bị loại.", `trang_thai="loi"`, `ma_loi="nghi_chen_lenh"`, `can_cu=[]`;
   4. cắt `noi_dung` tối đa 8000 ký tự; `can_cu` tối đa `tool.so_can_cu_toi_da`;
   5. bọc `noi_dung` thành `<<<KET_QUA_CONG_CU ten=<ten>>>>\n...\nKET_QUA_CONG_CU>>>`.
8. Tiến trình qua `ghi_buoc` (`app/core/progress.py`):
   - mã bước `cong_cu_<n>` (`n` là số thứ tự lần gọi trong lượt, từ 1), `ten=tool.ten_hien_thi`;
   - `bat_dau` trước khi chạy;
   - `xong` với `chi_tiet=kết quả.chi_tiet_tien_trinh` hoặc `"Xong"`;
   - `loi` khi lỗi, với `ly_do` cố định theo `ma_loi`. Không bao giờ đưa chữ của ngoại lệ hay tham số vào bước.
   - Từ chối ở bước 1–5 cũng ghi một bước `loi` với tên `"Gọi công cụ bị từ chối"`.
9. Nhật ký kiểm toán: logger `app.agent.audit`, mức INFO, một dòng mỗi lần gọi, gồm:
   - tên tool, vai trò, chế độ;
   - `ca` = 12 ký tự đầu của sha256 `ca_id` (hoặc `-`);
   - kết quả (`cho_phep` / `tu_choi:<ma_loi>` / `loi:<ma_loi>`), số căn cứ, thời gian ms.

   **Không ghi** câu hỏi, tham số hay nội dung.

### 3.5. `app/agent/tools/luong_cu_cung.py`

Docstring module **phải có ghi chú** (giữ nguyên ý):

> Luồng cũ cứng (RAG cố định) bọc thành công cụ. Đây là luồng hỏi đáp trước plan 1.9, giữ lại làm công cụ chuyển tiếp và đường lui (plan 1.9 mục 6.6). Không thêm tính năng mới vào đây. Sẽ thôi gọi khi các công cụ chuyên biệt đạt đánh giá; khi đó tắt bằng `cong_cu.luong_cu_cung.bat: false` trong `config/tool_policy.yaml`.

`class LuongCuCung(Tool)`:
- `ten = "luong_cu_cung"`, `ten_hien_thi = "Luồng cũ cứng (RAG cố định)"`.
- `mo_ta`: nói cho LLM biết tool chạy toàn bộ luồng hỏi đáp cố định (truy xuất nhãn thuốc theo hoạt chất của ca, một lần mô hình, kiểm chứng) và trả câu trả lời đã kiểm chứng kèm đoạn nguồn. Không cần tham số.
- `LuocDoThamSo`: model rỗng, `extra="forbid"`.
- `thoi_gian_toi_da = 45.0`, `so_can_cu_toi_da = 8`.
- `__init__(self, asker)`: `asker` có `ask(...)` và `ask_global(...)` cùng chữ ký `CaseAsker`.
- `chay_truc_tiep(ctx) -> AskResult`:
  - chế độ `ca`: `asker.ask(ctx.ca, ctx.cau_hoi_goc, list(ctx.lich_su_goc), ket_qua=ctx.ket_qua_luat, ai_result=ctx.ai_result, nhan_dinh_id=ctx.nhan_dinh_id)`;
  - chế độ `chung`: `asker.ask_global(list(ctx.cac_ca), dict(ctx.cac_ket_qua), ctx.cau_hoi_goc, list(ctx.lich_su_goc))`.
  - T102 dùng hàm này cho nút đường lui.
- `chay(tham_so, ctx) -> KetQuaCongCu`: gọi `chay_truc_tiep` rồi đổi kết quả:
  - `trang_thai`: `ok` → `ok`; `khong_co_nguon`, `ngoai_pham_vi` → `khong_co`; còn lại → `loi`.
  - `noi_dung`: câu trả lời, rồi danh sách trích dẫn dạng `[so] nhan: trich_nguyen_van`. Giá trị thật vẫn ở đây; Gateway sẽ che.
  - `can_cu`: mỗi `Chunk` trong `AskResult.doan` thành `CanCu(ma=f"doan:{id}", loai="doan", nhan=<nhãn nguồn>, doan=chunk)`.
  - `chi_tiet_tien_trinh = f"{len(doan)} đoạn nguồn"`.

### 3.6. Cấu hình

`app/config/settings.py`:

```python
class AskSettings(BaseModel):
    """Chọn đường chạy hỏi đáp: luồng cứng cũ hoặc agent theo đồ thị (plan 1.9 mục 6.6)."""
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    engine: Literal["co_dinh", "agentic"] = "co_dinh"
    tool_policy: str = "config/tool_policy.yaml"
```

Thêm vào `Settings`: `ask: AskSettings = AskSettings()`.

`config/settings.yaml` thêm cuối tệp:

```yaml
ask:
  engine: "co_dinh"                 # co_dinh | agentic (plan 1.9 mục 6.6)
  tool_policy: "config/tool_policy.yaml"
```

### 3.7. Marker test

- `pyproject.toml`, thêm vào `markers`: `"luong_cu_cung: test của luồng hỏi đáp cũ cứng; tự bỏ qua khi tool luong_cu_cung tắt"`.
- `tests/conftest.py`: trong `pytest_collection_modifyitems`, nếu `luong_cu_cung_dang_bat()` là `False` thì mọi item mang marker `luong_cu_cung` được thêm `pytest.mark.skip(reason="luồng cũ cứng đang tắt (config/tool_policy.yaml hoặc CDSS_LUONG_CU_CUNG=0)")`.
- Thêm `pytestmark = pytest.mark.luong_cu_cung` ở đầu module (thêm `import pytest` nếu chưa có) cho:
  - `tests/orchestration/test_ask.py`
  - `tests/orchestration/test_ask_deid.py`
  - `tests/orchestration/test_ask_global_none_fields.py`
  - `tests/orchestration/test_prompt_single_pass.py`
  - `tests/agent/test_luong_cu_cung.py`
- Gắn `@pytest.mark.luong_cu_cung` **cho từng hàm** (không cả module) dựng `CaseAsker` trong:
  - `tests/orchestration/test_progress.py` (các hàm dùng `asker_ok`, `asker_no_ret`, `asker_retry`, `asker_err`, `asker_global`);
  - `tests/db/test_bang_luat.py` (hàm quanh dòng 503).

### 3.8. Test mới (`tests/agent/`)

Dùng ca thật `data/mock/demo/DEMO-02.json` (`app.domain.loader.load_case`) và `open_deid_session` (`app/llm/case_context.py`) khi cần định danh. Dùng tool giả định nghĩa trong test. Tiến trình kiểm bằng `TienTrinh` + `tien_trinh_hien_tai` như `tests/orchestration/test_progress.py`.

`test_registry.py`:
- đăng ký trùng tên báo lỗi;
- lược đồ thiếu `extra="forbid"` báo lỗi;
- lược đồ có `ca_id` báo lỗi;
- `mo_ta_cho_llm` chỉ trả tên được hỏi và đã đăng ký.

`test_policy.py`:
- tệp thật `config/tool_policy.yaml` nạp được, `luong_cu_cung` bật, `duoc_si_ls` được gọi;
- vai trò lạ bị từ chối;
- tool trong `che_do.chung.cam` bị từ chối ở chế độ chung, vẫn được ở chế độ ca;
- khoá lạ trong YAML báo `ConfigError`;
- `CDSS_LUONG_CU_CUNG=0` (dùng `monkeypatch.setenv`) làm `luong_cu_cung_dang_bat()` trả `False`;
- tệp không tồn tại thì trả `True`.

`test_gateway.py`:
- tên lạ → `khong_co_cong_cu`, tool không được gọi;
- vai trò không được phép → `khong_co_quyen`, tool không được gọi;
- gọi quá `so_lan_goi_toi_da` → `het_ngan_sach`;
- `han_chot` đã qua → `het_gio`;
- tham số thừa trường → `sai_tham_so`, và `noi_dung` không chứa giá trị đã gửi;
- tham số chứa họ tên người bệnh của DEMO-02 → `tham_so_co_dinh_danh`; tham số chỉ chứa `[TEN_1]` thì qua;
- tool ném `RuntimeError("bi mat 123")` → `loi_cong_cu`; chuỗi `"bi mat 123"` không có trong `noi_dung`, không có trong bước tiến trình, không có trong log;
- tool chạy quá `thoi_gian_toi_da` → `het_gio`;
- kết quả chứa họ tên người bệnh → đã bị che trong `noi_dung`;
- kết quả chứa "bỏ qua mọi hướng dẫn" → `nghi_chen_lenh`, `can_cu` rỗng;
- kết quả chứa `<<<DU_LIEU_BENH_AN` → chuỗi đó không còn;
- `noi_dung` 20000 ký tự bị cắt (phần thân ≤ 8000) và được bọc `<<<KET_QUA_CONG_CU`;
- tiến trình có bước `cong_cu_1` với `ten` là `ten_hien_thi`;
- `caplog` của `app.agent.audit` có một dòng mỗi lần gọi và không chứa câu hỏi hay tham số.

`test_luong_cu_cung.py` (module mang marker):
- tool giả lập `asker` bằng một lớp spy:
  - chế độ `ca` gọi `ask` với đúng đối số từ `ToolContext`;
  - chế độ `chung` gọi `ask_global`.
- `AskResult` có 2 `Chunk` → `can_cu` có 2 phần tử `doan:<id>`, `chi_tiet_tien_trinh == "2 đoạn nguồn"`.
- Ánh xạ trạng thái đúng như 3.5.
- Lược đồ tham số từ chối mọi trường (`{"x": 1}`).
- Một test tích hợp dùng `CaseAsker` thật với `FakeLLM`, theo mẫu `_make_asker` của `tests/orchestration/test_ask.py`: gọi qua `ToolGateway` → `trang_thai="ok"`, nội dung đã che PII.

## 4. Tiêu chí nghiệm thu (người review chạy)

```
uv run pytest -q                                   # toàn bộ xanh, số test cũ không giảm
uv run ruff check .
uv run ruff format --check .
CDSS_LUONG_CU_CUNG=0 uv run pytest -q tests/orchestration tests/agent   # không trượt; test marker bị skip
```

Thêm: rà diff không có tệp nào ngoài mục 2; không có f-string trong SQL; không log nội dung; `git diff app/orchestration app/api web` rỗng.

## 5. Báo cáo

Ghi `plan/briefs/T101-bao-cao.md`:
- tệp đã tạo hoặc sửa;
- quyết định đã chọn khi brief chưa nói rõ;
- danh sách test đã gắn marker;
- điều chưa làm được.
