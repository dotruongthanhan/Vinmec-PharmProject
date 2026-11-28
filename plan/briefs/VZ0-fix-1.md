# VZ0-fix-1 – Sửa sau review VZ0

Người làm: agy Gemini 4 Neon high (**không gọi shell**). Đọc: `plan/briefs/VZ0-mau-minh-hoa-ngu-phap.md`, `plan/briefs/VZ0-bao-cao.md`, `web/src/__tests__/style-guard.test.ts`.

## Claude đã chạy (26/11 23:40)

- `uv run python tools/xuat_mau_minh_hoa.py`: đạt (216 dòng lưới; Claude tự tính lại 216/216 CrCl khớp; 0 định danh trong tệp mẫu). ruff sạch.
- `npx tsc -b`: **4 lỗi** TS2352 ở `src/features/minh-hoa/__tests__/nguPhap.test.ts` dòng 75, 167, 175, 186 (ép `DacTaMinhHoa` sang `{ phu_de: unknown[] }`… trong khi kiểu là `readonly`).
- `npx vitest run`: 394 qua / **1 trượt**: `style-guard.test.ts` – `VeSvg.tsx` có `style={{ ... }}` chứa thuộc tính màu (`fill`/`stroke`/`color`…).
- `npx oxlint`: cảnh báo mới `react(set-state-in-effect)` ở `KhungMinhHoa.tsx:355`.
- Xem trực quan (sáng, tối, kéo thanh tới 120 µmol/L → 28,3, mức 26–50, nhãn giả định; toàn màn; xem bảng): **chạy đúng**.

## Sửa

1. **tsc:** sửa 4 chỗ ép kiểu trong test (ví dụ qua `unknown`, hoặc dựng đối tượng mới bằng spread). Không đổi kiểu `readonly` của ngữ pháp.
2. **style-guard:** bỏ mọi thuộc tính màu trong `style={{}}` ở `VeSvg.tsx` (và tệp khác trong `minh-hoa` nếu có). Dùng class Tailwind theo token (`fill-…`, `stroke-…`, `text-…`) như các component khác đang làm, hoặc thuộc tính SVG trỏ token đã có. Không thêm mã màu thô.
3. **oxlint:** bỏ `setState` đồng bộ trong effect ở `KhungMinhHoa.tsx:355` (suy ra khi render hoặc đặt khi sự kiện xảy ra). Không để lại cảnh báo mới nào trong `minh-hoa`.
4. **Hình liều thận:**
   - Nhãn số của mốc ca ("16,0") đang đè lên nhãn mức "10–25": dời nhãn để không chồng nhau (ví dụ đặt dưới dải, hoặc né theo toạ độ).
   - Nhãn khuyến cáo trong dải bị cắt "…": cho xuống tối đa 2 dòng; vẫn dài thì cắt và để đủ chữ trong tooltip / focus (đã có).
   - **Khe 25–26 (và mọi khe giữa hai mức):** luật `select_renal_tier` xếp CrCl > 25 vào mức 26–50, nên điểm 25,97 hiện rơi vào khoảng trống giữa hai dải. Script thêm vào `ds-1` hai cột `bien_ve_tu`, `bien_ve_den` do **code** suy ra theo đúng ngữ nghĩa của `select_renal_tier` (với meropenem: >50; >25–50; 10–25; <10), giữ nguyên `crcl_tu`/`crcl_den` để làm nhãn. Đặc tả dùng `bien_ve_*` cho `x_tu`/`x_den`. Test `dungMoHinh`: mọi dòng `ds-2` đều có điểm nằm trong đúng dải có `khuyen_cao` trùng với dòng đó.
5. **Ma trận tương tác:**
   - Ô co giãn theo bề rộng khung (tối thiểu 32 px, tối đa 72 px), để khi toàn màn không còn nhỏ, lệch trái.
   - Script ưu tiên ca có **ít nhất 1 cặp `nghiem_trong` hoặc `chong_chi_dinh`** (theo mức độ mà `lookup_interactions` trả), rồi mới tới ca có 5–8 hoạt chất. In ra lý do chọn ca. Không có ca nào như vậy thì giữ cách cũ và ghi vào báo cáo.

## Tệp

Được sửa: `tools/xuat_mau_minh_hoa.py`, `web/src/features/minh-hoa/**`. Báo cáo: thêm mục "Fix-1" vào cuối `plan/briefs/VZ0-bao-cao.md`.
Cấm: như brief VZ0 (không sửa `style-guard.test.ts`, không thêm gói, không gọi shell, không commit).

## Nghiệm thu (Claude chạy)

```
KB_SOURCE=file uv run python tools/xuat_mau_minh_hoa.py
uv run ruff check tools/xuat_mau_minh_hoa.py && uv run ruff format --check tools/xuat_mau_minh_hoa.py
cd web && npx tsc -b && npx oxlint && npx vitest run
```
tsc 0 lỗi; vitest 0 trượt; oxlint không có cảnh báo trong `src/features/minh-hoa`.
