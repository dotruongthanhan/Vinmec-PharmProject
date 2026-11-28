# T104 – Tab Thẩm định: điều hướng 8 mục ở thanh bên

Đọc `AGENTS.md` trước. Bố cục chốt ở `plan/plan-1.2-giao-dien-ui-ux.md` mục 3.9. Hệ thống thiết kế: `plan/plan-1.4-he-thong-thiet-ke.md` (token màu theo nghĩa đã có: `danger-*`, `missing-*`, `success-*`, `ink-*`, `primary`).

## Bối cảnh

Màn chi tiết ca (`/app/...`) có thanh bên tối `web/src/features/sidebar/SidebarNav.tsx`. Nửa dưới thanh bên hiện là thẻ thông tin người bệnh `PatientSidebarCard` (thu gọn: `PatientCollapsedButton`). Vùng nội dung là `web/src/features/order-detail/OrderDetailView.tsx`, có các tab; tab hiện ở URL `?tab=` (vắng = `tham_dinh`). Tab Thẩm định hiện xếp dọc: dải 7 ô `SixFactorStrip`, `AiStatusBar`, danh sách `FindingCard`, `PassedList`, `InteractionSection`.

`WorkspacePage.tsx` dựng `SidebarNav` (truyền `patient`) và `OrderDetailView`. Trạng thái 7 yếu tố tính bằng `computeSixFactorsStatus` trong `web/src/lib/orderDetail.ts`, từ `displayedFindings` (gộp kết quả luật, AI và phản hồi trong phiên) tính trong `OrderDetailView`.

## Yêu cầu

1. **Thanh bên, chỉ khi đang mở một ca và tab đang là Thẩm định:** thay `PatientSidebarCard` bằng thành phần mới `ReviewFactorNav` (`web/src/features/sidebar/ReviewFactorNav.tsx`). Tab khác hoặc trang danh sách: giữ nguyên thẻ người bệnh như hiện tại.
2. `ReviewFactorNav` hiện 8 mục: **Tổng quan**, rồi 7 yếu tố theo `SIX_FACTOR_DEFINITIONS`. Mỗi mục: số thứ tự (Tổng quan không có số), tên đầy đủ (cho xuống dòng, không cắt chữ), biểu tượng và màu theo trạng thái (dùng lại bộ biểu tượng của `SixFactorStrip`), và số nhận định cần chú ý của yếu tố (ẩn khi bằng 0). Mục Tổng quan hiện tổng số cần chú ý. Mục có ít nhất một nhận định mức Nghiêm trọng được tô nhấn bằng token `danger`. Mục đang chọn có `aria-current="page"` và nền nổi như mục điều hướng chính. Cuối danh sách: dòng nhỏ "N luật đã chạy" (`detail.nhan_dinh.so_luat_da_chay`). Phần tử gốc là `<nav aria-label="Mục thẩm định">`, mỗi mục là `<button>`.
3. **Thanh bên thu gọn (56 px):** thay `PatientCollapsedButton` bằng cột biểu tượng của 8 mục (số hoặc biểu tượng trạng thái), có `Tooltip` hiện tên. Chế độ ngăn kéo (`inDrawer`) dùng bản đầy đủ; chọn mục thì đóng ngăn kéo (`onNavigate`).
4. **Mục đang chọn nằm trên URL** ở tham số `yt`: `tong_quan` hoặc `1`–`7`. Vắng hoặc sai giá trị → Tổng quan. Ghi bằng `setSearchParams(..., { replace: true, state: locationState })` như cách `handleTabChange` đang làm; giữ các tham số khác (`tab`, `yl`). Chọn Tổng quan thì xoá `yt` khỏi URL.
5. **Dùng chung một nguồn tính toán.** Tách phần tính `displayedFindings` → `allAttention`, `allPassed`, `sixFactors` trong `OrderDetailView` thành hook thuần `useReviewFindings` (`web/src/features/order-detail/useReviewFindings.ts`). `WorkspacePage` gọi hook đó với cùng đầu vào để dựng `ReviewFactorNav`. `OrderDetailView` cũng gọi hook này, không còn bản tính riêng. Thêm vào `lib/orderDetail.ts` hàm thuần `factorIndexOf(yeuTo: string): 1..7 | null` (dùng lại logic `matchesFactorIndex`) và hàm đếm số cần chú ý theo yếu tố.
6. **Vùng nội dung tab Thẩm định:**
   - Bỏ section "Bảy yếu tố thẩm định" (`SixFactorStrip`). Không xoá tệp `SixFactorStrip.tsx` nếu còn nơi khác hoặc test dùng; nếu không còn ai dùng thì xoá tệp và test của nó.
   - **Tổng quan (`yt` vắng):** giữ đúng nội dung hiện có (tiêu đề "Nhận định" + huy hiệu, lọc theo thuốc, `AiStatusBar`, bản nháp phản hồi, mọi `FindingCard`, `PassedList`). Mỗi `FindingCard` ở Tổng quan có thêm nút nhỏ "Mở mục N" (N là yếu tố của nhận định) để chuyển `yt=N`. Thêm nút bằng một prop tuỳ chọn của `FindingCard` (ví dụ `onOpenFactor?: () => void`); vắng prop thì không hiện. Không đổi giao diện khác của thẻ. Bỏ `InteractionSection` khỏi Tổng quan.
   - **Yếu tố N:** tiêu đề là tên yếu tố kèm trạng thái, chỉ các `FindingCard` của yếu tố N (vẫn áp dụng lọc theo thuốc), rồi `PassedList` chỉ gồm mục đạt của yếu tố N, mở sẵn khi yếu tố không có nhận định cần chú ý. Yếu tố 4 thêm `InteractionSection` ở cuối. Yếu tố trạng thái `chua_co_luat` hiện khung trống "Chưa có luật cho yếu tố này" (không bao giờ ghi "Đạt"). Không có gì để hiện thì dùng `InlineAlert` tone success như câu hiện có, nhưng nói theo yếu tố.
   - Bản nháp phản hồi (`feedbackDrafts`) không được mất khi đổi mục. Hiện state đã nằm trong `OrderDetailView`; giữ nguyên.
7. **Liên kết cũ phải còn chạy:**
   - Bấm dòng thuốc ở tab Y lệnh (`handleSelectDrugForReview`) → sang Thẩm định, `yt` về Tổng quan.
   - `InteractionSection.onOpenFinding` / `handleOpenFinding`: nếu nhận định không nằm trong mục đang mở thì đổi `yt` sang yếu tố của nó rồi mới cuộn tới `finding-<id>`.
   - "Hỏi về mục này" (`onAskAboutFinding`) không đổi.
8. Đổi tab khác rồi quay lại Thẩm định thì giữ `yt` (nằm trên URL).

## Phạm vi tệp

- Được sửa: `web/src/features/order-detail/**`, `web/src/features/sidebar/**`, `web/src/app/WorkspacePage.tsx`, `web/src/lib/orderDetail.ts`, `web/src/__tests__/**`.
- Cấm: mọi thứ ngoài `web/src`; `web/package.json` và lockfile (không thêm thư viện); `web/src/api/**` (không đổi kiểu API); `LookupWorkspace.tsx`; backend `app/**`.
- Không gọi công cụ shell (không chạy npm, git, hay lệnh nào). Claude sẽ tự chạy kiểm tra.

## Tiêu chí nghiệm thu (Claude chạy trong `web/`)

1. `npx tsc -b` không lỗi; `npm run lint` không lỗi mới; `npx vitest run` toàn bộ qua; `npm run build` qua.
2. Test mới (vitest, `renderToStaticMarkup` hoặc kiểu test đang dùng trong `web/src/__tests__`):
   - `ReviewFactorNav`: đủ 8 mục, đúng thứ tự, mục chọn có `aria-current="page"`, số đếm đúng, mục `chua_co_luat` không chứa chữ "Đạt", có dòng "N luật đã chạy".
   - `SidebarNav`: có `reviewNav` → không còn "Thông tin người bệnh", có "Mục thẩm định"; không có `reviewNav` → thẻ người bệnh như cũ.
   - `factorIndexOf`: "3. Chỉ định…" → 3, "6 · Cơ địa" → 6, chuỗi lạ → null.
   - `OrderDetailView` với `?yt=6` (MemoryRouter `initialEntries`): chỉ hiện thẻ của yếu tố 6, không có `SixFactorStrip`; `?yt=4` có phần tương tác; `?yt=abc` → Tổng quan.
3. Cập nhật các test cũ bị ảnh hưởng (ví dụ test tìm "Bảy yếu tố thẩm định" trong `OrderDetailView`, `orderDetailInteraction.test.tsx`) cho đúng hành vi mới. Không xoá test để cho qua.

## Bảo mật

- Chỉ đổi cách hiển thị dữ liệu đã có; không thêm lời gọi API, không ghi dữ liệu người bệnh vào `localStorage` hay log.
- `yt` là đầu vào từ URL: chỉ nhận đúng tập giá trị hợp lệ, không chèn vào DOM dạng HTML. Không dùng `innerHTML` / `dangerouslySetInnerHTML`.

## Báo cáo

Ghi `plan/briefs/T104-bao-cao.md`: tệp đã đổi, quyết định thiết kế (đặc biệt cách chia sẻ hook), test đã thêm hoặc sửa, việc chưa làm.
