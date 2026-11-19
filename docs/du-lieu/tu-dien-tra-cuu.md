# Từ điển thuốc và bộ tra `tra_cuu.sqlite`

Cập nhật: 19/11/2026. Người ghi: Codex, đo trên tệp cục bộ; không tải nguồn, không dựng lại hoặc ghi cơ sở dữ liệu.

| Mục | Giá trị |
|:--|:--|
| Nguồn | [DAV](dav.md), [RxNav/RxClass](rxnav.md), kho cũ `data/kb/hoat_chat.json`, danh mục trong ca giả lập; [DDInter](ddinter.md) bổ sung liên kết khi dựng chỉ mục |
| Giấy phép | Dữ liệu dẫn xuất có nhiều nguồn, **không có một giấy phép chung được ghi trong JSONL/SQLite**. DAV chỉ có ghi chú xuất xứ; giấy phép RxNav chưa có bằng chứng cục bộ; DDInter ghi CC BY-NC-SA 4.0 trong hồ sơ nguồn. Không suy ra bộ tra là dữ liệu mở không điều kiện. |
| Tầng tin cậy | Đây là lớp định danh/phân giải tên, không phải bằng chứng lâm sàng đã duyệt. Không gán một số tầng tin cậy chung cho mọi bản ghi. DDInter vẫn là nguồn sàng lọc theo tài liệu riêng. |
| Cách lấy | Dựng ngoại tuyến từ dữ liệu đã lưu, giữ khóa cũ và neo nguồn; tạo JSONL từ điển, rồi dựng SQLite cho tra cứu trong bộ nhớ |
| Ngày lấy/dựng | Ngày nguồn theo tài liệu DAV/RxNav; cả các JSONL đang có ghi `ngay_dung=2026-11-18`, `phien_ban=T52-v1`. SQLite ghi `T53-v1`, `2026-11-18`; mã lấy ngày lớn nhất trong nguồn, **không phải giờ chạy build thực tế**. |
| Lệnh | `uv run python -m app.kb.dictionary build`; `uv run python -m app.kb.dictionary report`; `uv run python -m app.kb.resolver build-index`; `uv run python -m app.kb.resolver report`. T59 chỉ kiểm đọc, không chạy lại các lệnh có ghi dữ liệu. |

## 1. Đơn vị dữ liệu và ranh giới hai kho

- `hoat_chat.jsonl`: một dòng là một khóa hoạt chất trên trục; khóa phối hợp cũ có thể được giữ để tương thích.
- `dong_nghia.jsonl`: một dòng là khóa tên chuẩn hóa → hoạt chất, kèm loại tên/nguồn/cách khớp.
- `thuoc.jsonl`: một dòng là một chế phẩm DAV theo số đăng ký.
- `thuoc_thanh_phan.jsonl`: một dòng là một quan sát quan hệ chế phẩm–hoạt chất đã khớp; có thể có nhiều quan sát cho cùng cặp.
- `anh_xa.jsonl`: một dòng là một tên/bản ghi nguồn đã nối được vào trục; không đồng nghĩa một hoạt chất mới.
- `cho_duyet.jsonl`: một dòng là một tên, chế phẩm hoặc đồng nghĩa còn cần duyệt, không phải ánh xạ đã chấp nhận.

`data/kb/hoat_chat.json` là **kho cũ**, có 54 mục `hoat_chat` và 50 khóa `nhan`, dùng làm nguồn neo/khóa tương thích trong `dictionary.axis.Inputs`. Nó không phải trục mới có 1.255 mục ở `data/kb_curated/tu_dien/hoat_chat.jsonl`. Đường chuẩn bị ca cũ vẫn dùng danh mục cũ; bộ phân giải T53 dùng SQLite được dựng từ trục mới. Không thay hai đường dẫn này cho nhau chỉ vì cùng có tên “hoạt chất”.

Runtime `DrugResolver.from_index` mở SQLite chỉ đọc, nạp các giá trị cần thiết vào bộ nhớ rồi đóng kết nối. Đường thẩm định không tải DAV/RxNav và không chạy xếp hạng ngữ nghĩa.

## 2. Ba tầng tệp

Kích thước đo bằng byte ngày cập nhật.

| Tầng | Đường dẫn | Kích thước | Vai trò |
|:--|:--|--:|:--|
| Thô | `data/kb_sources/dav/`, `data/kb_sources/rxnav/` | Xem số đo từng tệp tại [DAV](dav.md) và [RxNav](rxnav.md) | Dữ liệu nguồn ngoại tuyến dùng chung |
| Đầu vào cũ | `data/kb/hoat_chat.json` | 16.387 | Danh mục cũ và ánh xạ khóa nhãn |
| Trung gian nguồn | `data/kb_staging/tu_dien/dav_thuoc.jsonl` | 26.678.340 | Bản ghi DAV theo SĐK; cấu trúc tại [DAV](dav.md) |
| Chuẩn hóa | `data/kb_curated/tu_dien/hoat_chat.jsonl` | 1.231.178; 1.255 dòng | Trục hoạt chất |
| Chuẩn hóa | `data/kb_curated/tu_dien/dong_nghia.jsonl` | 2.550.279; 4.624 dòng | Tên tra |
| Chuẩn hóa | `data/kb_curated/tu_dien/thuoc.jsonl` | 28.730.413; 54.910 dòng | Chế phẩm DAV |
| Chuẩn hóa | `data/kb_curated/tu_dien/thuoc_thanh_phan.jsonl` | 20.015.686; 46.367 dòng | Thành phần đã khớp |
| Chuẩn hóa | `data/kb_curated/tu_dien/anh_xa.jsonl` | 25.026.593; 52.388 dòng | Ánh xạ có neo nguồn |
| Chuẩn hóa | `data/kb_curated/tu_dien/cho_duyet.jsonl` | 20.782.907; 27.554 dòng | Hàng chờ |
| Tổng JSONL chuẩn hóa | `data/kb_curated/tu_dien/*.jsonl` | 98.337.056 | Dựng lại được từ nguồn/quy tắc/quyết định duyệt |
| Bộ tra runtime | `data/kb_curated/tra_cuu/tra_cuu.sqlite` | 11.005.952 | Chỉ mục tra tên, chuyển mã ca và nối DDInter |

Mặc dù đường dẫn JSONL chứa `curated`, chúng là lớp đầu vào cho bộ tra runtime, không phải tất cả đều được runtime đọc. Không có manifest cạnh sáu JSONL; thông tin phiên bản lặp trên từng dòng, còn nguồn chỉ mục nằm trong bảng `meta` của SQLite.

## 3. Trường của từng tệp

✅ build là dựng/kiểm/báo cáo/xuất bản, ✅ runtime là giá trị được bộ phân giải thực sự đọc. Việc mã publish chép trường vào PostgreSQL chỉ là sử dụng khi xuất bản, không chứng minh runtime đang đọc trường đó. Bảng dưới chỉ liệt kê các khóa có thật trên đĩa; các trường tùy chọn không xuất hiện trong snapshot không được coi là đã có.

### 3.1. Trường chung trên cả sáu JSONL

Các trường này có trong `hoat_chat`, `dong_nghia`, `thuoc`, `thuoc_thanh_phan`, `anh_xa`, `cho_duyet`.

| Trường | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `nguon_ban_ghi_ids[]` | Neo tới DAV, cache/danh mục RxNav, kho cũ hoặc mục danh mục ca | ✅ build: kiểm mọi dòng có neo; `dictionary/publish.py` giữ nguồn; ❌ resolver runtime |
| `phien_ban` | Phiên bản từ điển | ✅ build: publish kiểm cùng phiên bản; ❌ runtime |
| `ngay_dung` | Ngày ghi trên dòng | ✅ build: `resolver.build.SourceFiles` chọn ngày meta; ❌ runtime |

### 3.2. `hoat_chat.jsonl`

| Trường | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `hoat_chat_id` | Khóa ổn định trên trục | ✅ build và runtime: khóa nối thành phần, tên, DDInter |
| `ten_inn` | Tên INN/chuẩn của trục | ✅ build: nối tên; ✅ runtime: kết quả phân giải |
| `ten_viet` | Tên hiển thị Việt từ kho/bằng chứng hiện có | ✅ runtime: kết quả thành phần |
| `rxcui` | RxCUI đã xác nhận, có thể null | ✅ build: vào SQLite và báo cáo độ phủ; ❌ `DrugResolver` không đọc cột này |
| `ma_atc[]` | Danh sách mã nhóm ATC đã có | ✅ build: gợi ý nối; ✅ runtime: kết quả và kiểm trùng nhóm |
| `ten_lop_atc[]` | Tên các lớp ATC | ✅ build/xuất bản; ❌ không đưa vào SQLite/runtime |
| `loai` | Phân loại hoạt chất như thuốc, dịch truyền/điện giải, dược liệu | ✅ runtime: xác định phạm vi tra tương tác |

Cộng thêm toàn bộ trường chung ở 3.1.

### 3.3. `dong_nghia.jsonl`

| Trường | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `khoa_chuan_hoa` | Khóa tên đã chuẩn hóa | ✅ build và runtime: tra tên |
| `hoat_chat_id` | Hoạt chất đích | ✅ build và runtime |
| `loai` | Loại tên: INN, Việt, muối, biệt dược… | ✅ build/runtime: `IngredientNames` phân biệt tên được dùng nối DDInter |
| `nguon` | Nguồn sinh tên | ✅ build/xuất bản; ❌ SQLite bỏ trường này |
| `cach_khop` | Cách xác nhận tên | ✅ build: đưa vào SQLite/xuất bản; ❌ resolver runtime không đọc cột cách khớp |

Cộng thêm 3.1. SQLite bỏ trùng theo khóa chính không gồm `nguon`, vì vậy số dòng nhỏ hơn JSONL.

### 3.4. `thuoc.jsonl`

| Trường | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `thuoc_id` | Khóa `dav:<so_dang_ky>` | ✅ build/runtime: nối công thức |
| `dav_id` | ID bản ghi DAV được chọn | ✅ build/xuất bản và truy nguyên; ❌ runtime |
| `ten_thuoc` | Tên chế phẩm gốc | ✅ build: tạo `khoa_ten_thuoc`; ✅ runtime dùng khóa dẫn xuất, không đọc cột tên gốc |
| `so_dang_ky` | SĐK | ✅ build: lưu SQLite/xuất bản; ❌ resolver runtime không đọc cột này |
| `ham_luong` | Chuỗi hàm lượng gốc, khác số lượng đã tách ở thành phần | ✅ build/xuất bản; ❌ SQLite/runtime không giữ chuỗi này |
| `dang_bao_che` | Dạng bào chế gốc | ✅ build: vào SQLite/xuất bản; ❌ resolver runtime không đọc cột này |
| `duong_dung_goc` | Đường dùng nguồn, hiện thiếu | ✅ build/xuất bản; ❌ runtime |
| `con_hieu_luc` | Cờ hiệu lực từ nguồn | ✅ build/xuất bản; ❌ runtime không dùng để lọc chế phẩm |
| `url_hdsd` | URL HDSD nguồn | ✅ build/xuất bản; ❌ runtime không lấy nội dung URL |
| `trang_thai_tach` | Trạng thái bộ tách chuỗi thành phần | ✅ build/xuất bản; ❌ runtime |
| `ly_do_tach` | Lý do chưa tách được hoặc null | ✅ build/xuất bản; ❌ runtime |
| `loai_san_pham` | Nhóm sản phẩm, có phân loại dược liệu | ✅ build/xuất bản; ❌ resolver dùng loại trên trục hoạt chất, không đọc cột này |
| `trang_thai_tra` | Đủ thành phần, chưa khớp hoặc không có dữ liệu tra | ✅ build/xuất bản; ❌ runtime không đọc cột trạng thái, dựa trên công thức được dựng |
| `khoa_chuan_hoa` | Khóa tên ở bước dictionary | ✅ build/xuất bản; resolver build **tính lại** bằng `product_key(ten_thuoc)`, không dùng trực tiếp khóa này |

Cộng thêm 3.1.

### 3.5. `thuoc_thanh_phan.jsonl`

| Trường | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `thuoc_id` | Chế phẩm cha | ✅ build/runtime |
| `hoat_chat_id` | Hoạt chất thành phần | ✅ build/runtime |
| `ham_luong` | Số hàm lượng tách được, có thể null | ✅ runtime: chỉ giữ khi nhất quán giữa các chế phẩm cùng khóa tên |
| `don_vi` | Đơn vị đi cùng số, có thể null | ✅ runtime cùng hàm lượng |
| `dang_muoi` | Phần mô tả dạng muối giữ lại | ✅ build/xuất bản; ❌ SQLite không mang trường này |
| `cach_khop` | Phương thức chấp nhận thành phần | ✅ build/xuất bản/kiểm hồi quy; ❌ runtime |
| `pin_ve_in` | Khóa tùy chọn, hiện `bo_muoi` khi dùng quy tắc PIN→IN | ✅ build/xuất bản và truy nguyên; ❌ runtime |

Cộng thêm 3.1. Không điền hàm lượng khi thiếu hoặc khi khóa phối hợp cũ chỉ có lượng chung. Khi nhiều dòng cùng cặp chế phẩm–hoạt chất bất đồng hàm lượng/đơn vị, dựng SQLite để null.

### 3.6. `anh_xa.jsonl`

| Trường | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `nguon` | Loại nguồn: DAV, kho cũ hoặc mock | ✅ build: báo cáo/phân nhóm/xuất bản |
| `ma_ban_ghi_nguon` | Khóa bản ghi nguồn, gồm cả khóa nhãn cũ | ✅ build: nối báo cáo và truy nguyên |
| `ten_goc` | Tên đã đem đối chiếu | ✅ build: mẫu kiểm/xuất bản |
| `khoa_chuan_hoa` | Khóa tên; có thể vắng ở ánh xạ khóa nhãn cũ | ✅ build: tổng hợp phương thức khớp |
| `hoat_chat_id` | Hoạt chất đích | ✅ build: đối chiếu độ phủ, neo/xuất bản |
| `cach_khop` | Phương thức chấp nhận | ✅ build: thống kê và kiểm được phép publish |
| `do_tin_cay` | Nhãn quy trình: chính xác/đã duyệt/ngữ nghĩa theo cách khớp | ✅ build/xuất bản; không phải xác suất hay mức bằng chứng lâm sàng |
| `pin_ve_in` | Dấu tùy chọn PIN về IN bằng bỏ muối | ✅ build/xuất bản; truy nguyên |

Cộng thêm 3.1. **❌ runtime:** bộ dựng chỉ mục không đọc `anh_xa.jsonl`; giữ khóa nhãn trong tệp này không đồng nghĩa runtime resolver đọc tệp.

### 3.7. `cho_duyet.jsonl`

| Trường | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `nguon` | Nguồn tên/chế phẩm chưa khớp | ✅ build: hàng duyệt và báo cáo |
| `ma_ban_ghi_nguon` | Định danh nguồn, có thể vắng theo loại dòng | ✅ build: đếm số chế phẩm liên quan |
| `ten_goc` | Tên cần xem | ✅ build: mẫu và hàng duyệt |
| `khoa_chuan_hoa` | Khóa tên ở dòng loại tên; không bắt buộc ở mọi loại | ✅ build: gộp hàng chờ |
| `loai_ban_ghi` | Tên, thuốc hoặc đồng nghĩa | ✅ build: chỉ nhóm `ten` vào hàng duyệt ưu tiên |
| `ly_do` | Lý do thiếu/xung đột | ✅ build: hàng duyệt, báo cáo |
| `cach_khop` | Trạng thái gần đúng/chưa khớp, tùy loại dòng | ✅ build: báo cáo; không phải phương thức đã được chấp nhận |
| `goi_y[]` | Danh sách gợi ý RxNav | ✅ build: mẫu báo cáo; không tự thêm vào trục |
| `goi_y[].rxcui` | Mã gợi ý | ✅ build: lưu đề xuất để đối chiếu |
| `goi_y[].ten_rxnav` | Tên đề xuất, có thể null | ✅ build: báo cáo |
| `goi_y[].diem` | Điểm nguồn dưới dạng chuỗi | ✅ build: báo cáo, không dùng như độ tin cậy lâm sàng |
| `goi_y[].nguon_ban_ghi_ids[]` | Neo của gợi ý | ✅ build: truy nguyên |
| `thuoc_id` | Chế phẩm liên quan ở dòng loại thuốc | ✅ build: mẫu kiểm/xuất bản |
| `thanh_phan_chua_khop[]` | Khóa các thành phần còn thiếu | ✅ build: mẫu kiểm và duyệt |

Cộng thêm 3.1. **❌ runtime:** tệp chưa duyệt không được dùng làm bảng ánh xạ tên. `publish` gộp các dòng loại tên thành hàng duyệt khác cấu trúc JSONL thô; không coi số dòng JSONL là số tên cần duyệt.

### 3.8. Kho cũ `data/kb/hoat_chat.json`

| Trường | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `hoat_chat[]` | Danh mục khóa cũ | ✅ build: `dictionary.axis.Inputs`; đường chuẩn bị ca cũ có dùng riêng |
| `hoat_chat[].hoat_chat_id` | Khóa hoạt chất cũ | ✅ build: giữ khóa tương thích |
| `hoat_chat[].ten_inn` | Tên quốc tế cũ | ✅ build: tên neo và đối chiếu |
| `hoat_chat[].ten_viet` | Tên Việt cũ | ✅ build: hiển thị/tên neo |
| `hoat_chat[].dong_nghia[]` | Tên đồng nghĩa đã có | ✅ build: tên Việt/INN/muối theo quy tắc |
| `hoat_chat[].nhom` | Nhóm cũ | ✅ nhập danh mục cũ: `db/sources.py:add_catalog`, ánh xạ sang `nhom_duoc_ly` trong `db/mapping.py`; ❌ trục mới không lấy loại từ trường này, tính theo tên/ATC/ngữ cảnh dược liệu |
| `hoat_chat[].thanh_phan[]` | Khóa con của mục phối hợp; có thể null | ✅ build: tách khóa phối hợp và tránh gán lượng chung cho từng con |
| `hoat_chat[].can_duyet` | Cờ cần duyệt của kho cũ | ✅ nhập danh mục cũ qua `db/sources.py:add_catalog` và `db/mapping.py`; ❌ không thấy dùng để chấp nhận/từ chối trong pipeline dictionary/resolver |
| `nhan` | Ánh xạ khóa nhãn cũ → danh sách khóa hoạt chất | ✅ build: `Inputs.labels`, giữ liên kết nhãn phối hợp |

Bảng này chỉ mô tả vai trò kho cũ trong pipeline từ điển; xem [ca-gia-lap.md](ca-gia-lap.md) về đường chuẩn bị ca. Không có dữ liệu bệnh án được chép tại đây.

## 4. Bộ tra `tra_cuu.sqlite`

Số dòng và khai báo cột lấy từ `count(*)` và `PRAGMA table_info` cho **mọi bảng**. Các chỉ mục không phải bảng dữ liệu riêng.

| Bảng | Số dòng | Khóa chính |
|:--|--:|:--|
| `hoat_chat` | 1.255 | `hoat_chat_id` |
| `dong_nghia` | 4.543 | `khoa_chuan_hoa, hoat_chat_id, loai, cach_khop` |
| `thuoc` | 54.910 | `thuoc_id` |
| `thuoc_thanh_phan` | 46.360 | `thuoc_id, hoat_chat_id` |
| `chuyen_ma_ca` | 50 | `ma_ca` |
| `meta` | 1 | Không khai báo |

### 4.1. Bảng `hoat_chat`

| Cột (kiểu PRAGMA) | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `hoat_chat_id TEXT` | Khóa trục | ✅ runtime: mọi phép nối |
| `ten_inn TEXT NOT NULL` | Tên chuẩn | ✅ runtime: đối chiếu/kết quả |
| `ten_viet TEXT` | Tên Việt | ✅ runtime: kết quả |
| `rxcui TEXT` | Mã RxNorm | ✅ báo cáo độ phủ `coverage/storage.py`; ❌ `DrugResolver` không nạp |
| `ma_atc_json TEXT NOT NULL` | Danh sách mã ATC mã hóa JSON | ✅ runtime: nạp danh sách/kết quả, yếu tố trùng nhóm |
| `loai TEXT NOT NULL` | Nhóm hoạt chất | ✅ runtime: xác định không áp dụng tra tương tác |
| `ddinter_id TEXT` | Mã DDInter đã nối một–một | ✅ runtime: tra cặp yếu tố tương tác; cột có ràng buộc UNIQUE trong schema dựng |
| `ddinter_cach_khop TEXT` | Phương thức nối DDInter | ✅ báo cáo độ phủ; ❌ `DrugResolver` không nạp |

### 4.2. Bảng `dong_nghia`

| Cột (kiểu PRAGMA) | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `khoa_chuan_hoa TEXT NOT NULL` | Khóa tên | ✅ runtime: `IngredientNames` |
| `hoat_chat_id TEXT NOT NULL` | Hoạt chất đích | ✅ runtime |
| `loai TEXT NOT NULL` | Loại tên | ✅ runtime: phân biệt tên INN/muối/biệt dược |
| `cach_khop TEXT NOT NULL` | Phương thức khớp | ❌ resolver runtime không nạp; ✅ build để giữ khóa và truy nguyên |

### 4.3. Bảng `thuoc`

| Cột (kiểu PRAGMA) | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `khoa_ten_thuoc TEXT NOT NULL` | Khóa tên tính bằng `product_key`, bỏ phần hàm lượng/dạng theo quy tắc | ✅ runtime: tìm nhóm chế phẩm |
| `thuoc_id TEXT` | Khóa chế phẩm | ✅ runtime: nối công thức |
| `ten_thuoc TEXT NOT NULL` | Tên nguồn | ❌ resolver runtime không nạp; ✅ build giữ để đối chiếu |
| `so_dang_ky TEXT` | SĐK nguồn | ❌ resolver runtime không nạp |
| `dang_bao_che TEXT` | Dạng bào chế nguồn | ❌ resolver runtime không nạp |

### 4.4. Bảng `thuoc_thanh_phan`

| Cột (kiểu PRAGMA) | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `thuoc_id TEXT NOT NULL` | Chế phẩm | ✅ runtime: `_formulas` |
| `hoat_chat_id TEXT NOT NULL` | Hoạt chất | ✅ runtime |
| `ham_luong REAL` | Lượng đã xác định hoặc null khi thiếu/xung đột | ✅ runtime: kết quả phân giải |
| `don_vi TEXT` | Đơn vị tương ứng hoặc null | ✅ runtime |

### 4.5. Bảng `chuyen_ma_ca`

| Cột (kiểu PRAGMA) | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `ma_ca TEXT` | Mã **hoạt chất cục bộ** dạng HC-…, không phải mã bệnh án | ✅ runtime: bảng chuyển sang trục |
| `hoat_chat_id TEXT NOT NULL` | Khóa trên trục mới | ✅ runtime |
| `cach_khop TEXT NOT NULL` | Phương thức chuyển mã khi dựng | ❌ runtime không nạp; bộ phân giải kiểm thêm danh mục ca khi có |

### 4.6. Bảng `meta`

| Cột (kiểu PRAGMA) | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `phien_ban TEXT` | Phiên bản bộ tra | ❌ `DrugResolver` không nạp; ✅ build ghi |
| `ngay_dung TEXT` | Ngày nguồn lớn nhất | ❌ runtime; ✅ build ghi |
| `nguon_tep_json TEXT` | Danh sách đường dẫn đầu vào dưới dạng JSON | ❌ runtime; ✅ build ghi để truy nguyên |
| `sha256_json TEXT` | Đường dẫn → SHA-256 byte đầu vào | ❌ runtime; ✅ build ghi để kiểm tái lập |

`meta` ghi 71 đầu vào. T59 kiểm băm mọi đầu vào theo bản ghi này: 0 tệp lệch. Bộ tra hiện là SHA-256 `dfe93f6163b3f3948466314dee8355d9dfa858f0d5613a7fa0b3583c82435384`.

## 5. Kết quả kiểm đã có

- T59: mọi dòng cả sáu JSONL đều có neo nguồn; số dòng thiếu neo bằng 0 cho từng tệp. Bản SQLite `integrity_check=ok`, `foreign_key_check` không có dòng lỗi.
- Trục hiện có 1.254 mục có RxCUI, 980 có ATC và 776 có mã DDInter. Trục tổng là 1.255; không đồng nhất “có hoạt chất” với “đủ mọi nguồn”.
- Chế phẩm: 39.230 đủ thành phần, 14.901 chưa khớp, 779 không có dữ liệu tra. Đây là trạng thái trên JSONL hiện tại.
- `T52_do_phu_truoc_sau.json` ghi mốc trước 36.099 chế phẩm đủ; sau 39.230, tăng 3.131; 0 chế phẩm lùi, 0 chế phẩm đủ nhưng đổi tập hoạt chất. `T52_lui.jsonl` hiện 0 byte. Đây là kết quả kiểm đã lưu, T59 không dựng lại để chạy kiểm hồi quy.
- Dấu `pin_ve_in=bo_muoi` có ở 2.472 dòng ánh xạ và 2.395 dòng thành phần, khớp phần bổ sung T52-fix-1.
- `T53_phan_giai_ca.json` là báo cáo đã lưu: 66 ca, 167 dòng; 117 đã phân giải, 0 một phần, 3 không nhận diện, 47 không áp dụng; danh sách mã ca chưa chuyển rỗng. Không chép nội dung ca và không coi đây là lượt chạy lại T59.
- T50/T53 trong `plan/reports/` có số đếm của snapshot cũ. T56 đã ghi nhận số trục tại chỗ khác mốc T53; số đo ở đây dùng tệp hiện có và khớp chữ ký T56. README nguồn ngày 16–17/11 chưa mô tả pipeline từ điển mới.
- Các báo cáo T52-fix-1/T53 ghi kiểm thử phần liên quan đã qua; đây là kết quả lịch sử, không phải kiểm thử được chạy lại trong nhiệm vụ tài liệu.

### 5b. Kết quả nhúng thật (T62, 19/11/2026, `gemini-embedding-2`)

- `candidates --embedder that`: 2.788 tên, kho 19.305 khóa. `review`: 2.788 tên chờ duyệt, 2.788 có ứng viên.
- `calibrate --embedder that`: 1.751 tên có nhãn, 125 cấu hình (`data/kb_reports/T52_hieu_chuan.json`). Với `nguong_ky_tu=0.65`, `chenh_toi_thieu=0.03`:

| nguong_nhung | tên nhận | nhận sai |
|---:|---:|---:|
| 0.60 | 548 | 56 |
| 0.85 | 539 | 47 |
| 0.94 | 288 | 17 |
| 0.95 | 205 | 12 |
| 0.99 | 6 | 0 |

- Bộ 0 nhận sai nhiều nhất: nhúng 0.99, ký tự 0.65, chênh 0.03, chỉ nhận 6 tên (độ phủ 0,3%). Chưa đủ để bật tự nhận; mọi tên vẫn qua dược sĩ duyệt. Chưa chạy `build` tự nhận hay `publish`.

## 6. Việc còn mở

- Giấy phép tổng hợp chưa được chốt; cần giữ nguồn riêng và bổ sung điều kiện sử dụng DAV/RxNav.
- Vẫn còn tên/chế phẩm trong hàng duyệt, thiếu ATC hoặc DDInter. Không dùng ATC làm liên kết DDInter đã xác nhận; ATC chỉ gợi ý khi chưa nối tên một–một.
- Khi sửa JSONL từ điển phải dựng lại chỉ mục và nạp lại resolver trong tiến trình; dữ liệu trong bộ nhớ không tự cập nhật.
- Không nhận diện đủ mọi dòng ca trong báo cáo đã có; giữ trạng thái thiếu thay vì tự thêm danh tính.
- Hiệu chuẩn nhúng giả hiện chỉ kiểm luồng. Tự nhận ngữ nghĩa chưa có chứng cứ hiệu chuẩn thật đủ để bật; không tự xuất bản hay gọi dịch vụ trong T59.
- Số dòng JSONL và SQLite khác nhau do bỏ trùng/gộp theo khóa; so đếm cần đúng đơn vị, không coi mọi chênh lệch là thất thoát.
- Kho cũ và trục mới cùng tồn tại, cần tiếp tục giữ rõ đường nào dùng kho nào trong các task sau.

## Cách kiểm lại

Các lệnh sau đã chạy từ gốc dự án, exit 0; chỉ đọc tệp, SQLite mở `mode=ro`, không gọi mạng. Lệnh băm chỉ đọc byte các tệp ca, không in/chép nội dung ca.

### Đếm, kích thước, khóa từng JSONL và toàn bộ bảng SQLite

```powershell
@'
import sys, json, sqlite3, hashlib
from pathlib import Path
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')
folder = Path('data/kb_curated/tu_dien')
tables = {}
for p in sorted(folder.glob('*.jsonl')):
    rows = [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s.strip()]
    tables[p.stem] = rows
    print(p.name, 'rows', len(rows), 'bytes', p.stat().st_size, 'keys', sorted({k for r in rows for k in r}))
    print('versions', dict(Counter(r['phien_ban'] for r in rows)), 'dates', dict(Counter(r['ngay_dung'] for r in rows)))
print('dictionary_total_bytes', sum(p.stat().st_size for p in folder.glob('*.jsonl')))
print('product_status', dict(Counter(r['trang_thai_tra'] for r in tables['thuoc'])))
print('missing_source_refs', {k: sum(not r.get('nguon_ban_ghi_ids') for r in rows) for k, rows in tables.items()})
print('pin_bo_muoi', {k: sum(r.get('pin_ve_in') == 'bo_muoi' for r in tables[k]) for k in ['anh_xa', 'thuoc_thanh_phan']})
for name in ['data/kb/hoat_chat.json', 'data/kb_staging/tu_dien/dav_thuoc.jsonl']:
    p = Path(name)
    print('input_bytes', name, p.stat().st_size)
print('legacy_ingredient_rows', len(json.loads(Path('data/kb/hoat_chat.json').read_text(encoding='utf-8'))['hoat_chat']))
p = Path('data/kb_curated/tra_cuu/tra_cuu.sqlite')
print('sqlite_bytes', p.stat().st_size, 'sha256', hashlib.sha256(p.read_bytes()).hexdigest())
with sqlite3.connect(p.resolve().as_uri() + '?mode=ro', uri=True) as db:
    for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        print('table', name, 'rows', db.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0])
        print('columns', db.execute(f'PRAGMA table_info("{name}")').fetchall())
    print('integrity_check', db.execute('PRAGMA integrity_check').fetchall())
    print('foreign_key_check', db.execute('PRAGMA foreign_key_check').fetchall())
    print('coverage', db.execute("SELECT count(rxcui),sum(ma_atc_json!='[]'),count(ddinter_id) FROM hoat_chat").fetchone())
    print('meta', db.execute('SELECT phien_ban,ngay_dung FROM meta').fetchall())
    refs, hashes = db.execute('SELECT nguon_tep_json,sha256_json FROM meta').fetchone()
    paths, expected = json.loads(refs), json.loads(hashes)
    print('source_file_count', len(paths), 'source_hash_mismatches', sum(hashlib.sha256(Path(k).read_bytes()).hexdigest() != v for k, v in expected.items()))
'@ | .venv/Scripts/python.exe -
```

### Kho cũ và các kết quả kiểm đã lưu

```powershell
@'
import sys,json
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
x=json.loads(Path('data/kb/hoat_chat.json').read_text(encoding='utf-8'))
print('legacy_root_keys',list(x),'hoat_chat_rows',len(x['hoat_chat']),'nhan_keys',len(x['nhan']))
print('legacy_item_fields',{k:sorted({type(r.get(k)).__name__ for r in x['hoat_chat'] if k in r}) for k in sorted({k for r in x['hoat_chat'] for k in r})})
print('legacy_label_value_types',sorted({type(v).__name__ for v in x['nhan'].values()}))
for name in ['data/kb_reports/T52_do_phu_truoc_sau.json','data/kb_reports/T53_phan_giai_ca.json']:
 x=json.loads(Path(name).read_text(encoding='utf-8'))
 allowed=['tong_che_pham','truoc','sau','so_che_pham_du_thanh_phan_moi','so_che_pham_chuyen_ve_chua_du','so_che_pham_du_nhung_doi_tap_hoat_chat','so_ten_con_trong_hang_duyet','hoat_chat_ca_gia_lap_chua_khop','so_ca','tong_so_dong','theo_trang_thai','ma_ca_chua_chuyen']
 print(name,json.dumps({k:x[k] for k in allowed if k in x},ensure_ascii=False))
print('regression_report_bytes',Path('data/kb_reports/T52_lui.jsonl').stat().st_size)
'@ | .venv/Scripts/python.exe -
```

### Tìm nơi dùng

```powershell
rg -n 'dav|rxnav|tra_cuu.sqlite|hoat_chat.jsonl|dong_nghia.jsonl|thuoc_thanh_phan.jsonl|anh_xa.jsonl|cho_duyet.jsonl' app
```

