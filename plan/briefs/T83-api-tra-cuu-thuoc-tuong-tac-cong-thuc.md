# T83 – API tra cứu thuốc, tra tương tác thủ công, máy tính công thức (backend)

Agent: **agy Gemini 4 Hydrogen xhigh**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Không sửa `web/` (T84 làm giao diện sau, dựa vào hợp đồng của task này).

## Bối cảnh

Người dùng (20/11) thêm 3 tính năng cho dược sĩ, chạy trên dữ liệu đã có trong PostgreSQL (`KB_SOURCE=db`), đồng thời là phép thử DB:
1. **Tra cứu thuốc:** bảng thuốc; bấm một thuốc → toàn bộ thông tin: tên, thành phần, nhóm ATC, chỉ định, chống chỉ định, liều, liều suy thận, suy gan, cảnh báo, tương tác, thai kỳ – cho con bú, đường dùng hợp lệ, liều tối đa, độc tính, kháng sinh quản lý, nhóm dị ứng chéo, ngưỡng xét nghiệm, thuốc–bệnh.
2. **Tra tương tác thủ công:** nhập tên thuốc A, B, C… → ma trận giống phần "Yếu tố 4 · Tương tác thuốc" trong trang ca.
3. **Máy tính công thức:** 14 công thức đã cài trong `app/calc/` (danh mục `config/kb/cong_thuc.yaml`). **Chỉ** dùng hàm đã cài và đã kiểm; **không** dùng dữ liệu cào MDCalc trong `data/formulas/`.

Đọc trước: `AGENTS.md`, `app/api/routes.py`, `app/api/schemas.py`, `app/api/service.py`, `app/api/presenter.py` (dựng `MaTranTuongTac`), `app/rules/interaction.py` (`build_interaction_matrix`, `_evaluate`), `app/kb/resolver/resolver.py`, `app/kb/interactions/store.py`, `app/db/bang_luat_store.py`, `app/retrieval/corpus.py`, `app/calc/*`, `config/kb/cong_thuc.yaml`, `plan/api-hop-dong-v1*.md`.

## Hợp đồng – `plan/api-hop-dong-v1.8-tra-cuu.md` (viết trước, khối `interface` TypeScript như v1.4/v1.7 để `tests/api/test_contract.py` đọc; thêm tệp vào test hợp đồng)

Mọi điểm cuối cần đăng nhập (`Caller`), chỉ đọc, `Cache-Control: private, no-store`.

### 1. `GET /api/thuoc?q=&trang=1&so_dong=30`
Tìm theo tên thuốc / hoạt chất (không dấu, không phân biệt hoa thường) trên `tri_thuc.tra_cuu_thuoc` + `tra_cuu_hoat_chat` + `tra_cuu_dong_nghia`. Không có `q` → danh sách hoạt chất có dữ liệu (ưu tiên hoạt chất có nhãn FDA / có quy tắc). Trả `{tong, trang, so_dong, ket_qua: [{hoat_chat_id, ten_inn, ten_viet, ma_atc[], so_che_pham, co_nhan_fda, so_quy_tac}]}`. Truy vấn phía DB (ILIKE / chỉ mục), giới hạn `so_dong ≤ 100`.

### 2. `GET /api/thuoc/{hoat_chat_id}`
Gộp, mỗi phần ghi **nguồn** (tên bảng / nhãn FDA set_id / DDInter) và **trạng thái duyệt** (`cho_duoc_si_duyet`…), không suy diễn:
- `dinh_danh`: INN, tên Việt, rxcui, ATC, `ddinter_id`.
- `che_pham`: tối đa 50 chế phẩm Cục QLD (`tra_cuu_thuoc` + `thuoc_thanh_phan`: tên, số đăng ký, dạng bào chế, hàm lượng) + tổng số.
- `nhan_fda`: các đoạn `tri_thuc.doan_trich` có `hoat_chat_ids ? hoat_chat_id`, nhóm theo `muc` (`chi_dinh`, `chong_chi_dinh`, `lieu`, `lieu_than`, `lieu_gan`, `canh_bao`, `tuong_tac`, `thai_ky_cho_bu`, `nhi_cao_tuoi`, `tac_dung_phu`, `qua_lieu`, `duoc_ly`, `khac`), giữ `duong_dan_muc`, `noi_dung_goc`, `url_goc`, `doan_trich_id`.
- `quy_tac`: các dòng của hoạt chất trong bảng luật D1–D7 (`load_rule_data` / bảng quan hệ T77): liều thận, gan, ngưỡng xét nghiệm, thuốc–bệnh, đường dùng, liều tối đa, độc tính, kháng sinh quản lý, nhóm dị ứng chéo, nhóm trùng điều trị – trả nguyên trường đã có (kèm `trich_nguyen_van`, `trang_thai`).
- `tuong_tac_tom_tat`: số cặp DDInter theo mức (Major / Moderate / Minor / Unknown) và 20 cặp Major đầu (tên thuốc kia, cơ chế) – một truy vấn có `LIMIT`, **không** nạp cả bảng.
- Hoạt chất không tồn tại → 404 thân lỗi chuẩn.

### 3. `POST /api/tuong-tac` body `{thuoc: string[]}` (2–12 tên tự do)
Phân giải từng tên bằng `DrugResolver` (như dòng y lệnh `ten_tu_do`) → dựng một `CaBenh` tạm **trong bộ nhớ** (không ghi DB, không ghi `ket_qua_tham_dinh`) với mỗi tên một dòng y lệnh chờ duyệt → `build_interaction_matrix` → trả **đúng** `MaTranTuongTac` như trang ca (cùng mức N/L/T/K/–/?, cùng `CanCu` DDInter), kèm `phan_giai: [{ten_nhap, trang_thai, hoat_chat[]}]` để báo tên nào không nhận diện được. Tên trống / trùng → 422.

### 4. `GET /api/cong-thuc` và `POST /api/cong-thuc/{ma}`
`GET`: danh mục từ `config/kb/cong_thuc.yaml` (ma, ten, loai, dau_vao kèm đơn vị cho phép / lựa chọn, dau_ra, tham_khao_goc, tham_chieu_mdcalc). `POST` body `{dau_vao: {...}}` → gọi đúng hàm `ham` trong yaml, trả `CalcResult` (`ket_qua`, `don_vi`, `ghi_chu`, `thieu_dau_vao`, `tham_khao`). Ngoài miền hợp lệ (`ValueError`) → 422 thông báo tiếng Việt, không lộ traceback. `ma` không có → 404. Không `eval`; ánh xạ `ham` qua danh sách cho phép.

## Yêu cầu chung

- Dùng lại kết nối `read_pool` / kho đã làm nóng (T79), không mở kết nối mới cho từng dòng. Chế độ tệp (`KB_SOURCE=file`) vẫn chạy được cho test.
- Không thay đổi kết quả thẩm định hiện có.

## Test

`tests/api/test_tra_cuu.py`: tìm "metformin" / "paracetamol" (không dấu) ra hoạt chất đúng; chi tiết meropenem có `lieu_than` từ nhãn và quy tắc thận; `POST /api/tuong-tac` ["Amiodaron 200 mg", "Digoxin 0,25 mg"] ra ô N với căn cứ DDInter; tên lạ → `phan_giai` báo chưa nhận diện, ô "?" / "T"; công thức `cockcroft_gault` (tuổi 75, nữ, 50 kg, creatinin 1,2 mg/dL) khớp hàm gốc, `child_pugh` thiếu đầu vào → `thieu_dau_vao`; `POST` không gọi DB ghi. Test hợp đồng đọc v1.8. Toàn kho 0 trượt, `ruff` sạch.

## Phạm vi

`app/api/` (routes mới, schemas, service hoặc module dịch vụ tra cứu mới `app/api/lookup.py`), `app/db/` (truy vấn tra cứu nếu cần), `plan/api-hop-dong-v1.8-tra-cuu.md`, `tests/api/`. Cấm `web/`, `data/`, `app/rules/` (chỉ được gọi hàm có sẵn), lược đồ. Báo cáo `plan/reports/T83.md`.
