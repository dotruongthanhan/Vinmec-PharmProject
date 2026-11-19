# Đường dùng hợp lệ và liều tối đa (plan 1.8, đợt D5)

Cập nhật: 19/11/2026. Người ghi: sub Sonnet (task T66 và T65-T66 hoàn thiện). Hai tệp dữ liệu nằm trong git (`data/kb/`), mọi dòng **`cho_duoc_si_duyet`**, chưa có dược sĩ duyệt.

| Mục | Giá trị |
|:--|:--|
| Tệp dữ liệu | `data/kb/duong_dung_hop_le.json` (D5-v1), `data/kb/lieu_toi_da.json` (D5-v2) |
| Nguồn | Đường dùng: (1) DAV dạng bào chế sản phẩm Việt Nam (`data/kb_sources/dav`, [dav.md](dav.md)), (2) NDC openFDA `route`, (3) nhãn FDA `openfda.route`; TT 20 chưa lấy được bản gốc nên chưa dùng. Liều tối đa: nhãn FDA (kho `data/kb_sources/openfda/`, `data/kb_sources/openfda_d5/`) |
| Giấy phép | openFDA public domain (`meta.license`); DAV: manifest chỉ ghi "dữ liệu công bố của Cục Quản lý Dược", chưa có điều khoản tái sử dụng (xem [dav.md](dav.md)); ở đây chỉ trích dạng bào chế và số lượng sản phẩm |
| Tầng tin cậy | DAV tầng cơ quan quản lý VN; NDC và nhãn FDA tầng 3. Mọi dòng chờ dược sĩ duyệt |
| Ngày lấy | DAV 18/11/2026; NDC và nhãn FDA 19/11/2026 |
| Lệnh | Không có lệnh dựng trong app; dựng một lần từ tập lệnh tạm của T66. Nhãn mới (`openfda_d5/`) và đếm route NDC (`openfda_ndc/`) tải bằng openFDA (≤ 2 yêu cầu/giây) |

Không lấy từ UpToDate, Lexicomp, MIMS, Micromedex.

## 1. `duong_dung_hop_le.json`

Khoá cấp cao: `ten`, `phien_ban`, `ngay`, `trang_thai`, `huong_giai_thich`, `bang_chuan_hoa_duong_dung`, `nhom` (62), `thuoc_trong_66_ca` (68), `tinh_huong_kiem` (3), `thong_ke`.

### 1.1. Cách dùng (`huong_giai_thich`)

Khoá tra: `hoat_chat_ids` (khoá trục `tra_cuu.sqlite`; thuốc phối hợp là danh sách sắp theo chữ cái) cộng `nhom_dang_bao_che`. Với dòng y lệnh: tìm hoạt chất của thuốc, xác định nhóm dạng (danh mục thuốc của ca chưa có dạng bào chế riêng, nhóm dạng suy từ trường `duong_dung` của `danh_muc_thuoc`: uống hay tiêm/truyền), rồi kiểm mã chuẩn của đường dùng có trong `duong_dung_hop_le` không. Không có: `khong_hop_le` (mức đề xuất `can_xem`, kèm nguồn, không phải kết luận kê sai). Không có hàng hoặc `duong_dung_hop_le` rỗng: `thieu_nguon`, không được ghi "đạt". Tĩnh mạch: `tiem_tinh_mach` và `truyen_tinh_mach` cùng một họ INTRAVENOUS của FDA, kiểm ở mức họ.

### 1.2. `bang_chuan_hoa_duong_dung`

Khoá chuẩn: bỏ dấu, chữ thường, gộp khoảng trắng, tra `khoa_sang_ma`. Không có trong bảng: `duong_dung_chuan = null`, kết quả `khong_chuan_hoa_duoc` (hỏi dược sĩ), không đoán. 15 mã chuẩn (`ma_chuan`): `uong`, `tiem_tinh_mach`, `truyen_tinh_mach`, `tiem_bap`, `tiem_duoi_da`, `tiem_trong_ong_tuy`, `tiem_ngoai_mang_cung`, `boi_ngoai_da`, `nho_mat`, `nho_tai`, `xit_mui`, `hit`, `dat_truc_trang`, `dat_am_dao`, `ngam_duoi_luoi`. `tu_mo_ho`: "đặt" phải hỏi (trực tràng hay âm đạo). `ma_fda_sang_ma_chuan`: ORAL, INTRAVENOUS (hai mã), INTRAMUSCULAR, SUBCUTANEOUS, INTRATHECAL, EPIDURAL, RECTAL, OPHTHALMIC, TOPICAL, NASAL…

Cách viết trong 66 ca (`cach_viet_trong_66_ca`, theo số dòng y lệnh): "uống" 39, "truyền tĩnh mạch" 13, "tiêm truyền tĩnh mạch" 7, "tiêm dưới da" 4, "uong" 3, "tiêm tĩnh mạch" 2.

### 1.3. Mỗi phần tử `nhom` (62 dòng, 37 hoạt chất)

| Trường | Ý nghĩa |
|:--|:--|
| `ma_dong` | `<hoat_chat>|<nhom_dang>` (ví dụ `morphine|dang_tiem_truyen`) |
| `hoat_chat_ids`, `nhom_dang_bao_che`, `ten_nhom_dang` | Khoá tra; nhóm dạng: `dang_uong` 26, `dang_tiem_truyen` 25, `dang_nho_mat` 4, `dang_dat` 3, `dang_boi_ngoai_da` 3, `dang_xit_mui` 1 |
| `duong_dung_hop_le[]` | Mã chuẩn hợp lệ |
| `muc_chac_chan` | `dav_va_fda` (48): DAV có dạng bào chế và FDA có route. `chi_fda` (7): chỉ FDA. `chi_dav_chu_dang_bao_che` (4): chỉ chữ trong dạng bào chế DAV. `khong_co_duong_dung_cu_the` (3): chưa có đường tiêm cụ thể |
| `nguon[]` | `loai`: `dav_dang_bao_che` (`so_san_pham_dav`, `dang_bao_che_goc_pho_bien`), `ndc_openfda` (`route_goc`, `truy_van`), `nhan_fda` (`set_id`, `route_goc`, `url`) |
| `ghi_chu`, `trang_thai` | Điều dược sĩ cần biết; `cho_duoc_si_duyet` |

### 1.4. Soát T65-T66 hoàn thiện (19/11)

- Mọi dòng `nhom` có ít nhất một nguồn (62/62, 0 dòng trống). Dòng chỉ có FDA đều ghi `muc_chac_chan: chi_fda`; không có dòng `chi_fda` nào lẫn nguồn DAV, không có dòng `dav_va_fda` nào thiếu DAV.
- **Morphin tiêm dưới da (HS-037)**: dòng `morphine|dang_tiem_truyen` không có `tiem_duoi_da`, trong khi danh mục thuốc của ca ghi "tiêm dưới da, tiêm tĩnh mạch". Đã tra lại: openFDA `drug/ndc` `generic_name:morphine AND route:SUBCUTANEOUS` **0 kết quả**; route sản phẩm morphin tiêm là INTRAVENOUS 26, INTRAMUSCULAR 11, EPIDURAL 8, INTRATHECAL 8; `drug/label` morphine sulfate `openfda.route:SUBCUTANEOUS` **0 kết quả**; nhãn trong kho chỉ nhắc tiêm dưới da ở phản ứng bất lợi và thí nghiệm động vật; DAV 4 sản phẩm morphin dung dịch tiêm, trường đường dùng để trống. **Kết luận: chưa thấy nguồn nên giữ nguyên, không thêm `tiem_duoi_da`**; đã ghi vào `ghi_chu` của dòng. HS-037 vẫn ra `khong_hop_le` mức `can_xem`, chờ dược sĩ đối chiếu Dược thư Quốc gia.

### 1.5. Y lệnh của 66 ca và tình huống kiểm

`thuoc_trong_66_ca` (68 dòng y lệnh): 66 `hop_le`, 1 `khong_hop_le` (HS-037 morphin), 1 `khong_co_hoat_chat` (HS-055, thực phẩm chức năng). `tinh_huong_kiem` (3): levofloxacin dạng uống kê tiêm tĩnh mạch → `khong_hop_le`; levofloxacin dạng truyền kê truyền (HS-018) → `hop_le`; levofloxacin uống kê uống (HS-041, HS-051) → `hop_le`.

## 2. `lieu_toi_da.json` (D5-v2)

Khoá cấp cao: `ten`, `phien_ban`, `ngay`, `trang_thai`, `huong_giai_thich`, `nhom` (40 dòng), `khong_ghi_toi_da` (22), `khong_ghi_toi_da_theo_duong_trong_ca` (21), `thong_ke`, `tinh_huong_kiem` (6), `doi_chieu_66_ca` (67), **`doi_tuong_dinh_nghia`** (mới), **`doi_tuong_dinh_nghia_ghi_chu`** (mới).

### 2.1. Mỗi phần tử `nhom`

| Trường | Ý nghĩa |
|:--|:--|
| `ma_dong` | `<hoat_chat>|<đường dùng nối bằng +>|<doi_tuong>` |
| `hoat_chat_ids`, `duong_dung[]` | Khoá tra; mã chuẩn đường dùng |
| `doi_tuong`, `dieu_kien` | Đối tượng và điều kiện áp dụng; nghĩa của `doi_tuong` xem 2.2 |
| `loai_gioi_han` | `toi_da_ro` (36; nhãn dùng "maximum", "not to exceed"), `tran_up_to` (3; "up to X", trần mềm, xử lý mức `can_xem`), `gioi_han_thiet_bi` (1; bút insulin, không dùng cảnh báo lâm sàng) |
| `lieu_toi_da_lan`, `lieu_toi_da_ngay`, `lieu_toi_da_tuan` | `{gia_tri, don_vi}` hoặc `null` |
| `theo_kg` | `lan_mg_kg` và/hoặc `ngay_mg_kg`; cần cân nặng, thiếu thì `khong_du_du_lieu` |
| `thuoc_dung_cung_hoat_chat_ids` | Trần tính chung cho mọi thuốc cùng hoạt chất (paracetamol) |
| `quy_doi_don_vi[]` | Với mỗi `don_vi_nhan`: `quy_doi_duoc`, `can_can_nang` (nếu quy đổi cần cân nặng), `sang_don_vi_ca[]` (`don_vi_ca`, `nhan_voi` hoặc `nhan_voi_can_nang_kg`) |
| `nguon` | Một nguồn nhãn: `ten_nhan`, `set_id`, `phien_ban_nguon`, `tep`, `muc_nhan`, `route_goc_cua_nhan`, `trich_nguyen_van`, `url`, `url_api`, `ngay_lay` |
| `ghi_chu`, `trang_thai` | Điều cần biết; `cho_duoc_si_duyet` |

### 2.2. `doi_tuong_dinh_nghia` (mới)

Giá trị `doi_tuong` ở từng dòng **giữ nguyên** (21 giá trị khác nhau). Bảng ánh xạ mỗi giá trị → `{tuoi_tu, tuoi_den, can_nang_tu, can_nang_den, dieu_kien_khac}`:

- Cận dưới gồm, cận trên không gồm; `null` là không giới hạn. Tuổi tính bằng năm; dưới 1 năm ghi số thập phân (29 ngày = 29/365 = 0.079; 3 tháng = 0.25).
- Tiêu chí không phải tuổi hay cân nặng ghi ở `dieu_kien_khac`: CrCl dưới 30, Child-Pugh C, nhiễm khuẩn đe doạ tính mạng, sarcoma xương, tuổi thai từ 32 tuần, nhồi máu cơ tim cấp ST chênh lên, điều kiện HOẶC của ketorolac.
- Nhãn không nói rõ "người lớn" từ bao nhiêu tuổi thì `tuoi_tu = 18`; trẻ em nhãn không nêu cận trên thì `tuoi_den = 18` (quy ước). Giải thích từng giá trị nằm ở `doi_tuong_dinh_nghia_ghi_chu` (khoá `_quy_uoc` và từng `doi_tuong`); ghi chú để riêng để mỗi định nghĩa giữ đúng 5 khoá.

Điểm biên cần dược sĩ xem: `nguoi_lon_tren_75_tuoi` (nhãn ">75", mô hình cận dưới gồm nên đặt 75), `tre_em_tren_40kg` (nhãn "> 40 kg", đặt 40), `nguoi_lon_va_thieu_nien_*` (nhãn không nêu tuổi thiếu niên, chỉ lọc theo cân nặng).

### 2.3. Soát T65-T66 hoàn thiện (19/11)

- Paracetamol: dòng "từ 50 kg" (`can_nang_tu: 50`, 4.000 mg/ngày) và "dưới 50 kg" (`can_nang_den: 50`, 75 mg/kg/ngày) **không chồng nhau** (cận dưới gồm, cận trên không gồm). Dòng trẻ 2 đến 12 tuổi cùng số 75 mg/kg/ngày nên chồng với dòng dưới 50 kg không gây mâu thuẫn.
- Gentamicin: dòng người lớn nhiễm khuẩn đe doạ tính mạng có `theo_kg.ngay_mg_kg = 5` và `quy_doi_don_vi[].can_can_nang = true`. Đạt.
- Mỗi trích dẫn là chuỗi con nguyên văn của tệp nhãn: 40/40 (Claude kiểm 19/11).

### 2.4. Số liệu và ba tình huống của plan

- 37 hoạt chất ca có đường dùng hợp lệ (37/37). 23 hoạt chất có dòng liều tối đa; 22 hoạt chất ở `khong_ghi_toi_da` (nhãn không ghi tối đa, để trống kèm lý do): amiodarone, amoxicillin, apixaban, cefoperazone, clarithromycin, clavulanic_acid, enoxaparin, esomeprazole, gabapentin, insulin_glargine, levofloxacin, meropenem, methotrexate, metoprolol, morphine, piperacillin, spironolactone, sulbactam, sulfamethoxazole, tazobactam, trimethoprim, warfarin (một số hoạt chất vẫn có dòng theo nhóm đặc biệt; xem `co_dong_theo_nhom_dac_biet`).
- Đối chiếu 66 ca: 31 `trong_gioi_han`, 1 `vuot_tran` (HS-019 paracetamol 1 g × 6 = 6.000 mg > 4.000 mg), 35 `khong_so_sanh`.
- Ba tình huống plan đã đủ dữ liệu: **levofloxacin** uống kê tiêm → `khong_hop_le`; **paracetamol** 1 g × 6 lần/ngày vượt 4 g/ngày; **gentamicin** theo kg: HS-026, HS-039, HS-059 so 5 mg/kg/ngày với cân nặng của ca đều `trong_gioi_han`, và khi bỏ cân nặng thì `khong_du_du_lieu`.
- Ba dòng `quy_doi_don_vi` không quy đổi được (`quy_doi_duoc: false`): sulfamethoxazole+trimethoprim trẻ em (ca ghi viên, nhãn mg), insulin glargine (ca ghi mg, nhãn units), colistimethate (ca ghi triệu đơn vị, nhãn mg/kg).

## 3. Việc còn mở

- Dược sĩ duyệt cả hai tệp.
- Nguồn Việt Nam thứ hai (TT 20, Dược thư) cho đường dùng; nhất là morphin tiêm dưới da.
- DAV nhiều sản phẩm không ghi rõ dạng (`dav_khong_ro_dang` trong `thong_ke`).
