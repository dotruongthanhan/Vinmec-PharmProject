**TRẠNG THÁI: CHƯA XONG**

Đã thêm các mô hình dữ liệu minh hoạ, trường `bo_du_lieu` trong kết quả công cụ và trường `minh_hoa` mặc định rỗng trong `AskResult` và `TraLoi`. Đã cập nhật test tập trường hợp đồng API.

Tính năng chưa sử dụng được: Gateway chưa quản lý và che PII cho bộ dữ liệu; chưa có tool `ve_bieu_do`, bộ kiểm đặc tả, lưới tính, prompt và các test mới theo brief. API hiện chỉ trả danh sách hình rỗng.

**FILE ĐÃ TẠO / SỬA:** [báo cáo VZ1a](D:/create/Vinmec-PharmProject/plan/briefs/VZ1a-bao-cao.md), `app/agent/minh_hoa/models.py`, `app/agent/tools/base.py`, `app/orchestration/ask.py`, `app/api/schemas.py`, `tests/api/test_contract.py`.

**LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:** Ruff check và format check đạt. Pytest chạy tuần tự: agent 149 đạt; orchestration 84 đạt; tracing 14 đạt; eval 21 đạt; API 217 đạt, 2 bỏ qua, **1 trượt**. Test trượt là `test_suggest_index_build_and_query_latency`: dựng chỉ mục mất 3,77 giây so với ngưỡng 3 giây. Chi tiết có trong báo cáo.

**ĐIỂM LỆCH SO VỚI BRIEF:** Phần triển khai và kiểm thử tính năng minh hoạ còn thiếu như nêu trên; chưa đọc hết tài liệu và mã được brief chỉ định. Các test hiện có đạt không chứng minh tính năng đã hoàn thành.

**VIỆC CHƯA LÀM / CÂU HỎI:** Cần hoàn tất các phần còn thiếu và chạy lại nghiệm thu. Không cài gói, gọi mạng, đọc `.env` hay commit.