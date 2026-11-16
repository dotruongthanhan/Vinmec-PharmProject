# Hợp đồng API v1 – giữa backend (FastAPI) và web (React)

**Ngày:** 16/11/2026 · Nguồn sự thật duy nhất cho T19 (backend) và T20 (web). Hai bên code theo đúng tên trường và kiểu ở đây. Muốn đổi thì sửa file này trước.

## 1. Quy ước chung

- Gốc: `/api`. JSON, UTF-8. Thời điểm là chuỗi ISO 8601 có múi giờ.
- **Backend chuẩn bị sẵn chuỗi hiển thị** (nhãn tiếng Việt, số đã định dạng dấu phẩy thập phân, thời điểm dạng `dd/mm/yyyy HH:MM`). Web không tự dịch mã nội bộ, không tự làm tròn số. Trường tên `*_text` hoặc `nhan*` là chuỗi để hiện nguyên văn; trường tên `*_ma` là mã để web chọn kiểu hiển thị (màu, biểu tượng).
- Mọi chuỗi đến từ dữ liệu ca là **văn bản thuần**. Web hiển thị bằng nút văn bản của React (không `dangerouslySetInnerHTML`, không diễn giải markdown, không biến thành liên kết).
- Lỗi: mã HTTP phù hợp + thân `{"loi": {"ma": string, "thong_bao": string}}`. Mã: `khong_tim_thay` (404), `du_lieu_khong_hop_le` (422), `loi_he_thong` (500).
- Chỉ có **một** điểm ghi: phản hồi của dược sĩ. Không có điểm nào ghi y lệnh, sửa ca, gửi tin.

## 2. Kiểu dữ liệu (viết theo TypeScript)

```ts
type MucDoMa = "nghiem_trong" | "can_luu_y" | null;
type KetLuanMa = "dat" | "can_xem" | "khong_du_du_lieu" | "ngoai_hdsd";
type DiUngMa = "co_di_ung" | "khong_di_ung_da_hoi" | "chua_co_thong_tin";
type LoaiCanCuMa = "du_lieu" | "tinh_toan" | "tai_lieu";
type PhanHoiMa = "dong_y" | "bac_bo" | "can_sua";

interface CheDo {               // hệ thống đang chạy ở chế độ nào
  co_llm: boolean;              // hôm nay: false
  truy_xuat: "chua_co" | "tu_khoa" | "lai";   // hôm nay: "chua_co"
  hoi_them: boolean;            // hôm nay: false
  thong_bao: string[];          // các dải thông báo trạng thái, ví dụ "Đang chạy không có bước AI: …"
}

interface DongHangDoi {
  ca_id: string; khoa: string; mo_ta: string;
  uu_tien: 0 | 1 | 2 | 3 | 4;   // 0 cao nhất
  huy_hieu: string;             // "⛔ 1 nghiêm trọng"
  so_nghiem_trong: number; so_can_luu_y: number; so_thieu_du_lieu: number;
  da_phan_hoi_het: boolean;     // mọi nhận định cần chú ý của ca đã có phản hồi
}

interface DanhSachCa { cases: DongHangDoi[]; loi_nap: { tep: string; loi: string }[]; che_do: CheDo; }

interface DinhDanhCa {
  ca_id: string; gioi_tuoi: string; can_nang: string; khoa_loai: string;
  crcl: string; crcl_bat_thuong: boolean;
  di_ung_ma: DiUngMa; di_ung_text: string;
  dem: { nghiem_trong: number; can_luu_y: number; thieu_du_lieu: number; ngoai_hdsd: number; dat: number };
}

interface TomTat {
  chan_doan: { loai_nhan: string; noi_dung: string; ma_icd10: string | null }[];   // chính đứng trước
  co_dia: string[];
  vao_vien_text: string;
  nam_vien_text: string | null;               // "3 ngày (tính tới lúc kê y lệnh)"
  dien_bien_moi_nhat: { thoi_diem_text: string; loai_nhan: string; noi_dung: string } | null;
  bat_thuong: { ten: string; gia_tri_text: string; don_vi: string; huong: "▲" | "▼"; thoi_diem_text: string; so_voi_truoc: string | null }[];
  bat_thuong_ghi_chu: string | null;          // "Không có xét nghiệm ngoài ngưỡng." | "Chưa đánh giá được: N kết quả không có khoảng tham chiếu." | …
}

interface ChiSo {
  cong_thuc: string; nhan: string; don_vi: string;
  gia_tri_text: string;                       // "16,0" hoặc "—"
  thieu: string[];                            // nhãn các đầu vào thiếu
  dau_vao: { nhan: string; gia_tri_text: string; don_vi: string; ban_ghi_id: string | null; thoi_diem_text: string | null }[];
  ghi_chu: string[]; tham_khao: string;
}

interface CanCu {
  so: number; loai_ma: LoaiCanCuMa; loai_nhan: string; mo_ta: string;
  ban_ghi_id: string | null;
  mo_duoc: boolean;                           // true: web gọi GET …/records/{ban_ghi_id} (du_lieu) hoặc mở ChiSo tương ứng (tinh_toan)
  cong_thuc: string | null;                   // với tinh_toan: khoá để tìm ChiSo
  ghi_chu: string | null;                     // với tai_lieu hôm nay: "Nguyên văn đoạn nguồn sẽ có khi nối kho tri thức."
}

interface PhanHoiDaGhi { phan_hoi: PhanHoiMa; phan_hoi_nhan: string; nhom_ly_do: string | null; ly_do: string | null; thoi_diem_text: string; }

interface NhanDinh {
  nhan_dinh_id: string;                       // ổn định trong một ca: ma_luat + "|" + các chi_tiet_y_lenh_id đã sắp xếp, nối bằng ","
  thuoc: string; yeu_to: string;              // "6. Cơ địa và xét nghiệm"
  nhan_xet: string;
  ket_luan_ma: KetLuanMa; ket_luan_nhan: string;
  muc_do_ma: MucDoMa; muc_do_nhan: string | null;
  nguon_goc_ma: "luat" | "ai_da_kiem_chung" | "ai_chua_kiem_chung"; nguon_goc_nhan: string;   // hôm nay luôn "luat" / "Luật"
  ma_luat: string; chi_tiet_y_lenh_id: string[];
  thong_tin_con_thieu: string[];
  can_cu: CanCu[];
  phan_hoi: PhanHoiDaGhi | null;
}

interface BangYLenh { cot: string[]; dong: Record<string, string>[]; }

interface ChiTietCa {
  ca_id: string;
  dinh_danh: DinhDanhCa;
  tom_tat: TomTat;
  chi_so: ChiSo[];                            // đúng 4, thứ tự CrCl, eGFR, BMI, BSA
  nhan_dinh: { can_chu_y: NhanDinh[]; dat: NhanDinh[]; yeu_to_chua_kiem: string[]; so_luat_da_chay: number };
  chi_tiet: {
    y_lenh: { thong_tin_text: string; cho_duyet: BangYLenh; dang_dung: BangYLenh | null };
    xet_nghiem: { thoi_diem_text: string; ten: string; gia_tri_text: string; don_vi: string; khoang_tham_chieu: string; ngoai_nguong: boolean; huong: "▲" | "▼" | null }[];
    vi_sinh: { benh_pham: string; lay_mau_text: string; vi_khuan: string; khang_sinh_do: { hoat_chat: string; ket_qua: string; mic_text: string; dang_ke: boolean }[] }[];
    dien_bien: { thoi_diem_text: string; loai_nhan: string; noi_dung: string }[];   // mới nhất trước
  };
  cau_hoi_goi_y: string[];
  nhom_ly_do: string[];                       // 5 lý do cho "Bác bỏ" / "Cần sửa"
  thoi_gian_ms: number;
  che_do: CheDo;
}

interface BanGhi { loai: string; tieu_de: string; dong: [string, string][]; }

interface GuiPhanHoi { nhan_dinh_id: string; phan_hoi: PhanHoiMa; nhom_ly_do?: string | null; ly_do?: string | null; }

interface GuiCauHoi { cau_hoi: string; lich_su: { vai: "nguoi_dung" | "he_thong"; noi_dung: string }[]; }
interface TraLoi {
  trang_thai: "chua_san_sang" | "ok" | "khong_co_nguon" | "ngoai_pham_vi" | "loi";
  noi_dung: string;
  trich_dan: { so: number; loai_ma: LoaiCanCuMa; nhan: string; ban_ghi_id: string | null }[];
  cong_cu_da_goi: string[];
}
```

## 3. Điểm cuối

| Phương thức | Đường dẫn | Trả về | Ghi chú |
| :--- | :--- | :--- | :--- |
| GET | `/api/health` | `{ "ok": true, "che_do": CheDo }` | |
| GET | `/api/cases` | `DanhSachCa` | Sắp theo `uu_tien` tăng dần, rồi thời điểm kê tăng dần |
| GET | `/api/cases/{ca_id}` | `ChiTietCa` | 404 nếu không có ca |
| GET | `/api/cases/{ca_id}/records/{ban_ghi_id}` | `BanGhi` | Chỉ tìm trong ca đó; 404 nếu không thấy |
| POST | `/api/cases/{ca_id}/feedback` | `PhanHoiDaGhi` | Thân `GuiPhanHoi`. `bac_bo` / `can_sua` thiếu `nhom_ly_do` → 422. `nhan_dinh_id` không thuộc ca → 404. `nhom_ly_do` ngoài danh sách → 422 |
| POST | `/api/cases/{ca_id}/ask` | `TraLoi` | Thân `GuiCauHoi`. Hôm nay luôn `trang_thai: "chua_san_sang"` |

## 4. Chạy

- Backend: `uv run uvicorn app.api.main:app --port 8000`.
- Web khi phát triển: `npm run dev` trong `web/` (cổng 5173), Vite chuyển tiếp `/api` sang `http://localhost:8000`.
- Bản đóng gói: `npm run build` sinh `web/dist`; backend phục vụ `web/dist` ở `/` khi thư mục đó tồn tại, nên demo chỉ cần một tiến trình ở cổng 8000.
