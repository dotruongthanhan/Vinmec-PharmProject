# T110 – Báo cáo tool `doc_doan_mo_rong`

TRẠNG THÁI: CHƯA XONG. Đã triển khai nhưng còn lỗi bảo mật và nghiệm thu chưa đạt; không nên coi tool đã sẵn sàng sử dụng.

## FILE ĐÃ TẠO / SỬA

- Tạo `app/agent/tools/doc_doan_mo_rong.py`, `tests/agent/test_tool_doc_doan_mo_rong.py` và báo cáo này.
- Sửa `app/agent/tools/base.py`, `gateway.py`, `tim_doan_nguon.py`, `__init__.py`, `app/container.py`, `config/tool_policy.yaml` và `config/prompts/tac_tu.v1.md`.
- Các thay đổi T108/T109 và các thay đổi có sẵn khác trong workspace được giữ lại. Không sửa `tra_thuoc.py` hay `tinh_chi_so.py`.

Gateway lưu cả tập mã lẫn `Chunk` tương ứng sau hậu xử lý, rồi truyền `doan_goc` bằng tham số từ khóa tùy chọn chỉ với tool yêu cầu đoạn đã trả. Cách này không nạp lại cả kho để tìm mã và không đổi `ToolContext`; tool cũ vẫn được gọi với hai tham số như trước. Tool mới nạp đoạn anh em bằng `ingredient_items`, không nhúng hay gọi LLM; thứ tự tệp được nạp lười một lần với khóa và lưu cache trong bộ nhớ.

## LỆNH ĐÃ CHẠY VÀ KẾT QUẢ

Đặt `UV_NO_SYNC=1`, `UV_OFFLINE=1`, `PYTHONDONTWRITEBYTECODE=1`, `KB_SOURCE=file`, `RUFF_NO_CACHE=true`; chuyển cache uv và thư mục tạm pytest sang thư mục tạm riêng vì đường mặc định bị từ chối truy cập. Không cài gói, gọi mạng hay ghi DB.

```text
uv run ruff check app tests
All checks passed!

uv run ruff format --check app tests
382 files already formatted

uv run pytest -q -p no:cacheprovider tests/agent tests/orchestration
3 failed, 203 passed in 37.09s

uv run pytest -q -p no:cacheprovider tests/agent tests/orchestration --tb=short
FAILED tests/agent/test_tool_doc_doan_mo_rong.py::test_luot_va_schema
FAILED tests/agent/test_tool_doc_doan_mo_rong.py::test_injection_does_not_authorize_sibling
FAILED tests/agent/test_tool_doc_doan_mo_rong.py::test_graph_verifies_sibling_quote[The sibling sentence is here.-ok]
3 failed, 203 passed in 39.18s
```

Ba test trượt: `test_luot_va_schema` (mã hợp lệ `DT-000000000001` trong kết quả bị che thành `DT-[CCCD_1]`); `test_injection_does_not_authorize_sibling` (mẫu chỉ thị trong đoạn anh em không bị phát hiện, trả `ok` thay vì `nghi_chen_lenh`); `test_graph_verifies_sibling_quote[The sibling sentence is here.-ok]` (`khong_co_nguon` thay vì `ok` do mã đoạn bị từ chối).

Lần đầu dùng cache uv mặc định bị `Access is denied`; sau đó dùng cache tạm riêng. Một lần chạy Ruff với `RUFF_NO_CACHE=1` bị từ chối vì Ruff yêu cầu `true` hoặc `false`; đã sửa thành `true` và chạy lại như trên.

## ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO

- Giả định `ask_global()` tạo Gateway mới không đúng với mã hiện tại: `AgenticAsker.ask()` tạo Gateway mới mỗi lượt; `ask_global()` đang chuyển thẳng sang bộ hỏi chung luồng cũ, không chạy Gateway/đồ thị agent. Không sửa luồng này vì brief cấm sửa phần đó. Tool được khai báo cho chế độ `chung`, nhưng `ask_global()` hiện không sử dụng tool.
- Bộ che PII hiện có nhận nhầm một số mã đoạn hợp lệ; bộ dò chèn lệnh hiện có không nhận cụm `Ignore all previous instructions`. Khi thử sửa hậu xử lý Gateway để xử lý hai lỗi này, 206 test đã qua, nhưng các sửa đổi hậu xử lý đó nằm ngoài phạm vi Gateway mà brief cho phép, nên đã bỏ. Cần chủ kho cho phép mở rộng phạm vi sửa hoặc giao brief tiếp theo trước khi sửa các chốt này.
- Không sửa tài liệu `docs/du-lieu/openfda-rag.md` vì brief T110 cấm `docs/`; tool chỉ đọc thứ tự dòng từ corpus hiện có, không thay dữ liệu hoặc pipeline tạo dữ liệu.
- Đã đọc nhầm một tệp hướng dẫn skill dưới `~/.codex` lúc bắt đầu, trái quy tắc dự án không đọc thư mục đó. Sau khi nhận ra, không đọc thêm tệp nào tại đó. Đây là lỗi thao tác, không phải yêu cầu của brief.

## VIỆC CHƯA LÀM / CÂU HỎI

- Cần sửa, chạy lại và nghiệm thu các trường hợp PII, chèn lệnh và trích dẫn kể trên. Cần xử lý riêng luồng hỏi chung nếu yêu cầu tool hoạt động qua `ask_global()`.
- Chính sách hiện khai báo tool bật theo brief, dù test chèn lệnh chưa đạt; không nên sử dụng tool này trước khi khắc phục.
- Chưa kiểm bằng LLM thật; brief giao việc đó cho Claude review. Không gọi mạng hay DB để kiểm.
