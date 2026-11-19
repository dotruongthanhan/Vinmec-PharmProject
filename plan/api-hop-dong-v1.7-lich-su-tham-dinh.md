# Hợp đồng API v1.7 – Lịch sử thẩm định hệ thống (chỉ đọc)

- Khi `CASE_SOURCE=db`, mỗi lần hệ thống chạy luật thật cho một ca ở `GET /api/cases/{ca_id}` (không phải lần đọc lại từ bộ đệm), hệ thống ghi một bản ghi vào `nghiep_vu.ket_qua_tham_dinh` và danh sách nhận định vào `nghiep_vu.ket_qua_nhan_dinh` (tách biệt với các bảng đáp án mẫu `lan_tham_dinh`/`nhan_dinh`). Lỗi ghi được ghi nhật ký cảnh báo và không làm gián đoạn phản hồi API.
- Khi `CASE_SOURCE=file`, không ghi DB và lịch sử trả danh sách rỗng.

```ts
interface KetLuanCounts {
  dat: number;
  can_xem: number;
  khong_du_du_lieu: number;
  ngoai_hdsd: number;
}

interface TomTatThamDinh {
  tong_nhan_dinh: number;
  dem: { nghiem_trong: number; can_luu_y: number; thieu_du_lieu: number; ngoai_hdsd: number; dat: number };
  theo_ket_luan: KetLuanCounts;
  theo_yeu_to: Record<string, number>;
}

interface LanThamDinhLichSu {
  ket_qua_id: string;
  ca_id: string;
  thoi_diem: string;           // ISO 8601 có múi giờ (+07:00)
  thoi_diem_text: string;      // dd/mm/yyyy HH:MM
  phien_ban_luat: string;      // SHA-256 bộ bảng luật đã dùng
  so_luat_da_chay: number;
  che_do: "file" | "db";       // nguồn bảng luật đã dùng
  tom_tat: TomTatThamDinh;
}

interface LichSuThamDinh {
  ca_id: string;
  lich_su: LanThamDinhLichSu[]; // mới nhất đứng đầu
}
```

| Phương thức | Đường dẫn | Trả về | Ghi chú |
| :--- | :--- | :--- | :--- |
| GET | `/api/cases/{ca_id}/lich-su-tham-dinh` | `LichSuThamDinh` | 404 nếu không có ca. `Cache-Control: private, no-store` |
