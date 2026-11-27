# Báo cáo LLM-GEMINI

## Trạng thái: CHƯA XONG

Đã chuyển máy khách sang `ChatLLMClient`, cấu hình `chat_api` và URL HTTPS; thêm `KeyRouter` giới hạn tối đa tám khoá, xoay vòng an toàn luồng, nghỉ theo 429, vô hiệu hoá khi 401/403, và ghi số thứ tự/số khoá đã thử vào vết. Không đưa giá trị khoá vào thông báo lỗi hoặc log. Thiếu tất cả khoá thì lùi về chế độ không có LLM. Cấu hình giá của mô hình mặc định là 0. Nhúng giữ nguyên.

Đã đổi tên `app/providers/deepseek_llm.py` thành `app/providers/llm_client.py`, thêm `app/providers/key_router.py`; sửa `app/providers/http.py`, `app/llm/setup.py`, `app/container.py`, `app/config/settings.py`, `app/tracing/models.py`, `config/settings.yaml`, `.env.example`; đổi tên và bổ sung test trong `tests/providers/`, sửa các test liên quan được liệt kê trong brief, thêm test cấu hình trong `tests/config/test_settings.py`.

## Kiểm tra

- `uv --no-cache run ruff check app tests`: qua.
- `uv --no-cache run ruff format --check app tests`: qua, 465 tệp.
- Pytest chạy riêng từng thư mục, `-q -p no:cacheprovider`: `tests/providers` 75 qua; `tests/config` 44 qua; `tests/agent` 268 qua; `tests/orchestration` 84 qua; `tests/tracing` 26 qua; kiểm tra thêm `tests/llm` 35 qua, `tests/api` 218 qua và 2 bỏ qua; `tests/test_container.py` 3 qua.
- Với pytest, đặt `PYTHON_DOTENV_DISABLED=1`, `UV_NO_SYNC=1`, dùng `--no-cache` và thư mục tạm riêng. Trước khi pytest nạp test, thay `app.config.settings.load_env_file` bằng hàm rỗng; một số test import `app.api.main` trong pytest. Không đọc `.env`, không gọi hàm nạp môi trường, không gọi mạng, không cài gói.
- Lần chạy đầu `uv run pytest` lỗi vì không có quyền truy cập cache uv mặc định; lần sau dùng `uv --no-cache`. Lần đầu test provider còn lỗi do tệp mới chưa hoàn tất và thư mục tạm mặc định không có quyền truy cập; đã sửa và chạy lại như trên.
- Các thư mục `.tmp-gemini-*` do pytest tạo trong `tests/providers/` và `tests/config/` còn lại: hệ thống tự động từ chối lệnh xoá đệ quy khi dọn chúng.

## Điểm chưa đạt

`rg -n -i "deepseek" app tests` còn bốn dòng: ba dòng trong `tests/architecture/test_notebook.py` và một dòng trong `tests/eval/test_cham_hoi_dap.py`. Hai tệp này không có trong danh sách tệp được phép sửa của brief bổ sung, nên giữ nguyên. Vì điều kiện nghiệm thu yêu cầu không có dòng nào, trạng thái vẫn là CHƯA XONG. Cần chủ kho mở rộng phạm vi cho hai tệp này hoặc điều chỉnh điều kiện nghiệm thu. Các kiểm thử gọi mô hình thật thuộc phần Claude chạy sau, chưa thực hiện do brief cấm mạng và đọc bí mật.
