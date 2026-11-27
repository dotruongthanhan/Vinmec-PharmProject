# UI2 – Nút mở rộng ở góc cho hình minh hoạ (đồng bộ với bảng)

Người làm: Codex gpt-6.1-terra high. Được chạy `npx tsc -b`, `npx oxlint`, `npx vitest run`, `npx vite build` trong `web/`. Không cài gói, không mạng, không commit, không đọc `.env`, không đọc `~/.codex`.

## Chủ kho yêu cầu (27/11, có ảnh)

Bảng Markdown trong chat (UI1) có **một nút icon nhỏ ở góc trên phải** (`Maximize2`, "Mở rộng bảng"), giống nút "Expand table" của ứng dụng Claude: hover thì hiện tooltip, bấm thì mở toàn màn.

Khối minh hoạ (`web/src/features/minh-hoa/KhungMinhHoa.tsx`, khoảng dòng 520–560) hiện lại dùng **hàng nút chữ** "Xem dạng bảng" và "Toàn màn" nằm dưới phụ đề. Chủ kho muốn hình **giống bảng**: một nút ở góc, bấm vào để mở rộng.

Trong ảnh chủ kho gửi, tab bộ dữ liệu ở chế độ xem bảng còn hiện mã nội bộ `ds-2 (195 dòng)`, `ds-4`, `ds-3`. Dược sĩ không hiểu các mã này.

## Việc phải làm
1. **Thành phần dùng chung** `web/src/components/ui/expand-button.tsx` (tên tuỳ, tiếng Anh):
   - nút icon `Maximize2` cỡ `size-7`, vùng chạm ≥ 32 px;
   - có `aria-label`;
   - tooltip dùng `Tooltip` sẵn có trong `components/ui/tooltip.tsx` (hoặc `icon-button.tsx` nếu đã gói sẵn tooltip);
   - nhận `label` ("Mở rộng bảng" / "Mở rộng hình");
   - dùng được làm `DialogTrigger asChild`.

   Bảng trong `ClinicalMarkdown.tsx` chuyển sang dùng thành phần này. Giao diện bảng giữ nguyên.
2. **Khối minh hoạ:**
   - Nút mở rộng đặt ở **góc trên phải của khung**, cùng hàng với tiêu đề. Tiêu đề co lại (`min-w-0`), không bị nút đè.
   - Bỏ nút chữ "Toàn màn".
   - "Xem dạng bảng" thành nút icon `Table2` ngay cạnh nút mở rộng: có tooltip "Xem dạng bảng" / "Ẩn bảng", có `aria-pressed`.
   - Không còn hàng nút riêng dưới phụ đề. Phụ đề nằm ngay dưới tiêu đề, dùng hết bề ngang.
   - Hộp thoại toàn màn giữ nguyên như hiện nay. Đóng (Esc hoặc nút X) thì tiêu điểm trả về nút mở rộng.
   - Khối "Không hiển thị được hình" (đặc tả hỏng) giữ nút "Xem dạng bảng" dạng chữ như hiện nay, vì không có hình để mở rộng.
3. **Tab bộ dữ liệu** (`BangDuLieuGoc`, khoảng dòng 60–85):
   - Không hiện mã `ds-n`. Nhãn tab lấy theo thứ tự ưu tiên:
     - (a) tên mô tả nếu bộ dữ liệu có;
     - (b) suy từ cột: có `creatinin` + `crcl` nhiều dòng → "Lưới CrCl theo creatinin"; 1 dòng → "Giá trị của ca"; có `khuyen_cao` → "Mức liều"; có `thuoc_a`/`thuoc_b` → "Cặp tương tác";
     - (c) "Bảng 1", "Bảng 2"… theo thứ tự.
   - Giữ "(N dòng)".
   - Mã `ds-n` chỉ để trong `title` hoặc `data-` cho người phát triển.
4. Không đổi gì khác: thanh kéo, phụ đề, logic dựng hình, ngân sách hiệu năng VZ1b.

## Test (vitest)
- Bảng vẫn có nút `aria-label="Mở rộng bảng"`. Hình có nút `aria-label="Mở rộng hình"`. Cả hai dùng chung thành phần mới (kiểm import hoặc `data-` chung).
- Khối minh hoạ hợp lệ không còn chữ "Toàn màn". Có nút `Table2` với `aria-pressed`.
- Tab bộ dữ liệu của `mau/khoi-that-demo02.json` không chứa chuỗi `ds-` trong phần chữ hiển thị. Nhãn lần lượt là "Lưới CrCl theo creatinin", "Mức liều", "Giá trị của ca" (theo thứ tự có trong khối).
- `style-guard.test.ts`, `safety.test.ts` vẫn qua, không sửa hai tệp này.

## Tệp
Được sửa/tạo:
- `web/src/components/ui/expand-button.tsx` (mới);
- `web/src/components/ui/ClinicalMarkdown.tsx` (chỉ đổi sang nút dùng chung);
- `web/src/features/minh-hoa/**`;
- test trong `web/src/**/__tests__/`.

Báo cáo ghi vào `plan/briefs/UI2-bao-cao.md`.

Cấm:
- `app/**`, `tests/**` Python, `data/**`, `plan/**` (trừ báo cáo);
- thêm gói, `innerHTML`, `dangerouslySetInnerHTML`, `eval`, `iframe`;
- dùng mạng, commit.

`vitest run` chỉ chạy một lần cho cả bộ (RAM).

## Nghiệm thu (Claude chạy)
```
cd web && npx tsc -b && npx oxlint && npx vitest run && npx vite build
```
Sau đó Claude kiểm trên trình duyệt:
- khối minh hoạ ở khung chat 399 px có nút ở góc, tooltip hiện khi rê chuột;
- bấm nút thì mở toàn màn; Esc đóng và trả tiêu điểm về nút;
- tab bảng có tên dễ hiểu.
