# T45 – Thông tin hành chính và quản lý người bệnh đầy đủ như bệnh án thật

Làm **trước T44** (cùng sửa `OrderDetailView.tsx`, `schema.sql`, API; T44 sẽ làm trên nền T45). Mô hình: Codex `gpt-6.1-sol` high cho toàn bộ (cả dữ liệu, bằng script xác định). Chạy bằng chế độ nền của app, không dùng `&`. Mẫu tham khảo: bệnh án nội trú Việt Nam (mục I Hành chính, II Quản lý người bệnh, III Chẩn đoán).

## Vấn đề
Tab Hồ sơ bệnh án hiện chỉ có "Mã ca, Người bệnh (giới · tuổi · cân nặng gộp một dòng), khoa, vào viện, nằm viện, dị ứng, chẩn đoán". Dữ liệu `nguoi_benh` chỉ có mã, tuổi, giới tính. Thiếu họ tên, ngày sinh, địa chỉ, đối tượng thanh toán… và chiều cao, cân nặng bị gộp chung một chuỗi chứ không phải trường riêng.

## Bộ trường cần có

### I. Hành chính (theo người bệnh, mức `nguoi_benh`)
| Trường (`snake_case`) | Ghi chú |
| :--- | :--- |
| `ho_ten` | giả lập, viết hoa theo mẫu bệnh án khi hiển thị |
| `ngay_sinh` | khớp tuổi hiện tại trong hồ sơ (`tuoi`) |
| `gioi_tinh`, `tuoi` | đã có; `tuoi_luc_vao` theo từng lần vào viện đã có |
| `dan_toc` | ví dụ Kinh, Tày, Mường… (đa số Kinh) |
| `ngoai_kieu` | quốc tịch nếu ngoại kiều, ngược lại null |
| `nghe_nghiep` | |
| `dia_chi` | `{so_nha, thon_pho, xa_phuong, huyen, tinh_thanh}`; địa danh có thật, số nhà giả |
| `doi_tuong` | `bhyt` / `thu_phi` / `mien` / `khac` |
| `bhyt` | `{so_the (giả, đúng dạng 15 ký tự), gia_tri_den}`; null nếu không có BHYT |
| `nguoi_bao_tin` | `{ho_ten, quan_he, dien_thoai}`; số điện thoại giả dạng `0900 000 0xx`, không số thật |
| `bo_me` | chỉ cho người bệnh dưới 16 tuổi: họ tên bố/mẹ, nghề nghiệp |
| `chieu_cao_cm`, `can_nang_kg` | **trường riêng** ở mức người bệnh (số đo gần nhất lúc vào viện); các số đo theo thời gian vẫn ở `sinh_hieu` |
| `nhom_mau` | tùy chọn |

### II. Quản lý người bệnh (theo từng lần vào viện, mức `dot_dieu_tri`)
Đã có: `hinh_thuc_vao` (ghi chú: giá trị hiện dùng `cap_cuu` v.v.), `thoi_diem_bat_dau/ket_thuc`, `so_ngay_dieu_tri`, `lich_su_khoa`, `khoa_dieu_tri`. Cần thêm:
- `noi_gioi_thieu` (`co_quan_y_te` / `tu_den` / `khac`) và `tuyen_chuyen_den` (cơ sở chuyển đến, nếu có)
- `vao_khoa_luc` (thời điểm vào khoa đầu)
- `so_giuong`, `so_luu_tru` (giả, dạng `LT-2026-xxxxx`), `ma_yt`
- `ra_vien`: `{hinh_thuc: ra_vien|xin_ve|bo_ve|dua_ve|chuyen_vien, chuyen_vien_den, ly_do}`; null khi chưa ra viện
- `bac_si_dieu_tri`: chỉ ghi **vai trò** (ví dụ "Bác sĩ điều trị"), không tên nhân sự, đúng quy ước kho

## Phần 1 – Dữ liệu (Codex tự sinh bằng script xác định, không dùng Haiku)
Viết `tools/sinh_hanh_chinh.py` (chạy lại được, kết quả cố định, có `--dry-run`) thêm khóa `hanh_chinh` (cùng cấp `nguoi_benh`) và `quan_ly` (trong từng phần tử `dot_dieu_tri`) vào **66 tệp**: `data/mock/hoso_gia_lap/HS-001..060.json` và `data/mock/demo/DEMO-01..06.json`. Chỉ **thêm** khóa, không đổi khóa nào khác (kiểm bằng so sánh trước/sau, như T42). Bản gốc để so: tạo `data/mock/_goc_truoc_T45/` chép nguyên 66 tệp trước khi chạy, cấm sửa.

**Họ tên (quyết định của người dùng):** đánh số theo thứ tự `1` đến `66`: `HS-001…HS-060` lấy số 1 đến 60, `DEMO-01…DEMO-06` lấy số 61 đến 66. Nam: `Nguyễn Văn <số>`; nữ: `Nguyễn Thị <số>`. Ví dụ HS-022 (nam) → `Nguyễn Văn 22`. Không sinh tên thật khác.

Các trường còn lại sinh xác định (cùng một hạt giống), **phải khớp hồ sơ**:
- `ngay_sinh` khớp `tuoi` tại thời điểm vào viện đầu; `dan_toc` (đa số Kinh, vài Tày, Mường, Nùng, Hoa); `ngoai_kieu` null; `nghe_nghiep` hợp lứa tuổi (trẻ nhỏ: null, học sinh; người cao tuổi: hưu trí…).
- `dia_chi` với địa danh có thật của Hà Nội và vùng lân cận, số nhà giả; `doi_tuong` (đa số `bhyt`, vài `thu_phi`), `bhyt` số thẻ giả đúng dạng 15 ký tự và hạn còn hiệu lực; `nguoi_bao_tin` (họ tên dạng `Nguyễn Thị <số>` kèm quan hệ, số điện thoại giả `0900 000 0xx`).
- Dưới 16 tuổi (ví dụ HS-020 3 tuổi, HS-040): thêm `bo_me`; quan hệ người báo tin là bố hoặc mẹ.
- `chieu_cao_cm`, `can_nang_kg`: cân nặng khớp giá trị đã có trong `sinh_hieu`/phiếu/hồ sơ nếu có (kiểm tra không mâu thuẫn); chiều cao hợp lý theo tuổi và giới. Trẻ em theo bảng tăng trưởng gần đúng.
- `quan_ly`: `noi_gioi_thieu` (cấp cứu: `tu_den` hoặc `co_quan_y_te`; ngoại trú: `tu_den`), `vao_khoa_luc`, `so_giuong`, `so_luu_tru`, `ma_yt`, `ra_vien` khớp `tong_ket`/`thoi_diem_ket_thuc` (đợt đang mở: null), `bac_si_dieu_tri` ghi vai trò.
- Từ điển cố định (`dan_toc`, `doi_tuong`, `noi_gioi_thieu`, `ra_vien.hinh_thuc`) đưa vào CHECK ở lược đồ.
- Tệp `data/mock/hoso_gia_lap/README.md` (hoặc `BANG_TRA.md`) ghi rõ: toàn bộ họ tên, số thẻ, số điện thoại, địa chỉ là **giả lập**.
- Cập nhật `tools/kiem_ho_so_gia_lap.py` cho phép khóa mới và viết `tools/kiem_hanh_chinh.py` kiểm: đủ trường, từ điển, ngày sinh–tuổi, trẻ em có bố mẹ, tên đúng quy tắc 1 đến 66, chỉ thêm khóa so với bản gốc.

## Phần 2 – Lược đồ và nạp (Codex)
- `db/schema.sql`: thêm cột vào `nghiep_vu.nguoi_benh` (các trường mục I, `dia_chi`, `bhyt`, `nguoi_bao_tin`, `bo_me` dạng `jsonb`, còn lại cột riêng, có CHECK) và `nghiep_vu.dot_dieu_tri` (mục II). Chỉ thêm cột (`ADD COLUMN IF NOT EXISTS`); có lệnh nạp **chỉ cập nhật các cột này** idempotent (`python -m app.db hanh-chinh`), có `--dry-run`, không `--reset`.
- `app/db/mapping.py`, `sources.py`, `engine.py`, `cli.py`, test.

## Phần 3 – API
Thêm vào hợp đồng (chỉ thêm trường, không xóa trường cũ), tạo `plan/api-hop-dong-v1.5-hanh-chinh.md`:
- `dinh_danh_day_du` (hoặc mở rộng `dinh_danh`): `ho_ten`, `ngay_sinh`, `tuoi`, `gioi_tinh`, `chieu_cao_cm`, `can_nang_kg`, `dan_toc`, `ngoai_kieu`, `nghe_nghiep`, `dia_chi` (cả chuỗi hiển thị), `doi_tuong`, `bhyt`, `nguoi_bao_tin`, `bo_me`.
- `quan_ly_nguoi_benh` cho lần vào viện hiện tại và `lich_su_vao_vien` (mọi lần vào viện: thứ tự, khoa, thời điểm vào/ra, hình thức vào, hình thức ra, số ngày, chẩn đoán chính).
- Đọc DB bằng truy vấn chỉ-đọc ngoài `CaBenh` (như T44); chế độ `file` trả trường rỗng, không lỗi.
- **Họ tên là dữ liệu giả nhưng vẫn nhạy cảm về thiết kế:** không đưa `ho_ten`, `ngay_sinh`, `dia_chi`, `dien_thoai` vào nhật ký truy cập, log lỗi, prompt gửi LLM hay bộ nhớ đệm chia sẻ. Pipeline AI **không nhận** các trường này; thêm test khẳng định `CaBenh` và prompt không chứa chúng.

## Phần 4 – Giao diện (`OrderDetailView.tsx` tab Hồ sơ bệnh án)
Sắp xếp **theo thứ tự bệnh án thật**, đầy đủ thông tin hành chính trước rồi mới tới chỉ số và lịch sử:
1. **I. Hành chính:** lưới hai cột, mỗi trường một ô riêng: Họ tên (viết hoa), Ngày sinh, Tuổi, Giới tính, Cân nặng (kg), Chiều cao (cm), Dân tộc, Ngoại kiều, Nghề nghiệp, Địa chỉ, Đối tượng, Số thẻ BHYT và hạn, Người nhà báo tin (tên, quan hệ, SĐT). Dưới 16 tuổi: thêm Họ tên bố/mẹ.
2. **II. Quản lý người bệnh:** vào viện (ngày giờ), hình thức vào, nơi giới thiệu, vào khoa, chuyển khoa (chuỗi từ `lich_su_khoa`), ra viện và hình thức ra viện, tổng số ngày điều trị, số giường, số lưu trữ.
3. **Lịch sử vào viện:** bảng mọi lần vào viện của người bệnh (chưa cần chọn y lệnh ở đây; T44 sau sẽ thêm), bấm một lần để xem y lệnh/phiếu của lần đó.
4. **III. Chẩn đoán** (đã có), dị ứng và cơ địa đặc biệt (đã có).
5. Sau đó mới tới **Chỉ số lâm sàng tính từ hồ sơ**, giá trị ngoài ngưỡng, diễn biến gần nhất (giữ nguyên).
- Tách "Nam 45 tuổi · 72 kg" thành các ô riêng; trường thiếu hiển thị "Chưa ghi nhận", không để trống.
- Bám `plan-1.4-he-thong-thiet-ke.md`; có thể thu gọn/mở rộng từng mục; hoạt động trên màn hình hẹp.
- Danh sách "Hồ sơ bệnh án" (`/app/ho-so`) hiện thêm họ tên (hoặc họ tên viết tắt chỉ chữ cái đầu để giảm lộ), ngày sinh, và hai cột Chẩn đoán/Vào viện đang trống phải có dữ liệu.
- Chế độ demo/mock: trường mới tùy chọn, không đổi hành vi hiện có.

## Nghiệm thu
- Python: `ruff check`, `ruff format --check`, `pytest -q` đều qua; test ánh xạ, nạp thử, kiểm đếm trên dữ liệu thật (60 hồ sơ đều có đủ `hanh_chinh`).
- Web: `vitest`, `oxlint`, `tsc -b`, `build` qua; test từng ô hiển thị, ô thiếu, trẻ em có bố/mẹ.
- Test bảo mật: `CaBenh`/prompt AI không chứa họ tên, ngày sinh, địa chỉ, điện thoại.
- `uv run python -m app.db hanh-chinh --dry-run`: 0 dòng loại.
- Báo cáo `plan/reports/T45.md`.

## Cấm làm
- Không commit/push, không ghi DB thật, không `--reset`, không đụng `.env`.
- Không đưa dữ liệu hành chính vào pipeline AI, nhật ký hay prompt.
- Không thêm thư viện. Không dùng `&` chạy nền. Không dừng giữa chừng để hỏi.
