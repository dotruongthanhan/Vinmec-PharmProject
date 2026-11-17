# Báo cáo T14 – 17/11/2026

## Trạng thái

**CHƯA XONG nghiệm thu kết nối.** Đã viết lược đồ, CLI, ánh xạ, tài liệu và
kiểm thử; 26 test T14 đạt. `all --dry-run` đạt. `check` thoát mã 1 vì chuỗi
kết nối hiện tại không đúng định dạng PostgreSQL mà psycopg nhận; chưa lấy
được phiên bản PostgreSQL, extension hay trạng thái hai lược đồ.

Không chạy `schema`, `reset`, `load` hay `all` ghi vào cơ sở dữ liệu thật.
Không commit/push, không sửa `.env`, nguồn y khoa hoặc mã các task khác.
Người dùng tự chạy lượt nạp thật đầu tiên sau khi kiểm tra cấu hình kết nối.

## File của T14

- `db/schema.sql`, `db/README.md`, `db/bao-cao-T14.md`.
- `app/db/__init__.py`, `app/db/__main__.py`, `app/db/cli.py`,
  `app/db/engine.py`, `app/db/mapping.py`, `app/db/sources.py`.
- `tests/db/conftest.py`, `tests/db/test_cli.py`, `tests/db/test_loading.py`,
  `tests/db/test_mapping.py`.
- `pyproject.toml`, `uv.lock`: chỉ thêm `psycopg[binary]` bản 3 và metadata
  khóa tương ứng. `.env.example` đã có `DATABASE_URL`, không thay đổi.

## Môi trường kiểm tra

Python đang có là 3.13.9 trên Windows. Truy cập PyPI bị chặn và cache mặc
định của uv bị từ chối quyền, nên `uv add 'psycopg[binary]>=3,<4'` trực tuyến
không thành công. Đã thêm khai báo bằng `uv add --frozen`, dùng metadata
registry có sẵn để bổ sung lock, rồi chạy thành công
`uv add --offline --no-sync 'psycopg[binary]>=3,<4'` và
`uv lock --offline --check` (`Resolved 88 packages`). Không tải nguồn dữ liệu.

Các lệnh bên dưới chạy với `UV_CACHE_DIR=tests/db/.tmp/uv-cache` và
`UV_NO_SYNC=1`. Môi trường hiện dùng psycopg 3.3.6 triển khai Python, cài
offline từ wheel dựng lại từ archive psycopg chính thức đã có trong cache,
và libpq có sẵn. Cache chưa có wheel binary phù hợp CPython 3.13; **chưa xác
minh được `uv sync` cài binary trong môi trường này**. Trên môi trường có
quyền truy cập kho thư viện, chạy `uv sync` để cài đúng extra đã khai báo.
Thư mục `tests/db/.tmp` còn cache thư viện và tệp tạm kiểm thử. Bộ kiểm duyệt
tự động từ chối lệnh xóa đệ quy, cả khi dùng đường dẫn tuyệt đối đã kiểm tra,
với lý do `blocked by policy`; không tiếp tục thử xóa bằng cách khác.

## Các lệnh nghiệm thu

| Lệnh | Mã thoát | Kết quả |
| --- | --- | --- |
| `uv run ruff check app/db tests/db` | 0 | `All checks passed!` |
| `uv run ruff format --check app/db tests/db` | 0 | `11 files already formatted` |
| `uv run pytest -q tests/db -p no:cacheprovider` | 0 | `26 passed in 25.17s` |
| `uv run python -m app.db all --dry-run` | 0 | Toàn bộ đầu ra ở dưới |
| `uv run python -m app.db check` | 1 | `ProgrammingError`, đầu ra đã che ở dưới |

### Đầu ra `all --dry-run`

```text
Số dòng sẽ nạp (sau gộp khoá trùng):
tri_thuc.hoat_chat: 61
nghiep_vu.nguoi_benh: 6
nghiep_vu.dot_dieu_tri: 6
nghiep_vu.di_ung: 1
nghiep_vu.thuoc: 6
nghiep_vu.thuoc_hoat_chat: 7
nghiep_vu.chan_doan: 6
nghiep_vu.sinh_hieu: 13
nghiep_vu.ket_qua_xet_nghiem: 9
nghiep_vu.vi_sinh: 1
nghiep_vu.khang_sinh_do: 1
nghiep_vu.dien_bien: 6
nghiep_vu.y_lenh: 6
nghiep_vu.chi_tiet_y_lenh: 6
nghiep_vu.lich_dung: 13
nghiep_vu.lan_tham_dinh: 6
nghiep_vu.nhan_dinh: 5
nghiep_vu.nhan_dinh_thuoc: 5
nghiep_vu.can_cu: 0
nghiep_vu.phan_hoi: 0
tri_thuc.ten_thuoc: 187
tri_thuc.tai_lieu: 50
tri_thuc.doan_trich: 3738
tri_thuc.quy_tac_lieu_than: 4
tri_thuc.tuong_tac_sang_loc: 234981
tri_thuc.hoat_chat: đọc=62, sẽ nạp=61
tri_thuc.hoat_chat: đọc=62, sẽ nạp=61
tri_thuc.ten_thuoc: đọc=275, sẽ nạp=187
tri_thuc.tuong_tac_sang_loc: đọc=507655, sẽ nạp=234981
Embedding từ bộ đệm: có=134, chưa có=3604
DRY-RUN: không kết nối cơ sở dữ liệu.
```

Danh mục hoạt chất là dữ liệu chung của hai nhóm nên phần đọc/gộp được in
một lần cho mỗi nhóm; tổng nạp vẫn là 61 khóa duy nhất.

### Đầu ra `check`

```text
Loi co so du lieu; may chu=***; loai=ProgrammingError
```

Lệnh dùng `default_transaction_read_only=on` từ lúc mở kết nối. Lỗi định dạng
xảy ra trước khi truy vấn được gửi. Không ghi lại chuỗi kết nối hoặc nội dung
ngoại lệ trong báo cáo. Cần người dùng cung cấp chuỗi kết nối PostgreSQL trực
tiếp hợp lệ trong biến cấu hình hiện có rồi chạy lại `check`.

Trong một lượt thử ban đầu, lỗi mã hóa cp1252 làm hỏng cả thông báo lỗi đã
che, dẫn đến traceback chứa thông tin kết nối trong đầu ra công cụ. Đã sửa
điểm vào CLI để cấu hình UTF-8 và dùng thông báo lỗi kết nối ASCII; đã thêm
test tiến trình con với URL giả, kiểm tra không có mật khẩu, máy chủ hay
traceback ngay cả khi `PYTHONIOENCODING=cp1252`. Không chép thông tin kết nối
đó vào file của task.
Người dùng nên thay mật khẩu kết nối đã xuất hiện trong đầu ra công cụ trước
lượt nạp thật.

## Kiểm thử bổ sung và rà soát

26 test T14 kiểm tra đối chiếu hai chiều ánh xạ/SQL, RLS, số dòng và khóa
ngoại của 6 ca, thứ tự nạp, trường bắt buộc, ngưỡng loại 5%, reset thiếu
`--yes`, SQL tham số hóa, dry-run của từng nhóm, che lỗi kết nối, kết nối chỉ
đọc, gộp DDInter, bảo toàn dữ liệu KB, cache nhúng chỉ đọc và hoàn tác lỗi.
Các test giao dịch dùng kết nối giả; không mở cơ sở dữ liệu thật.

Rà soát độc lập phát hiện hai lỗi và đã có test tái hiện trước khi sửa:
dòng danh mục bị loại vẫn được dùng tạo tên gọi, và văn bản nhúng thay đổi
có thể giữ embedding cũ. Hai lỗi đã sửa; upsert chỉ giữ embedding khi
`noi_dung_nhung` không đổi, còn cache hỏng bị loại và ghi lý do theo ngưỡng.

Đã chạy thêm toàn bộ test dự án. Lượt đầu dùng thư mục tạm mặc định bị
Windows từ chối quyền: `2 failed, 559 passed, 1 warning, 100 errors`.
Lượt chạy lại:

```text
uv run pytest -q -p no:cacheprovider --tb=short --basetemp=tests/db/.tmp/full-suite
10 failed, 662 passed, 1 warning in 32.95s
```

Các lỗi nằm ngoài file được phép sửa của T14, ở trạng thái workspace có các
task khác đang thay đổi. Không kết luận nguyên nhân từ thay đổi T14 hay sửa
những file đó. Đầu ra lỗi chính:

```text
tests/api/test_routes.py::test_queue_order_fields_for_six_demo_cases
E   KeyError: 'ma_y_lenh'
tests/kb/test_names.py::test_hoat_chat_json_unique_and_covers_all_manifest_labels
E   AssertionError: Khong doc duoc danh sach manifest
tests/kb/test_openfda_source.py::test_load_real_meropenem_label
E   StopIteration
tests/orchestration/test_ask.py::test_ask_distinguishes_missing_clinical_evidence_from_scope
E   AssertionError: assert 'ngoai_pham_vi' == 'khong_co_nguon'
tests/orchestration/test_ask.py::test_ask_retries_entire_answer_once_with_specific_verification_error
  [True-unknown_id], [True-quote], [True-number]:
E   AssertionError: assert 'khong_co_nguon' == 'ok'
  [False-unknown_id], [False-quote], [False-number]:
E   AssertionError: assert 1 == 2
```

Không sửa hoặc chạy lại các test ngoài phạm vi để né lỗi.

## Chênh lệch ERD và lựa chọn theo nguồn

- ERD có `ngay_sinh`, `pid_hash`, thông tin đồng bộ OH/EMR; nguồn pydantic chỉ
  có `tuoi`, `gioi_tinh`, mã người bệnh nên giữ các trường có thật, không suy ra
  ngày sinh hay tạo thông tin đồng bộ. Trạng thái dị ứng được giữ dưới dạng
  JSONB ở người bệnh; cơ địa và mô tả ca nằm ở đợt điều trị.
- Xét nghiệm giữ `gia_tri_so`, `gia_tri_text`, `nguong_duoi`, `nguong_tren`;
  không dùng cột `gia_tri`/`khoang_tham_chieu` dạng chữ của ERD. Chi tiết y lệnh
  giữ `trang_thai_dong`, `so_lan_moi_ngay`, `khoang_cach_gio`, `ten_tu_do`,
  `loai_san_pham`; không tự tính `tong_lieu_ngay` hay suy ra thời điểm ngừng.
  Thuốc đang dùng có liên kết đợt điều trị và `y_lenh_id` rỗng khi nguồn không
  có mã y lệnh gốc. Lịch dùng và kháng sinh đồ là bảng con riêng.
- `thuoc` dùng trường pydantic, thành phần tách sang `thuoc_hoat_chat` với khóa
  kép; không tạo mã thuốc/thành phần giả. Các mã hoạt chất `HC-...` của ca và
  mã INN trong KB được giữ nguyên, không đoán gộp dựa trên tên gần giống.
- Đáp án vàng được đánh dấu bằng `tham_dinh_id` bắt đầu `dap_an:`; mỗi phần tử
  kỳ vọng thành `nhan_dinh`, liên kết dòng thuốc qua `nhan_dinh_thuoc`. Giữ
  `yeu_to`, `ket_luan`, `muc_do`, `mo_ta` theo pydantic thay các trường mã tự do
  của ERD. Không tạo thời điểm, quyết định dược sĩ hay kết quả AI giả. Nguồn
  không có căn cứ/phản hồi nên hai bảng tương ứng có 0 dòng. Trường căn cứ và
  phản hồi theo mô hình sẵn có trong `app/rules/types.py`, `app/feedback.py`.
- Tài liệu lấy giấy phép, phiên bản và SHA-256 từ manifest cục bộ; không tải
  nhãn từ mạng. Tên gọi lấy từ danh mục có sẵn. Mỗi mức liều thận giữ nguyên
  giới hạn, cờ biên và khuyến cáo; không sửa khe giữa các khoảng.
- Theo brief T14, DDInter giữ toàn bộ 234.981 cặp duy nhất sau gộp từ 507.655
  dòng, không áp dụng bước lọc chỉ lấy hoạt chất dự án trong plan 1.3. Giữ mã
  DDInter và tên gốc, không đoán mã hoạt chất nội bộ. Mức nguồn giữ nguyên;
  nếu lệch mức thì lưu toàn bộ mức nguồn, cờ lệch và mức cao nhất theo plan
  1.3. Mọi dòng ở trạng thái `sang_loc`, cần đối chiếu, không có cơ chế/xử trí
  do nguồn không cung cấp. Giấy phép đọc từ manifest, giữ mọi tệp góp nguồn.
- Cache nhúng dùng SHA-256 của `model + "\ndoc\n" + noi_dung_nhung`, đúng bộ
  đệm hiện có, chỉ đọc SQLite bằng `mode=ro`. Không gọi nhà cung cấp. `verify`
  báo thiếu embedding; mã thoát thành công khi số có/thiếu khớp cache hiện có,
  không yêu cầu cache đã phủ hết kho.
- Tạo hai schema ngay trước `CREATE EXTENSION IF NOT EXISTS vector WITH
  SCHEMA tri_thuc` ở đầu file, để cài mới không tạo đối tượng trong `public`.
  Nếu extension có sẵn ở schema khác thì giữ nguyên, chỉ tra namespace để
  tìm kiểu/operator class. Không tạo hoặc thay đổi đối tượng ngoài hai schema.
- Báo cáo đặt ở `db/` vì brief cho phép đường dẫn này và cấm sửa `plan/`.

## Việc chưa thực hiện

- Cài và kiểm chứng wheel `psycopg-binary` cho Python 3.13 bằng `uv sync`.
- Chạy `check` thành công với chuỗi kết nối PostgreSQL trực tiếp hợp lệ.
- Thực thi SQL và nghiệm thu số dòng trên Supabase thật: thuộc lượt chạy của
  người dùng; task này tuyệt đối không thực hiện lệnh ghi thật.
