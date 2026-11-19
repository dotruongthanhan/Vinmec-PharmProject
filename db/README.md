# Nạp dữ liệu giả lập vào Supabase

Ứng dụng mặc định đọc JSON. Bộ lệnh này dùng PostgreSQL trực tiếp, chỉ quản lý
`nghiep_vu` và `tri_thuc`. Chuỗi kết nối đọc qua `database.url_env` trong cấu hình
sẵn có, mặc định là `DATABASE_URL` trong `.env`; không đưa giá trị vào log.

## Nguồn đọc ca bệnh của API

Đặt `CASE_SOURCE=db` để API đọc Supabase qua `DATABASE_URL`; `CASE_SOURCE=file`
(mặc định) giữ 6 ca demo từ thư mục JSON hiện tại. Nguồn DB dựng 66 ca theo y
lệnh có `ca_id`, giữ đúng đợt điều trị và nạp lười. Yêu cầu đầu tiên sau khi
hết TTL làm mới danh sách. `CASE_CACHE_TTL_SECONDS` mặc định 60 và được giới
hạn trong 10–600 giây. Hành chính được đọc riêng cho từng yêu cầu.
Ba đường đọc nghiệp vụ dùng chung tối đa ba kết nối mỗi tiến trình, với giao
dịch chỉ đọc và giới hạn tám giây cho mỗi câu truy vấn trong giao dịch.
Thiếu cấu hình hoặc lỗi DB: health vẫn 200, API ca trả lỗi 503 thống nhất.

Kiểm nguồn DB với tệp, không ghi DB:

```bash
uv run python -m app.db.reader verify-read
```

Lệnh nằm trong `reader.py` để không sửa CLI nạp dữ liệu. Đối chiếu bỏ khác
biệt thứ tự, mã hoạt chất và biểu diễn múi giờ; danh mục chỉ giữ thuốc xuất
hiện và hoạt chất được tham chiếu, dùng metadata hoạt chất KB giống bộ nạp.
Không bỏ qua sai lệch số liệu lâm sàng, liều, đơn vị hay đường dùng. Chi tiết
các khác biệt nguồn và kết quả kiểm tại `plan/reports/T43.md`.

## Chạy lần đầu

```bash
uv sync
uv run python -m app.db check
uv run python -m app.db all --dry-run
# Người dùng tự chạy lệnh ghi sau khi xem kết quả dry-run:
uv run python -m app.db all
```

`check` chỉ đọc phiên bản PostgreSQL, phiên bản extension và sự tồn tại của hai
lược đồ. `verify` cũng dùng kết nối chỉ đọc. Mọi `--dry-run` đọc nguồn, kiểm kiểu,
in số dòng duy nhất sau gộp trùng và các dòng bị loại, không mở PostgreSQL.

| Lệnh sau `uv run python -m app.db` | Tác dụng |
| --- | --- |
| `schema` | Tạo đối tượng chưa có theo `db/schema.sql` |
| `reset --yes` | Xoá hai lược đồ bằng CASCADE rồi tạo lại |
| `load cases [--dry-run] [--replace]` | 6 ca demo + 60 hồ sơ nhiều lần vào viện, danh mục thuốc và đáp án vàng |
| `load kb [--dry-run] [--replace]` | Hoạt chất, tên gọi, nhãn, đoạn trích và mức liều thận |
| `load ddinter [--dry-run] [--replace]` | 14 CSV, gộp cặp đảo chiều, COPY vào bảng tạm rồi upsert |
| `load embeddings [--dry-run] [--replace]` | Chỉ đọc SQLite, cập nhật véc-tơ đã có trong cache |
| `all [--dry-run] [--reset --yes]` | Schema → cases → kb → ddinter → embeddings → verify |
| `verify` | Đối chiếu mọi bảng, view thuốc đang dùng, ca_id, khoá ngoại và độ phủ véc-tơ; lệch trả mã 1 |

## Nâng cấp từ DB cũ

Nếu DB còn lược đồ trước T40, phải chạy `uv run python -m app.db reset --yes`
để tạo lại lược đồ rồi chạy `uv run python -m app.db all` để nạp nguồn. Lệnh
reset xoá toàn bộ dữ liệu trong hai lược đồ `nghiep_vu` và `tri_thuc`. Chỉ
khối thêm cột T45 trong `db/schema.sql` có thể áp dụng lại an toàn cho bảng
đã có dữ liệu. `schema` không tự nâng cấp cấu trúc các bảng cũ.

## Quan hệ và thứ tự nạp

Người bệnh → lần vào viện (`dot_dieu_tri`) → y lệnh → dòng thuốc → lịch dùng.
Một hồ sơ có nhiều lần vào viện, mỗi lần có nhiều y lệnh. **Ca là y lệnh trọng
tâm**: chỉ y lệnh này có `ca_id` duy nhất (mã demo hoặc `ho_so_id`), kèm mô tả
ngắn. Đợt điều trị giữ bệnh sử, tiền sử, tóm tắt, lịch sử khoa và tuổi lúc vào
viện nếu nguồn có. Tuổi người bệnh vẫn lấy trực tiếp từ hồ sơ.

Đáp án vàng và phản hồi tham chiếu `y_lenh.ca_id`; cặp `(y_lenh_id, ca_id)` ở
lần thẩm định có khoá ngoại tổng hợp để không trỏ nhầm y lệnh. Chuỗi thay thế
y lệnh dùng khoá ngoại tự tham chiếu hoãn kiểm tới cuối giao dịch.

Thứ tự bảng trong `mapping.py`: hoạt chất → người bệnh → đợt → dị ứng → thuốc
→ thành phần thuốc → chẩn đoán → sinh hiệu → xét nghiệm → vi sinh → kháng sinh
đồ → diễn biến → y lệnh → dòng thuốc → lịch dùng → lần thẩm định → nhận định
→ thuốc của nhận định → căn cứ → phản hồi → tên thuốc → tài liệu → đoạn trích
→ mức liều thận → tương tác sàng lọc. Xoá nhóm theo thứ tự ngược lại.

Không lưu cờ thuốc đang dùng trên dòng thuốc. View `nghiep_vu.v_thuoc_dang_dung`
chọn dòng `active` của y lệnh `da_duyet` hoặc `dang_thuc_hien`. Với demo có
thuốc nền rời, bộ nạp tạo một y lệnh `YL-<ca_id>-NEN`, lấy thời điểm bắt đầu
sớm nhất của các dòng; không tạo nếu danh sách rỗng. View dùng quyền bên gọi,
không cấp quyền cho `PUBLIC`, `anon`, `authenticated`.

Mã `HC-...` được chuẩn hoá trước khi ghi hoạt chất, thành phần thuốc, dị ứng
và kháng sinh đồ; tên chuẩn đã có dùng thông tin từ KB. Mã ngoài KB được in
rõ, thêm từ danh mục hồ sơ với `can_duyet=true`. Thuốc trùng ID được gộp khi
tên, hàm lượng và thành phần giống nhau (sau chuẩn hoá mã hoạt chất); giữ các
thuộc tính còn lại của bản đầu. Nếu khác các trường này, giữ bản đầu và ghi
nguyên bản sau vào `data/runtime/nap_loi.jsonl`, không nạp thành phần của bản
bị loại. Không tự quy đổi đơn vị hoặc đồng nhất tên thuốc khác nhau.

## Nạp từ đầu một lệnh

Sau khi review nguồn và kết quả dry-run, người vận hành chỉ cần chạy:

```bash
uv run python -m app.db all --reset --yes
```

Lệnh kiểm nguồn trước khi kết nối, rồi xoá hai lược đồ, dựng lại từ
`db/schema.sql`, nạp `cases` → `kb` → `ddinter` → `embeddings`, cuối cùng chạy
`verify`. Không cần chạy riêng `schema` hay từng nhóm nạp. Mọi thay đổi cột
chỉ cần sửa `db/schema.sql` + `app/db/mapping.py` rồi chạy lại lệnh này;
nếu thay cấu trúc nguồn thì cập nhật thêm bộ đọc trong `sources.py`.

Tại thời điểm T40, nguồn có 9 bản thuốc xung đột trên 127 bản (vượt ngưỡng
5%), nên kiểm nguồn dừng trước kết nối. Chi tiết ở
[báo cáo T40](../plan/reports/T40.md); cần thống nhất danh mục nguồn trước khi nạp thật.

Mỗi nhóm `load` là một giao dịch; lỗi sẽ hoàn tác cả nhóm. `all` giữ ranh giới
giao dịch riêng cho từng nhóm. Upsert theo khoá chính không tạo dòng trùng;
`load kb` giữ embedding khi văn bản nhúng không đổi, xoá véc-tơ cũ khi văn bản
nhúng thay đổi. `--replace` xoá nhóm tương ứng trước khi nạp,
theo thứ tự bảng con trước bảng cha, không dùng CASCADE giữa các nhóm.
Riêng hoạt chất là danh mục dùng chung: `cases` và `kb` nạp cùng hợp danh mục
KB + danh mục ca; `cases --replace` không xoá hoạt chất, `kb --replace` chỉ xoá
các mã không còn trong hợp nguồn và cập nhật những mã còn lại. Nếu dữ liệu khác
đang tham chiếu mã bị xoá, khoá ngoại chặn và giao dịch hoàn tác.
`embeddings --replace` xoá véc-tơ cũ rồi điền từ cache, không xoá đoạn văn.

## Sửa ánh xạ rồi dựng lại

Sửa khối bảng trong `app/db/mapping.py`: `primary_key`, `columns`, `Column.source`
(một tên hoặc danh sách tên dự phòng), `annotation`, `transform`; sửa cột tương
ứng trong `db/schema.sql`. Các tên trường lấy từ mô hình pydantic nếu có.

Ví dụ tên hoạt chất có hai nguồn `ten_hoat_chat` và `ten_viet`, được khai báo
ngay tại cột `ten_hoat_chat`. Thứ tự khối bảng là thứ tự nạp theo khoá ngoại.
`nap_luc` và `tu_khoa` do PostgreSQL sinh; `embedding` được nạp riêng.

```bash
uv run ruff check app/db tests/db
uv run pytest -q tests/db -p no:cacheprovider
uv run python -m app.db all --dry-run
# Xoá toàn bộ dữ liệu hai lược đồ và dựng lại theo ánh xạ mới:
uv run python -m app.db all --reset --yes
```

`schema` không thay đổi bảng đã tồn tại. Khi thay cấu trúc cột, dùng reset để
dựng lại; `reset` hoặc `all --reset` thiếu `--yes` sẽ từ chối trước khi kết nối.
Không truyền tên lược đồ qua CLI. Hai lệnh reset xoá cả những bảng tự thêm
bên trong hai lược đồ này.

Dòng sai kiểu, thiếu trường bắt buộc hoặc thiếu cha bị loại và ghi lý do vào
`data/runtime/nap_loi.jsonl`. Trên 5% một bảng thì dừng trước khi kết nối.
Không tự điền số liệu lâm sàng. Tệp lỗi được ghi nối tiếp qua các lần chạy.

## Extension vector và quyền

Nếu `check` báo thiếu `vector`, người dùng bật extension **vector** trong
Supabase Dashboard → Database → Extensions, rồi chạy lại `check`. Tài khoản
dựng kho cần quyền tạo lược đồ/extension và quyền chủ sở hữu hoặc BYPASSRLS.
Mọi bảng bật RLS và không có policy nên khoá công khai không truy cập được.

`schema.sql` tạo hai lược đồ trước câu `CREATE EXTENSION` ở đầu file để cài mới
vector vào `tri_thuc`, tránh tạo đối tượng trong `public`. Nếu extension đã
được bật sẵn ở `extensions` hoặc lược đồ khác, giữ nguyên vị trí và tra đúng
namespace cho kiểu `halfvec`/operator class. Không cấp quyền hay sửa các lược đồ
Supabase. SQL chạy trong giao dịch. Cột embedding dùng `halfvec(2048)` với HNSW
cosine; cột `tu_khoa` sinh từ nguyên văn bằng cấu hình `simple`, có GIN.

Chênh lệch với ERD, lựa chọn theo nguồn và kết quả nghiệm thu thực tế nằm
trong [báo cáo T14](bao-cao-T14.md).

