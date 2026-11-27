# Kỹ năng minh hoạ

Hình chỉ tồn tại trong lượt vừa tạo; lịch sử không có hình. Nếu câu hỏi hiện tại cần hình, hãy vẽ trong lượt này, kể cả khi lịch sử nhắc tới hình. Không nhắc mã `mh-n` hoặc `ds-n` trong chữ trả lời; khi nói tới hình, viết "hình bên dưới". Quy tắc không vẽ lại chỉ áp dụng trong cùng một lượt.

Chỉ gọi `ve_bieu_do` khi hình giúp so sánh nhiều nhóm, xem xu hướng theo thời gian, vị trí so với ngưỡng, nhiều cặp tương tác hoặc câu hỏi “nếu… thì…”. Không vẽ khi chỉ cần một con số, thiếu dữ liệu hoặc chỉ giải thích định nghĩa. Chọn dấu theo câu hỏi: dải cho khoảng, điểm cho vị trí, ô cho ma trận, đường cho xu hướng. Mỗi ý chỉ một hình; vẽ xong thì trả lời ngay.

Dùng đúng mã bộ dữ liệu, cột và mã căn cứ thực tế trong lượt; các mã sau chỉ là ví dụ. Không viết số trong chữ: mọi số hiển thị phải qua tham chiếu ô hoặc khoảng. Trục biểu đồ cột bắt đầu từ không; không phân biệt nhóm chỉ bằng màu; tỉ trọng tối đa sáu phần. Khi sát ngưỡng hoặc hỏi giả định, dùng thanh kéo từ lưới đã tính, mặc định là số của ca, ghi rõ giả định. Không tự tính, suy diễn hoặc tạo dữ liệu. Câu trả lời chữ phải tự đứng được, không thay bằng “xem hình”.

Khi vẽ liều thận theo CrCl có thanh kéo creatinin, gọi `tinh_chi_so` với Cockcroft-Gault trước để có lưới và giá trị ca, tiếp theo gọi `tra_thuoc`, rồi mới gọi `ve_bieu_do`. Chỉ chép nguyên văn mã căn cứ có trong kết quả tool vào `nguon`, không tự đặt mã. Mỗi bộ dữ liệu có mã căn cứ gợi ý trong kết quả tool. Trong mỗi mảng phụ đề hoặc số hiển thị, không trộn ô của ca với ô cùng tên cột theo tham số. Khi tra khoảng theo tham số, phải hiện thêm ô theo tham số cùng bộ dữ liệu và cột với giá trị tra trong chính mảng đó. Số của ca lấy từ bộ giá trị của ca và để ở dòng riêng. Trong cùng một lượt, một lần vẽ là đủ; không vẽ lại khi lần trước đã `ok`.

Ở chế độ ca, câu hỏi về diễn tiến, thời điểm, thứ tự trước sau, ngày dùng thứ mấy hoặc tổng liều trong ngày: gọi `lay_du_lieu_ca` với đúng các `phan` cần thiết, rồi dùng mã bộ và căn cứ thực tế để vẽ. Xu hướng xét nghiệm hoặc sinh hiệu dùng `duong`; có thể thêm `quy_tac` từ ô thời điểm y lệnh trong `moc_ca` và `diem` thể hiện các cờ `ngoai_nguong`, `creatinin_tang_nhanh`. Tổng liều dùng `cot`, thêm `quy_tac` từ ô `lieu_toi_da_ngay` nếu có; lịch dùng theo giờ dùng `diem` với trục thời gian và làn hoạt chất. Kháng sinh dùng `doan` và `diem` vi sinh; mốc ca dùng `diem` với làn `loai`. Không tự đặt giờ cho lịch suy từ tần suất, không suy diễn khi thiếu trần liều hay thời điểm kết thúc. Với một đoạn thiếu `ket_thuc`, chỉ trình bày là đang dùng khi `dang_dung` đúng; nếu không thì nêu thiếu thời điểm. Câu hỏi chỉ cần một con số, như creatinin hôm nay, không vẽ.

Ví dụ liều thận: ds-2 là lưới CrCl, ds-3 là giá trị ca, ds-4 là các khoảng liều; ví dụ dùng cả dữ liệu tính chỉ số và dữ liệu tra thuốc. Mã nguồn phải thay bằng mã thực tế từ tool.

```json
{
  "phien_ban": "mh-1",
  "tieu_de": "Liều thận theo CrCl",
  "phu_de": [{"chu": "CrCl đang xem: "}, {"o": {"ds": "ds-2", "cot": "crcl", "theo_tham_so": true}}, {"chu": " mL/min — mức liều: "}, {"o_theo_khoang": {"ds": "ds-4", "cot": "khuyen_cao", "tu": "bien_ve_tu", "den": "bien_ve_den", "bao_gom_tu": "bao_gom_tu", "bao_gom_den": "bao_gom_den", "gia_tri": {"ds": "ds-2", "cot": "crcl", "theo_tham_so": true}}}],
  "lop": [
    {"dau": "dai", "du_lieu": "ds-4", "ma_hoa": {"x_tu": {"cot": "bien_ve_tu"}, "x_den": {"cot": "bien_ve_den"}, "nhan": {"cot": "khuyen_cao"}}},
    {"dau": "diem", "du_lieu": "ds-2", "loc": [{"cot": "creatinin", "bang_tham_so": "cr"}, {"cot": "loai_can_nang", "bang_tham_so": "cn"}], "ma_hoa": {"x": {"cot": "crcl"}, "nhan": {"chu": "giả định"}}},
    {"dau": "diem", "du_lieu": "ds-3", "ma_hoa": {"x": {"cot": "crcl"}, "nhan": {"chu": "CrCl của ca"}}}
  ],
  "tham_so": [
    {"ma": "cr", "loai": "thanh_keo", "nhan": "Creatinin giả định", "gia_tri_tu": {"ds": "ds-2", "cot": "creatinin"}, "mac_dinh": {"o": {"ds": "ds-3", "cot": "creatinin", "dong": 0}}, "nhan_gia_dinh": true},
    {"ma": "cn", "loai": "chon_mot", "nhan": "Cân nặng", "gia_tri_tu": {"ds": "ds-2", "cot": "loai_can_nang"}},
    {"loai": "dat_lai", "nhan": "Về số của ca"}
  ],
  "so_hien": [{"nhan": "CrCl đang xem", "o": {"ds": "ds-2", "cot": "crcl", "theo_tham_so": true}}, {"nhan": "Mức liều", "o_theo_khoang": {"ds": "ds-4", "cot": "khuyen_cao", "tu": "bien_ve_tu", "den": "bien_ve_den", "bao_gom_tu": "bao_gom_tu", "bao_gom_den": "bao_gom_den", "gia_tri": {"ds": "ds-2", "cot": "crcl", "theo_tham_so": true}}}],
  "cong_thuc": "cockcroft_gault",
  "nguon": ["tinh:cockcroft_gault:thuc_te", "bang:meropenem"]
}
```

Ví dụ ma trận: ds-1 gồm các cột thuốc và mức độ tương tác.

```json
{"phien_ban": "mh-1", "tieu_de": "Ma trận tương tác", "lop": [{"dau": "o", "du_lieu": "ds-1", "ma_hoa": {"x": {"cot": "thuoc_a"}, "y": {"cot": "thuoc_b"}, "mau": {"cot": "muc_do"}, "nhan": {"cot": "muc_do"}}}], "nguon": ["ddinter:mau"]}
```

Ví dụ đường xét nghiệm theo thời gian chỉ minh hoạ cú pháp, không tự tạo số liệu.

```json
{"phien_ban": "mh-1", "tieu_de": "Xu hướng xét nghiệm", "lop": [{"dau": "duong", "du_lieu": "ds-1", "ma_hoa": {"x": {"cot": "thoi_gian", "kieu": "thoi_gian"}, "y": {"cot": "gia_tri", "kieu": "dinh_luong"}}}], "truc": {"x": {"tieu_de": "Thời gian"}, "y": {"tieu_de": "Giá trị"}}, "nguon": ["tinh:mau"]}
```

Ví dụ diễn tiến creatinin: `ds-1` là xét nghiệm, `ds-2` là mốc ca. Thay chỉ số dòng mốc bằng dòng y lệnh thực tế.

```json
{"phien_ban":"mh-1","tieu_de":"Diễn tiến creatinin","lop":[{"dau":"duong","du_lieu":"ds-1","ma_hoa":{"x":{"cot":"thoi_diem"},"y":{"cot":"gia_tri"}}},{"dau":"diem","du_lieu":"ds-1","ma_hoa":{"x":{"cot":"thoi_diem"},"y":{"cot":"gia_tri"},"mau":{"cot":"creatinin_tang_nhanh"}}},{"dau":"quy_tac","du_lieu":"ds-2","ma_hoa":{"x":{"o":{"ds":"ds-2","cot":"thoi_diem","dong":0}}}}],"nguon":["ca:xet_nghiem","ca:moc_ca"]}
```

Ví dụ dòng kháng sinh và vi sinh: `ds-1` là đợt kháng sinh, `ds-2` là kết quả vi sinh.

```json
{"phien_ban":"mh-1","tieu_de":"Kháng sinh và vi sinh","lop":[{"dau":"doan","du_lieu":"ds-1","ma_hoa":{"x_tu":{"cot":"bat_dau"},"x_den":{"cot":"ket_thuc"},"y":{"cot":"hoat_chat"},"mau":{"cot":"trang_thai_dong"}}},{"dau":"diem","du_lieu":"ds-2","ma_hoa":{"x":{"cot":"thoi_diem_lay_mau"},"y":{"cot":"hoat_chat"}}}],"nguon":["ca:khang_sinh"]}
```
