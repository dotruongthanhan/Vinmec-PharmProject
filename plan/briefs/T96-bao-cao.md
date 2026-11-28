# Báo cáo T96: Tách `streamlit` ra khỏi production image

**Ngày:** 20/11/2026  
**Trạng thái:** Đã sửa `pyproject.toml` và hoàn tất rà soát tĩnh bằng đọc tệp; **chưa chạy** lệnh nghiệm thu (`uv lock`, `uv sync`, `ruff`, `pytest`, build Docker) do yêu cầu không dùng công cụ shell/mạng và không sửa `uv.lock`.

---

## 1. Tệp đã tạo / sửa và tệp giữ nguyên

- **Đã sửa:** `pyproject.toml`
  - Gỡ `"streamlit"` khỏi `[project].dependencies` (dòng 10–21).
  - Thêm `"streamlit"` vào `[dependency-groups].dev` (dòng 24–31).
- **Đã tạo:** `plan/briefs/T96-bao-cao.md` (báo cáo này).
- **Đã kiểm tra, không cần sửa:**
  - `README.md` (chỉ có 1 dòng `# Vinmec-PharmProject`, không nhắc Streamlit).
  - `CLAUDE.md` (dòng 80 đã ghi rõ *"giao diện chính là bản web React + TypeScript (`web/`) gọi API FastAPI (`app/api/`), bản Streamlit (`app/ui/`) chỉ để tham khảo và làm đường lui"*, không có câu nói Streamlit là phụ thuộc chính).
- **Không đụng theo đúng phạm vi brief:** `uv.lock`, `app/ui/*`, `Dockerfile`, `.github/workflows/ci.yml`, `web/`, `tests/`, `.env*`.

---

## 2. Rà soát `import streamlit` / `from streamlit` trong `app/` ngoài `app/ui/` (Mục 3)

**Kết quả:** Không phát hiện `import streamlit` hay `from streamlit` trong các tệp đã đọc thuộc `app/api/`, `app/orchestration/` và các gói khác ngoài `app/ui/`.

Chi tiết phạm vi đã đọc trực tiếp:

1. **`app/api/` (11 tệp, đọc đủ toàn bộ):**
   - `__init__.py`, `main.py`, `routes.py`, `service.py`, `presenter.py`, `schemas.py`, `lookup.py`, `formulas.py`, `access_log.py`, `rate_limit.py`, `auth_schemas.py` → `0` lượt nhập `streamlit`.
2. **`app/orchestration/` (10 tệp, đọc đủ toàn bộ):**
   - `__init__.py`, `ai_review.py`, `ask.py`, `evidence.py`, `jobs.py`, `graph/__init__.py`, `graph/builder.py`, `graph/nodes.py`, `graph/result.py`, `graph/state.py` → `0` lượt nhập `streamlit`.
3. **Các gói `app/` khác đã đọc kiểm tra trực tiếp:**
   - Gốc `app/`: `container.py`, `pipeline.py`, `feedback.py`.
   - `app/auth/`: `roles.py`, `principal.py`, `errors.py`, `verifier.py` (dòng 1–100), `revocation.py`, `online.py`, `dependencies.py`.
   - `app/config/`: `settings.py`.
   - `app/core/`: `interfaces.py`, `errors.py`, `types.py`.
   - `app/db/`: `reader.py`, `bang_luat_store.py` (dòng 1–800), `administrative.py`, `medical_record.py`, `chi_muc.py` (dòng 1–100), `bang_luat.py` (dòng 1–100), `mapping.py` (dòng 1–100), `sources.py` (dòng 1–100), `read_pool.py`, `cli.py` (dòng 1–100), `engine.py` (dòng 1–100), `timezone.py`.
   - `app/kb/`: `names.py` (dòng 1–100), `resolver/resolver.py` (dòng 1–100), `resolver/matching.py` (dòng 1–100), `interactions/store.py` (dòng 1–100), `interactions/models.py`.
   - `app/llm/`: `__init__.py`, `case_context.py`, `prompt_loader.py`, `schema.py`, `setup.py`, `synthesizer.py`.
   - `app/providers/`: `deepseek_llm.py` (dòng 1–100), `fakes.py`, `http.py`, `bm25_index.py`, `memory_store.py`, `embedder_factory.py` (dòng 1–100), `openrouter_embed.py`, `openrouter_rerank.py`, `cached_embedder.py`, `gemini_embed.py` (dòng 1–100).
   - `app/retrieval/`: `corpus.py` (dòng 1–100), `hybrid.py` (dòng 1–100), `fusion.py`.
   - `app/storage/`: `feedback_chat.py`, `review_results.py`, `case_repo.py`.
   - `app/verify/`: `citation.py`, `number.py` (dòng 1–100), `pipeline.py`, `merge.py` (dòng 1–100).
4. **Ràng buộc kiến trúc sẵn có:**
   - `tests/architecture/test_import_boundaries.py` (`test_core_import_boundaries`) kiểm AST cấm `streamlit` trong `app/domain`, `app/core`, `app/calc`, `app/rules`, `app/deid`.

> **Lưu ý phạm vi:** Do không dùng công cụ shell/liệt kê thư mục, việc kiểm tra dựa trên các tệp đọc trực tiếp theo danh sách đã biết; các lớp `app/domain`, `app/calc`, `app/rules`, `app/deid` chưa đọc từng tệp nhưng đã có bài kiểm AST `test_core_import_boundaries` và sẽ được xác minh toàn diện khi chạy `pytest` + nhập `app.api.main` trong môi trường `--no-dev`.

---

## 3. Kiểm tra các mô-đun `app/ui/` được dùng chung (Mục 4)

### 3.1. Danh sách nơi gọi `app.ui.*`

- **Trong `app/api/`:**
  - `app/api/service.py` (dòng 71–72): nhập `NHOM_LY_DO` từ `app.ui.labels`; nhập `NotReadyAskService`, `PipelineReviewService`, `ReviewService` từ `app.ui.services`.
  - `app/api/presenter.py` (dòng 19–20): nhập `app.ui.labels` và `app.ui.view_model`.
- **Trong `app/orchestration/`:**
  - `app/orchestration/ask.py` (dòng 37–38): nhập `app.ui.labels` và `app.ui.view_model`.
- **Trong các mô-đun `app/` khác (ngoài `app/ui/`):**
  - `app/db/medical_record.py` (dòng 18): nhập `app.ui.view_model`.
  - `app/storage/review_results.py` (dòng 30): nhập `app.ui.view_model`.
- **Trong `tests/api/` và `tests/orchestration/` (các tệp đã đọc):**
  - `tests/api/test_interaction_runtime.py` (dòng 30): nhập `PipelineReviewService` từ `app.ui.services`.
  - `tests/orchestration/test_ask.py` (dòng 587): nhập `finding_ids` từ `app.ui.view_model`.
  - Các tệp khác đã đọc trong `tests/api/` (`conftest.py`, `test_routes.py`, `test_contract.py`, `test_ai_routes.py`, `test_ask_routes.py`, `test_auth_ownership.py`, `test_access_log.py`, `test_llm_limits.py`, `test_body_limit_auth_first.py`, `test_ask_server_history.py`, `test_tra_cuu.py`, `test_review_results_db.py`, `test_administrative.py`, `test_medical_record.py`, `test_feedback_chat_db.py`) và `tests/orchestration/` (`test_ai_review.py`, `test_graph.py`, `test_jobs_limits.py`, `test_prompt_single_pass.py`, `test_jobs.py`, `test_evidence.py`) không nhập `app.ui.*` hay `streamlit`.

### 3.2. Xác nhận các mô-đun `app/ui/` dùng chung không nhập `streamlit`

- `app/ui/__init__.py` (1 dòng): chỉ có docstring, không có lệnh `import` (tức khi Python nhập gói `app.ui` không kích hoạt `streamlit_app.py`).
- `app/ui/labels.py`: chỉ nhập `collections.abc.Mapping`.
- `app/ui/services.py`: chỉ nhập stdlib (`pathlib`, `typing`), `pydantic`, `app.domain.*`, `app.pipeline`, `app.rules.*`, và lazy `app.container` trong `PipelineReviewService.review`; không nhập `streamlit`.
- `app/ui/view_model.py`: chỉ nhập stdlib, `app.domain.*`, `app.ui.labels` (và các kiểu dưới `if TYPE_CHECKING:`); không nhập `streamlit`.
- `app/ui/state.py` (cùng nhóm thuần UI): chỉ nhập stdlib và khối `TYPE_CHECKING`; không nhập `streamlit`.
- Chỉ duy nhất `app/ui/streamlit_app.py` nhập `streamlit`.
- Ngoài kiểm tra trực tiếp, `tests/ui/test_static_safety.py::test_pure_ui_modules_do_not_import_streamlit` kiểm AST bắt buộc `view_model.py`, `labels.py`, `services.py`, `state.py` không được nhập `streamlit`.

---

## 4. Nghiệm thu còn chờ Claude chạy

Do brief quy định *"Agent chỉ sửa tệp; Claude chạy `uv lock`, `uv sync`, `pytest`, `ruff`, build Docker"* và lần gọi này cấm dùng shell/mạng:

```bash
uv lock
uv sync --frozen
uv run ruff check .
uv run pytest
uv run --no-dev python -c "import app.api.main"
docker compose build api
```
