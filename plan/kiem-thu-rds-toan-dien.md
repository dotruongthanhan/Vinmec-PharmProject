# Kiểm thử toàn diện sau khi chuyển dữ liệu sang AWS RDS (19/11)

Mục tiêu: production chỉ cần code + `.env`; mọi dữ liệu (hồ sơ, y lệnh, dữ liệu plan 1.8) đọc / ghi trên Postgres RDS. Mỗi mục ghi **lệnh / cách kiểm** và **đạt khi**.

## A. Dữ liệu trên DB (sau khi xoá và nạp lại)

| # | Kiểm | Đạt khi |
|:-:|:--|:--|
| A1 | Lược đồ áp từ đầu trên DB trống | Không lỗi; không còn bảng cũ không dùng (`tri_thuc.hoat_chat` 58 dòng, `ten_thuoc`, `quy_tac_lieu_than` cũ, `tuong_tac_sang_loc`) hoặc ghi rõ lý do giữ |
| A2 | Hồ sơ, y lệnh, phiếu điều trị, hành chính | 66 ca; số dòng từng bảng `nghiep_vu` = số nạp được từ tệp, 0 dòng bị loại |
| A3 | D0 từ điển / bộ phân giải (`tra_cuu_*`) | Khớp 100% số dòng `tra_cuu.sqlite` |
| A4 | D1 DDInter (`ddinter_*`) | 291.876 / 1.971 / 805 |
| A5 | D2–D7 bảng luật (T77) | Mỗi tệp dựng lại từ DB == tệp gốc |
| A6 | Đoạn nguồn RAG | 3.730 đoạn, 3.730 có vector 2048 chiều |
| A7 | Đáp án mẫu (gold) | Tách khỏi kết quả hệ thống |

## B. App chạy chỉ bằng DB (giả lập máy khác)

Ẩn `data/kb/`, `data/kb_curated/`, `data/cache/`, `config/kb/`, `data/mock/`; `.env`: `CASE_SOURCE=db`, `KB_SOURCE=db`.

| # | Kiểm | Đạt khi |
|:-:|:--|:--|
| B1 | 66 ca qua API | 577 nhận định, khớp từng dòng bản đọc tệp; 0 `loi_luat` |
| B2 | Log khởi động | Không có "Không chạy yếu tố 4", không lỗi nạp bảng luật |
| B3 | Tương tác thuốc | HS-024 amiodaron × digoxin `nghiem_trong`; ma trận tương tác có dữ liệu |
| B4 | 7 yếu tố | Mỗi yếu tố có luật chạy; DEMO-02 meropenem CrCl; HS-019 paracetamol vượt liều; HS-042 INR không còn "thiếu đơn vị" |
| B5 | Chatbot theo ca + hỏi đáp chung | Trả lời có nguồn trích; log chỉ nhúng câu hỏi (không nhúng lại đoạn); không còn lỗi `:g` |
| B6 | Phản hồi dược sĩ, lịch sử hỏi đáp | Có dòng trong `nghiep_vu.phan_hoi`, `nghiep_vu.hoi_thoai`; khởi động lại backend vẫn thấy |
| B7 | Kết quả thẩm định (T78) | Mở ca → dòng mới `ket_qua_tham_dinh`, số `ket_qua_nhan_dinh` = số mục trên màn hình |

## C. Trình duyệt (web 5173 → backend 8000 → RDS)

Danh sách 67 y lệnh; mở DEMO-02, HS-024, HS-019, HS-042; hồ sơ bệnh án; ma trận tương tác; chatbot; gửi phản hồi; console không lỗi; log backend không 5xx.

## D. Hồ sơ giả mới

Nạp `TEST-CLAUDE-02` (cài sẵn lỗi biết trước) lên RDS → hiện trên web → thẩm định ra đúng lỗi cài → kết quả ghi DB.

## E. Lỗi đã gặp hôm nay (không được tái diễn)

- Nạp bảng cũ không ai đọc, sót dữ liệu plan 1.8 → A1, A3–A5.
- Kiểm trên máy có sẵn tệp nên không thấy thiếu → B (ẩn tệp).
- DDInter nạp cả bảng quá chậm / timeout → B2, B3.
- Lược đồ mới chưa áp lên DB `.env` đang trỏ → 503 → C.
- RAG không dùng vector DB → B5.
