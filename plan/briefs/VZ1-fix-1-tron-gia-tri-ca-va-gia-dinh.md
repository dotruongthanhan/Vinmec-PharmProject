# VZ1-fix-1 – Phụ đề trộn số của ca với kết quả giả định; chữ hình bị bóp trong khung chat

Người làm: Codex gpt-6.1-terra xhigh. Không cài gói, không mạng, không commit, không đọc `.env`, không đọc `~/.codex`.

## Claude thử e2e (27/11 tối)

Môi trường: `localhost:5173` demo, API `CDSS_PROFILE=e2e` (engine agentic), DeepSeek thật, DEMO-02, khung nhìn 1440×900.

**Đạt:**
- Hình hiện trong khung chat.
- Chunk `KhungMinhHoa` chỉ tải khi có hình.
- Khung chat không tràn ngang (399/399).
- Thanh kéo dùng được bằng phím; nút ±, chọn loại cân nặng, nút "Về số của ca", nhãn "giả định" đều có.
- Kéo creatinin về 121 → CrCl 28,0 → mức "Liều khuyến cáo, mỗi 12 giờ" (đúng dải 26–50).
- Toàn màn đẹp, có bảng dữ liệu và nguồn.

### Lỗi 1 – nguy hiểm lâm sàng
LLM viết `phu_de` như sau:
```
[{"chu":"CrCl của ca: "}, {"o":{"ds":"ds-3","cot":"crcl","dong":0}}, {"chu":" mL/min — Mức liều: "},
 {"o_theo_khoang":{… "gia_tri":{"ds":"ds-2","cot":"crcl","theo_tham_so":true}}}]
```
Khi kéo thanh tới 121 µmol/L, phụ đề hiện: **"CrCl của ca: 16 mL/min — Mức liều: Liều khuyến cáo, mỗi 12 giờ"**.
- Số 16 là của ca. Mức liều lại theo giá trị giả định.
- Đọc lướt sẽ hiểu ca này dùng đủ liều. Đúng ra, ở CrCl 16 phải là "Một nửa liều khuyến cáo, mỗi 12 giờ".

Huy hiệu "Đang xem giá trị giả định" có hiện, nhưng không đủ để tránh hiểu sai.

### Lỗi 2 – bố cục
Ở khung chat rộng 399 px, phụ đề và ô "Mức liều" bị bóp thành cột hẹp khoảng 100 px, mỗi dòng 2–3 chữ (Claude có ảnh chụp). Toàn màn thì bình thường.

## Việc phải làm

### A. Máy chủ (`app/agent/minh_hoa/kiem.py`)
Thêm quy tắc **không trộn giá trị ca với giá trị giả định** trong cùng một mảng chữ (`phu_de`, `so_hien`, chú thích…). Mảng nào có phần tử phụ thuộc tham số (`theo_tham_so: true`, kể cả bên trong `o_theo_khoang.gia_tri`) thì:
- (a) mọi `o` trong mảng đó trỏ tới **cùng tên cột** (ví dụ `crcl`) cũng phải `theo_tham_so: true`; nếu không thì từ chối `tron_gia_tri_ca_va_gia_dinh:<vị trí>`;
- (b) có `o_theo_khoang` phụ thuộc tham số thì mảng phải có ít nhất một `o` hiện chính giá trị dùng để tra (cùng `ds`/`cot`, `theo_tham_so: true`), để người đọc biết mức liều đang ứng với CrCl nào. Thiếu thì từ chối `thieu_gia_tri_tra:<vị trí>`.

Lời từ chối gửi LLM phải có gợi ý cách sửa. Ví dụ: "Dùng CrCl theo tham số trong cùng câu, hoặc tách số của ca sang một dòng khác".

Thêm vào kỹ năng (`config/prompts/ky_nang_minh_hoa.v1.md`) mẫu đúng:
- `"CrCl đang xem: " {o theo_tham_so} " mL/min — mức liều: " {o_theo_khoang …}`;
- số của ca để ở dòng riêng.

Sửa ví dụ 1 trong kỹ năng nếu đang vi phạm.

### B. Web (`web/src/features/minh-hoa/**`)
1. `kiemDacTa` áp đúng hai quy tắc (a) và (b), để khối cũ hoặc khối không qua máy chủ cũng bị chặn.
2. Phần tử chữ phụ thuộc tham số: khi điều khiển khác giá trị mặc định thì hiện kiểu "giả định" ngay tại phần tử đó (nhãn nhỏ hoặc gạch chân chấm, không chỉ bằng màu).
3. **Bố cục khung hẹp:** ở bề rộng < 480 px, phụ đề và ô `so_hien` chiếm hết chiều ngang (xếp dọc), không bị bóp thành cột. Kiểm ở 320 px và 399 px: không có dòng nào dưới 20 ký tự do bị bóp; không tràn ngang.

## Test
- **Python (`tests/agent/test_minh_hoa_kiem.py`):**
  - mảng có `o` crcl của ca + `o_theo_khoang` theo tham số → `tron_gia_tri_ca_va_gia_dinh`;
  - `o_theo_khoang` theo tham số mà thiếu `o` theo tham số → `thieu_gia_tri_tra`;
  - mẫu đúng → đạt;
  - 3 mẫu VZ0, các ví dụ trong kỹ năng, và khối thật `web/src/features/minh-hoa/mau/khoi-that-demo02.json` (khối này **phải bị từ chối** với lý do mới) đều cho kết quả đúng như trên.
- **Web (vitest):** cùng các ca trên cho `kiemDacTa`. Test bố cục chạy tĩnh (lớp CSS) cho phụ đề ở khung hẹp.
- Sửa mẫu `khoi-that-demo02.json` thành bản đúng quy tắc (đặt tên rõ là đã chỉnh) để mock và demo dùng. Giữ bản gốc dưới tên `khoi-that-demo02-vi-pham.json` cho test từ chối.

## Tệp
Được sửa:
- `app/agent/minh_hoa/kiem.py`;
- `config/prompts/ky_nang_minh_hoa.v1.md`;
- `tests/agent/test_minh_hoa_kiem.py`, `tests/agent/test_minh_hoa_do_thi.py` (nếu ví dụ đổi);
- `web/src/features/minh-hoa/**`, `web/src/api/mock.ts`.

Báo cáo ghi vào `plan/briefs/VZ1-fix-1-bao-cao.md`.

Cấm:
- `app/agent/nodes.py`, `gateway.py`, `asker.py`, `app/api/**`, `data/**`, `plan/**` (trừ báo cáo);
- sửa `style-guard.test.ts`, `safety.test.ts`;
- thêm gói, dùng mạng, commit.

**RAM:** pytest chỉ 2 tệp trên (từng tệp); `vitest run` một lần.

## Nghiệm thu (Claude chạy)
```
uv run ruff check app tests && uv run ruff format --check app tests/agent
uv run pytest -q -p no:cacheprovider tests/agent
cd web && npx tsc -b && npx oxlint && npx vitest run && npx vite build
```
Sau đó Claude chạy lại e2e trên trình duyệt. Đạt khi:
- kéo thanh thì phụ đề ghi CrCl đang xem khớp với mức liều;
- số của ca nằm ở dòng riêng;
- khung chat 399 px không bị bóp chữ.
