# Cục Quản lý Dược (DAV) – công bố số đăng ký thuốc

Cập nhật: 19/11/2026. Người ghi: Codex, đọc dữ liệu cục bộ và mã trong `app/`; không gọi mạng.

| Mục | Giá trị |
|:--|:--|
| Trang gốc | https://dichvucong.dav.gov.vn/congbothuoc/index |
| API nguồn | `/api/services/app/soDangKy/GetAllPublicServerPaging` trên cùng máy chủ |
| Giấy phép | Manifest chỉ ghi “dữ liệu công bố của Cục Quản lý Dược – Bộ Y tế”. **Chưa có điều khoản cấp phép tái sử dụng cụ thể trong bản lưu**; không suy ra đây là giấy phép mở. |
| Tầng tin cậy | Nguồn cơ quan quản lý Việt Nam cho danh tính/số đăng ký; bản lưu không gán số tầng tin cậy lâm sàng. Không phải nguồn kết luận liều hoặc tương tác. |
| Cách lấy | GET trang công bố để nhận cookie, POST phân trang với `X-XSRF-TOKEN`; lưu nguyên phản hồi JSON dưới dạng gzip, kiểm tổng và ID trước khi xuất JSONL. |
| Ngày lấy | Manifest ghi `2026-11-18T17:09:57.216061+00:00` (giờ UTC). Đây là mốc lượt tải, không phải ngày kiểm tài liệu. |
| Lệnh tải/xử lý | `uv run python -m app.kb.fetch dav` → `uv run python -m app.kb.fetch rxnav` → `uv run python -m app.kb.dictionary build` → `uv run python -m app.kb.resolver build-index`. Đây là lệnh pipeline đã có; T59 chỉ kiểm đọc, không tải hay dựng lại. |

## 1. Đơn vị dữ liệu

Một phần tử `result.items[]` của tệp thô là một **bản ghi công bố có ID DAV**, không phải một hoạt chất. Một dòng `dav_thuoc.jsonl` là một **số đăng ký** sau gộp bản ghi trùng. Nguồn có 55.030 ID nhưng 54.910 số đăng ký; 120 số đăng ký xuất hiện ở nhiều ID. `_stage` chọn ID nhỏ nhất theo **thứ tự chuỗi**, giữ các ID xung đột trong manifest; bước dựng từ điển đưa các số đăng ký trùng vào diện chưa khớp.

Tên thuốc, chuỗi hoạt chất và hàm lượng gốc được giữ riêng. Tách được chuỗi thành phần chưa đồng nghĩa đã nối đủ hoạt chất trên trục; xem [từ điển và bộ tra](tu-dien-tra-cuu.md).

## 2. Ba tầng tệp

Kích thước là byte trên đĩa, đo ngày cập nhật; không làm tròn.

| Tầng | Đường dẫn | Kích thước | Vai trò |
|:--|:--|--:|:--|
| Thô | `data/kb_sources/dav/trang/*.json.gz` | 11.283.537 byte; 551 tệp | Phản hồi nguồn, có thể phân tích lại |
| Thô, siêu dữ liệu | `data/kb_sources/dav/manifest.json` | 88.396 byte | Tổng thô gồm cả manifest: 11.371.933 byte |
| Trung gian | `data/kb_staging/tu_dien/dav_thuoc.jsonl` | 26.678.340 byte; 54.910 dòng | Bản ghi theo số đăng ký, đầu vào dictionary |
| Đã chuẩn hóa, dùng chung nguồn | `data/kb_curated/tu_dien/thuoc.jsonl` | 28.730.413 byte | Danh mục chế phẩm sau bước dựng |
| Đã chuẩn hóa, dùng chung nguồn | `data/kb_curated/tu_dien/thuoc_thanh_phan.jsonl` | 20.015.686 byte | Quan hệ chế phẩm–hoạt chất đã khớp |
| Bộ tra runtime, dùng chung nguồn | `data/kb_curated/tra_cuu/tra_cuu.sqlite` | 11.005.952 byte | Bộ phân giải nạp vào bộ nhớ; không mở DAV thô khi thẩm định |

Các tệp chuẩn hóa còn lại và toàn bộ bảng/cột SQLite được mô tả tại [tu-dien-tra-cuu.md](tu-dien-tra-cuu.md); không cộng kích thước bộ tra dùng chung thành dung lượng riêng của DAV.

## 3. Trường của từng tệp

Quy ước: ✅ build là mã tải/phân tích/dựng có đọc hoặc chuyển trường; ✅ runtime là tiến trình thẩm định đọc giá trị đã đưa vào bộ tra. ❌ nghĩa là chưa tìm thấy xử lý trực tiếp ngoài việc lưu nguyên bản hoặc xuất mẫu kiểm. Việc giữ nguyên phản hồi không làm mọi trường trở thành dữ liệu được sử dụng.

### 3.1. Tệp thô `trang/<skipCount>.json.gz`

Bảng dưới liệt kê hợp các khóa của toàn bộ phản hồi. Dấu `[]` chỉ phần tử mảng. Các trường quản trị không có diễn giải trong mã được ghi chưa xác định, không dùng để suy ra hiệu lực thuốc.

<!-- RAW_FIELDS -->

### 3.2. `manifest.json`

| Trường | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `ngay_lay` | Mốc bắt đầu/lưu lượt lấy | ✅ build: ghi bởi `sources/dav.py`; ❌ runtime |
| `url` | Endpoint phân trang | ✅ build: thông tin truy nguyên; ❌ runtime |
| `than_yeu_cau` | Thân POST nền | ✅ build: `fetch_dav` dùng để chạy tiếp |
| `than_yeu_cau.filterText` | Bộ lọc chữ, hiện để rỗng | ✅ build: gửi trong POST |
| `than_yeu_cau.SoDangKyThuoc` | Đối tượng lọc số đăng ký, hiện rỗng | ✅ build: gửi trong POST |
| `than_yeu_cau.KichHoat` | Bộ lọc kích hoạt của API | ✅ build: gửi trong POST; không tự suy ra hiệu lực từng thuốc |
| `than_yeu_cau.sorting` | Tham số sắp xếp, hiện null | ✅ build: gửi trong POST |
| `than_yeu_cau.skipCount` | Vị trí đầu trang | ✅ build: thay theo trang |
| `than_yeu_cau.maxResultCount` | Kích thước trang | ✅ build: kiểm số mục trả về |
| `header_toi_thieu` | Tên header/cookie cần cho yêu cầu; không chứa token thật | ❌ runtime; siêu dữ liệu tải |
| `giay_phep` | Ghi chú xuất xứ, chưa là điều khoản cấp phép | ❌ runtime |
| `thu_kich_thuoc_trang` | Nhật ký thử giảm kích thước trang; hiện mảng rỗng | ✅ build: checkpoint khi nguồn từ chối/cắt trang |
| `totalCount` | Tổng nguồn khai báo | ✅ build: điều kiện xuất tầng trung gian; `dictionary/report.py` |
| `tep` | Ánh xạ vị trí trang sang tệp và mã băm | ✅ build: tiếp tục lượt tải |
| `tep.<skip>.duong_dan` | Đường dẫn gzip tương đối | ✅ build: nạp trang đã có |
| `tep.<skip>.sha256` | SHA-256 **byte gzip** | ✅ build: xác nhận trang cache, không phải băm JSON giải nén |
| `trang_thai` | Trạng thái lượt tải; hiện `xong` | ✅ build: `dictionary/axis.py:Inputs` chỉ nhận tầng trung gian khi xong |
| `so_trang` | Số trang được ghi nhận | ✅ build: checkpoint/kiểm |
| `so_id_duy_nhat` | Số ID DAV không trùng | ✅ build: kiểm đủ lượt tải |
| `so_ban_ghi_thieu_id` | Số bản ghi thiếu ID | ✅ build: không cho xuất khi thiếu |
| `thoi_gian_giay` | Thời gian lượt chạy | ❌ runtime; nhật ký |
| `so_dang_ky_duy_nhat` | Số dòng sau gộp SĐK | ❌ runtime; kiểm tải |
| `id_thieu_so_dang_ky` | ID nguồn thiếu SĐK | ✅ build: tạo dòng chờ duyệt trong `dictionary/build.py` |
| `so_dang_ky_trung` | SĐK → danh sách ID trùng | ✅ build: `Inputs._read_dav` chặn tách và giữ neo nguồn |

`thu_kich_thuoc_trang` đang rỗng nên không có khóa con thực đo. Mã hỗ trợ nhật ký `kich_thuoc`, `http`, `so_muc`; đây là cấu trúc dự kiến của mã, không phải bản ghi đã có.

### 3.3. `dav_thuoc.jsonl`

| Trường | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `so_dang_ky` | SĐK, khóa gộp bản ghi | ✅ build: chặn SĐK trùng, tạo `thuoc_id`; đưa vào SQLite nhưng ❌ resolver runtime không đọc cột SĐK |
| `ten_thuoc` | Tên chế phẩm nguyên nguồn | ✅ build: ngữ cảnh tách, tạo khóa tên runtime |
| `hoat_chat_goc` | Chuỗi hoạt chất từ `thongTinThuocCoBan.hoatChatChinh` | ✅ build: `split_components`; có 2 dòng null |
| `ham_luong_goc` | Chuỗi hàm lượng, chưa phải số đã tách | ✅ build: `split_components`; có 6.544 dòng null |
| `dang_bao_che` | Dạng bào chế nguyên nguồn | ✅ build: chuyển sang danh mục/SQLite; ❌ resolver runtime không đọc cột này |
| `dong_goi` | Quy cách đóng gói | ❌ ngoài lưu trung gian và mẫu kiểm |
| `duong_dung_goc` | Đường dùng nguyên nguồn | ✅ build: chép sang `thuoc.jsonl`; ❌ runtime, toàn bộ 54.910 dòng đang null |
| `con_hieu_luc` | Cờ tính từ `isActive` và `isHetHan`; thiếu chứng cứ thì null theo mã | ✅ build: chép sang `thuoc.jsonl`; ❌ resolver runtime không lọc theo cờ này |
| `url_hdsd` | URL HDSD hoặc tài liệu nhãn+HDSD dự phòng | ✅ build: chép sang `thuoc.jsonl`; ❌ runtime, không tải nội dung ở đường này |
| `url_nhan` | URL nhãn hoặc nhãn+HDSD dự phòng | ❌ ngoài lưu trung gian và mẫu kiểm |
| `dav_id` | ID DAV dưới dạng chuỗi | ✅ build: neo `dav:<id>`, khóa quyết định theo chế phẩm |
| `ngay_het_han` | Ngày hết hạn SĐK nguyên nguồn | ❌ ngoài lưu trung gian và mẫu kiểm; không tính hiệu lực từ ngày này |

## 4. Bộ tra

DAV không có SQLite riêng. Bảng `thuoc` và `thuoc_thanh_phan` trong bộ tra dùng chung giữ khóa tên chế phẩm và thành phần; danh tính hoạt chất có thêm bằng chứng [RxNav](rxnav.md), kho cũ và DDInter. Xem [toàn bộ PRAGMA/cột/số dòng](tu-dien-tra-cuu.md#4-bo-tra-tra_cuusqlite). Có chế phẩm trong `thuoc` chưa có công thức trong `thuoc_thanh_phan`; sự hiện diện của SĐK không chứng minh bộ phân giải đã có đủ thành phần.

## 5. Kết quả kiểm đã có

- Kiểm đọc T59: 551 trang, 55.030 bản ghi và 55.030 ID duy nhất; số đăng ký duy nhất 54.910; 120 số đăng ký trùng. Mã băm tất cả trang khớp manifest: 0 lệch.
- Manifest ghi lượt tải `xong`, 0 bản ghi thiếu ID, danh sách thiếu SĐK rỗng. Kiểm đếm trực tiếp đồng nhất với manifest.
- `plan/reports/T50.md`, phần T50-fix-1, ghi đã kiểm phản hồi thật và sửa bộ tách theo nguồn. `T50_tom_tat.json` là mốc T50, còn kết quả sau các sửa T52 nằm ở `T52_do_phu_truoc_sau.json`; không dùng số mốc cũ làm số hiện tại.
- README nguồn ngày 16–17/11 chưa liệt kê DAV. Không còn đúng nếu coi danh sách “đã có” trong README đó là danh mục đầy đủ.

## 6. Việc còn mở

- Bổ sung điều khoản tái sử dụng DAV vào hồ sơ nguồn; ghi chú xuất xứ trong manifest chưa đủ để xác định giấy phép.
- Đường dùng đang thiếu hoàn toàn trong trung gian. Không lấy dạng bào chế hoặc tên thuốc để tự điền.
- SĐK trùng, chuỗi “tương đương”, dược liệu và hàm lượng mơ hồ còn cần duyệt theo hàng chờ; không ghép gần đúng tự động.
- URL tài liệu mới là đường dẫn nguồn; chưa chứng minh đã lấy được HDSD/nhãn Việt Nam.
- Bộ tra hiện chưa dùng hiệu lực SĐK để loại thuốc khi phân giải tên.

## Cách kiểm lại

Chạy từ gốc dự án, bằng Python có sẵn. Lệnh dưới đã chạy trong T59, exit 0; chỉ đọc tệp và không gọi mạng.

```powershell
@'
import sys, json, gzip, hashlib
from pathlib import Path
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')
root = Path('data/kb_sources/dav')
m = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
files = list((root / 'trang').iterdir())
items = [r for p in files for r in json.loads(gzip.decompress(p.read_bytes()))['result']['items']]
print('manifest_bytes', (root / 'manifest.json').stat().st_size)
print('pages', len(files), 'page_bytes', sum(p.stat().st_size for p in files))
print('raw_total_bytes', (root / 'manifest.json').stat().st_size + sum(p.stat().st_size for p in files))
print('raw_items', len(items), 'unique_ids', len({r['id'] for r in items}))
regs = Counter(r.get('soDangKy') for r in items)
print('unique_registrations', len(regs), 'duplicate_registrations', sum(v > 1 for v in regs.values()))
print('manifest', json.dumps({k: v for k, v in m.items() if k != 'tep' and k != 'so_dang_ky_trung'}, ensure_ascii=False))
print('bad_page_hashes', sum(hashlib.sha256((root / r['duong_dan']).read_bytes()).hexdigest() != r['sha256'] for r in m['tep'].values()))
p = Path('data/kb_staging/tu_dien/dav_thuoc.jsonl')
rows = [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s.strip()]
print('staging_rows', len(rows), 'staging_bytes', p.stat().st_size, 'keys', sorted({k for r in rows for k in r}))
print('staging_nulls', {k: sum(r.get(k) is None for r in rows) for k in rows[0]})
for p in [*sorted(Path('data/kb_curated/tu_dien').glob('*.jsonl')), Path('data/kb_curated/tra_cuu/tra_cuu.sqlite')]:
    print('derived_bytes', p.as_posix(), p.stat().st_size)
'@ | .venv/Scripts/python.exe -
```

Đối chiếu nơi dùng bằng tìm kiếm đã chạy:

```powershell
rg -n 'dav|rxnav|tra_cuu.sqlite|hoat_chat.jsonl|dong_nghia.jsonl|thuoc_thanh_phan.jsonl|anh_xa.jsonl|cho_duyet.jsonl' app
```

