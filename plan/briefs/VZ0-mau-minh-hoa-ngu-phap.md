# VZ0 – Trang mẫu minh hoạ tương tác theo ngữ pháp `mh-0`

Người làm: agy Gemini 4 Neon high (**không gọi công cụ shell**; Claude tự chạy tsc, oxlint, vitest, script Python khi review).
Đọc trước: `AGENTS.md`; `plan/plan-1.11-bo-sung-ngu-phap-minh-hoa.md` (**bắt buộc, toàn bộ**); `plan/plan-1.11-tracer-va-visualizer.md` mục B.5, B.6; `plan/plan-1.4-he-thong-thiet-ke.md`; `web/src/features/charts/LabTrendChart.tsx` (cách vẽ SVG hiện có); `web/src/components/ui/dialog.tsx` và `ClinicalMarkdown.tsx` (hộp thoại toàn màn của UI1).

## Mục tiêu

Một trang **chỉ chạy ở chế độ dev** để chủ kho và dược sĩ xem cảm giác "AI tự dựng hình tương tác" trước khi làm thật. Trang vẽ 3 hình **từ đặc tả JSON theo ngữ pháp `mh-0`**, không viết riêng từng biểu đồ: cùng một bộ vẽ đọc đặc tả + bộ dữ liệu rồi dựng hình. Cảm giác tương tác như ví dụ ChatGPT chủ kho gửi (thanh kéo mượt, số đổi theo thanh, nút chọn, nút đặt lại, công thức bên dưới).

## Phần 1 – Script dữ liệu mẫu (Python)

Tạo `tools/xuat_mau_minh_hoa.py`. Claude sẽ chạy: `KB_SOURCE=file uv run python tools/xuat_mau_minh_hoa.py`. Script ghi 3 tệp vào `web/src/features/minh-hoa/mau/` (mỗi tệp = `{ "dac_ta": {...}, "bo_du_lieu": [{ "ma": "ds-n", "cot": [{ "ten", "kieu", "don_vi" }], "dong": [...] }] }`):

1. `lieu-meropenem-crcl.json` – ca `DEMO-02` (đọc từ `data/mock/demo/DEMO-02.json`):
   - `ds-1`: các mức của meropenem trong `data/kb/quy_tac_lieu_than.json` (`crcl_tu`, `crcl_den`, `can_chinh`, `khuyen_cao`).
   - `ds-2`: **lưới tính sẵn**: creatinin từ 50 đến 400 µmol/L bước 5 × `loai_can_nang` ∈ {`thuc_te`, `ly_tuong`, `hieu_chinh`}; mỗi dòng có `crcl` tính bằng **`app.calc.renal.cockcroft_gault`** (không tự viết công thức) và `khuyen_cao` chọn bằng **`app.rules.renal_dose.select_renal_tier`**. Dòng nào hàm báo lỗi/thiếu dữ liệu thì bỏ.
   - `ds-3`: một dòng số liệu thật của ca (creatinin, cân nặng, CrCl hiện tại).
   - Đặc tả như ví dụ ở mục 2 của tệp bổ sung, thêm `cong_thuc: "cockcroft_gault"` và chuỗi công thức lấy từ `app.calc.hien_thi.CONG_THUC_HIEN_THI` (ghi vào `bo_du_lieu` hoặc trường `cong_thuc_hien_thi` của tệp, **không** để web tự chép công thức).
2. `ma-tran-tuong-tac.json` – chọn một ca trong `data/mock/` có từ 5 đến 8 hoạt chất trong y lệnh; gọi **`app.api.lookup.lookup_interactions`** với danh sách tên đó; `ds-1` gồm mỗi cặp (`thuoc_a`, `thuoc_b`, `muc_do`, `co_che` cắt 200 ký tự, `ma_can_cu`). Đặc tả dùng dấu `o` (ô ma trận), màu theo `muc_do`, điều khiển `loc` theo mức độ.
3. `thong-ke-thang.json` – **số giả lập** (seed cố định, ghi `"gia_lap": true` và phụ đề "Dữ liệu giả lập để xem mẫu"): số y lệnh cần thẩm định theo ngày trong 30 ngày, tách theo 4 khoa giả định ("Khoa A"…"Khoa D"); đặc tả dùng dấu `duong` + `bat_tat` theo khoa + một hình `cot` tổng theo khoa (dùng chung một tệp, 2 đặc tả trong mảng `dac_ta` là được).

Không ghi họ tên, HN, SĐT, CCCD hay địa chỉ vào tệp mẫu. Script in ra số dòng mỗi bộ dữ liệu.

## Phần 2 – Bộ vẽ trên web

Thư mục mới `web/src/features/minh-hoa/`:

- `nguPhap.ts` – kiểu TypeScript của ngữ pháp `mh-0` và hàm `kiemDacTa(dacTa, boDuLieu): { hopLe: true, ... } | { hopLe: false, lyDo: string[] }`. Kiểm: khoá lạ; `ds-n` không có; cột không có hoặc sai kiểu; số tự do ở chỗ phải là tham chiếu ô; chữ (tiêu đề, nhãn) > 120 ký tự hoặc chứa `<`, `http`, `javascript:`, mẫu "ignore previous instructions"; quá 6 lớp, 6 điều khiển, 2.000 điểm; đặc tả > 16 KB. Đặc tả không hợp lệ thì khung hiện thông báo gọn + nút xem bảng, **không vẽ**.
- `dungMoHinh.ts` – **hàm thuần**: (đặc tả, bộ dữ liệu, trạng thái điều khiển) → mô hình vẽ (thang đo, toạ độ từng phần tử, chữ hiển thị). Mọi số trên hình phải đến từ ô dữ liệu; hàm này không được tạo số nào ngoài toạ độ và vạch chia trục.
- `VeSvg.tsx` – vẽ mô hình bằng JSX SVG; hỗ trợ các dấu `duong`, `vung`, `cot`, `diem`, `o`, `dai`, `quy_tac`, `chu`. Di chuột / focus vào phần tử thì hiện giá trị và nguồn.
- `KhungMinhHoa.tsx` – khung giống B.6 plan 1.11: tiêu đề, phụ đề (tham chiếu ô), nút mở rộng toàn màn (dùng lại hộp thoại của UI1), nút "Xem dạng bảng" (bảng đúng số của các bộ dữ liệu), vùng điều khiển (`thanh_keo` có phím mũi tên, `chon_mot`, `bat_tat`, `loc`, `dat_lai`), dòng `so_hien`, dòng công thức, dòng nguồn, nhãn cố định "Minh hoạ, không phải khuyến cáo". Điểm giả định khác màu, nét đứt, có chữ "giả định"; khi thanh kéo ở giá trị của ca thì không hiện chữ "giả định".
- `MauMinhHoaPage.tsx` – trang hiện 3 tệp mẫu (import JSON tĩnh).
- Route `/app/mau-minh-hoa` trong `web/src/app/router.tsx`, **chỉ đăng ký khi `import.meta.env.DEV`**.
- Màu, chữ, viền theo plan 1.4, chạy cả sáng và tối (dùng token sẵn có trong `web/src/styles`); không phân biệt chỉ bằng màu (thêm nét/ký hiệu/nhãn); vùng chạm điều khiển ≥ 32 px; hình co theo bề rộng khung (tối thiểu 320 px không tràn ngang).

## Test (vitest, chỉ hàm thuần – kho chưa có jsdom, không được thêm gói)

`web/src/features/minh-hoa/__tests__/`:
- `kiemDacTa`: 3 tệp mẫu hợp lệ; ít nhất 8 đặc tả hỏng bị bỏ đúng lý do (khoá lạ, `ds-9` không có, cột sai, số tự do trong `phu_de`, chữ có `<script`, `javascript:`, quá 2.000 điểm, chèn lệnh trong tiêu đề).
- `dungMoHinh`: với tệp meropenem, đặt creatinin = giá trị của ca → điểm nằm đúng ở `crcl` của dòng tương ứng trong `ds-2` và `so_hien` = `khuyen_cao` của dòng đó; kéo tới 120 → điểm sang mức khác đúng theo `ds-2`; đổi `loai_can_nang` → đổi theo đúng dòng. Mọi chữ số xuất hiện trong chữ hiển thị đều có trong bộ dữ liệu.
- Ma trận: số ô = số cặp; lọc theo mức độ chỉ còn đúng các cặp đó.

## Tệp

Được tạo/sửa: `tools/xuat_mau_minh_hoa.py`, `web/src/features/minh-hoa/**`, `web/src/app/router.tsx` (chỉ thêm route dev), `web/tsconfig.app.json` (chỉ được thêm `"resolveJsonModule": true` nếu tsc cần để import JSON; ghi vào báo cáo). Báo cáo: `plan/briefs/VZ0-bao-cao.md` (trạng thái, tệp, điểm lệch, việc chưa làm).
**Cấm:** sửa `app/**`, `tests/**` Python, `data/**`, `plan/plan-1.11-*`, các tệp web khác (kể cả `ClinicalMarkdown.tsx`, `dialog.tsx` – chỉ import); thêm gói npm/PyPI; `innerHTML`, `dangerouslySetInnerHTML`, `eval`, `new Function`, `iframe`; gọi mạng; gọi shell; commit.

## Nghiệm thu (Claude chạy)

```
KB_SOURCE=file uv run python tools/xuat_mau_minh_hoa.py
uv run ruff check tools/xuat_mau_minh_hoa.py && uv run ruff format --check tools/xuat_mau_minh_hoa.py
cd web && npx tsc -b && npx oxlint && npx vitest run
grep -rnE "innerHTML|dangerouslySetInnerHTML|new Function|eval\(" web/src/features/minh-hoa   # phải rỗng
```
Claude kiểm độc lập: tự tính lại CrCl DEMO-02 vài điểm trên lưới; quét tệp mẫu không có định danh; mở `http://localhost:5173/app/mau-minh-hoa` xem sáng/tối, kéo thanh, mở rộng, xem bảng.
