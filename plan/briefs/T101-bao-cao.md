# Báo cáo T101 – Lớp công cụ của agent, chính sách quyền, ToolGateway và tool `luong_cu_cung`

## 1. Tệp đã tạo hoặc sửa

**Tạo mới:**
- `app/agent/__init__.py`
- `app/agent/tools/__init__.py`
- `app/agent/tools/base.py`: `CheDo`, `CanCu`, `KetQuaCongCu`, `ToolContext`, `Tool`
- `app/agent/tools/registry.py`: `DanhMucCongCu`
- `app/agent/tools/policy.py`: `ChinhSachCongCu`, `luong_cu_cung_dang_bat`
- `app/agent/tools/gateway.py`: `ToolGateway`
- `app/agent/tools/luong_cu_cung.py`: `LuongCuCung`
- `config/tool_policy.yaml`
- `tests/agent/__init__.py`
- `tests/agent/test_registry.py`
- `tests/agent/test_policy.py`
- `tests/agent/test_gateway.py`
- `tests/agent/test_luong_cu_cung.py`

**Đã sửa (đúng phạm vi brief):**
- `app/config/settings.py`: thêm `AskSettings` và trường `ask: AskSettings = AskSettings()` vào `Settings`
- `config/settings.yaml`: thêm khối `ask` (`engine: "co_dinh"`, `tool_policy: "config/tool_policy.yaml"`)
- `pyproject.toml`: thêm marker `luong_cu_cung` vào `[tool.pytest.ini_options].markers`
- `tests/conftest.py`: giữ nguyên `can_du_lieu` và thêm bước skip item mang marker `luong_cu_cung` khi `luong_cu_cung_dang_bat()` trả `False`
- Gắn marker `luong_cu_cung` vào các tệp test của luồng cũ (xem mục 3).

Không sửa tệp nào trong `app/orchestration/`, `app/api/`, `app/container.py`, `web/`, `config/prompts/`.

## 2. Quyết định đã chọn khi brief chưa nói rõ

1. **Cách đếm ngân sách `so_lan_goi_toi_da` trong `ToolGateway`:**
   Chỉ tăng bộ đếm lượt đã gọi khi yêu cầu vượt qua các bước kiểm tra trước (tồn tại, quyền, ngân sách, hạn giờ, lược đồ tham số, quét PII) và chuẩn bị thực thi tool ở bước 6. Lần gọi bị từ chối ở bước 1–5 vẫn ghi bước tiến trình lỗi (`cong_cu_<n>`, tên `"Gọi công cụ bị từ chối"`) và một dòng nhật ký kiểm toán `app.agent.audit`, nhưng không tiêu tốn ngân sách thực thi tool.
2. **Định dạng thẻ bọc đầu ra `ToolGateway`:**
   Bước 7.5 bọc theo mẫu `<<<KET_QUA_CONG_CU ten={tool.ten}>>>\n{cleaned}\nKET_QUA_CONG_CU>>>` (ba dấu `>` đóng thẻ mở sau tên tool) để khớp với bước 7.2 (`<<<KET_QUA_CONG_CU` và `KET_QUA_CONG_CU>>>`).
3. **Cách chạy tool trong luồng phụ và `ContextVar` tiến trình:**
   `ToolGateway` chạy `tool.chay` trong `ThreadPoolExecutor(max_workers=1)` tương tự `CaseAsker._run_with_deadline` mà không sao chép `ContextVar` `tien_trinh_hien_tai` sang luồng con, để tránh tool bên trong (như `CaseAsker` trong `luong_cu_cung`) ghi đè hoặc chèn bước con vào tiến trình `cong_cu_<n>` do `ToolGateway` quản lý.
4. **Hậu xử lý ký tự rộng 0 khi quét chèn lệnh:**
   Ngoài `_has_injection_directive(cleaned)` từ `app.orchestration.ask`, `ToolGateway` còn kiểm tra bản đã loại ký tự rộng 0 / đảo chiều (`\u200b-\u200f`, `\u202a-\u202e`, `\ufeff`) để tránh lách bộ lọc chèn lệnh.
5. **Định dạng trích dẫn trong `LuongCuCung.chay` và nhãn `CanCu`:**
   - Trích dẫn có `trich_nguyen_van` định dạng `[so] nhan: trich_nguyen_van`; trích dẫn không có `trich_nguyen_van` (ví dụ `du_lieu`, `tinh_toan`) định dạng `[so] nhan`.
   - `CanCu.nhan` map mã nguồn công khai (`openfda` → `"Nhãn FDA"`, `byt` → `"Hướng dẫn Bộ Y tế"`, v.v.).
6. **Chính sách `che_do_cho_phep` trong `ChinhSachCongCu.cac_cong_cu_duoc_phep`:**
   Ngoài kiểm tra YAML `cho_phep`, hàm còn lọc theo `che_do in tool.che_do_cho_phep` của từng tool đã đăng ký để đồng bộ với chốt chặn tại bước 2 của `ToolGateway`.
7. **Áp dụng `CDSS_LUONG_CU_CUNG`:**
   Đặt hàm `luong_cu_cung_dang_bat()` gọi `ChinhSachCongCu.tu_tep(path)` trước rồi kiểm `cong_cu_bat("luong_cu_cung")`, trả `True` khi tệp thiếu hoặc lỗi (`ConfigError`).

## 3. Danh sách test đã gắn marker `luong_cu_cung`

**Cả module (`pytestmark = pytest.mark.luong_cu_cung`):**
- `tests/orchestration/test_ask.py`
- `tests/orchestration/test_ask_deid.py`
- `tests/orchestration/test_ask_global_none_fields.py`
- `tests/orchestration/test_prompt_single_pass.py`
- `tests/agent/test_luong_cu_cung.py`

**Từng hàm (`@pytest.mark.luong_cu_cung`):**
- `tests/orchestration/test_progress.py`: `test_case_asker_records_steps_for_success_retry_and_errors`
- `tests/db/test_bang_luat.py`: `test_container_service_asker_use_db_without_local_kb_files`

## 4. Điều chưa làm được

- Theo yêu cầu không gọi công cụ shell, các lệnh nghiệm thu (`uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `CDSS_LUONG_CU_CUNG=0 uv run pytest -q tests/orchestration tests/agent`) **chưa được chạy** trong phiên này; người review cần chạy trực tiếp để xác nhận.
