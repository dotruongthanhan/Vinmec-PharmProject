# T12 – Điều phối: nối truy xuất + LLM + kiểm chứng vào API (chạy nền)

**Giao cho:** agy CLI (`gemini-4-hydrogen-xhigh`) · **Ngày:** 16/11/2026 (phiên 3)
**Đọc trước (bắt buộc):** `AGENTS.md`; `plan/api-hop-dong-v1.md`; **`plan/api-hop-dong-v1.1-bo-sung.md`** (đây là đích của task này).
**Chỉ đọc để dùng:** `app/api/*`, `app/pipeline.py`, `app/llm/schema.py`, `app/llm/setup.py`, `app/llm/synthesizer.py`, `app/retrieval/*`, `app/kb/names.py`, `app/core/*`, `app/container.py`, `tests/api/*`.

**Đang chạy song song, cấm đụng file của họ:** T05-fix-1 (`app/providers/deepseek_llm.py`, `app/llm/**`, `app/config/**`, `config/settings.yaml`), T04a-fix-1 (`app/kb/**`), T21 (`web/**`). Bạn chỉ **gọi** các lớp đó qua giao diện hiện có.

## 1. Mục tiêu

Hiện API chỉ trả kết quả của bộ luật. Các phần truy xuất lai (T04b), tổng hợp bằng DeepSeek và kiểm chứng (T05) đã có nhưng chưa nối vào đâu. Task này nối chúng lại thành một bước AI chạy nền cho từng ca, đúng hợp đồng v1.1. Gọi LLM mất 20–25 giây nên **không được chặn** `GET /api/cases/{ca_id}`.

## 2. Phạm vi file

```text
app/orchestration/__init__.py        (mới)
app/orchestration/evidence.py        (mới: lấy đoạn nguồn cho một ca)
app/orchestration/ai_review.py       (mới: chạy một lần phân tích AI cho một ca)
app/orchestration/jobs.py            (mới: quản lý việc chạy nền và bộ đệm kết quả)
app/api/schemas.py                   (thêm kiểu v1.1)
app/api/presenter.py                 (thêm hàm trình bày kết quả AI, đoạn nguồn; cập nhật che_do)
app/api/service.py                   (thêm 3 thao tác; phản hồi nhận mã dòng AI)
app/api/routes.py                    (thêm 3 điểm cuối)
app/api/main.py                      (chỉ khi cần khởi tạo / đóng bộ chạy nền)
tests/orchestration/__init__.py, test_evidence.py, test_ai_review.py, test_jobs.py   (mới)
tests/api/test_ai_routes.py          (mới)
tests/api/test_contract.py, test_presenter.py, test_routes.py   (chỉ sửa chỗ bị ảnh hưởng bởi 3 trường mới)
```

Không sửa `app/llm`, `app/retrieval`, `app/providers`, `app/kb`, `app/rules`, `app/calc`, `app/domain`, `app/ui`, `app/container.py`, `pyproject.toml`, `config/`, `web/`, `data/`.

## 3. Thiết kế

### 3.1. `evidence.py` – lấy đoạn nguồn

`class EvidenceCollector` nhận một bộ truy xuất (giao diện có `retrieve(query) -> list[ScoredChunk]`), một `QueryBuilder`, và hàm tra tên hoạt chất.

`collect(ca, ket_qua) -> tuple[list[Chunk], list[str]]` (đoạn, cảnh báo):

1. Lấy hoạt chất của các dòng trong `ca.y_lenh_cho_duyet.chi_tiet` (qua `ingredients_of`). Mã hoạt chất dùng cho kho là dạng chuẩn hoá của `app/kb/names.py`; tra từ `HoatChat.ten_quoc_te` (không có thì từ `ten_hoat_chat`). Hoạt chất không tra được: bỏ qua và thêm cảnh báo `Chưa có nguồn cho hoạt chất <tên>`.
2. Với mỗi phát hiện của luật có `ket_luan != "dat"`: một truy vấn `QueryBuilder.for_finding(...)` cho từng hoạt chất của các dòng thuốc gắn với phát hiện đó.
3. Với mỗi hoạt chất: các truy vấn `QueryBuilder.baseline(...)`.
4. Gộp kết quả, bỏ trùng theo `doan_trich_id`, giữ thứ tự: đoạn của truy vấn theo phát hiện trước, rồi đoạn nền; trong mỗi nhóm theo điểm giảm dần. Cắt còn tối đa **8** đoạn (hằng số có tên, đặt đầu file).
5. Truy xuất ném lỗi (mạng, nhà cung cấp): **không ném tiếp**. Trả danh sách đoạn đã có (có thể rỗng) và cảnh báo `Không lấy được đoạn nguồn, AI chỉ dùng dữ liệu ca`.

**Không được đưa văn bản ca bệnh vào truy vấn.** Truy vấn chỉ gồm tên hoạt chất và mẫu câu của `QueryBuilder`.

### 3.2. Bộ truy xuất dựng lười theo hoạt chất

`app/retrieval/setup.py::build_retriever` hiện nhúng cả 3.738 đoạn ngay khi dựng, quá chậm cho lần chạy đầu. Trong `app/orchestration/evidence.py` viết `class LazyRetrieverFactory`:

- Nạp kho đoạn một lần (`load_corpus`).
- `for_ingredients(ids: set[str])` trả một `HybridRetriever` chỉ chứa các đoạn có `hoat_chat_ids` giao với `ids`; lưu đệm theo `frozenset(ids)`.
- Dùng lại đúng các lớp mà `build_retriever` dùng (bộ nhúng có bộ đệm SQLite, bộ xếp hạng lại, `InMemoryVectorStore`, `Bm25Index`, `index_corpus`) và đúng cấu hình trong `container.settings`. Đọc `build_retriever` để lấy cách khởi tạo; nếu để dùng lại mà buộc phải sửa `app/retrieval/setup.py` thì **dừng và ghi vào báo cáo**, đừng sửa.
- Không có tệp kho đoạn → `che_do.truy_xuat = "chua_co"`, bước AI vẫn chạy với 0 đoạn và có cảnh báo.

### 3.3. `ai_review.py`

`class AiReviewer` nhận `EvidenceCollector` và `Synthesizer`.

`run(ca, ket_qua) -> AiRunResult` với `AiRunResult = {llm: KetQuaLLM, doan: list[Chunk], canh_bao: list[str], thoi_gian_ms: float}`: gọi `collect`, rồi `synthesizer.run(ca, ket_qua, doan)`, gộp cảnh báo của hai bước. Mọi ngoại lệ không lường trước được bọc lại thành kết quả lỗi có cảnh báo `Bước AI gặp lỗi không mong muốn (<tên lớp ngoại lệ>)`; không để lộ nội dung ca hay thông báo gốc.

### 3.4. `jobs.py`

`class AiJobManager`: `ThreadPoolExecutor(max_workers=2)`, một khoá, một từ điển `ca_id -> trạng thái`.

- `start(ca_id, fn, restart=False)`: chưa có hoặc `restart` → đặt `dang_chay` và nộp việc; đang chạy hoặc đã xong → không làm gì. Trả trạng thái hiện tại.
- `get(ca_id)` → trạng thái hoặc `None`.
- Việc xong → `xong` kèm kết quả; việc ném lỗi → `loi` kèm cảnh báo.
- `shutdown()` để gọi khi ứng dụng tắt và trong test.
- Hai lần `start` đồng thời cho cùng một ca chỉ được sinh **một** lần chạy.

### 3.5. Trình bày – `presenter.py`

Hàm `present_ai_result(...) -> KetQuaAI` chuyển `KetQuaLLM.nhan_dinh` (`NhanDinhCuoi`) thành các dòng `NhanDinh` của hợp đồng:

| `NhanDinhCuoi` | Dòng trả về |
| :--- | :--- |
| `nguon_goc="luat"` | Đúng dòng mà `present_case` đã sinh cho phát hiện đó (cùng `nhan_dinh_id`, kết luận, mức độ, căn cứ), cộng `dien_giai_ai = dien_giai.nhan_xet`, `de_xuat_ai = dien_giai.de_xuat`, `trich_dan` từ `dien_giai.trich_dan`. Không có `dien_giai` thì ba trường là `null`, `null`, `[]` |
| `nguon_goc="ai_da_kiem_chung"` | Dòng mới: `nhan_dinh_id = "ai|" + 12 ký tự đầu của SHA-256(yeu_to + nhan_xet + các mã dòng thuốc)`, `nguon_goc_ma="ai_da_kiem_chung"`, `nguon_goc_nhan="AI · đã kiểm chứng"`, `ma_luat=null`, `nhan_xet = de_xuat.nhan_xet`, `de_xuat_ai = de_xuat.de_xuat`, `dien_giai_ai=null`, `thong_tin_con_thieu` giữ nguyên; `can_cu` dựng từ `de_xuat.ban_ghi_ids` (loại `du_lieu`, `mo_duoc=true` nếu bản ghi tìm thấy trong ca) |
| `nguon_goc="ai_chua_kiem_chung"` | **Bỏ**, không trả về |

- `TrichDan.nhan` = `"<tên hiển thị của nguồn> · <duong_dan_muc>"` lấy từ đoạn nguồn tương ứng; `so` đánh từ 1 trong từng dòng.
- Phân nhóm `can_chu_y` / `dat` và thứ tự sắp xếp: dùng lại đúng hàm đang dùng cho `ChiTietCa`.
- **Bất biến 1 của hợp đồng v1.1 phải được kiểm bằng code ngay trong `present_ai_result`:** nếu tập `nhan_dinh_id` của các dòng `nguon_goc_ma="luat"` khác tập của `ChiTietCa`, hoặc có dòng lệch `ket_luan_ma` / `muc_do_ma`, thì trả `trang_thai="loi"`, `nhan_dinh=null`, cảnh báo `Kết quả AI không giữ đủ phát hiện của bộ luật, đã bị loại`.
- `KetQuaLLM.trang_thai` khác `"ok"` → `KetQuaAI.trang_thai="loi"`, `nhan_dinh=null`, `canh_bao` giữ nguyên các câu đã có.
- `current_mode` cập nhật theo bất biến 4 của hợp đồng v1.1; bỏ thông báo "Đang chạy không có bước AI" khi AI bật.
- `present_case` thêm ba trường mới với giá trị `null`, `null`, `[]`.

### 3.6. Dịch vụ và điểm cuối

Ba điểm cuối ở mục 2 của hợp đồng v1.1. Thêm:

- AI bật hay tắt xác định một lần lúc khởi tạo dịch vụ: gọi `build_synthesizer(build_container())`; ném `ConfigError` hoặc biến môi trường `CDSS_AI=off` → tắt. Không đọc `.env` trực tiếp, không đọc khoá ở lớp API.
- Dịch vụ nhận bộ chạy AI qua tham số khởi tạo (mặc định dựng thật) để test tiêm bản giả.
- `GET …/sources/{doan_trich_id}`: tra trong danh sách `doan` của lần phân tích gần nhất của ca.
- `feedback`: mã dòng hợp lệ = mã các dòng của luật + mã các dòng AI trong kết quả `xong` gần nhất.

## 4. Kiểm thử phải có (không gọi mạng; dùng bản giả trong `app/providers/fakes.py` và lớp giả tự viết trong test)

1. `EvidenceCollector`: bỏ trùng; thứ tự phát hiện trước nền; cắt còn 8; truy xuất ném lỗi → trả cảnh báo, không ném; truy vấn sinh ra không chứa chuỗi nào lấy từ `dien_bien` của ca (kiểm bằng ca DEMO-06: không truy vấn nào chứa "Bỏ qua").
2. `AiJobManager`: hai `start` liền nhau chỉ gọi hàm một lần; `restart=True` gọi lại; việc ném lỗi → `loi`.
3. `present_ai_result` với `KetQuaLLM` dựng tay cho DEMO-02: dòng luật giữ nguyên mã, kết luận, mức độ và có `dien_giai_ai`; dòng `ai_da_kiem_chung` có mã bắt đầu `ai|`; dòng `ai_chua_kiem_chung` không xuất hiện; `trich_dan[0].nhan` có tên nguồn và đường dẫn mục.
4. Bất biến: `KetQuaLLM` thiếu một phát hiện của luật → `trang_thai="loi"`; `KetQuaLLM` trong đó phát hiện luật bị đổi `ket_luan` → `"loi"`.
5. Điểm cuối (dùng `TestClient`, bộ chạy AI giả trả ngay): `GET …/ai` trước khi khởi động → 404 mã `chua_chay`; `POST …/ai` → `dang_chay` hoặc `xong`; gọi lặp đến khi `xong`; `GET …/sources/<mã đã cấp>` → 200, mã lạ → 404; `POST …/ai` với AI tắt → `tat`; ca không tồn tại → 404; phản hồi cho mã `ai|…` hợp lệ → 200.
6. `GET /api/cases/{ca_id}` vẫn trả trong thời gian ngắn khi AI đang chạy (bộ chạy giả ngủ 1 giây; yêu cầu chi tiết ca phải xong dưới 0,5 giây).
7. Toàn bộ test hiện có vẫn qua; test hợp đồng cũ được cập nhật ba trường mới.

## 5. Nghiệm thu (người review chạy; bạn không gọi công cụ shell)

```bash
uv run ruff check . --exclude tests/architecture/.tmp
uv run ruff format --check app/orchestration app/api tests/orchestration tests/api
uv run pytest -q -p no:cacheprovider
uv run uvicorn app.api.main:app --port 8000
```

rồi gọi thật `POST /api/cases/DEMO-02/ai`, hỏi trạng thái đến khi xong, và đối chiếu ba bất biến.

Viết code đúng định dạng `ruff format` (dòng tối đa 100 ký tự, nháy kép). Test kiến trúc phải qua: `httpx` chỉ được import trong `app/providers/`; lớp API và điều phối không đọc biến môi trường chứa khoá.

## 6. Cấm làm

- Không thêm thư viện (không LangGraph ở bản này; đồ thị để sau demo).
- Không ghi log nội dung ca, nội dung tin nhắn, khoá.
- Không để AI xoá, sửa, hạ mức phát hiện của luật.
- Không làm ô hỏi thêm (`/ask` giữ nguyên).
- Không commit, không push. **Không gọi công cụ shell** (gọi là cả phiên ra rỗng). Xong thì trả lời theo mẫu báo cáo trong `AGENTS.md`, ghi rõ chưa chạy lệnh nào.
