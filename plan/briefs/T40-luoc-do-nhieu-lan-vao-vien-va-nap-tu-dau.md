# T40 – Lược đồ nhiều lần vào viện, nhiều y lệnh và lệnh nạp từ đầu (plan 1.7 mục 10)

Đọc trước: `AGENTS.md`, `plan/plan-1.7-du-lieu-benh-an-gia-lap.md` (mục 3.0, 5.1, 5.2, 10), `db/README.md`, `db/schema.sql`, `app/db/mapping.py`, `app/db/sources.py`, `app/db/engine.py`, `app/db/cli.py`, `tests/db/`.

## Bối cảnh
- Bộ 60 hồ sơ giả lập mới nằm ở `data/mock/hoso_gia_lap/HS-001..060.json` (định dạng: `plan/briefs/H3-sinh-ho-so-gia-lap.md`), đáp án ở `data/gold/hoso_gia_lap/`. Mỗi hồ sơ gồm **nhiều lần vào viện** (`dot_dieu_tri[]`), mỗi lần **nhiều y lệnh** (`y_lenh[]`), đúng một y lệnh trọng tâm (`trang_thai = "cho_duyet"`, `y_lenh_trong_tam`) mà đáp án nói tới. Bảng tra: `data/mock/hoso_gia_lap/BANG_TRA.md`. Script kiểm: `tools/kiem_ho_so_gia_lap.py` (đừng sửa).
- 6 ca cũ `data/mock/demo/DEMO-xx.json` (định dạng `CaBenh`, mỗi ca một đợt, một y lệnh) và đáp án `data/gold/demo/` **vẫn phải nạp được**, ánh xạ vào cùng lược đồ mới (mỗi ca thành một đợt, y lệnh `y_lenh_cho_duyet` là trọng tâm).
- Hiện lược đồ gắn "ca" vào `dot_dieu_tri.ca_id` (một đợt = một ca). Mới: **"ca" là y lệnh trọng tâm**.
- Ứng dụng chạy bằng tệp, không đọc Supabase; chỉ `app/db`, `db/`, `tests/db/` dính tới DB.

## Yêu cầu

### A. Lược đồ (`db/schema.sql`), theo phần 10 của plan 1.7
1. **Ca thuộc y lệnh.** Thêm `y_lenh.ca_id text UNIQUE` (nullable: chỉ y lệnh trọng tâm có), `y_lenh.mo_ta_ngan text` (nullable). **Bỏ** `dot_dieu_tri.ca_id` và `dot_dieu_tri.mo_ta_ngan`. `lan_tham_dinh.ca_id` và `phan_hoi.ca_id` trỏ khóa ngoại vào `y_lenh(ca_id)` (thay vì `dot_dieu_tri(ca_id)`). Giữ `lan_tham_dinh.y_lenh_id` và bảo đảm hai cột nhất quán (cùng một y lệnh) bằng ràng buộc hoặc khóa ngoại tổng hợp.
2. **`dot_dieu_tri` thêm cột** (đều nullable): `thu_tu integer`, `thoi_diem_ket_thuc timestamptz`, `so_ngay_dieu_tri integer`, `hinh_thuc_vao text`, `lich_su_khoa jsonb`, `ly_do_vao_vien text`, `benh_su text`, `tien_su jsonb`, `kham_benh text`, `tom_tat text`, `tong_ket text`, `tuoi_luc_vao integer`. Ràng buộc duy nhất `(nguoi_benh_id, thu_tu)`. Giữ `co_dia jsonb NOT NULL`.
3. **`y_lenh` thêm cột:** `vai_tro_nguoi_ke text` (kiểm: `bac_si_dieu_tri`, `bac_si_truc`, `hoi_chan`), `loai text` (kiểm: `thuong_quy`, `cap_cuu`, `khi_can`, `hoi_chan`), `trang_thai text NOT NULL` (kiểm: `cho_duyet`, `da_duyet`, `dang_thuc_hien`, `ngung`, `hoan_tat`), `thay_the_y_lenh_id text` (khóa ngoại tự tham chiếu `y_lenh(y_lenh_id)`), `ly_do_ngung text`, `thoi_diem_ngung timestamptz`. Với 6 ca demo: `trang_thai = 'cho_duyet'`, `loai = 'thuong_quy'`, `vai_tro_nguoi_ke = 'bac_si_dieu_tri'`.
4. **Bỏ lưu tay `chi_tiet_y_lenh.thuoc_dang_dung`.** Xóa cột; tạo **view** `nghiep_vu.v_thuoc_dang_dung` gồm các dòng thuốc có `trang_thai_dong = 'active'` thuộc y lệnh có `trang_thai IN ('da_duyet','dang_thuc_hien')`. `chi_tiet_y_lenh.y_lenh_id` thành **NOT NULL**: dòng "thuốc đang dùng" của ca demo (không có y lệnh) được gắn vào **một y lệnh nền tổng hợp** `YL-<ca_id>-NEN` (`trang_thai = 'dang_thuc_hien'`, cùng đợt, `thoi_diem_ke` = thời điểm bắt đầu sớm nhất của các dòng đó); chỉ tạo khi ca có dòng như vậy.
5. **Không làm** mục 5 (`la_gia_lap` ...): bỏ qua, giữ nguyên `nguoi_benh`.
6. **Chuẩn hóa mã hoạt chất (mục 6 của phần 10).** `tri_thuc.hoat_chat` chỉ giữ **mã chuẩn** của `data/kb/hoat_chat.json` (kiểu `amoxicillin`). Khi nạp ca (cả demo lẫn hồ sơ mới), mọi mã hoạt chất dạng `HC-...` được **ánh xạ về mã chuẩn** trước khi ghi `thuoc_hoat_chat`, `di_ung`, `khang_sinh_do`. Quy tắc: bỏ tiền tố `HC-`, viết thường, đổi `-` thành `_`; cộng bảng đồng nghĩa tường minh trong code cho các mã lệch tên: `AMLODIPIN→amlodipine`, `CEFTRIAXON→ceftriaxone`, `ACID-CLAVULANIC→clavulanic_acid`, `ACID_CLAVULANIC→clavulanic_acid`, `SULFAMETHOXAZOL→sulfamethoxazole`, `COLISTIMETHAT→colistimethate`, `VALPROATE→valproic_acid`, `ACIDVALPROIC→valproic_acid`, `INSULIN_GLARGIN→insulin_glargine`, `ENOXAPARIN→enoxaparin`, `HEPARIN→heparin`, `TRIMETHOPRIM→trimethoprim`. Mã nào sau ánh xạ vẫn không có trong KB phải được **liệt kê trong báo cáo** (không im lặng). Hợp danh mục "KB + danh mục ca" không còn sinh các dòng `HC-...` trùng nghĩa.
7. **Hoạt chất ngoài tri thức** (ví dụ `gabapentin`, `cefoperazone`, `sulbactam` của hồ sơ ngoài HDSD): thêm vào `tri_thuc.hoat_chat` với `can_duyet = true`, `ten_hoat_chat` và `ten_quoc_te` lấy từ danh mục hoạt chất của chính hồ sơ, `ma_atc` / `nhom_duoc_ly` nếu có; không bịa. Mã tạo theo quy tắc chuẩn hóa ở mục 6.
8. **`chan_doan`** thêm `thoi_diem timestamptz` (nullable); **`dien_bien`** thêm `nguoi_ghi_vai_tro text` (nullable). Nạp các trường này từ hồ sơ mới nếu có (`chan_doan` hồ sơ mới chưa có thời điểm riêng: dùng `thoi_diem_bat_dau` của đợt).
9. Mọi bảng mới/đổi vẫn **bật RLS, không có policy**, đúng quy ước hiện tại; view không cấp quyền cho `anon`, `authenticated`.

### B. Ánh xạ và nạp (`app/db/mapping.py`, `app/db/sources.py`, `app/db/engine.py`, `app/db/cli.py`)
1. Nhóm `cases` nạp **cả hai nguồn**: `data/mock/demo` (6 ca) và `data/mock/hoso_gia_lap` (60 hồ sơ), cộng đáp án `data/gold/demo`, `data/gold/hoso_gia_lap`. Bỏ qua tệp bắt đầu bằng `_` (như `_kich_ban.json`, `BANG_TRA.md`).
2. Hồ sơ mới: một `nguoi_benh`; mỗi phần tử `dot_dieu_tri[]` thành một dòng `dot_dieu_tri` (các cột mới theo mục A2, `dot_dieu_tri_id` lấy từ hồ sơ); `chan_doan`, `sinh_hieu`, `ket_qua_xet_nghiem`, `vi_sinh` (+ `khang_sinh_do`), `dien_bien` theo từng đợt; mỗi `y_lenh[]` thành một dòng `y_lenh` (`ca_id` = `ho_so_id` **chỉ** cho y lệnh trọng tâm; `mo_ta_ngan` lấy `tom_tat` của đợt cuối rút gọn tối đa 200 ký tự); `chi_tiet_y_lenh` (+ `lich_dung`) theo từng y lệnh. `di_ung` và `tinh_trang_di_ung` ở cấp hồ sơ gắn vào `nguoi_benh`. `danh_muc_thuoc` và `danh_muc_hoat_chat` vào `thuoc`, `thuoc_hoat_chat`, `hoat_chat`. Trường tuổi: `nguoi_benh.tuoi` lấy từ hồ sơ; `tuoi_luc_vao` ở đợt không có thì để null.
3. Đáp án vàng của hồ sơ mới nạp như của demo vào `lan_tham_dinh`, `nhan_dinh`, `nhan_dinh_thuoc`; mã `ca_id` = `ho_so_id`, `y_lenh_id` = y lệnh trọng tâm.
4. Hồ sơ trùng ID thuốc giữa các hồ sơ phải gộp theo khóa chính, nhưng **cảnh báo** nếu hai bản có nội dung khác nhau (cùng `thuoc_id` khác `ten_thuoc`/`ham_luong`/thành phần): báo vào báo cáo và loại bản sau vào `data/runtime/nap_loi.jsonl`, không âm thầm ghi đè.
5. `--dry-run` vẫn không mở kết nối, in số dòng dự kiến mỗi bảng (kể cả bảng mới) và số dòng bị loại. Mọi dòng bị loại phải **bằng 0** với dữ liệu hiện có (nếu không phải giải thích trong báo cáo).
6. `verify` đối chiếu cả bảng mới, view `v_thuoc_dang_dung`, ràng buộc `ca_id` và khóa ngoại mới.

### C. Nạp từ đầu bằng một lệnh
Lệnh duy nhất **`uv run python -m app.db all --reset --yes`** phải dựng lại toàn bộ từ trắng: xóa hai lược đồ, tạo lại theo `db/schema.sql` mới, nạp `cases` (66 hồ sơ/ca), `kb`, `ddinter`, `embeddings`, rồi `verify`. Không cần lệnh nào khác. Cập nhật `db/README.md`: bảng lệnh, mô tả lược đồ mới (quan hệ người bệnh → lần vào viện → y lệnh → dòng thuốc; ca = y lệnh trọng tâm), thứ tự bảng, mục "nạp từ đầu một lệnh", và nhắc rằng mọi thay đổi cột chỉ cần sửa `db/schema.sql` + `mapping.py` rồi chạy lại lệnh trên.

### D. Kiểm thử (`tests/db/`)
Cập nhật và thêm test, không giảm độ phủ hiện có:
- nạp thử trong bộ nhớ cả 66 hồ sơ/ca qua lớp chuyển đổi: 0 dòng bị loại, 0 khóa ngoại mồ côi, mọi mã hoạt chất sau ánh xạ nằm trong tập mã chuẩn hoặc tập "ngoài tri thức" đã nêu;
- mỗi y lệnh trọng tâm có `ca_id` duy nhất, mỗi hồ sơ đúng một;
- đợt cũ không có `ca_id`; đáp án vàng trỏ đúng y lệnh;
- 6 ca demo vẫn qua (có y lệnh nền tổng hợp khi cần);
- bảng đếm dòng dự kiến khớp: 66 `nguoi_benh`; tổng đợt bằng 6 + 87; tổng y lệnh đúng số đếm thực tế từ tệp;
- test sinh SQL: `schema.sql` có các cột/ràng buộc mới, không còn `thuoc_dang_dung`, `dot_dieu_tri.ca_id`.
Test không được mở kết nối mạng hay đọc `.env`.

## Tiêu chí nghiệm thu (chạy được)
```
uv run ruff check app/db tests/db
uv run pytest -q tests/db -p no:cacheprovider
uv run pytest -q -p no:cacheprovider          # toàn bộ vẫn qua
uv run python -m app.db all --dry-run          # không kết nối; 0 dòng bị loại
```
Báo cáo `plan/reports/T40.md`: danh sách thay đổi từng tệp, kết quả bốn lệnh trên, bảng số dòng dự kiến, danh sách mã hoạt chất không ánh xạ được và hoạt chất thêm mới "ngoài tri thức", và mọi chỗ lệch brief.

## Cấm làm
- **Không chạy lệnh ghi vào Supabase** (`schema`, `reset`, `load` không `--dry-run`, `all` không `--dry-run`); chỉ `--dry-run`. Claude sẽ chạy bước ghi sau khi review.
- Không đọc, in, hay ghi `.env` hoặc chuỗi kết nối vào log/báo cáo.
- Không sửa: `data/mock/**`, `data/gold/**`, `tools/`, `web/`, `app/` ngoài `app/db/`, `tests/` ngoài `tests/db/`, tài liệu `plan/` trừ báo cáo của task này.
- Không thêm thư viện.
- Không đổi quy ước RLS (bật, không policy) và không cấp quyền cho vai trò công khai.
