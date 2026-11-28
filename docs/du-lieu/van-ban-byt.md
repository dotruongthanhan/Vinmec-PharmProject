# Văn bản Bộ Y tế – VBHN 15, TT 37, QĐ 5631

Cập nhật: 19/11/2026. Đọc trực tiếp manifest, đo tệp tại chỗ và đọc lớp chữ PDF bằng `pdftotext`; không gọi mạng.

| Mục | Giá trị |
|:--|:--|
| Nguồn | VBHN 15/VBHN-BYT và TT 37/2024/TT-BYT: Cổng Thông tin điện tử Chính phủ (`vanban.chinhphu.vn`, tệp ở `datafiles.chinhphu.vn`). QĐ 5631/QĐ-BYT: bản sao trên `files01.duytan.edu.vn`, không phải máy chủ cơ quan nhà nước. URL từng tệp nằm trong manifest tương ứng |
| Giấy phép | Manifest VBHN 15 ghi văn bản quy phạm pháp luật công khai và viện dẫn Điều 15 Luật Sở hữu trí tuệ; manifest TT 37 ghi văn bản quy phạm pháp luật công khai; manifest QĐ 5631 ghi văn bản Bộ Y tế công khai. Đây là thông tin nguồn đã ghi, chưa phải kết quả thẩm định pháp lý hoặc xác minh quyền của bản sao thứ cấp |
| Tầng tin cậy | `tang_tin_cay = 1` trong manifest VBHN 15 và TT 37; QĐ 5631 lưu chuỗi `1 (nội dung); bản sao thứ cấp`. Tầng của nội dung và xuất xứ bản sao cần được phân biệt. Tiêu đề báo cáo T54 nói “tầng 0”, nhưng giá trị thực trong manifest là như trên |
| Cách lấy | T54 tải trực tiếp PDF công khai, không đăng nhập, không vượt CAPTCHA; lưu riêng manifest cho mỗi gói văn bản. User-Agent ghi trong nguồn: `VinmecPharmProject-kb/1.0` |
| Ngày lấy | `2026-11-19` trong cả ba manifest |
| Lệnh tải và xử lý | Không có nguyên lệnh tải BYT được lưu trong manifest hoặc báo cáo T54; không suy dựng lệnh lịch sử. Chưa có bước OCR/tách bảng/ingest BYT trong `app/`. Lệnh đo và kiểm ngoại tuyến đã chạy được chép đầy đủ ở mục “Cách kiểm lại” |
| Mục đích dự kiến | Theo danh mục dữ liệu: yếu tố 2, 3, 7. Hiện mới lưu nguồn, chưa tạo quy tắc lâm sàng hoặc căn cứ RAG từ các PDF này |

## 1. Đơn vị dữ liệu

Mỗi thư mục con là **một gói văn bản**, có một đối tượng JSON trong `manifest.json`. Mỗi phần tử `cac_tep[]` mô tả một PDF tải về. Gói TT 37 gồm tệp chính và tệp kèm; không coi mỗi PDF là một thuốc hay một quy tắc.

PDF là văn bản theo trang, có điều khoản, phụ lục, bảng hoặc biểu mẫu. Chưa có JSONL/CSV thuốc, điều kiện thanh toán hay danh mục kháng sinh được tách từ các tài liệu này. Vì vậy không có khái niệm “một dòng lâm sàng” hoặc schema trường lâm sàng đã chuẩn hóa.

## 2. Ba tầng tệp

Kích thước dưới đây là số byte đo trực tiếp ngày 19/11/2026, gồm cả manifest nếu ghi theo thư mục.

| Tầng | Đường dẫn | Số tệp / kích thước | Giữ lâu dài? |
|:--|:--|--:|:--|
| Thô | `data/kb_sources/van_ban_byt/` | 7 tệp: 4 PDF, 3 JSON; **30.306.957 byte** | Có: giữ nguyên PDF và manifest để đối chiếu |
| Trung gian | Chưa có tệp BYT được nhận diện trong `data/kb_staging/` | Chưa tạo; chưa có kích thước tầng BYT | Chưa áp dụng |
| Bộ tra / đoạn app đọc | Chưa có tệp BYT được nhận diện trong `data/kb_curated/`; `chunks.jsonl` hiện có **0 đoạn** với `nguon` là `byt` hoặc `van_ban_byt` | Chưa ingest BYT; chưa có kích thước bộ tra BYT | Chưa áp dụng |

Chi tiết tầng thô:

| Thư mục / tệp (tương đối dưới `data/kb_sources/van_ban_byt/`) | Số tệp | Byte | Trang PDF |
|:--|--:|--:|--:|
| `vbhn15_2024/` | 2 | 20.446.391 | — |
| `vbhn15_2024/15-vbhn-byt.pdf` | 1 | 20.445.232 | 75 |
| `vbhn15_2024/manifest.json` | 1 | 1.159 | — |
| `tt37_2024/` | 3 | 8.194.462 | — |
| `tt37_2024/37-byt.pdf` | 1 | 8.066.604 | 21 |
| `tt37_2024/37-byt-kem.pdf` | 1 | 126.433 | 4 |
| `tt37_2024/manifest.json` | 1 | 1.425 | — |
| `qd5631_2020/` | 2 | 1.666.104 | — |
| `qd5631_2020/qd5631_duytan.pdf` | 1 | 1.664.757 | 30 |
| `qd5631_2020/manifest.json` | 1 | 1.347 | — |

Số trang được đếm từ dấu ngắt trang của `pdftotext`, không phải đếm dòng văn bản. Quét tên đường dẫn trong hai tầng sau không tìm thấy `van_ban_byt`, `vbhn15`, `tt37`, `qd5631`; kết hợp với kiểm nguồn từng dòng `chunks.jsonl` và tìm mã nguồn app để xác định trạng thái chưa ingest.

## 3. Trường của từng tệp

### 3.1. Ba tệp `manifest.json`

Ba manifest có cùng bộ khóa, dù thứ tự khác nhau. Đối tượng gốc dùng các trường sau. Cột “App dùng?” nói về **giá trị trong ba manifest BYT này**, không phải những trường cùng tên của nguồn khác.

| Trường | Kiểu hiện có | Ý nghĩa | App dùng? / dùng ở đâu |
|:--|:--|:--|:--|
| `ma` | chuỗi | Mã gói: `vbhn15_2024`, `tt37_2024`, `qd5631_2020` | ❌ Chưa có bộ đọc manifest BYT trong `app/` |
| `ten` | chuỗi | Tên, số hiệu và ngày văn bản mà người tải ghi nhận | ❌ Chỉ siêu dữ liệu nguồn |
| `nguon` | chuỗi | Cơ quan/trang cung cấp; QĐ 5631 ghi rõ bản sao Duy Tân | ❌ Chưa chuyển thành nguồn trích dẫn của app |
| `tang_tin_cay` | số nguyên hoặc chuỗi | Phân tầng nội dung; QĐ 5631 còn kèm hạn chế bản sao thứ cấp | ❌ Chưa chuẩn hóa/nạp vào `Chunk` |
| `giay_phep` | chuỗi | Ghi nhận về tính công khai và giấy phép ở thời điểm tải | ❌ Chưa có xử lý giấy phép BYT trong app |
| `day_du_phu_luc` | chuỗi | Ghi chú phạm vi phụ lục và chất lượng lớp chữ | ❌ Ghi nhận thủ công; chưa tách bảng |
| `co_chu_ky` | chuỗi | Nhận xét của người tải về số/ngày, dấu/chữ ký; **có mâu thuẫn cần kiểm lại** ở mục 5 | ❌ Không phải trường boolean hay kết quả xác minh chữ ký số |
| `ngay_lay` | chuỗi ngày | Ngày tải gói nguồn | ❌ Chưa nạp làm siêu dữ liệu căn cứ |
| `user_agent` | chuỗi | User-Agent dùng khi tải | ❌ Chỉ truy vết việc lấy nguồn |
| `cac_tep` | mảng đối tượng | Danh sách PDF: VBHN 15 có 1, TT 37 có 2, QĐ 5631 có 1 phần tử | ❌ Chưa có vòng nạp BYT trong app |

Mỗi phần tử `cac_tep[]` có đầy đủ các trường sau:

| Trường | Kiểu hiện có | Ý nghĩa | App dùng? / dùng ở đâu |
|:--|:--|:--|:--|
| `tep` | chuỗi | Tên PDF tương đối dưới thư mục chứa manifest | ❌ Chưa được app mở |
| `url_tai_truc_tiep` | chuỗi | URL đã dùng để tải PDF | ❌ Chưa trở thành URL căn cứ trong app |
| `trang_chua_lien_ket` | chuỗi | Trang công bố liên kết; QĐ 5631 ghi mô tả tìm kiếm thay vì URL ổn định | ❌ Chỉ truy vết nguồn |
| `sha256` | chuỗi | Mã băm nội dung PDF | ❌ App chưa kiểm manifest BYT; đã đối chiếu bằng lệnh ngoại tuyến ở mục 7 |
| `dung_luong_byte` | số nguyên | Dung lượng PDF lúc tải | ❌ App chưa dùng; đã so với `stat().st_size` ở mục 7 |
| `ghi_chu` | chuỗi | Số trang, loại PDF, giới hạn hoặc đối chiếu bản khác | ❌ Ghi chú nguồn, chưa phải dữ liệu lâm sàng |

### 3.2. Các PDF

PDF không có bộ trường JSON/CSV của dự án. Bảng dưới mô tả nội dung vật lý cần phân biệt, không đặt schema lâm sàng mới.

| Tệp | Nội dung / cấu trúc hiện có | App dùng? / dùng ở đâu |
|:--|:--|:--|
| `vbhn15_2024/15-vbhn-byt.pdf` | VBHN về danh mục và tỷ lệ, điều kiện thanh toán thuốc; bản quét có lớp chữ. T54 ghi có Phụ lục I, II, III và cảnh báo OCR/cột bảng kém. Chưa trích danh mục thành bản ghi có cấu trúc | ❌ Chưa có parser, đoạn trích hay quy tắc sinh từ PDF |
| `tt37_2024/37-byt.pdf` | Văn bản thông tư; lớp chữ trích được số hiệu và ngày trên trang đầu. Cần phân biệt tệp này với tệp mẫu kèm và với danh mục thuốc đã tách bảng | ❌ Chưa nạp vào kho đoạn |
| `tt37_2024/37-byt-kem.pdf` | Phụ lục biểu mẫu thống kê; trang đầu có mẫu về dịch vụ kỹ thuật sử dụng thuốc phóng xạ/chất đánh dấu, dòng dẫn thông tư còn chỗ trống. Không phải bảng thuốc đã chuẩn hóa | ❌ Chưa xử lý biểu mẫu |
| `qd5631_2020/qd5631_duytan.pdf` | Hướng dẫn quản lý sử dụng kháng sinh trong bệnh viện; T54 ghi đủ các phụ lục và danh mục kháng sinh ưu tiên quản lý. Lớp chữ trích được nhưng có ký tự tiếng Việt bất thường | ❌ Chưa tách danh mục hay chuyển thành luật thẩm định |

### 3.3. App đã có tên nguồn nhưng chưa đọc bộ PDF này

| Nơi dùng | Trạng thái | Ý nghĩa |
|:--|:--|:--|
| `app/config/settings.py:123`, `config/settings.yaml` | ✅ Tên cấu hình `retrieval.van_ban_byt` có tồn tại | Đây là cấu hình nhóm truy xuất; không chứng minh đã có dữ liệu BYT |
| `app/api/presenter.py:25`, `app/orchestration/ask.py:71` | ✅ Bảng ánh xạ `byt` / `van_ban_byt` sang nhãn tiếng Việt | Chỉ đặt tên hiển thị nếu gặp nguồn đó |
| `app/retrieval/setup.py`, `app/retrieval/corpus.py` | ❌ Không mở PDF hay manifest BYT | Nạp kho chung `data/kb_curated/chunks.jsonl`; kho tại chỗ chưa có đoạn BYT |
| `app/kb/build.py` | ❌ Không dựng dữ liệu BYT | Pipeline hiện tại dành cho nhãn openFDA; không áp dụng trực tiếp lệnh dựng này cho ba manifest BYT |

## 4. Bộ tra

Chưa có SQLite, CSV hoặc JSONL BYT đã chuẩn hóa để liệt kê bảng/cột/số dòng. Không coi phần bảng nằm trong PDF là bảng cơ sở dữ liệu. Không có đoạn `byt` / `van_ban_byt` trong kho RAG tại thời điểm kiểm.

Các đường dẫn tầng trung gian và bộ tra cho BYT cũng chưa được thiết lập trong phần mã app đã tìm. Không ghi đường dẫn dự kiến thành đường dẫn đang có.

## 5. Kết quả kiểm đã có

**Kiểm hiện tại ngày 19/11/2026:**

- Tất cả PDF kê trong ba manifest tồn tại; SHA-256 và `dung_luong_byte` đều khớp byte thực tế. Bốn tệp đều đọc được lớp chữ bằng `pdftotext`; điều này không xác nhận độ đúng OCR hay tính toàn vẹn bảng.
- Số trang đo hiện tại khớp ghi chú số trang trong từng manifest. Không chạy lại tải nguồn, OCR hoặc build.
- `data/kb_sources/manifest.json` ở gốc có **0 mục** khớp mã/đường dẫn của gói BYT. Nguồn này hiện được mô tả bằng manifest riêng từng thư mục, khác phát biểu tổng quát trong README nguồn cũ rằng mọi tệp có dòng ở manifest gốc.
- Kho `data/kb_curated/chunks.jsonl` có nguồn `openfda`, không có nguồn `byt` hoặc `van_ban_byt`. Những tên nguồn đã khai báo trong app chưa có nghĩa bộ PDF này đang được dùng khi thẩm định.

**Lịch sử T54:** [báo cáo tải nguồn](../../plan/reports/T54-tai-nguon-van-ban.md) ghi nhận VBHN 15 đã lấy, TT 37 lấy một phần, QĐ 5631 là bản sao thứ cấp; TT 20/2022 bản gốc và QĐ 5948 chưa lấy được. Hạn chế OCR VBHN và nhu cầu chuẩn hóa chữ QĐ 5631 vẫn cần được giải quyết trước khi trích bảng. Không có nghiệm thu bộ tra BYT trong các báo cáo T25, T50–T56 hoặc báo cáo dữ liệu đã tìm theo mã nguồn BYT.

**Mâu thuẫn cần lưu ý:** manifest TT 37 và QĐ 5631, cùng T54, nói số/ngày để trống. Trong byte PDF hiện có (đã khớp SHA-256 manifest), `pdftotext` trích được `37 /2024/TT-BYT`, ngày `16`, tháng `11`, năm `2024` ở tệp chính TT 37; và `5631 /QĐ-BYT`, ngày `31`, tháng `12`, năm `2020` ở QĐ 5631. Tệp mẫu `37-byt-kem.pdf` vẫn có dòng số/ngày thông tư để trống. Do vậy không lặp lại kết luận thiếu số/ngày cho toàn bộ gói. Chưa kiểm trực quan hoặc xác minh chữ ký số, nên cũng không kết luận đây là bản ký hợp lệ. Không sửa manifest trong task tài liệu này.

README cũ `data/kb_sources/README.md` ngày 16–17/11 không liệt kê các gói BYT lấy ngày 19/11. Thông tin cũ về QĐ 5948 chưa có nguồn chính thức vẫn phù hợp với T54; còn mô tả có thể dựng mọi nguồn bằng `app.kb.build` không áp dụng cho các PDF BYT hiện tại.

## 6. Việc còn mở

- Đối chiếu bản gốc và hình ảnh số/ngày, dấu/chữ ký của TT 37 và QĐ 5631; làm rõ mâu thuẫn `co_chu_ky` trước khi cập nhật siêu dữ liệu hoặc sử dụng làm căn cứ.
- Xin bản chính thức phù hợp của TT 20/2022 và QĐ 5948; kiểm lại tính đầy đủ của tệp TT 37. Bản sao QĐ 5631 cần được đối chiếu với nguồn cơ quan có thẩm quyền.
- OCR/tách bảng VBHN 15 có kiểm soát; xử lý cột, ô gộp, ký hiệu và ghi chú, rồi dược sĩ duyệt. Đếm trang hoặc có lớp chữ không thay cho kiểm bảng.
- Chưa có schema trích bảng, tầng trung gian, bộ tra, đoạn RAG hay quy tắc BYT được nghiệm thu. Các bước này thuộc việc sau; không tự tạo trường hoặc suy diễn nội dung y khoa trong tài liệu này.
- Lệnh tải nguyên gốc không được lưu đầy đủ; lần tải sau cần ghi lệnh và cập nhật tài liệu nguồn cùng lúc.

## 7. Cách kiểm lại

Chạy từ thư mục gốc dự án. Lệnh dưới đây **đã chạy, exit 0**, sinh toàn bộ số tệp, kích thước byte, số phần tử manifest, số trang, số đoạn BYT và số mục manifest gốc nêu trên. Chỉ đọc; dùng Python trong môi trường sẵn có và `pdftotext.exe` đi kèm Git. Không cài thư viện. Số trang được đếm sau khi bỏ phần rỗng cuối do dấu ngắt trang cuối tệp.

```powershell
@'
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
root = Path('data/kb_sources/van_ban_byt')
files = sorted(p for p in root.rglob('*') if p.is_file())
print(json.dumps({'root': str(root), 'files': len(files), 'bytes': sum(p.stat().st_size for p in files), 'by_suffix': dict(Counter(p.suffix for p in files))}))
for folder in sorted(p for p in root.iterdir() if p.is_dir()):
    members = sorted(p for p in folder.rglob('*') if p.is_file())
    print(json.dumps({'folder': str(folder), 'files': len(members), 'bytes': sum(p.stat().st_size for p in members)}))
for path in files:
    item = {'path': str(path), 'bytes': path.stat().st_size}
    if path.suffix == '.json':
        manifest = json.loads(path.read_text(encoding='utf-8-sig'))
        item.update({'keys': list(manifest), 'cac_tep': len(manifest['cac_tep']), 'entry_keys': sorted({key for entry in manifest['cac_tep'] for key in entry}), 'hash_matches': all(hashlib.sha256((path.parent / entry['tep']).read_bytes()).hexdigest() == entry['sha256'] for entry in manifest['cac_tep']), 'size_matches': all((path.parent / entry['tep']).stat().st_size == entry['dung_luong_byte'] for entry in manifest['cac_tep'])})
    else:
        result = subprocess.run(['C:/Program Files/Git/mingw64/bin/pdftotext.exe', '-layout', '-enc', 'UTF-8', str(path), '-'], capture_output=True, check=True)
        pages = result.stdout.decode('utf-8').split('\f')
        if pages and not pages[-1].strip():
            pages.pop()
        item.update({'pages': len(pages), 'first_page_heading': ' '.join(pages[0].split())[:220]})
    print(json.dumps(item, ensure_ascii=True))
for root_name in ('data/kb_staging', 'data/kb_curated'):
    base = Path(root_name)
    matches = sorted(str(p) for p in base.rglob('*') if any(term in str(p).lower() for term in ('van_ban_byt', 'vbhn15', 'tt37', 'qd5631')))
    print(json.dumps({'root': root_name, 'matching_paths': matches}))
counts = Counter()
for line in Path('data/kb_curated/chunks.jsonl').read_text(encoding='utf-8-sig').splitlines():
    if line.strip():
        counts[str(json.loads(line).get('nguon'))] += 1
print(json.dumps({'chunks_sources': dict(sorted(counts.items())), 'byt_rows': sum(n for source, n in counts.items() if source in ('byt', 'van_ban_byt'))}))
manifest = json.loads(Path('data/kb_sources/manifest.json').read_text(encoding='utf-8-sig'))
entries = manifest if isinstance(manifest, list) else [row for value in manifest.values() if isinstance(value, list) for row in value]
matches = [row for row in entries if isinstance(row, dict) and any(term in json.dumps(row, ensure_ascii=False).lower() for term in ('van_ban_byt', 'vbhn15', 'tt37', 'qd5631'))]
print(json.dumps({'root_manifest_matches': len(matches)}))
'@ | .venv/Scripts/python.exe -B -
```

Môi trường hiện tại không có `pypdf` trong `.venv` (`ModuleNotFoundError` ở lần thử đầu); không cài thêm. Các kết quả PDF nêu trên lấy từ lệnh `pdftotext` đã chạy thành công, không lấy từ lần thử lỗi.
