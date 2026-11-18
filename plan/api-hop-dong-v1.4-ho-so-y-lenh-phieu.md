# API v1.4 – Y lệnh trong hồ sơ và phiếu điều trị (T44)

Bổ sung tương thích trên v1/v1.1/v1.2 và phần hành chính T45 (v1.5).
Không đổi/xóa trường cũ. `CaBenh`, thẩm định và mọi điểm ghi không đổi.

## Phản hồi chi tiết

Mở rộng `GET /api/cases/{ca_id}` bằng `danh_sach_y_lenh` và `phieu_dieu_tri`.
Chọn mở rộng phản hồi vì đây là hai tab của chi tiết ca đã có, tránh thêm một
vòng xác thực và một yêu cầu mạng riêng. Quyền đọc, lỗi và
`Cache-Control: private, no-store` giữ như route cũ.

```ts
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
  nap_luc: string | null;
  nguon_tep: string | null;
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
`nap_luc` là thời điểm nạp DB, có thể null khi dựng từ hàng kiểm thử nguồn.

## Đường đọc và lưu trữ

`app/db/medical_record.py` có bộ dựng thuần từ tập hàng, không dựng `CaBenh`.
Mỗi lượt đọc dùng bảy SELECT tham số hóa, gộp theo các mã đợt/dòng thuốc;
giao dịch REPEATABLE READ chỉ đọc và không cache hồ sơ trong dịch vụ AI.
Không trả lỗi DB gốc hay ghi nội dung người bệnh vào log.

`nghiep_vu.phieu_dieu_tri` lưu nội dung phiếu, `theo_doi` JSONB mảng.
`nghiep_vu.phieu_y_lenh` dùng FK kép `(phieu_dieu_tri_id, dot_dieu_tri_id)`
và `(y_lenh_id, dot_dieu_tri_id)`, vừa kiểm tồn tại vừa chặn liên kết sai đợt.
Cả hai bật RLS không policy, thu hồi quyền PUBLIC/anon/authenticated.

`uv run python -m app.db phieu-dieu-tri [--dry-run]` chỉ upsert hai bảng
phiếu theo khóa, không reset và không sửa bảng khác; yêu cầu schema và các
khóa cha đã có. Dữ liệu đầu vào bị loại hoặc thiếu FK làm dừng trước kết
nối/ghi. Nạp lại cùng nguồn không tăng số dòng. `all` cũng nạp hai bảng này.

`uv run python -m app.db.reader verify-ho-so` chỉ đọc, đối chiếu số y lệnh
và số phiếu ở mọi đợt cho từng ca với số hàng DB (HS-022: 7 y lệnh).
Việc chạy trên Supabase thật do người review thực hiện sau T44.

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
