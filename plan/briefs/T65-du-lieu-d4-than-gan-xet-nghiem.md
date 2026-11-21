# T65 – Dữ liệu D4: liều thận, ngưỡng gan, ngưỡng xét nghiệm, thuốc–bệnh (plan 1.8 đợt D4, phần dữ liệu)

Agent: **sub Sonnet** (việc dữ liệu chỉ Sonnet làm). Được dùng mạng cho openFDA / DailyMed. Không viết code ứng dụng.

**Chạy song song với T66 (dữ liệu D5).** Không đụng tệp của T66: `data/kb/duong_dung_hop_le.json`, `data/kb/lieu_toi_da.json`, `docs/du-lieu/lieu-duong-dung.md`.

Đọc trước:
- `AGENTS.md` (quy tắc 9)
- `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md`: mục 2, **Đợt D4**
- `docs/du-lieu/README.md`, `openfda-rag.md`, `ddinter.md` (mục tương tác thuốc–bệnh), `tu-dien-tra-cuu.md`, `ca-gia-lap.md`, `di-ung-cheo.md` (mẫu bảng có trích dẫn)
- `data/kb/quy_tac_lieu_than.json` và `app/rules/renal_dose.py`: **giữ đúng lược đồ hiện có**, chỉ mở rộng

## Việc

### 1. Liều thận (ưu tiên số 1)

Mở rộng `data/kb/quy_tac_lieu_than.json` theo **đúng lược đồ hiện tại** (không đổi tên khoá, không xoá quy tắc meropenem đã duyệt).

- **Phạm vi:** mọi hoạt chất trong 66 ca (xem `tu-dien-tra-cuu.md` / `chuyen_ma_ca`) mà nhãn FDA có bảng hoặc câu chỉnh liều theo CrCl hoặc eGFR. Ưu tiên kháng sinh, chống đông, thuốc khoảng điều trị hẹp (digoxin, vancomycin, aminoglycoside, levetiracetam…).
- **Nguồn:** đoạn `lieu_than` trong `data/kb_curated/chunks.jsonl` và nhãn trong `data/kb_sources/openfda*`. Thiếu nhãn thì tải thêm qua openFDA (≤ 2 yêu cầu/giây).
- **Mỗi dòng quy tắc phải có:**
  - `chi_so`: ghi đúng `CrCl` (Cockcroft-Gault) hay `eGFR` như nhãn;
  - các khoảng ngưỡng;
  - liều và khoảng cách;
  - `trich_nguyen_van`, `set_id`, `url`, `ngay_lay`;
  - `trang_thai: cho_duoc_si_duyet`. Quy tắc đã duyệt thì giữ nguyên trạng thái cũ.
- **Kiểm bằng code:**
  - các khoảng của mỗi hoạt chất phủ kín, không chồng nhau, không hở;
  - mỗi `trich_nguyen_van` là chuỗi con nguyên văn của tệp nhãn.
- Nhãn chỉ ghi chung "giảm liều khi suy thận", không có ngưỡng: **không** tự đặt ngưỡng; ghi vào mục "không có ngưỡng".

### 2. Ngưỡng gan

Tệp mới `data/kb/quy_tac_gan.json`. Lấy đoạn `lieu_gan` và câu theo Child-Pugh A/B/C trong nhãn (ví dụ "Child-Pugh class C: not recommended").

- Chỉ ghi điều nhãn nói, có trích dẫn.
- **Không cài công thức Child-Pugh.** Công thức chờ người dùng lấy từ MDCalc.

### 3. Ngưỡng xét nghiệm

Tệp mới `data/kb/nguong_xet_nghiem.json`. Các cặp plan nêu:
- K⁺ với spironolactone / ức chế RAS;
- INR với warfarin;
- tiểu cầu với heparin / enoxaparin;
- ALT/AST với thuốc độc gan;
- natri;
- glucose với insulin;
- metformin với eGFR.

Mỗi dòng: `hoat_chat_ids`, `xet_nghiem` (tên và mã như trong ca; xem `ca-gia-lap.md` phần kết quả xét nghiệm), ngưỡng, đơn vị, hành động nhãn nêu, trích nguyên văn, nguồn.

- **Chỉ lấy ngưỡng có số trong nhãn.** Không bịa ngưỡng.
- Đơn vị phải khớp đơn vị xét nghiệm trong ca. Không khớp thì ghi rõ cần quy đổi.

### 4. Thuốc–bệnh (DDInter)

Bảng `data/kb/thuoc_benh_icd.json`: ánh xạ `ten_benh` của DDInter (`data/kb_staging/ddinter/tuong_tac_benh.jsonl`) sang mã ICD-10 (nhóm chương hoặc nhóm 3 ký tự).

- Chỉ cho các bệnh liên quan tới hoạt chất trong 66 ca.
- Ánh xạ làm bằng tay, `trang_thai: cho_duoc_si_duyet`.
- Ghi số cặp (hoạt chất ca × bệnh) khớp với `chan_doan` của 66 ca.

### 5. Kiểm kê ca

Chạy bằng `load_source_cases`. Ghi vào báo cáo:
- Mỗi ca có đủ dữ liệu để tính CrCl không: tuổi, cân nặng, giới, creatinin, đơn vị.
- Ca nào có xét nghiệm gan.
- Ca nào thuộc nhóm đặc biệt: thai, cho bú, trẻ em, người cao tuổi.

### 6. Tài liệu

- `docs/du-lieu/lieu-than-gan-xet-nghiem.md` theo mẫu.
- Thêm dòng vào `docs/du-lieu/README.md`.
- Báo cáo `plan/reports/T65.md`.

## Cấm

- Sửa `app/`, `tests/`, `config/`, `web/`.
- Sửa dữ liệu ca, `chunks.jsonl`, `tra_cuu.sqlite`.
- Đụng tệp của T66.
- Commit.
- In khoá.
- Bịa ngưỡng hay trích dẫn.

## Nghiệm thu (dán vào báo cáo)

- Số hoạt chất có quy tắc thận: trước / sau.
- Số dòng gan, số dòng xét nghiệm, số bệnh đã ánh xạ ICD.
- Kết quả hai kiểm tra bằng code ở việc 1.
- Danh sách "không có ngưỡng" và "thiếu nguồn".
