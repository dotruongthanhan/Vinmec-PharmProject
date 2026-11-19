# T51 – Cào DDInter 2.0 đầy đủ trường (thuốc, thuốc–thuốc, chi tiết cặp, thuốc–bệnh, thuốc–thức ăn)

Mô hình: Codex `gpt-6.2-sol`, effort `medium`. Chạy nền, không dừng để hỏi. Điểm chưa rõ thì chọn cách ít rủi ro nhất và ghi vào báo cáo, mục "Lựa chọn đã làm".

Đọc trước:
- `AGENTS.md`
- `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md`: mục 3, 3.1, 3.2, đợt D1.1–D1.3
- `plan/plan-1.3-du-lieu-thu-thap-tong-hop-tien-xu-ly.md`: mục 4, 6.2
- `data/kb_sources/README.md`
- `app/kb/fetch/client.py` (cách thử lại có sẵn)

Task **T50** (Cục Quản lý Dược + RxNav) chạy **song song**. Không đụng file của nó.

## Bối cảnh

- `data/kb_sources/ddinter/*.csv` (14 tệp, tải ngày 16/11) chỉ có `DDInterID_A, Drug_A, DDInterID_B, Drug_B, Level`. Tổng 2.568 thuốc, 234.981 cặp không trùng.
- Trang web có nhiều trường hơn. Claude đã kiểm ngày 18/11.

**Trang thuốc** `GET https://ddinter2.scbdd.com/server/drug-detail/<DDInterID>/`
- Phần thông tin: ID, Drug Type, Molecular Formula, Molecular Weight, CAS Number, Description, **ATC Classification**, IUPAC Name, InChI, SMILES, Useful Links.
- Bảng nạp qua XHR, cả bốn trả 200:
  - `POST /server/interact-with/<id>/`: thuốc–thuốc; cột Severity, ID, Name, **Mechanism** (Antagonism, Synergy, Absorption, Distribution, Metabolism, Excretion, Others), liên kết "view" tới `/server/interact/<n>/`.
  - `POST /server/interact-with-dis/<id>/`: thuốc–bệnh (Severity, Disease name, Text, References).
  - `POST /server/interact-with-food/<id>/`: thuốc–thức ăn (Severity, Food name, Description, **Management**, Mechanism, References).
  - `POST /server/interact-with-multi/<id>/`: tương tác với chế phẩm phối hợp.
- Mỗi bảng ghi "total N items", ví dụ warfarin `DDInter1951`: 936 cặp thuốc–thuốc.

**Trang cặp** `GET /server/interact/<n>/` (`n` là số riêng, không phải DDInterID):
- Tiêu đề "Interaction between A and B", mức độ, cơ chế.
- **Interaction** (hậu quả), **Management** (xử trí), **References** (danh sách).
- **Alternative for A / B** (mã ATC và tên thuốc thay thế).
- Mục "Potential metabolism interactions" (CYP).
- Còn có `GET /server/linkmarker/<n>/` (chưa rõ nội dung; xem và ghi lại).

Trang không có `robots.txt`. Giấy phép là **CC BY-NC-SA 4.0** (phi thương mại): ghi vào manifest và mọi tệp đầu ra.

## Phạm vi file

**Được tạo / sửa:**
- `app/kb/sources/ddinter_web.py`, `app/kb/fetch/ddinter.py` (mới)
- **Không sửa** `app/kb/fetch/__main__.py`, `runner.py` (T50 đang sửa). Điểm vào riêng: `python -m app.kb.fetch.ddinter` (đặt `if __name__ == "__main__"` trong `app/kb/fetch/ddinter.py`)
- `tests/kb/test_ddinter_web*.py`, `tests/kb/fixtures/ddinter/**` (một ít phản hồi thật đã lưu, mỗi tệp < 200 KB)
- Dữ liệu: `data/kb_sources/ddinter_web/**` (tầng 0, có `manifest.json` riêng), `data/kb_staging/ddinter/**` (tầng 1), `data/kb_reports/T51_*`
- Báo cáo `plan/reports/T51.md`

**Cấm đụng:**
- `data/kb_sources/ddinter/*.csv` (chỉ đọc), `data/kb_sources/manifest.json`
- `app/kb/dictionary/**`, `app/kb/sources/dav.py`, `app/kb/sources/rxnav.py`, `tests/kb/test_dav*`, `test_rxnav*`, `test_dictionary*`, `data/kb_sources/dav/**`, `rxnav/**`, `data/kb_*/tu_dien/**` (của T50)
- `app/rules/**`, `app/api/**`, `app/db/**`, `web/**`, `db/schema.sql`, `data/mock/**`, `data/kb/**` (chỉ đọc)
- `pyproject.toml`, `uv.lock`: không thêm thư viện. Phân tích HTML bằng thư viện chuẩn (`html.parser`) hoặc thư viện đã có trong môi trường; kiểm `uv pip list` trước. Thiếu thì dừng, ghi báo cáo

## Mạng được phép

Chỉ `https://ddinter2.scbdd.com`.

- Không đăng nhập, không vượt CAPTCHA.
- User-Agent chung `VinmecPharmProject-kb/1.0`, không email hay tên người.
- Test **không gọi mạng**.

## Yêu cầu

### 1. Bộ cào (`python -m app.kb.fetch.ddinter <pha> [tuỳ chọn]`)

- Nhịp mặc định **2 yêu cầu/giây** toàn cục (`--rps`, tối đa 2).
- Thử lại 429/5xx/hết giờ có giãn cách mũ, tối đa 5 lần. Gặp lỗi liên tiếp > 20 thì dừng có báo cáo, không tiếp tục dội máy chủ.
- **Chạy tiếp được sau khi dừng:**
  - Mỗi phản hồi lưu thô vào `data/kb_sources/ddinter_web/<loai>/<khoa>.(html|json).gz`.
  - Có tệp trạng thái; chạy lại thì bỏ qua cái đã có, trừ khi `--refresh`.
- `--limit N` và `--ids DDInter1951,DDInter83` để chạy thử.
- **POST:** tự đọc JS / mã nguồn trang để biết tham số cần gửi (có thể là DataTables phía máy chủ: `draw`, `start`, `length`, CSRF token lấy từ cookie / trang). Phải lấy **toàn bộ** dòng, kể cả khi phải phân trang. Ghi thân yêu cầu vào báo cáo.

### 2. Các pha

| Pha | Việc | Ước lượng |
|:--|:--|:--|
| `thuoc` | Với mỗi DDInterID trong hợp các CSV (2.568): trang thuốc + 4 điểm POST | ~12.840 yêu cầu |
| `cap-uu-tien` | Trang cặp `/server/interact/<n>/` cho cặp mà **cả hai bên** thuộc danh sách ưu tiên (mục 3) | vài trăm đến vài nghìn |
| `cap-mot-ben` | Như trên, cặp có **ít nhất một bên** thuộc danh sách ưu tiên | vài chục nghìn |
| `cap-tat-ca` | Mọi cặp còn lại | ~235k; chạy nền nhiều ngày, **không chạy trong task này** |

Trong task này **chỉ chạy thật**:
- `thuoc --limit 30`
- `cap-uu-tien --limit 200`

Mục đích là kiểm bộ cào và bộ phân tích. Claude sẽ tự chạy các pha đầy đủ ở nền sau khi review. Báo cáo ghi rõ lệnh chạy đầy đủ cho từng pha.

### 3. Danh sách ưu tiên (`data/kb_staging/ddinter/uu_tien.json`)

- Lấy tên quốc tế của:
  - (a) 54 hoạt chất trong `data/kb/hoat_chat.json` (`ten_inn`, `dong_nghia`, `hoat_chat_id`).
  - (b) Hoạt chất trong `danh_muc_hoat_chat` của `data/mock/demo/*.json` và `data/mock/hoso_gia_lap/*.json` (chỉ đọc; dùng tên quốc tế nếu có).
- Khớp với tên thuốc DDInter trong CSV **chính xác** (không phân biệt hoa thường, bỏ muối bằng `app/kb/names.py`).
- Thuốc phối hợp tách theo thành phần.
- Không khớp được thì liệt kê trong báo cáo (T52 sẽ khớp lại qua trục hoạt chất của T50). **Không ghép mờ.**

### 4. Bộ phân tích → tầng 1 (`data/kb_staging/ddinter/`, JSONL)

Mỗi dòng có `nguon` = `DDInter 2.0`, `giay_phep` = `CC BY-NC-SA 4.0`, `url_goc`, `tep_tho` (đường dẫn tầng 0), `ngay_lay`.

| Tệp | Trường |
|:--|:--|
| `thuoc.jsonl` | `ddinter_id`, `ten`, `loai_thuoc`, `ma_atc[]`, `cas`, `mo_ta`, `lien_ket{drugbank,pubchem,...}`, `tong_tuong_tac_tren_trang` (số "total N" của từng bảng) |
| `tuong_tac_thuoc.jsonl` | `ddinter_id_a`, `ddinter_id_b` (sắp theo thứ tự để A < B), `ten_a`, `ten_b`, `muc_do`, `co_che[]`, `ma_trang_cap` (`n`), `tu_trang_cua` |
| `tuong_tac_chi_tiet.jsonl` | `ma_trang_cap`, `ddinter_id_a`, `ddinter_id_b`, `muc_do`, `co_che[]`, `hau_qua` (Interaction), `xu_tri` (Management), `tai_lieu[]`, `thay_the_a{ma_atc, thuoc[]}`, `thay_the_b{...}`, `cyp_tho` (nguyên văn mục CYP, nếu có) |
| `tuong_tac_benh.jsonl` | `ddinter_id`, `ten_benh`, `muc_do`, `noi_dung` (**đủ văn bản**, không phải bản cắt "..."; nếu trang chỉ trả bản cắt thì tìm cách lấy bản đủ và ghi rõ), `tai_lieu[]` |
| `tuong_tac_thuc_an.jsonl` | `ddinter_id`, `thuc_an`, `muc_do`, `mo_ta`, `xu_tri`, `co_che[]`, `tai_lieu[]` |
| `che_pham_phoi_hop.jsonl` | Theo cấu trúc thật của `interact-with-multi`; ghi mô tả cấu trúc vào báo cáo |

- Văn bản giữ **nguyên văn**: chỉ gộp khoảng trắng và bỏ thẻ HTML. Không dịch, không tóm tắt.
- Thiếu trường thì để `null` hoặc `[]`, không đoán.

### 5. Kiểm tự động (`python -m app.kb.fetch.ddinter kiem`)

Ghi ra `data/kb_reports/T51_kiem.json`:
- **Đếm:** số dòng mỗi bảng của mỗi thuốc so với "total N" trên trang; liệt kê mọi chỗ lệch.
- **Đối chiếu CSV:**
  - Cặp có trong CSV cũ mà không có trong `tuong_tac_thuoc` (với các thuốc đã cào), và ngược lại.
  - Mức độ lệch giữa CSV và trang.
- **Đối xứng:** cặp lấy từ trang thuốc A và trang thuốc B cho cùng mức độ.
- **Mồ côi:** dòng chi tiết không có cặp tương ứng.

Ghi ra `data/kb_reports/T51_mau_kiem.jsonl`: 40 cặp chi tiết ngẫu nhiên (seed 51) kèm `url_goc`. Claude sẽ mở trình duyệt so từng trường.

## Nghiệm thu (dán kết quả vào báo cáo)

- Dán đầu ra của các lệnh chạy thử:
  - `thuoc --limit 30` (có `DDInter1951` warfarin và `DDInter83` amoxicillin)
  - `cap-uu-tien --limit 200`
  - `kiem`
- Với warfarin: số dòng thuốc–thuốc = 936 (hoặc đúng số "total" lúc chạy); có bảng thuốc–bệnh và thuốc–thức ăn (`alcohol` có `xu_tri`).
- Cặp warfarin–acalabrutinib (trang `/server/interact/3039/`) có `hau_qua`, `xu_tri`, 3 tài liệu, `thay_the_a.ma_atc` = `B01A`.
- Test bộ phân tích trên fixture: trang thuốc, 4 phản hồi POST, 2 trang cặp (một có đủ mục, một thiếu mục), phản hồi lỗi.
- Test chạy tiếp sau khi dừng: lần chạy 2 không gọi lại khoá đã có (giả lập client).
- Đo thời gian trung bình mỗi yêu cầu; ước lượng thời gian cho `thuoc`, `cap-mot-ben`, `cap-tat-ca`.
- `uv run ruff check .`, `uv run ruff format --check` (tệp đã sửa), `uv run pytest -q --basetemp=.pytest_t51` đều qua; test cũ không đổi kỳ vọng.
- Báo cáo `plan/reports/T51.md`:
  - Có các mục "Lựa chọn đã làm", "Cấu trúc phản hồi POST", "Lệnh chạy đầy đủ", "Giới hạn còn lại".
  - Ghi dung lượng dự kiến khi cào đủ.

## Cấm làm

- Không commit / push. Không dùng `&`.
- Không vượt 2 yêu cầu/giây.
- Không chạy `cap-mot-ben` / `cap-tat-ca` đầy đủ.
- Không gọi LLM.
- Không sửa tệp CSV cũ.
- Xoá `.pytest_t51*` khi xong.
