# T54 – Tải nguồn tầng 0 (văn bản BYT, LiverTox, LactMed)

Ngày lấy: 19/11/2026. User-Agent `VinmecPharmProject-kb/1.0`, nhịp ≥ 1 giây, không đăng nhập, không vượt CAPTCHA. Mỗi thư mục có `manifest.json` (URL, SHA-256, dung lượng, giấy phép, ghi chú).

## Kết quả theo nguồn

| Nguồn | Trạng thái | Thư mục | Dung lượng | Kiểm |
|:--|:--|:--|--:|:--|
| VBHN 15/VBHN-BYT (16/12/2024) | Đã lấy | `data/kb_sources/van_ban_byt/vbhn15_2024/15-vbhn-byt.pdf` | 20,4 MB | 75 trang, PDF ảnh quét; Phụ lục I tr.6–71, Phụ lục II tr.72–74, Phụ lục III tr.75 (đã bãi bỏ). Lớp chữ OCR rất kém (ký tự mất đầu, cột lệch) |
| TT 20/2022/TT-BYT (bản gốc + Phụ lục I) | **Chưa lấy** | (không tạo) | – | Xem mục "Không lấy được" |
| TT 37/2024/TT-BYT | Lấy một phần | `van_ban_byt/tt37_2024/` (`37-byt.pdf`, `37-byt-kem.pdf`) | 8,1 MB + 0,1 MB | 21 trang thân thông tư + 4 trang mẫu kèm; bản cổng Chính phủ chưa điền số/ngày, không có chữ ký; không có phụ lục danh mục thuốc |
| QĐ 5631/QĐ-BYT (31/12/2020) | Lấy (bản sao thứ cấp) | `van_ban_byt/qd5631_2020/qd5631_duytan.pdf` | 1,7 MB | 30 trang, chữ trích sạch; có Phụ lục 1–7 (tr.14–30). Phụ lục 2 (tr.17–19) là danh mục kháng sinh ưu tiên quản lý (Nhóm 1: ceftolozan-tazobactam, tigecyclin, colistin, fosfomycin, linezolid…; Nhóm 2: carbapenem, ertapenem, vancomycin, teicoplanin…). Số và ngày để trống, không chữ ký |
| QĐ 5948/QĐ-BYT (30/12/2021) | **Chưa lấy** | (không tạo) | – | Chỉ có bản trên luatvietnam.vn, bắt buộc đăng nhập |
| LiverTox NBK547852 | Đã lấy (gói chính thức) | `data/kb_sources/livertox/` | gói 196 MB; giải nén 454 MB | 3.438 tệp: 1.389 NXML (BITS 2.0), 1.419 PDF, 626 JPG, `masterlist02-26.xlsx` (1.727 dòng thuốc, có Likelihood Score, phân loại; cập nhật 30/01/2026), 2 docx, `license.txt`. `muc_luc.csv` 1.389 dòng (13 chương không có tên thuốc: hướng dẫn, TOC…) |
| LactMed NBK501922 | Đã lấy (gói chính thức) | `data/kb_sources/lactmed/` | gói 212 MB; giải nén 442 MB | 4.036 tệp: 1.976 NXML, 1.976 PDF, 83 JPG, `license.txt`. `muc_luc.csv` 1.976 dòng (9 chương phụ trợ không tên thuốc) |

URL gói NCBI: `https://ftp.ncbi.nlm.nih.gov/pub/litarch/29/31/livertox_NBK547852.tar.gz` và `.../90/6c/lactmed_NBK501922.tar.gz` (tra từ `https://ftp.ncbi.nlm.nih.gov/pub/litarch/file_list.csv`). Không cào trang HTML.

URL văn bản: VBHN `https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/12/15-vbhn-byt.pdf` (trang `vanban.chinhphu.vn/?classid=2629&docid=212091&pageid=27160`); TT 37 `.../2024/11/37-byt.pdf` và `37-byt-kem.pdf` (docid=211770); QĐ 5631 `files01.duytan.edu.vn/...` (xem manifest).

## Giấy phép
- Văn bản BYT: văn bản quy phạm pháp luật công khai.
- LiverTox / LactMed: theo `license.txt` của gói và Bookshelf Copyright Notice; tệp NXML không có tuyên bố bản quyền riêng nên thuộc phạm vi công cộng, cần ghi nguồn cơ quan tạo lập (NIDDK/NICHD, NLM). Trang web sách trả CAPTCHA nên không đọc được điều khoản trực tiếp; không vượt CAPTCHA.

## Không lấy được và lý do
1. **TT 20/2022 bản gốc kèm Phụ lục I**: vbpl.vn là ứng dụng JS, trang văn bản tự chuyển về trang chủ, không lộ liên kết tệp (đường dẫn `Attachments/.../*.doc` đoán thử trả 404); vanban.chinhphu.vn không tìm thấy mục của TT 20; đoán đường dẫn datafiles đều 404; luatvietnam / thuvienphapluat cần đăng nhập để tải. Thay thế tạm: VBHN 15 chứa Phụ lục I của TT 20 sau hợp nhất (nhưng ảnh quét).
2. **TT 37 bản ký**: chỉ thấy bản đăng cổng chưa điền số/ngày.
3. **QĐ 5631 bản nhà nước/có chữ ký**: static.luatvietnam.vn trả HTML rỗng (chặn đăng nhập). Dùng bản sao Duy Tân (nội dung đủ phụ lục, nhưng thứ cấp, chưa ký).
4. **QĐ 5948/QĐ-BYT**: đã thử luatvietnam.vn (đăng nhập), kết quả tìm kiếm trên moh.gov.vn, kcb.vn, dav.gov.vn không có tệp công khai; `tuongtacthuoc.ehealth.gov.vn` không dùng được (plan 1.8). Không có bản công khai từ nguồn đáng tin.

## Gợi ý tách bảng ở bước sau
- **Phụ lục I (VBHN 15, tr.6–71)**: PDF ảnh quét, OCR hiện có không dùng được (mất ký tự đầu dòng, cột và dấu "+" lệch hàng). Cần OCR lại (ví dụ Tesseract tiếng Việt hoặc dịch vụ OCR khác) ở 300 dpi, hoặc xuất từng trang ra ảnh rồi dùng mô hình thị giác trích bảng theo cột: STT, tên hoạt chất, đường dùng/dạng dùng, hạng bệnh viện (cột 4–6, VBHN đã bỏ cột hạng theo TT 37 nhưng trang scan vẫn có), ghi chú. Khó khăn: bảng nhiều tầng (nhóm 1., 1.1…), ô gộp dòng, đánh số trùng STT theo từng nhóm, dấu sao hội chẩn, ghi chú dài tràn trang. Ưu tiên kiểm lại với bản Word/Excel gốc nếu tìm được từ người dùng (đăng nhập luatvietnam / thuvienphapluat do nhóm tự tải).
- **Phụ lục 2 QĐ 5631 (tr.17–19)**: chữ trích sạch, dùng `pypdf`/`pdfplumber` đủ; bảng 6–7 cột với tiêu đề nhóm (1.1 Nhóm 1, 1.2 Nhóm 2…) chen giữa dòng. Khó khăn: ô "ghi chú" và danh sách thuốc nằm nhiều dòng trong một ô (ví dụ dòng 10, 11 tách rời), ký hiệu `*`/`***` chú thích cuối trang, ký tự tiếng Việt dùng dạng tổ hợp lạ (ví dụ "Ƣ", "Đƣờng") cần chuẩn hoá NFC và thay "ƣ" thành "ư". Phụ lục 3–7 (quy trình, phiếu, chuyển tiêm sang uống) là văn bản/sơ đồ, chưa cần tách bảng.
- **LiverTox / LactMed**: dùng NXML (cấu trúc `book-part`, tiêu đề phần "Likelihood score", "Drug Levels and Effects"); `masterlist02-26.xlsx` cho sẵn thuốc → Likelihood Score → lớp thuốc, nối với chuyên luận qua cột "Chapter Title".

## Lưu ý
- Hai thư mục NCBI nặng khoảng 900 MB và chưa nằm trong `.gitignore`; cân nhắc `.gitignore` các thư mục `giai_nen/` và gói `.tar.gz` trước khi commit.
- Đã dùng `uv run --no-project --with pypdf/openpyxl` (tạm thời, không sửa `pyproject.toml`); script tạm đã xoá.
- Không đụng `app/`, `tests/`, `web/`, `db/`, `config/`, `data/kb_curated`, `data/kb_staging`, README và `manifest.json` gốc.
