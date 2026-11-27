# T109-fix-1 – Báo cáo

TRẠNG THÁI: XONG

## FILE ĐÃ TẠO / SỬA

- Sửa `app/agent/tools/tinh_chi_so.py`: chỉ thêm giả định cân nặng vào nhãn Cockcroft–Gault; giữ nguyên mã trích dẫn.
- Sửa `tests/agent/test_tool_tinh_chi_so.py`: kiểm tra nhãn và mã của IBW Devine và Cockcroft–Gault với cân nặng lý tưởng.
- Sửa `config/prompts/tac_tu.v1.md`: chuyển nguyên câu hướng dẫn gọi công cụ thành gạch đầu dòng trong mục 2.
- Tạo báo cáo này.

## LỆNH ĐÃ CHẠY VÀ KẾT QUẢ

Các lệnh `uv run` dùng `UV_NO_SYNC=1`, `UV_OFFLINE=1`, thư mục cache uv trong thư mục tạm; pytest tắt ghi bytecode, tắt dotenv, đặt `KB_SOURCE=file`, bỏ `DATABASE_URL` khỏi môi trường tiến trình và dùng thư mục tạm riêng. Không cài gói, gọi mạng hay ghi DB.

- Trước khi sửa mã, `uv run pytest -q -p no:cacheprovider tests/agent/test_tool_tinh_chi_so.py -k citation_labels_match_weight_assumption`: **1 failed, 14 deselected in 0.21s**. Lỗi đúng như dự kiến: nhãn IBW là `IBW Devine · cân nặng thực tế` thay vì `IBW Devine`.
- `uv run ruff check app tests`: `All checks passed!`
- `uv run ruff format --check app tests`: `380 files already formatted`
- `uv run pytest -q -p no:cacheprovider tests/agent tests/orchestration`: `196 passed in 37.14s`.

Hai lệnh Ruff lúc đầu thoát mã 1 vì đặt `RUFF_NO_CACHE=1`: `error: invalid value '1' for '--no-cache'` (giá trị hợp lệ `true`, `false`). Đã chạy lại với `RUFF_NO_CACHE=true` và đạt như trên.

Lần pytest nghiệm thu đầu: `186 passed, 10 errors in 29.43s`. Mười lỗi đều khi thiết lập thư mục tạm với `PermissionError: [WinError 5] Access is denied: 'C:\UsersAdminAppDataLocalTempt109-fix-pytest'`, do dấu phân cách đường dẫn bị mất khi phân tích `PYTEST_ADDOPTS`. Đã chạy lại với đường dẫn dùng dấu `/`, đạt như trên.

## ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO

Không có.

## VIỆC CHƯA LÀM / CÂU HỎI

Không có.
