# Nạp dữ liệu giả lập vào Supabase

Ứng dụng vẫn đọc JSON. Bộ lệnh này dùng PostgreSQL trực tiếp, chỉ quản lý
`nghiep_vu` và `tri_thuc`. Chuỗi kết nối đọc qua `database.url_env` trong cấu hình
sẵn có, mặc định là `DATABASE_URL` trong `.env`; không đưa giá trị vào log.

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
| `load cases [--dry-run] [--replace]` | 6 ca demo, danh mục thuốc và đáp án vàng |
| `load kb [--dry-run] [--replace]` | Hoạt chất, tên gọi, nhãn, đoạn trích và mức liều thận |
| `load ddinter [--dry-run] [--replace]` | 14 CSV, gộp cặp đảo chiều, COPY vào bảng tạm rồi upsert |
| `load embeddings [--dry-run] [--replace]` | Chỉ đọc SQLite, cập nhật véc-tơ đã có trong cache |
| `all [--dry-run] [--reset --yes]` | Schema → cases → kb → ddinter → embeddings → verify |
| `verify` | Đối chiếu mọi bảng, khoá ngoại và độ phủ véc-tơ; lệch trả mã 1 |

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

