# Hợp đồng API v1.2 – hỏi đáp theo ca (bổ sung cho v1 và v1.1)

Ngày: 17/11/2026. Chỉ **thêm** trường; không đổi tên, không bỏ trường nào của v1 và v1.1.

## 1. `POST /api/cases/{ca_id}/ask`

Thân `GuiCauHoi` (thêm 1 trường tuỳ chọn):

| Trường | Kiểu | Ghi chú |
| :--- | :--- | :--- |
| `cau_hoi` | chuỗi, 1–1000 ký tự | Dài hơn → 422 |
| `lich_su` | danh sách `ChatMessage` | Backend chỉ dùng tối đa 6 tin gần nhất |
| `nhan_dinh_id` | chuỗi hoặc `null` (mới, mặc định `null`) | Dược sĩ bấm "Hỏi AI về mục này" trên một thẻ nhận định |

Trả `TraLoi`:

| Trường | Kiểu | Ghi chú |
| :--- | :--- | :--- |
| `trang_thai` | `ok` · `khong_co_nguon` · `ngoai_pham_vi` · `loi` · `chua_san_sang` | `chua_san_sang` chỉ khi máy chủ không có LLM |
| `noi_dung` | chuỗi văn bản thuần | Không markdown, không HTML |
| `trich_dan` | danh sách `Citation` | Số `so` khớp với dấu `[n]` trong `noi_dung` |
| `cong_cu_da_goi` | danh sách chuỗi | Ví dụ `["du_lieu_ca", "bo_luat", "truy_xuat"]` |
| `thoi_gian_ms` | số nguyên (mới) | |

`Citation` (thêm 2 trường tuỳ chọn):

| Trường | Kiểu | Ghi chú |
| :--- | :--- | :--- |
| `so` | số nguyên | |
| `loai_ma` | `LoaiCanCuMa` sẵn có | dữ liệu ca · tính toán · tài liệu |
| `nhan` | chuỗi | |
| `ban_ghi_id` | chuỗi hoặc `null` | Khi căn cứ là bản ghi của ca |
| `doan_trich_id` | chuỗi hoặc `null` (mới) | Khi căn cứ là đoạn tài liệu; mở bằng `GET /api/cases/{ca_id}/sources/{doan_trich_id}` |
| `trich_nguyen_van` | chuỗi hoặc `null` (mới) | Câu nguyên văn, phải là chuỗi con của đoạn nguồn |

## 2. Nghĩa của từng trạng thái

| Trạng thái | Khi nào | `noi_dung` |
| :--- | :--- | :--- |
| `ok` | Có căn cứ, câu trả lời qua được bước kiểm chứng | Câu trả lời kèm dấu `[n]` |
| `khong_co_nguon` | Không truy xuất được đoạn nào liên quan, hoặc câu trả lời không qua kiểm chứng | Câu cố định nói rõ không đủ căn cứ để trả lời |
| `ngoai_pham_vi` | Câu hỏi không liên quan ca hoặc thuốc; yêu cầu hệ thống duyệt thay, kê đơn thay; câu hỏi chứa chỉ thị cho hệ thống | Câu cố định |
| `loi` | Lỗi mạng, quá thời gian, LLM trả sai định dạng sau khi thử lại | Câu cố định |

## 3. Bất biến

1. Câu trả lời không chứa con số nào không có trong dữ liệu ca, kết quả tính của code, hoặc đoạn nguồn đã trích. LLM không tự tính.
2. Mỗi `trich_nguyen_van` là chuỗi con nguyên văn của đoạn nguồn tương ứng.
3. Câu hỏi và lịch sử đi qua cổng che định danh trước khi tới LLM; che lỗi thì trả `loi`, không gọi LLM.
4. Hỏi đáp không đổi kết luận, mức độ của bất kỳ nhận định nào và không ghi gì ngoài nhật ký hội thoại.

## 4. Bổ sung cho `GET /api/cases` (17/11, sau khi review T23)

Mỗi dòng của danh sách (`DongHangDoi`) thêm bốn trường, đều có mặc định để bản cũ không vỡ:

| Trường | Kiểu | Ghi chú |
| :--- | :--- | :--- |
| `ma_y_lenh` | chuỗi hoặc `null` | Ví dụ `YL-DEMO-02` |
| `thoi_diem_ke` | chuỗi ISO 8601 hoặc `null` | Thời điểm kê y lệnh |
| `nguoi_benh_tom_tat` | chuỗi hoặc `null` | Chỉ giới và tuổi, ví dụ `Nữ, 75 tuổi`. Không có họ tên |
| `thuoc` | danh sách chuỗi (mặc định rỗng) | Tên thuốc kèm hàm lượng của từng dòng y lệnh, theo thứ tự kê |

## 5. v1.10 – tiến trình hỏi đáp

Bổ sung cặp điểm cuối đọc-chỉ `GET /api/cases/{ca_id}/ask/tien-trinh` và `GET /api/ask/tien-trinh` trả `TienTrinhHoiDap` (`dang_chay`, `cac_buoc`, `da_chay_ms`) gắn theo chính người gọi trong lúc `POST` đang xử lý và giữ thêm 60 giây sau khi xong. Chi tiết hợp đồng và quy tắc bảo mật xem tại [plan 1.10 mục 10](plan-1.10-tien-trinh-ai-ui.md#10-mở-rộng-tiến-trình-trong-khung-chat-hỏi-đáp-21112026-người-dùng-chọn-làm-đủ).
