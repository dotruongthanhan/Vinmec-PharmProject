# PLAN 1.3 – DỮ LIỆU: THU THẬP, TỔNG HỢP, TIỀN XỬ LÝ

**Ngày viết:** 16/11/2026 · **Trạng thái:** đợt 1 đã tải xong; phần xử lý chờ giao (T04a, T16).
**Quan hệ:** plan 1 mục 6 (nguồn tri thức, nguyên tắc) · plan 1.1 mục 5–6 (cắt đoạn, truy xuất) và mục 10 (lược đồ `tri_thuc`) · `data/kb_sources/README.md` (hiện trạng từng tệp). Bản này nói **dữ liệu đi từ nguồn tới kho như thế nào**; cắt đoạn và truy xuất đã có ở plan 1.1 nên không lặp lại.

---

## 1. Phạm vi

Ba loại dữ liệu, ba cách xử lý khác nhau:

| Loại | Ví dụ | Đích | Ai quyết định đúng sai |
| :--- | :--- | :--- | :--- |
| **A. Văn bản nguồn** | Nhãn thuốc, văn bản Bộ Y tế, chuyên luận | Bảng `tri_thuc.doan_trich` (đoạn + véc-tơ) | Nguồn gốc; hệ thống chỉ trích nguyên văn |
| **B. Tri thức có cấu trúc** | Cặp tương tác, mức chỉnh liều theo thận / gan, nhóm dị ứng chéo, công thức | Bảng `tri_thuc.tuong_tac`, `quy_tac_lieu`, `nhom_di_ung_cheo`, `cong_thuc` | **Dược sĩ duyệt từng dòng** |
| **C. Dữ liệu ca giả lập** | 6 ca demo, mở rộng lên 20–30 ca | Tệp JSON → lược đồ `nghiep_vu` | Nhóm viết, dược sĩ duyệt đáp án (Q3) |

Luật chạy trên loại B. RAG chạy trên loại A. Loại B luôn trỏ ngược về một đoạn loại A làm căn cứ.

## 2. Nguyên tắc

1. **Tệp gốc không bao giờ bị sửa.** Mọi biến đổi sinh ra tệp mới ở tầng sau; tầng sau luôn dựng lại được từ tầng trước bằng lệnh.
2. **Mỗi dòng dữ liệu biết mình từ đâu ra:** nguồn, tầng tin cậy, phiên bản, ngày lấy, giấy phép, mã băm tệp gốc, và với loại B là `doan_trich_id` của đoạn căn cứ.
3. **Không tự hoà giải nội dung y khoa.** Hai nguồn nói khác nhau thì giữ cả hai, nguồn tầng cao đứng trước, đánh dấu xung đột để dược sĩ xem. Chỉ được bỏ dòng khi nó **trùng hẳn** với dòng của nguồn tầng cao hơn.
4. **LLM được dùng để rút nháp, không được dùng để phát hành.** Dòng do LLM rút ra có trạng thái `nhap`; chỉ dòng `da_duyet` (có `nguoi_duyet`) mới được luật coi là căn cứ kết luận. Dòng `nhap` vẫn hiển thị được nhưng phải ghi "chưa được dược sĩ duyệt".
5. **Con số được kiểm bằng code, không bằng mắt.** Mỗi con số trong dòng loại B phải tìm thấy nguyên văn trong đoạn căn cứ; không thấy thì dòng bị từ chối.
6. **Chỉ lấy nguồn có quyền dùng.** Nguồn có bản quyền thương mại chỉ liên kết sang (plan 1 mục 6.4).

## 3. Sơ đồ nguồn

### 3.1. Đã có trong `data/kb_sources/` (đợt 1, 16/11)

| Nguồn | Tầng | Số lượng | Điểm cần biết khi xử lý |
| :--- | :-: | :--- | :--- |
| openFDA Drug Label | 3 | 50 nhãn, khoảng 4,2 triệu ký tự (trung bình 84 nghìn ký tự mỗi nhãn) | Đã chia mục sẵn. Độ phủ: chỉ định, liều, chống chỉ định 50/50; tương tác 46/50; nhóm đặc biệt 38/50; cảnh báo đóng khung 23/50. **12 nhãn theo định dạng cũ** (`warnings` + `precautions` thay cho `warnings_and_cautions`) nên bảng ánh xạ mục phải xử lý cả hai. 27 nhãn có bảng liều dạng HTML. 34 nhãn nhắc tới độ thanh thải creatinin; 7 nhãn nhắc Child-Pugh |
| DDInter 2.0 | 4 | 14 tệp CSV, 507.655 dòng, **234.981 cặp không trùng** | Chỉ có tên hai thuốc và mức độ (Major 39.082 · Moderate 143.748 · Minor 9.736 · Unknown 42.415). Một cặp xuất hiện ở nhiều tệp và theo cả hai chiều. Không có cơ chế, không có xử trí. Giấy phép phi thương mại |

### 3.2. Cần lấy tiếp, theo thứ tự ưu tiên

| # | Nguồn | Tầng | Dùng cho | Cách lấy | Chặn bởi |
| :-: | :--- | :-: | :--- | :--- | :--- |
| 1 | Quyết định 5948/QĐ-BYT – danh mục tương tác chống chỉ định | 1 | Yếu tố 4, mức nghiêm trọng | Bản PDF có chữ ký → nhập tay thành bảng, hai người đối chiếu | **Khoa Dược cấp bản chính thức** (chưa tìm được bản công khai trên trang Bộ Y tế; trang tra cứu `tuongtacthuoc.ehealth.gov.vn` không kết nối được ngày 16/11) |
| 2 | Dược thư Quốc gia Việt Nam, lần xuất bản thứ ba | 2 | Chỉ định, liều, chỉnh liều, tương tác bằng tiếng Việt | PDF → tách theo chuyên luận và đề mục | Câu Q4: bản chính thức và quyền dùng |
| 3 | Danh mục thuốc của viện: tên thương mại → hoạt chất, hàm lượng, dạng bào chế | — | Chuẩn hoá tên (mục 5) | Khoa Dược cấp; hoặc tra tay cổng Cục Quản lý Dược cho 50 thuốc | Câu Q10 |
| 4 | RxNorm / RxNav | — | Mã RxCUI, tên đồng nghĩa, lớp ATC qua RxClass | API công khai, không cần khoá | Không |
| 5 | DailyMed SPL | 3 | Nhãn đúng dạng bào chế viện dùng, khi bản openFDA lấy được là dạng khác | API theo `set_id` | Danh mục ở dòng 3 |
| 6 | LiverTox, LactMed (NCBI Bookshelf) | 3 | Độc tính gan; thuốc và cho con bú | Tải theo hoạt chất | Sau demo |
| 7 | NIH Office of Dietary Supplements; NCCIH | 3 | Thực phẩm chức năng, thảo dược: tương tác với thuốc | Tờ thông tin cho nhân viên y tế; API của ODS trả mã 403 khi gọi bằng lệnh nên tải tay hoặc xin khoá | Sau demo |
| 8 | EMA – tóm tắt đặc tính sản phẩm | 3 | Đối chiếu khi nhãn Mỹ và thực hành Việt Nam lệch | PDF theo thuốc; kiểm điều khoản trước | Sau demo |
| 9 | Hướng dẫn chẩn đoán điều trị, hướng dẫn kháng sinh của Bộ Y tế | 1 | Yếu tố 3 | PDF; kiểm văn bản còn hiệu lực | Sau demo |

### 3.3. Nguồn không dùng

- **UpToDate / Lexicomp, Micromedex, MIMS:** có bản quyền, viện đã có tài khoản. Chỉ liên kết sang.
- **`doctorabad.com/uptodate/`:** bản sao Lexicomp Drug Interactions (trang ghi rõ Wolters Kluwer), dữ liệu đóng băng 04/2018. Không tải, không nạp, không dùng để đối chiếu.

## 4. Các tầng xử lý

```text
data/kb_sources/         TẦNG 0 – GỐC      tệp tải về, không sửa, có manifest.json
        │  đọc + kiểm định dạng
data/kb_staging/         TẦNG 1 – CHUẨN    cùng nội dung, một lược đồ chung, tên thuốc đã chuẩn hoá
        │  khử trùng lặp, gộp nguồn, đánh dấu xung đột
data/kb_curated/         TẦNG 2 – TỔNG HỢP bảng có cấu trúc (nháp + đã duyệt), tài liệu đã cắt đoạn
        │  kiểm chất lượng (mục 9) → nhúng → nạp
PostgreSQL tri_thuc      TẦNG 3 – PHÁT HÀNH một phien_ban_kho, chỉ đọc với ứng dụng
```

- Mỗi tầng là một lệnh: `python -m app.kb.fetch` (tầng 0, có sẵn bằng tay ở đợt 1) · `python -m app.kb.normalize` (tầng 1) · `python -m app.kb.curate` (tầng 2) · `python -m app.kb.build` (tầng 3).
- Mỗi lệnh ghi một **báo cáo chạy** (`data/kb_reports/<ngày>-<lệnh>.json`): số dòng vào, ra, bị loại và **lý do loại từng nhóm**. Không có dòng nào biến mất mà không có lý do.
- Tầng 1 và 2 là tệp JSONL / CSV đọc được bằng mắt, để dược sĩ và người review mở xem được.
- `data/kb/quy_tac_lieu_than.json` hiện có chuyển thành một tệp của tầng 2.

## 5. Chuẩn hoá tên thuốc

Đây là bước quyết định việc gộp nguồn có đúng không: `amoxicilin` (Dược thư), `Amoxicillin` (DDInter), `AMOXICILLIN AND CLAVULANATE POTASSIUM` (openFDA), `Augmentin` (y lệnh) phải về cùng một hoạt chất.

Bảng `tri_thuc.hoat_chat` và `tri_thuc.ten_dong_nghia`:

```text
hoat_chat:       hoat_chat_id (khoá nội bộ, snake_case không dấu theo INN: "amoxicillin")
                 ten_inn, ten_viet, rxcui, ma_atc, nhom_duoc_ly, la_phoi_hop: bool
ten_dong_nghia:  ten_chuan_hoa → hoat_chat_id, loai (inn | viet | muoi | thuong_mai | viet_tat), nguon
```

Quy tắc:

1. **Khoá chuẩn hoá** của một tên: chữ thường, bỏ dấu, bỏ khoảng trắng thừa và dấu câu.
2. **Bỏ gốc muối và este** khi so khớp (`besylate`, `hydrochloride`, `sodium`, `potassium`, `tartrate`, `succinate`, `sulfate`, `calcium`, `magnesium`, …), nhưng **giữ lại ở trường riêng** khi muối làm đổi liều hoặc dạng dùng (metoprolol tartrat so với succinat).
3. **Thuốc phối hợp tách thành nhiều hoạt chất**: `amoxicillin and clavulanate potassium` → `amoxicillin` + `clavulanic_acid`. Tương tác, dị ứng, trùng lặp kiểm theo từng thành phần.
4. **Chính tả Việt – quốc tế** theo bảng tra, không theo quy tắc đoán (`amoxicilin`, `ceftriaxon`, `amlodipin`, `acid valproic`).
5. **Không khớp được thì không đoán.** Tên không tìm thấy vào danh sách `chua_khop` trong báo cáo chạy để người xem; dòng đó không được nạp.
6. Lớp dược lý lấy từ ATC (qua RxClass) để phục vụ luật trùng nhóm điều trị và dị ứng chéo.

## 6. Tiền xử lý theo từng nguồn

### 6.1. Nhãn openFDA

| Bước | Việc | Kiểm |
| :-: | :--- | :--- |
| 1 | Đọc `results[0]`; lấy `set_id`, `effective_time`, `openfda.*` làm siêu dữ liệu tài liệu | Thiếu `set_id` → loại |
| 2 | Ánh xạ tên trường về bảng `muc` chuẩn (plan 1.1 mục 5.4), **cả định dạng mới và cũ**: `warnings_and_cautions`, `warnings`, `precautions`, `boxed_warning` → `canh_bao`; `use_in_specific_populations`, `pregnancy`, `nursing_mothers`, `lactation`, `pediatric_use`, `geriatric_use` → tách `thai_ky_cho_bu`, `nhi_cao_tuoi`; tiểu mục nói về suy thận / suy gan trong `dosage_and_administration` và `use_in_specific_populations` → `lieu_than`, `lieu_gan` | Trường không có trong bảng ánh xạ → `khac`, ghi vào báo cáo |
| 3 | Bỏ các trường không dùng: `spl_product_data_elements`, `package_label_principal_display_panel`, `how_supplied`, `clinical_studies`, `nonclinical_toxicology`, `references`, `description` | — |
| 4 | Làm sạch văn bản: gộp khoảng trắng; tách số tiểu mục (`2.2 Dosage in Renal Impairment`) thành `duong_dan_muc`; bỏ phần tóm tắt đầu nhãn bị lặp (mục `Highlights` lặp lại nội dung chi tiết, như đã thấy ở nhãn meropenem) | Đoạn trùng nguyên văn trong cùng một nhãn chỉ giữ một |
| 5 | Bảng (`*_table`, HTML) → cấu trúc `{tieu_de, cot[], dong[][]}` và một bản văn bản phẳng đọc được; bảng là **đơn vị không cắt** | Số ô mỗi dòng bằng số cột, lệch thì giữ bản phẳng và ghi cảnh báo |
| 6 | Gắn `hoat_chat_ids` theo mục 5 | Không khớp → không nạp |
| 7 | Chuyển cho bộ cắt đoạn (plan 1.1 mục 5) | — |

Giữ `noi_dung_goc` đúng nguyên văn sau bước 4; mọi thứ thêm vào (tiêu đề ngữ cảnh) chỉ nằm ở `noi_dung_nhung`.

### 6.2. DDInter

| Bước | Việc |
| :-: | :--- |
| 1 | Đọc 14 tệp; cột `Drug_A`, `Drug_B`, `Level`, `DDInterID_A`, `DDInterID_B` |
| 2 | Chuẩn hoá hai tên theo mục 5; **sắp hai hoạt chất theo thứ tự chữ cái** để cặp (A, B) và (B, A) thành một |
| 3 | Khử trùng lặp theo cặp. Một cặp có nhiều mức giữa các tệp → giữ **mức cao nhất** và ghi `co_muc_lech: true` |
| 4 | Bỏ cặp một thuốc với chính nó. Giữ mức `Unknown` nhưng **không coi là "không tương tác"**; luật không báo gì với mức này |
| 5 | **Chỉ giữ cặp mà cả hai hoạt chất nằm trong danh mục của dự án** (50 hoạt chất tạm → khoảng vài trăm cặp), để dược sĩ rà được |
| 6 | Ghi `tang_tin_cay: 4`, `trang_thai: sang_loc`, `giay_phep`; không có `co_che`, `xu_tri` (nguồn không cung cấp) |

### 6.3. Quyết định 5948/QĐ-BYT (khi có bản chính thức)

Nhập tay từng dòng: hai hoạt chất (hoặc nhóm), cơ chế, hậu quả, xử trí, điều kiện ngoại lệ nếu văn bản có. **Hai người nhập độc lập rồi so tệp**; đếm số cặp từ văn bản gốc (các bài báo ghi lệch nhau: 11 và 25). Dòng viết theo **nhóm thuốc** phải được mở thành từng hoạt chất qua bảng nhóm, và giữ nguyên dòng gốc để trích dẫn. Mỗi dòng cũng thành một đoạn loại A (`TableRowChunker`).

### 6.4. Dược thư Quốc gia (khi có quyền dùng)

PDF → văn bản theo chuyên luận → đề mục chuẩn của Dược thư. Kiểm sau khi tách: mỗi chuyên luận có đủ các đề mục bắt buộc; lỗi nhận dạng ký tự với liều (`1 g` thành `l g`, mất dấu phẩy thập phân) được bắt bằng biểu thức tìm con số đứng cạnh đơn vị; chuyên luận nào có cảnh báo thì người xem lại trước khi nạp.

### 6.5. Thực phẩm chức năng

Coi như một nhóm hoạt chất riêng (`loai: thuc_pham_chuc_nang`), chỉ nạp phần **tương tác với thuốc** và **cảnh báo an toàn** từ nguồn cơ quan y tế. Tên sản phẩm thương mại không chuẩn hoá được thì không khớp; hệ thống báo "không nhận diện được thành phần" thay vì im lặng.

## 7. Tổng hợp nhiều nguồn và xử lý trùng

### 7.1. Văn bản nguồn (loại A)

- Trùng **nguyên văn** (so mã băm của văn bản đã chuẩn hoá khoảng trắng) trong cùng tài liệu: giữ một.
- Cùng nội dung ở hai nguồn khác nhau (ví dụ nhãn FDA và Dược thư cùng nói về chỉnh liều thận): **giữ cả hai**. Đó là hai căn cứ độc lập; khi truy xuất, tầng cao đứng trước.
- Hai nhãn của cùng hoạt chất, cùng dạng dùng từ hai nhà sản xuất: chỉ nạp một (bản mới nhất), ghi `set_id` các bản còn lại.

### 7.2. Tương tác thuốc (loại B)

Khoá gộp: cặp hoạt chất đã chuẩn hoá và sắp thứ tự.

| Tình huống | Xử lý |
| :--- | :--- |
| Cặp có ở QĐ 5948 và ở DDInter | Giữ dòng QĐ 5948 làm dòng chính (tầng 1). Dòng DDInter **bị lọc khỏi bảng luật** và ghi vào `nguon_phu` của dòng chính |
| Cặp có ở nhãn FDA (mục tương tác hoặc chống chỉ định) và ở DDInter | Dòng chính lấy từ nhãn (tầng 3, có nguyên văn, có xử trí); DDInter thành `nguon_phu` |
| Cặp chỉ có ở DDInter | Giữ, `trang_thai: sang_loc`. Giao diện ghi "sàng lọc, cần đối chiếu"; mức độ không được dùng để kết luận nghiêm trọng |
| Hai nguồn lệch **mức độ** | Không tự chọn mức trung bình. Dòng chính theo nguồn tầng cao; ghi `xung_dot: true` và mức của nguồn kia; đưa vào danh sách dược sĩ rà |
| Nguồn tầng cao nói chống chỉ định, nguồn tầng thấp không có cặp đó | Giữ theo tầng cao |
| Nguồn tầng thấp báo Major, nguồn tầng cao không nhắc | Giữ là sàng lọc, đánh dấu ưu tiên rà |

Lược đồ một dòng:

```text
tuong_tac:  hoat_chat_a, hoat_chat_b (đã sắp thứ tự), muc_do (chong_chi_dinh | nghiem_trong | trung_binh | nhe | chua_ro),
            co_che, hau_qua, xu_tri, dieu_kien,
            nguon, tang_tin_cay, doan_trich_id, nguon_phu[],
            xung_dot: bool, trang_thai (nhap | sang_loc | da_duyet), nguoi_duyet, ngay_duyet, phien_ban
```

Ánh xạ mức độ giữa các nguồn nằm ở **một bảng duy nhất** trong code (`Major` → `nghiem_trong`, `Moderate` → `trung_binh`, `Minor` → `nhe`, `Unknown` → `chua_ro`; QĐ 5948 → `chong_chi_dinh`), có test.

### 7.3. Chỉnh liều theo chức năng thận và gan (loại B)

Nguồn: mục liều và mục nhóm đặc biệt của nhãn (34/50 nhãn có ngưỡng theo độ thanh thải creatinin; 7/50 có Child-Pugh), về sau thêm Dược thư.

Quy trình cho mỗi hoạt chất:

1. Bộ lọc bằng code tìm bảng và câu có `creatinine clearance`, `CrCl`, `CLcr`, `eGFR`, `Child-Pugh`, `hepatic impairment`.
2. LLM rút **nháp** theo lược đồ dưới, bắt buộc kèm `trich_nguyen_van`.
3. **Kiểm bằng code:** mọi con số trong dòng nháp phải có trong `trich_nguyen_van`, và `trich_nguyen_van` phải là chuỗi con của đoạn nguồn. Các khoảng phải **phủ kín và không chồng nhau** (bảng meropenem ghi `26–50` và `10–25`: giá trị 25,5 rơi vào khe, phải có quy tắc đóng khe ghi rõ, như `select_renal_tier` đang làm).
4. Dược sĩ duyệt từng dòng → `da_duyet`.

```text
quy_tac_lieu:  hoat_chat_id, duong_dung, chi_dinh (nếu liều khác theo chỉ định),
               loai_dieu_kien (than | gan | tuoi | can_nang),
               chi_so (crcl_cockcroft_gault | egfr_ckd_epi | child_pugh), tu, den, bao_gom_can_duoi,
               can_chinh: bool, khuyen_cao (nguyên văn đã dịch), lieu_toi_da, khoang_cach_lieu,
               nguon, tang_tin_cay, doan_trich_id, trich_nguyen_van,
               trang_thai, nguoi_duyet, ngay_duyet, phien_ban
```

Lưu ý quan trọng khi rút: nhãn thuốc phần lớn chỉnh liều theo **CrCl Cockcroft-Gault**, không theo eGFR; dòng nào dùng chỉ số nào phải ghi đúng `chi_so`, luật không được thay chỉ số này bằng chỉ số kia.

### 7.4. Dị ứng chéo (loại B)

Không có nguồn mở có cấu trúc. Dựng bảng `nhom_di_ung_cheo` từ lớp ATC (penicillin, cephalosporin, carbapenem, sulfonamid, NSAID, …) cộng câu chống chỉ định trong nhãn; mức cảnh báo (`cung_nhom` chắc chắn, `nhom_lien_quan` cần cân nhắc) do dược sĩ duyệt. Bảng hiện dùng trong `app/rules/allergy.py` chuyển vào đây.

### 7.5. Công thức (loại B)

| Công thức | Tình trạng | Nguồn |
| :--- | :--- | :--- |
| Cockcroft-Gault, CKD-EPI 2021, BMI, BSA Mosteller, IBW, AdjBW | Đã có ở `app/calc`, đã kiểm | Bài báo gốc |
| **Child-Pugh** (5 thành phần → điểm → lớp A / B / C) | **Chưa có.** Cần cho chỉnh liều theo gan | Pugh 1973; đối chiếu MedCalc-Bench |
| Hiệu chỉnh canxi theo albumin, khoảng QTc | Chưa có, làm khi có luật cần | Bài báo gốc |

Công thức vẫn theo quy tắc của plan 1 mục 7: tự cài bằng Python, có trích dẫn, có ca kiểm từ bài báo, kiểm chéo với MedCalc-Bench. Bảng `cong_thuc` chỉ lưu siêu dữ liệu (tên, phiên bản, trích dẫn, đầu vào), không lưu code.

## 8. Dữ liệu ca giả lập (loại C)

- Nguồn gốc là tệp JSON ở `data/mock/`, đáp án ở `data/gold/`. 100% giả lập, không lấy từ ca thật, không dùng tên người thật.
- Mở rộng từ 6 lên 20–30 ca theo ma trận ở Phụ lục A của plan 1: mỗi yếu tố ít nhất 2 ca dương và 1 ca âm, có ca thiếu dữ liệu, ca nhiều phát hiện, ca chèn lệnh.
- **Ca phải dùng thuốc nằm trong danh mục đã có nguồn**; ca và kho tri thức mở rộng cùng nhau.
- Mỗi ca mới đi kèm đáp án viết **trước khi** chạy hệ thống, để đáp án không bị viết theo kết quả.
- Dữ liệu có trục thời gian (y lệnh hằng ngày, xét nghiệm lặp lại) cần ít nhất 3 ca có nhiều ngày, để thử xu hướng và "thuốc đang dùng".

## 9. Cổng chất lượng trước khi phát hành một phiên bản kho

Lệnh `python -m app.kb.build` chỉ phát hành khi mọi mục sau đạt; không đạt thì dừng và in lý do:

| # | Kiểm | Ngưỡng |
| :-: | :--- | :--- |
| Q1 | Mọi tệp tầng 0 có trong `manifest.json` và khớp mã băm | 100% |
| Q2 | Mọi đoạn có `hoat_chat_ids`, `muc`, `nguon`, `tang_tin_cay`, `noi_dung_goc` khác rỗng | 100% |
| Q3 | Mỗi hoạt chất trong danh mục có ít nhất các mục `chi_dinh`, `lieu`, `chong_chi_dinh` | 100%, thiếu thì nêu tên |
| Q4 | Không có hai đoạn trùng `doan_trich_id`; không có đoạn rỗng hoặc dưới 50 ký tự (trừ dòng bảng) | 0 vi phạm |
| Q5 | Mọi dòng loại B có `doan_trich_id` tồn tại trong kho và con số khớp nguyên văn | 100% |
| Q6 | Các khoảng của `quy_tac_lieu` cho cùng hoạt chất và điều kiện: phủ kín, không chồng | 100% |
| Q7 | Không có cặp tương tác trùng khoá; không có cặp tự tương tác | 0 vi phạm |
| Q8 | Tỉ lệ tên thuốc không khớp ở mỗi nguồn | Báo cáo; trên 5% thì dừng |
| Q9 | Bộ câu hỏi truy xuất vàng (plan 1.1 mục 6.7) không tụt so với phiên bản trước | Không giảm quá 2 điểm phần trăm |
| Q10 | Số dòng `da_duyet` so với `nhap`, `sang_loc` | Báo cáo, hiện ở giao diện quản trị |

## 10. Phiên bản và cập nhật

- Mỗi lần phát hành là một `phien_ban_kho` (ngày + số thứ tự). `phien_ai` ghi phiên bản đã dùng.
- Nhãn FDA: kiểm `effective_time` hằng tháng; nhãn đổi thì dựng lại hoạt chất đó và **đưa các dòng `quy_tac_lieu` rút từ nhãn cũ về `nhap`** cho tới khi dược sĩ xem lại.
- Văn bản Bộ Y tế: cập nhật khi có văn bản mới hoặc văn bản thay thế; văn bản hết hiệu lực giữ lại với cờ `het_hieu_luc`, không xoá.
- Đổi mô hình nhúng: dựng lại toàn bộ véc-tơ, văn bản và bảng có cấu trúc không đổi.

## 11. Thứ tự làm

| Mã | Việc | Phụ thuộc | Khi nào |
| :-: | :--- | :--- | :-: |
| T15 | Tải đợt 1, manifest, đối chiếu meropenem | — | **Xong 16/11** |
| T04a | Tiền xử lý nhãn openFDA (mục 6.1) + cắt đoạn + chuẩn hoá tên cho 6 hoạt chất demo, rồi 50 | T11 | 17/11 |
| T16 | Tổng hợp tương tác: DDInter (mục 6.2) + tương tác từ nhãn, bảng `tuong_tac`, luật tương tác v0 (yếu tố 4), ít nhất 1 ca demo có tương tác | T04a | 18/11 |
| T17 | Rút nháp `quy_tac_lieu` theo thận cho các kháng sinh trong danh mục + kiểm bằng code (mục 7.3) | T04a, T05 | 18/11 nếu kịp, không thì tuần 4 |
| T18 | Child-Pugh + chỉnh liều theo gan | T17 | Tuần 4 |
| — | QĐ 5948, Dược thư, danh mục thuốc viện | Khoa Dược | Khi có |
| — | Thực phẩm chức năng, LiverTox, LactMed, 20–30 ca | — | Tuần 4 |

**Cho demo 20/11:** đủ là 6 hoạt chất demo có nhãn đã cắt đoạn, bảng liều thận meropenem (đã đối chiếu nhãn), và một bảng tương tác nhỏ ở trạng thái sàng lọc. Mọi dòng chưa duyệt đều hiện đúng là chưa duyệt.

## 12. Việc cần người dùng và Khoa Dược

1. Bản chính thức Quyết định 5948/QĐ-BYT.
2. Bản chính thức và quyền dùng Dược thư Quốc gia (Q4).
3. Danh mục hoạt chất và tên thương mại tại viện (Q10); trong lúc chờ dùng 50 hoạt chất tạm.
4. Một dược sĩ duyệt dòng loại B (Q3). Chưa có thì mọi dòng ở trạng thái nháp hoặc sàng lọc.
5. Quyết định có đưa `data/kb_sources/ddinter/` (22 MB, giấy phép phi thương mại) vào git hay không.
