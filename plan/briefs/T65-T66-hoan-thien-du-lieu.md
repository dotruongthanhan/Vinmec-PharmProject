# T65-T66 hoàn thiện – Dữ liệu D4 + D5: sửa khoảng CrCl, thêm trường cho luật, tài liệu, báo cáo

Agent: **sub Sonnet** (việc dữ liệu). Không viết code ứng dụng. Mạng: chỉ openFDA / DailyMed / DAV nếu cần kiểm morphin (việc 4).

Lượt trước (T65, T66) bị dừng giữa chừng. **Không làm lại từ đầu.** Sáu tệp đã có trong `data/kb/` và Claude đã kiểm ngày 19/11:
- 103/103 câu `trich_nguyen_van` là chuỗi con nguyên văn của tệp nhãn (`quy_tac_lieu_than` 24, `quy_tac_gan` 24, `nguong_xet_nghiem` 15, `lieu_toi_da` 40). Không cần kiểm lại phần này.
- Còn các lỗi và thiếu dưới đây.

Đọc trước: `AGENTS.md` (quy tắc 9), `plan/HANDOFF.md` mục 3, `plan/briefs/T65-du-lieu-d4-than-gan-xet-nghiem.md`, `plan/briefs/T66-du-lieu-d5-lieu-duong-dung.md`, `docs/du-lieu/README.md`, `docs/du-lieu/di-ung-cheo.md` (mẫu tài liệu).

**Song song với bạn:** agent code (agy) đang viết luật D4 (T67) và D5 (T68) đọc các tệp này theo **đúng lược đồ ghi trong brief này**. Không đổi tên khoá đã có; chỉ thêm khoá như dưới.

## Việc

### 1. `quy_tac_lieu_than.json`: khoảng CrCl chồng ở ranh giới

Thêm trường tuỳ chọn cho mỗi mức: **`bao_gom_can_tren`** (bool). Ý nghĩa: `true` → `crcl <= crcl_den`; `false` → `crcl < crcl_den`. Không ghi thì luật hiểu như cũ (`<=`, trừ mức có `crcl_tu = null` và `bao_gom_can_duoi = false` thì `<`).

Claude đo bằng cách thử các giá trị 0 → 130: sáu hoạt chất trong `quy_tac_cho_duyet` có điểm rơi vào **hai** mức cùng lúc:

| Hoạt chất | Điểm chồng | Sửa |
|:--|:--|:--|
| cefepime | 30 | mức "11–29": `bao_gom_can_tren: false` |
| levofloxacin | 20, 50 | mức "20 to 49" và "10 to 19": `bao_gom_can_tren: false` |
| gabapentin | 60 | mức ">30 to 59": `bao_gom_can_tren: false` |
| levetiracetam | 50 | nhãn tự chồng ("Mild 50 to 80", "Moderate 30 to 50"): mức Moderate `bao_gom_can_tren: false`, ghi `ghi_khoang` nói rõ nhãn chồng ở 50 và đã xếp 50 vào mức nhẹ, chờ dược sĩ |
| colistimethate | 30, 50, 80 | ba mức "…to 79", "…to 49", "…to 29": `bao_gom_can_tren: false` |
| simvastatin | 30 | mức "15 – 29": `bao_gom_can_tren: false` |

- **Không** đụng khoá `quy_tac` (meropenem đã duyệt; luật có nhánh riêng cho nó).
- Sửa xong, tự kiểm bằng script (để trong thư mục scratchpad, không để trong kho): với mọi quy tắc, mọi giá trị CrCl từ 0 đến 150 bước 0,5 phải rơi vào **đúng một** mức theo ngữ nghĩa trên. Dán kết quả vào báo cáo.
- Thêm khoá cấp cao **`khong_co_nguong`**: danh sách `{hoat_chat_id, ly_do, set_id, url}` cho hoạt chất của 66 ca mà nhãn chỉ nói chung "thận trọng / giảm liều khi suy thận" không có số, hoặc nhãn nói không cần chỉnh. Không tự đặt ngưỡng.

### 2. `nguong_xet_nghiem.json`: thêm trường ngữ nghĩa cho luật

Mỗi dòng trong `quy_tac` thêm:

- **`kieu_dieu_kien`** (bắt buộc), một trong:
  - `canh_bao_khi_thoa`: điều kiện đúng thì cảnh báo (ví dụ INR > 4,0; digoxin > 2,0; metformin eGFR < 30).
  - `canh_bao_khi_ngoai_khoang`: `dieu_kien` là khoảng đích điều trị; giá trị ngoài khoảng thì cảnh báo (warfarin INR 2–3, phenytoin 10–20).
  - `dieu_kien_khoi_dau`: nhãn chỉ cho bắt đầu / tiếp tục khi điều kiện đúng; điều kiện sai thì cảnh báo (spironolacton K⁺ ≤ 5,0 và eGFR > 50).
- **`muc_do_de_xuat`**: `nghiem_trong` (nhãn dùng chống chỉ định, "do not", "discontinue", "contraindicated") hoặc `can_luu_y` (theo dõi, cân nhắc, giảm liều).
- **Mỗi phần tử trong `dieu_kien`** thêm ba khoá để luật đổi đơn vị mà không phải đọc chữ tự do:
  - `don_vi_nhan`: đơn vị của `gia_tri` (như nhãn), ví dụ `"mg/dL"`, `"mEq/L"`, `"mL/min/1.73 m2"`, `null` nếu không đơn vị (INR).
  - `don_vi_ca`: đơn vị đúng như chuỗi `don_vi` trong xét nghiệm của ca (đã kiểm kê: creatinin `umol/L`, kali `mmol/L`, egfr `mL/phút/1,73m2`, inr `""` hoặc `null`, digoxin `ng/mL`, phenytoin `mcg/mL`, glucose `mmol/L`, alt/ast `U/L`).
  - `he_so_ca_sang_nhan`: số nhân giá trị ca để ra đơn vị nhãn. Ví dụ creatinin µmol/L → mg/dL là `1/88.4` (ghi số thập phân `0.011312`), mEq/L ↔ mmol/L của kali, natri là `1`, eGFR hai cách viết là `1`, INR `1`. Mỗi hệ số khác 1 ghi nguồn trong `ghi_chu` của dòng.
- **`dieu_kien_khac`** (chuỗi, tuỳ chọn): nếu câu nhãn gộp xét nghiệm với tiêu chí không phải xét nghiệm (ví dụ apixaban giảm liều khi có 2 trong 3: tuổi ≥ 80, cân nặng ≤ 60 kg, creatinin ≥ 1,5 mg/dL), ghi nguyên các tiêu chí còn lại bằng tiếng Việt. Luật sẽ chỉ báo "cần xem, đối chiếu thêm" chứ không kết luận một mình xét nghiệm.
- Tiểu cầu, natri chưa có trong ca: giữ dòng, ghi `ma_xet_nghiem` dự kiến (`tieu_cau`, `natri`).
- Ghi trong `ghi_chu` của tệp ý nghĩa ba giá trị `kieu_dieu_kien`.

### 3. `thuoc_benh_icd.json`: thêm cặp thuốc–bệnh để luật không phải đọc `data/kb_staging`

`data/kb_staging/` không có trên git (CI không có), nên luật chỉ được đọc `data/kb/`. Thêm khoá **`cap_thuoc_benh`**: mọi dòng DDInter `tuong_tac_benh.jsonl` có hoạt chất thuộc 66 ca (khoảng 300 dòng, đã đếm ở `thong_ke.so_dong_ddinter_lien_quan`). Mỗi phần tử:

```json
{"hoat_chat_id": "enalapril", "ddinter_id": "DDInter…", "ten_benh": "Kidney Diseases",
 "ma_icd10": ["N00-N19"], "muc_do": "Major|Moderate|Minor",
 "noi_dung": "<nguyên văn trường noi_dung của DDInter, cắt ≤ 600 ký tự, thêm '…' nếu cắt>",
 "url": "<url_goc>", "trang_thai": "cho_duoc_si_duyet"}
```

- `ma_icd10` lấy từ `anh_xa` theo `ten_benh` (bệnh `khong_anh_xa` thì để `[]`).
- Chuyển mã DDInter → `hoat_chat_id` theo đúng cách lượt trước đã làm (bảng chuyển mã / trục `tra_cuu.sqlite`).
- Sau khi thêm, tính lại `cap_khop_chan_doan_ca` từ `cap_thuoc_benh` và so với 13 dòng đang có; lệch thì ghi lý do.

### 4. `duong_dung_hop_le.json`: soát một nghi vấn

HS-037 morphin 10 mg **tiêm dưới da** ra `khong_hop_le` vì dòng `morphine|dang_tiem_truyen` không có `tiem_duoi_da`, trong khi danh mục thuốc của ca ghi "tiêm dưới da, tiêm tĩnh mạch". Tra DAV (dạng bào chế / đường dùng của sản phẩm morphin tiêm VN) và NDC openFDA `route` của morphin tiêm. Nguồn có `SUBCUTANEOUS` hoặc chữ "tiêm dưới da" thì thêm `tiem_duoi_da` kèm nguồn; không có thì giữ nguyên và ghi rõ trong `ghi_chu` của dòng là đã tra, chưa thấy nguồn.

Kiểm thêm: mỗi dòng `nhom` có ít nhất một nguồn; dòng nào chỉ có FDA ghi rõ `muc_chac_chan: chi_fda` (đã có khoá này, chỉ soát).

### 5. `lieu_toi_da.json`: soát

- Paracetamol: dòng người lớn ≥ 50 kg 4.000 mg/ngày, dòng < 50 kg 75 mg/kg/ngày: đã có. Kiểm `doi_tuong` của hai dòng không chồng nhau (ngưỡng 50 kg).
- Gentamicin: dòng theo kg phải có `theo_kg.ngay_mg_kg` và `quy_doi_don_vi[].can_can_nang: true`.
- `doi_tuong` hiện có 21 giá trị khác nhau (`nguoi_lon`, `tre_em_tu_3_thang`, `nguoi_lon_tu_75_tuoi`, `nguoi_lon_clcr_duoi_30`, `nguoi_lon_child_pugh_c`…). **Giữ nguyên giá trị**, nhưng **bắt buộc** thêm bảng cấp cao **`doi_tuong_dinh_nghia`**: mỗi giá trị đang dùng → `{"tuoi_tu": năm|null, "tuoi_den": năm|null, "can_nang_tu": kg|null, "can_nang_den": kg|null, "dieu_kien_khac": chuỗi|null}`. Cận dưới gồm, cận trên không gồm; null là không giới hạn; tuổi dưới 1 năm ghi số thập phân (29 ngày = 29/365, ghi 3 chữ số). Tiêu chí không phải tuổi / cân nặng (CrCl < 30, Child-Pugh C, nhiễm trùng đe doạ tính mạng, sarcoma xương, tuổi thai) ghi vào `dieu_kien_khac`. Lấy định nghĩa đúng theo câu nhãn của dòng; nhãn không nói rõ "người lớn" từ bao nhiêu tuổi thì `tuoi_tu: 18` và ghi điều đó trong `ghi_chu` của bảng.

### 6. Tài liệu và báo cáo

- `docs/du-lieu/lieu-than-gan-xet-nghiem.md` (bốn tệp D4) và `docs/du-lieu/lieu-duong-dung.md` (hai tệp D5), theo mẫu `di-ung-cheo.md`: nguồn, lược đồ từng khoá (gồm khoá mới ở việc 1–3, 5), cách luật dùng, số liệu, giới hạn, trạng thái duyệt.
- Thêm hai dòng vào `docs/du-lieu/README.md`.
- Báo cáo `plan/reports/T65.md` và `plan/reports/T66.md` theo mục "Nghiệm thu" của hai brief gốc, cộng kết quả các việc 1–5 ở đây.
- Kiểm kê ca (T65 việc 5): ca đủ dữ liệu tính CrCl; ca có xét nghiệm gan; ca có cơ địa đặc biệt. Dùng `app.db.reader.load_source_cases(Path("."))`, không đọc thẳng `HS-*.json`, không đếm tệp `_kich_ban.json`.

## Cấm

- Sửa `app/`, `tests/`, `config/`, `web/`; sửa dữ liệu ca, `chunks.jsonl`, `tra_cuu.sqlite`.
- Đổi tên hay xoá khoá đã có trong sáu tệp; đụng khoá `quy_tac` (meropenem) của tệp thận.
- Bịa ngưỡng, liều, trích dẫn, mã ICD.
- Commit; in khoá API.
- Chạy `du` / `find` trong `data/kb_sources/ddinter_web` (hàng chục nghìn tệp).

## Nghiệm thu (dán vào báo cáo)

1. Script phủ kín CrCl: 0 điểm chồng, 0 điểm hở cho 17 quy tắc `quy_tac_cho_duyet`.
2. 15/15 dòng `nguong_xet_nghiem` có `kieu_dieu_kien`, `muc_do_de_xuat`; mọi điều kiện có `don_vi_nhan`, `don_vi_ca`, `he_so_ca_sang_nhan`.
3. `cap_thuoc_benh`: số dòng, số hoạt chất, số dòng `ma_icd10` rỗng; số cặp khớp chẩn đoán ca tính lại.
4. Kết quả soát morphin tiêm dưới da (có / không có nguồn).
5. `json.load` đọc được cả sáu tệp; `uv run pytest -q -p no:cacheprovider tests/rules tests/api` vẫn qua (bạn được chạy lệnh này để chắc dữ liệu không làm vỡ luật hiện có).
