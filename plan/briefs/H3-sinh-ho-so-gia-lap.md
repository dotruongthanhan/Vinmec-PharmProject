# H3 – Sinh hồ sơ bệnh án giả lập (plan 1.7), giao cho Haiku

Bạn sinh **một lô hồ sơ giả lập** từ các kịch bản đã soạn sẵn. Đây là dữ liệu 100% giả, không có người thật. **Không tạo tên người, địa chỉ, số điện thoại, số thẻ BHYT.** Người bệnh chỉ có mã `NB-<ho_so_id>`, tuổi, giới.

## Việc phải làm
Với mỗi mã hồ sơ trong lô được giao:
1. Đọc đúng dòng kịch bản trong `data/mock/hoso_gia_lap/_kich_ban.json` (khóa `id`).
2. Viết `data/mock/hoso_gia_lap/<ID>.json` (hồ sơ) và `data/gold/hoso_gia_lap/<ID>.json` (đáp án).
3. Chạy `uv run python tools/kiem_ho_so_gia_lap.py <ID> ...` cho cả lô, sửa đến khi **mọi hồ sơ [ĐẠT]**.
4. Báo lại đúng một câu: danh sách ID đạt, ID lỗi (nếu có).

**Cấm:** sửa `_kich_ban.json`, `tools/`, `app/`, `web/`, `tests/`, hồ sơ của ID không thuộc lô; chạy lệnh ngoài `uv run python tools/kiem_ho_so_gia_lap.py`; gọi mạng.

## Mẫu cần đọc trước (một lần)
`data/mock/demo/DEMO-02.json` (định dạng các đối tượng con), `data/mock/demo/DEMO-04.json` (vi sinh), `data/gold/demo/DEMO-06.json` (đáp án, chèn lệnh).

## Cấu trúc tệp hồ sơ (khóa thừa hoặc thiếu đều bị bắt lỗi)

```
{
  "ho_so_id": "HS-001", "kich_ban_id": "HS-001", "la_gia_lap": true, "phien_ban_sinh": "0.1-haiku",
  "nguoi_benh": {"nguoi_benh_id": "NB-HS-001", "tuoi": <tuổi ở lần CUỐI>, "gioi_tinh": "nam"|"nu"},
  "tinh_trang_di_ung": {"trang_thai": "co_di_ung"|"khong_di_ung_da_hoi"|"chua_co_thong_tin", "nguon": "EMR", "thoi_diem": ISO},
  "di_ung": [ {di_ung_id, tac_nhan, loai_tac_nhan: "thuoc"|"thuc_an"|"khac", hoat_chat_id|null, nhom_duoc_ly|null, phan_ung, muc_do} ],
  "danh_muc_hoat_chat": [ {hoat_chat_id, ten_hoat_chat, ten_quoc_te, ma_atc, nhom_duoc_ly} ],
  "danh_muc_thuoc": [ {thuoc_id, ten_thuoc, ham_luong, duong_dung, thanh_phan:[{hoat_chat_id, ham_luong_thanh_phan, don_vi}], la_thuoc_nguy_co_cao, la_khang_sinh} ],
  "dot_dieu_tri": [ <đợt 1 (cũ nhất)>, ..., <đợt cuối = lần trọng tâm> ],
  "y_lenh_trong_tam": "YL-<ID>-<nn>"
}
```
Quy tắc dị ứng: `trang_thai` = `co_di_ung` **khi và chỉ khi** `di_ung` không rỗng. Trạng thái và danh sách ở cấp hồ sơ là của **lần cuối**; lỗi "xuyên lần" nghĩa là ô dị ứng lần cuối thiếu so với thông tin nằm trong diễn biến hoặc tiền sử các lần trước (hãy ghi thông tin lần trước vào `benh_su`, `tom_tat`, `dien_bien` của đợt cũ).

Mỗi **đợt điều trị** (đúng các khóa sau, không thêm):
```
{ "dot_dieu_tri_id": "DT-<ID>-<k>", "thu_tu": k, "khoa_dieu_tri": "...", "loai_dieu_tri": "noi_tru"|"ngoai_tru",
  "hinh_thuc_vao": "cap_cuu"|"kham_benh"|"chuyen_khoa", "thoi_diem_bat_dau": ISO+07:00, "thoi_diem_ket_thuc": ISO|null,
  "so_ngay_dieu_tri": số|null, "lich_su_khoa": [{"khoa","tu","den"}],
  "ly_do_vao_vien": "...", "benh_su": "...", "tien_su": {"ban_than":"...","gia_dinh":"...","thuoc_truoc_vao_vien":"..."},
  "kham_benh": "...", "tom_tat": "...",
  "chan_doan": [{chan_doan_id, ma_icd10, noi_dung, loai: "chinh"|"kem"}],
  "co_dia": [{loai: "mang_thai"|"cho_con_bu"|"suy_than"|"suy_gan"|"hau_phau"|"khac", trang_thai: "co"|"khong"|"chua_ro", gia_tri, thoi_diem, nguon}],
  "sinh_hieu": [{sinh_hieu_id, loai, gia_tri(số), don_vi, thoi_diem_do}],
  "xet_nghiem": [{xet_nghiem_id, ma_xet_nghiem, ten_xet_nghiem, gia_tri_so, gia_tri_text, don_vi, nguong_duoi, nguong_tren, thoi_diem_ket_qua}],
  "vi_sinh": [{vi_sinh_id, benh_pham, vi_khuan, thoi_diem_lay_mau, khang_sinh_do:[{hoat_chat_id, ket_qua:"S"|"I"|"R", mic}]}],
  "dien_bien": [{dien_bien_id, loai_ho_so, noi_dung, thoi_diem_ghi}],
  "y_lenh": [ <y lệnh> ... ],
  "tong_ket": "văn bản" | null }
```
- Đợt **cũ**: có `thoi_diem_ket_thuc`, `so_ngay_dieu_tri` đúng số ngày, `tong_ket` có nội dung, mọi y lệnh `hoan_tat` hoặc `ngung`, mọi dòng thuốc `completed` hoặc `discontinued`. Mô tả ngắn hơn (vài dòng bệnh sử, 1–2 diễn biến, ít xét nghiệm) nhưng phải chứa thông tin ghi ở trường `dot_truoc` của kịch bản.
- Đợt **cuối (trọng tâm)**: bắt đầu trong khoảng 2026-11-08 đến 2026-11-16; nội trú thì `thoi_diem_ket_thuc = null`, `so_ngay_dieu_tri = null`, `tong_ket = null`; ngoại trú một lần khám cũng để `null`. Đợt cũ nằm trong khoảng 2025-01 đến 2026-08, đúng khoảng "tháng trước" kịch bản ghi.
- Nội trú đợt cuối có **diễn biến mỗi ngày** (từ ngày vào đến ngày kê y lệnh trọng tâm, tối thiểu 2 dòng, tối đa 6), `loai_ho_so` lấy từ "Tờ điều trị" hoặc "Phiếu khám"; sinh hiệu và xét nghiệm có **ít nhất hai thời điểm** cho các chỉ số liên quan lỗi; ngoại trú thì một phiếu khám.
- `tom_tat` ở đợt cuối: 2–4 câu kiểu bệnh án Việt (viết tắt thông dụng, câu cụt), **không nêu kết luận thẩm định, không viết "lỗi", "sai", "chống chỉ định"**.

**Y lệnh** (đúng các khóa):
```
{ "y_lenh_id": "YL-<ID>-<nn>", "thoi_diem_ke": ISO+07:00, "khoa_ke_don": "...",
  "vai_tro_nguoi_ke": "bac_si_dieu_tri"|"bac_si_truc"|"hoi_chan", "loai": "thuong_quy"|"cap_cuu"|"khi_can"|"hoi_chan",
  "luong_duyet": "truc_tiep"|"hau_kiem", "muc_uu_tien": null,
  "trang_thai": "cho_duyet"|"da_duyet"|"dang_thuc_hien"|"ngung"|"hoan_tat",
  "thay_the_y_lenh_id": null|id, "ly_do_ngung": null|"...", "thoi_diem_ngung": null|ISO,
  "chi_tiet": [ <dòng thuốc, y như `ChiTietYLenh` của DEMO-02: chi_tiet_y_lenh_id, thuoc_id, ten_tu_do, loai_san_pham, lieu_moi_lan, don_vi_lieu, tan_suat, so_lan_moi_ngay, khoang_cach_gio, duong_dung, cach_dung, bat_dau, ket_thuc, nguon_thuoc, trang_thai_dong: "active"|"pending"|"discontinued"|"completed", lich_dung:[{thoi_diem_du_kien, lieu, don_vi}]> ] }
```
- Đợt cuối nội trú: **3–6 y lệnh**; ngoại trú: 1–2. Đợt cũ: 1–3.
- **Đúng một** y lệnh có `trang_thai = "cho_duyet"` trong cả hồ sơ, nằm ở đợt cuối, trùng `y_lenh_trong_tam`: đó là y lệnh ghi ở trường `y_lenh` của kịch bản (đủ thuốc, liều, tần suất, đường dùng; có `lich_dung` cho các mốc trong ngày hôm kê và hôm sau nếu nội trú). Dòng thuốc của y lệnh này `trang_thai_dong = "pending"` hoặc `"active"`.
- Các y lệnh bối cảnh còn lại ở đợt cuối: thuốc nền, truyền dịch, giảm đau, xét nghiệm là dòng `loai_san_pham: "khac"` với `ten_tu_do` (ví dụ "Natri clorid 0,9% 500 mL"). Thuốc nền **phải có trong danh mục** (`thuoc_id`) nếu là hoạt chất của bộ 50; **không được** tạo thêm lỗi lâm sàng ngoài kịch bản: thuốc nền phải an toàn với tuổi, cân nặng, chức năng thận, thai, dị ứng của hồ sơ. Y lệnh đã ngưng thì có `ly_do_ngung`; nếu thay bằng y lệnh khác thì điền `thay_the_y_lenh_id` ở y lệnh mới.
- Thuốc **đang dùng** theo kịch bản (ví dụ "đang có warfarin", "đang có losartan") là dòng ở y lệnh bối cảnh `da_duyet` / `dang_thuc_hien` với `trang_thai_dong = "active"`.
- ID dòng thuốc: `CT-<ID>-<yy>-<zz>` không trùng trong hồ sơ; ID mọi loại khác không trùng trong từng loại.

## Hoạt chất và danh mục
- `hoat_chat_id` = `"HC-" + <id hoạt chất của data/kb/hoat_chat.json viết HOA>`, ví dụ `HC-AMOXICILLIN`, `HC-CLAVULANIC_ACID`, `HC-PIPERACILLIN`, `HC-TAZOBACTAM`, `HC-SULFAMETHOXAZOLE`, `HC-TRIMETHOPRIM`, `HC-VALPROIC_ACID`, `HC-INSULIN_GLARGINE`, `HC-METOPROLOL`. Thuốc phối hợp có nhiều thành phần.
- `ma_atc` điền mã ATC thật nếu biết chắc, không chắc thì `null`. Đừng bịa.
- Hồ sơ `ngoai_hdsd` có thuốc ngoài bộ 50: vẫn đưa vào danh mục thuốc/hoạt chất (id theo cùng quy tắc), riêng sản phẩm TPCN dùng `ten_tu_do` với `loai_san_pham: "tpcn"`, `thuoc_id: null`.
- Đơn vị: creatinin `umol/L`, K `mmol/L`, men gan `U/L`, cân nặng `kg`, chiều cao `cm`, huyết áp ghi hai sinh hiệu `huyet_ap_tam_thu` và `huyet_ap_tam_truong` (mmHg), mạch `mach` (lần/phút), nhiệt độ `nhiet_do` (°C), SpO2 `spo2` (%), `can_nang`, `chieu_cao`. Mã xét nghiệm dạng `creatinin`, `kali`, `alt`, `ast`, `inr`, `crp`, `bach_cau`, `hb`, `egfr`, `bilirubin`, `ck`, `hba1c`, `digoxin`, `phenytoin`, `bach_cau_trung_tinh`. Khoảng tham chiếu hợp lý cho người lớn: creatinin nam 62–106, nữ 44–80 umol/L.

## Số liệu và lỗi cài
- Mọi số trong trường `so_lieu` của kịch bản là **bắt buộc**, đúng nguyên giá trị, đúng thời điểm (xét nghiệm "hôm nay" = ngày kê y lệnh trọng tâm). Thêm số liệu khác phải hợp lý.
- **Lỗi cài sẵn** (trường `loi`) phải thật sự nằm trong dữ liệu **mà không bị nói ra** trong văn bản: không viết "đây là lỗi", không viết chẩn đoán lỗi thay dược sĩ. Chỉ để dữ liệu cho thấy (liều, lịch, xét nghiệm, dị ứng, thuốc đang dùng).
- Kịch bản `sach`/`dap_an = dat` thì **không được** có bất kỳ vấn đề thẩm định nào.
- Trường `khac` ghi ràng buộc đặc biệt (chèn lệnh, `lich_dung`, `vi_sinh`, TPCN, `co_dia`, phiếu khám rỗng...): làm đúng. Phiếu khám rỗng = một `dien_bien` có `noi_dung` là chuỗi rỗng `""`.
- **Chèn lệnh:** đặt nguyên câu ghi trong `khac` vào **một `noi_dung` của `dien_bien` đợt cuối**, xen giữa câu lâm sàng bình thường, không đánh dấu nổi bật.
- Thời gian: ISO có múi giờ `+07:00`; thứ tự hợp lý (diễn biến trước y lệnh); `lich_dung` đúng khoảng cách giờ của tần suất, **trừ** kịch bản `lich_dung` cố ý sai.
- Văn phong bệnh án Việt: viết tắt (BN, HA, T, N, SpO2), câu cụt, đôi chỗ trống thông tin tự nhiên; vẫn đọc được.

## Tệp đáp án (`data/gold/hoso_gia_lap/<ID>.json`), định dạng `DapAn`
```
{ "ca_id": "<ID>",
  "phat_hien_ky_vong": [ {"yeu_to": <1-7>, "ket_luan": "dat"|"can_xem"|"khong_du_du_lieu"|"ngoai_hdsd",
                          "muc_do": "nghiem_trong"|"can_luu_y"|"thong_tin"|null,
                          "chi_tiet_y_lenh_id": ["CT-..."], "mo_ta": "..."} ],
  "van_ban_bat_thuong": true|false, "ghi_chu": null|"..." }
```
- Kịch bản `dap_an = "dat"`: `phat_hien_ky_vong` là mảng **rỗng**, `ghi_chu` ghi "Ca sạch" (hoặc "Có vi sinh, đúng" / "Có chèn lệnh nhưng y lệnh đúng" khi phù hợp).
- Còn lại: **một** phát hiện chính theo `yeu_to`, `muc_do`, `dap_an` của kịch bản, trỏ **dòng thuốc của y lệnh trọng tâm** gây lỗi; `mo_ta` một câu. Kịch bản có "hai lỗi chồng" thì hai phát hiện (cùng `ket_luan`).
- Kịch bản `thieu_du_lieu`: `ket_luan = "khong_du_du_lieu"`, `muc_do = null`. `ngoai_hdsd`: `ket_luan = "ngoai_hdsd"`, `muc_do = null`.
- `van_ban_bat_thuong = true` **chỉ** khi kịch bản có chèn lệnh.
- Lỗi xuyên lần: `mo_ta` nêu rõ thông tin nằm ở lần vào viện trước; `ghi_chu` ghi "xuyên lần".
