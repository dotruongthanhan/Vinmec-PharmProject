# T04a – Tiền xử lý nhãn openFDA, chuẩn hoá tên thuốc, cắt đoạn

**Giao cho:** agy CLI (`gemini-4-hydrogen-xhigh`) · **Ngày:** 16/11/2026
**Đọc trước (bắt buộc):** `AGENTS.md`; `plan/plan-1.1-kien-truc-chi-tiet.md` mục 5 (chiến lược cắt đoạn, toàn bộ); `plan/plan-1.3-du-lieu-thu-thap-tong-hop-tien-xu-ly.md` mục 4, 5, 6.1; `data/kb_sources/README.md`; **chỉ đọc**: `app/core/types.py` (lớp `Chunk`), `app/core/interfaces.py` (`Chunker`), `app/config/settings.py` (`ChunkingSettings`), `data/kb_sources/manifest.json`, và 2–3 tệp trong `data/kb_sources/openfda/` (ít nhất `meropenem.json` là nhãn định dạng mới và `ceftriaxone.json` là nhãn định dạng cũ).

**Không gọi công cụ shell / terminal / command dưới bất kỳ hình thức nào**: phiên này không có quyền đó và gọi là mất toàn bộ kết quả. Chỉ dùng công cụ đọc, liệt kê, ghi và sửa file. Người review sẽ tự chạy lệnh.

**Nhiều task khác đang chạy song song.** Chỉ tạo và sửa file ở mục 2. Không sửa `pyproject.toml`, `app/core/`, `app/config/`, `app/container.py`, `app/providers/`, `app/retrieval/`, `app/llm/`, `app/verify/`, `app/api/`, `app/ui/`, `web/`, `config/`, `data/kb_sources/`, `data/kb/quy_tac_lieu_than.json`. Chỉ dùng thư viện chuẩn và pydantic (đọc HTML bảng bằng `html.parser`).

## 1. Mục tiêu

Biến 50 tệp nhãn ở `data/kb_sources/openfda/` thành tệp đoạn `data/kb_curated/chunks.jsonl` (mỗi dòng một `Chunk`), đúng chiến lược cắt theo cấu trúc. Không nhúng, không gọi mạng, không gọi LLM.

## 2. Phạm vi file

```text
app/kb/__init__.py
app/kb/names.py                 # chuẩn hoá tên thuốc
app/kb/sources/__init__.py
app/kb/sources/openfda.py       # đọc nhãn, ánh xạ mục, làm sạch, đọc bảng
app/kb/chunking/__init__.py
app/kb/chunking/base.py         # BaseChunker: gộp mảnh nhỏ, chia mục dài, gắn tiêu đề ngữ cảnh
app/kb/chunking/label_chunker.py
app/kb/build.py                 # python -m app.kb.build
app/kb/__main__.py              # gọi build.main()
data/kb/hoat_chat.json          # bảng hoạt chất và tên đồng nghĩa (mục 3)
tests/kb/__init__.py
tests/kb/test_names.py  test_openfda_source.py  test_chunking.py  test_build.py
tests/kb/fixtures/…             # nhãn thu nhỏ tự dựng để test
```

`data/kb_curated/` và `data/kb_reports/` là đầu ra của lệnh build: không tự viết tay tệp trong đó.

## 3. Chuẩn hoá tên – `app/kb/names.py` và `data/kb/hoat_chat.json`

`hoat_chat.json`: danh sách mục `{hoat_chat_id, ten_inn, ten_viet, dong_nghia: [..], thanh_phan: [..] | null, nhom: str | null}` cho **đủ 50 tệp** trong `manifest.json` (trường `ten_goi`).

- `hoat_chat_id`: INN chữ thường, không dấu, `snake_case` (`amoxicillin`, `clavulanic_acid`, `valproic_acid`, `sulfamethoxazole`, `trimethoprim`, `insulin_glargine`).
- Thuốc phối hợp (`amoxicillin_and_clavulanate_potassium`, `piperacillin_and_tazobactam`, `imipenem_and_cilastatin`, `sulfamethoxazole_and_trimethoprim`) **không** là một hoạt chất: khai báo từng thành phần là một mục riêng, và một bảng `ten_goi_nhan → [hoat_chat_id, …]` trong cùng tệp (khoá `nhan`) để biết tệp nhãn nào chứa những hoạt chất nào. `metoprolol_tartrate` và `metoprolol_succinate` cùng về `metoprolol`.
- `ten_viet`: cách viết của Dược thư Quốc gia (`amoxicilin`, `ceftriaxon`, `amlodipin`, `acid valproic`, `paracetamol` cho acetaminophen). Không chắc cách viết thì để bằng `ten_inn` và thêm `"can_duyet": true`. Không bịa tên thương mại.
- `nhom`: nhóm dược lý ngắn (`carbapenem`, `penicillin`, `cephalosporin`, `aminoglycosid`, `fluoroquinolon`, `chong_dong`, …) chỉ khi chắc chắn; không chắc thì `null`.

`names.py`:

```python
def normalize_key(name: str) -> str        # chữ thường, bỏ dấu (đ → d), bỏ dấu câu, gộp khoảng trắng
def strip_salt(key: str) -> str            # bỏ gốc muối ở cuối: besylate, hydrochloride, sodium, potassium, tartrate,
                                           # succinate, sulfate, calcium, magnesium, maleate, bisulfate, citrate, etexilate, tromethamine
class DrugNameIndex:
    def __init__(self, entries: list[dict], labels: dict[str, list[str]]) -> None
    @classmethod
    def load(cls, path: Path) -> "DrugNameIndex"
    def resolve(self, name: str) -> list[str]          # tên bất kỳ → danh sách hoat_chat_id; không khớp → []
    def ids_for_label(self, ten_goi: str) -> list[str] # tệp nhãn → các hoạt chất
```

`resolve` thử theo thứ tự: khoá đầy đủ → khoá đã bỏ muối → tách theo `" and "`, `" + "`, `"/"` rồi giải từng phần. **Không khớp thì trả rỗng, không đoán gần đúng.**

## 4. Đọc nhãn – `app/kb/sources/openfda.py`

```python
class LabelSection(BaseModel):  muc: str; duong_dan_muc: str; truong_goc: str; van_ban: str; bang: list[LabelTable] = []
class LabelTable(BaseModel):    tieu_de: str | None; cot: list[str]; dong: list[list[str]]; van_ban_phang: str
class LabelDocument(BaseModel): tai_lieu_id: str; ten_goi: str; hoat_chat_ids: list[str]; set_id: str
                                phien_ban_nguon: str; url_goc: str; ten_hien_thi: str; sections: list[LabelSection]
def load_label(path: Path, manifest_entry: dict, names: DrugNameIndex) -> LabelDocument
```

- `tai_lieu_id = "openfda:" + set_id`. `ten_hien_thi` dạng `"Nhãn FDA <brand hoặc generic> (<ngày hiệu lực dd/mm/yyyy>)"`.
- **Bảng ánh xạ trường → `muc`** đúng mục 6.1 bước 2 của plan 1.3, xử lý cả hai định dạng nhãn. Bảng `muc` chuẩn: `chi_dinh`, `chong_chi_dinh`, `lieu`, `lieu_than`, `lieu_gan`, `tuong_tac`, `canh_bao`, `thai_ky_cho_bu`, `nhi_cao_tuoi`, `tac_dung_phu`, `qua_lieu`, `duoc_ly`, `khac`. `clinical_pharmacology`, `pharmacokinetics`, `pharmacodynamics`, `mechanism_of_action` → `duoc_ly`; `adverse_reactions` → `tac_dung_phu`; `overdosage` → `qua_lieu`.
- **Bỏ** các trường: `spl_product_data_elements`, `package_label_principal_display_panel`, `how_supplied`, `storage_and_handling`, `clinical_studies`, `nonclinical_toxicology`, `carcinogenesis_and_mutagenesis_and_impairment_of_fertility`, `references`, `description`, `microbiology`, `information_for_patients`, `recent_major_changes`, `spl_unclassified_section`, mọi trường `*_table` (bảng được đọc riêng), và mọi trường không phải danh sách chuỗi.
- **Tách tiểu mục:** văn bản của một trường thường chứa nhiều tiểu mục đánh số (`2.1 …`, `2.2 Dosage in Adult Patients with Renal Impairment …`, `8.6 Renal Impairment`, `8.7 Hepatic Impairment`). Tách theo mẫu số tiểu mục `\b\d{1,2}\.\d{1,2}\s+[A-Z]`; mỗi tiểu mục thành một `LabelSection` với `duong_dan_muc = "<tên trường dạng chữ> > <tiêu đề tiểu mục>"`. Tiểu mục có tiêu đề chứa `renal` → `muc = "lieu_than"`; chứa `hepatic` → `lieu_gan`; chứa `pregnan`, `lactation`, `nursing` → `thai_ky_cho_bu`; chứa `pediatric`, `geriatric` → `nhi_cao_tuoi`; còn lại theo trường cha.
- **Bỏ phần tóm tắt lặp:** nhiều nhãn mở đầu trường bằng bản tóm tắt (các câu kết thúc bằng tham chiếu kiểu `( 2.1 )`, `( 2.2 )`) rồi mới tới nội dung chi tiết. Phần đứng trước tiểu mục đánh số đầu tiên mà có ít nhất hai tham chiếu dạng `\(\s*\d{1,2}\.\d{1,2}\s*\)` thì bỏ.
- **Làm sạch:** gộp khoảng trắng liên tiếp thành một dấu cách, bỏ khoảng trắng đầu cuối. Không sửa chữ, không sửa số, không dịch.
- **Bảng:** đọc từ trường `<truong>_table` (HTML) bằng `html.parser`: `tieu_de` từ `<caption>` nếu có; hàng đầu tiên có nội dung làm `cot`; các hàng sau làm `dong`; `van_ban_phang` là các hàng nối bằng xuống dòng, các ô nối bằng `" | "`. Gắn bảng vào tiểu mục mà văn bản của nó chứa tiêu đề bảng hoặc chứa ô đầu tiên của bảng; không tìm được thì gắn vào tiểu mục đầu của trường. Số ô lệch nhau giữa các hàng: vẫn giữ `van_ban_phang`, để `cot = []`, `dong = []`.
- Trường nào không có trong bảng ánh xạ và không trong danh sách bỏ → `muc = "khac"` và được trả về trong danh sách cảnh báo của hàm.

## 5. Cắt đoạn – `app/kb/chunking/`

`LabelChunker(settings: ChunkingSettings)` có `split(document: LabelDocument) -> list[Chunk]` (giao diện `Chunker` nhận `dict`: nhận cả `LabelDocument` lẫn `dict` rồi `model_validate`).

Làm đúng 7 nguyên tắc ở mục 5.2 của plan 1.1. Cụ thể:

1. Mỗi `LabelSection` là một **mục cha**: `muc_cha_id = sha1(tai_lieu_id + "|" + duong_dan_muc)[:16]`.
2. Đơn vị của một mục: các đoạn văn (tách theo câu dẫn + danh sách, hoặc theo câu khi không có dấu hiệu đoạn) và các bảng. **Bảng là một đơn vị không cắt**, nội dung là `tieu_de` + `van_ban_phang`, `loai_noi_dung = "bang"`, được phép vượt `max_chars`.
3. **Câu liều kèm điều kiện không bị cắt đôi:** không tách tại vị trí mà phần sau bắt đầu bằng số hoặc đơn vị, hoặc phần trước kết thúc bằng `mg`, `mL`, `mL/min`, `g`, `mcg`, `every`, `q`, `CrCl`, `to`, `-`, `:`. Tách câu chỉ tại `. ` theo sau là chữ hoa, và không tách sau các viết tắt `e.g.`, `i.e.`, `vs.`, `No.`, `Fig.`, `approx.`, hay sau số thập phân.
4. **Gộp:** cộng dồn các đơn vị văn bản liền nhau của cùng một mục cho tới `target_chars`; mảnh cuối nhỏ hơn `min_chars` thì gộp vào mảnh trước (dù vượt `target_chars`, miễn không vượt `max_chars`; nếu vượt thì để riêng).
5. **Chia mục dài:** một đơn vị văn bản đơn lẻ dài hơn `max_chars` thì chia theo câu; hai mảnh liền nhau gối `overlap_sentences` câu. **Không gối giữa hai mục cha khác nhau.**
6. `noi_dung_goc` là nguyên văn (sau làm sạch ở mục 4). `noi_dung_nhung = "[" + tên các hoạt chất (ten_inn, nối bằng " + ") + " | " + ten_hien_thi + " | " + duong_dan_muc + "]\n" + noi_dung_goc`.
7. `doan_trich_id = "DT-" + sha1(tai_lieu_id + "|" + duong_dan_muc + "|" + str(thứ tự trong mục) + "|" + noi_dung_goc)[:12]`: ổn định giữa các lần chạy.
8. Các trường còn lại của `Chunk`: `nhom_nguon = "nhan_thuoc"`, `nguon = "openfda"`, `tang_tin_cay = 3`, `ngon_ngu = "en"`, `hoat_chat_ids` từ tài liệu, `muc` từ mục cha, `phien_ban_nguon`, `url_goc`.
9. Đoạn trùng `noi_dung_goc` trong cùng một tài liệu chỉ giữ đoạn đầu.

## 6. Lệnh dựng – `python -m app.kb.build`

Tham số: `--sources data/kb_sources`, `--out data/kb_curated`, `--reports data/kb_reports`, `--only <ten_goi,…>` (tuỳ chọn). Đường dẫn mặc định tính từ gốc kho.

1. Kiểm `manifest.json`: mỗi tệp openFDA có mặt và **khớp `sha256`**; lệch thì dừng với mã thoát khác 0.
2. Với từng nhãn: `load_label` → `LabelChunker.split`. Nhãn không giải được hoạt chất nào thì bỏ qua và ghi lý do.
3. Ghi `chunks.jsonl` (UTF-8, mỗi dòng `Chunk.model_dump_json()`), sắp theo `tai_lieu_id` rồi thứ tự xuất hiện, để hai lần chạy cho tệp giống hệt nhau.
4. Cổng chất lượng (plan 1.3 mục 9, các mục Q2, Q3, Q4): mọi đoạn có `hoat_chat_ids`, `muc`, `noi_dung_goc` khác rỗng; không trùng `doan_trich_id`; không đoạn văn bản nào dưới 50 ký tự (trừ `loai_noi_dung` là `bang`); mỗi nhãn có ít nhất một đoạn ở mỗi mục `chi_dinh`, `lieu`, `chong_chi_dinh`. Vi phạm Q2 hoặc Q4 → dừng, mã thoát khác 0. Vi phạm Q3 → ghi cảnh báo nêu tên nhãn, vẫn phát hành.
5. Ghi `data/kb_reports/build-<YYYYMMDD-HHMMSS>.json`: số nhãn vào, số nhãn bỏ qua kèm lý do, số đoạn theo `muc`, theo `loai_noi_dung`, phân bố độ dài (nhỏ nhất, trung vị, lớn nhất, số đoạn vượt `max_chars`), danh sách trường rơi vào `khac`, cảnh báo Q3. In tóm tắt ra màn hình bằng ASCII (không dấu) để không lỗi mã hoá trên Windows.

`build.py` chỉ điều phối; logic nằm ở các module trên. Có hàm `load_chunks(path: Path) -> list[Chunk]` để task khác đọc lại tệp.

## 7. Kiểm thử phải có

Dùng nhãn thu nhỏ tự dựng trong `tests/kb/fixtures/` (cả định dạng mới và cũ), và **một test trên tệp thật** `data/kb_sources/openfda/meropenem.json`.

- `normalize_key("Acid Valproïc ")`, `strip_salt("amlodipine besylate") == "amlodipine"`; `resolve("AMOXICILLIN AND CLAVULANATE POTASSIUM") == ["amoxicillin", "clavulanic_acid"]`; `resolve("Metoprolol Succinate") == ["metoprolol"]`; `resolve("amoxicilin") == ["amoxicillin"]`; `resolve("thuoc la") == []`.
- `hoat_chat.json`: mọi `ten_goi` trong `manifest.json` (nguồn `openfda_drug_label`) đều có trong bảng `nhan` và giải ra ít nhất một hoạt chất; không trùng `hoat_chat_id`.
- Nhãn định dạng cũ: `warnings` và `precautions` ra `muc == "canh_bao"`.
- Tách tiểu mục: tiểu mục có `Renal Impairment` ra `lieu_than`; phần tóm tắt có `( 2.1 )`, `( 2.2 )` bị bỏ.
- Bảng HTML 3 cột 4 hàng đọc đúng `cot`, `dong`; bảng lệch số ô vẫn có `van_ban_phang`.
- Cắt đoạn: bảng không bị cắt dù dài hơn `max_chars`; ba mảnh 80 ký tự cùng mục được gộp thành một đoạn; mục 5.000 ký tự được chia, mỗi đoạn ≤ `max_chars`, hai đoạn liền nhau có đúng 1 câu gối; hai mục cha khác nhau không có câu chung; câu `CrCl 10 to 25 mL/min: one-half the recommended dose every 12 hours.` không bị tách ở giữa; `noi_dung_goc` **là chuỗi con** của văn bản mục đã làm sạch; `noi_dung_nhung` bắt đầu bằng `[` và chứa `noi_dung_goc`; chạy hai lần cho cùng danh sách `doan_trich_id`.
- **Meropenem thật:** có đúng một đoạn `loai_noi_dung == "bang"` chứa đồng thời `26-50`, `10-25`, `Less than 10`, `Every 24 hours`; đoạn đó có `muc == "lieu_than"` hoặc nằm trong mục cha có `duong_dan_muc` chứa `Renal`; không đoạn nào của meropenem chứa cả `( 2.1 )` lẫn `( 2.2 )`.
- `build`: chạy trên thư mục `tmp_path` chứa 2 nhãn fixture + manifest khớp băm → sinh `chunks.jsonl` đọc lại được bằng `load_chunks`; sửa một byte của tệp nguồn → mã thoát khác 0; chạy hai lần → `chunks.jsonl` giống hệt.

## 8. Nghiệm thu (người review chạy)

```bash
uv run ruff check app/kb tests/kb
uv run ruff format --check app/kb tests/kb
uv run pytest -q tests/kb
uv run python -m app.kb.build
```

Lệnh cuối phải chạy trọn 50 nhãn, không nhãn nào bị bỏ qua vì tên không khớp. Viết code đúng định dạng `ruff format` (dòng tối đa 100 ký tự, nháy kép).

## 9. Cấm làm

- Không gọi mạng, LLM, không nhúng. Không thêm thư viện.
- Không sửa, không dịch, không tóm tắt nội dung y khoa trong nhãn. Không tự thêm liều, ngưỡng.
- Không sửa tệp trong `data/kb_sources/`.
- Không commit, không push.

Xong thì trả lời theo mẫu báo cáo trong `AGENTS.md`, ghi rõ là chưa chạy lệnh nào.
