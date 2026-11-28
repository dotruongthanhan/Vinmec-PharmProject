# API v1.4 – Y lệnh trong hồ sơ và phiếu điều trị (T44)

Bổ sung tương thích trên v1/v1.1/v1.2 và phần hành chính T45 (v1.5).
T46 bỏ hai trường nội bộ `nguon_tep` và `nap_luc` khỏi mọi phản hồi API.

## Làm mới danh sách ca

Khi `CASE_SOURCE=db`, `GET /api/cases` có thêm `lam_moi_luc`, thời điểm nạp
danh sách gần nhất theo ISO 8601 với múi giờ `+07:00`. Yêu cầu đầu tiên sau
khi hết TTL làm mới danh sách. `CASE_CACHE_TTL_SECONDS` mặc định 60 giây,
giới hạn 10–600 giây. Ca đã bị xoá trả 404 sau lần làm mới.
Chế độ `CASE_SOURCE=file` bỏ qua trường này.

## Phản hồi chi tiết

Mở rộng `GET /api/cases/{ca_id}` bằng `danh_sach_y_lenh` và `phieu_dieu_tri`.
Chọn mở rộng phản hồi vì đây là hai tab của chi tiết ca đã có, tránh thêm một
vòng xác thực và một yêu cầu mạng riêng. Quyền đọc, lỗi và
`Cache-Control: private, no-store` giữ như route cũ.

```ts
interface DanhSachCa {
  lam_moi_luc?: string;
}
interface MedicalOrder {
  y_lenh_id: string;
  dot_dieu_tri_id: string;
  thu_tu_dot: number | null;
  thoi_diem_ke: string | null;
  trang_thai: string | null;
  loai: string | null;
  vai_tro_nguoi_ke: string | null;
  khoa_ke_don: string | null;
  luong_duyet: string | null;
  ly_do_ngung: string | null;
  thoi_diem_ngung: string | null;
  thay_the_y_lenh_id: string | null;
  la_trong_tam: boolean;
  cot: string[];
  dong: Record<string, string>[];
}
interface TreatmentSheet {
  phieu_dieu_tri_id: string;
  dot_dieu_tri_id: string;
  thu_tu_dot: number | null;
  ngay_dieu_tri: number;
  thoi_diem_lap: string;
  vai_tro_nguoi_lap: string;
  dien_bien: string;
  danh_gia: string;
  huong_xu_tri: string;
  y_lenh_trong_ngay: string[];
  che_do_cham_soc: string | null;
  che_do_an: string;
  theo_doi: string[];
  dan_do: string | null;
}
interface ChiTietCa {
  danh_sach_y_lenh?: MedicalOrder[];
  phieu_dieu_tri?: TreatmentSheet[];
}
// Đối tượng nội bộ của đường đọc giao diện, không truyền vào pipeline AI.
interface MedicalRecord {
  danh_sach_y_lenh: MedicalOrder[];
  phieu_dieu_tri: TreatmentSheet[];
}
```

Backend luôn trả hai mảng; kiểu web tùy chọn để tương thích mock/client cũ.
Timestamp ISO 8601 có múi giờ. Trường thiếu giữ null; không tạo số liệu lâm
sàng mặc định. Văn bản được hiển thị dạng text, không HTML/Markdown.

`danh_sach_y_lenh` gồm tất cả y lệnh ở mọi đợt của người bệnh có ca đang mở,
kể cả đợt không có y lệnh trọng tâm. Sắp `thu_tu_dot`, thời điểm kê thực tế,
rồi mã để phân định khi trùng thời điểm. `la_trong_tam` khi `y_lenh.ca_id`
bằng ca đang mở; không suy từ trạng thái. `dong` là đúng cấu trúc bảng
`chi_tiet.y_lenh`: các cột Thuốc, Liều, Tần suất, Đường dùng, Lịch dùng,
Trạng thái, với chuỗi hiển thị định dạng như bảng cũ. `cot` khai báo tên
cột để dùng lại thành phần bảng. Y lệnh lịch sử không có nhận định AI.

`phieu_dieu_tri` lấy bảng phiếu riêng, không suy từ `dien_bien`. Sắp theo
đợt rồi `ngay_dieu_tri`, thời điểm và mã phiếu. `y_lenh_trong_ngay` là
danh sách mã từ bảng nối, thứ tự mã ổn định; mỗi liên kết thuộc cùng đợt.

## Đường đọc và lưu trữ

`app/db/medical_record.py` có bộ dựng thuần từ tập hàng, không dựng `CaBenh`.
Mỗi lượt đọc dùng bảy SELECT tham số hóa, gộp theo các mã đợt/dòng thuốc
trong giao dịch REPEATABLE READ chỉ đọc. Bộ đệm chi tiết giữ y lệnh và
phiếu tối đa 60 giây cho cùng phiên bản ca. API đọc hành chính mỗi yêu cầu.
Không trả lỗi DB gốc hay ghi nội dung người bệnh vào log.

`nghiep_vu.phieu_dieu_tri` lưu nội dung phiếu, `theo_doi` JSONB mảng.
`nghiep_vu.phieu_y_lenh` dùng FK kép `(phieu_dieu_tri_id, dot_dieu_tri_id)`
và `(y_lenh_id, dot_dieu_tri_id)`, vừa kiểm tồn tại vừa chặn liên kết sai đợt.
Cả hai bật RLS không policy, thu hồi quyền PUBLIC/anon/authenticated.

`uv run python -m app.db phieu-dieu-tri [--dry-run]` thay toàn bộ phiếu
và liên kết của các đợt có trong lô trong một giao dịch. Lệnh yêu cầu
lược đồ và khóa cha có sẵn. Dữ liệu đầu vào bị loại hoặc thiếu khóa ngoại
trong nguồn làm dừng trước khi kết nối. `all` cũng nạp hai bảng này.

`uv run python -m app.db.reader verify-ho-so` chỉ đọc. Lệnh đối chiếu số
y lệnh ở mọi đợt của từng ca với dữ liệu nguồn và số phiếu với số hàng DB.

## Chế độ file và URL giao diện

Không truy cập DB: danh sách suy từ y lệnh chờ duyệt và thuốc đang dùng
trong `CaBenh`. Thuốc nền được gom thành y lệnh hiển thị `YL-{ca_id}-NEN`,
cùng quy ước nạp dữ liệu cũ; đây là mã nhóm hiển thị, không khẳng định một
y lệnh gốc. `thu_tu_dot=1` chỉ biểu thị đợt duy nhất có sẵn trong dữ liệu
file; metadata không có giữ null. Phiếu luôn `[]`.

Web chọn trọng tâm khi URL chưa có `yl`, lưu lựa chọn dưới
`?tab=y_lenh&yl=<y_lenh_id>` và mã hóa bằng URLSearchParams. Mã không hợp
lệ quay về trọng tâm; khi đổi ca bỏ lựa chọn cũ. Chỉ dòng của y lệnh trọng
tâm có hành động chuyển sang thẩm định. Với mock cũ không có trường phiếu,
web giữ cách hiển thị ghi chép cũ; một mảng `[]` rõ ràng luôn có nghĩa rỗng.
