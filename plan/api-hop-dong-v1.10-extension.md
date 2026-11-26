# Hợp đồng API v1.10 — Extension Thẩm định Độc lập (Zero-Retention)

- **Phạm vi:** Dịch vụ FastAPI độc lập (`app/extension_api/`, cổng mặc định `8001`) dành riêng cho Chrome Side Panel Extension (`extension/`).
- **Nguyên tắc cô lập tuyệt đối:**
  1. Không kết nối hay đọc/ghi bất kỳ dữ liệu bệnh nhân nào thuộc schema `nghiep_vu` (`app.db.reader`, `app.db.administrative`, `app.db.medical_record`, `DbReviewResultStore`, `DbFeedbackChatStore`).
  2. Chỉ dùng kho tri thức công khai (`tri_thuc` hoặc file SQLite cục bộ: DAV, DDInter, openFDA, bảng luật D1–D7) ở chế độ **chỉ đọc**.
  3. Toàn bộ hồ sơ trích xuất (`CaBenh`, ảnh `OH`, kết quả thẩm định, tiến trình AI, hội thoại) chỉ nằm trong **RAM tạm thời** (`EphemeralSessionStore`, TTL mặc định 30 phút, tối đa 50 phiên), tự huỷ khi hết hạn hoặc khi dược sĩ bấm xoá phiên. Không ghi log dữ liệu bệnh nhân, không lưu ảnh xuống đĩa.
  4. Xác thực qua JWT Supabase (Bearer token) dùng chung tầng `app/auth/`; `AUTH_MODE=off` chỉ cho phép ở môi trường dev cục bộ.

## Danh sách điểm cuối (`/api/extension/*`)

| Phương thức | Đường dẫn | Trần thân | Mô tả |
|---|---|---|---|
| `GET` | `/api/extension/health` | — | Trạng thái dịch vụ độc lập, `zero_retention: true`, chế độ LLM/KB/xác thực |
| `GET` | `/api/extension/me` | — | Thông tin dược sĩ đang đăng nhập từ JWT (`NguoiDung`) |
| `POST` | `/api/extension/classify-schema` | `512 KB` | Phân loại **chỉ tên nhãn trường** EMR bằng `gemini-3.5-flash-lite` + tầng lọc từ khoá PII tiếng Việt |
| `POST` | `/api/extension/extract-and-review` | `8 MB` (`multipart/form-data`) | Nhận EMR JSON đã che PII + ảnh chụp `OH` lossless PNG (tuỳ chọn); chạy 4 worker Gemini song song + `run_case` tất định, trả `ExtensionReviewResponse` |
| `POST` | `/api/extension/sessions/{session_id}/recalc` | `512 KB` | Dược sĩ sửa nhanh sinh hiệu/xét nghiệm/dị ứng/thuốc và chạy lại `run_case` trong `<50 ms` |
| `POST` | `/api/extension/sessions/{session_id}/ai` | `512 KB` | Khởi động tác vụ nền `deepseek-flash` (`AiReviewer` + RAG openFDA + kiểm chứng `app/verify/`) |
| `GET` | `/api/extension/sessions/{session_id}/ai` | — | Đọc tiến trình từng bước (`cac_buoc`) và kết quả `KetQuaAI` |
| `POST` | `/api/extension/sessions/{session_id}/ask` | `512 KB` | Hỏi đáp agentic (`AgenticAsker`) có trích dẫn nguồn mở và lịch sử hội thoại giữ trong RAM phiên |
| `GET` | `/api/extension/sessions/{session_id}/ask-progress` | — | Đọc `TienTrinhHoiDap` thời gian thực cho câu hỏi đang chạy |
| `GET` | `/api/extension/sessions/{session_id}/sources/{doan_trich_id}` | — | Xem đoạn nguồn `DoanNguon` đã cấp cho phiên |
| `DELETE` | `/api/extension/sessions/{session_id}` | — | Xoá ngay lập tức toàn bộ dữ liệu RAM của phiên |
| `GET` | `/api/extension/lookup/drugs` | — | Tra cứu hoạt chất/chế phẩm công khai (tái sử dụng helper tra cứu chỉ đọc) |
| `POST` | `/api/extension/lookup/interactions` | `512 KB` | Tra nhanh ma trận tương tác DDInter công khai |

## Bảo mật bắt buộc theo hợp đồng

- **Chống IDOR (`404`):** Mọi thao tác trên `sessions/{session_id}*` kiểm tra `session.owner_user_id == principal.nguoi_dung_id`; nếu sai chủ sở hữu hoặc không tồn tại, trả đồng nhất `404`.
- **Kiểm tra chữ ký tệp ảnh:** `oh_image` bắt buộc có magic bytes hợp lệ của PNG, JPEG hoặc WebP và dung lượng `<= 8 MB`, nếu sai trả `422` (`HTTP 413` nếu vượt trần thân HTTP trước khi đọc).
- **Xác nhận cắt ảnh OH:** Nếu gửi kèm `oh_image`, trường `oh_crop_confirmed` phải là `true` để xác nhận dược sĩ đã cắt bỏ thanh định danh bệnh nhân.
- **Bảo vệ phân loại schema:** Chỉ nhận tên nhãn (`ten_nhan`), mã băm (`schema_hash`) và kiểu phần tử DOM; mọi lỗi phân loại đều an toàn chuyển sang nhóm `nghi_ngo_pii` để không làm lọt PII.
