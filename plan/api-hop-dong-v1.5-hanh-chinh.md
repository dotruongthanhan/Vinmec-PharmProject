# API v1.5 – Hành chính và quản lý người bệnh

Bổ sung tương thích vào v1/v1.1/v1.2; không xóa hay đổi ý nghĩa trường cũ.
`GET /api/cases` và `GET /api/cases/{ca_id}` giữ xác thực, trả
`Cache-Control: private, no-store`. Không có endpoint ghi hành chính.

## Chi tiết và danh sách

`dinh_danh_day_du` là thông tin người bệnh; `quan_ly_nguoi_benh` là đợt chứa
y lệnh trọng tâm; `lich_su_vao_vien` gồm mọi đợt của cùng người bệnh, kể cả đợt
không có ca trọng tâm. Sắp theo thứ tự và thời điểm vào. Mỗi đợt kèm các y lệnh,
thuốc hiển thị và ghi chép điều trị để mở tại bảng lịch sử, chưa chọn y lệnh
để thẩm định (T44). Phiếu ở đây lấy các ghi chép có loại Phiếu điều trị/Tờ điều trị.

Danh sách ca thêm `ho_ten`, `ngay_sinh`, `chan_doan_chinh`, `vao_vien`,
`so_y_lenh`. Chẩn đoán và vào viện lấy từ ca lâm sàng ngay cả ở chế độ file.
Trong chế độ file: định danh đầy đủ/quản lý là null, lịch sử là [], họ tên/ngày
sinh/số y lệnh là null. Client cũ và mock cũ vẫn hoạt động; trường thiếu hiển
thị “Chưa ghi nhận”. Không thay số đo lâm sàng thiếu bằng số mặc định.

Ngày sinh/hạn BHYT là YYYY-MM-DD; timestamp ISO 8601 có múi giờ.
`dia_chi_text` nối các phần địa chỉ có giá trị theo thứ tự số nhà → tỉnh/thành.
Họ tên viết hoa ở giao diện. Các chuỗi và giá trị số có thể null.

```ts
interface DongHangDoi {
  ho_ten?: string | null;
  ngay_sinh?: string | null;
  chan_doan_chinh?: string | null;
  vao_vien?: string | null;
  so_y_lenh?: number | null;
}
interface ChiTietCa {
  dinh_danh_day_du?: FullIdentity | null;
  quan_ly_nguoi_benh?: PatientManagement | null;
  lich_su_vao_vien?: EncounterHistory[];
}
interface Address {
  so_nha: string | null;
  thon_pho: string | null;
  xa_phuong: string | null;
  huyen: string | null;
  tinh_thanh: string | null;
}
interface Insurance {
  so_the: string | null;
  gia_tri_den: string | null;
}
interface Contact {
  ho_ten: string | null;
  quan_he: string | null;
  dien_thoai: string | null;
}
interface Parent {
  ho_ten: string | null;
  nghe_nghiep: string | null;
}
interface Parents {
  bo: Parent | null;
  me: Parent | null;
}
interface FullIdentity {
  ho_ten: string | null;
  ngay_sinh: string | null;
  tuoi: number | null;
  gioi_tinh: 'nam' | 'nu' | null;
  chieu_cao_cm: number | null;
  can_nang_kg: number | null;
  dan_toc: string | null;
  ngoai_kieu: string | null;
  nghe_nghiep: string | null;
  dia_chi: Address | null;
  dia_chi_text: string | null;
  doi_tuong: 'bhyt' | 'thu_phi' | 'mien' | 'khac' | null;
  bhyt: Insurance | null;
  nguoi_bao_tin: Contact | null;
  bo_me: Parents | null;
  nhom_mau: string | null;
}
interface Discharge {
  hinh_thuc: 'ra_vien' | 'xin_ve' | 'bo_ve' | 'dua_ve' | 'chuyen_vien';
  chuyen_vien_den: string | null;
  ly_do: string | null;
}
interface DepartmentStay {
  khoa: string;
  tu: string | null;
  den: string | null;
}
interface PatientManagement {
  dot_dieu_tri_id: string;
  khoa_dieu_tri: string | null;
  thoi_diem_bat_dau: string | null;
  thoi_diem_ket_thuc: string | null;
  hinh_thuc_vao: string | null;
  so_ngay_dieu_tri: number | null;
  lich_su_khoa: DepartmentStay[];
  noi_gioi_thieu: 'co_quan_y_te' | 'tu_den' | 'khac' | null;
  tuyen_chuyen_den: string | null;
  vao_khoa_luc: string | null;
  so_giuong: string | null;
  so_luu_tru: string | null;
  ma_yt: string | null;
  ra_vien: Discharge | null;
  bac_si_dieu_tri: string | null;
}
interface EncounterOrder {
  y_lenh_id: string;
  thoi_diem_ke: string | null;
  trang_thai: string | null;
  thuoc: string[];
}
interface EncounterNote {
  thoi_diem_ghi: string | null;
  loai_ho_so: string | null;
  noi_dung: string;
}
// Khai báo phẳng, có toàn bộ trường PatientManagement để dễ kiểm hợp đồng.
interface EncounterHistory {
  dot_dieu_tri_id: string;
  khoa_dieu_tri: string | null;
  thoi_diem_bat_dau: string | null;
  thoi_diem_ket_thuc: string | null;
  hinh_thuc_vao: string | null;
  so_ngay_dieu_tri: number | null;
  lich_su_khoa: DepartmentStay[];
  noi_gioi_thieu: 'co_quan_y_te' | 'tu_den' | 'khac' | null;
  tuyen_chuyen_den: string | null;
  vao_khoa_luc: string | null;
  so_giuong: string | null;
  so_luu_tru: string | null;
  ma_yt: string | null;
  ra_vien: Discharge | null;
  bac_si_dieu_tri: string | null;
  thu_tu: number | null;
  chan_doan_chinh: string | null;
  y_lenh: EncounterOrder[];
  phieu_dieu_tri: EncounterNote[];
}
// Đối tượng nội bộ của đường đọc giao diện, không dùng làm đầu vào AI.
interface AdministrativeRecord {
  dinh_danh_day_du: FullIdentity;
  lich_su_vao_vien: EncounterHistory[];
}
```

## Ranh giới dữ liệu

Đọc DB qua `app/db/administrative.py` trong giao dịch REPEATABLE READ chỉ đọc,
truy vấn tham số hóa theo tập mã người bệnh lấy từ ca hợp lệ. Không cache kết
quả hành chính trong CaseService, DbReviewService, kết quả thẩm định hay tác vụ AI.
Không có ho_ten/ngay_sinh/dia_chi/dien_thoai trong mô hình CaBenh, prompt hay log.
Lỗi DB trả thông báo cố định, không phản chiếu hàng dữ liệu hoặc ngoại lệ gốc.
Nhật ký truy cập chỉ ghi metadata có sẵn, không ghi nội dung phản hồi.

Toàn bộ dữ liệu bổ sung là giả lập theo T45. Bố mẹ chỉ có ở người bệnh dưới 16
tuổi; cân nặng giữ đúng số đo nguồn, thiếu giữ null. Không được dùng để quyết
định lâm sàng hay đưa dữ liệu hành chính vào pipeline AI.
