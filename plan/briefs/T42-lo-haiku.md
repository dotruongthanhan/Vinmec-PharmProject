# T42 – hướng dẫn cho agent sinh phiếu điều trị theo lô

Bạn sinh phiếu điều trị cho một nhóm hồ sơ giả lập. Đọc kỹ `plan/briefs/T42-sinh-phieu-dieu-tri.md` (cấu trúc phiếu, số lượng phiếu, yêu cầu nhất quán, mục Bổ sung 1) và làm đúng như vậy, **trừ phần ghi kết quả** ở dưới.

## Việc làm với từng hồ sơ trong lô
1. Đọc `data/mock/hoso_gia_lap/HS-xxx.json` (cả hồ sơ; chú ý `dot_dieu_tri[*]`: `sinh_hieu`, `xet_nghiem`, `vi_sinh`, `dien_bien`, `y_lenh`, `tom_tat`, `tong_ket`, `chan_doan`, `co_dia`, `tinh_trang_di_ung`) và dòng tương ứng trong `data/mock/hoso_gia_lap/BANG_TRA.md` để hiểu kịch bản.
2. Với mỗi đợt, tính số phiếu và các ngày theo brief (đợt đang mở: điểm cuối là `thoi_diem_ke` của y lệnh muộn nhất; tối đa 10 phiếu; ngoại trú 1 phiếu).
3. Viết các phiếu bằng tiếng Việt y khoa tự nhiên, mỗi phiếu khác nhau về câu chữ, đủ dài (ba trường văn bản cộng khoảng 500–1200 ký tự), bám dữ liệu hồ sơ. Tự viết nội dung, không dùng mẫu ghép, không gọi dịch vụ ngoài.
4. **Ghi kết quả vào `data/mock/phieu_tmp/HS-xxx.json`** (một tệp mỗi hồ sơ, tạo thư mục nếu chưa có), dạng:
   ```
   { "<dot_dieu_tri_id>": [ {phiếu 1}, {phiếu 2}, … ], "<dot_dieu_tri_id khác>": [ … ] }
   ```
   Mỗi phần tử đúng cấu trúc phiếu trong brief (`phieu_dieu_tri_id` dạng `PDT-HS-001-1-01`, `ngay_dieu_tri`, `thoi_diem_lap` ISO có `+07:00`, `vai_tro_nguoi_lap`, `dien_bien`, `danh_gia`, `huong_xu_tri`, `y_lenh_trong_ngay`, `che_do_cham_soc`, `che_do_an`, `theo_doi`, `dan_do`). Mọi đợt của hồ sơ phải có mặt.
5. **Không sửa** `data/mock/hoso_gia_lap/*.json` hay tệp nào khác ngoài `data/mock/phieu_tmp/`.

## Tự kiểm trước khi trả
- `y_lenh_trong_ngay` chỉ chứa mã y lệnh có thật trong đợt đó và có hiệu lực ngày đó.
- Số liệu sinh hiệu/xét nghiệm nêu trong phiếu có trong dữ liệu đợt đó; không bịa số mới trái hồ sơ.
- `thoi_diem_lap` trong đợt, tăng dần theo ngày, không vượt điểm cuối.
- Y lệnh `cho_duyet` chỉ nhắc ở ngày kê, như "chỉ định/đề nghị".
- Không nhắc lỗi cài, không tên thật, không mã người bệnh thật.
- JSON hợp lệ (đọc lại được bằng `python -I -c "import json;json.load(open(...,encoding='utf-8'))"`).

Cuối cùng trả lời ngắn: các hồ sơ đã xong, số phiếu mỗi hồ sơ, chỗ nào nghi ngờ.
