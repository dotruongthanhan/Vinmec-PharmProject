# Hợp đồng API v1.9 – Giới hạn bảo mật: kích thước, tốc độ, hàng đợi AI, lịch sử hỏi đáp

Ngày 20/11/2026. Bổ sung cho `api-hop-dong-v1.md` … `v1.8`. Nguồn: đợt sửa bảo mật T88, T89, T91 (`docs/bao-cao-bao-mat-2026-11-20.md` mục C4, T1, T6, L5, L6). Không thêm hay xoá điểm cuối; chỉ thêm ràng buộc và mã lỗi.

Thân lỗi vẫn là `{ "loi": { "ma": string, "thong_bao": string } }`.

## 1. Kiểm tra trước khi đọc thân yêu cầu (T89)

Áp cho mọi `/api/*` trừ `GET /api/health` và `OPTIONS` (preflight CORS), chạy **trước** định tuyến:

| Điều kiện | Mã HTTP | `ma` |
| :-- | :-- | :-- |
| `Content-Length` > 262.144 byte, hoặc thân chunked vượt 262.144 byte | 413 | `than_qua_lon` |
| `Content-Length` sai định dạng hoặc nhiều giá trị khác nhau | 400 | `du_lieu_khong_hop_le` |
| `AUTH_MODE` bắt buộc mà thiếu đúng một tiêu đề `Authorization: Bearer <token>` | 401 | `chua_dang_nhap` |

Hệ quả cho web: yêu cầu chưa đăng nhập luôn nhận 401 (trước đây có thể nhận 422 khi thân hỏng). Caddy cũng chặn `request_body` 256 KB cho `/api/*`.

## 2. Giới hạn trường (T88) – vi phạm trả 422 `du_lieu_khong_hop_le`

| Trường | Giới hạn |
| :-- | :-- |
| `GuiCauHoi.cau_hoi` | 1–1.000 ký tự (đã có từ v1.2) |
| `GuiCauHoi.lich_su` | tối đa 6 phần tử; **bị máy chủ bỏ qua** từ T91 (mục 4) |
| `ChatMessage.noi_dung` | tối đa 4.000 ký tự |
| `GuiCauHoi.nhan_dinh_id`, `GuiPhanHoi.nhan_dinh_id` | tối đa 128 ký tự |
| `GuiPhanHoi.nhom_ly_do` | tối đa 64 ký tự (vẫn phải thuộc danh mục nhóm lý do) |
| `GuiPhanHoi.ly_do` | tối đa 1.000 ký tự |
| `TinhCongThucYeuCau.dau_vao` | tối đa 30 khoá; tên khoá ≤ 64 ký tự; giá trị chuỗi ≤ 200 ký tự |

## 3. Giới hạn tốc độ, ngân sách ngày, hàng đợi AI (T88) – 429 kèm `Retry-After`

Mọi 429 có tiêu đề `Retry-After: <số giây nguyên dương>`.

| `ma` | Khi nào | Mặc định (biến môi trường) |
| :-- | :-- | :-- |
| `vuot_gioi_han` | Một người dùng gọi LLM quá nhiều: `POST /api/ask` và `POST /api/cases/{ca_id}/ask` | 20 lượt / 5 phút (`LLM_ASK_PER_5MIN`) |
| `vuot_gioi_han` | `POST /api/cases/{ca_id}/ai` khi **thực sự nộp** việc AI mới | 15 lượt / giờ (`LLM_AI_PER_HOUR`) |
| `het_ngan_sach_ngay` | Tổng lượt LLM toàn hệ thống trong ngày (giờ Việt Nam); `Retry-After` = số giây tới 00:00 | 600 lượt (`LLM_DAILY_CALLS`) |
| `hang_doi_day` | Hàng đợi AI nền đã có 6 việc chưa xong; `Retry-After: 30` | 6 việc |

Hành vi kèm theo:

- `POST /api/cases/{ca_id}/ai` với `chay_lai: true` khi ca **đang chạy** trả trạng thái hiện có, không nộp thêm, không tính lượt. Chỉ chạy lại khi lần trước đã `xong` hoặc `loi`.
- Khi AI tắt, câu trả lời "chưa sẵn sàng" không tính lượt.
- Bộ đếm nằm trong RAM của một tiến trình API; chạy nhiều worker thì hạn mức nhân theo số worker.

Web hiển thị thông báo thân thiện kèm số giây chờ khi nhận 429.

## 4. Lịch sử hỏi đáp do máy chủ dựng (T91)

- Máy chủ tự lấy tối đa **3 lượt gần nhất của chính người gọi** trong cùng phạm vi (`ca_id` hoặc `__global__`) từ `nghiep_vu.hoi_thoai` (hoặc tệp khi chạy cục bộ), mỗi tin cắt 4.000 ký tự. Lượt đã xoá bằng `POST /api/conversations/{ca_id}/clear` không còn trong lịch sử.
- Trường `lich_su` trong thân yêu cầu **vẫn được nhận** (để trình duyệt cũ không bị 422) nhưng **bị bỏ qua**. Web từ T91 không gửi trường này nữa.

## 5. Đoạn nguồn hỏi đáp chung tách theo người dùng (T88, L5)

`GET /api/cases/__global__/sources/{doan_trich_id}` chỉ trả đoạn nguồn thuộc câu trả lời `POST /api/ask` của **chính người gọi**; người khác nhận 404. Mỗi phạm vi giữ tối đa 200 đoạn gần nhất.
