# T60 – Dữ liệu D3: bảng dị ứng và dị ứng chéo (plan 1.8 đợt D3, phần dữ liệu)

Agent: **sub Sonnet** (người dùng chốt 19/11: việc dữ liệu chỉ do Sonnet làm). Được dùng mạng để gọi openFDA. Không viết code ứng dụng.

Đọc trước:
- `AGENTS.md` (quy tắc 9: tài liệu dữ liệu)
- `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md`: mục 2 (nguyên tắc) và "Đợt D3"
- `docs/du-lieu/README.md`, `docs/du-lieu/openfda-rag.md`, `docs/du-lieu/tu-dien-tra-cuu.md`, `docs/du-lieu/ca-gia-lap.md`
- `app/rules/allergy.py`: chỉ đọc, để biết luật hiện tại cần gì

## Mục tiêu

Chuẩn bị **dữ liệu** để sau đó agent code viết luật dị ứng mới. Luật sẽ:
- phân giải tên dị ứng ra hoạt chất;
- dùng bảng dị ứng chéo theo nhóm.

Bản thân task này **không** viết luật.

## Việc

### 1. Kiểm kê dị ứng trong 66 ca

Dùng `app.db.reader.load_source_cases`.

- Liệt kê mọi tác nhân dị ứng, tình trạng (`co_di_ung` / `khong_di_ung_da_hoi` / `chua_co_thong_tin`) và loại tác nhân.
- Cho mỗi tác nhân loại thuốc chạy qua bộ phân giải: `DrugResolver.resolve_name`, chỉ mục ở `data/kb_curated/tra_cuu/tra_cuu.sqlite`. Ghi kết quả ra hoạt chất nào, hay chưa nhận diện.
- Ghi cả cặp "dị ứng X ↔ y lệnh Y" đang có trong ca.

### 2. Bảng nhóm dị ứng chéo

Tệp `data/kb/di_ung_cheo.json`. Thư mục `data/kb/` có trên git, vì đây là bảng quy tắc nhỏ cần dược sĩ duyệt.

Nhóm tối thiểu, theo plan:
- **Beta-lactam:**
  - Penicillin ↔ cephalosporin theo **chuỗi bên R1** (ví dụ amoxicillin / ampicillin ↔ cefadroxil / cephalexin / cefaclor).
  - Penicillin ↔ carbapenem.
  - Penicillin ↔ monobactam (aztreonam gần như không chéo, trừ ceftazidime cùng R1).
- **Sulfonamid kháng khuẩn**: không gộp với sulfonamid không kháng khuẩn (furosemide, thiazide, celecoxib). Ghi rõ mức bằng chứng.
- **NSAID**: phản ứng chéo do ức chế COX-1.
- **Thuốc chống động kinh nhân thơm**: carbamazepine, phenytoin, phenobarbital, lamotrigine, oxcarbazepine.
- Nhóm khác nếu ca có tác nhân thuộc nhóm đó.

Mỗi dòng gồm:
- `ma_nhom`, `ten_nhom` (tiếng Việt)
- `hoat_chat_ids`: **khoá trên trục** `tra_cuu.sqlite`, không tự đặt mã mới
- `hoat_chat_lien_quan`: nhóm chéo kèm `muc_cheo` (`cao` / `thap` / `rat_thap`)
- `co_so` (R1, cấu trúc, cơ chế)
- `nguon`, gồm:
  - `loai`: `nhan_fda` hoặc `tong_quan`
  - `trich_nguyen_van` (câu gốc tiếng Anh)
  - `set_id` hoặc DOI / PMID
  - `url`
  - `ngay_lay`
- `trang_thai`: luôn là `"cho_duoc_si_duyet"`

**Quy tắc nguồn:**
- Ưu tiên câu trong nhãn FDA, mục `contraindications` và `warnings_and_cautions`. Ví dụ câu về "cross-sensitivity" giữa penicillin và cephalosporin trong nhãn ceftriaxone, cefazolin…
- Lấy bằng openFDA `drug/label`: `https://api.fda.gov/drug/label.json?search=...`, ≤ 2 yêu cầu/giây, không cần khoá.
- Tài liệu tổng quan (bài báo về chuỗi bên R1) chỉ được dùng khi có DOI / PMID thật, mở được. **Không bịa trích dẫn.** Không có nguồn thì không thêm dòng; ghi vào mục "thiếu nguồn".
- **Không** lấy từ UpToDate, Lexicomp, MIMS, Micromedex.

### 3. Câu "quá mẫn" của nhãn

Với mỗi hoạt chất trong ca có nhãn FDA (đoạn trong `data/kb_curated/chunks.jsonl`):
- Liệt kê mã đoạn chứa câu chống chỉ định do quá mẫn ("hypersensitivity to … or any component").
- Ghi ra `data/kb_reports/T60_qua_man_nhan.json`.
- Luật sau này sẽ dùng các đoạn này làm căn cứ.

### 4. Tài liệu

- Tạo `docs/du-lieu/di-ung-cheo.md` theo mẫu `docs/du-lieu/ddinter.md`. Ghi cả kết quả kiểm kê ở việc 1.
- Thêm dòng vào bảng danh mục của `docs/du-lieu/README.md`.

## Phạm vi

**Được tạo / sửa:**
- `data/kb/di_ung_cheo.json`
- `data/kb_reports/T60_*`
- `data/kb_sources/openfda_d3/` (nhãn mới tải, kèm manifest)
- `docs/du-lieu/di-ung-cheo.md`, `docs/du-lieu/README.md` (thêm dòng)
- `plan/reports/T60.md`

**Cấm:**
- Sửa `app/**`, `tests/**`, `web/**`, `config/**`
- Sửa dữ liệu ca, `tra_cuu.sqlite`, `chunks.jsonl`
- Commit, push
- In khoá trong `.env`

## Nghiệm thu (ghi vào `plan/reports/T60.md`)

- Bảng kiểm kê dị ứng 66 ca, kèm tỷ lệ phân giải được.
- `data/kb/di_ung_cheo.json`:
  - đọc được bằng `json.load`;
  - mọi `hoat_chat_ids` có trong bảng `hoat_chat` của `tra_cuu.sqlite` (dán lệnh kiểm và kết quả);
  - mọi dòng có `trich_nguyen_van` và `url`.
- Ba tình huống của plan có đủ dữ liệu:
  - "Augmentin" phân giải ra amoxicillin;
  - penicillin ↔ ceftriaxone có dòng nhóm chéo;
  - tình trạng dị ứng "chưa có thông tin" được đếm trong kiểm kê.
- Mục "thiếu nguồn": dòng muốn thêm nhưng chưa có nguồn đáng tin.
- Có thể dừng giữa chừng nếu D3 phụ thuộc một bước D0 / D1 chưa xong. Ví dụ embedding: **chỉ dừng nếu thật sự cần**, và ghi rõ lý do.
