# Bảng độc tính (D6) và kháng sinh quản lý (D7) (plan 1.8, đợt D6 và D7)

Cập nhật: 19/11/2026. Người ghi: sub Sonnet (task T70), đọc nhãn FDA, chuyên luận LiverTox và QĐ 5631 đã có trong kho; không gọi mạng.

| Mục | Giá trị |
|:--|:--|
| Tệp dữ liệu | `data/kb/doc_tinh.json` (D6-v1) và `data/kb/khang_sinh_quan_ly.json` (D7-v1); trong git, bảng quy tắc nhỏ để dược sĩ duyệt |
| Nguồn | D6: nhãn FDA (openFDA, `data/kb_sources/openfda`, `openfda_d5`, `t65`) và LiverTox NXML (`data/kb_sources/livertox/giai_nen`). D7: QĐ 5631/QĐ-BYT ngày 31/12/2020, bản sao thứ cấp Duy Tân (`data/kb_sources/van_ban_byt/qd5631_2020`) |
| Giấy phép | Nhãn FDA public domain theo `meta.license`; LiverTox cần ghi nguồn NIDDK/NLM (xem [livertox.md](livertox.md)); văn bản BYT công khai (xem [van-ban-byt.md](van-ban-byt.md)) |
| Tầng tin cậy | Nhãn FDA và LiverTox tầng 3; QĐ 5631 tầng 1 nhưng là bản sao thứ cấp. **Mọi dòng `cho_duoc_si_duyet`, chưa có dược sĩ duyệt** |
| Ngày lấy | `ngay_lay` 2026-11-19 (ngày dựng bảng; nhãn tải 16 đến 19/11) |
| Lệnh | Không có lệnh dựng trong app. Dựng một lần từ tập lệnh tạm (không nằm trong kho). Câu trích được cắt tự động từ tệp nguồn, kiểm lại bằng chương trình là chuỗi con sau khi gộp khoảng trắng |

Phạm vi: 43 hoạt chất (khoá trên trục `hoat_chat.hoat_chat_id` của `tra_cuu.sqlite`) có trong 66 ca, lấy bằng `load_source_cases` và bảng `chuyen_ma_ca`. Không suy từ kiến thức chung: không thấy câu nguồn thì không ghi.

## 1. `doc_tinh.json`

Khoá cấp cao: `phien_ban`, `ngay`, `trang_thai`, `ghi_chu`, `doc_than`, `keo_dai_qt`, `khoang_dieu_tri_hep`, `doc_gan_livertox`, `khong_co_nguon`.

| Danh sách | Số dòng | Điều kiện đưa vào | Trường riêng |
|:--|--:|:--|:--|
| `doc_than` | 7 | Nhãn nêu chính thuốc gây độc thận / tổn thương thận ở boxed warning hoặc warnings: gentamicin, vancomycin, colistimethate, ibuprofen, ketorolac, methotrexate, piperacillin (nhãn piperacillin-tazobactam) | `nhom` (do người dựng đặt) |
| `keo_dai_qt` | 4 | Nhãn nêu kéo dài QT / torsades ở boxed warning hoặc warnings and precautions: amiodarone, clarithromycin, fluconazole (nhãn dạng cũ, mục Precautions), levofloxacin | `muc_nhan` |
| `khoang_dieu_tri_hep` | 5 | Nhãn khuyến cáo đo nồng độ thuốc: vancomycin, gentamicin, valproic_acid, digoxin, phenytoin | `ma_xet_nghiem_nong_do` (mã dự kiến; trong 66 ca chỉ có `digoxin`, `phenytoin`; `vancomycin`, `gentamicin`, `valproat` chưa có). Không ghi khoảng đích (đã ở `nguong_xet_nghiem.json`) |
| `doc_gan_livertox` | 38 | Dòng "Likelihood score" của chuyên luận LiverTox | `likelihood_score` (chữ cái; hậu tố [H]/[HD] của insulin và acetaminophen nằm trong câu trích) |
| `khong_co_nguon` | 36 | Thiếu nhãn / chương, hoặc loại trừ có lý do | `danh_sach`, `ly_do` |

Phần tử `nguon`: `loai` (`nhan_fda` hoặc `livertox`), `ten_nhan`, `tep`, `truong_nhan`, `trich_nguyen_van`, `url`, `ngay_lay`. Chỉ nhãn có `set_id`, `phien_ban_nguon` (ngày hiệu lực). Chỉ LiverTox có `ma_chuyen_luan` (NXML không có mã NBK riêng cho từng chương nên `url` là trang sách NBK547852).

Điểm cần biết:
- Thuốc có câu về thận nhưng cơ chế gián tiếp (huyết động, miễn dịch, tắc nghẽn, tương tác) **không** vào `doc_than`: 16 dòng ở `khong_co_nguon` với `danh_sach=doc_than` (warfarin, simvastatin, omeprazole, esomeprazole, losartan, enalapril, ceftriaxone, levofloxacin, clarithromycin, fluconazole, spironolactone, furosemide, sulfamethoxazole, amiodarone, rivaroxaban, amoxicillin). Dược sĩ quyết định có mở rộng không.
- Thành phần không có nhãn đơn chất (cefoperazone, sulbactam, clavulanic_acid, trimethoprim, tazobactam) ghi ở `khong_co_nguon`. Tazobactam không lặp câu độc thận của piperacillin để một y lệnh không bị đếm hai lần.
- LiverTox: chương nhóm (digoxin, enoxaparin, furosemide, cefoperazone) là điểm của nhóm; clavulanic_acid, piperacillin, sulfamethoxazole dùng chương phối hợp. Esomeprazole, colistimethate, sulbactam, trimethoprim, tazobactam không có điểm riêng (ghi ở `khong_co_nguon`).
- Không dùng openFDA `drug/event` (FAERS).

## 2. `khang_sinh_quan_ly.json`

Khoá cấp cao: `phien_ban`, `ngay`, `trang_thai`, `nguon_van_ban`, `ghi_chu`, `nhom`, `khang_sinh`, `khong_anh_xa`.

| Danh sách | Số dòng | Nội dung |
|:--|--:|:--|
| `nhom` | 2 | `phe_duyet_truoc` = "Kháng sinh cần ưu tiên quản lý – Nhóm 1" (yêu cầu trích nguyên văn tr.5-6: danh mục áp dụng quy định hội chẩn, phê duyệt trước; thời gian duyệt trước khi dùng hoặc 24 đến 48 giờ khi cấp cứu; không quá 14 ngày mỗi lần duyệt; người được ủy quyền duyệt). `theo_doi_giam_sat` = "Kháng sinh cần theo dõi, giám sát sử dụng – Nhóm 2" (chỉ khuyến khích giám sát, không yêu cầu phê duyệt) |
| `khang_sinh` | 32 | 20 hoạt chất Nhóm 1 và 12 Nhóm 2, mỗi tên trong ngoặc của dòng nhóm là một dòng; `trang_pdf` 17 đến 19 |
| `khong_anh_xa` | 13 | Amphotericin B (3 dạng bào chế, trục không tách dạng) và 10 thuốc mới chưa có trên trục (ceftobiprol, cefiderocol, dalbavancin, dalfopristin-quinupristin, eravacyclin, omadacyclin, oritavancin, plazomicin, tedizolid, telavancin) |

Điểm cần biết:
- `ma_nhom` do người dựng đặt; tên nhóm (`ten_nhom_van_ban`) đúng tên Phụ lục 2. Văn bản ghi các bệnh viện **tuỳ theo hạng** xây dựng danh mục và quy định phê duyệt; ba cột "+"/"-" theo hạng bệnh viện ở Phụ lục 2 là việc xây dựng hướng dẫn sử dụng, chưa trích theo từng thuốc.
- Chú thích *** (carbapenem): khoa truyền nhiễm, cấp cứu, hồi sức tích cực, gây mê hồi sức của bệnh viện tuyến trung ương không cần phê duyệt trước. Chép nguyên văn ở `ghi_chu`; chưa mã hoá theo khoa.
- Chữ pdf: `pdftotext` làm mất dấu, đọc bằng `pdfplumber`; ký tự "ƣ/Ƣ" đã đổi thành "ư/Ư" (ghi trong `ghi_chu`).
- Ánh xạ: Colistin → `colistimethate`; "neltimicin" (viết sai) → `netilmicin`; "anidulafundin" → `anidulafungin`; ceftolozan-tazobactam chỉ gán `ceftolozane`, ceftazidim-avibactam chỉ gán `avibactam` để ceftazidime / tazobactam dùng riêng không bị gắn nhầm.

## 3. Số ca theo 66 ca (ngày 19/11/2026)

Tính trên hoạt chất của y lệnh chờ duyệt cộng thuốc đang dùng còn hiệu lực.

| Tình huống | Số ca |
|:--|--:|
| ≥ 2 thuốc `doc_than` | 2 (HS-017 ibuprofen + ketorolac; HS-028 ibuprofen + methotrexate); 8 ca chỉ 1 thuốc |
| ≥ 2 thuốc `keo_dai_qt` | 0; 8 ca có đúng 1 thuốc (levofloxacin 3, clarithromycin 2, amiodarone 2, fluconazole 1) |
| Có thuốc `khoang_dieu_tri_hep` mà thiếu xét nghiệm nồng độ | 7 (vancomycin 3, gentamicin 3, valproic_acid 1); digoxin và phenytoin đều có xét nghiệm |
| Có kháng sinh `phe_duyet_truoc` | 7 (meropenem 3, vancomycin 3, colistimethate 1) |
| Có kháng sinh `theo_doi_giam_sat` | 6 (levofloxacin 3, gentamicin 3) |

Không có ca gentamicin + vancomycin (tình huống mẫu của plan D6), nên ca dương tính cho luật cộng dồn độc thận kiểu aminoglycosid + vancomycin phải tạo thêm.

## 4. Kiểm lại

- Câu trích: mọi `trich_nguyen_van` (59 nguồn) là chuỗi con của tệp nguồn sau khi gộp khoảng trắng; câu nhãn FDA nằm đúng trường `truong_nhan` và khớp `set_id`; `yeu_cau` của D7 là chuỗi con của pdf tr.5-6 sau khi đổi "ƣ" thành "ư".
- Mọi `hoat_chat_id` có trên trục `tra_cuu.sqlite`.
- Luật đọc: `load_toxicity_config()` (D6) và `load_stewardship_config()` (D7) nạp được hai tệp.
