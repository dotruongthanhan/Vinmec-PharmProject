# T50 – Từ điển thuốc: cào Cục Quản lý Dược, tách thành phần, ánh xạ RxNav / ATC

Mô hình: Codex `gpt-6.2-sol`, effort `high`. Chạy nền, không dừng để hỏi. Điểm chưa rõ thì chọn cách ít rủi ro nhất và ghi vào báo cáo, mục "Lựa chọn đã làm".

Đọc trước:
- `AGENTS.md`
- `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md`: mục 3.1, 3.2 (đồng bộ, chống bản ghi ma), 4.1 (từ điển thuốc), đợt D0.1–D0.3
- `plan/plan-1.3-du-lieu-thu-thap-tong-hop-tien-xu-ly.md`: mục 4 (4 tầng), mục 5 (chuẩn hoá tên)
- `app/kb/names.py`, `app/kb/fetch/*` (cách cào openFDA đã có: client, thử lại, manifest)

Task **T51** (cào DDInter) chạy **song song**. Không đụng file của nó.

## Mục tiêu

Dựng tầng 0 → tầng 2 cho **trục hoạt chất** và **chế phẩm**, để T52 làm được bộ phân giải tên. Cụ thể:

1. Tải toàn bộ công bố số đăng ký thuốc của Cục Quản lý Dược.
2. Tách văn bản hoạt chất của mỗi thuốc thành từng thành phần.
3. Ánh xạ từng thành phần sang hoạt chất chuẩn quốc tế (`rxcui`, nhóm ATC) qua RxNav.
4. Xuất từ điển và báo cáo độ phủ.

## Phạm vi file

**Được tạo / sửa:**
- `app/kb/sources/dav.py`, `app/kb/sources/rxnav.py` (mới)
- `app/kb/dictionary/**` (mới: tách thành phần, dựng trục, ánh xạ, báo cáo)
- `app/kb/fetch/__main__.py` và `app/kb/fetch/runner.py`: **chỉ thêm** lệnh con `dav`, `rxnav`; không đổi hành vi lệnh cũ
- `app/kb/__main__.py`: chỉ thêm lệnh con nếu cần
- `tests/kb/test_dav*.py`, `tests/kb/test_rxnav*.py`, `tests/kb/test_dictionary*.py`, `tests/kb/fixtures/dav/**`, `tests/kb/fixtures/rxnav/**`
- Dữ liệu: `data/kb_sources/dav/**`, `data/kb_sources/rxnav/**`, `data/kb_staging/tu_dien/**`, `data/kb_curated/tu_dien/**`, `data/kb_reports/T50_*`
- Báo cáo `plan/reports/T50.md`

**Cấm đụng:**
- `app/rules/**`, `app/api/**`, `app/db/**`, `app/llm/**`, `app/orchestration/**`, `web/**`
- `db/schema.sql`, `data/mock/**`, `data/kb/**` (chỉ đọc)
- `data/kb_sources/ddinter*/**`, `data/kb_sources/manifest.json` (chỉ đọc; manifest của task này để riêng ở `data/kb_sources/dav/manifest.json` và `data/kb_sources/rxnav/manifest.json`)
- `app/kb/sources/ddinter*`, `app/kb/fetch/ddinter*`, `tests/kb/test_ddinter*` (của T51)
- `config/prompts/`, `.env`, `pyproject.toml`, `uv.lock`: không thêm thư viện; dùng `httpx` / thư viện chuẩn đã có. Nếu thật sự thiếu thì dừng và ghi báo cáo

## Mạng được phép

- `https://dichvucong.dav.gov.vn`: chỉ trang công bố `/congbothuoc/index`, JS của trang đó, và điểm `POST /api/services/app/soDangKy/GetAllPublicServerPaging`.
- `https://rxnav.nlm.nih.gov/REST/`: các điểm `approximateTerm`, `rxcui`, `related`, `rxclass/class/byRxcui` hoặc `byDrugName`.

Ràng buộc chung:
- Không đăng nhập, không vượt CAPTCHA.
- User-Agent chung, ví dụ `VinmecPharmProject-kb/1.0`. Không ghi email hay tên người.
- Test **không gọi mạng**: dùng fixture.

## Yêu cầu

### 1. Cào Cục Quản lý Dược (`python -m app.kb.fetch dav`)

- Claude đã thấy điểm này trả `{"result":{"totalCount":55030,"items":[...]}}`. Mỗi `item` có:
  - `tenThuoc`, `soDangKy`, `soDangKyCu`, `isHetHan`, `isActive`
  - `thongTinThuocCoBan.{hoatChatChinh, hamLuong, dangBaoChe, dongGoi, tieuChuan, tuoiTho, maDuongDung, tenDuongDung}`
  - `thongTinTaiLieu.{urlHuongDanSuDung, urlNhan, urlNhanVaHDSD}`
  - `thongTinDangKyThuoc.{ngayCapSoDangKy, ngayHetHanSoDangKy, soQuyetDinh, dotCap}`
  - `congTySanXuat`, `congTyDangKy`, `id`
- **Tự tìm thân yêu cầu đúng** bằng cách đọc JS của trang. Có thể là kiểu ABP: `skipCount`, `maxResultCount`, cùng đối tượng lọc. Ghi thân yêu cầu đã dùng vào báo cáo.
- Kích thước trang:
  - Thử 100. Nếu máy chủ từ chối hoặc cắt bớt thì giảm dần (50, 20) và ghi lại.
  - Kiểm `totalCount` không đổi giữa các trang.
  - Kiểm tổng số `id` không trùng bằng `totalCount`. Lệch thì ghi báo cáo, không tự lấp.
- Nhịp: tối đa **1 yêu cầu/giây**. Thử lại khi gặp 429/5xx, có giãn cách, tối đa 5 lần.
- **Chạy tiếp được sau khi dừng:** lưu từng trang thô `data/kb_sources/dav/trang/<skip>.json.gz`; chạy lại thì bỏ qua trang đã có (trừ khi `--refresh`).
- `manifest.json` riêng ghi: ngày lấy, URL, thân yêu cầu, `totalCount`, số trang, SHA-256 từng tệp, ghi chú giấy phép ("dữ liệu công bố của Cục Quản lý Dược – Bộ Y tế").
- **Không tải tệp PDF tờ hướng dẫn sử dụng.** Chỉ giữ URL.
- Tầng 1, `data/kb_staging/tu_dien/dav_thuoc.jsonl`: mỗi số đăng ký một dòng gồm
  - `so_dang_ky`, `ten_thuoc`, `hoat_chat_goc` (nguyên văn `hoatChatChinh`), `ham_luong_goc`, `dang_bao_che`, `dong_goi`
  - `duong_dung_goc` (`tenDuongDung` nếu có), `con_hieu_luc`, `url_hdsd`, `url_nhan`, `dav_id`, `ngay_het_han`

### 2. Tách thành phần (`app/kb/dictionary/split.py`, hàm thuần)

Đầu vào: `hoat_chat_goc` + `ham_luong_goc`. Đầu ra: danh sách `{ten_hoat_chat_goc, ten_chuan_hoa, dang_muoi, ham_luong, don_vi}` và `trang_thai`: `tach_duoc` · `chua_khop` (kèm `ly_do`).

Quy tắc, chỉ bằng code, **không dùng LLM**:
- Tách phối hợp theo `;`, `,` ở cấp ngoài cùng, `+`, ` và `, `/`. Không tách bên trong ngoặc.
- Bỏ phần "(dưới dạng …)", "(as …)", "tương đương (với)", "eq. to", tiêu chuẩn dược điển (`USP`, `BP`, `EP`, `DĐVN`, `JP`, `Ph.Eur`, năm). Phần muối đã bỏ thì ghi vào `dang_muoi`.
- Tách hàm lượng cho từng thành phần khi `ham_luong_goc` có cùng số phần (ví dụ `875mg; 125mg`, `800/160 mg`). Không khớp số phần thì để `ham_luong` = `null`, không đoán.
- Dùng lại khoá chuẩn hoá và danh sách muối của `app/kb/names.py`; mở rộng danh sách muối thì đặt trong `dictionary/`, không sửa hành vi hàm cũ.
- Thuốc dược liệu / đông dược (nhiều vị, tên Latin thực vật) và vaccin, sinh phẩm: gắn `loai_san_pham` = `duoc_lieu` · `sinh_pham` theo dấu hiệu rõ ràng. Không tách được thì `chua_khop`.
- **Không chắc thì `chua_khop`.** Thà thiếu còn hơn khớp sai.

Test bằng ví dụ thật lấy từ dữ liệu, ít nhất 25 ca:
- Đơn chất có "(dưới dạng …)".
- Phối hợp 2 và 3 thành phần.
- "Sulfamethoxazol 800mg; Trimethoprim 160mg".
- "Amoxicilin (dưới dạng Amoxicilin trihydrat) 875mg; Acid clavulanic (dưới dạng Kali clavulanat) 125mg".
- Có "tương đương".
- Dịch truyền "Natri clorid 0,9%".
- Ca phải ra `chua_khop`.

### 3. Trục hoạt chất và ánh xạ RxNav (`python -m app.kb.fetch rxnav`, `app/kb/dictionary/axis.py`)

- Tập tên cần ánh xạ:
  - (a) Mọi `ten_chuan_hoa` duy nhất từ bước 2.
  - (b) 54 hoạt chất trong `data/kb/hoat_chat.json` (kèm đồng nghĩa).
  - (c) Mọi tên hoạt chất trong `danh_muc_hoat_chat` / `danh_muc_thuoc` của `data/mock/demo/*.json` và `data/mock/hoso_gia_lap/*.json` (chỉ đọc).
- Thứ tự khớp, mỗi tên ghi `cach_khop`:
  1. Tên đã có trong `data/kb/hoat_chat.json` hoặc đồng nghĩa → `ma_chuan`.
  2. Bảng chính tả Việt → quốc tế viết tay trong code (ví dụ `amoxicilin→amoxicillin`, `ceftriaxon→ceftriaxone`, `acid clavulanic→clavulanic acid`, `natri clorid→sodium chloride`, `paracetamol→acetaminophen`). Chỉ thêm mục **chắc chắn**; liệt kê toàn bộ trong báo cáo để Claude duyệt → `bang_viet_quoc_te`.
  3. RxNav: tìm chính xác theo tên (`rxcui.json?name=`) với `tty` IN/PIN → `rxnav_chinh_xac`.
  4. RxNav `approximateTerm` → **chỉ đưa vào `cho_duyet`**, không ghi vào trục (kèm điểm và tên RxNav gợi ý).
- Với mỗi IN đã khớp:
  - Lấy `rxcui`, tên IN.
  - Lấy lớp ATC qua RxClass (`relaSource=ATC`), có thể nhiều lớp.
  - PIN → IN qua `related?tty=IN`.
- Nhịp RxNav: tối đa 5 yêu cầu/giây. Lưu đệm thô `data/kb_sources/rxnav/cache/<khoa>.json`; chạy lại thì đọc đệm.
- Khoá `hoat_chat_id`:
  - Giữ đúng khoá cũ cho 54 hoạt chất đã có (ví dụ `acetaminophen`, `amoxicillin_and_clavulanate_potassium` là mục phối hợp cũ: ghi rõ cách xử lý trong báo cáo, **không đổi khoá cũ**).
  - Hoạt chất mới: tên IN của RxNav, viết thường, `snake_case`.

### 4. Đầu ra tầng 2 (`data/kb_curated/tu_dien/`)

Ghi JSONL, có `phien_ban` và `ngay_dung`. Mỗi dòng có `nguon_ban_ghi_ids` trỏ về tầng 0/1.

| Tệp | Nội dung |
|:--|:--|
| `hoat_chat.jsonl` | `hoat_chat_id`, `ten_inn`, `ten_viet` (cách viết VN gặp nhiều nhất trong dữ liệu Cục Quản lý Dược, hoặc từ `data/kb`), `rxcui`, `ma_atc[]`, `ten_lop_atc[]`, `loai` (`thuoc` · `dich_truyen_dien_giai` · `vitamin_khoang` · `duoc_lieu` · `sinh_pham`, chỉ khi có căn cứ rõ; còn lại `thuoc`), `nguon_ban_ghi_ids` |
| `dong_nghia.jsonl` | `khoa_chuan_hoa`, `hoat_chat_id`, `loai` (`inn` · `viet` · `muoi` · `biet_duoc`), `nguon`, `cach_khop` |
| `thuoc.jsonl` | Chế phẩm Cục Quản lý Dược: `thuoc_id` = `dav:<so_dang_ky>`, `ten_thuoc`, `so_dang_ky`, `ham_luong`, `dang_bao_che`, `duong_dung_goc`, `con_hieu_luc`, `url_hdsd`, `trang_thai_tach` |
| `thuoc_thanh_phan.jsonl` | `thuoc_id`, `hoat_chat_id`, `ham_luong`, `don_vi`, `dang_muoi`; **chỉ khi mọi thành phần của thuốc đã khớp trục**. Một phần không khớp thì cả thuốc vào `cho_duyet` |
| `anh_xa.jsonl` | `nguon`, `ma_ban_ghi_nguon`, `ten_goc`, `hoat_chat_id`, `cach_khop`, `do_tin_cay` |
| `cho_duyet.jsonl` | Mọi tên / thuốc chưa khớp hoặc khớp gần đúng, kèm `ly_do` và gợi ý |

**Bất biến kiểm bằng test:**
- Không dòng nào ở `thuoc_thanh_phan` trỏ tới `hoat_chat_id` không có trong `hoat_chat`.
- Không có `hoat_chat` nào không có nguồn neo (Cục Quản lý Dược + RxNav, hoặc `data/kb`).
- Không có dòng tầng 2 nào thiếu `nguon_ban_ghi_ids`.

### 5. Báo cáo độ phủ (`python -m app.kb.dictionary report`)

`data/kb_reports/T50_do_phu.csv`: mỗi hoạt chất một dòng; các cột:
- `so_thuoc_dav`, `co_rxcui`, `co_atc`
- `co_nhan_openfda` (có tệp trong `data/kb_sources/openfda/` khớp khoá)
- `trong_ca_gia_lap`
- `ddinter_id` để trống (T52 điền)

`data/kb_reports/T50_tom_tat.json`:
- Tổng số bản ghi Cục Quản lý Dược; tỷ lệ `tach_duoc` / `chua_khop` (kèm 10 lý do hàng đầu).
- Số tên ánh xạ theo từng `cach_khop`; số hoạt chất trên trục.
- **Danh sách hoạt chất trong ca giả lập chưa khớp** (mục tiêu: 0).

`data/kb_reports/T50_mau_kiem.jsonl`: 50 bản ghi Cục Quản lý Dược chọn ngẫu nhiên (seed 50) kèm kết quả tách và ánh xạ, cộng 30 hoạt chất ngẫu nhiên kèm ATC. Claude sẽ so tay với trang gốc.

## Nghiệm thu (dán kết quả vào báo cáo)

- `uv run python -m app.kb.fetch dav` chạy hết; dán `totalCount`, số trang, số `id` duy nhất, thời gian chạy.
- `uv run python -m app.kb.fetch rxnav` chạy hết; dán số tên tra, số khớp theo `cach_khop`.
- `uv run python -m app.kb.dictionary build` và `report` chạy được; dán nội dung `T50_tom_tat.json`.
- Mọi hoạt chất của `data/mock/demo` và `data/mock/hoso_gia_lap` có trên trục. Đặc biệt: amoxicillin + clavulanic acid, sulfamethoxazole + trimethoprim, piperacillin + tazobactam, cefoperazone + sulbactam, insulin glargine, colistimethate, natri clorid nếu có.
- Tra thử trong báo cáo:
  - "Augmentin" nếu có trong Cục Quản lý Dược.
  - "Ceftriaxon 1 g": ra đúng chế phẩm và thành phần.
- `uv run ruff check .`, `uv run ruff format --check` (các tệp đã sửa), `uv run pytest -q --basetemp=.pytest_t50` đều qua; test cũ không đổi kỳ vọng.
- Báo cáo `plan/reports/T50.md`:
  - Có các mục "Lựa chọn đã làm", "Bảng chính tả Việt–quốc tế đã thêm", "Giới hạn còn lại".
  - Ghi dung lượng thư mục dữ liệu mới để Claude quyết định có đưa vào `.gitignore` không (task này không sửa `.gitignore`).

## Cấm làm

- Không commit / push. Không dùng `&`; lệnh dài chạy tuần tự trong phiên.
- Không gọi LLM.
- Không tải PDF.
- Không ghép mờ tự động.
- Không sửa dữ liệu ca.
- Không in khoá hay biến môi trường.
- Xoá `.pytest_t50*` khi xong.
