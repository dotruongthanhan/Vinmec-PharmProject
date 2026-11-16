# Sơ đồ hệ thống hỗ trợ thẩm định y lệnh

**Phạm vi:** Bản đề xuất cho bài toán hỗ trợ dược sĩ lâm sàng tổng hợp thông tin và thẩm định y lệnh nội trú, có thể xem xét mở rộng cho đơn ngoại trú phức tạp. Căn cứ: ghi chép khảo sát, báo cáo tuần 2 và đề xuất dự án trong kho. Đây là thiết kế dự kiến, không khẳng định bệnh viện đã có kết nối hay cơ sở dữ liệu như dưới đây. Cách lấy dữ liệu, phạm vi sử dụng và quyền ghi kết quả cần bệnh viện xác nhận.

## 1. Quy trình vận hành dành cho dược sĩ

```mermaid
flowchart TD
    A["Bác sĩ kê y lệnh thuốc"] --> B["Dược sĩ mở danh sách y lệnh cần thẩm định"]
    B --> C["Chọn y lệnh và người bệnh"]
    C --> D["Hệ thống tập hợp y lệnh, bệnh án, thuốc đang dùng, dị ứng, xét nghiệm và diễn biến"]
    D --> E{"Thông tin cần thiết<br/>đã đủ và còn phù hợp?"}
    E -- "Chưa đủ hoặc chưa rõ" --> F["Hiển thị thông tin thiếu hoặc cần kiểm tra; dược sĩ bổ sung, tra cứu hoặc liên hệ bộ phận liên quan"]
    F --> G{"Đã đủ thông tin<br/>để tiếp tục?"}
    G -- "Chưa" --> H["Ghi nhận cần bổ sung và chờ; dược sĩ xử lý theo quy trình bệnh viện"]
    H --> C
    G -- "Đã đủ" --> I
    E -- "Đã đủ" --> I["Hiển thị tóm tắt bệnh án, thuốc và các xét nghiệm liên quan"]
    I --> J["Hỗ trợ tính chỉ số khi có đủ dữ liệu và rà soát các yếu tố an toàn dùng thuốc"]
    J --> K["Hiển thị bảng nhận định: thuốc, nội dung kiểm tra, nhận xét; kèm căn cứ, nguồn và thông tin còn thiếu"]
    K --> L["Dược sĩ đọc kết quả, kiểm tra bệnh án và tài liệu gốc, đánh giá theo chuyên môn"]
    L --> M{"Cần làm rõ hoặc<br/>điều chỉnh y lệnh?"}
    M -- "Có" --> N["Dược sĩ trao đổi với bác sĩ và các bộ phận liên quan; ghi nhận kết quả trao đổi"]
    N --> O{"Cần cập nhật<br/>y lệnh hoặc thông tin?"}
    O -- "Có" --> P["Bác sĩ cập nhật y lệnh hoặc bổ sung thông tin theo quy trình"]
    P --> C
    O -- "Không" --> Q["Dược sĩ đưa ra quyết định thẩm định theo quy trình bệnh viện"]
    M -- "Không" --> Q
    Q --> R["Ghi nhận kết quả thẩm định trên hệ thống được bệnh viện cho phép"]
    R --> S["Tiếp tục cấp phát, thực hiện thuốc hoặc theo dõi theo quy trình bệnh viện"]
```

Hệ thống dự kiến hỗ trợ rà soát dị ứng, trùng thuốc, chỉ định và liều / đường dùng, tương tác, độc tính, chẩn đoán và xét nghiệm, chống chỉ định; đồng thời kiểm tra lịch dùng khi có dữ liệu. Kết quả hỗ trợ có thể thiếu hoặc cần kiểm chứng. **Dược sĩ chịu trách nhiệm đánh giá và quyết định; hệ thống không tự phê duyệt, thay đổi y lệnh hay tự cấp phát.** Việc kết nối OH / EMR và cập nhật kết quả hiện chỉ là đề xuất; trước mắt có thể thử bằng dữ liệu giả lập.

## 2. Sơ đồ dữ liệu dự kiến

Sơ đồ dưới đây mô tả **mô hình dữ liệu đề xuất cho bản thử**, không phải cấu trúc thật của OH hay EMR. `PK` là khóa chính, `FK` là khóa liên kết. Các tên trường, quan hệ, nguồn và quyền truy cập cần đối chiếu với dữ liệu mẫu được phép sử dụng. Có thể không cần lưu bản sao mọi thông tin khi triển khai thực tế.

```mermaid
erDiagram
    NGUOI_BENH ||--o{ DOT_DIEU_TRI : co
    DOT_DIEU_TRI ||--o{ Y_LENH : gom
    DOT_DIEU_TRI ||--o{ CHAN_DOAN : ghi_nhan
    DOT_DIEU_TRI ||--o{ KET_QUA_XET_NGHIEM : co
    DOT_DIEU_TRI ||--o{ SINH_HIEU : co
    DOT_DIEU_TRI ||--o{ DIEN_BIEN : co
    NGUOI_BENH ||--o{ DI_UNG : co
    THUOC ||--o{ Y_LENH : duoc_ke
    Y_LENH ||--o{ LICH_DUNG : co
    Y_LENH ||--o{ LAN_THAM_DINH : duoc_tham_dinh
    DUOC_SI ||--o{ LAN_THAM_DINH : thuc_hien
    LAN_THAM_DINH ||--o{ NHAN_DINH : gom
    NHAN_DINH ||--o{ CAN_CU : tham_chieu

    NGUOI_BENH {
        string nguoi_benh_id PK "Mã giả lập"
        int tuoi "Tuổi"
        string gioi_tinh "Giới tính"
        string co_dia_dac_biet "Mang thai, cho con bú hoặc tình trạng khác"
    }
    DOT_DIEU_TRI {
        string dot_dieu_tri_id PK
        string nguoi_benh_id FK
        string khoa_dieu_tri
        string loai_dieu_tri "Nội trú hoặc ngoại trú"
        datetime thoi_diem_bat_dau
    }
    Y_LENH {
        string y_lenh_id PK
        string dot_dieu_tri_id FK
        string thuoc_id FK
        decimal lieu_moi_lan
        string don_vi_lieu
        string tan_suat
        string duong_dung
        string cach_dung
        datetime bat_dau
        datetime ket_thuc
        string nguon_thuoc
        string muc_uu_tien
        string trang_thai_nguon "Trạng thái trên hệ thống nguồn"
    }
    THUOC {
        string thuoc_id PK
        string ma_thuoc
        string ten_thuoc
        string hoat_chat
        string ham_luong
        string don_vi
    }
    LICH_DUNG {
        string lich_dung_id PK
        string y_lenh_id FK
        datetime thoi_diem_du_kien
        decimal lieu_du_kien
        string don_vi_lieu
    }
    CHAN_DOAN {
        string chan_doan_id PK
        string dot_dieu_tri_id FK
        string noi_dung
        string loai "Chẩn đoán chính hoặc bệnh kèm"
        datetime thoi_diem_ghi
    }
    DI_UNG {
        string di_ung_id PK
        string nguoi_benh_id FK
        string tac_nhan
        string phan_ung
        string muc_do
        datetime thoi_diem_ghi
        string nguon
    }
    KET_QUA_XET_NGHIEM {
        string xet_nghiem_id PK
        string dot_dieu_tri_id FK
        string ten_xet_nghiem
        string gia_tri "Số hoặc kết quả văn bản"
        string don_vi
        string khoang_tham_chieu
        datetime thoi_diem_ket_qua
        string nguon
    }
    SINH_HIEU {
        string sinh_hieu_id PK
        string dot_dieu_tri_id FK
        string loai "Cân nặng, chiều cao, huyết áp..."
        decimal gia_tri
        string don_vi
        datetime thoi_diem_do
    }
    DIEN_BIEN {
        string dien_bien_id PK
        string dot_dieu_tri_id FK
        string noi_dung
        datetime thoi_diem_ghi
        string nguon
    }
    DUOC_SI {
        string duoc_si_id PK
        string ten_hien_thi
    }
    LAN_THAM_DINH {
        string tham_dinh_id PK
        string y_lenh_id FK
        string duoc_si_id FK
        datetime thoi_diem
        string trang_thai "Chờ, hoàn tất hoặc cần làm rõ"
        string quyet_dinh "Kết quả do dược sĩ ghi nhận"
        string ghi_chu
    }
    NHAN_DINH {
        string nhan_dinh_id PK
        string tham_dinh_id FK
        string yeu_to_kiem_tra
        string noi_dung
        string muc_do
        string thong_tin_con_thieu
        string nguon_nhan_dinh "Hệ thống hoặc dược sĩ"
    }
    CAN_CU {
        string can_cu_id PK
        string nhan_dinh_id FK
        string ten_tai_lieu_hoac_du_lieu
        string vi_tri_trich_dan
        string phien_ban_hoac_ngay
    }
```

**Điểm cần xác nhận:** mã liên kết giữa OH và EMR; các trường thật, đơn vị và thời gian cập nhật; dữ liệu dị ứng, thuốc đang dùng và lịch dùng; cách lưu các chỉ số tính toán và trao đổi với bác sĩ; hình thức truy cập và ghi kết quả thẩm định. Một y lệnh có thể được thẩm định lại nhiều lần; bản ghi nhận định gắn với từng lần thẩm định để phân biệt kết quả.
