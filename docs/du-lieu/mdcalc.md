# MDCalc – toàn bộ 882 công thức lâm sàng đã cào và phân loại

Cập nhật: 19/11/2026. Người ghi: Antigravity (cào trực tiếp và kiểm trên toàn bộ 882 công cụ `type == "c"`).

| Mục | Giá trị |
|:--|:--|
| Trang gốc | https://www.mdcalc.com |
| Giấy phép / lưu ý | Bản dữ liệu phục vụ nghiên cứu phi thương mại; lưu ý điều khoản sử dụng MDCalc (20/05/2026) trước khi đưa vào vận hành thương mại hoặc công bố dẫn xuất |
| Tầng tin cậy | Tham chiếu cấu trúc, đầu vào, đơn vị và bài báo gốc; **logic tính thực thi trong `app/calc/` vẫn tự cài bằng hàm thuần Python theo bài báo gốc** và kiểm chéo |
| Cách lấy | API danh mục `GET /api/v1/search/tools` (1.000 mục: 882 `c`, 114 `g`, 4 `x`) + bóc `<script id="__NEXT_DATA__">` từ HTML từng trang `/calc/<id>/<slug>` |
| Ngày lấy | 19/11/2026 |
| Lệnh | `uv run python tools/scrape_mdcalc.py fetch` → `parse` → `verify` |

## 1. Cấu trúc tệp trong `data/formulas/`

Thư mục `data/formulas/` nằm trong `.gitignore` (chỉ giữ `data/formulas/README.md` trên git).

| Tầng | Đường dẫn | Nội dung |
|:--|:--|:--|
| Thô | `data/formulas/raw/tools_index.json`, `manifest.json`, `calcs/*.json` | Danh mục 1.000 mục + 882 tệp `pageProps` gốc kèm SHA-256 (0 lỗi tải) |
| Đã chuẩn hoá (gộp) | `data/formulas/curated/cong_thuc_mdcalc.json` | 882 công thức, tên trường `snake_case` tiếng Việt, giữ nguyên nội dung tiếng Anh từ MDCalc |
| Tách theo nhóm | `data/formulas/curated/theo_nhom/<nhom>.json` | 5 tệp tương ứng 5 nhóm Vinmec (tổng 882 mục) |
| Thống kê phân loại | `data/formulas/curated/thong_ke_phan_loai.json` | Đếm theo nhóm chính/phụ, kiểu input, chuyên khoa và danh sách 14 ca cần rà soát |

## 2. Phân loại toàn bộ 882 công thức trên MDCalc

Trên MDCalc, `calc_type` hầu hết đều là `"calculator"` nên phải phân loại dựa trên `dosing`, `purpose_en`, `input_schema` (`show_points`, `conditionality`, `subheading`) và nội dung `formula_en` / `more_info_en`:

| Nhóm Vinmec (`loai_vinmec`) | Số lượng | Phân loại phụ (`loai_phu`) |
|:--|--:|:--|
| `cong_thuc_toan` | 110 | `phuong_trinh_dai_so` (80), `da_cong_thuc_hoac_co_dieu_kien_bien` (15), `phuong_trinh_kem_bang_he_so` (13), `can_ra_soat_them` (2) |
| `thang_diem` | 484 | `thang_diem_phan_tang_hoac_trong_so_hon_hop` (312), `thang_diem_nhi_phan` (103), `thang_diem_ket_hop_nhap_chi_so` (39), `thang_diem_trong_so_thap_phan` (30) |
| `diem_ra_nguy_co` | 52 | `mo_hinh_hoi_quy_tinh_phan_tram` (43), `mo_hinh_hoi_quy_co_bo_chon_bien_the` (9) |
| `tinh_lieu` | 33 | `tinh_lieu_theo_chi_so_co_the` (24), `quy_doi_lieu_tuong_duong_theo_bang` (7), `huong_dan_lieu_thuoc` (2) |
| `tieu_chi_van_ban` | 203 | `luu_do_quyet_dinh` (131), `bang_kiem_tieu_chi_van_ban` (55), `phan_giai_doan_hoac_tieu_chi_noi_tang` (17) |

## 3. Phân bố 6 kiểu input quan sát được (`6.976` trường trên 882 công thức)

| `kieu_mdcalc` | `kieu_chuan_hoa` | Số trường | Ghi chú |
|:--|:--|--:|:--|
| `toggle` | `chon_nhi_phan_hoac_nut_bam` | 2.838 | Nút bấm 2 lựa chọn (thường kèm điểm 0/+1/+2) |
| `radio` | `chon_mot_trong_nhieu` | 2.467 | Chọn 1 trong N mức điểm hoặc chọn biến thể phương trình |
| `textbox` | `so_thuc` | 1.050 | Số thực gắn `measurements` (đơn vị SI/US, ngưỡng bình thường/cảnh báo/lỗi) |
| `subheading` | `tieu_de_nhom_khong_nhap` | 579 | Tiêu đề phân bước trong lưu đồ/nhóm câu hỏi (`bat_buoc: false`) |
| `visual` | `hinh_minh_hoa_khong_nhap` | 30 | Ảnh minh hoạ nhúng giữa biểu mẫu (`bat_buoc: false`) |
| `dropdown` | `danh_sach_chon` | 12 | Danh sách thả xuống nhiều mục (ví dụ chọn thuốc/loại phẫu thuật ở MME, Gupta, Paxlovid, CTCAE) |

## 4. Kết quả kiểm tra toàn vẹn (19/11/2026)

- `verify`: `Expected type=='c': 882 | Curated: 882 | Missing IDs: 0 | Duplicate IDs: 0 | Empty title=0 | Empty inputs=0 | Invalid group=0 | Group files sum: 882`.
- Duy nhất 1 mục thiếu `tai_lieu_goc` (`10484` EMBED do nguồn không gắn `references_list`).
- 868/882 công thức phân loại với độ tin cậy `cao`; 14/882 gắn `can_ra_soat` (chủ yếu các công thức kiểm tra tiêu chí văn bản không có `formula_en` dạng phương trình hoặc không có danh mục tham số số).
- Hạn chế cố hữu của nguồn: `equation_logic` chỉ là chuỗi MD5 32 ký tự, một số công thức đặt bảng phân hạng ở Result Banner (`340` Child-Pugh) hoặc cây quyết định dạng ảnh PNG (`4067` YEARS).
