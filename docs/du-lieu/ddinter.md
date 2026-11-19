# DDInter 2.0 – tương tác thuốc (yếu tố 4)

Cập nhật: 19/11/2026. Người ghi: Claude (đọc trực tiếp tệp dữ liệu).

| Mục | Giá trị |
|:--|:--|
| Trang gốc | https://ddinter2.scbdd.com |
| Giấy phép | CC BY-NC-SA 4.0, **phi thương mại**; dùng cho bản thử học thuật, vận hành ở bệnh viện phải xin phép tác giả |
| Tầng tin cậy | 4, chỉ **sàng lọc**. Luôn ghi "cần đối chiếu"; không bao giờ ra "chống chỉ định" |
| Cách lấy | Cào web (T51, sub Sonnet), ≤ 2 yêu cầu/giây, chạy tiếp được sau khi dừng |
| Ngày lấy | 18–19/11/2026 |
| Lệnh | Cào `uv run python -m app.kb.fetch ddinter <pha>` (`thuoc`, `cap-uu-tien`, `cap-mot-ben`, `cap-tat-ca`) → `phan-tich` → `kiem`; dựng bảng `uv run python -m app.kb.interactions build`; báo cáo ca `... report-ca` |

## 1. Đơn vị: "thuốc" của DDInter là gì

Mỗi mục `DDInterxxxx` là **một chất**, gần như tương đương **một hoạt chất**, không phải biệt dược hay chế phẩm.

- Ví dụ: `Abacavir`, `Methotrexate`, `Amiodarone`.
- Một số mục mang tên muối: `Magnesium sulfate`, `Megestrol acetate`, `Porfimer sodium`.
- Một số là sinh phẩm hoặc vắc xin, ví dụ `Influenza A virus A/California/…`.
- 1.971 chất; chỉ 4 tên có dấu "/", đều là sinh phẩm, không phải thuốc phối hợp.
- Thuốc phối hợp nằm riêng ở mục "chế phẩm phối hợp".

Hệ quả:
- Tương tác thuốc–thuốc thực chất là **hoạt chất × hoạt chất**.
- App nối hoạt chất trên trục RxNorm sang mã DDInter qua cột `hoat_chat.ddinter_id` trong `data/kb_curated/tra_cuu/tra_cuu.sqlite`.
- Biệt dược phối hợp (ví dụ Augmentin) được bộ phân giải tách thành từng hoạt chất rồi mới tra cặp.

## 2. Ba tầng tệp

| Tầng | Đường dẫn | Kích thước | Giữ lâu dài? |
|:--|:--|--:|:--|
| Thô | `data/kb_sources/ddinter_web/` (`thuoc/`, `tuong_tac_thuoc/`, `tuong_tac_benh/`, `tuong_tac_thuc_an/`, `che_pham_phoi_hop/`: mỗi thư mục 1.971 tệp `.gz`; `tuong_tac_chi_tiet/`: 27.936 tệp `.html.gz`; `manifest.json`, `trang_thai.json`) | vài trăm MB, ~38 nghìn tệp | Có, đóng băng theo ngày cào; nên nén thành một gói mỗi lần cào |
| Trung gian | `data/kb_staging/ddinter/*.jsonl` | ~518 MB | Không bắt buộc, dựng lại được bằng `phan-tich` |
| Bộ tra (app đọc) | `data/kb_curated/tuong_tac/ddinter.sqlite` | 133 MB | Có, đây là thứ thành viên cần |
| Lưu trữ cũ | `data/_luu_tru/ddinter_csv_2026-11-16/` (14 CSV bản tải 16/11) | 29 MB | Không. **Toàn bộ 1.971 thuốc và 234.981 cặp đã có trong bản cào web** (Claude kiểm 19/11). Chuyển vào lưu trữ ngày 19/11 |

**Còn code đọc CSV cũ** (phải đổi trước khi xoá hẳn):
- `app/db/sources.py:494`: lệnh `load ddinter` nạp `tri_thuc.tuong_tac_sang_loc` lên Supabase.
- `app/kb/fetch/ddinter.py:99`: bước `kiem` so CSV với web.

## 3. Trường của từng tệp trung gian (`data/kb_staging/ddinter/`)

Mọi dòng đều có thêm `nguon`, `giay_phep`, `url_goc`, `tep_tho` (tệp thô tương ứng) và `ngay_lay`.

### 3.1. `thuoc.jsonl`: 1.971 dòng

| Trường | Ý nghĩa | App dùng? |
|:--|:--|:--|
| `ddinter_id` | Mã DDInter, ví dụ `DDInter1` | ✅ |
| `ten` | Tên tiếng Anh | ✅ |
| `loai_thuoc` | `small molecule` / sinh học | ❌ |
| `ma_atc` | Danh sách mã ATC đầy đủ (mức 5) | ✅ khi nối trục |
| `cas` | Số CAS | ❌ |
| `mo_ta` | Mô tả tiếng Anh | ❌ |
| `lien_ket` | DrugBank, ChEBI… | ❌ |
| `tong_tuong_tac_tren_trang` | Tổng số tương tác thuốc / bệnh / thức ăn / phối hợp ghi trên trang | ✅ **bắt buộc**: so với số đã cào để biết thuốc "đã cào đủ" (điều kiện được ghi "không phát hiện") |

### 3.2. `tuong_tac_thuoc.jsonl`: 553.657 dòng → 291.876 cặp

Mỗi cặp xuất hiện **hai lần**, một lần từ trang của mỗi thuốc.

| Trường | Ý nghĩa | App dùng? |
|:--|:--|:--|
| `ddinter_id_a`, `ddinter_id_b`, `ten_a`, `ten_b` | Cặp thuốc | ✅ |
| `muc_do`, `muc_do_so` | Major 3 / Moderate 2 / Minor 1 / Unknown 0 | ✅ |
| `co_che` | Danh sách cơ chế: Synergy, Antagonism, Absorption, Distribution, Metabolism, Excretion, Others | ✅ |
| `ma_trang_cap` | Mã trang chi tiết cặp (`/server/interact/<mã>/`) | ✅ nối chi tiết |
| `tu_trang_cua` | Dòng này lấy từ trang thuốc nào | ✅ đếm "đã cào đủ" |
| `cot_goc` | Toàn bộ cột JSON gốc | ❌ (chiếm nhiều chỗ nhất) |

### 3.3. `tuong_tac_chi_tiet.jsonl`: 27.936 dòng (~10% số cặp)

Gồm mọi cặp có ít nhất một bên thuộc trục hoạt chất. **Mọi cặp trong 66 ca đều đã có.**

| Trường | Ý nghĩa | App dùng? |
|:--|:--|:--|
| `ma_trang_cap`, `ddinter_id_a/b`, `ten_a/b`, `muc_do`, `co_che` | Như trên | ✅ |
| `hau_qua` | Mô tả hậu quả (tiếng Anh). Cặp mức Unknown: DDInter ghi chữ `None`, bộ dựng coi là thiếu (T55-fix-4) | ✅ căn cứ |
| `xu_tri` | Hướng xử trí (tiếng Anh) | ✅ căn cứ |
| `tai_lieu` | Danh sách tài liệu tham khảo | ✅ căn cứ (chiếm 44 MB trong bộ tra) |
| `thay_the_a`, `thay_the_b` | Nhóm ATC và danh sách thuốc thay thế cho mỗi bên | ❌ (có thể dùng để gợi ý thay thuốc) |
| `cyp_tho` | Văn bản CYP thô, lỗi mã hoá ký tự | ❌ |

### 3.4. `tuong_tac_thuc_an.jsonl`: 805 dòng

`ddinter_id`, `thuc_an` (rượu, bưởi…), `muc_do`, `mo_ta`, `xu_tri`, `co_che`, `tai_lieu`. ✅ dùng: dòng thức ăn dưới ma trận.

### 3.5. `tuong_tac_benh.jsonl`: 8.009 dòng

`ddinter_id`, `ten_benh` (ví dụ `Liver Diseases`), `muc_do`, `noi_dung`, `tai_lieu`, `ma_trang`. ❌ **chưa dùng**; dự kiến cho yếu tố 6 (cơ địa) sau demo.

### 3.6. `che_pham_phoi_hop.jsonl`: 5.663 dòng

`ddinter_id`, `ten_thuong_mai`, `ten_phoi_hop`, `loai_thuoc`, `canh_bao` (số thuốc tối đa cùng nhóm), `ghi_chu`, `cot_goc`. ❌ chưa dùng; trùng ý với trùng nhóm D2.

### 3.7. `uu_tien.json`

Danh sách mã DDInter ưu tiên cào chi tiết.

## 4. Bộ tra `ddinter.sqlite`

| Bảng | Số dòng | Cột |
|:--|--:|:--|
| `cap` | 291.876 | `ddinter_id_a`, `ddinter_id_b` (đã sắp xếp), `muc_do`, `muc_do_so`, `co_che_json`, `co_lech_muc`, `cac_muc_nguon_json`, `ma_trang_cap_json`, `hau_qua`, `xu_tri`, `tai_lieu_json`, `url_goc` |
| `thuoc` | 1.971 | `ddinter_id`, `ten`, `da_cao_du` |
| `thuc_an` | 805 | `ddinter_id`, `thuc_an`, `muc_do`, `mo_ta`, `xu_tri`, `co_che_json` |

Số theo mức:

| Mức | Số cặp |
|:--|--:|
| Major | 50.402 |
| Moderate | 186.830 |
| Minor | 12.229 |
| Unknown | 42.415 |

- 27.644 cặp có chi tiết (hậu quả, xử trí, tài liệu).
- 293 cặp có nhiều mức khác nhau trên web: lấy **mức cao nhất**, `co_lech_muc = 1`.
- 1.971 thuốc đã cào đủ.

## 5. Kết quả kiểm (19/11)

`kiem` (lệnh của bộ cào):
- Lệch đếm 0, lệch đối xứng 0, chi tiết mồ côi 0.
- `web_thieu_trong_csv` 56.896 là cặp web có mà CSV cũ không có, vì web mới hơn.
- `lech_muc_do` 548 dòng, tương ứng 293 cặp ở trên.

Claude kiểm:
- 14 cặp "không phát hiện" trong ca đều có cả hai thuốc đã cào đủ và không có bản ghi cặp.
- 13 cặp nặng / trung bình tra trực tiếp đều có hậu quả và xử trí.

## 6. Việc còn mở / đề xuất giảm tải (chờ nhóm quyết)

- Cào nốt ~235 nghìn trang chi tiết còn lại (~5 ngày chạy nền): đề xuất **không**; chỉ cào bổ sung khi ca mới có cặp thiếu chi tiết.
- Bỏ `tai_lieu_json` khỏi bộ tra (133 → ~85 MB), chỉ giữ link trang gốc.
- Bỏ `cot_goc` khỏi tầng trung gian.
- Đổi lệnh `load ddinter` (Supabase) và `kiem` sang đọc bản cào web, rồi xoá hẳn CSV lưu trữ.
- Thuốc–bệnh: giữ, dùng cho yếu tố 6 sau demo.
