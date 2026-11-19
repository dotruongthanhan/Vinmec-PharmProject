# T73 – Công thức đợt 1: Child-Pugh, QTc, canxi hiệu chỉnh; danh mục công thức

Agent: **agy Gemini 4 Hydrogen high**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Claude tự chạy `ruff`, `pytest`.

## Bối cảnh

Người dùng chốt: nguồn công thức theo **MDCalc**. Viện đã gửi xin phép MDCalc nhưng **chưa có văn bản cho phép**, nên đợt này không cào. Claude đọc từng trang như người dùng, ghi lại **dữ kiện công thức và bài báo gốc** dưới đây bằng lời của mình. Công thức lấy theo bài gốc; đường dẫn MDCalc chỉ để tham chiếu và đối chiếu kết quả. **Không** chép văn bản, JSON hay mã logic của trang MDCalc vào kho.

Claude đã kiểm 6 công thức có sẵn trong `app/calc/` (BMI, BSA Mosteller / DuBois, IBW Devine, ABW, Cockcroft-Gault, CKD-EPI 2021): khớp từng số với công thức MDCalc trên 4 bộ số thử. Đợt này chỉ thêm 3 công thức mới và một danh mục.

## Đọc trước

`AGENTS.md` (quy tắc 6, 7), `app/calc/types.py` (`CalcResult`, `CalcInput`, `validate_range`), `app/calc/body.py`, `app/calc/renal.py`, `app/calc/units.py`, `tests/calc/`. Theo đúng kiểu đã có: thiếu đầu vào trả `ket_qua=None` + `thieu_dau_vao`; ngoài miền hợp lệ ném `ValueError`; mỗi hàm có `tham_khao` ghi bài gốc.

## Phạm vi tệp

Tạo: `app/calc/hepatic.py`, `app/calc/cardiac.py`, `app/calc/electrolyte.py`, `tests/calc/test_hepatic.py`, `tests/calc/test_cardiac.py`, `tests/calc/test_electrolyte.py`, `config/kb/cong_thuc.yaml`, `plan/reports/T73.md`.
Sửa: `app/calc/units.py` (thêm hàm đổi đơn vị dưới đây), `app/calc/__init__.py` (xuất hàm mới nếu tệp này đang xuất hàm), `tests/calc/test_units.py` (thêm test).
Cấm: `app/rules/`, `app/api/`, mọi tệp khác. **Chưa nối công thức vào luật** (để task sau).

## Công thức (hằng số dưới đây là dữ kiện được phép dùng; không thêm hằng số khác)

### 1. Child-Pugh – `app/calc/hepatic.py`, hàm `child_pugh(...)` – loại B (thang điểm)

Tham khảo gốc: Child CG, Turcotte JG. Surgery and portal hypertension. In: The liver and portal hypertension. Philadelphia: Saunders 1964:50-64. Pugh RN, Murray-Lyon IM, Dawson JL, Pietroni MC, Williams R. Transection of the oesophagus for bleeding oesophageal varices. Br J Surg 1973;60(8):646-9. Tham chiếu MDCalc: `https://www.mdcalc.com/calc/340`.

Đầu vào: `bilirubin` + `bilirubin_don_vi` (`mg/dL` hoặc `umol/L`), `albumin` + `albumin_don_vi` (`g/dL` hoặc `g/L`), `inr`, `co_truong` ∈ `khong`, `nhe`, `vua` (không có / ít / vừa trở lên), `nao_gan` ∈ `khong`, `do_1_2`, `do_3_4`.

| Thành phần | 1 điểm | 2 điểm | 3 điểm |
|:--|:--|:--|:--|
| Bilirubin toàn phần | < 2 mg/dL (< 34,2 µmol/L) | 2–3 mg/dL (34,2–51,3 µmol/L) | > 3 mg/dL (> 51,3 µmol/L) |
| Albumin | > 3,5 g/dL (> 35 g/L) | 2,8–3,5 g/dL (28–35 g/L) | < 2,8 g/dL (< 28 g/L) |
| INR | < 1,7 | 1,7–2,3 | > 2,3 |
| Cổ trướng | không | nhẹ | vừa |
| Bệnh não gan | không | độ 1–2 | độ 3–4 |

Hai đầu khoảng giữa đều gồm (2 và 3 mg/dL → 2 điểm; 3,5 và 2,8 g/dL → 2 điểm; 1,7 và 2,3 → 2 điểm). Đổi về mg/dL và g/dL trước khi chấm: bilirubin µmol/L ÷ 17,1; albumin g/L ÷ 10.
Kết quả: `ket_qua` = tổng điểm (5–15), `don_vi="diem"`; thêm vào `ghi_chu` hạng: **A** 5–6, **B** 7–9, **C** 10–15 (Pugh 1973). Trả thêm hàm nhỏ `child_pugh_class(diem) -> Literal["A","B","C"]`. Thiếu thành phần nào → `ket_qua=None`, `thieu_dau_vao` liệt kê đúng tên (không chấm điểm mặc định cho thành phần thiếu).

Ca thử (Claude tự tính):
- bilirubin 1,0 mg/dL, albumin 4,0 g/dL, INR 1,1, không cổ trướng, không não gan → 5, A.
- bilirubin 40 µmol/L (= 2,34 mg/dL → 2), albumin 30 g/L (→ 2), INR 1,8 (→ 2), cổ trướng nhẹ (→ 2), không não gan (→ 1) → 9, B.
- bilirubin 4 mg/dL, albumin 2,5 g/dL, INR 2,5, cổ trướng vừa, não gan độ 3–4 → 15, C.
- Biên: bilirubin đúng 2,0 → 2 điểm; albumin đúng 3,5 → 2 điểm; INR đúng 1,7 → 2 điểm.

### 2. QTc – `app/calc/cardiac.py` – loại A (công thức toán)

Đầu vào chung: `qt_ms` (khoảng QT đo được, ms), `nhip_tim` (lần/phút). `RR (giây) = 60 / nhip_tim`. Năm hàm, mỗi hàm trả `don_vi="ms"`:

| Hàm | Công thức | Tham khảo gốc |
|:--|:--|:--|
| `qtc_bazett` | QT / √RR | Bazett HC. Heart 1920;7:353-70 |
| `qtc_fridericia` | QT / RR^(1/3) | Fridericia LS. Acta Med Scand 1920;53:469-86 (bản dịch Ann Noninvasive Electrocardiol 2003;8(4):343-51) |
| `qtc_framingham` | QT + 154 × (1 − RR) | Sagie A, et al. Am J Cardiol 1992;70:797-801 |
| `qtc_hodges` | QT + 1,75 × (nhịp tim − 60) | Hodges M, et al. J Am Coll Cardiol 1983;1:694 |
| `qtc_rautaharju` | QT × (120 + nhịp tim) / 180 | Rautaharju PM, et al. Int J Cardiol 2014;174(3):535-40 |

Tham chiếu MDCalc: `https://www.mdcalc.com/calc/48`. **Không** cài ngưỡng chẩn đoán QT dài (để luật D6 quyết định sau, khi có nguồn được chốt).

Ca thử (QT 400 ms, nhịp 75 → RR 0,8 s): Bazett 447,2; Fridericia 430,9; Framingham 430,8; Hodges 426,25; Rautaharju 433,3 (làm tròn 0,1 trong assert, dùng `pytest.approx(abs=0.1)`). Thêm ca nhịp 60 (RR = 1): cả năm công thức trả đúng 400.

### 3. Canxi hiệu chỉnh theo albumin – `app/calc/electrolyte.py`, hàm `calcium_corrected(...)` – loại A

Tham khảo gốc: Payne RB, Little AJ, Williams RB, Milner JR. Interpretation of serum calcium in patients with abnormal serum proteins. BMJ 1973;4(5893):643-6. Tham chiếu MDCalc: `https://www.mdcalc.com/calc/31`.

Công thức (đơn vị mg/dL và g/dL): **Ca hiệu chỉnh = Ca đo + 0,8 × (albumin bình thường − albumin người bệnh)**. `albumin_binh_thuong` là tham số, mặc định 4,0 g/dL (giá trị mặc định của trang tham chiếu; ghi vào `ghi_chu` khi dùng mặc định).
Đầu vào: `canxi` + `canxi_don_vi` (`mg/dL` hoặc `mmol/L`), `albumin` + `albumin_don_vi` (`g/dL` hoặc `g/L`). Đổi: canxi mmol/L × 4,008 = mg/dL (khối lượng mol Ca 40,08 g/mol); albumin g/L ÷ 10. Kết quả trả **cả hai đơn vị**: `ket_qua` theo đơn vị đầu vào của canxi, `ghi_chu` ghi giá trị ở đơn vị còn lại.

Ca thử: Ca 8,0 mg/dL, albumin 2,5 g/dL → 9,2 mg/dL. Ca 2,00 mmol/L, albumin 25 g/L → 8,016 + 1,2 = 9,216 mg/dL = 2,2994 mmol/L (`approx(abs=0.001)`).

### 4. `app/calc/units.py`

Thêm: `bilirubin_to_mg_dl(gia_tri, don_vi)` (÷ 17,1 cho µmol/L), `albumin_to_g_dl(gia_tri, don_vi)` (÷ 10 cho g/L), `calcium_to_mg_dl(gia_tri, don_vi)` (× 4,008 cho mmol/L), `calcium_mg_dl_to_mmol_l(gia_tri)`. Đơn vị lạ → `ValueError`, như `creatinine_to_mg_dl`.

## 5. Danh mục `config/kb/cong_thuc.yaml`

Mỗi công thức (9 cái có sẵn + mới: `bmi`, `bsa_mosteller`, `bsa_dubois`, `ibw_devine`, `adjusted_body_weight`, `cockcroft_gault`, `egfr_ckd_epi_2021`, `child_pugh`, `qtc_bazett`, `qtc_fridericia`, `qtc_framingham`, `qtc_hodges`, `qtc_rautaharju`, `calcium_corrected`) một mục:

```yaml
- ma: child_pugh
  ten: Child-Pugh
  loai: thang_diem            # cong_thuc_toan | thang_diem | diem_ra_nguy_co | tieu_chi_van_ban | tinh_lieu
  ham: app.calc.hepatic.child_pugh
  dau_ra: {don_vi: diem, phan_hang: [A, B, C]}
  dau_vao:
    - {ten: bilirubin, don_vi: [mg/dL, umol/L], nguon_trong_ca: "xet_nghiem: bilirubin"}
    - {ten: co_truong, kieu: lua_chon, gia_tri: [khong, nhe, vua], nguon_trong_ca: "chưa có trường trong CaBenh"}
  tham_khao_goc: ["Pugh RN ... Br J Surg 1973;60(8):646-9"]
  tham_chieu_mdcalc: https://www.mdcalc.com/calc/340
  trang_thai: chua_duoc_si_duyet
```

`nguon_trong_ca`: mã xét nghiệm / sinh hiệu đang có trong ca (`creatinin`, `bilirubin`, `inr`, `can_nang`, …; xem `docs/du-lieu/ca-gia-lap.md`), hoặc ghi rõ "chưa có trường trong CaBenh" (albumin, canxi, QT, nhịp tim, cổ trướng, bệnh não gan, chiều cao nếu ca chưa có). Mục cũ lấy `tham_khao` từ hàm đã có; `tham_chieu_mdcalc`: Cockcroft-Gault `/calc/43`, CKD-EPI `/calc/3939`, BMI + BSA `/calc/29`, IBW + ABW `/calc/68` (BSA DuBois không có trang riêng: để `null`).

## Nghiệm thu (Claude chạy)

`uv run ruff check .`, `uv run ruff format --check app/calc tests/calc`, `uv run pytest -q -p no:cacheprovider tests/calc`. Claude tự tính lại các ca thử và đối chiếu thêm bằng máy tính MDCalc.

## Khi xong

`plan/reports/T73.md`: tệp đã tạo / sửa, quyết định khi brief chưa rõ, trường ca còn thiếu để dùng từng công thức.
