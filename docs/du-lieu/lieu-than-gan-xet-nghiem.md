# Liều thận, suy gan, ngưỡng xét nghiệm, thuốc–bệnh (plan 1.8, đợt D4)

Cập nhật: 19/11/2026. Người ghi: sub Sonnet (task T65 và T65-T66 hoàn thiện). Bốn tệp dữ liệu nằm trong git (`data/kb/`), tất cả ở trạng thái **`cho_duoc_si_duyet`**: chưa có dược sĩ duyệt, app và DB chưa đọc khoá chờ duyệt cho tới khi có task chuyển.

| Mục | Giá trị |
|:--|:--|
| Tệp dữ liệu | `data/kb/quy_tac_lieu_than.json` (v0.3), `data/kb/quy_tac_gan.json` (D4-v1), `data/kb/nguong_xet_nghiem.json` (D4-v2), `data/kb/thuoc_benh_icd.json` (D4-v2) |
| Nguồn | Nhãn FDA (openFDA `drug/label`, kho `data/kb_sources/openfda/`, `data/kb_sources/t65/`); DDInter 2.0 `interact-with-dis` (`data/kb_staging/ddinter/tuong_tac_benh.jsonl`) cho thuốc–bệnh |
| Giấy phép | Nhãn FDA: public domain theo `meta.license` của openFDA. DDInter: CC BY-NC-SA 4.0, **chỉ sàng lọc**, không dùng thương mại |
| Tầng tin cậy | Nhãn FDA tầng 3; DDInter tầng sàng lọc. Mọi dòng chờ dược sĩ duyệt |
| Ngày lấy | Nhãn: 16 đến 19/11/2026 (ngày hiệu lực nhãn ghi ở `phien_ban_nguon`); DDInter: 18/11/2026 |
| Lệnh | Không có lệnh dựng trong app. Bảng dựng một lần từ tập lệnh tạm của T65 (câu trích cắt tự động từ tệp nhãn nên là chuỗi con nguyên văn); tập lệnh sửa/bổ sung ngày 19/11 nằm ở thư mục tạm, không đưa vào kho |

Không lấy từ UpToDate, Lexicomp, MIMS, Micromedex. Không có công thức Child-Pugh (chờ MDCalc).

## 1. `quy_tac_lieu_than.json` (liều theo CrCl)

Khoá cấp cao: `phien_ban` (`0.3`), `ghi_chu`, `quy_tac` (1 quy tắc **đã duyệt**: meropenem, không đụng), `quy_tac_cho_duyet` (17 quy tắc, cùng lược đồ với `quy_tac`, 51 mức, 19 hoạt chất tính cả tazobactam và trimethoprim theo phối hợp), `khong_co_nguong` (28 hoạt chất).

### 1.1. Mỗi quy tắc

| Trường | Ý nghĩa |
|:--|:--|
| `ten_quoc_te`, `hoat_chat_ids` | Tên INN và **khoá trên trục** `hoat_chat.hoat_chat_id` của `tra_cuu.sqlite`. Thuốc phối hợp: một bảng, khoá luật là thành phần đầu để không phát hiện đôi (`phoi_hop`) |
| `chi_so` | Ghi đúng `CrCl (Cockcroft-Gault)` hay `eGFR` như nhãn |
| `muc[]` | Các khoảng CrCl, xem 1.2 |
| `nguon_chi_tiet[]` | `loai`, `ten_nhan`, `set_id`, `phien_ban_nguon`, `tep`, `truong_nhan`, `trich_nguyen_van` (chuỗi con nguyên văn của tệp nhãn; Claude đã kiểm 24/24 ở liều thận, 24/24 ở gan, 15/15 ở xét nghiệm ngày 19/11), `url` (DailyMed), `ngay_lay` |
| `trang_thai`, `nguoi_duyet` | `cho_duoc_si_duyet`, `null` |
| `bi_danh`, `phoi_hop`, `ghi_chu` | Tên khác (paracetamol); giải thích phối hợp; điều dược sĩ cần biết |

### 1.2. Mỗi mức `muc[]`

| Trường | Ý nghĩa |
|:--|:--|
| `crcl_tu`, `crcl_den` | Cận dưới, cận trên (mL/phút); `null` là không giới hạn |
| `bao_gom_can_duoi` | `true`: `crcl >= crcl_tu`; `false`: `crcl > crcl_tu` |
| **`bao_gom_can_tren`** (mới, tuỳ chọn) | `true`: `crcl <= crcl_den`; `false`: `crcl < crcl_den`. Không ghi thì như cũ: `<=`, trừ mức có `crcl_tu = null` và `bao_gom_can_duoi = false` thì `<` |
| `can_chinh`, `khuyen_cao` | Có cần chỉnh liều, nội dung nhãn (tiếng Việt) |
| `nhan_ghi` | Khoảng nguyên văn của nhãn ("20 to 49", "Greater than 60") |
| `ghi_khoang` | Cách xử lý ranh giới khi nhãn nối liền khoảng nguyên (29 sang 30) hoặc tự chồng |
| `khong_co_so_lieu_nhan` | `true`: mức do chính tài liệu này điền cho kín khoảng, nhãn không có dữ liệu |

**Vì sao thêm `bao_gom_can_tren`.** Nhãn viết các khoảng liền nhau ("20 to 49", "10 to 19") hoặc chồng nhau ("30 to 60", "11 to 29"); mô hình cũ cho cả cận dưới và cận trên gồm nên chín điểm CrCl rơi vào hai mức cùng lúc. Đã đặt `bao_gom_can_tren: false` ở mức dưới của 6 hoạt chất:

| Hoạt chất | Điểm từng chồng | Mức sửa |
|:--|:--|:--|
| cefepime | 30 | "11–29" |
| levofloxacin | 20, 50 | "20 to 49" và "10 to 19" |
| gabapentin | 60 | ">30 to 59" |
| levetiracetam | 50 | "Moderate 30 to 50"; **nhãn tự chồng** (Mild 50 to 80), CrCl đúng 50 xếp vào mức nhẹ, có `ghi_khoang`, chờ dược sĩ |
| colistimethate | 30, 50, 80 | "…to 79", "…to 49", "…to 29" |
| simvastatin | 30 | "15–29" |

**Kiểm bằng code (19/11):** với 17 quy tắc, mọi giá trị CrCl từ 0 đến 150 bước 0,5: **0 điểm chồng, 0 điểm hở**.

### 1.3. `khong_co_nguong` (28 hoạt chất của 66 ca không có ngưỡng CrCl cắt trong `quy_tac`/`quy_tac_cho_duyet`)

Mỗi phần tử: `hoat_chat_id`, `loai`, `ly_do`, `set_id`, `url` (null nếu chưa có nhãn). Không tự đặt ngưỡng.

| `loai` | Số | Hoạt chất |
|:--|--:|:--|
| `khong_can_chinh` (nhãn nói không cần chỉnh hoặc không có mục thận) | 8 | amiodarone, ceftriaxone, linezolid, losartan, metoprolol, omeprazole, valproic_acid, warfarin |
| `chi_noi_chung` (chỉ "thận trọng / theo dõi", không có số) | 8 | amlodipine, esomeprazole, furosemide, ibuprofen, insulin_glargine, ketorolac, morphine, phenytoin |
| `bang_hoac_cong_thuc` (bảng liều theo CrCl hoặc công thức creatinin, không có ngưỡng cắt đơn; **chưa cài**) | 5 | amikacin, digoxin, gentamicin, sulbactam, vancomycin |
| `co_nguong_o_tep_khac` (ngưỡng nằm ở `nguong_xet_nghiem.json`) | 5 | amoxicillin, clavulanic_acid, apixaban, metformin, spironolactone |
| `chua_co_nhan` (chưa có nhãn FDA trong kho) | 2 | cefoperazone, penicillin_g |

**Lỗ hổng cần quyết định:** `sulbactam` (nhãn ampicillin/sulbactam Table 3: CrCl >= 30, 15 đến 29, 5 đến 14 chỉnh khoảng cách liều) có ngưỡng số rõ nhưng chưa được cài vào `quy_tac_cho_duyet` ở T65; cần task bổ sung nếu muốn luật chạy cho ampicillin/sulbactam. Bảng liều theo CrCl của digoxin, vancomycin cũng chưa cài (biểu theo từng bước 10).

### 1.4. Cách luật dùng

`app/rules/renal_dose.py` hiện chỉ đọc khoá `quy_tac`. `quy_tac_cho_duyet` chỉ được đọc sau khi dược sĩ duyệt và có task chuyển sang `quy_tac`. Luật T67 đọc `bao_gom_can_tren` theo ngữ nghĩa ở 1.2.

## 2. `quy_tac_gan.json` (suy gan theo nhãn)

24 dòng, 22 hoạt chất. Chỉ ghi điều nhãn FDA nói về suy gan, kèm trích nguyên văn. **Không cài công thức Child-Pugh.**

| Trường | Ý nghĩa |
|:--|:--|
| `ten_quoc_te`, `hoat_chat_ids` | Như 1.1 |
| `phan_loai_gan[]` | `child_pugh_A`, `child_pugh_B`, `child_pugh_C` khi nhãn ghi theo Child-Pugh; `nhe_vua`, `nang` khi nhãn ghi theo mô tả; `khong_phan_loai` khi nhãn chỉ nói suy gan chung |
| `hanh_dong_nhan` | `chong_chi_dinh`, `tranh_khong_khuyen_cao`, `giam_lieu`, `theo_doi`, `khong_chinh_lieu`, `khong_co_khuyen_cao_cu_the` |
| `khuyen_cao` | Tóm tắt tiếng Việt |
| `nguon_chi_tiet[]` | Như 1.1 |
| `trang_thai` | `cho_duoc_si_duyet` |

Số liệu: `phan_loai_gan` `khong_phan_loai` 14, Child-Pugh C 4, B 3, A 2, `nang` 3, `nhe_vua` 1; `hanh_dong_nhan` `giam_lieu` 7, `khong_chinh_lieu` 5, `theo_doi` 4, `tranh_khong_khuyen_cao` 3, `chong_chi_dinh` 3, `khong_co_khuyen_cao_cu_the` 2. Luật T67 đọc tệp này (chưa gắn công thức gan nên chỉ báo "cần xem" khi ca có chẩn đoán/xét nghiệm gan).

## 3. `nguong_xet_nghiem.json` (D4-v2)

15 dòng, 9 hoạt chất (10 `hoat_chat_ids` tính cả clavulanic_acid), phân theo `xet_nghiem` (`egfr` 5, `inr` 2, `creatinin` 2, `digoxin` 2, `tieu_cau` 1, `kali` 1, `natri` 1, `phenytoin` 1). Chỉ lấy ngưỡng có số trong nhãn FDA.

### 3.1. Mỗi dòng

| Trường | Ý nghĩa |
|:--|:--|
| `ten_quoc_te`, `hoat_chat_ids`, `xet_nghiem` | `xet_nghiem` là mã xét nghiệm trong ca (`ma_xet_nghiem`). `tieu_cau` và `natri` **chưa có trong 66 ca**, giữ dòng với mã dự kiến |
| `dieu_kien[]` | Xem 3.2 |
| **`kieu_dieu_kien`** (mới, bắt buộc) | `canh_bao_khi_thoa`: điều kiện đúng thì cảnh báo (12 dòng). `canh_bao_khi_ngoai_khoang`: `dieu_kien` là khoảng đích, giá trị ngoài khoảng thì cảnh báo (warfarin INR 2–3, phenytoin 10–20; 2 dòng). `dieu_kien_khoi_dau`: nhãn chỉ cho bắt đầu khi điều kiện đúng, sai thì cảnh báo (spironolacton K+ ≤ 5,0 và eGFR > 50; 1 dòng) |
| **`muc_do_de_xuat`** (mới, bắt buộc) | `nghiem_trong` (nhãn dùng chống chỉ định, "should NOT", "discontinue"; 3 dòng: enoxaparin tiểu cầu, metformin eGFR < 30, amoxicillin GFR < 30 với viên 875 mg) hoặc `can_luu_y` (theo dõi, cân nhắc, giảm liều, "not recommended"; 12 dòng). Đề xuất, chờ dược sĩ duyệt |
| **`dieu_kien_khac`** (mới, tuỳ chọn, 9 dòng) | Tiêu chí không phải xét nghiệm trong cùng câu nhãn (suy tim, chỉ định huyết khối tĩnh mạch, viên 875 mg, apixaban cần 2 trong 3 tiêu chí tuổi, cân nặng, creatinin). Luật chỉ báo "cần xem, đối chiếu thêm", không kết luận từ xét nghiệm một mình |
| `hanh_dong_nhan`, `don_vi_nhan`, `don_vi_trong_ca`, `quy_doi`, `ghi_chu` | Giữ như cũ: hành động nhãn nêu bằng tiếng Việt; mô tả đơn vị bằng chữ; ghi chú |
| `nguon_chi_tiet[]` | Như 1.1 |
| `trang_thai` | `cho_duoc_si_duyet` |

### 3.2. Mỗi phần tử `dieu_kien[]`

| Trường | Ý nghĩa |
|:--|:--|
| `ma_xet_nghiem`, `toan_tu`, `gia_tri`, `gia_tri_den` | `toan_tu`: `<`, `<=`, `>`, `>=`, `khoang` (`gia_tri` đến `gia_tri_den`, gồm hai đầu) |
| **`don_vi_nhan`** (mới) | Đơn vị của `gia_tri` như nhãn; `null` nếu không đơn vị (INR) |
| **`don_vi_ca`** (mới) | Đúng chuỗi `don_vi` của xét nghiệm trong ca; INR trong ca ghi `""` hoặc `null` nên để `null`; `tieu_cau`, `natri` là đơn vị dự kiến |
| **`he_so_ca_sang_nhan`** (mới) | Nhân giá trị ca để ra đơn vị nhãn |

Bảng đơn vị đã kiểm kê trong 66 ca: creatinin `umol/L`, kali `mmol/L`, egfr `mL/phút/1,73m2`, inr `""`/`null`, digoxin `ng/mL`, phenytoin `mcg/mL`, glucose `mmol/L`, alt/ast `U/L`.

| Xét nghiệm | `don_vi_nhan` | `don_vi_ca` | `he_so_ca_sang_nhan` | Nguồn hệ số |
|:--|:--|:--|--:|:--|
| creatinin | mg/dL | umol/L | 0.011312 (= 1/88,4) | `app/calc/units.py` (88,4), ghi ở `ghi_chu` các dòng enalapril và apixaban |
| kali, natri | mEq/L | mmol/L | 1 | ion hoá trị 1, số không đổi |
| egfr | mL/min/1.73 m2 | mL/phút/1,73m2 | 1 | cùng đại lượng, hai cách viết |
| egfr (dòng amoxicillin) | mL/min | mL/phút/1,73m2 | 1 | nhãn ghi GFR mL/min; chưa rõ nên dùng CrCl hay eGFR, **dược sĩ chốt** |
| tieu_cau | /mm3 | G/L | 1000 | 1 G/L = 10^9/L = 1.000/mm3 (đổi đơn vị thuần tuý), ghi ở `ghi_chu` dòng enoxaparin |
| inr | `null` | `null` | 1 | không đơn vị |
| digoxin, phenytoin | ng/mL, mcg/mL | giống nhãn | 1 | khớp |

### 3.3. Giới hạn

- Glucose với insulin, ALT/AST với thuốc độc gan: **chưa có dòng**; T65 không đưa được ngưỡng số có trích dẫn từ nhãn trong kho, và lượt hoàn thiện này không kiểm lại. Không bịa ngưỡng.
- Dòng enalapril natri và creatinin lấy từ cùng một câu nhãn (một trong hai là đủ); hai dòng tách để mỗi dòng chỉ một xét nghiệm.

## 4. `thuoc_benh_icd.json` (D4-v2, thuốc–bệnh DDInter sang ICD-10)

| Khoá | Nội dung |
|:--|:--|
| `anh_xa` (119) | Mỗi `ten_benh` của DDInter liên quan hoạt chất trong ca → `ma_icd10` (danh sách mã 3 ký tự, 3 ký tự kèm thập phân, hoặc khoảng "D50-D64"), `khong_anh_xa` (2 tên bệnh không có mã: Coumarin Resistance, Coumarin Sensitivity), `hoat_chat_ids`, `so_dong_ddinter`, `muc_do_cao_nhat`. Làm tay, chưa dược sĩ duyệt |
| **`cap_thuoc_benh`** (mới, 300 dòng) | Mọi dòng DDInter `tuong_tac_benh.jsonl` có hoạt chất thuộc 66 ca, để **luật chỉ đọc `data/kb`**, không đọc `data/kb_staging` (không có trên git/CI). Phần tử: `hoat_chat_id`, `ddinter_id`, `ten_benh`, `ma_icd10` (từ `anh_xa` theo `ten_benh`; bệnh `khong_anh_xa` thì `[]`), `muc_do` (Major 153, Moderate 147), `noi_dung` (nguyên văn DDInter, cắt 600 ký tự thêm "…"), `url` (`url_goc`), `trang_thai` |
| `cap_khop_chan_doan_ca` (13) | Cặp (ca, hoạt chất, bệnh, mã ICD của ca) khớp chẩn đoán |
| `thong_ke` | Số liệu, xem dưới |

Số liệu: 300 dòng, 40 hoạt chất có dòng thuốc–bệnh (trong 48 hoạt chất của ca; penicillin G và sulbactam không có mã DDInter), 2 dòng `ma_icd10` rỗng, 119 tên bệnh. Chuyển mã DDInter → `hoat_chat_id` qua cột `hoat_chat.ddinter_id` trong `data/kb_curated/tra_cuu/tra_cuu.sqlite`; 46 mã DDInter thuộc hoạt chất ca.

**Quy tắc khớp mã ca:** mã trong `anh_xa` có thập phân (Z49.1, N18.5) thì so tiền tố với mã chẩn đoán của ca; mã 3 ký tự hoặc khoảng thì so 3 ký tự đầu. Tính lại `cap_khop_chan_doan_ca` từ `cap_thuoc_benh` theo quy tắc này: **13 dòng, trùng 13/13** với dòng đang có (9 ca, 10 cặp hoạt chất–bệnh).

Giới hạn: DDInter chỉ để sàng lọc, không thay nhãn FDA; ánh xạ ICD chưa dược sĩ duyệt.

## 5. Kiểm kê 66 ca (T65 việc 5, `load_source_cases`)

| Nhóm | Số ca | Ca |
|:--|--:|:--|
| Đủ trường để tính CrCl (tuổi, giới, cân nặng, creatinin kèm đơn vị `umol/L`) | **51** | các ca còn lại |
| Thiếu creatinin | 15 | HS-007, 010, 013, 015, 019, 020, 023, 029, 032, 034, 039, 040, 042, 043, 055 |
| Thiếu cân nặng | 1 | HS-040 (cũng thiếu creatinin) |
| Có xét nghiệm gan (alt, ast, bilirubin) | 5 | HS-009 (ALT), HS-019 (ALT), HS-023 (ALT), HS-028 (ALT, AST), HS-029 (ALT, AST, bilirubin) |
| Trẻ em dưới 18 tuổi | 5 | HS-007, 013, 020, 040, 055 (Cockcroft-Gault không dùng cho trẻ em; cả 5 đều thiếu creatinin) |
| Từ 65 tuổi | 23 | trong đó từ 75 tuổi: 6 |
| Mang thai | 2 | HS-030 (có), HS-041 (chưa rõ); HS-002 ghi không mang thai |
| Cho con bú | 1 | HS-033 |
| Hậu phẫu / hậu sản | 1 | HS-033 (`hau_phau`, hậu sản ngày 3 sau mổ lấy thai; cũng là ca cho con bú) |
| Suy thận ghi trong `co_dia` | 3 | HS-026, HS-027, HS-028 (có mức CrCl hoặc eGFR ghi chữ) |

(Số ca đủ CrCl chỉ nói đủ trường dữ liệu; không phải đã kiểm giá trị hợp lý.)

## 6. Việc còn mở

- Dược sĩ duyệt cả bốn tệp (`nguoi_duyet`, `trang_thai`).
- Quyết định có cài `sulbactam`, bảng digoxin, vancomycin, aminoglycoside vào `quy_tac_cho_duyet` không.
- Levetiracetam điểm 50; chỉ số của amoxicillin (GFR hay CrCl); `muc_do_de_xuat` các dòng "not recommended" (đang `can_luu_y`).
- Ngưỡng glucose/insulin và ALT/AST chưa có nguồn số trong nhãn đã tải.
