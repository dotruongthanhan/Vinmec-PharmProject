# RxNav / RxClass – RxNorm và nhóm ATC

Cập nhật: 19/11/2026. Người ghi: Codex, kiểm tệp cục bộ và mã `app/`; không gọi mạng.

| Mục | Giá trị |
|:--|:--|
| Nguồn | NLM RxNav, `https://rxnav.nlm.nih.gov/REST/`; RxClass `rxclass/class/byRxcui.json` với `relaSource=ATC` |
| Giấy phép | **Chưa xác định từ bản lưu cục bộ.** Hai manifest không có trường giấy phép/điều khoản tái sử dụng. Không suy ra toàn bộ RxNorm, các trường nguồn và ATC cùng một giấy phép. |
| Tầng tin cậy | Danh pháp và mã định danh/nhóm thuốc; manifest không gán số tầng tin cậy lâm sàng. Nguồn này không cung cấp kết luận điều trị trong pipeline hiện hành. |
| Cách lấy | Tra chính xác tên, xác minh IN/PIN và quan hệ, tra ATC, lưu từng phản hồi JSON theo SHA-256 của URL truy vấn. Gợi ý gần đúng chỉ đưa vào hàng chờ. Danh mục IN/PIN được tải riêng. |
| Ngày lấy | Manifest đệm: `2026-11-18T18:18:52.203992+00:00`. Manifest danh mục: `2026-11-19T02:31:55+07:00`. Mốc đệm là mốc lượt chạy, không phải ngày riêng của từng tệp. |
| Lệnh | `uv run python -m app.kb.fetch rxnav` → `uv run python -m app.kb.dictionary build` → `uv run python -m app.kb.resolver build-index`. Danh mục ghi URL `allconcepts.json?tty=IN+PIN`, không lưu nguyên lệnh tải; **lệnh tải danh mục chưa xác định**. T59 không chạy các lệnh tải/dựng này. |

## 1. Đơn vị dữ liệu

Một tệp `cache/<sha256-url>.json` là **một phản hồi của một truy vấn**, không phải một dòng hoạt chất. Cùng hoạt chất có thể cần nhiều truy vấn; phản hồi rỗng vẫn là tệp đệm hợp lệ.

Một phần tử `minConceptGroup.minConcept[]` trong `allconcepts_IN_PIN.json` là một khái niệm RxNorm: IN là hoạt chất; PIN là hoạt chất chính xác hơn, có thể là dạng muối/ester. Bộ dựng quy PIN về IN khi có bằng chứng theo quy tắc đang áp dụng, không coi PIN và IN là hai hoạt chất độc lập trong mọi trường hợp.

Danh mục có 18.406 mục: 14.718 IN, 3.688 PIN. Chỉ các khái niệm được chấp nhận từ dữ liệu đầu vào mới vào [trục hoạt chất](tu-dien-tra-cuu.md); không đưa toàn bộ danh mục vào bộ tra runtime.

## 2. Ba tầng tệp

| Tầng | Đường dẫn | Kích thước đo | Vai trò |
|:--|:--|--:|:--|
| Thô, đệm truy vấn | `data/kb_sources/rxnav/cache/*.json` | 3.428.644 byte; 11.343 tệp | Lưu phản hồi nguyên nguồn |
| Thô, sổ lượt chạy | `data/kb_sources/rxnav/manifest.json` | 3.245.066 byte | Liệt kê phản hồi được dùng trong lượt manifest |
| Thô, danh mục | `data/kb_sources/rxnav/danh_muc/allconcepts_IN_PIN.json` | 1.169.371 byte | Kho tên ứng viên IN/PIN |
| Thô, sổ danh mục | `data/kb_sources/rxnav/danh_muc/manifest.json` | 387 byte | Xuất xứ, ngày và SHA-256 danh mục |
| Trung gian | Không có JSONL RxNav riêng | Không có tệp riêng để đo | `RxIngredient` và kho `Catalog` được dựng trong bộ nhớ từ đệm/danh mục |
| Chuẩn hóa, dùng chung | `data/kb_curated/tu_dien/hoat_chat.jsonl` | 1.231.178 byte | Mã RxCUI, tên INN và ATC trên trục; các JSONL đồng nghĩa/ánh xạ cùng ở thư mục này |
| Bộ tra runtime, dùng chung | `data/kb_curated/tra_cuu/tra_cuu.sqlite` | 11.005.952 byte | Thẩm định nạp chỉ mục đã dựng; không truy vấn RxNav |

Không có manifest riêng cho từng tệp đệm. Manifest hiện liệt kê 10.780 tệp, còn đĩa có 11.343: **563 tệp đệm không nằm trong manifest lượt hiện tại**, không có tệp được liệt kê mà thiếu trên đĩa. `RxNav._get` tính khóa trực tiếp từ URL nên có thể đọc tệp đệm ngoài danh sách này; `Catalog._read_reverse_pins` lại duyệt chính danh sách manifest để tìm quan hệ ngược.

## 3. Trường của từng tệp

✅ build chỉ xử lý chuẩn hóa/dựng/chờ duyệt, không đồng nghĩa được dùng lúc thẩm định. ❌ nghĩa chưa thấy đọc trực tiếp ngoài lưu nguyên phản hồi. Runtime đọc bộ tra theo mô tả ở [tu-dien-tra-cuu.md](tu-dien-tra-cuu.md).

### 3.1. Các dạng phản hồi `cache/*.json`

Các bảng liệt kê hợp khóa thực có trên đĩa. Endpoint không có kết quả có thể trả đối tượng rỗng hoặc bỏ mảng; không gán mã/ATC mặc định.

| Trường phản hồi tìm chính xác | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `idGroup` | Bao kết quả tra tên | ✅ build: `sources/rxnav.py:exact` kiểm cấu trúc |
| `idGroup.rxnormId[]` | Danh sách RxCUI trả về | ✅ build: xác minh từng mã là IN/PIN và chỉ nhận một IN |

| Trường gợi ý gần đúng | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `approximateGroup` | Bao kết quả gần đúng | ✅ build: `RxNav.suggestions` |
| `approximateGroup.inputTerm` | Trường truy vấn nguồn, hiện null trong bản lưu | ❌ |
| `approximateGroup.candidate[]` | Các khái niệm gợi ý | ✅ build: hàng chờ |
| `candidate[].rxcui` | Mã ứng viên | ✅ build: bỏ trùng, giữ để duyệt |
| `candidate[].name` | Tên ứng viên nếu nguồn có | ✅ build: `ten_rxnav`; khi thiếu có thể tra tên qua RxClass |
| `candidate[].score` | Điểm do RxNav trả, đang là chuỗi | ✅ build: ghi `goi_y[].diem`; không phải độ đúng lâm sàng |
| `candidate[].rank` | Thứ hạng gốc | ❌ |
| `candidate[].rxaui` | Mã atom do nguồn trả | ❌ |
| `candidate[].source` | Nguồn từ vựng của gợi ý | ❌ |

Trong bảng trên, `candidate[]` nằm dưới `approximateGroup`.

| Trường quan hệ | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `relatedGroup` | Bao quan hệ RxNorm | ✅ build: `RxNav._related` |
| `relatedGroup.rxcui` | Mã gốc phản hồi; bản lưu có null | ❌; mã truy vấn lấy từ URL |
| `relatedGroup.conceptGroup[]` | Nhóm theo loại khái niệm | ✅ build |
| `conceptGroup[].tty` | Loại khái niệm của nhóm | ✅ build: chỉ lấy nhóm được yêu cầu |
| `conceptGroup[].conceptProperties[]` | Khái niệm liên quan | ✅ build |
| `conceptProperties[].rxcui` | Mã IN/PIN liên quan | ✅ build: chứng cứ PIN→IN và IN→PIN |
| `conceptProperties[].name` | Tên khái niệm liên quan | ✅ build: đối chiếu danh tính |
| `conceptProperties[].tty` | Loại khái niệm riêng của mục | ❌; mã hiện lọc bằng `conceptGroup[].tty` |
| `conceptProperties[].language` | Ngôn ngữ tên | ❌ |
| `conceptProperties[].synonym` | Đồng nghĩa do nguồn trả | ❌; không tự nhập mọi đồng nghĩa nguồn |
| `conceptProperties[].suppress` | Cờ suppress của nguồn | ❌ |
| `conceptProperties[].umlscui` | Mã UMLS do nguồn trả | ❌ |

`conceptGroup[]` và `conceptProperties[]` trong bảng này đều thuộc `relatedGroup`.

| Trường RxClass | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `rxclassDrugInfoList` | Bao kết quả phân lớp | ✅ build: `RxNav._atc` |
| `rxclassDrugInfoList.rxclassDrugInfo[]` | Quan hệ khái niệm–lớp | ✅ build |
| `rxclassDrugInfo[].minConcept` | Khái niệm thuốc | ✅ build |
| `minConcept.rxcui` | Mã thuốc của quan hệ | ✅ build: chỉ nhận nếu trùng mã truy vấn |
| `minConcept.name` | Tên thuốc | ✅ build: xác minh IN/PIN và tên chuẩn |
| `minConcept.tty` | Loại khái niệm thuốc | ✅ build: xác minh IN/PIN |
| `rxclassDrugInfo[].relaSource` | Nguồn quan hệ | ✅ build: chỉ nhận ATC |
| `rxclassDrugInfo[].rela` | Loại quan hệ nguồn | ❌ |
| `rxclassDrugInfo[].rxclassMinConceptItem` | Khái niệm lớp | ✅ build |
| `rxclassMinConceptItem.classId` | Mã ATC/lớp | ✅ build: kiểm dạng mã và xuất `ma_atc` |
| `rxclassMinConceptItem.className` | Tên lớp | ✅ build: xuất `ten_lop_atc` |
| `rxclassMinConceptItem.classType` | Kiểu lớp nguồn | ❌ |

Các đường dẫn rút gọn ở bảng RxClass đều nằm trong `rxclassDrugInfoList.rxclassDrugInfo[]`.

### 3.2. `allconcepts_IN_PIN.json`

| Trường | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `minConceptGroup` | Bao danh mục | ✅ build: `dictionary/catalog.py:Catalog` |
| `minConceptGroup.minConcept[]` | Mảng khái niệm | ✅ build: kho tên ứng viên |
| `minConcept[].rxcui` | Mã RxNorm | ✅ build: nối danh tính, neo nguồn đến mục danh mục |
| `minConcept[].name` | Tên nguồn | ✅ build: khóa tên chính xác, PIN về IN, xếp hạng để duyệt |
| `minConcept[].tty` | IN hoặc PIN | ✅ build: phân biệt hoạt chất gốc/dạng chính xác |

### 3.3. `rxnav/manifest.json`

| Trường | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `ngay_lay` | Mốc lượt chạy | ✅ build: ghi bởi `RxNav.manifest`; ❌ runtime |
| `url` | Gốc API | ❌ runtime; truy nguyên |
| `trang_thai` | Tình trạng lượt chạy | ✅ build: `dictionary/report.py` |
| `so_phan_hoi_moi` | Số phản hồi mới trong lượt | ❌ runtime; thống kê lượt |
| `so_phan_hoi_doc_dem` | Số phản hồi đọc từ đệm trong lượt | ❌ runtime; không phải tổng số tệp đĩa |
| `so_ten_tra` | Số tên đầu vào của lượt | ❌ runtime; thống kê |
| `so_phan_hoi_tra_ten_rxnav` | Số phản hồi tìm mã theo tên | ❌ runtime; thống kê |
| `so_ten_theo_cach_khop` | Số tên theo cách khớp | ❌ runtime; báo cáo lượt |
| `so_ten_theo_cach_khop.bang_viet_quoc_te` | Khớp bảng chính tả | ❌ runtime |
| `so_ten_theo_cach_khop.cho_duyet_gan_dung` | Tên có gợi ý gần đúng | ❌ runtime |
| `so_ten_theo_cach_khop.chua_khop` | Tên chưa khớp | ❌ runtime |
| `so_ten_theo_cach_khop.ma_chuan` | Khớp khóa đã có | ❌ runtime |
| `so_ten_theo_cach_khop.rxnav_chinh_xac` | Khớp chính xác RxNav | ❌ runtime |
| `hoat_chat_ca_gia_lap_chua_khop` | Danh sách tên còn thiếu trong nhóm ca | ❌ runtime; kiểm độ phủ |
| `loi` | Lỗi lượt chạy, hiện null | ❌ runtime |
| `tep[]` | Phản hồi đã dùng trong lượt này | ✅ build: `Catalog._read_reverse_pins` |
| `tep[].duong_dan` | Tệp phản hồi tương đối | ❌ đọc trực tiếp từ manifest trong bộ tra; `_get` tự tính tên tệp từ URL |
| `tep[].url` | URL đầy đủ của truy vấn, không chứa khóa bí mật | ✅ build: tìm quan hệ IN→PIN đã có |
| `tep[].sha256` | Băm byte JSON phản hồi | ❌ runtime; ghi để truy nguyên; `RxNav._get` hiện không kiểm lại băm manifest khi đọc cache |

### 3.4. `danh_muc/manifest.json`

| Trường | Ý nghĩa | App dùng? / ở đâu |
|:--|:--|:--|
| `nguon` | Tên nguồn danh mục | ❌ runtime; truy nguyên |
| `url` | URL danh mục IN/PIN | ❌ runtime; truy nguyên |
| `ngay_lay` | Mốc tải danh mục | ❌ runtime |
| `sha256` | SHA-256 tệp danh mục | ❌ mã `Catalog` chưa kiểm băm này khi nạp; T59 đã đối chiếu |
| `so_muc` | Số khái niệm | ❌ runtime; kiểm đếm |
| `nguoi_tai` | Người/lượt ghi tải | ❌ runtime |
| `ghi_chu` | Mục đích dùng danh mục | ❌ runtime |

## 4. Bộ tra

Không có SQLite RxNav riêng. Giá trị `rxcui`, `ma_atc_json` nằm ở bảng `hoat_chat` của bộ tra dùng chung. `DrugResolver.from_index` đọc tên/ATC nhưng **không đọc cột RxCUI**; báo cáo độ phủ đọc RxCUI. Tên lớp ATC không được mang vào SQLite. Xem [bảng, cột, số dòng và cách dùng](tu-dien-tra-cuu.md).

## 5. Kết quả kiểm đã có

- T59 đếm trực tiếp danh mục được 18.406 mục, đúng manifest; băm SHA-256 khớp.
- T59 kiểm đường dẫn manifest đệm: 10.780 tệp được liệt kê đều tồn tại; còn 563 tệp ngoài danh sách của lượt manifest. Đây là khác biệt giữa sổ lượt chạy và toàn thư mục, chưa chứng minh mất dữ liệu.
- T50-fix-1 ghi đã xác nhận phản hồi thật của RxNav/RxClass và xử lý được đáp ứng ATC rỗng. T52-fix-1 bổ sung PIN về IN bằng quy tắc đặt tên khi thiếu quan hệ cache; phải giữ neo cả PIN và IN.
- ATC trong trục chủ yếu là lớp mức 4 theo báo cáo T50; không diễn giải mã nhóm này thành mã hoạt chất mức 5. Một số hoạt chất không có ATC; dữ liệu thiếu giữ rỗng.
- README nguồn ngày 16–17/11 chưa liệt kê RxNav. Danh mục nguồn cũ không phản ánh phần này.

## 6. Việc còn mở

- Lưu điều khoản giấy phép/điều kiện sử dụng chính thức và lệnh tải danh mục; hiện chưa có chứng cứ cục bộ đủ để điền.
- Nếu cần biết ngày chính xác từng phản hồi, manifest lượt chạy chưa cung cấp được.
- Cần phân biệt rõ danh sách manifest và toàn cache khi kiểm đầy đủ/đóng gói; chưa có sổ hợp nhất cho mọi tệp hiện hữu.
- PIN thiếu quan hệ, tên nhiều mã và tên chưa đủ chứng cứ vẫn vào hàng duyệt; không tự chấp nhận kết quả gần đúng.
- Không dùng kết quả hiệu chuẩn nhúng giả làm bằng chứng bật tự nhận; xem [việc mở của từ điển](tu-dien-tra-cuu.md).

## Cách kiểm lại

Lệnh đo đã chạy từ gốc dự án, exit 0, không mạng:

```powershell
@'
import sys, json, hashlib
from pathlib import Path
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')
root = Path('data/kb_sources/rxnav')
for folder in [root / 'cache', root / 'danh_muc']:
    files = list(folder.iterdir())
    print(folder.as_posix(), 'files', len(files), 'bytes', sum(p.stat().st_size for p in files))
for p in [root / 'manifest.json', root / 'danh_muc/allconcepts_IN_PIN.json', root / 'danh_muc/manifest.json']:
    print(p.as_posix(), 'bytes', p.stat().st_size)
m = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
print('manifest', json.dumps({k: v for k, v in m.items() if k != 'tep'}, ensure_ascii=False))
listed = {r['duong_dan'] for r in m['tep']}
on_disk = {'cache/' + p.name for p in (root / 'cache').iterdir()}
print('listed_cache', len(listed), 'unlisted_cache', len(on_disk - listed), 'missing_cache', len(listed - on_disk))
p = root / 'danh_muc/allconcepts_IN_PIN.json'
rows = json.loads(p.read_text(encoding='utf-8'))['minConceptGroup']['minConcept']
print('catalog_rows', len(rows), 'by_tty', dict(Counter(r['tty'] for r in rows)), 'keys', sorted({k for r in rows for k in r}))
cm = json.loads((root / 'danh_muc/manifest.json').read_text(encoding='utf-8'))
print('catalog_manifest', json.dumps(cm, ensure_ascii=False))
print('catalog_hash_matches', hashlib.sha256(p.read_bytes()).hexdigest() == cm['sha256'])
for p in [Path('data/kb_curated/tu_dien/hoat_chat.jsonl'), Path('data/kb_curated/tra_cuu/tra_cuu.sqlite')]:
    print('derived_bytes', p.as_posix(), p.stat().st_size)
'@ | .venv/Scripts/python.exe -
```

Tìm nơi sử dụng đã chạy cùng lượt:

```powershell
rg -n 'dav|rxnav|tra_cuu.sqlite|hoat_chat.jsonl|dong_nghia.jsonl|thuoc_thanh_phan.jsonl|anh_xa.jsonl|cho_duyet.jsonl' app
```

