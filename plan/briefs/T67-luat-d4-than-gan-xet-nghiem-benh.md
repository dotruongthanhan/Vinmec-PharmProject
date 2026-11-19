# T67 – Luật D4 (yếu tố 6): liều thận mở rộng, gan theo nhãn, ngưỡng xét nghiệm, thuốc–bệnh

Agent: **agy Gemini 4 Hydrogen**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Claude tự chạy `ruff`, `pytest` khi review.

Chạy **song song** với T68 (luật D5) và một sub dữ liệu (T65-T66 hoàn thiện). Việc nối vào `engine.py` / `registry.py` để cho **T69** làm sau. Bạn **không** sửa hai tệp đó.

## Đọc trước

- `AGENTS.md` (toàn bộ, nhất là quy tắc 6, 7, 8).
- `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md` mục 2 và **Đợt D4**.
- `app/rules/types.py` (`PhatHien`, `CanCu`, `pending_lines`, `line_label`), `app/rules/renal_dose.py`, `app/rules/allergy.py` + `app/rules/allergy_config.py` (mẫu: nạp bảng `data/kb/*.json` lười bằng `lru_cache`, `try_load_default_…`, dùng `DrugResolver.resolve_line`, `_extract_resolved_ids`, `_is_line_excluded`, cách viết căn cứ tài liệu `_build_cross_source_evidence`), `app/rules/interaction.py` (bảng đổi mức DDInter `Major/Moderate/Minor`).
- `app/domain/models.py` (`CaBenh`, `ChanDoan.ma_icd10`, `CoDia`, `KetQuaXetNghiem`), `app/domain/loader.py` (`latest_lab`, `latest_vital`, `ingredients_of`), `app/calc/renal.py` (`cockcroft_gault`).
- Dữ liệu: `data/kb/quy_tac_lieu_than.json`, `data/kb/quy_tac_gan.json`, `data/kb/nguong_xet_nghiem.json`, `data/kb/thuoc_benh_icd.json`. Đọc khoá `ghi_chu` của từng tệp.

## Phạm vi tệp

Được sửa: `app/rules/renal_dose.py`.
Được tạo: `app/rules/hepatic.py`, `app/rules/lab_threshold.py`, `app/rules/drug_disease.py`, `app/rules/d4_config.py` (mô hình pydantic + bộ nạp cho ba bảng gan, xét nghiệm, thuốc–bệnh), `tests/rules/test_renal_dose_d4.py`, `tests/rules/test_hepatic.py`, `tests/rules/test_lab_threshold.py`, `tests/rules/test_drug_disease.py`.

**Cấm đụng:** `app/rules/engine.py`, `app/rules/registry.py`, `app/rules/__init__.py`, `app/rules/antibiotic.py`, mọi tệp của T68 (`app/rules/route*.py`, `app/rules/max_dose*.py`, `app/rules/d5_config.py`, `tests/rules/test_route*.py`, `tests/rules/test_max_dose*.py`), mọi tệp test đã có (kể cả `tests/rules/test_renal_dose.py`: thay đổi của bạn phải giữ nó qua), `data/`, `config/`, `web/`, `docs/`, `plan/`.

## Lược đồ dữ liệu (sub dữ liệu đang thêm các khoá đánh dấu MỚI; code phải đọc được cả khi khoá MỚI chưa có, theo giá trị mặc định ghi dưới)

- `quy_tac_lieu_than.json`: `quy_tac` (đã duyệt, meropenem) và `quy_tac_cho_duyet` (17 quy tắc, cùng lược đồ, thêm `hoat_chat_ids`, `chi_so`, `trang_thai`, `nguon_chi_tiet[]` có `ten_nhan`, `set_id`, `trich_nguyen_van`, `url`; có thể có `phoi_hop`, `bi_danh`). Mỗi mức: `crcl_tu`, `crcl_den`, `bao_gom_can_duoi`, `can_chinh`, `khuyen_cao`, có thể có `nhan_ghi`, `ghi_khoang`, `khong_co_so_lieu_nhan`, **MỚI** `bao_gom_can_tren` (bool | null, mặc định null). Khoá **MỚI** cấp cao `khong_co_nguong` (danh sách, mặc định rỗng).
- `quy_tac_gan.json` → `quy_tac[]`: `ten_quoc_te`, `hoat_chat_ids`, `phan_loai_gan` (danh sách trong `child_pugh_A|B|C`, `nhe_vua`, `nang`, `khong_phan_loai`), `hanh_dong_nhan` (`chong_chi_dinh`, `tranh_khong_khuyen_cao`, `giam_lieu`, `theo_doi`, `khong_chinh_lieu`, `khong_co_khuyen_cao_cu_the`), `khuyen_cao`, `nguon_chi_tiet[]`.
- `nguong_xet_nghiem.json` → `quy_tac[]`: `hoat_chat_ids`, `xet_nghiem`, `dieu_kien[]` (`ma_xet_nghiem`, `toan_tu` ∈ `<`, `<=`, `>`, `>=`, `khoang`; `gia_tri`, `gia_tri_den`; **MỚI** `don_vi_nhan`, `don_vi_ca`, `he_so_ca_sang_nhan`), `hanh_dong_nhan`, `nguon_chi_tiet[]`, **MỚI** `kieu_dieu_kien` ∈ `canh_bao_khi_thoa | canh_bao_khi_ngoai_khoang | dieu_kien_khoi_dau`, **MỚI** `muc_do_de_xuat` ∈ `nghiem_trong | can_luu_y`, **MỚI** `dieu_kien_khac` (chuỗi | null).
- `thuoc_benh_icd.json`: **MỚI** `cap_thuoc_benh[]`: `hoat_chat_id`, `ddinter_id`, `ten_benh`, `ma_icd10` (danh sách: `"N18"`, `"E87.2"`, hoặc khoảng `"D50-D64"`), `muc_do` (`Major|Moderate|Minor`), `noi_dung`, `url`, `trang_thai`.

Mọi mô hình pydantic dùng `extra="ignore"`. Thiếu khoá MỚI thì: dòng xét nghiệm không có `kieu_dieu_kien` → **bỏ qua dòng đó** (không đoán ngữ nghĩa); điều kiện không có `don_vi_ca` → coi như không đổi được đơn vị (xem dưới); tệp thuốc–bệnh không có `cap_thuoc_benh` → luật trả `[]`.

## Quy ước chung cho ba luật mới

- `yeu_to = 6`. Chữ ký: `check(ca: CaBenh, resolver: DrugResolver | None, config: <Config> | None = None) -> list[PhatHien]`. `resolver is None` → trả `[]`. `config is None` → nạp mặc định bằng `try_load_default_…()` có `lru_cache`; tệp không có → trả `[]`.
- Hoạt chất của dòng: `resolver.resolve_line(ca, line)`; bỏ dòng loại trừ (theo cách `allergy._is_line_excluded`); lấy tập `hoat_chat_id` như `allergy._extract_resolved_ids` (chép hàm nhỏ sang module mới hoặc import, không sửa `allergy.py`).
- **Một phát hiện cho mỗi (dòng, quy tắc hoạt chất)**, không nhân đôi khi thuốc phối hợp có nhiều khoá cùng trỏ một quy tắc.
- `can_cu` luôn có: căn cứ `du_lieu` (giá trị ca đã dùng, kèm thời điểm) và căn cứ `tai_lieu` cho mỗi `nguon_chi_tiet`: `'<Nhãn FDA TEN (set_id=…)>: "<trich_nguyen_van>" — <url> (chờ dược sĩ duyệt)'`.
- `khong_du_du_lieu` luôn có `muc_do=None` và `thong_tin_con_thieu` khác rỗng (bất biến của `PhatHien`). **Không bao giờ ra `dat` khi thiếu dữ liệu.**
- Không cài công thức mới. **Không cài Child-Pugh**, không tính diện tích da. Chỉ dùng `cockcroft_gault` đã có.

## Việc 1 – `renal_dose.py` mở rộng

1. Mô hình: `RenalDoseTier` thêm `bao_gom_can_tren: bool | None = None`, `khong_co_so_lieu_nhan: bool = False`; `RenalDrugRule` thêm `hoat_chat_ids: list[str] = []`, `chi_so: str | None = None`, `trang_thai: str | None = None`, `nguon_chi_tiet: list[…] = []` (mô hình nguồn `extra="ignore"`); `RenalRuleBook` thêm `quy_tac_cho_duyet: list[RenalDrugRule] = []`, `khong_co_nguong: list[dict] = []`. Đặt `model_config = ConfigDict(extra="ignore")`.
2. `select_renal_tier`: **giữ nguyên** nhánh đặc biệt 4 mức của meropenem. Ở vòng lặp chung: nếu `bao_gom_can_tren` khác `None` thì cận trên dùng `<=` khi `true`, `<` khi `false`; nếu `None` giữ đúng logic hiện tại.
3. `check(ca, rules, resolver=None)` (tham số mới tuỳ chọn, giữ tương thích mọi chỗ gọi cũ):
   - Không có resolver: hành vi **y hệt hiện tại** (chỉ đọc `quy_tac`, khớp theo `ten_quoc_te`). Test cũ phải qua nguyên.
   - Có resolver: khớp quy tắc khi giao của `hoat_chat_ids` quy tắc (rỗng thì dùng `[ten_quoc_te]`) với tập hoạt chất của dòng khác rỗng. Duyệt `quy_tac` trước, rồi `quy_tac_cho_duyet`; hoạt chất đã khớp ở `quy_tac` thì bỏ ở `quy_tac_cho_duyet`.
   - Tính CrCl, xử lý thiếu đầu vào / số liệu bất thường **đúng như hiện tại** (dùng lại mã `lieu_than_thieu_du_lieu`, `lieu_than_so_lieu_bat_thuong`).
   - `chi_so` chứa `1.73` (CrCl hiệu chỉnh diện tích da, ví dụ levetiracetam) → `khong_du_du_lieu`, `ma_luat="lieu_than_can_crcl_hieu_chinh_bsa"`, `thong_tin_con_thieu=["crcl_hieu_chinh_dien_tich_da"]`, mô tả nói nhãn chia mức theo mL/min/1,73 m², công thức diện tích da chưa được duyệt nên chưa so.
   - Mức chọn được có `khong_co_so_lieu_nhan=true` → `ket_luan="ngoai_hdsd"`, `muc_do="can_luu_y"`, `ma_luat="lieu_than_ngoai_nhan"`, mô tả: nhãn không có khuyến cáo cho mức CrCl này.
   - Quy tắc từ `quy_tac_cho_duyet`: dùng cùng `ma_luat` như cũ (`lieu_than_can_chinh` / `lieu_than_khong_can_chinh`) nhưng: `can_chinh` → `can_xem` mức **`can_luu_y`** (không phải `nghiem_trong`, vì chưa duyệt); mô tả thêm hậu tố ` (quy tắc từ nhãn FDA, chờ dược sĩ duyệt)`; căn cứ `tai_lieu` lấy từ `nguon_chi_tiet` (trích nguyên văn + URL). Quy tắc đã duyệt giữ đúng mức và mô tả cũ.

## Việc 2 – `hepatic.py` (luật gan theo câu nhãn)

Tình trạng gan của người bệnh, chỉ lấy từ `ca.co_dia` loại `suy_gan` mới nhất (theo `thoi_diem`, `None` xếp cũ nhất):
- `trang_thai="khong"` → `khong_suy`.
- `trang_thai="co"`: tìm hạng trong `gia_tri` bằng regex không phân biệt hoa thường `child[\s-]*pugh\s*(?:class\s*)?([abc])\b` → `child_pugh_A|B|C`; không thấy → `co_suy_chua_phan_hang`.
- Không có bản ghi, hoặc `chua_ro` → `chua_danh_gia`.

Dòng áp dụng cho một hạng: `child_pugh_X` khớp đúng hạng; `nhe_vua` khớp A, B; `nang` khớp C; `khong_phan_loai` khớp mọi trường hợp có suy gan.

Mức theo `hanh_dong_nhan`: `chong_chi_dinh`, `tranh_khong_khuyen_cao` → `can_xem` `nghiem_trong`; `giam_lieu`, `theo_doi` → `can_xem` `can_luu_y`; `khong_co_khuyen_cao_cu_the` → `ngoai_hdsd` `can_luu_y`; `khong_chinh_lieu` → `dat` `thong_tin`. Nhiều dòng cùng áp dụng → lấy mức nặng nhất, gộp căn cứ của các dòng áp dụng.

Với mỗi (dòng y lệnh, hoạt chất có trong bảng gan), "dòng cần hành động" = dòng có `hanh_dong_nhan` khác `khong_chinh_lieu`:
| Tình trạng | Kết quả |
|:--|:--|
| `khong_suy` | `dat` `thong_tin`, `ma_luat="gan_khong_suy_gan"` |
| `child_pugh_X` | dòng áp dụng có → theo bảng mức, `ma_luat="gan_theo_nhan"`; không dòng nào áp dụng → `dat` `thong_tin`, `ma_luat="gan_khong_co_khuyen_cao_cho_hang"` |
| `co_suy_chua_phan_hang` | có dòng `khong_phan_loai` cần hành động → theo bảng mức (`gan_theo_nhan`); còn lại nếu có dòng cần hành động theo hạng → `khong_du_du_lieu`, `ma_luat="gan_thieu_phan_hang"`, `thong_tin_con_thieu=["phan_hang_child_pugh"]`, mô tả liệt kê `khuyen_cao` của các dòng; không có dòng cần hành động → `dat` |
| `chua_danh_gia` | có dòng cần hành động → `khong_du_du_lieu`, `ma_luat="gan_chua_danh_gia"`, `thong_tin_con_thieu=["danh_gia_chuc_nang_gan"]`; căn cứ `du_lieu` thêm ALT, AST, bilirubin mới nhất nếu có (chỉ để dược sĩ xem, **không** dùng để phân hạng); không có dòng cần hành động → không sinh phát hiện |

## Việc 3 – `lab_threshold.py` (ngưỡng xét nghiệm theo nhãn)

Với mỗi (dòng y lệnh, hoạt chất) và mỗi dòng bảng của hoạt chất đó (bỏ dòng thiếu `kieu_dieu_kien`):
- Mỗi điều kiện: `latest_lab(ca, ma_xet_nghiem)`. Không có kết quả hoặc `gia_tri_so is None` → điều kiện **thiếu**.
- Đổi đơn vị: chuẩn hoá chuỗi đơn vị (bỏ khoảng trắng, chữ thường; `None` và `""` coi như nhau). Đơn vị ca khớp `don_vi_ca` → `gia_tri_nhan = gia_tri_so × he_so_ca_sang_nhan`. Không khớp, hoặc dòng không có `don_vi_ca` / `he_so_ca_sang_nhan` → điều kiện **không đổi được đơn vị**.
- So sánh theo `toan_tu` (`khoang`: `gia_tri <= x <= gia_tri_den`).
- Kết quả dòng bảng:
  - còn điều kiện thiếu hoặc không đổi được đơn vị → `thieu`;
  - `canh_bao_khi_thoa`: mọi điều kiện đúng → `canh_bao`, ngược lại `dat`;
  - `canh_bao_khi_ngoai_khoang`: giá trị nằm ngoài khoảng → `canh_bao`, trong khoảng → `dat`;
  - `dieu_kien_khoi_dau`: mọi điều kiện đúng → `dat`, có điều kiện sai → `canh_bao`.
- Gộp các dòng bảng của cùng (dòng y lệnh, hoạt chất) thành **một** phát hiện:
  - có `canh_bao` → `can_xem`, `ma_luat="xet_nghiem_vuot_nguong"`, mức = nặng nhất trong `muc_do_de_xuat` của các dòng cảnh báo (thiếu khoá → `can_luu_y`); dòng có `dieu_kien_khac` thì mức tối đa `can_luu_y` và mô tả thêm "cần đối chiếu thêm: <dieu_kien_khac>"; mô tả ghi giá trị ca (đơn vị ca), giá trị đã đổi (đơn vị nhãn), ngưỡng và `hanh_dong_nhan`.
  - không cảnh báo nhưng có `thieu` → `khong_du_du_lieu`, `ma_luat="xet_nghiem_thieu"`, `thong_tin_con_thieu` = các `ma_xet_nghiem` thiếu (thêm hậu tố `_don_vi` nếu thiếu do đơn vị).
  - còn lại → `dat` `thong_tin`, `ma_luat="xet_nghiem_trong_nguong"`.

## Việc 4 – `drug_disease.py` (thuốc–bệnh DDInter theo ICD-10)

- Khớp mã: chuẩn hoá mã ICD (bỏ khoảng trắng, chữ hoa). Mục `"A00-B99"` dạng khoảng: so 3 ký tự đầu của mã ca nằm trong khoảng (so chuỗi chữ cái + 2 số). Mục có dấu chấm (`"E87.2"`): mã ca bắt đầu bằng mục. Mục 3 ký tự: 3 ký tự đầu của mã ca bằng mục.
- Với mỗi (dòng y lệnh, hoạt chất có trong `cap_thuoc_benh`):
  - khớp ít nhất một `chan_doan.ma_icd10` → mỗi bệnh khớp một phát hiện `can_xem`, `ma_luat="thuoc_benh_ddinter"`, mức theo bảng của `interaction.py` (`Major → nghiem_trong`, `Moderate → can_luu_y`, `Minor → thong_tin`). Mô tả: `"<thuốc> – <ten_benh> (chẩn đoán <mã> <noi_dung chẩn đoán>): DDInter mức …, chỉ dùng sàng lọc"`. Căn cứ: `du_lieu` cho `chan_doan_id`; `tai_lieu` gồm `noi_dung`, `url`, chữ "DDInter 2.0, CC BY-NC-SA 4.0, chỉ dùng sàng lọc, chờ dược sĩ duyệt". **Không** viết chữ "chống chỉ định" trong mô tả hay căn cứ.
  - không khớp, và có chẩn đoán không có `ma_icd10` (hoặc ca không có chẩn đoán) → `khong_du_du_lieu`, `ma_luat="thuoc_benh_thieu_icd"`, `thong_tin_con_thieu=["ma_icd10_chan_doan"]`.
  - không khớp và mọi chẩn đoán đều có mã → `dat` `thong_tin`, `ma_luat="thuoc_benh_khong_khop"`.
- Cặp có `ma_icd10` rỗng: bỏ qua khi so, nhưng không làm hoạt chất đó thành "đạt" nếu đó là các cặp duy nhất của hoạt chất (khi đó không sinh phát hiện).

## Test (dựng ca trong test bằng pydantic, không đọc `HS-*.json` thẳng)

- Dùng resolver giả: lớp nhỏ trong test có `resolve_line(ca, line)` trả `KetQuaPhanGiai` dựng tay. Không mở `tra_cuu.sqlite` trong test đơn vị.
- Dùng config dựng tay trong test (truyền tham số `config`), **cộng** một test nạp tệp thật trong `data/kb/` chỉ kiểm nạp được và số dòng > 0 (bỏ qua bằng `pytest.skip` nếu khoá MỚI chưa có).
- Tối thiểu:
  - Thận: `bao_gom_can_tren=false` ở điểm 30 rơi đúng mức trên; ca thiếu cân nặng → `khong_du_du_lieu`; quy tắc chờ duyệt → `can_luu_y` và có hậu tố; chỉ số `1.73` → `lieu_than_can_crcl_hieu_chinh_bsa`; `khong_co_so_lieu_nhan` → `ngoai_hdsd`; thuốc phối hợp piperacillin + tazobactam ra **một** phát hiện; không resolver → kết quả giống hệt bản cũ (meropenem).
  - Gan: đủ năm hàng của bảng tình trạng; regex nhận `Child-Pugh B`, `child pugh class c`.
  - Xét nghiệm: ba kiểu điều kiện, mỗi kiểu có ca dương và âm; đổi creatinin µmol/L → mg/dL (tự tính trong test: 150 µmol/L × 0,011312 = 1,697 > 1,6); đơn vị lệch → `khong_du_du_lieu` hậu tố `_don_vi`; không có xét nghiệm → `khong_du_du_lieu`; `dieu_kien_khac` hạ mức về `can_luu_y`.
  - Thuốc–bệnh: khớp khoảng `N00-N19` với `N18.2`, khớp `E87.2`, không khớp `E87.1` với mục `E87.2`; chẩn đoán thiếu mã → `khong_du_du_lieu`; không có chữ "chống chỉ định".
  - Mọi phát hiện `khong_du_du_lieu` có `muc_do=None`.

## Nghiệm thu (Claude chạy)

- `uv run ruff check .` sạch; `uv run ruff format --check` sạch trên các tệp bạn tạo / sửa.
- `uv run pytest -q -p no:cacheprovider tests/rules` qua, gồm `tests/rules/test_renal_dose.py` cũ không sửa.
- Toàn kho không thêm test trượt.

## Khi xong

Viết `plan/reports/T67.md` (được phép tạo riêng tệp này): tệp đã tạo / sửa, quyết định khi brief chưa rõ, các điểm bạn nghi dữ liệu sai (không sửa dữ liệu), lệnh Claude cần chạy.
