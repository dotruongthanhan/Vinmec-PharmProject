# Sơ đồ Thực thể Liên kết (ERD) – Hệ thống AI CDSS Thẩm định Y lệnh

![Sơ đồ ERD Hệ thống AI CDSS](./erd.svg)

> **Ghi chú kiến trúc:**
> - **Phi xâm lấn (Read-Only Shadow Schema):** Các bảng nguồn đồng bộ từ `OH` / `EMR` (`NGUOI_BENH`, `DOT_DIEU_TRI`, `Y_LENH`, `CHI_TIET_Y_LENH`, dữ liệu bệnh án) sử dụng `source_system`, `source_record_id`, `last_synced_at` để ánh xạ 1 chiều, không ghi đè vào cơ sở dữ liệu lõi của bệnh viện.
> - **Chuẩn hóa bảng trung gian:** Tách cấp đơn `Y_LENH` và dòng thuốc `CHI_TIET_Y_LENH`; tách `THUOC` – `THUOC_HOAT_CHAT` – `HOAT_CHAT` để bắt trùng lặp/cộng dồn liều trên thuốc phối hợp; bổ sung `NHAN_DINH_THUOC` để trỏ cảnh báo tới đúng cặp/dòng thuốc liên quan.

## Mã Mermaid tham chiếu

```mermaid
erDiagram
    NGUOI_BENH ||--o{ DI_UNG : co
    NGUOI_BENH ||--o{ DOT_DIEU_TRI : co
    DOT_DIEU_TRI ||--o{ CHAN_DOAN : ghi_nhan
    DOT_DIEU_TRI ||--o{ SINH_HIEU : co
    DOT_DIEU_TRI ||--o{ KET_QUA_XET_NGHIEM : co
    DOT_DIEU_TRI ||--o{ DIEN_BIEN : co
    DOT_DIEU_TRI ||--o{ Y_LENH : gom
    Y_LENH ||--|{ CHI_TIET_Y_LENH : gom_thuoc
    THUOC ||--o{ CHI_TIET_Y_LENH : duoc_ke
    THUOC ||--|{ THUOC_HOAT_CHAT : chua
    HOAT_CHAT ||--o{ THUOC_HOAT_CHAT : thuoc_ve
    Y_LENH ||--o{ LAN_THAM_DINH : duoc_tham_dinh
    DUOC_SI ||--o{ LAN_THAM_DINH : thuc_hien
    LAN_THAM_DINH ||--o{ NHAN_DINH : gom
    NHAN_DINH ||--o{ NHAN_DINH_THUOC : gan_voi
    CHI_TIET_Y_LENH ||--o{ NHAN_DINH_THUOC : bi_canh_bao
    NHAN_DINH ||--o{ CAN_CU : tham_chieu

    NGUOI_BENH {
        string nguoi_benh_id PK
        string pid_hash "Mã định danh ẩn danh map với OH/EMR"
        date ngay_sinh
        string gioi_tinh
        string source_system
        string source_record_id
        datetime last_synced_at
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
    DOT_DIEU_TRI {
        string dot_dieu_tri_id PK
        string nguoi_benh_id FK
        string khoa_dieu_tri
        string loai_dieu_tri "Nội trú hoặc Ngoại trú"
        string co_dia_dac_biet "Mang thai, cho con bú, suy gan, suy thận..."
        string chi_so_lam_sang "CrCl, eGFR, BSA... dạng string"
        datetime thoi_diem_bat_dau
        datetime thoi_diem_ket_thuc
        string trang_thai_dot "Đang điều trị hoặc Đã kết thúc"
        string source_system
        string source_record_id
        datetime last_synced_at
    }
    CHAN_DOAN {
        string chan_doan_id PK
        string dot_dieu_tri_id FK
        string ma_icd10
        string noi_dung
        string loai "Chẩn đoán chính hoặc Bệnh kèm"
        string chuyen_khoa
        datetime thoi_diem_ghi
    }
    SINH_HIEU {
        string sinh_hieu_id PK
        string dot_dieu_tri_id FK
        string loai "Cân nặng, chiều cao, huyết áp, SpO2..."
        decimal gia_tri
        string don_vi
        datetime thoi_diem_do
    }
    KET_QUA_XET_NGHIEM {
        string xet_nghiem_id PK
        string dot_dieu_tri_id FK
        string nhom_xet_nghiem "Gan-Thận, Vi sinh, Huyết học..."
        string ten_xet_nghiem
        string gia_tri
        string don_vi
        string khoang_tham_chieu
        string muc_canh_bao "Bình thường, Vàng, Đỏ"
        string ghi_chu "Bệnh phẩm, vi khuẩn, kháng sinh đồ S/I/R nếu có"
        datetime thoi_diem_ket_qua
        string nguon
    }
    DIEN_BIEN {
        string dien_bien_id PK
        string dot_dieu_tri_id FK
        string loai_ho_so "Phiếu khám, Phiếu điều trị, CĐHA, Bệnh án..."
        string chuyen_khoa
        string noi_dung
        boolean co_noi_dung "False nếu là phiếu khám rỗng"
        datetime thoi_diem_ghi
        string nguon
    }
    Y_LENH {
        string y_lenh_id PK
        string dot_dieu_tri_id FK
        string khoa_ke_don
        string luong_duyet "Duyệt trực tiếp hoặc Hậu kiểm"
        string muc_uu_tien "Đỏ, Vàng, Xanh lá, Xanh dương"
        string trang_thai "Trạng thái trên hệ thống nguồn OH"
        datetime thoi_diem_ke
        string source_system
        string source_record_id
        datetime last_synced_at
    }
    CHI_TIET_Y_LENH {
        string chi_tiet_y_lenh_id PK
        string y_lenh_id FK
        string thuoc_id FK
        decimal lieu_moi_lan
        string don_vi_lieu
        string tan_suat
        decimal tong_lieu_ngay
        string duong_dung
        string cach_dung
        string khung_gio_dung "Mốc giờ dùng thuốc trong ngày nếu có"
        datetime bat_dau
        datetime ket_thuc
        string nguon_thuoc "Kho nội trú, Tủ trực, Nhà thuốc, Tự mua/TPCN"
        boolean is_discontinued
        datetime thoi_diem_ngung
        string source_record_id
    }
    THUOC {
        string thuoc_id PK
        string ma_thuoc
        string ten_thuoc
        string ham_luong
        string don_vi
        string nhom_atc
        string dang_bao_che
        boolean la_thuoc_nguy_co_cao
        boolean la_khang_sinh
    }
    THUOC_HOAT_CHAT {
        string thuoc_hoat_chat_id PK
        string thuoc_id FK
        string hoat_chat_id FK
        decimal ham_luong_thanh_phan
        string don_vi
    }
    HOAT_CHAT {
        string hoat_chat_id PK
        string ten_hoat_chat
        string ma_atc
        string nhom_duoc_ly
    }
    DUOC_SI {
        string duoc_si_id PK
        string ten_hien_thi
    }
    LAN_THAM_DINH {
        string tham_dinh_id PK
        string y_lenh_id FK
        string duoc_si_id FK "Nullable khi chưa phân công DSLS"
        string loai_tham_dinh "Duyệt trực tiếp hoặc Hậu kiểm"
        datetime thoi_diem_tao
        datetime thoi_diem_hoan_tat
        string trang_thai "Chờ duyệt, Hoàn tất, Cần làm rõ"
        string quyet_dinh "Approved, Hold, Cancelled do DSLS chốt"
        string ket_qua_ai_tong_hop
        string ghi_chu
    }
    NHAN_DINH {
        string nhan_dinh_id PK
        string tham_dinh_id FK
        string yeu_to_kiem_tra "1 đến 7 theo Ma trận 7 yếu tố"
        string noi_dung
        string muc_do "Đỏ, Vàng, Xanh"
        string thong_tin_con_thieu
        string nguon_nhan_dinh "Hệ thống hoặc Dược sĩ"
        string trang_thai_phan_hoi_dsls "Đồng ý, Bác bỏ, Cần sửa"
        string ly_do_phan_hoi
    }
    NHAN_DINH_THUOC {
        string nhan_dinh_thuoc_id PK
        string nhan_dinh_id FK
        string chi_tiet_y_lenh_id FK
        string vai_tro "Thuốc chính hoặc Thuốc tương tác"
    }
    CAN_CU {
        string can_cu_id PK
        string nhan_dinh_id FK
        string loai_can_cu "Dữ liệu bệnh nhân EMR/OH hoặc Tài liệu chuyên môn"
        string ten_tai_lieu_hoac_du_lieu
        string vi_tri_trich_dan
        string duong_dan_hoac_ma
        string phien_ban_hoac_ngay
    }
```
