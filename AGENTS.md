# AGENTS.md – quy tắc cho agent code (Codex CLI, Gemini CLI)

Bạn là agent viết code cho dự án "AI agent hỗ trợ dược sĩ thẩm định y lệnh". Mỗi lần được gọi, bạn nhận một brief ở `plan/briefs/`. Làm đúng brief đó, không hơn.

## Bối cảnh ngắn

Hệ thống gom bối cảnh bệnh án, tính chỉ số lâm sàng, rà y lệnh theo 7 yếu tố và trả bảng nhận định có trích dẫn cho dược sĩ lâm sàng. Dược sĩ là người quyết định. Chi tiết ở `plan/plan-trien-khai-ai-agent-tham-dinh-y-lenh.md` (chỉ đọc mục brief chỉ tới).

## Quy tắc bắt buộc

1. **Phạm vi file:** chỉ tạo và sửa file brief cho phép. Không đụng `docs/`, `plan/`, `CLAUDE.md`, `AGENTS.md`, `README.md`, `.gitignore` trừ khi brief nói rõ.
2. **Git:** không `commit`, không `push`, không đổi nhánh, không `reset`, không `stash`.
3. **Dữ liệu:** không có dữ liệu người bệnh thật. Dữ liệu mẫu là giả lập, không dùng tên người thật.
4. **Mạng:** chỉ dùng mạng để cài thư viện brief liệt kê. Không tải dữ liệu, không gọi API ngoài, trừ khi brief nói rõ.
5. **Bí mật:** không ghi khoá API hay bí mật vào code, test, log. Đọc từ biến môi trường.
6. **Y khoa:** không tự bịa công thức, ngưỡng, liều. Chỉ dùng công thức và hằng số brief đưa. Thiếu thông tin thì dừng và ghi vào báo cáo, không đoán.
7. **Thiếu dữ liệu đầu vào:** trả kết quả "thiếu" kèm tên trường thiếu. Không gán giá trị mặc định cho số liệu lâm sàng.
8. **Không làm thừa:** không thêm tính năng, thư viện, lớp trừu tượng brief không yêu cầu.
9. **Tài liệu dữ liệu:**
   - Mỗi bộ dữ liệu có một tệp mô tả trong `docs/du-lieu/` (mục lục: `docs/du-lieu/README.md`).
   - Cần biết dữ liệu có trường gì thì **đọc tệp mô tả trước**, không mở dữ liệu dò lại.
   - Task nào tải, cào hay đổi cách xử lý dữ liệu thì **phải cập nhật tệp mô tả tương ứng**: trường, số dòng, lệnh, ngày. Được phép sửa tệp đó dù brief không nhắc, và ghi vào báo cáo.

## Quy ước code

- Python ≥ 3.11, quản lý bằng `uv` (`uv sync`, `uv run ...`).
- Kiểu dữ liệu đầy đủ (type hints); mô hình dữ liệu dùng pydantic v2.
- Tên trường dữ liệu: tiếng Việt không dấu, `snake_case`, đúng theo brief. Tên hàm, lớp, module: tiếng Anh.
- Docstring và chú thích: tiếng Việt, ngắn.
- Hàm tính toán là hàm thuần: không đọc file, không gọi mạng, không in ra màn hình.
- Số thập phân: tính bằng `float`, **không làm tròn bên trong hàm tính**; làm tròn chỉ ở lớp hiển thị.
- Test bằng `pytest`; lint bằng `ruff`.

## Khi xong

Chạy đủ lệnh nghiệm thu trong brief. Trả lời cuối cùng theo mẫu:

```text
TRẠNG THÁI: XONG | CHƯA XONG
FILE ĐÃ TẠO / SỬA: ...
LỆNH ĐÃ CHẠY VÀ KẾT QUẢ: ...
ĐIỂM LỆCH SO VỚI BRIEF (nếu có) VÀ LÝ DO: ...
VIỆC CHƯA LÀM / CÂU HỎI: ...
```

Nói thật kết quả: test trượt thì ghi là trượt kèm đầu ra.
