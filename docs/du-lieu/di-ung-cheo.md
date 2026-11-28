# Bảng dị ứng chéo theo nhóm (plan 1.8, đợt D3)

Cập nhật: 19/11/2026. Người ghi: sub Sonnet (task T60), đọc dữ liệu thực và gọi openFDA, Europe PMC, Crossref.

| Mục | Giá trị |
|:--|:--|
| Tệp dữ liệu | `data/kb/di_ung_cheo.json` (trong git; bảng quy tắc nhỏ để dược sĩ duyệt) |
| Nguồn | Nhãn FDA (openFDA `drug/label`, mục chống chỉ định, cảnh báo, thận trọng) và bài tổng quan có DOI/PMID mở được |
| Giấy phép | Nhãn FDA: public domain theo `meta.license` của openFDA. Bài tổng quan: chỉ trích câu ngắn nguyên văn kèm DOI, không sao chép nội dung |
| Tầng tin cậy | Nhãn FDA tầng 3; tổng quan tầng bài báo. **Mọi dòng `cho_duoc_si_duyet`, chưa có dược sĩ duyệt** |
| Ngày lấy | 19/11/2026 (nhãn mới và bài báo); nhãn đã có sẵn trong kho lấy 16 đến 17/11 |
| Lệnh | Không có lệnh dựng trong app. Nhãn mới tải bằng gọi openFDA (≤ 2 yêu cầu/giây, không khoá) vào `data/kb_sources/openfda_d3/`; bảng dựng một lần từ tập lệnh tạm của T60 (đánh dấu: câu trích được cắt tự động từ nhãn nên nguyên văn) |

Không lấy từ UpToDate, Lexicomp, MIMS, Micromedex.

## 1. Cấu trúc tệp

Tệp gốc có các khoá cấp cao: `ten`, `phien_ban` (`D3-v1`), `ngay`, `trang_thai`, `y_nghia_muc_cheo`, `y_nghia_muc_canh_bao_nhan`, `huong_giai_thich`, `ten_nhom_di_ung_sang_hoat_chat`, `nhom`.

### 1.1. Mỗi phần tử của `nhom` (26 dòng)

| Trường | Ý nghĩa | App dùng? |
|:--|:--|:--|
| `ma_nhom` | Mã nhóm, dạng `BL01_...` (beta-lactam), `SU..` (sulfonamid), `NS..` (NSAID), `AED..`, `AG..`, `FQ..`, `MAC..`, `TP..`, `PPI..` | ❌ chưa; luật D3 sẽ dùng |
| `ten_nhom` | Tên tiếng Việt | ❌ hiển thị sau |
| `hoat_chat_ids` | Tác nhân gây dị ứng thuộc nhóm. **Khoá trên trục** `hoat_chat.hoat_chat_id` của `tra_cuu.sqlite` | ❌ |
| `hoat_chat_lien_quan` | Danh sách `{hoat_chat_ids, muc_cheo, muc_canh_bao_nhan, ly_do}`: hoạt chất có nguy cơ chéo khi dị ứng một chất trong `hoat_chat_ids` | ❌ |
| `huong` | `hai_chieu` hoặc `mot_chieu`; xem 1.3 | ❌ |
| `co_so` | Cơ sở (R1, cấu trúc, cơ chế) | ❌ |
| `nguon` | Danh sách nguồn, xem 1.2 | ❌ |
| `ghi_chu` | Điều dược sĩ cần biết, kể cả mâu thuẫn giữa nguồn | ❌ |
| `trang_thai` | Luôn `cho_duoc_si_duyet` | ❌ |

`muc_cheo` (cao, thap, rat_thap):
- `cao`: cùng khung hoặc cùng chuỗi bên quyết định kháng nguyên, hoặc nhãn FDA nêu tỷ lệ chéo đáng kể.
- `thap`: có ghi nhận chéo hoặc nhãn cảnh báo thận trọng, xác suất vừa hoặc chưa định lượng.
- `rat_thap`: tổng quan cho thấy chéo hiếm hoặc không do cấu trúc; vẫn có thể có cảnh báo nhãn.

`muc_canh_bao_nhan`: `chong_chi_dinh` (nhãn FDA nêu ở mục chống chỉ định), `than_trong` (nêu ở cảnh báo hoặc thận trọng), `khong_neu`. Trường này tách khỏi `muc_cheo` vì nhãn và tổng quan có thể không khớp (ví dụ celecoxib với sulfonamid, xem SU03).

### 1.2. Phần tử của `nguon`

| Trường | Ý nghĩa |
|:--|:--|
| `loai` | `nhan_fda` hoặc `tong_quan` |
| `trich_nguyen_van` | Câu gốc tiếng Anh. Nhãn: cắt tự động từ tệp nhãn, nên là chuỗi con nguyên văn. Tổng quan: câu trong tóm tắt hoặc toàn văn, đã kiểm lại bằng chương trình |
| `url` | Nhãn: trang DailyMed theo `set_id`. Tổng quan: DOI hoặc PMC |
| `ngay_lay` | Ngày lấy |
| Chỉ có ở nhãn | `set_id`, `phien_ban_nguon` (ngày hiệu lực nhãn), `ten_nhan`, `tep` (tệp nhãn trong kho), `url_api` (truy vấn openFDA), `muc_nhan` (`chong_chi_dinh`, `than_trong`, `khong_neu`) |
| Chỉ có ở tổng quan | `tieu_de`, `nam`, `pmid`, `doi`, `doi_url`, `cach_mo` |

### 1.3. Hướng

- `hai_chieu`: dị ứng bất kỳ chất nào trong `hoat_chat_ids` thì cảnh báo với các chất trong `hoat_chat_lien_quan` (tập tác nhân và tập liên quan là một).
- `mot_chieu`: chỉ từ `hoat_chat_ids` sang `hoat_chat_lien_quan`. Chiều ngược của các cặp có R1 giống nhau đã nằm ở dòng `hai_chieu` (BL02, BL03, BL07, BL12). Chiều ngược của cặp khác (cephalosporin → penicillin, carbapenem → penicillin, lamotrigine → thuốc chống động kinh khác...) **chưa có dòng**, dược sĩ quyết định có thêm không.
- Một cặp có thể xuất hiện ở nhiều dòng (ví dụ BL02 và BL04). **Lấy `muc_cheo` cao nhất**, ghi tất cả nguồn.

### 1.4. `ten_nhom_di_ung_sang_hoat_chat`

Bệnh án hay ghi dị ứng theo **tên nhóm** ("Penicillin", "Sulfonamid", "NSAID"), mà bộ phân giải `DrugResolver.resolve_name` không nhận tên nhóm (xem 3.2). Bảng này ánh xạ tên nhóm viết thường, bỏ dấu cách thừa → `{ma_nhom, hoat_chat_ids}`. Hiện có 8 khoá: `penicillin`, `sulfonamid`, `sulfonamide`, `cephalosporin`, `nsaid`, `aminoglycosid`, `macrolid`, `quinolon`. Đây là bảng của T60, **chưa qua dược sĩ duyệt**.

## 2. Các nhóm hiện có (26)

Cột "Số chất" là số hoạt chất tác nhân → số hoạt chất liên quan; cột mức là `muc_cheo/muc_canh_bao_nhan` của từng mục liên quan.

| Mã | Tên | Số chất | Hướng | Mức | Nguồn |
|:--|:--|:-:|:-:|:--|:--|
| `BL01_PENICILLIN_NOI_NHOM` | Penicillin: dị ứng một penicillin thì tránh cả nhóm penicillin | 8 → 8 | hai_chieu | cao/chong_chi_dinh | 2 nhãn, 0 tổng quan |
| `BL02_AMINOPEN_AMINOCEPH_AMOX` | Amoxicillin ↔ cephalosporin cùng chuỗi bên R1 (cefadroxil, cefprozil) | 3 → 3 | hai_chieu | cao/than_trong | 1 nhãn, 2 tổng quan |
| `BL03_AMINOPEN_AMINOCEPH_AMP` | Ampicillin ↔ cephalosporin cùng chuỗi bên R1 (cephalexin, cefaclor) | 3 → 3 | hai_chieu | cao/than_trong | 1 nhãn, 2 tổng quan |
| `BL04_PEN_CEPH_R1_TUONG_TU` | Penicillin ↔ aminocephalosporin có R1 tương tự (không giống hệt) | 8 → 4 | mot_chieu | thap/than_trong | 2 nhãn, 1 tổng quan |
| `BL05_PEN_CEPH_R1_KHAC` | Penicillin ↔ cephalosporin có R1 khác penicillin (ceftriaxone, cefuroxime, cefepime...) | 8 → 22 | mot_chieu | thap/than_trong | 2 nhãn, 1 tổng quan |
| `BL06_PEN_CEFAZOLIN` | Penicillin ↔ cefazolin (R1 riêng, không trùng beta-lactam nào) | 8 → 1 | mot_chieu | rat_thap/than_trong | 1 nhãn, 1 tổng quan |
| `BL07_CEPH_R1_OXIM` | Cephalosporin cùng chuỗi bên methoxyimino (ceftriaxone, cefotaxime, cefepime, cefpodoxime...) | 7 → 7 | hai_chieu | cao/than_trong | 1 nhãn, 2 tổng quan |
| `BL08_CEPH_NOI_LOP` | Cephalosporin: dị ứng một cephalosporin thì thận trọng với cephalosporin khác | 27 → 27 | hai_chieu | thap/chong_chi_dinh | 2 nhãn, 1 tổng quan |
| `BL09_PEN_CARBAPENEM` | Penicillin ↔ carbapenem | 8 → 4 | mot_chieu | rat_thap/than_trong | 2 nhãn, 1 tổng quan |
| `BL10_CEPH_CARBAPENEM` | Cephalosporin ↔ carbapenem, monobactam | 27 → 5 | mot_chieu | rat_thap/than_trong | 1 nhãn, 1 tổng quan |
| `BL11_PEN_AZTREONAM` | Penicillin ↔ aztreonam (monobactam) | 8 → 1 | mot_chieu | rat_thap/than_trong | 1 nhãn, 1 tổng quan |
| `BL12_CEFTAZIDIME_AZTREONAM` | Ceftazidime ↔ aztreonam (cùng chuỗi bên R1) | 2 → 2 | hai_chieu | cao/than_trong | 1 nhãn, 1 tổng quan |
| `SU01_SULFONAMID_KHANG_KHUAN` | Sulfonamid kháng khuẩn (sulfamethoxazole, sulfasalazine) | 2 → 2 | hai_chieu | cao/chong_chi_dinh | 2 nhãn, 0 tổng quan |
| `SU02_SULFONAMID_KHONG_KHANG_KHUAN` | Sulfonamid kháng khuẩn ↔ sulfonamid không kháng khuẩn (furosemide, thiazide): chéo hiếm, không do cấu trúc | 2 → 2 | mot_chieu | rat_thap/than_trong | 1 nhãn, 1 tổng quan |
| `SU03_SULFONAMID_CELECOXIB` | Sulfonamid kháng khuẩn ↔ celecoxib (nhãn chống chỉ định) | 2 → 1 | mot_chieu | rat_thap/chong_chi_dinh | 2 nhãn, 1 tổng quan |
| `NS01_NSAID_COX1` | NSAID không chọn lọc: phản ứng chéo do ức chế COX-1 (hen, mày đay sau aspirin hoặc NSAID) | 11 → 11 | hai_chieu | cao/chong_chi_dinh | 3 nhãn, 0 tổng quan |
| `NS02_NSAID_COX2` | NSAID không chọn lọc ↔ celecoxib | 11 → 1 | mot_chieu | thap/chong_chi_dinh | 2 nhãn, 0 tổng quan |
| `AED01_CBZ_OXC` | Carbamazepine ↔ oxcarbazepine | 2 → 2 | hai_chieu | cao/than_trong | 1 nhãn, 1 tổng quan |
| `AED02_CBZ_PHT_PB` | Carbamazepine ↔ phenytoin, phenobarbital | 3 → 3 | hai_chieu | cao/than_trong | 2 nhãn, 1 tổng quan |
| `AED03_LTG` | Lamotrigine ↔ thuốc chống động kinh nhân thơm khác | 5 → 1 | mot_chieu | thap/khong_neu | 1 nhãn, 1 tổng quan |
| `AED04_CBZ_TRICYCLIC` | Carbamazepine ↔ thuốc chống trầm cảm ba vòng | 1 → 1 | mot_chieu | thap/chong_chi_dinh | 1 nhãn, 0 tổng quan |
| `AG01_AMINOGLYCOSID` | Aminoglycoside: dị ứng một thuốc thì tránh cả nhóm | 6 → 6 | hai_chieu | cao/chong_chi_dinh | 2 nhãn, 0 tổng quan |
| `FQ01_QUINOLON` | Fluoroquinolone: dị ứng một thuốc thì tránh cả nhóm | 5 → 5 | hai_chieu | cao/chong_chi_dinh | 1 nhãn, 0 tổng quan |
| `MAC01_MACROLID` | Macrolid: dị ứng một thuốc thì tránh cả nhóm | 4 → 4 | hai_chieu | cao/chong_chi_dinh | 1 nhãn, 0 tổng quan |
| `TP01_THIENOPYRIDIN` | Thienopyridine (clopidogrel, ticlopidine, prasugrel) | 3 → 3 | hai_chieu | cao/than_trong | 1 nhãn, 0 tổng quan |
| `PPI01_BENZIMIDAZOL` | Thuốc ức chế bơm proton (benzimidazole thế) | 5 → 5 | hai_chieu | cao/chong_chi_dinh | 1 nhãn, 0 tổng quan |

Các nhóm chia theo ba yêu cầu của plan:

- **Beta-lactam theo chuỗi bên R1** (BL02, BL03, BL07, BL12): amoxicillin cùng R1 với cefadroxil và cefprozil; ampicillin cùng R1 với cephalexin và cefaclor; ceftriaxone, cefotaxime, cefepime, cefpodoxime cùng R1; ceftazidime cùng R1 với aztreonam. Danh sách này đọc từ bảng 1 của Chaudhry 2019 (PMC6789778), cột "R1 giống hệt".
- **Penicillin ↔ carbapenem** (BL09) và **penicillin ↔ aztreonam** (BL11): `rat_thap` theo tổng quan; nhãn carbapenem vẫn ghi thận trọng.
- **Sulfonamid kháng khuẩn** (SU01) tách khỏi sulfonamid không kháng khuẩn (SU02: furosemide, hydrochlorothiazide) và celecoxib (SU03).
- **NSAID** (NS01 nhóm không chọn lọc; NS02 celecoxib), **chống động kinh nhân thơm** (AED01 đến AED04).
- Nhóm thêm vì nhãn đã có trong kho: aminoglycoside, fluoroquinolone, macrolid, thienopyridine, benzimidazole thế (PPI). Không ca nào dùng, để sẵn.

## 3. Kiểm kê dị ứng trong 66 ca giả lập

Lệnh: `app.db.reader.load_source_cases(Path('.'))` và `DrugResolver.from_index('data/kb_curated/tra_cuu/tra_cuu.sqlite').resolve_name`. Kết quả đầy đủ ở `data/kb_reports/T60_kiem_ke_di_ung.json`.

### 3.1. Tình trạng

| `tinh_trang_di_ung.trang_thai` | Số ca |
|:--|--:|
| `khong_di_ung_da_hoi` | 58 |
| `co_di_ung` | 5 |
| `chua_co_thong_tin` | 3 (DEMO-03, HS-012, HS-038) |
| Tổng | 66 |

### 3.2. Tác nhân dị ứng ghi trong ca (5 bản ghi, đều `loai_tac_nhan = thuoc`)

| Ca | `di_ung_id` | Tác nhân | Loại | `hoat_chat_id` ghi trong ca | `resolve_name` |
|:--|:--|:--|:--|:--|:--|
| DEMO-06 | DU-DEMO06-01 | Penicillin | thuoc | HC-PENICILLIN | khong_nhan_dien |
| HS-010 | DU-HS-010-01 | Penicillin | thuoc | — | khong_nhan_dien |
| HS-011 | DU-HS-011-01 | Sulfonamid | thuoc | — | khong_nhan_dien |
| HS-013 | DU-HS-013-01 | Penicillin | thuoc | — | khong_nhan_dien |
| HS-056 | DU-HS056-01 | Sulfamethoxazol (sulfonamide) | thuoc | HC-SULFAMETHOXAZOLE | khong_nhan_dien |

Tỷ lệ phân giải: **0/5** tác nhân dị ứng nhận ra được bằng `resolve_name`. Nguyên nhân:
- 3 bản ghi ghi tên **nhóm** ("Penicillin") và 1 ghi "Sulfonamid": bộ phân giải chỉ biết tên chế phẩm DAV, đồng nghĩa và tên phối hợp, không biết tên nhóm.
- 1 bản ghi "Sulfamethoxazol (sulfonamide)": ngoặc đơn làm lệch khoá chuẩn hoá. Khi bỏ phần ngoặc ("Sulfamethoxazol") thì ra `sulfamethoxazole`.
- 2 bản ghi có `hoat_chat_id` trong ca (`HC-PENICILLIN`, `HC-SULFAMETHOXAZOLE`): mã kiểu cũ `HC-...`, không phải khoá trục. `HC-PENICILLIN` **không có trên trục**; `HC-SULFAMETHOXAZOLE` ứng với `sulfamethoxazole`.

→ Luật D3 phải đi qua `ten_nhom_di_ung_sang_hoat_chat` (mục 1.4), không dựa vào `resolve_name` cho tên nhóm.

Các tên thuốc kiểm thêm bằng `resolve_name` (T60, 19/11): "Augmentin" → amoxicillin + clavulanic_acid; "Amoxicilin" → amoxicillin; "Penicillin V" → penicillin_v; "Cefalexin" → cephalexin; "Ceftriaxon" → ceftriaxone; "Cotrimoxazol" → sulfamethoxazole + trimethoprim. **Không nhận**: "Penicillin", "Sulfonamid", "NSAID", "Beta-lactam", "Bactrim", "Penicilin V" (chế phẩm DAV chưa có thành phần). **Lỗi cần xử lý ở bộ phân giải (ngoài phạm vi T60)**: "Cephalexin" và "Paracetamol" trả `khong_nhan_dien` với lý do "tên ứng với nhiều công thức", trong khi "Cefalexin" và các tên INN khác ra bình thường.

### 3.3. Cặp "dị ứng X ↔ y lệnh Y" có trong ca

5 ca có dị ứng đều có đúng một dòng thuốc chờ duyệt; cả 5 cặp:

| Ca | Dị ứng | Thuốc trong y lệnh | Hoạt chất (qua `resolve_name`) |
|:--|:--|:--|:--|
| DEMO-06 | Penicillin | Amoxicillin 500 mg | amoxicillin |
| HS-010 | Penicillin | Amoxicillin 500 mg | amoxicillin |
| HS-011 | Sulfonamid | Sulfamethoxazol 800 mg + trimethoprim 160 mg | sulfamethoxazole, trimethoprim |
| HS-013 | Penicillin | Piperacillin + tazobactam 2,25 g | piperacillin, tazobactam |
| HS-056 | Sulfamethoxazol (sulfonamide) | Sulfamethoxazol + trimethoprim 800/160 mg | sulfamethoxazole, trimethoprim |

Với bảng D3, các cặp này đều có lời giải: DEMO-06, HS-010, HS-013 dị ứng penicillin với amoxicillin hoặc piperacillin là nhóm `BL01` (`cao`); HS-011 sulfonamid với sulfamethoxazole là `SU01` (`cao`); HS-056 trùng hoạt chất trực tiếp.

### 3.4. Ba tình huống nghiệm thu của plan

| Tình huống | Có đủ dữ liệu? |
|:--|:--|
| "Augmentin" phân giải ra amoxicillin | Có: `resolve_name("Augmentin")` → `amoxicillin`, `clavulanic_acid` |
| Dị ứng penicillin ↔ ceftriaxone có dòng nhóm chéo | Có: `BL05_PEN_CEPH_R1_KHAC` (`thap/than_trong`); `ceftriaxone` cũng nằm trong `BL08` và `BL07` |
| Tình trạng dị ứng "chưa có thông tin" được đếm | Có: 3 ca (mục 3.1) |

## 4. Câu "quá mẫn" của nhãn làm căn cứ văn bản

Tệp `data/kb_reports/T60_qua_man_nhan.json`. Với 40 hoạt chất xuất hiện trong danh mục thuốc của 66 ca (qua `resolve_name`), 37 có nhãn trong `chunks.jsonl`. Trong đó **36** có đoạn chống chỉ định chứa câu quá mẫn (từ khoá `hypersensitiv`, `allerg`, `anaphyla`, `sensitivity`); mỗi hoạt chất liệt kê `doan_trich_id`, `duong_dan_muc`, `url` và câu quá mẫn.

- Không có đoạn quá mẫn: spironolactone (nhãn chống chỉ định không có câu quá mẫn).
- Hoạt chất trong ca nhưng không có nhãn trong `chunks.jsonl`: cefoperazone, gabapentin, sulbactam.
- Chỉ xét đoạn có `muc = chong_chi_dinh` hoặc đường dẫn mục chứa "Contraindications". Câu quá mẫn ở mục cảnh báo (như "serious hypersensitivity reactions") chưa đưa vào.

## 5. Ba tầng tệp

| Tầng | Đường dẫn | Ghi chú |
|:--|:--|:--|
| Thô: nhãn mới | `data/kb_sources/openfda_d3/*.json` (26 nhãn) + `manifest.json` | Mỗi tệp một nhãn đã chọn trong `results[0]`, cùng `meta`. Nhãn Rx ưu tiên; 3 tệp lấy nhầm thuốc phối hợp (aspirin, hydrochlorothiazide, levetiracetam lần hai) đã xoá |
| Thô: nhãn sẵn | `data/kb_sources/openfda/*.json` | 50 nhãn; xem [openfda-rag.md](openfda-rag.md) |
| Bộ dùng | `data/kb/di_ung_cheo.json` | Trong git |
| Báo cáo | `data/kb_reports/T60_kiem_ke_di_ung.json`, `T60_qua_man_nhan.json` | Ngoài git |

Các nhãn mới (26): amoxicillin, ampicillin, aztreonam, carbamazepine, cefaclor, cefadroxil, cefazolin, cefdinir, cefixime, cefotaxime, cefpodoxime, ceftazidime, cefuroxime, celecoxib, cephalexin, diclofenac, ertapenem, lamotrigine, meloxicam, naproxen, oxacillin, oxcarbazepine, penicillin_g, penicillin_v, phenobarbital, sulfasalazine. Chỉ ngày hiệu lực nhãn (`effective_time`) và `set_id` do openFDA trả; không giả định nhãn là bản mới nhất của hoạt chất.

## 6. Hạn chế và việc còn mở

- **Chưa dược sĩ duyệt dòng nào.** Mọi `trang_thai` là `cho_duoc_si_duyet`. Mức `muc_cheo` do T60 gán theo nguồn; đây là điểm cần duyệt chính.
- Nhãn chưa đưa vào `chunks.jsonl`, nên chưa có `doan_trich_id` cho các nhãn mới; luật sau dùng `trich_nguyen_van` + `url` + `set_id` của bảng này.
- Nhãn aspirin đơn chất, hydrochlorothiazide đơn chất chưa lấy được; xem `plan/reports/T60.md`, mục thiếu nguồn.
- Bảng chỉ có **dị ứng chéo giữa nhóm hoạt chất**. Dị ứng với tá dược, thuốc cản quang, dị ứng chọn lọc một thuốc trong nhóm chưa có.
- Danh sách chất ở mỗi nhóm lấy từ hoạt chất **có trên trục** `tra_cuu.sqlite`; hoạt chất ngoài trục (cefatrizine, cefonicid, cefiderocol) chưa có `hoat_chat_id` nên chưa vào bảng.
