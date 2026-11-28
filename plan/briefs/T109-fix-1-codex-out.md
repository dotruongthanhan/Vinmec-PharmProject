TRẠNG THÁI: **XONG**

FILE ĐÃ TẠO / SỬA:

- [tinh_chi_so.py](D:/create/Vinmec-PharmProject/app/agent/tools/tinh_chi_so.py): chỉ thêm giả định cân nặng vào nhãn Cockcroft–Gault; giữ nguyên mã trích dẫn.
- [test_tool_tinh_chi_so.py](D:/create/Vinmec-PharmProject/tests/agent/test_tool_tinh_chi_so.py): bổ sung kiểm thử nhãn IBW và Cockcroft–Gault.
- [tac_tu.v1.md](D:/create/Vinmec-PharmProject/config/prompts/tac_tu.v1.md): chuyển câu hướng dẫn vào mục 2.
- [T109-fix-1-bao-cao.md](D:/create/Vinmec-PharmProject/plan/briefs/T109-fix-1-bao-cao.md): ghi kết quả thực tế.

LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:

- `uv run ruff check app tests`: đạt.
- `uv run ruff format --check app tests`: 380 tệp đúng định dạng.
- `uv run pytest -q -p no:cacheprovider tests/agent tests/orchestration`: **196 passed**.

Các lệnh Ruff và pytest nghiệm thu đã được chạy lại sau lỗi thiết lập biến môi trường ở lần đầu; chi tiết có trong báo cáo. Kiểm thử mới cũng đã tái hiện lỗi nhãn trước khi sửa.

ĐIỂM LỆCH SO VỚI BRIEF: Không có.

VIỆC CHƯA LÀM / CÂU HỎI: Không có.