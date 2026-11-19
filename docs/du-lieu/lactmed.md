# LactMed – thuốc và cho con bú

Cập nhật: 19/11/2026. Đọc trực tiếp tệp, manifest và mã ứng dụng; không gọi mạng.

| Mục | Giá trị |
|:--|:--|
| Trang gốc | NCBI Bookshelf, NBK501922; [gói chính thức](https://ftp.ncbi.nlm.nih.gov/pub/litarch/90/6c/lactmed_NBK501922.tar.gz); danh sách gói: https://ftp.ncbi.nlm.nih.gov/pub/litarch/file_list.csv |
| Giấy phép | `license.txt` yêu cầu xét tuyên bố bản quyền/giấy phép của từng XML/PDF và tệp đi kèm. Tài liệu không có tuyên bố thuộc phạm vi công cộng, phải ghi nguồn NICHD/NLM. Quét NXML không thấy thẻ copyright; chưa rà riêng điều khoản trong mọi PDF/ảnh/tệp bổ trợ. Không suy rộng giấy phép một tệp cho cả gói. |
| Tầng tin cậy | 3 theo manifest. Tiêu đề báo cáo T54 ghi “nguồn tầng 0” nhưng không định nghĩa số 0; tài liệu này giữ giá trị manifest và ghi nhận chênh lệch đó. |
| Cách lấy | T54 tải gói chính thức, giải nén NXML BITS 2.0/PDF/JPG và lập `muc_luc.csv`; không cào HTML. User-Agent `VinmecPharmProject-kb/1.0`, nhịp ít nhất một giây theo báo cáo. |
| Ngày lấy | 19/11/2026 theo manifest; ghi chú gói cập nhật 22/10/2026. |
| Lệnh | Chưa xác định lệnh shell tải/lập mục lục gốc: manifest và báo cáo không lưu nguyên văn. CLI `app/kb/fetch/__main__.py` chưa có nguồn lactmed. Lệnh kiểm chỉ đọc đã chạy được chép nguyên ở cuối tệp. |

## 1. Đơn vị dữ liệu

Một `.nxml` là một chương/phần sách, có thể là chuyên luận thuốc, nhóm thuốc hoặc chương phụ trợ. Một dòng `muc_luc.csv` trỏ tới một chương NXML cùng PDF: **1.976 dòng dữ liệu**, không gồm tiêu đề, **9 dòng không có `ten`**. PDF là bản trình bày tài liệu; JPG là ảnh, không phải bản ghi thuốc.

## 2. Ba tầng tệp

Kích thước là tổng `stat().st_size` của tệp thường, đơn vị byte; không phải dung lượng cấp phát đĩa.

| Tầng | Đường dẫn | Số lượng / kích thước byte | Giữ lâu dài? |
|:--|:--|--:|:--|
| Thô | `data/kb_sources/lactmed/lactmed_NBK501922.tar.gz` | 211.615.014 | Có, gói tải có mã băm |
| Thô giải nén | `data/kb_sources/lactmed/giai_nen/lactmed_NBK501922/` | 4.036 tệp; 242.572.268 | Có thể giải nén lại |
| Thô: NXML | `data/kb_sources/lactmed/giai_nen/lactmed_NBK501922/*.nxml` | 1.976 tệp; 26.454.132 | Nội dung để xử lý sau |
| Thô: PDF | `data/kb_sources/lactmed/giai_nen/lactmed_NBK501922/*.pdf` | 1.976 tệp; 215.517.402 | Đối chiếu bản trình bày |
| Thô: JPG | `data/kb_sources/lactmed/giai_nen/lactmed_NBK501922/*.jpg` | 83 tệp; 599.714 | Tệp ảnh liên quan |
| Siêu dữ liệu | `data/kb_sources/lactmed/manifest.json` | 1.115 | Có |
| Trung gian: mục lục | `data/kb_sources/lactmed/muc_luc.csv` | 1.976 dòng; 199.513 | Có; hiện đặt cùng nguồn, chưa ở `kb_staging` |
| Bộ tra | Chưa có SQLite/chunks riêng cho lactmed | Chưa tạo; không gán kích thước 0 cho tệp không tồn tại | Chưa áp dụng |

Tổng cả thư mục nguồn, gồm gói nén, giải nén, manifest và CSV: **454.387.910 byte**. `license.txt`: 1.020 byte.

## 3. Trường của từng tệp

✅ là có đường đọc trong mã hiện tại, có ghi rõ giai đoạn dùng. ❌ là chưa có đường dùng tương ứng trong `app/`.

### 3.1. `muc_luc.csv`

| Trường | Ý nghĩa | App dùng ở đâu? |
|:--|:--|:--|
| `ma_chuyen_luan` | Mã chương do bước lập mục lục ghi | ❌ Chưa nối trục hoặc dùng để trích dẫn |
| `ten` | Tên chương/thuốc, có thể rỗng ở chương phụ trợ | ✅ `app/kb/coverage/storage.py:_read_catalog` đọc cho báo cáo; `coverage/report.py:calculate_coverage` khớp tên INN sau `normalize_key`. Chỉ báo hiện diện nguồn, không đọc nội dung chuyên luận khi thẩm định ca. |
| `duong_dan_nxml` | Đường dẫn tương đối với `data/kb_sources/lactmed/`, không phải gốc dự án | ❌ Coverage không mở XML |
| `duong_dan_pdf` | Đường dẫn PDF tương đối cùng thư mục nguồn | ❌ Coverage không mở PDF |

### 3.2. `manifest.json`

| Trường | Ý nghĩa | App dùng ở đâu? |
|:--|:--|:--|
| `ma` | Mã bộ nguồn | ❌ Lưu vết tải; app chưa đọc manifest này |
| `ten` | Tên sách và cơ quan | ❌ Lưu vết tải; app chưa đọc manifest này |
| `nguon` | Nguồn phát hành gói | ❌ Lưu vết tải; app chưa đọc manifest này |
| `tang_tin_cay` | Tầng tin cậy theo manifest | ❌ Lưu vết tải; app chưa đọc manifest này |
| `giay_phep` | Ghi chú quyền dùng; phải đối chiếu license.txt và từng tài liệu | ❌ Lưu vết tải; app chưa đọc manifest này |
| `dinh_dang` | Định dạng có trong gói | ❌ Lưu vết tải; app chưa đọc manifest này |
| `so_chuyen_luan_nxml` | Số tài liệu XML khi tải | ❌ Lưu vết tải; app chưa đọc manifest này |
| `ngay_lay` | Ngày lấy gói | ❌ Lưu vết tải; app chưa đọc manifest này |
| `user_agent` | User-Agent dùng lúc tải | ❌ Lưu vết tải; app chưa đọc manifest này |
| `cac_tep` | Danh sách gói tải | ❌ Lưu vết tải; app chưa đọc manifest này |
| `cac_tep[].tep` | Tên gói cục bộ | ❌ Lưu vết tải; app chưa đọc manifest này |
| `cac_tep[].url_tai_truc_tiep` | URL gói chính thức | ❌ Lưu vết tải; app chưa đọc manifest này |
| `cac_tep[].trang_chua_lien_ket` | Mục lục gói NCBI | ❌ Lưu vết tải; app chưa đọc manifest này |
| `cac_tep[].sha256` | Mã băm gói | ❌ Lưu vết tải; app chưa đọc manifest này |
| `cac_tep[].dung_luong_byte` | Dung lượng gói | ❌ Lưu vết tải; app chưa đọc manifest này |
| `cac_tep[].ghi_chu` | Ngày cập nhật gói và nơi giải nén | ❌ Lưu vết tải; app chưa đọc manifest này |

### 3.3. NXML: từng tên phần tử và thuộc tính thực có

Gốc thực là `book-part-wrapper`; hai nhánh chính là `book-meta` và `book-part`. Metadata chương ở `book-part/book-part-meta`, tiêu đề ở `title-group/title`, ngày ở `pub-history/date`; nội dung ở `book-part/body/sec`, có `sec` lồng nhau. Bảng ở `table-wrap/table/(thead|tbody)/tr/(th|td)`; tài liệu dẫn ở `ref-list/ref`.

Drug Levels and Effects và Substance Identification là các mục trong cây; từ khóa/định danh chất còn có `book-part-meta/kwd-group/kwd`. Chưa rút thành trường đánh giá an toàn cho con bú. Bảng sau là hợp tên thẻ từ toàn bộ NXML; không phải mọi chương đều có đủ.

| Trường | Ý nghĩa | App dùng ở đâu? |
|:--|:--|:--|
| `abstract` | Tóm tắt sách/chương | ❌ Chưa có parser nguồn này trong app |
| `aff` | Cơ quan của tác giả | ❌ Chưa có parser nguồn này trong app |
| `alt-text` | Văn bản thay thế của hình | ❌ Chưa có parser nguồn này trong app |
| `article-title` | Tiêu đề bài báo tham khảo | ❌ Chưa có parser nguồn này trong app |
| `body` | Thân chuyên luận | ❌ Chưa có parser nguồn này trong app |
| `bold` | Định dạng in đậm | ❌ Chưa có parser nguồn này trong app |
| `book-app` | Phụ lục sách | ❌ Chưa có parser nguồn này trong app |
| `book-id` | Định danh sách; thuộc tính book-id-type cho biết hệ mã | ❌ Chưa có parser nguồn này trong app |
| `book-meta` | Siêu dữ liệu sách | ❌ Chưa có parser nguồn này trong app |
| `book-page-count` | Số trang sách trong counts | ❌ Chưa có parser nguồn này trong app |
| `book-part` | Chương/phần sách bên trong wrapper | ❌ Chưa có parser nguồn này trong app |
| `book-part-id` | Định danh chương; book-part-id-type xác định hệ mã | ❌ Chưa có parser nguồn này trong app |
| `book-part-meta` | Siêu dữ liệu chương | ❌ Chưa có parser nguồn này trong app |
| `book-part-wrapper` | Gốc tài liệu BITS; bao siêu dữ liệu sách và chương | ❌ Chưa có parser nguồn này trong app |
| `book-title` | Tiêu đề sách được dẫn hoặc sách chủ | ❌ Chưa có parser nguồn này trong app |
| `book-title-group` | Nhóm tiêu đề sách | ❌ Chưa có parser nguồn này trong app |
| `chapter-title` | Tiêu đề chương được dẫn | ❌ Chưa có parser nguồn này trong app |
| `collab` | Tác giả tập thể | ❌ Chưa có parser nguồn này trong app |
| `comment` | Ghi chú trong trích dẫn | ❌ Chưa có parser nguồn này trong app |
| `conf-loc` | Địa điểm hội nghị của tài liệu dẫn | ❌ Chưa có parser nguồn này trong app |
| `conf-name` | Tên hội nghị của tài liệu dẫn | ❌ Chưa có parser nguồn này trong app |
| `contrib` | Tác giả/người đóng góp | ❌ Chưa có parser nguồn này trong app |
| `contrib-group` | Nhóm người đóng góp | ❌ Chưa có parser nguồn này trong app |
| `counts` | Khối số đếm xuất bản | ❌ Chưa có parser nguồn này trong app |
| `custom-meta` | Điểm siêu dữ liệu tự định nghĩa | ❌ Chưa có parser nguồn này trong app |
| `custom-meta-group` | Nhóm siêu dữ liệu mở rộng | ❌ Chưa có parser nguồn này trong app |
| `date` | Ngày cập nhật/chỉnh sửa; date-type chỉ loại ngày | ❌ Chưa có parser nguồn này trong app |
| `date-in-citation` | Ngày trong tài liệu dẫn | ❌ Chưa có parser nguồn này trong app |
| `day` | Ngày trong một ngày tháng | ❌ Chưa có parser nguồn này trong app |
| `def` | Nội dung định nghĩa | ❌ Chưa có parser nguồn này trong app |
| `def-item` | Một cặp thuật ngữ/định nghĩa | ❌ Chưa có parser nguồn này trong app |
| `def-list` | Danh sách định nghĩa | ❌ Chưa có parser nguồn này trong app |
| `degrees` | Học vị tác giả | ❌ Chưa có parser nguồn này trong app |
| `edition` | Lần xuất bản của tài liệu dẫn | ❌ Chưa có parser nguồn này trong app |
| `element-citation` | Trích dẫn có cấu trúc | ❌ Chưa có parser nguồn này trong app |
| `elocation-id` | Định danh vị trí điện tử của bài báo | ❌ Chưa có parser nguồn này trong app |
| `email` | Địa chỉ liên hệ nguồn | ❌ Chưa có parser nguồn này trong app |
| `etal` | Dấu rút gọn danh sách tác giả | ❌ Chưa có parser nguồn này trong app |
| `ext-link` | Liên kết ngoài; xlink:href là đích | ❌ Chưa có parser nguồn này trong app |
| `fpage` | Trang đầu tài liệu dẫn | ❌ Chưa có parser nguồn này trong app |
| `given-names` | Tên riêng tác giả | ❌ Chưa có parser nguồn này trong app |
| `graphic` | Tệp ảnh liên kết | ❌ Chưa có parser nguồn này trong app |
| `issue` | Số tạp chí | ❌ Chưa có parser nguồn này trong app |
| `italic` | Định dạng nghiêng | ❌ Chưa có parser nguồn này trong app |
| `kwd` | Từ khóa của chuyên luận | ❌ Chưa có parser nguồn này trong app |
| `kwd-group` | Nhóm từ khóa/định danh chất | ❌ Chưa có parser nguồn này trong app |
| `label` | Nhãn hình/bảng/mục | ❌ Chưa có parser nguồn này trong app |
| `list` | Danh sách | ❌ Chưa có parser nguồn này trong app |
| `list-item` | Một mục danh sách | ❌ Chưa có parser nguồn này trong app |
| `lpage` | Trang cuối tài liệu dẫn | ❌ Chưa có parser nguồn này trong app |
| `meta-name` | Tên khóa siêu dữ liệu | ❌ Chưa có parser nguồn này trong app |
| `meta-value` | Giá trị khóa siêu dữ liệu | ❌ Chưa có parser nguồn này trong app |
| `mixed-citation` | Trích dẫn hỗn hợp văn bản và thẻ | ❌ Chưa có parser nguồn này trong app |
| `month` | Tháng trong ngày tháng | ❌ Chưa có parser nguồn này trong app |
| `name` | Tên tác giả có cấu trúc | ❌ Chưa có parser nguồn này trong app |
| `nav-pointer` | Con trỏ điều hướng mục lục | ❌ Chưa có parser nguồn này trong app |
| `notes` | Ghi chú/miễn trừ của nguồn | ❌ Chưa có parser nguồn này trong app |
| `p` | Đoạn văn; có thể chứa nội dung chuyên luận, ca minh họa hay thư mục | ❌ Chưa có parser nguồn này trong app |
| `person-group` | Nhóm tác giả tài liệu dẫn | ❌ Chưa có parser nguồn này trong app |
| `pub-date` | Ngày xuất bản | ❌ Chưa có parser nguồn này trong app |
| `pub-history` | Lịch sử cập nhật | ❌ Chưa có parser nguồn này trong app |
| `pub-id` | Định danh tài liệu dẫn, ví dụ PubMed | ❌ Chưa có parser nguồn này trong app |
| `publisher` | Thông tin nhà xuất bản | ❌ Chưa có parser nguồn này trong app |
| `publisher-loc` | Địa điểm nhà xuất bản | ❌ Chưa có parser nguồn này trong app |
| `publisher-name` | Tên nhà xuất bản | ❌ Chưa có parser nguồn này trong app |
| `ref` | Một tài liệu tham khảo | ❌ Chưa có parser nguồn này trong app |
| `ref-list` | Danh sách tài liệu tham khảo | ❌ Chưa có parser nguồn này trong app |
| `related-object` | Liên kết chương/sách liên quan | ❌ Chưa có parser nguồn này trong app |
| `season` | Mùa xuất bản | ❌ Chưa có parser nguồn này trong app |
| `sec` | Mục/tiểu mục; id định danh, sec-type loại mục | ❌ Chưa có parser nguồn này trong app |
| `source` | Tên tạp chí/nguồn của trích dẫn | ❌ Chưa có parser nguồn này trong app |
| `string-name` | Tên tác giả dạng chuỗi hỗn hợp | ❌ Chưa có parser nguồn này trong app |
| `sub` | Chỉ số dưới | ❌ Chưa có parser nguồn này trong app |
| `suffix` | Hậu tố tên tác giả | ❌ Chưa có parser nguồn này trong app |
| `sup` | Chỉ số trên | ❌ Chưa có parser nguồn này trong app |
| `supplement` | Phụ bản trong trích dẫn | ❌ Chưa có parser nguồn này trong app |
| `surname` | Họ tác giả | ❌ Chưa có parser nguồn này trong app |
| `table` | Bảng của nguồn | ❌ Chưa có parser nguồn này trong app |
| `table-wrap` | Khối bảng có tiêu đề, chú thích | ❌ Chưa có parser nguồn này trong app |
| `tbody` | Thân bảng | ❌ Chưa có parser nguồn này trong app |
| `td` | Ô dữ liệu | ❌ Chưa có parser nguồn này trong app |
| `term` | Thuật ngữ được định nghĩa | ❌ Chưa có parser nguồn này trong app |
| `th` | Ô tiêu đề bảng | ❌ Chưa có parser nguồn này trong app |
| `thead` | Phần tiêu đề bảng | ❌ Chưa có parser nguồn này trong app |
| `title` | Tiêu đề mục, bảng hoặc chú thích | ❌ Chưa có parser nguồn này trong app |
| `title-group` | Nhóm tiêu đề chương | ❌ Chưa có parser nguồn này trong app |
| `toc` | Mục lục sách | ❌ Chưa có parser nguồn này trong app |
| `toc-entry` | Một mục trong mục lục | ❌ Chưa có parser nguồn này trong app |
| `tr` | Hàng bảng | ❌ Chưa có parser nguồn này trong app |
| `underline` | Định dạng gạch dưới | ❌ Chưa có parser nguồn này trong app |
| `volume` | Tập tạp chí | ❌ Chưa có parser nguồn này trong app |
| `xref` | Tham chiếu nội bộ; rid trỏ id, ref-type chỉ loại đích | ❌ Chưa có parser nguồn này trong app |
| `year` | Năm trong ngày tháng | ❌ Chưa có parser nguồn này trong app |

Thuộc tính được liệt kê riêng theo phần tử chủ. `xlink` là namespace `http://www.w3.org/1999/xlink`; các thuộc tính trình bày cũng được giữ nguyên trong nguồn.

| Trường | Ý nghĩa | App dùng ở đâu? |
|:--|:--|:--|
| `book-part-wrapper/@content-type` | Loại nội dung do nguồn gán | ❌ Chưa đọc |
| `book-part-wrapper/@dtd-version` | Phiên bản DTD BITS | ❌ Chưa đọc |
| `book-part-wrapper/@from-where` | Vị trí phần trong sách | ❌ Chưa đọc |
| `book-part-wrapper/@id` | Định danh nội bộ XML | ❌ Chưa đọc |
| `book-id/@book-id-type` | Hệ mã sách | ❌ Chưa đọc |
| `pub-date/@date-type` | Loại ngày | ❌ Chưa đọc |
| `pub-date/@publication-format` | Dạng xuất bản | ❌ Chưa đọc |
| `notes/@notes-type` | Loại ghi chú | ❌ Chưa đọc |
| `notes/@specific-use` | Phạm vi sử dụng do nguồn gán | ❌ Chưa đọc |
| `p/@content-type` | Loại nội dung do nguồn gán | ❌ Chưa đọc |
| `book-part/@book-part-type` | Loại phần sách | ❌ Chưa đọc |
| `book-part/@indexed` | Cờ lập chỉ mục nguồn | ❌ Chưa đọc |
| `book-part-id/@book-part-id-type` | Hệ mã chương | ❌ Chưa đọc |
| `date/@date-type` | Loại ngày | ❌ Chưa đọc |
| `related-object/@document-id` | Định danh tài liệu đích | ❌ Chưa đọc |
| `related-object/@document-id-type` | Hệ định danh tài liệu đích | ❌ Chưa đọc |
| `related-object/@document-type` | Loại tài liệu đích | ❌ Chưa đọc |
| `related-object/@link-type` | Loại quan hệ liên kết | ❌ Chưa đọc |
| `related-object/@object-id` | Định danh đối tượng đích | ❌ Chưa đọc |
| `related-object/@object-id-type` | Hệ định danh đối tượng đích | ❌ Chưa đọc |
| `related-object/@object-type` | Loại đối tượng đích | ❌ Chưa đọc |
| `related-object/@source-id` | Định danh nguồn liên quan | ❌ Chưa đọc |
| `kwd-group/@kwd-group-type` | Loại nhóm từ khóa | ❌ Chưa đọc |
| `kwd-group/@specific-use` | Phạm vi sử dụng do nguồn gán | ❌ Chưa đọc |
| `sec/@id` | Định danh nội bộ XML | ❌ Chưa đọc |
| `sec/@sec-type` | Loại mục | ❌ Chưa đọc |
| `xref/@ref-type` | Loại đích tham chiếu nội bộ | ❌ Chưa đọc |
| `xref/@rid` | Id đích tham chiếu nội bộ | ❌ Chưa đọc |
| `italic/@toggle` | Quy tắc đảo định dạng | ❌ Chưa đọc |
| `ref-list/@id` | Định danh nội bộ XML | ❌ Chưa đọc |
| `ref/@id` | Định danh nội bộ XML | ❌ Chưa đọc |
| `mixed-citation/@publication-type` | Loại tài liệu tham khảo | ❌ Chưa đọc |
| `string-name/@name-style` | Kiểu trình bày tên | ❌ Chưa đọc |
| `fpage/@seq` | Thứ tự phân trang | ❌ Chưa đọc |
| `pub-id/@pub-id-type` | Hệ định danh tài liệu dẫn | ❌ Chưa đọc |
| `book-page-count/@count` | Số đếm | ❌ Chưa đọc |
| `element-citation/@publication-type` | Loại tài liệu tham khảo | ❌ Chưa đọc |
| `name/@name-style` | Kiểu trình bày tên | ❌ Chưa đọc |
| `contrib/@contrib-type` | Vai trò người đóng góp | ❌ Chưa đọc |
| `aff/@id` | Định danh nội bộ XML | ❌ Chưa đọc |
| `table-wrap/@id` | Định danh nội bộ XML | ❌ Chưa đọc |
| `table-wrap/@orientation` | Hướng trình bày | ❌ Chưa đọc |
| `table-wrap/@position` | Vị trí trình bày | ❌ Chưa đọc |
| `table/@frame` | Viền bảng | ❌ Chưa đọc |
| `table/@rules` | Quy tắc kẻ bảng | ❌ Chưa đọc |
| `td/@align` | Căn ngang | ❌ Chưa đọc |
| `td/@colspan` | Số cột gộp | ❌ Chưa đọc |
| `td/@headers` | Các id ô tiêu đề liên quan | ❌ Chưa đọc |
| `td/@rowspan` | Số hàng gộp | ❌ Chưa đọc |
| `td/@scope` | Phạm vi ô tiêu đề | ❌ Chưa đọc |
| `td/@style` | Kiểu trình bày | ❌ Chưa đọc |
| `td/@valign` | Căn dọc | ❌ Chưa đọc |
| `ext-link/@ext-link-type` | Loại liên kết ngoài | ❌ Chưa đọc |
| `ext-link/@xlink:href` | Đích liên kết hoặc tệp đi kèm | ❌ Chưa đọc |
| `book-app/@book-part-type` | Loại phần sách | ❌ Chưa đọc |
| `def-item/@id` | Định danh nội bộ XML | ❌ Chưa đọc |
| `graphic/@mime-subtype` | Kiểu MIME phụ | ❌ Chưa đọc |
| `graphic/@orientation` | Hướng trình bày | ❌ Chưa đọc |
| `graphic/@position` | Vị trí trình bày | ❌ Chưa đọc |
| `graphic/@xlink:href` | Đích liên kết hoặc tệp đi kèm | ❌ Chưa đọc |
| `graphic/@xlink:title` | Tiêu đề liên kết | ❌ Chưa đọc |
| `list/@list-type` | Loại danh sách | ❌ Chưa đọc |
| `date-in-citation/@content-type` | Loại nội dung do nguồn gán | ❌ Chưa đọc |
| `th/@align` | Căn ngang | ❌ Chưa đọc |
| `th/@colspan` | Số cột gộp | ❌ Chưa đọc |
| `th/@id` | Định danh nội bộ XML | ❌ Chưa đọc |
| `th/@rowspan` | Số hàng gộp | ❌ Chưa đọc |
| `th/@scope` | Phạm vi ô tiêu đề | ❌ Chưa đọc |
| `th/@valign` | Căn dọc | ❌ Chưa đọc |
| `toc-entry/@id` | Định danh nội bộ XML | ❌ Chưa đọc |
| `nav-pointer/@nav-pointer-type` | Loại con trỏ mục lục | ❌ Chưa đọc |

### 3.4. Tệp trình bày, gói nén và giấy phép

PDF/JPG là tệp trình bày/phụ trợ, không có schema bản ghi mà app hiện nạp; ❌ chưa dùng. Gói `.tar.gz` là bao lưu trữ. `license.txt` là văn bản điều khoản quyền dùng, ❌ app không đọc; người xử lý cần đối chiếu trước tái sử dụng. Không chép nội dung ca minh họa của chuyên luận vào tài liệu này.

## 4. Bộ tra và sử dụng hiện tại

Chưa có SQLite dành cho lactmed, nên không có `PRAGMA table_info` hoặc `count(*)` để báo. `data/kb_curated/chunks.jsonl` hiện chỉ có nhãn openFDA; lactmed chưa tham gia corpus RAG hoặc cache nhúng đó.

Đường đọc hiện có chỉ đánh dấu hiện diện tên trong báo cáo độ phủ. Có mục lục không đồng nghĩa đã có căn cứ lâm sàng khi thẩm định, khớp mọi tên đồng nghĩa hoặc có nội dung cho mọi thuốc.

## 5. Kết quả kiểm đã có

- T54 ngày 19/11: lấy gói chính thức và lập mục lục; số NXML/CSV khớp manifest.
- Kiểm chỉ đọc ngày 19/11: parse toàn bộ NXML thành công; SHA-256 gói khớp manifest; mọi đường dẫn CSV tồn tại khi ghép với thư mục nguồn; số tên rỗng là 9. Không thấy thẻ copyright trong NXML; chưa kiểm riêng bản quyền mọi PDF/ảnh/tệp bổ trợ.
- Kích thước giải nén ước lượng trong `plan/reports/T54-tai-nguon-van-ban.md` không khớp phép đo byte mục 2; tài liệu này dùng số đo thực.
- `data/kb_sources/README.md` ghi LiverTox/LactMed “chưa tải” đã lỗi thời sau T54.
- `plan/reports/T56.md` và `data/kb_reports/do_phu_da_nguon.json` được tạo khi chưa có mục lục; phần “chưa có nguồn” là kết quả lịch sử. Không chạy lại báo cáo vì T59 cấm sửa dữ liệu.

## 6. Việc còn mở

- Quyết định phạm vi LactMed cho yếu tố 6 sau demo; chưa có pipeline trích đoạn hoặc luật cho con bú.
- Khi có brief xử lý dữ liệu, bổ sung parser NXML và liên kết trích dẫn có phiên bản, cập nhật tài liệu cùng dữ liệu.
- Rà điều khoản tệp trình bày/phụ trợ trước tái phân phối; lệnh tải gốc vẫn chưa xác định.
- Chạy lại báo cáo độ phủ trong task được phép ghi `data/kb_reports`. Khớp tên sau chuẩn hóa không thay cho nối hoạt chất đã duyệt.

## Cách kiểm lại

Chạy từ gốc dự án bằng PowerShell. Đây là **nguyên lệnh đã chạy**, đo cả hai gói: số dòng, byte, trường, đường dẫn, XML và mã băm; chỉ đọc, không tải hoặc dựng lại dữ liệu.

```powershell
$env:PYTHONIOENCODING='utf-8'
@'
import collections, csv, hashlib, json, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
for name in ('livertox', 'lactmed'):
    folder = Path('data/kb_sources') / name
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    files = [p for p in (folder / 'giai_nen').rglob('*') if p.is_file()]
    print(name, 'manifest', manifest)
    print('root_files_bytes', {p.name: p.stat().st_size for p in folder.iterdir() if p.is_file()})
    print('extracted_count_bytes', len(files), sum(p.stat().st_size for p in files))
    print('extensions', dict(collections.Counter(p.suffix for p in files)))
    print('extension_bytes', {ext: sum(p.stat().st_size for p in files if p.suffix == ext) for ext in sorted({p.suffix for p in files})})
    print('all_bytes', sum(p.stat().st_size for p in files) + sum(p.stat().st_size for p in folder.iterdir() if p.is_file()))
    print('other_files', {p.name: p.stat().st_size for p in files if p.suffix not in ('.nxml', '.pdf', '.jpg')})
    with (folder / 'muc_luc.csv').open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        print('csv_columns_rows', reader.fieldnames, len(rows))
    print('csv_empty', {key: sum(not row[key] for row in rows) for key in reader.fieldnames})
    print('catalog_paths_example', {key: rows[0][key] for key in ('duong_dan_nxml', 'duong_dan_pdf')})
    print('catalog_missing_paths', {key: sum(not (folder / row[key]).is_file() for row in rows) for key in ('duong_dan_nxml', 'duong_dan_pdf')})
    archive = folder / manifest['cac_tep'][0]['tep']
    print('archive_sha256_matches', hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() == manifest['cac_tep'][0]['sha256'])
    tags = set()
    attributes = collections.defaultdict(set)
    copyright_documents = 0
    for path in files:
        if path.suffix == '.nxml':
            tree = ET.parse(path)
            copyright_documents += int(any('copyright' in element.tag for element in tree.iter()))
            for element in tree.iter():
                tags.add(element.tag.rsplit('}', 1)[-1])
                attributes[element.tag.rsplit('}', 1)[-1]].update(element.attrib)
    print('nxml_tags', sorted(tags))
    print('nxml_attributes', {key: sorted(value) for key, value in attributes.items() if value})
    print('nxml_copyright_documents', copyright_documents)
    print('license', next(p for p in files if p.name == 'license.txt').read_text(encoding='utf-8'))
    if name == 'livertox':
        with zipfile.ZipFile(next(p for p in files if p.suffix == '.xlsx')) as archive:
            ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            strings = [''.join(item.itertext()) for item in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', ns)]
            sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
            sheet_rows = sheet.findall('s:sheetData/s:row', ns)
            headers = [(cell.attrib['r'], strings[int(cell.find('s:v', ns).text)]) for cell in sheet_rows[1] if cell.attrib.get('t') == 's']
            print('xlsx_dimension_rows_data_headers', sheet.find('s:dimension', ns).attrib, len(sheet_rows), len(sheet_rows[2:]), headers)
'@ | .venv/Scripts/python.exe -
```

