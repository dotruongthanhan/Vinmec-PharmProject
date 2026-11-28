# Ca giả lập – ca demo, hồ sơ nhiều đợt và đáp án

Cập nhật: 19/11/2026. Người ghi: Codex, đọc trực tiếp khóa JSON và mã ứng dụng; không chép nội dung ca.

| Mục | Giá trị |
|:--|:--|
| Nguồn | Bộ ca nội bộ tại `data/mock/`, đáp án tại `data/gold/`; kịch bản `data/mock/hoso_gia_lap/_kich_ban.json` |
| Giấy phép | Chưa thấy tuyên bố giấy phép riêng trong bộ tệp; không suy ra giấy phép của dữ liệu từ giấy phép thư viện |
| Tầng tin cậy | Dữ liệu kiểm thử giả lập, **không phải nguồn tri thức y khoa** và không gán tầng chứng cứ của nguồn thuốc |
| Cách lấy | Soạn/sinh nội bộ; hồ sơ có `la_gia_lap`, `phien_ban_sinh`; công cụ kiểm có sẵn trong `tools/`. `tools/sinh_hanh_chinh.py` bổ sung cấu trúc hành chính, không phải công cụ sinh bệnh án gốc |
| Ngày lấy | Không có manifest hoặc ngày tạo có thẩm quyền cho từng ca. Bản sinh hồ sơ hiện ghi phiên bản `0.1-haiku`; các bản lưu trước T42/T45 thể hiện lịch sử biến đổi, không phải ngày tải |
| Lệnh | Kiểm đọc tại chỗ bằng `uv run python tools/kiem_ho_so_gia_lap.py`, `.../kiem_y_lenh_gia_lap.py`, `.../kiem_phieu_dieu_tri.py`, `.../kiem_hanh_chinh.py`. Bổ sung hành chính: `uv run python tools/sinh_hanh_chinh.py --dry-run` / bỏ `--dry-run` để ghi; **T59 không chạy lệnh sinh/ghi**. Không có lệnh tải mạng |

## 1. Đơn vị dữ liệu

Đây là JSON nhiều dòng: **một tệp là một ca/hồ sơ hoặc một đáp án**, không phải một dòng vật lý là một bản ghi.

- `data/mock/demo/*.json`: mỗi tệp là một `CaBenh`, một đợt điều trị và một y lệnh chờ duyệt; có phần hành chính ngoài mô hình AI.
- `data/mock/hoso_gia_lap/HS-*.json`: mỗi tệp là một hồ sơ có nhiều `dot_dieu_tri[]`, nhiều `y_lenh[]`; `y_lenh_trong_tam` chọn y lệnh cần thẩm định. Không truyền trực tiếp cả tệp vào `CaBenh`.
- `_kich_ban.json`: một đối tượng cấu hình, bên trong `kich_ban[]` là từng kịch bản sinh/kiểm; không phải ca bổ sung. `app/db/sources.py:read_cases` bỏ tệp bắt đầu bằng `_`.
- `data/gold/{demo,hoso_gia_lap}/*.json`: mỗi tệp là một `DapAn`; mỗi phần tử `phat_hien_ky_vong[]` là một nhận định kỳ vọng, không phải kết quả AI đã chạy.

Tất cả là dữ liệu giả lập. Tài liệu chỉ liệt kê cấu trúc, số lượng và nơi sử dụng; không minh họa bằng tên, địa chỉ, số điện thoại hay nội dung bệnh án.

## 2. Ba tầng tệp

Kích thước là tổng byte tệp, không phải dung lượng cấp phát của ổ đĩa. Bộ này không có chuỗi `kb_sources → kb_staging → kb_curated` như nguồn thuốc.

| Tầng / vai trò | Đường dẫn | Số tệp / đơn vị | Kích thước (byte) | Giữ lâu dài? |
|:--|:--|--:|--:|:--|
| Nguồn ca demo hiện hành | `data/mock/demo/*.json` | 6 ca | 30.626 | Có |
| Nguồn hồ sơ hiện hành | `data/mock/hoso_gia_lap/HS-*.json` | 60 hồ sơ | 1.426.632 | Có |
| Cấu hình sinh/kiểm | `data/mock/hoso_gia_lap/_kich_ban.json` | 1 tệp | 33.091 | Có |
| Đáp án demo | `data/gold/demo/*.json` | 6 đáp án | 1.914 | Có |
| Đáp án hồ sơ | `data/gold/hoso_gia_lap/*.json` | 60 đáp án | 22.104 | Có |
| Bản gốc trước T42 | `data/mock/_goc_hoso_truoc_T42/*.json` | 60 hồ sơ | 809.310 | Giữ để đối chiếu; không nằm trong lượt đọc ca của app |
| Bản gốc trước T45 | `data/mock/_goc_truoc_T45/*.json` | 66 ca/hồ sơ | 1.369.424 | Giữ để công cụ kiểm hành chính đối chiếu |
| Trung gian | `Batch` từ `app.db.sources.prepare_cases` và khung nhìn `CaBenh` từ `app.db.reader.load_source_cases` | Dựng trong bộ nhớ | Không có tệp trung gian để đo | Dựng lại được |
| Bộ đọc của app | JSON demo qua `app/storage/case_repo.py`; hồ sơ qua `app/db/reader.py`, các bảng `nghiep_vu.*` sau nạp DB | Không có SQLite riêng của ca | Không đo kích thước DB từ xa trong T59 | Nguồn JSON giữ trong git |

Hồ sơ hiện có 87 đợt, 222 y lệnh và 333 phiếu điều trị. Demo có 6 đợt; y lệnh nằm ở `y_lenh_cho_duyet`, nên không cộng vào số `dot_dieu_tri[].y_lenh[]` của hồ sơ. Đáp án demo có 5 phát hiện, đáp án hồ sơ có 50 phát hiện. Đếm `*.json` trong thư mục hồ sơ sẽ ra 61 vì gồm `_kich_ban.json`; số hồ sơ vẫn là 60.

## 3. Từng trường của từng tệp

Ký hiệu `[]` chỉ phần tử danh sách. Các bảng dưới đây là **hợp khóa thực đọc trên tất cả tệp hiện hành**, bao gồm trường `null` và danh sách rỗng. ✅ ghi rõ đường đọc/nạp; không đồng nghĩa trường đó đã có luật lâm sàng hoặc được gửi vào LLM. ❌ là không đi qua đường đọc ca của `app/`, dù công cụ sinh/kiểm ngoài `app/` có thể dùng.

`app/domain/loader.py:load_case` bỏ `hanh_chinh` và `dot_dieu_tri.quan_ly` trước khi xác thực demo. `app/db/sources.py` vẫn nạp chúng cho giao diện; `app/db/reader.py:load_source_cases` chỉ dùng chiều cao hành chính để bổ sung sinh hiệu khi chưa có, không lấy cân nặng hành chính làm mặc định lâm sàng. Hồ sơ chọn đúng đợt chứa y lệnh trọng tâm; thuốc đang dùng lấy từ dòng `active` của y lệnh khác **trong cùng đợt**.

### 3.1. Ca demo

| Trường | Kiểu thực có | Ý nghĩa | App dùng? / nơi dùng |
|:--|:--|:--|:--|
| `ca_id` | str | Mã ca liên kết đáp án và y lệnh trọng tâm | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `chan_doan` | list | Danh sách chẩn đoán | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `chan_doan[].chan_doan_id` | str | Mã chẩn đoán | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `chan_doan[].loai` | str | Chẩn đoán chính hoặc kèm | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `chan_doan[].ma_icd10` | str | Mã ICD-10 khi có | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `chan_doan[].noi_dung` | str | Nội dung văn bản của bản ghi | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `co_dia` | list | Danh sách cơ địa đặc biệt | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_hoat_chat` | list | Danh mục hoạt chất của ca | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_hoat_chat[].hoat_chat_id` | str | Mã hoạt chất để nối danh mục | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_hoat_chat[].ma_atc` | str | Mã ATC được khai báo | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_hoat_chat[].nhom_duoc_ly` | str | Nhóm dược lý được khai báo | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_hoat_chat[].ten_hoat_chat` | str | Tên hoạt chất trong ca | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_hoat_chat[].ten_quoc_te` | str | Tên quốc tế nếu có | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_thuoc` | list | Danh mục chế phẩm của ca | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_thuoc[].duong_dung` | str | Đường dùng | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_thuoc[].ham_luong` | str | Hàm lượng chế phẩm nguyên văn | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_thuoc[].la_khang_sinh` | bool | Cờ kháng sinh trong danh mục giả lập | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_thuoc[].la_thuoc_nguy_co_cao` | bool | Cờ thuốc nguy cơ cao trong danh mục giả lập | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_thuoc[].ten_thuoc` | str | Tên chế phẩm | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_thuoc[].thanh_phan` | list | Danh sách thành phần của chế phẩm | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_thuoc[].thanh_phan[].don_vi` | str | Đơn vị đi kèm giá trị | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_thuoc[].thanh_phan[].ham_luong_thanh_phan` | float | Hàm lượng thành phần khi nguồn có | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_thuoc[].thanh_phan[].hoat_chat_id` | str | Mã hoạt chất để nối danh mục | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `danh_muc_thuoc[].thuoc_id` | str | Mã chế phẩm nối danh mục thuốc | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `di_ung` | list | Danh sách dị ứng cụ thể | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `di_ung[].di_ung_id` | str | Mã bản ghi dị ứng | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `di_ung[].hoat_chat_id` | str | Mã hoạt chất để nối danh mục | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `di_ung[].loai_tac_nhan` | str | Loại tác nhân: thuốc, thức ăn hoặc khác | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `di_ung[].muc_do` | str | Mức độ được ghi trong nguồn | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `di_ung[].nhom_duoc_ly` | str | Nhóm dược lý được khai báo | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `di_ung[].phan_ung` | str | Phản ứng dị ứng được ghi nhận | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `di_ung[].tac_nhan` | str | Tên tác nhân dị ứng | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `dien_bien` | list | Ghi chép diễn biến lâm sàng | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `dien_bien[].dien_bien_id` | str | Mã ghi chép diễn biến | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `dien_bien[].loai_ho_so` | str | Loại ghi chép diễn biến | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `dien_bien[].noi_dung` | str | Nội dung văn bản của bản ghi | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `dien_bien[].thoi_diem_ghi` | str | Thời điểm ghi diễn biến | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `dot_dieu_tri` | dict | Đợt điều trị; đối tượng ở demo, danh sách ở hồ sơ | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `dot_dieu_tri.dot_dieu_tri_id` | str | Mã đợt điều trị | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `dot_dieu_tri.khoa_dieu_tri` | str | Khoa của đợt | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `dot_dieu_tri.loai_dieu_tri` | str | Nội trú hoặc ngoại trú | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `dot_dieu_tri.quan_ly` | dict | Thông tin quản lý đợt ngoài mô hình AI | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri.quan_ly.bac_si_dieu_tri` | str | Vai trò bác sĩ điều trị, không phải tên người | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri.quan_ly.ma_yt` | str | Mã quản lý y tế giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri.quan_ly.noi_gioi_thieu` | str | Nơi giới thiệu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri.quan_ly.ra_vien` | NoneType | Thông tin ra viện nếu đợt đã kết thúc | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri.quan_ly.so_giuong` | NoneType / str | Mã giường nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri.quan_ly.so_luu_tru` | str | Mã lưu trữ giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri.quan_ly.tuyen_chuyen_den` | NoneType | Tuyến chuyển đến nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri.quan_ly.vao_khoa_luc` | str | Thời điểm vào khoa | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri.thoi_diem_bat_dau` | str | Thời điểm bắt đầu đợt | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `hanh_chinh` | dict | Thông tin hành chính giả lập ngoài mô hình AI | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.bhyt` | NoneType / dict | Thông tin bảo hiểm giả lập nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.bhyt.gia_tri_den` | str | Hạn thẻ bảo hiểm giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.bhyt.so_the` | str | Mã thẻ bảo hiểm giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.bo_me` | NoneType | Thông tin cha mẹ giả lập nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.can_nang_kg` | float | Cân nặng hành chính theo kg | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.chieu_cao_cm` | float | Chiều cao hành chính theo cm | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI; `app/db/reader.py:with_height_vital` bổ sung sinh hiệu khi thiếu |
| `hanh_chinh.dan_toc` | str | Dân tộc khai báo | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.dia_chi` | dict | Địa chỉ giả lập có cấu trúc | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.dia_chi.huyen` | str | Phần huyện giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.dia_chi.so_nha` | str | Phần số nhà giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.dia_chi.thon_pho` | str | Phần thôn/phố giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.dia_chi.tinh_thanh` | str | Phần tỉnh/thành giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.dia_chi.xa_phuong` | str | Phần xã/phường giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.doi_tuong` | str | Đối tượng thanh toán | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.ho_ten` | str | Nhãn tên giả lập, không sao chép giá trị trong tài liệu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.ngay_sinh` | str | Ngày sinh giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.nghe_nghiep` | str | Nghề nghiệp khai báo | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.ngoai_kieu` | NoneType | Thông tin ngoại kiều nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.nguoi_bao_tin` | dict | Liên hệ giả lập có cấu trúc | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.nguoi_bao_tin.dien_thoai` | str | Số liên hệ giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.nguoi_bao_tin.ho_ten` | str | Nhãn tên giả lập, không sao chép giá trị trong tài liệu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.nguoi_bao_tin.quan_he` | str | Quan hệ với người bệnh | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.nhom_mau` | NoneType | Nhóm máu nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `mo_ta_ngan` | str | Mô tả ngắn để nhận biết ca | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `nguoi_benh` | dict | Thông tin người bệnh giả lập | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `nguoi_benh.gioi_tinh` | str | Giới tính được khai báo | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `nguoi_benh.nguoi_benh_id` | str | Mã người bệnh giả lập | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `nguoi_benh.tuoi` | int | Tuổi được khai báo trong nguồn | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `sinh_hieu` | list | Danh sách sinh hiệu/nhân trắc | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `sinh_hieu[].don_vi` | str | Đơn vị đi kèm giá trị | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `sinh_hieu[].gia_tri` | float | Số đo dạng số, không tự điền khi thiếu | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `sinh_hieu[].loai` | str | Loại số đo sinh hiệu/nhân trắc | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `sinh_hieu[].sinh_hieu_id` | str | Mã số đo sinh hiệu | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `sinh_hieu[].thoi_diem_do` | str | Thời điểm đo sinh hiệu | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `thuoc_dang_dung` | list | Dòng thuốc nền của ca demo | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `tinh_trang_di_ung` | dict | Thông tin đã khai thác dị ứng ở cấp người bệnh | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `tinh_trang_di_ung.nguon` | NoneType / str | Nguồn ghi nhận thông tin | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `tinh_trang_di_ung.thoi_diem` | NoneType / str | Thời điểm ghi nhận có múi giờ | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `tinh_trang_di_ung.trang_thai` | str | Trạng thái khai thác: có dị ứng, đã hỏi không dị ứng hoặc chưa có thông tin | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `vi_sinh` | list | Danh sách kết quả vi sinh | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `vi_sinh[].benh_pham` | str | Loại bệnh phẩm | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `vi_sinh[].khang_sinh_do` | list | Danh sách độ nhạy từng hoạt chất | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `vi_sinh[].khang_sinh_do[].hoat_chat_id` | str | Mã hoạt chất để nối danh mục | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `vi_sinh[].khang_sinh_do[].ket_qua` | str | Phân loại S/I/R của kháng sinh đồ | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `vi_sinh[].khang_sinh_do[].mic` | NoneType | Giá trị MIC khi được khai báo | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `vi_sinh[].thoi_diem_lay_mau` | str | Thời điểm lấy mẫu | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `vi_sinh[].vi_khuan` | str | Tên tác nhân vi sinh nếu có | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `vi_sinh[].vi_sinh_id` | str | Mã kết quả vi sinh | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `xet_nghiem` | list | Danh sách kết quả xét nghiệm | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `xet_nghiem[].don_vi` | str | Đơn vị đi kèm giá trị | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `xet_nghiem[].gia_tri_so` | float | Kết quả dạng số; thiếu giữ null | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `xet_nghiem[].gia_tri_text` | NoneType | Kết quả dạng chữ | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `xet_nghiem[].ma_xet_nghiem` | str | Mã loại xét nghiệm | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `xet_nghiem[].nguong_duoi` | NoneType / float / int | Giới hạn dưới do nguồn cung cấp | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `xet_nghiem[].nguong_tren` | float / int | Giới hạn trên do nguồn cung cấp | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `xet_nghiem[].ten_xet_nghiem` | str | Tên loại xét nghiệm | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `xet_nghiem[].thoi_diem_ket_qua` | str | Thời điểm kết quả xét nghiệm | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `xet_nghiem[].xet_nghiem_id` | str | Mã kết quả xét nghiệm | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet` | dict | Y lệnh trọng tâm ở cấu trúc demo | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet` | list | Danh sách dòng thuốc/sản phẩm của y lệnh | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].bat_dau` | str | Thời điểm bắt đầu dòng thuốc | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].cach_dung` | str | Hướng dẫn cách dùng nguyên văn | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].chi_tiet_y_lenh_id` | str | Mã dòng y lệnh; trong đáp án là danh sách mã dòng liên quan | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].don_vi_lieu` | str | Đơn vị liều mỗi lần | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].duong_dung` | str | Đường dùng | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].ket_thuc` | NoneType | Thời điểm kết thúc nếu có | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].khoang_cach_gio` | float | Khoảng cách dùng tính bằng giờ nếu có | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].lich_dung` | list | Danh sách lần dùng dự kiến | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].lich_dung[].don_vi` | str | Đơn vị đi kèm giá trị | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].lich_dung[].lieu` | float | Liều của lần dùng dự kiến | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].lich_dung[].thoi_diem_du_kien` | str | Thời điểm lần dùng dự kiến | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].lieu_moi_lan` | float | Liều mỗi lần do nguồn cung cấp | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].loai_san_pham` | str | Thuốc, thực phẩm chức năng, dinh dưỡng hoặc khác | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].nguon_thuoc` | str | Nguồn thuốc nếu có | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].so_lan_moi_ngay` | int | Số lần dùng mỗi ngày nếu có | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].tan_suat` | str | Tần suất nguyên văn | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].ten_tu_do` | NoneType | Tên sản phẩm tự do khi chưa có mã thuốc | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].thuoc_id` | str | Mã chế phẩm nối danh mục thuốc | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.chi_tiet[].trang_thai_dong` | str | Trạng thái active/pending/discontinued/completed | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.khoa_ke_don` | str | Khoa kê y lệnh | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.luong_duyet` | str | Luồng trực tiếp hoặc hậu kiểm | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.muc_uu_tien` | NoneType | Mức ưu tiên nếu được khai báo | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.thoi_diem_ke` | str | Thời điểm kê y lệnh | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |
| `y_lenh_cho_duyet.y_lenh_id` | str | Mã y lệnh | ✅ `app/domain/loader.py:load_case` xác thực/giữ trong `CaBenh`; `app/db/sources.py` nạp DB |

### 3.2. Hồ sơ nhiều đợt

| Trường | Kiểu thực có | Ý nghĩa | App dùng? / nơi dùng |
|:--|:--|:--|:--|
| `danh_muc_hoat_chat` | list | Danh mục hoạt chất của ca | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_hoat_chat[].hoat_chat_id` | str | Mã hoạt chất để nối danh mục | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_hoat_chat[].ma_atc` | NoneType / str | Mã ATC được khai báo | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_hoat_chat[].nhom_duoc_ly` | str | Nhóm dược lý được khai báo | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_hoat_chat[].ten_hoat_chat` | str | Tên hoạt chất trong ca | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_hoat_chat[].ten_quoc_te` | str | Tên quốc tế nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_thuoc` | list | Danh mục chế phẩm của ca | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_thuoc[].duong_dung` | str | Đường dùng | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_thuoc[].ham_luong` | str | Hàm lượng chế phẩm nguyên văn | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_thuoc[].la_khang_sinh` | bool | Cờ kháng sinh trong danh mục giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_thuoc[].la_thuoc_nguy_co_cao` | bool | Cờ thuốc nguy cơ cao trong danh mục giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_thuoc[].ten_thuoc` | str | Tên chế phẩm | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_thuoc[].thanh_phan` | list | Danh sách thành phần của chế phẩm | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_thuoc[].thanh_phan[].don_vi` | str | Đơn vị đi kèm giá trị | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_thuoc[].thanh_phan[].ham_luong_thanh_phan` | float | Hàm lượng thành phần khi nguồn có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_thuoc[].thanh_phan[].hoat_chat_id` | str | Mã hoạt chất để nối danh mục | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `danh_muc_thuoc[].thuoc_id` | str | Mã chế phẩm nối danh mục thuốc | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `di_ung` | list | Danh sách dị ứng cụ thể | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `di_ung[].di_ung_id` | str | Mã bản ghi dị ứng | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `di_ung[].hoat_chat_id` | NoneType / str | Mã hoạt chất để nối danh mục | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `di_ung[].loai_tac_nhan` | str | Loại tác nhân: thuốc, thức ăn hoặc khác | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `di_ung[].muc_do` | NoneType / str | Mức độ được ghi trong nguồn | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `di_ung[].nhom_duoc_ly` | str | Nhóm dược lý được khai báo | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `di_ung[].phan_ung` | str | Phản ứng dị ứng được ghi nhận | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `di_ung[].tac_nhan` | str | Tên tác nhân dị ứng | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri` | list | Đợt điều trị; đối tượng ở demo, danh sách ở hồ sơ | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].benh_su` | str | Bệnh sử nguyên văn | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].chan_doan` | list | Danh sách chẩn đoán | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].chan_doan[].chan_doan_id` | str | Mã chẩn đoán | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].chan_doan[].loai` | str | Chẩn đoán chính hoặc kèm | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].chan_doan[].ma_icd10` | NoneType / str | Mã ICD-10 khi có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].chan_doan[].noi_dung` | str | Nội dung văn bản của bản ghi | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].co_dia` | list | Danh sách cơ địa đặc biệt | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].co_dia[].gia_tri` | NoneType / str | Chi tiết dạng chữ của cơ địa nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].co_dia[].loai` | str | Loại cơ địa đặc biệt | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].co_dia[].nguon` | str | Nguồn ghi nhận thông tin | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].co_dia[].thoi_diem` | str | Thời điểm ghi nhận có múi giờ | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].co_dia[].trang_thai` | str | Trạng thái của đối tượng chứa trường | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].dien_bien` | list | Ghi chép diễn biến lâm sàng | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].dien_bien[].dien_bien_id` | str | Mã ghi chép diễn biến | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].dien_bien[].loai_ho_so` | str | Loại ghi chép diễn biến | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].dien_bien[].noi_dung` | str | Nội dung văn bản của bản ghi | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].dien_bien[].thoi_diem_ghi` | str | Thời điểm ghi diễn biến | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].dot_dieu_tri_id` | str | Mã đợt điều trị | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].hinh_thuc_vao` | str | Hình thức vào viện | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].kham_benh` | str | Ghi chép khám bệnh | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].khoa_dieu_tri` | str | Khoa của đợt | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].lich_su_khoa` | list | Lịch sử khoa trong đợt | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].lich_su_khoa[].den` | NoneType / str | Thời điểm kết thúc ở khoa nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].lich_su_khoa[].khoa` | str | Tên khoa ở lịch sử/kịch bản | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].lich_su_khoa[].tu` | str | Thời điểm bắt đầu ở khoa | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].loai_dieu_tri` | str | Nội trú hoặc ngoại trú | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].ly_do_vao_vien` | str | Lý do vào viện | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].phieu_dieu_tri` | list | Danh sách phiếu điều trị trong đợt | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].phieu_dieu_tri[].che_do_an` | str | Chế độ ăn | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].phieu_dieu_tri[].che_do_cham_soc` | NoneType / str | Chế độ chăm sóc nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].phieu_dieu_tri[].dan_do` | NoneType / str | Dặn dò nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].phieu_dieu_tri[].danh_gia` | str | Đánh giá trên phiếu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].phieu_dieu_tri[].dien_bien` | str | Ghi chép diễn biến lâm sàng | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].phieu_dieu_tri[].huong_xu_tri` | str | Hướng xử trí trên phiếu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].phieu_dieu_tri[].ngay_dieu_tri` | int | Thứ tự ngày điều trị của phiếu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].phieu_dieu_tri[].phieu_dieu_tri_id` | str | Mã phiếu điều trị | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].phieu_dieu_tri[].theo_doi` | list | Danh sách nội dung theo dõi | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].phieu_dieu_tri[].thoi_diem_lap` | str | Thời điểm lập phiếu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].phieu_dieu_tri[].vai_tro_nguoi_lap` | str | Vai trò người lập phiếu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].phieu_dieu_tri[].y_lenh_trong_ngay` | list | Danh sách mã y lệnh liên quan phiếu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].quan_ly` | dict | Thông tin quản lý đợt ngoài mô hình AI | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri[].quan_ly.bac_si_dieu_tri` | str | Vai trò bác sĩ điều trị, không phải tên người | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri[].quan_ly.ma_yt` | str | Mã quản lý y tế giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri[].quan_ly.noi_gioi_thieu` | str | Nơi giới thiệu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri[].quan_ly.ra_vien` | NoneType / dict | Thông tin ra viện nếu đợt đã kết thúc | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri[].quan_ly.ra_vien.chuyen_vien_den` | NoneType | Nơi chuyển viện nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri[].quan_ly.ra_vien.hinh_thuc` | str | Hình thức ra viện | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri[].quan_ly.ra_vien.ly_do` | str | Lý do ra viện | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri[].quan_ly.so_giuong` | NoneType / str | Mã giường nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri[].quan_ly.so_luu_tru` | str | Mã lưu trữ giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri[].quan_ly.tuyen_chuyen_den` | NoneType / str | Tuyến chuyển đến nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri[].quan_ly.vao_khoa_luc` | str | Thời điểm vào khoa | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `dot_dieu_tri[].sinh_hieu` | list | Danh sách sinh hiệu/nhân trắc | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].sinh_hieu[].don_vi` | str | Đơn vị đi kèm giá trị | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].sinh_hieu[].gia_tri` | float | Số đo dạng số, không tự điền khi thiếu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].sinh_hieu[].loai` | str | Loại số đo sinh hiệu/nhân trắc | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].sinh_hieu[].sinh_hieu_id` | str | Mã số đo sinh hiệu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].sinh_hieu[].thoi_diem_do` | str | Thời điểm đo sinh hiệu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].so_ngay_dieu_tri` | NoneType / int | Số ngày điều trị do nguồn khai báo | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].thoi_diem_bat_dau` | str | Thời điểm bắt đầu đợt | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].thoi_diem_ket_thuc` | NoneType / str | Thời điểm kết thúc đợt nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].thu_tu` | int | Thứ tự đợt trong hồ sơ | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].tien_su` | dict | Tiền sử có cấu trúc | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].tien_su.ban_than` | str | Tiền sử bản thân | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].tien_su.gia_dinh` | str | Tiền sử gia đình | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].tien_su.thuoc_truoc_vao_vien` | str | Tiền sử thuốc trước vào viện | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].tom_tat` | str | Tóm tắt đợt điều trị | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].tong_ket` | NoneType / str | Tổng kết đợt đã kết thúc | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].vi_sinh` | list | Danh sách kết quả vi sinh | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].vi_sinh[].benh_pham` | str | Loại bệnh phẩm | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].vi_sinh[].khang_sinh_do` | list | Danh sách độ nhạy từng hoạt chất | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].vi_sinh[].khang_sinh_do[].hoat_chat_id` | str | Mã hoạt chất để nối danh mục | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].vi_sinh[].khang_sinh_do[].ket_qua` | str | Phân loại S/I/R của kháng sinh đồ | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].vi_sinh[].khang_sinh_do[].mic` | NoneType / float | Giá trị MIC khi được khai báo | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].vi_sinh[].thoi_diem_lay_mau` | str | Thời điểm lấy mẫu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].vi_sinh[].vi_khuan` | NoneType / str | Tên tác nhân vi sinh nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].vi_sinh[].vi_sinh_id` | str | Mã kết quả vi sinh | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].xet_nghiem` | list | Danh sách kết quả xét nghiệm | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].xet_nghiem[].don_vi` | NoneType / str | Đơn vị đi kèm giá trị | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].xet_nghiem[].gia_tri_so` | float | Kết quả dạng số; thiếu giữ null | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].xet_nghiem[].gia_tri_text` | NoneType | Kết quả dạng chữ | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].xet_nghiem[].ma_xet_nghiem` | str | Mã loại xét nghiệm | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].xet_nghiem[].nguong_duoi` | NoneType / float / int | Giới hạn dưới do nguồn cung cấp | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].xet_nghiem[].nguong_tren` | NoneType / float / int | Giới hạn trên do nguồn cung cấp | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].xet_nghiem[].ten_xet_nghiem` | str | Tên loại xét nghiệm | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].xet_nghiem[].thoi_diem_ket_qua` | str | Thời điểm kết quả xét nghiệm | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].xet_nghiem[].xet_nghiem_id` | str | Mã kết quả xét nghiệm | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh` | list | Danh sách y lệnh trong đợt | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet` | list | Danh sách dòng thuốc/sản phẩm của y lệnh | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].bat_dau` | str | Thời điểm bắt đầu dòng thuốc | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].cach_dung` | str | Hướng dẫn cách dùng nguyên văn | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].chi_tiet_y_lenh_id` | str | Mã dòng y lệnh; trong đáp án là danh sách mã dòng liên quan | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].don_vi_lieu` | NoneType / str | Đơn vị liều mỗi lần | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].duong_dung` | NoneType / str | Đường dùng | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].ket_thuc` | NoneType / str | Thời điểm kết thúc nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].khoang_cach_gio` | NoneType / float | Khoảng cách dùng tính bằng giờ nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].lich_dung` | list | Danh sách lần dùng dự kiến | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].lich_dung[].don_vi` | str | Đơn vị đi kèm giá trị | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].lich_dung[].lieu` | float | Liều của lần dùng dự kiến | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].lich_dung[].thoi_diem_du_kien` | str | Thời điểm lần dùng dự kiến | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].lieu_moi_lan` | NoneType / float | Liều mỗi lần do nguồn cung cấp | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].loai_san_pham` | str | Thuốc, thực phẩm chức năng, dinh dưỡng hoặc khác | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].nguon_thuoc` | NoneType / str | Nguồn thuốc nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].so_lan_moi_ngay` | NoneType / int | Số lần dùng mỗi ngày nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].tan_suat` | NoneType / str | Tần suất nguyên văn | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].ten_tu_do` | NoneType / str | Tên sản phẩm tự do khi chưa có mã thuốc | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].thuoc_id` | NoneType / str | Mã chế phẩm nối danh mục thuốc | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].chi_tiet[].trang_thai_dong` | str | Trạng thái active/pending/discontinued/completed | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].khoa_ke_don` | str | Khoa kê y lệnh | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].loai` | str | Loại của đối tượng chứa trường | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].luong_duyet` | str | Luồng trực tiếp hoặc hậu kiểm | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].ly_do_ngung` | NoneType / str | Lý do ngừng y lệnh | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].muc_uu_tien` | NoneType | Mức ưu tiên nếu được khai báo | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].thay_the_y_lenh_id` | NoneType / str | Mã y lệnh cũ bị thay thế | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].thoi_diem_ke` | str | Thời điểm kê y lệnh | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].thoi_diem_ngung` | NoneType / str | Thời điểm ngừng y lệnh | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].trang_thai` | str | Trạng thái của đối tượng chứa trường | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].vai_tro_nguoi_ke` | str | Vai trò người kê, không phải tên cá nhân | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `dot_dieu_tri[].y_lenh[].y_lenh_id` | str | Mã y lệnh | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `hanh_chinh` | dict | Thông tin hành chính giả lập ngoài mô hình AI | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.bhyt` | NoneType / dict | Thông tin bảo hiểm giả lập nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.bhyt.gia_tri_den` | str | Hạn thẻ bảo hiểm giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.bhyt.so_the` | str | Mã thẻ bảo hiểm giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.bo_me` | NoneType / dict | Thông tin cha mẹ giả lập nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.bo_me.bo` | dict | Thông tin cha giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.bo_me.bo.ho_ten` | str | Nhãn tên giả lập, không sao chép giá trị trong tài liệu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.bo_me.bo.nghe_nghiep` | str | Nghề nghiệp khai báo | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.bo_me.me` | dict | Thông tin mẹ giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.bo_me.me.ho_ten` | str | Nhãn tên giả lập, không sao chép giá trị trong tài liệu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.bo_me.me.nghe_nghiep` | str | Nghề nghiệp khai báo | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.can_nang_kg` | NoneType / float | Cân nặng hành chính theo kg | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.chieu_cao_cm` | float | Chiều cao hành chính theo cm | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI; `app/db/reader.py:with_height_vital` bổ sung sinh hiệu khi thiếu |
| `hanh_chinh.dan_toc` | str | Dân tộc khai báo | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.dia_chi` | dict | Địa chỉ giả lập có cấu trúc | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.dia_chi.huyen` | str | Phần huyện giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.dia_chi.so_nha` | str | Phần số nhà giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.dia_chi.thon_pho` | str | Phần thôn/phố giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.dia_chi.tinh_thanh` | str | Phần tỉnh/thành giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.dia_chi.xa_phuong` | str | Phần xã/phường giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.doi_tuong` | str | Đối tượng thanh toán | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.ho_ten` | str | Nhãn tên giả lập, không sao chép giá trị trong tài liệu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.ngay_sinh` | str | Ngày sinh giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.nghe_nghiep` | NoneType / str | Nghề nghiệp khai báo | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.ngoai_kieu` | NoneType | Thông tin ngoại kiều nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.nguoi_bao_tin` | dict | Liên hệ giả lập có cấu trúc | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.nguoi_bao_tin.dien_thoai` | str | Số liên hệ giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.nguoi_bao_tin.ho_ten` | str | Nhãn tên giả lập, không sao chép giá trị trong tài liệu | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.nguoi_bao_tin.quan_he` | str | Quan hệ với người bệnh | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `hanh_chinh.nhom_mau` | NoneType | Nhóm máu nếu có | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp giao diện; bỏ khỏi mô hình AI |
| `ho_so_id` | str | Mã hồ sơ, chuyển thành ca_id khi dựng khung nhìn | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `kich_ban_id` | str | Mã kịch bản sinh/kiểm hồ sơ | ❌ không đưa vào mapping/khung nhìn AI; metadata cho công cụ kiểm |
| `la_gia_lap` | bool | Cờ đánh dấu dữ liệu giả lập | ❌ không đưa vào mapping/khung nhìn AI; metadata cho công cụ kiểm |
| `nguoi_benh` | dict | Thông tin người bệnh giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `nguoi_benh.gioi_tinh` | str | Giới tính được khai báo | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `nguoi_benh.nguoi_benh_id` | str | Mã người bệnh giả lập | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `nguoi_benh.tuoi` | int | Tuổi được khai báo trong nguồn | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `phien_ban_sinh` | str | Phiên bản bộ sinh hồ sơ | ❌ không đưa vào mapping/khung nhìn AI; metadata cho công cụ kiểm |
| `tinh_trang_di_ung` | dict | Thông tin đã khai thác dị ứng ở cấp người bệnh | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `tinh_trang_di_ung.nguon` | str | Nguồn ghi nhận thông tin | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `tinh_trang_di_ung.thoi_diem` | str | Thời điểm ghi nhận có múi giờ | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `tinh_trang_di_ung.trang_thai` | str | Trạng thái khai thác: có dị ứng, đã hỏi không dị ứng hoặc chưa có thông tin | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |
| `y_lenh_trong_tam` | str | Mã y lệnh được chọn để thẩm định | ✅ `app/db/sources.py` / `app/db/mapping.py` nạp; `app/db/reader.py` chọn đợt/dựng `CaBenh` hoặc giao diện |

### 3.3. `_kich_ban.json`

| Trường | Kiểu thực có | Ý nghĩa | App dùng? / nơi dùng |
|:--|:--|:--|:--|
| `ghi_chu` | str | Yêu cầu kịch bản: ghi chú của bộ dữ liệu | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban` | list | Yêu cầu kịch bản: danh sách kịch bản sinh/kiểm | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].benh` | str | Yêu cầu kịch bản: mô tả bệnh trong kịch bản | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].dap_an` | str | Yêu cầu kịch bản: yêu cầu đáp án trong kịch bản | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].di_ung` | str | Yêu cầu kịch bản: danh sách dị ứng cụ thể | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].dot_truoc` | str | Yêu cầu kịch bản: yêu cầu đợt trước trong kịch bản | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].gioi` | str | Yêu cầu kịch bản: giới tính trong kịch bản | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].id` | str | Yêu cầu kịch bản: mã kịch bản | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].khac` | str | Yêu cầu kịch bản: yêu cầu khác của kịch bản | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].khoa` | str | Yêu cầu kịch bản: tên khoa ở lịch sử/kịch bản | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].loai` | str | Yêu cầu kịch bản: loại của đối tượng chứa trường | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].loi` | str | Yêu cầu kịch bản: loại sai sót được thiết kế trong kịch bản | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].muc_do` | NoneType / str | Yêu cầu kịch bản: mức độ được ghi trong nguồn | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].nhom` | str | Yêu cầu kịch bản: nhóm kịch bản | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].so_dot` | int | Yêu cầu kịch bản: số đợt dự kiến trong kịch bản | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].so_lieu` | str | Yêu cầu kịch bản: yêu cầu số liệu giả lập của kịch bản | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].tuoi` | int | Yêu cầu kịch bản: tuổi được khai báo trong nguồn | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].y_lenh` | str | Yêu cầu kịch bản: danh sách y lệnh trong đợt | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `kich_ban[].yeu_to` | NoneType / int | Yêu cầu kịch bản: yếu tố thẩm định của phát hiện | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |
| `phien_ban` | str | Yêu cầu kịch bản: phiên bản tệp kịch bản | ❌ `app/db/sources.py:read_cases` bỏ tệp `_`; công cụ `tools/kiem_ho_so_gia_lap.py` dùng ngoài app |

### 3.4. Đáp án (cả hai thư mục `data/gold/`)

| Trường | Kiểu thực có | Ý nghĩa | App dùng? / nơi dùng |
|:--|:--|:--|:--|
| `ca_id` | str | Mã ca liên kết đáp án và y lệnh trọng tâm | ✅ `app/domain/loader.py:load_answer`; `app/db/sources.py:add_gold` nạp đáp án |
| `ghi_chu` | NoneType / str | Ghi chú của bộ dữ liệu | ✅ `app/domain/loader.py:load_answer`; `app/db/sources.py:add_gold` nạp đáp án |
| `phat_hien_ky_vong` | list | Danh sách nhận định kỳ vọng | ✅ `app/domain/loader.py:load_answer`; `app/db/sources.py:add_gold` nạp đáp án |
| `phat_hien_ky_vong[].chi_tiet_y_lenh_id` | list | Mã dòng y lệnh; trong đáp án là danh sách mã dòng liên quan | ✅ `app/domain/loader.py:load_answer`; `app/db/sources.py:add_gold` nạp đáp án |
| `phat_hien_ky_vong[].ket_luan` | str | Kết luận kỳ vọng theo mô hình DapAn | ✅ `app/domain/loader.py:load_answer`; `app/db/sources.py:add_gold` nạp đáp án |
| `phat_hien_ky_vong[].mo_ta` | str | Mô tả kỳ vọng | ✅ `app/domain/loader.py:load_answer`; `app/db/sources.py:add_gold` nạp đáp án |
| `phat_hien_ky_vong[].muc_do` | NoneType / str | Mức độ được ghi trong nguồn | ✅ `app/domain/loader.py:load_answer`; `app/db/sources.py:add_gold` nạp đáp án |
| `phat_hien_ky_vong[].yeu_to` | int | Yếu tố thẩm định của phát hiện | ✅ `app/domain/loader.py:load_answer`; `app/db/sources.py:add_gold` nạp đáp án |
| `van_ban_bat_thuong` | bool | Cờ ca có văn bản bất thường | ✅ `app/domain/loader.py:load_answer`; `app/db/sources.py:add_gold` nạp đáp án |

### 3.5. Hai thư mục lưu trữ

`_goc_hoso_truoc_T42` dùng cấu trúc hồ sơ nhiều đợt ở bảng 3.2, trước khi thêm `phieu_dieu_tri` và phần hành chính. `_goc_truoc_T45` chứa cả cấu trúc demo (3.1) và hồ sơ (3.2), trước khi thêm `hanh_chinh` và `quan_ly`. Ý nghĩa các khóa giữ nguyên như các bảng hiện hành. Cả hai đều ❌ với đường đọc ca của app; chỉ công cụ kiểm trong `tools/` đối chiếu. Danh sách chênh lệch khóa chính xác được lệnh A ở cuối tệp in ra, không suy luận từ tên thư mục.

## 4. Bộ tra / các bảng được chuẩn bị để nạp DB

Không có SQLite của ca để chạy `PRAGMA`. Bảng dưới là số hàng **trong bộ nhớ** của `prepare_cases(Path.cwd())`, sau kiểm và khử trùng, không phải số hàng đã nạp vào Supabase. Không kết nối DB, không gọi `Batch.finish` hoặc lệnh `load`.

| Bảng | Số hàng batch | Cột mapping (không kể `nguon_tep`) |
|:--|--:|:--|
| `nghiep_vu.can_cu` | 0 | `can_cu_id`, `nhan_dinh_id`, `loai`, `ban_ghi_id`, `mo_ta` |
| `nghiep_vu.chan_doan` | 123 | `chan_doan_id`, `ma_icd10`, `noi_dung`, `loai`, `dot_dieu_tri_id`, `thoi_diem` |
| `nghiep_vu.chi_tiet_y_lenh` | 233 | `chi_tiet_y_lenh_id`, `thuoc_id`, `ten_tu_do`, `loai_san_pham`, `lieu_moi_lan`, `don_vi_lieu`, `tan_suat`, `so_lan_moi_ngay`, `khoang_cach_gio`, `duong_dung`, `cach_dung`, `bat_dau`, `ket_thuc`, `nguon_thuoc`, `trang_thai_dong`, `y_lenh_id`, `dot_dieu_tri_id` |
| `nghiep_vu.di_ung` | 5 | `di_ung_id`, `tac_nhan`, `loai_tac_nhan`, `hoat_chat_id`, `nhom_duoc_ly`, `phan_ung`, `muc_do`, `nguoi_benh_id` |
| `nghiep_vu.dien_bien` | 227 | `dien_bien_id`, `loai_ho_so`, `noi_dung`, `thoi_diem_ghi`, `dot_dieu_tri_id`, `nguoi_ghi_vai_tro` |
| `nghiep_vu.dot_dieu_tri` | 93 | `dot_dieu_tri_id`, `khoa_dieu_tri`, `loai_dieu_tri`, `thoi_diem_bat_dau`, `nguoi_benh_id`, `co_dia`, `thu_tu`, `so_ngay_dieu_tri`, `tuoi_luc_vao`, `thoi_diem_ket_thuc`, `hinh_thuc_vao`, `ly_do_vao_vien`, `benh_su`, `kham_benh`, `tom_tat`, `tong_ket`, `lich_su_khoa`, `tien_su`, `noi_gioi_thieu`, `tuyen_chuyen_den`, `vao_khoa_luc`, `so_giuong`, `so_luu_tru`, `ma_yt`, `ra_vien`, `bac_si_dieu_tri` |
| `nghiep_vu.ket_qua_xet_nghiem` | 225 | `xet_nghiem_id`, `ma_xet_nghiem`, `ten_xet_nghiem`, `gia_tri_so`, `gia_tri_text`, `don_vi`, `nguong_duoi`, `nguong_tren`, `thoi_diem_ket_qua`, `dot_dieu_tri_id` |
| `nghiep_vu.khang_sinh_do` | 16 | `vi_sinh_id`, `hoat_chat_id`, `ket_qua`, `mic` |
| `nghiep_vu.lan_tham_dinh` | 66 | `tham_dinh_id`, `y_lenh_id`, `ca_id`, `van_ban_bat_thuong`, `ghi_chu` |
| `nghiep_vu.lich_dung` | 217 | `chi_tiet_y_lenh_id`, `thu_tu`, `thoi_diem_du_kien`, `lieu`, `don_vi` |
| `nghiep_vu.nguoi_benh` | 66 | `nguoi_benh_id`, `tuoi`, `gioi_tinh`, `tinh_trang_di_ung`, `ho_ten`, `ngay_sinh`, `dan_toc`, `ngoai_kieu`, `nghe_nghiep`, `dia_chi`, `doi_tuong`, `bhyt`, `nguoi_bao_tin`, `bo_me`, `chieu_cao_cm`, `can_nang_kg`, `nhom_mau` |
| `nghiep_vu.nhan_dinh` | 55 | `nhan_dinh_id`, `tham_dinh_id`, `yeu_to`, `ket_luan`, `muc_do`, `mo_ta` |
| `nghiep_vu.nhan_dinh_thuoc` | 55 | `nhan_dinh_id`, `chi_tiet_y_lenh_id` |
| `nghiep_vu.phan_hoi` | 0 | `thoi_diem`, `ca_id`, `ma_luat`, `yeu_to`, `chi_tiet_y_lenh_id`, `phan_hoi`, `nhom_ly_do`, `ly_do` |
| `nghiep_vu.phieu_dieu_tri` | 333 | `phieu_dieu_tri_id`, `dot_dieu_tri_id`, `dien_bien`, `danh_gia`, `huong_xu_tri`, `che_do_an`, `ngay_dieu_tri`, `thoi_diem_lap`, `vai_tro_nguoi_lap`, `che_do_cham_soc`, `theo_doi`, `dan_do` |
| `nghiep_vu.phieu_y_lenh` | 625 | `phieu_dieu_tri_id`, `y_lenh_id`, `dot_dieu_tri_id` |
| `nghiep_vu.sinh_hieu` | 440 | `sinh_hieu_id`, `loai`, `gia_tri`, `don_vi`, `thoi_diem_do`, `dot_dieu_tri_id` |
| `nghiep_vu.thuoc` | 67 | `thuoc_id`, `ten_thuoc`, `ham_luong`, `duong_dung`, `la_thuoc_nguy_co_cao`, `la_khang_sinh` |
| `nghiep_vu.thuoc_hoat_chat` | 75 | `thuoc_id`, `hoat_chat_id`, `ham_luong_thanh_phan`, `don_vi` |
| `nghiep_vu.vi_sinh` | 8 | `vi_sinh_id`, `benh_pham`, `vi_khuan`, `thoi_diem_lay_mau`, `dot_dieu_tri_id` |
| `nghiep_vu.y_lenh` | 228 | `y_lenh_id`, `khoa_ke_don`, `luong_duyet`, `muc_uu_tien`, `thoi_diem_ke`, `dot_dieu_tri_id`, `ca_id`, `mo_ta_ngan`, `vai_tro_nguoi_ke`, `loai`, `trang_thai`, `thay_the_y_lenh_id`, `ly_do_ngung`, `thoi_diem_ngung` |
| `tri_thuc.hoat_chat` | 58 | `hoat_chat_id`, `ten_hoat_chat`, `ten_quoc_te`, `ma_atc`, `nhom_duoc_ly`, `thanh_phan`, `can_duyet` |

Mỗi bảng còn được lớp nạp bổ sung `nguon_tep` để truy xuất nguồn. Batch còn đọc danh mục cũ `data/kb/hoat_chat.json` qua `app/db/sources.py:add_catalog`, không chỉ các danh mục nằm trong ca; đây không phải trục hoạt chất mới của bộ tra tên thuốc. Xem thêm [từ điển và bộ tra](tu-dien-tra-cuu.md). Ý nghĩa các cột từ JSON ca đã ghi ở mục 3; các cột từ danh mục cũ hoặc phát sinh đáng chú ý:

| Cột phát sinh | Ý nghĩa | App dùng ở đâu |
|:--|:--|:--|
| `dot_dieu_tri_id`, `nguoi_benh_id`, `y_lenh_id`, `thuoc_id`, `vi_sinh_id` khi thêm vào hàng con | Khóa liên kết từ ngữ cảnh cha | ✅ `app/db/sources.py`, `app/db/mapping.py`, `app/db/reader.py` |
| `thoi_diem` của chẩn đoán | Nếu hồ sơ mới không có, lớp nạp lấy thời điểm bắt đầu đợt | ✅ `add_encounter`; đây là hành vi code hiện có, không phải số liệu mới do T59 gán |
| `thu_tu` của `lich_dung` | Vị trí phần tử lịch trong danh sách nguồn | ✅ `add_order` / `build_case` |
| `ca_id`, `mo_ta_ngan` ở y lệnh hồ sơ | Chỉ gắn cho y lệnh trọng tâm; mô tả từ tóm tắt đợt cuối ở lớp nạp | ✅ `prepare_cases`; `load_source_cases` dùng tóm tắt của đợt chứa y lệnh, cần giữ rõ hai đường đọc |
| `tham_dinh_id`, `nhan_dinh_id` | Khóa do `add_gold` tạo từ mã ca và vị trí phát hiện | ✅ nạp đáp án và liên kết nhận định–dòng thuốc |
| `tri_thuc.hoat_chat.thanh_phan` | Danh sách mã hoạt chất `list[str]` của mục phối hợp trong danh mục cũ; khác danh sách đối tượng thành phần chế phẩm ở mục 3 | ✅ `add_catalog` đọc danh mục cũ, `app/db/mapping.py` nhận làm cột JSON |
| `tri_thuc.hoat_chat.can_duyet` | Cờ cần duyệt; `add_catalog` đặt `True` khi bổ sung hoạt chất của ca nằm ngoài danh mục cũ | ✅ `app/db/sources.py:add_catalog` và mapping; không phải kết quả dược sĩ đã duyệt |
| `tuoi_luc_vao`, `nguoi_ghi_vai_tro` | Cột đích có trong mapping, chưa có khóa tương ứng trong nguồn hiện đo | ✅ được mapping chấp nhận; không tự tạo giá trị lâm sàng |
| `can_cu_id`, `nhan_dinh_id`, `loai`, `ban_ghi_id`, `mo_ta` của `can_cu` | Liên kết căn cứ cho nhận định; batch ca không sinh hàng | ❌ không lấy từ bộ JSON này |
| `thoi_diem`, `ca_id`, `ma_luat`, `yeu_to`, `chi_tiet_y_lenh_id`, `phan_hoi`, `nhom_ly_do`, `ly_do` của `phan_hoi` | Phản hồi người dùng; batch ca không sinh hàng | ❌ không lấy từ bộ JSON này |

## 5. Kết quả kiểm

Kiểm lại ngày 19/11/2026, chỉ đọc:

- `load_source_cases`: 66 ca hợp lệ; `load_answer`: 66 đáp án hợp lệ; tập mã hai bên khớp nhau.
- Batch chuẩn bị DB: 0 dòng bị loại, 0 tham chiếu mồ côi. Đây là kiểm cấu trúc/nạp, không xác nhận tính đúng y khoa của đáp án.
- `kiem_ho_so_gia_lap.py`: exit 0, `Tổng 60 hồ sơ, 0 hồ sơ lỗi`.
- `kiem_hanh_chinh.py`: exit 0, `Tổng 66 hồ sơ, 0 hồ sơ lỗi; đối chiếu chỉ thêm khóa với bản gốc T45.`
- `kiem_y_lenh_gia_lap.py`: **exit 1**; 26 hồ sơ có lỗi (63 mục), 46 hồ sơ có cảnh báo (75 mục). Không suy ra bộ ca đạt mọi phép kiểm chỉ vì Pydantic nạp được.
- `kiem_phieu_dieu_tri.py`: **exit 1**; 60 hồ sơ có lỗi, vẫn đếm được 333 phiếu. Có 60 thông báo `phần hồ sơ gốc thay đổi` và 112 mục khác. Công cụ so với bản trước T42 trong khi hiện có thêm phần hành chính; ngoài lệch bản gốc còn các mục khác, chưa coi tất cả là lỗi công cụ.

Các lỗi được ghi bằng số lượng, không dán nội dung ca. T59 không sửa công cụ hoặc dữ liệu để làm phép kiểm qua.

## 6. Việc còn mở

- Rà soát độc lập các lỗi/cảnh báo của bộ kiểm y lệnh và phiếu; thống nhất mốc so sánh bản gốc sau bổ sung hành chính. Chưa chỉnh dữ liệu hoặc công cụ trong T59.
- Bổ sung nguồn gốc/ngày tạo/giấy phép nội bộ và ghi nhận người duyệt đáp án nếu cần quản lý phiên bản; hiện chưa có manifest để xác thực các thông tin này.
- Không nhầm đáp án giả lập với căn cứ y khoa hoặc kết luận dược sĩ đã duyệt.
- Không dùng `JsonCaseRepository`/`load_case` trực tiếp cho hồ sơ nhiều đợt; dùng đường chuyển đổi hiện có. README cũ của `data/kb_sources` chỉ mô tả tri thức thuốc, không phải mô tả cấu trúc ca này.

## 7. Cách kiểm lại

Chạy từ gốc dự án, hoàn toàn offline. Các lệnh dưới đã chạy khi viết tài liệu. Không ghi tệp dữ liệu và không in giá trị trường ca. Không cần tải thư viện.

Thiết lập cho các lệnh A–C:

```powershell
$env:UV_OFFLINE='1'
$env:UV_NO_SYNC='1'
$env:UV_NO_CACHE='1'
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONDONTWRITEBYTECODE='1'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
```

A. Đo tệp và hợp khóa (không in giá trị ca)

```powershell
@'
import json
from pathlib import Path
from collections import defaultdict, Counter

def schema(paths):
    fields = defaultdict(set)
    def walk(value, prefix=''):
        if isinstance(value, dict):
            for key, item in value.items():
                path = prefix + '.' + key if prefix else key
                fields[path].add(type(item).__name__)
                walk(item, path)
        elif isinstance(value, list):
            for item in value:
                walk(item, prefix + '[]')
    for path in paths:
        walk(json.loads(path.read_text(encoding='utf-8-sig')))
    return {key: sorted(types) for key, types in sorted(fields.items())}

folders = ['data/mock/demo', 'data/mock/hoso_gia_lap',
           'data/mock/_goc_hoso_truoc_T42', 'data/mock/_goc_truoc_T45',
           'data/gold/demo', 'data/gold/hoso_gia_lap']
current_keys = set()
for folder in folders:
    paths = sorted(Path(folder).glob('*.json'))
    records = [path for path in paths if not path.name.startswith('_')]
    values = [json.loads(path.read_text(encoding='utf-8-sig')) for path in records]
    fields = schema(records)
    print(folder, 'files=', len(paths), 'bytes=', sum(p.stat().st_size for p in paths),
          'records=', len(records), 'record_bytes=', sum(p.stat().st_size for p in records))
    print('first_keys=', list(values[0]) if values else [], 'fields=', fields)
    if folder in ['data/mock/demo', 'data/mock/hoso_gia_lap']:
        current_keys.update(fields)
        encounters = [enc for r in values for enc in
                      (r['dot_dieu_tri'] if isinstance(r['dot_dieu_tri'], list) else [r['dot_dieu_tri']])]
        print('encounters=', len(encounters),
              'orders=', sum(len(e.get('y_lenh', [])) for e in encounters),
              'sheets=', sum(len(e.get('phieu_dieu_tri', [])) for e in encounters),
              'versions=', dict(Counter(r.get('phien_ban_sinh', 'khong_co') for r in values)))
    elif folder.startswith('data/gold'):
        print('findings=', sum(len(r['phat_hien_ky_vong']) for r in values))
meta = Path('data/mock/hoso_gia_lap/_kich_ban.json')
print('metadata=', meta.name, 'bytes=', meta.stat().st_size, 'fields=', schema([meta]))
for folder in ['data/mock/_goc_hoso_truoc_T42', 'data/mock/_goc_truoc_T45']:
    old = set(schema(sorted(Path(folder).glob('*.json'))))
    print(folder, 'only_archived=', sorted(old-current_keys), 'only_current=', sorted(current_keys-old))
print('manifest_candidates=', [p.as_posix() for root in ['data/mock', 'data/gold']
                               for pattern in ['manifest.json', '*/manifest.json']
                               for p in Path(root).glob(pattern)])
'@ | uv run python -
```

B. Nạp mô hình và tóm tắt công cụ kiểm

```powershell
@'
from pathlib import Path
from collections import Counter
import subprocess
import sys
from app.db.reader import load_source_cases
from app.domain.loader import load_answer
from tools.kiem_y_lenh_gia_lap import kiem
from tools.kiem_phieu_dieu_tri import check

cases = load_source_cases(Path.cwd())
answers = [load_answer(p) for folder in ['data/gold/demo', 'data/gold/hoso_gia_lap']
           for p in Path(folder).glob('*.json')]
print('validated_cases=', len(cases), 'validated_answers=', len(answers),
      'matching_ids=', {c.ca_id for c in cases} == {a.ca_id for a in answers})
paths = sorted(Path('data/mock/hoso_gia_lap').glob('HS-*.json'))
errors = []; warnings = []; bad = warn = 0
for path in paths:
    errs, warns = kiem(path)
    bad += bool(errs); warn += bool(warns)
    errors.extend(errs); warnings.extend(warns)
print('order_check:', {'files_with_errors': bad, 'errors': len(errors),
                       'files_with_warnings': warn, 'warnings': len(warnings)})
seen_ids = set(); seen_text = set(); bad = total = 0; categories = Counter()
for path in paths:
    errs, count = check(path, seen_ids, seen_text)
    bad += bool(errs); total += count
    for err in errs:
        categories['phần hồ sơ gốc thay đổi' if err == 'phần hồ sơ gốc thay đổi' else 'khác'] += 1
print('sheet_check:', {'files_with_errors': bad, 'sheets': total,
                       'error_categories': dict(categories)})
for name in ['kiem_ho_so_gia_lap.py', 'kiem_y_lenh_gia_lap.py',
             'kiem_phieu_dieu_tri.py', 'kiem_hanh_chinh.py']:
    run = subprocess.run([sys.executable, 'tools/' + name], capture_output=True,
                         text=True, encoding='utf-8')
    lines = run.stdout.splitlines()
    print(name, 'exit=', run.returncode,
          'summary=', lines[0] if name == 'kiem_y_lenh_gia_lap.py' else lines[-1])
'@ | uv run python -
```

C. Đếm bảng/cột của batch cục bộ

```powershell
@'
from pathlib import Path
from app.db.sources import prepare_cases
from app.db.mapping import TABLES
batch = prepare_cases(Path.cwd())
for table in sorted(batch.tables):
    print(table, len(batch.rows[table]), ','.join(TABLES[table].columns))
print('rejected=', len(batch.rejected), 'orphans=', len(batch.orphans()))
'@ | uv run python -
```

## Bổ sung 27/11/2026 – bộ dữ liệu thời gian trong lượt hỏi

`app/agent/tools/lay_du_lieu_ca.py` đọc `CaBenh` hiện tại trong bộ nhớ; không đổi tệp nguồn, không tạo bộ dữ liệu lưu trên đĩa. Gateway đánh mã và che định danh các ô chuỗi. Mỗi bộ có tối đa 2.000 dòng, giữ dòng mới nhất; số dòng gốc và số dòng bị cắt được ghi trong span. Số dòng phụ thuộc ca và bộ lọc, nên không có tổng cố định cho bộ dữ liệu tạm. Kiểm thử `DEMO-02` lọc `creatinin` có 2 dòng.

Các bộ và trường đầu ra:

- Xét nghiệm: `thoi_diem`, `ma_xet_nghiem`, `ten_xet_nghiem`, `gia_tri`, `don_vi`, `nguong_duoi`, `nguong_tren`, `ngoai_nguong`, `creatinin_tang_nhanh`.
- Sinh hiệu: `thoi_diem`, `loai`, `gia_tri`, `don_vi`.
- Liều từng lần: `thoi_diem`, `thuoc`, `hoat_chat`, `lieu`, `don_vi`, `nguon_lich`; tổng theo hoạt chất: `hoat_chat`, `tong_24h_lon_nhat`, `cua_so_tu`, `cua_so_den`, `lieu_toi_da_ngay`, `vuot`, `so_che_pham`, `nguon_lich`.
- Đợt kháng sinh: `thuoc`, `hoat_chat`, `bat_dau`, `ket_thuc`, `dang_dung`, `ngay_thu`, `trang_thai_dong`; vi sinh: `thoi_diem_lay_mau`, `benh_pham`, `vi_khuan`, `hoat_chat`, `ket_qua`, `mic`.
- Mốc ca: `thoi_diem`, `loai`, `nhan`; không lấy nội dung tự do của diễn biến hoặc chẩn đoán.

Liều có lịch dùng được cộng trên cửa sổ trượt `(cua_so_tu, cua_so_den]`. Khi chỉ có liều mỗi lần và tần suất, tổng được đánh dấu `suy_tu_tan_suat`, không tạo giờ giả; dữ liệu không đủ hoặc không đồng nhất được để trống và nêu trường thiếu. Trần liều lấy qua cấu hình D5, chỉ khi xác định được hoạt chất, đường dùng và đối tượng. Ngày kháng sinh tính theo thời điểm kê y lệnh chờ duyệt của ca. Đây là dữ liệu phục vụ minh hoạ, không phải kết luận điều trị.

Lệnh kiểm bộ dữ liệu tạm: `uv run --offline --no-sync pytest -q -p no:cacheprovider tests/agent/test_tool_lay_du_lieu_ca.py --basetemp %TEMP%/vz2-test` (chọn thư mục tạm mới cho mỗi lần chạy).

### Điều chỉnh 27/11/2026 – fix-2

Không thay đổi tệp nguồn, trường hay số dòng của các bộ dữ liệu tạm. Gateway giữ giá trị ISO 8601 hợp lệ trong cột `thoi_gian` để dựng hình; mẫu gửi LLM vẫn che ngày, các ô chữ khác vẫn che định danh. Căn cứ lịch dùng và tổng 24 giờ đổi thành `tinh:lich_dung`; văn bản căn cứ có tổng và số liều theo từng mức liều thực tế trong cửa sổ tính. Kiểm tra ngoại tuyến: `uv run --offline --no-sync pytest -q -p no:cacheprovider tests/agent/test_tool_lay_du_lieu_ca.py --basetemp %TEMP%/vz2-fix2-case`.
