# T66 – Dữ liệu D5: đường dùng hợp lệ và liều tối đa (plan 1.8 đợt D5, phần dữ liệu)

Agent: **sub Sonnet** (việc dữ liệu chỉ Sonnet làm). Được dùng mạng cho openFDA. Không viết code ứng dụng.

**Chạy song song với T65 (dữ liệu D4).** Không đụng tệp của T65: `data/kb/quy_tac_lieu_than.json`, `data/kb/quy_tac_gan.json`, `data/kb/nguong_xet_nghiem.json`, `data/kb/thuoc_benh_icd.json`, `docs/du-lieu/lieu-than-gan-xet-nghiem.md`.

Đọc trước:
- `AGENTS.md` (quy tắc 9)
- `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md`: mục 2, **Đợt D5**
- `docs/du-lieu/README.md`, `dav.md` (dạng bào chế, đường dùng của Cục Quản lý Dược), `openfda-rag.md` (NDC `route`, mục liều của nhãn), `van-ban-byt.md` (cột đường dùng TT 20 / VBHN 15 nếu đã tách được), `tu-dien-tra-cuu.md`, `ca-gia-lap.md` (trường `duong_dung`, `lieu_moi_lan`, `so_lan_moi_ngay`, đơn vị trong y lệnh), `di-ung-cheo.md` (mẫu bảng có trích dẫn)

## Việc

### 1. Kiểm kê y lệnh 66 ca

Chạy bằng `load_source_cases`. Liệt kê:
- các giá trị `duong_dung` đang có, cùng cách viết (IV, tiêm tĩnh mạch, uống, PO…);
- đơn vị liều;
- dòng nào đủ dữ liệu để tính liều ngày;
- dòng nào cần cân nặng.

Đề xuất bảng chuẩn hoá tên đường dùng: tên trong ca → mã chuẩn (`uong`, `tiem_tinh_mach`, `tiem_bap`, `tiem_duoi_da`, `truyen_tinh_mach`, `dat`, `boi`, `nho`, `hit`…).

### 2. Đường dùng hợp lệ

Tệp `data/kb/duong_dung_hop_le.json`. Theo **hoạt chất + dạng bào chế** (không chỉ theo hoạt chất, vì levofloxacin có cả viên uống và dịch truyền).

- **Nguồn**, theo thứ tự tin cậy:
  1. Cục Quản lý Dược (dạng bào chế của sản phẩm VN);
  2. TT 20 (nếu tách được);
  3. NDC / nhãn FDA (`route`).
- Mỗi dòng: `hoat_chat_id`, dạng bào chế, danh sách đường dùng hợp lệ (mã chuẩn), nguồn kèm trích hoặc trường gốc, `trang_thai: cho_duoc_si_duyet`.
- **Phạm vi:** mọi hoạt chất trong 66 ca.
- **Tình huống plan:** levofloxacin dạng uống mà kê tiêm phải ra "không hợp lệ".

### 3. Liều tối đa

Tệp `data/kb/lieu_toi_da.json`. Mỗi hoạt chất trong ca, theo đường dùng và đối tượng (người lớn; trẻ em nếu nhãn có):
- `lieu_toi_da_lan`, `lieu_toi_da_ngay`, đơn vị;
- liều theo kg nếu nhãn ghi (`mg/kg/lan`, `mg/kg/ngay`, kèm trần tuyệt đối nếu có);
- `trich_nguyen_van`, `set_id`, `url`, `trang_thai: cho_duoc_si_duyet`.

Quy tắc:
- **Chỉ lấy số nhãn ghi rõ** ("not to exceed 4 g per day", "maximum daily dose"). Nhãn không ghi tối đa thì để trống và ghi lý do. Không suy từ liều thường dùng.
- **Tình huống plan:** paracetamol 1 g × 6 lần/ngày vượt 4 g; gentamicin theo kg.
- Kiểm bằng code: mỗi trích là chuỗi con nguyên văn của nhãn; đơn vị quy đổi được về đơn vị trong ca.

### 4. Tài liệu

- `docs/du-lieu/lieu-duong-dung.md` theo mẫu.
- Thêm dòng vào `docs/du-lieu/README.md`.
- Báo cáo `plan/reports/T66.md`.

## Cấm

- Sửa `app/`, `tests/`, `config/`, `web/`.
- Sửa dữ liệu ca, `chunks.jsonl`, `tra_cuu.sqlite`.
- Đụng tệp của T65.
- Commit.
- In khoá.
- Bịa số liều.

## Nghiệm thu (dán vào báo cáo)

- Kiểm kê y lệnh và bảng chuẩn hoá đường dùng.
- Số hoạt chất có đường dùng hợp lệ / có liều tối đa, trên tổng số hoạt chất ca.
- Ba tình huống của plan đã có đủ dữ liệu: levofloxacin, paracetamol, gentamicin theo kg thiếu cân nặng.
- Danh sách "nhãn không ghi tối đa" và "thiếu nguồn".
