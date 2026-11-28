# T68 – Luật D5 (yếu tố 3): đường dùng hợp lệ và liều tối đa

Agent: **agy Gemini 4 Hydrogen**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Claude tự chạy `ruff`, `pytest` khi review.

Chạy **song song** với T67 (luật D4) và một sub dữ liệu (T65-T66 hoàn thiện). Việc nối vào `engine.py` / `registry.py` và chuyển `antibiotic.py` sang yếu tố 6 để cho **T69**. Bạn **không** sửa các tệp đó.

## Đọc trước

- `AGENTS.md` (toàn bộ, nhất là quy tắc 6, 7, 8).
- `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md` mục 2 và **Đợt D5**.
- `app/rules/types.py`, `app/rules/allergy.py` + `app/rules/allergy_config.py` (mẫu nạp bảng lười, dùng `DrugResolver.resolve_line`, `_extract_resolved_ids`, `_is_line_excluded`, căn cứ tài liệu), `app/kb/names.py` (`normalize_key`: bỏ dấu, chữ thường, gộp ký tự không phải chữ số thành một khoảng trắng).
- `app/domain/models.py` (`ChiTietYLenh`: `lieu_moi_lan`, `don_vi_lieu`, `so_lan_moi_ngay`, `duong_dung`, `loai_san_pham`; `Thuoc`: `duong_dung`, `thanh_phan[].ham_luong_thanh_phan`, `don_vi`), `app/domain/loader.py` (`latest_vital`).
- Dữ liệu: `data/kb/duong_dung_hop_le.json` (đọc kỹ `huong_giai_thich`, `bang_chuan_hoa_duong_dung`), `data/kb/lieu_toi_da.json` (đọc kỹ `huong_giai_thich`, `tinh_huong_kiem`).

## Phạm vi tệp

Được tạo: `app/rules/route.py`, `app/rules/max_dose.py`, `app/rules/d5_config.py` (mô hình pydantic `extra="ignore"` + bộ nạp lười hai bảng), `tests/rules/test_route.py`, `tests/rules/test_max_dose.py`.

**Cấm đụng:** `app/rules/engine.py`, `app/rules/registry.py`, `app/rules/__init__.py`, `app/rules/antibiotic.py`, `app/rules/renal_dose.py`, mọi tệp của T67 (`app/rules/hepatic.py`, `lab_threshold.py`, `drug_disease.py`, `d4_config.py`, test tương ứng), mọi tệp test đã có, `data/`, `config/`, `web/`, `docs/`, `plan/`.

## Quy ước chung

- `yeu_to = 3`. Chữ ký: `check(ca: CaBenh, resolver: DrugResolver | None, config: … | None = None) -> list[PhatHien]`. `resolver is None` → `[]`. `config is None` → nạp mặc định (`lru_cache`); tệp không có → `[]`.
- Chỉ xét `pending_lines(ca)`; bỏ dòng `loai_san_pham != "thuoc"` và dòng bị loại trừ theo resolver (dịch truyền, dược liệu, `khong_ap_dung`).
- Dòng resolver trả `khong_nhan_dien` / không ra hoạt chất → `khong_du_du_lieu`, `thong_tin_con_thieu=["hoat_chat"]`.
- Căn cứ `tai_lieu` kèm nguồn và URL, hậu tố "(chờ dược sĩ duyệt)". `khong_du_du_lieu` luôn `muc_do=None` + `thong_tin_con_thieu`. **Không ra `dat` khi thiếu dữ liệu hay thiếu nguồn.**
- Không tự đặt hằng số lâm sàng. Đổi đơn vị khối lượng chỉ dùng `g = 1000 mg`, `mcg = 0,001 mg` (đơn vị SI, không phải hằng số lâm sàng).

## Việc 1 – `route.py`: đường dùng hợp lệ

1. **Chuẩn hoá đường dùng của dòng:** `normalize_key(line.duong_dung)` rồi tra `bang_chuan_hoa_duong_dung.khoa_sang_ma`. Không có `duong_dung` → `khong_du_du_lieu` `["duong_dung"]`, `ma_luat="duong_dung_thieu"`. Khoá nằm trong `tu_mo_ho` hoặc tra ra `null` / không có → `khong_du_du_lieu` `["duong_dung_chuan_hoa"]`, `ma_luat="duong_dung_khong_chuan_hoa_duoc"`, mô tả nêu cách viết gốc.
2. **Nhóm dạng của sản phẩm** (theo `huong_giai_thich.nhom_dang` của tệp): lấy `Thuoc.duong_dung` của danh mục, tách theo `,`, `;`, `/`, chữ ` và `; chuẩn hoá từng phần như bước 1; mã → nhóm:
   - `uong`, `ngam_duoi_luoi` → `dang_uong`
   - `tiem_tinh_mach`, `truyen_tinh_mach`, `tiem_bap`, `tiem_duoi_da`, `tiem_trong_ong_tuy`, `tiem_ngoai_mang_cung` → `dang_tiem_truyen`
   - `dat_truc_trang`, `dat_am_dao` → `dang_dat`; `boi_ngoai_da` → `dang_boi_ngoai_da`; `nho_mat` → `dang_nho_mat`; `xit_mui` → `dang_xit_mui`; `nho_tai`, `hit` → không có nhóm trong bảng (coi như không xác định).
   - Tập nhóm thu được rỗng (danh mục không ghi đường dùng hoặc không chuẩn hoá được) → `khong_du_du_lieu` `["dang_bao_che"]`, `ma_luat="duong_dung_thieu_dang_bao_che"`. Nhiều nhóm → xét lần lượt, dòng hợp lệ nếu hợp lệ với **một** nhóm.
3. **Tra bảng `nhom`:** khoá = `sorted(hoat_chat_ids của dòng)` + `nhom_dang_bao_che`. Thuốc phối hợp không có hàng gộp thì thử hàng của từng hoạt chất; dòng hợp lệ chỉ khi hợp lệ với mọi hoạt chất có hàng. Không có hàng hoặc `duong_dung_hop_le` rỗng → `khong_du_du_lieu` `["nguon_duong_dung"]`, `ma_luat="duong_dung_thieu_nguon"`.
4. **So sánh:** `tiem_tinh_mach` và `truyen_tinh_mach` tương đương nhau (cùng họ tĩnh mạch, theo `huong_giai_thich.tinh_mach`).
   - Đường của dòng nằm trong tập hợp lệ → `dat` `thong_tin`, `ma_luat="duong_dung_hop_le"`.
   - Không nằm trong, và đường của dòng thuộc **nhóm dạng khác** nhóm của sản phẩm (ví dụ sản phẩm `dang_uong` mà kê `tiem_tinh_mach`) → `can_xem` **`nghiem_trong`**, `ma_luat="duong_dung_khac_dang_bao_che"`.
   - Không nằm trong nhưng cùng nhóm dạng (ví dụ `dang_tiem_truyen` kê `tiem_duoi_da` mà nguồn chỉ có tĩnh mạch, bắp) → `can_xem` `can_luu_y`, `ma_luat="duong_dung_ngoai_nguon"`, mô tả: "không thấy trong nguồn đã lấy, chưa phải kết luận kê sai".
   - Mô tả nêu: tên thuốc (`line_label`), đường kê (gốc và mã chuẩn), nhóm dạng, tập hợp lệ; căn cứ `tai_lieu` từ `nguon` của hàng (DAV: số sản phẩm và ví dụ số đăng ký; NDC: `route_goc`, `truy_van`).

## Việc 2 – `max_dose.py`: liều tối đa

1. **Đầu vào của dòng:** thiếu `lieu_moi_lan` → `khong_du_du_lieu` `["lieu_moi_lan"]`; thiếu `so_lan_moi_ngay` → `khong_du_du_lieu` `["so_lan_moi_ngay"]` (vẫn so được liều một lần nếu có trần một lần: khi đó sinh phát hiện cho phần so được và **thêm** một phát hiện thiếu cho liều ngày). `ma_luat="lieu_toi_da_thieu_du_lieu"`.
2. **Đổi liều của dòng sang mg** (theo từng hoạt chất):
   - `don_vi_lieu` chuẩn hoá ∈ `mg`, `g`, `mcg`: đổi trực tiếp (thuốc một thành phần).
   - `vien` (hoặc đơn vị đếm khác như `ong`, `lo`, `goi`): liều mg của hoạt chất = `lieu_moi_lan × ham_luong_thanh_phan` khi `ThanhPhan.don_vi` ∈ `mg`, `g`, `mcg`; thiếu hàm lượng → `khong_du_du_lieu` `["ham_luong_thanh_phan"]`.
   - `mg/kg`: liều mỗi lần theo kg = `lieu_moi_lan`; đổi ra mg cần cân nặng.
   - Đơn vị khác (`mL`, `triệu đơn vị`, `UI`…): chỉ so khi đơn vị trần trong bảng trùng đúng đơn vị dòng sau chuẩn hoá; không thì `khong_du_du_lieu` `["don_vi_lieu_quy_doi"]`.
   - Thuốc nhiều thành phần dạng mg (không phải đơn vị đếm): `khong_du_du_lieu` `["ham_luong_thanh_phan"]` (không chia liều giữa các thành phần).
3. **Chọn hàng bảng:** hàng có `hoat_chat_ids` chứa hoạt chất, `duong_dung` chứa đường chuẩn của dòng (tĩnh mạch tương đương như việc 1; chuẩn hoá đường dùng như việc 1), `loai_gioi_han != "gioi_han_thiet_bi"`.
   - Đối tượng: tra `doi_tuong_dinh_nghia[doi_tuong]` (**khoá MỚI**, sub dữ liệu đang thêm; chưa có thì chỉ dùng hàng có `doi_tuong` ∈ `nguoi_lon`, `nguoi_lon_va_tre_em` cho người ≥ 18 tuổi và bỏ các hàng khác). Hàng có `dieu_kien_khac` khác null: **không dùng để so tự động**; chỉ thêm vào mô tả "nhãn có mức riêng cho: …" khi hoạt chất đó có phát hiện.
   - Hàng cần tuổi / cân nặng mà ca thiếu (`nguoi_benh.tuoi`, `latest_vital(ca, "can_nang")`) và không quyết được hàng nào áp dụng → `khong_du_du_lieu` với trường thiếu (`tuoi` / `can_nang`).
   - Hàng có `thuoc_dung_cung_hoat_chat_ids`: chỉ áp dụng khi một hoạt chất trong danh sách có ở **dòng khác** của `effective_lines(ca)` (dùng resolver); khi áp dụng, ghi rõ thuốc dùng cùng trong mô tả.
   - Hoạt chất không có hàng nào (nằm trong `khong_ghi_toi_da` / `khong_ghi_toi_da_theo_duong_trong_ca`, hoặc không có trong bảng) → `khong_du_du_lieu` `["nguon_lieu_toi_da"]`, `ma_luat="lieu_toi_da_khong_co_nguon"`, mô tả lấy `ly_do` nếu có.
4. **So sánh**, với mỗi hàng áp dụng:
   - `lieu_toi_da_lan` so với liều một lần (mg); `lieu_toi_da_ngay` so với `liều một lần × so_lan_moi_ngay`; đơn vị trần đổi về mg bằng quy tắc SI ở trên.
   - `theo_kg.lan_mg_kg` / `ngay_mg_kg`: cần cân nặng (thiếu → `khong_du_du_lieu` `["can_nang"]`); so liều mg/kg của dòng. Dòng kê `mg/kg` so trực tiếp phần mỗi lần, không cần cân nặng.
   - Vượt bất kỳ trần nào: `toi_da_ro` → `can_xem` `nghiem_trong`, `ma_luat="lieu_toi_da_vuot"`; `tran_up_to` → `can_xem` `can_luu_y`, `ma_luat="lieu_toi_da_vuot_tran_mem"`.
   - Không vượt và đã so ít nhất một trần → `dat` `thong_tin`, `ma_luat="lieu_toi_da_trong_gioi_han"`.
   - Mô tả phải có **phép tính**: ví dụ `"Paracetamol 1000 mg × 6 lần = 6000 mg/ngày > 4000 mg/ngày (nhãn FDA)"`. Căn cứ `du_lieu` gồm liều, số lần, cân nặng (nếu dùng, kèm thời điểm); căn cứ `tinh_toan` ghi phép tính; căn cứ `tai_lieu` từ `nguon` (`trich_nguyen_van`, `url`).
   - Gộp: một phát hiện cho mỗi (dòng, hoạt chất), lấy kết quả nặng nhất giữa các hàng; liệt kê mọi trần đã so trong căn cứ.

## Test (dựng ca bằng pydantic; resolver giả trả `KetQuaPhanGiai` dựng tay; config dựng tay)

Bắt buộc ba tình huống của plan, mỗi cái một test tên rõ:
- `test_levofloxacin_oral_product_ordered_iv`: sản phẩm `duong_dung="uống"`, dòng kê `"tiêm tĩnh mạch"` → `can_xem` `nghiem_trong`, `duong_dung_khac_dang_bao_che`.
- `test_paracetamol_1g_six_times_exceeds_4g`: 1 g × 6, người lớn 60 kg → `lieu_toi_da_vuot`, mô tả chứa `6000` và `4000`.
- `test_gentamicin_per_kg_without_weight`: hàng chỉ có `theo_kg.ngay_mg_kg`, ca không có cân nặng → `khong_du_du_lieu`, `thong_tin_con_thieu` chứa `can_nang`.

Thêm: levofloxacin truyền kê truyền → `dat`; `tiem_tinh_mach` ≡ `truyen_tinh_mach`; đường dùng `"dat"` (mơ hồ) → không chuẩn hoá được; không có hàng → `duong_dung_thieu_nguon`; liều `viên` × hàm lượng; thiếu `so_lan_moi_ngay`; `tran_up_to` → `can_luu_y`; hàng có `dieu_kien_khac` không dùng để so; hàng `thuoc_dung_cung_hoat_chat_ids` chỉ áp dụng khi có thuốc dùng cùng; hoạt chất không có nguồn → `lieu_toi_da_khong_co_nguon`. Một test nạp hai tệp thật `data/kb/` chỉ kiểm nạp được và số hàng > 0. Mọi `khong_du_du_lieu` có `muc_do=None`.

## Nghiệm thu (Claude chạy)

- `uv run ruff check .` sạch; `uv run ruff format --check` sạch trên tệp bạn tạo.
- `uv run pytest -q -p no:cacheprovider tests/rules` qua.

## Khi xong

Viết `plan/reports/T68.md` (được phép tạo riêng tệp này): tệp đã tạo, quyết định khi brief chưa rõ, nghi vấn dữ liệu (không sửa dữ liệu), lệnh Claude cần chạy.
