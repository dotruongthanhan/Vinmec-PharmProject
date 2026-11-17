# Báo cáo T23-fix-1

TRẠNG THÁI: XONG

Thực hiện phần A, nghiệm thu A, rồi mới triển khai phần B. Chỉ thay đổi trong `web/`; không sửa backend hay tài liệu kế hoạch, không đọc `.env` gốc, không commit/push hay thay đổi nhánh. Dữ liệu kiểm tra hoàn toàn từ bản giả lập có sẵn.

## Phần A

| Mục | Kết quả |
| --- | --- |
| A1–A2 | Bỏ import không dùng; gắn trích dẫn theo chỉ số bước tài liệu đầu tiên, không gán lại biến trong render; trạng thái tải nguồn suy ra từ khoá yêu cầu; diễn hoạt cập nhật bằng các sự kiện hẹn giờ có huỷ khi dọn dẹp. Không tắt luật lint. |
| A3 | Bỏ ký tự mũi tên trong chú thích `labChart.ts`; giữ nguyên test style guard. |
| A4 | Mã nguồn vốn đã là NFC và import Fraunces đã chứa tập tiếng Việt, nên đã loại trừ hai nguyên nhân này. Thay Fraunces bằng phông có chân Cambria, dự phòng Noto Serif/Times New Roman/serif. Kiểm tra cmap của Cambria và Times New Roman: đủ toàn bộ U+1EA0–U+1EF9 và các chữ Việt bổ sung. Xác nhận trực quan ba tiêu đề và thêm test NFC quét nguồn. Không khẳng định đã xác định lỗi nội bộ của Fraunces. |
| A5 | Lưu đúng một cờ demo `pharm_review_demo=1` trong bộ nhớ phiên; khởi tạo trước khi bảo vệ tuyến; đăng xuất xoá cờ. Cờ không bật demo nếu đã cấu hình xác thực. Có test hàm quyết định và mở thẳng/tải lại chi tiết bằng trình duyệt. |
| A6–A7 | Bảng fixed layout, cột thuốc co và có dấu ba chấm. Đủ thứ tự cột theo hợp đồng v1.2, thuốc đầu và `+n`, tóm tắt là chú giải dòng. Thời điểm/mã/người bệnh/thuốc tuỳ chọn; null hoặc vắng để trống. Dữ liệu mẫu sao từ chi tiết sáu ca hiện có. Tìm kiếm hỗ trợ mảng thuốc. Có test dựng thành phần thật kiểm null/vắng và `+n`. |
| A8 | Dải người bệnh: hàng thông tin và điều hướng căn phải; hàng dị ứng/chẩn đoán/chỉ số. Nút trước/sau dùng biểu tượng kèm nhãn truy cập khi hẹp. Đường dẫn giữ nguyên mã y lệnh. |
| A9 | Tên yếu tố đầy đủ, xuống dòng; sáu ô cùng chiều cao, bố cục theo vùng chứa. |
| A10 | Xoá tám thành phần chết và ba tài sản không còn nhập. Giữ `App.tsx` vì `main.tsx` dùng; giữ `lib/queue.ts` vì `useCases.ts` dùng cập nhật phản hồi và `prefs.ts` dùng kiểu bộ lọc. Giữ test logic tương ứng. |

Kiểm tra thêm theo mục 3.2 của T23 ở 1440, 1180, 900, 390px: trang chủ, đăng nhập, danh sách, chi tiết DEMO-02 và trợ lý. Đã sửa tràn ngang trang chủ do nhãn tài liệu dài, thẻ chi tiết bị cắt trên điện thoại và chiều cao ô yếu tố không đều. Bỏ biểu tượng lấp lánh cạnh nhãn bật AI/trạng thái hoàn tất; giữ ở nhãn nguồn gốc đã kiểm chứng theo ngoại lệ được phép. Nạp lười bàn làm việc để build không còn cảnh báo chunk lớn.

Tại thời điểm kết thúc A, trước khi bắt đầu B:

| Lệnh trong `web/` | Kết quả |
| --- | --- |
| `npm run build` | Đạt, không cảnh báo chunk lớn |
| `npm run lint` | Đạt, 0 cảnh báo |
| `npx vitest run` | 15 tệp, 77/77 test qua |
| `node qa/browser-check.mjs a` | Đã dựng năm màn ở bốn kích thước; không tràn ngang trang/bảng danh sách; mỗi dòng bảng 44px; sáu ô bằng chiều cao; F5 giữ `/app/y-lenh/DEMO-02`; không lỗi JavaScript |

Ảnh A: [thư mục ảnh](artifacts/a/), [số đo](artifacts/a/layout.json). Ba tiêu đề được chụp riêng:

- [Tất cả y lệnh](artifacts/a/heading-orders.png)
- [Truy vết đầy đủ](artifacts/a/heading-landing.png)
- [Đối chiếu và quyết định](artifacts/a/heading-login.png)

## Phần B

- Ba lựa chọn Sáng/Tối/Theo hệ thống; lưu qua `prefs.ts`; thuộc tính `data-theme` trên html. `useSyncExternalStore` nhận thay đổi thiết lập hệ điều hành; cây trạng thái không bị dựng lại khi đổi màu.
- Đoạn script trước React trong `index.html`, có `try/catch`, giá trị hỏng/chặn bộ nhớ theo hệ thống; đồng bộ `color-scheme` và meta `theme-color`.
- Thanh phân đoạn ở trang chủ, đăng nhập và đáy thanh bên; khi thanh bên thu gọn, nút có chú giải mở popover.
- Định nghĩa đầy đủ biến màu cho tối, ba bậc nền/bề mặt/bề mặt nổi, chữ chính không trắng tuyệt đối, bảy bộ màu nghĩa nền trầm. Nút chính, tooltip, lớp phủ và viền tiêu điểm dùng biến riêng.
- Hàm tương phản thuần theo WCAG; 42 kiểm tra bao gồm màu nguồn thực của cả hai chế độ, bảy bộ nghĩa, chữ chính/phụ, nút, hover và viền tiêu điểm. Không nới ngưỡng.
- Rà soát độc lập phát hiện biểu đồ bị thu nhỏ bởi breakpoint theo màn hình: đã sửa thành một biểu đồ trọn hàng, đo vùng vẽ bằng ResizeObserver, nhãn 12px và tách nhãn thời điểm kê khỏi giá trị. Test trình duyệt tái hiện chữ 5,839px trước sửa rồi qua sau sửa. Hai cặp màu phụ chưa đủ tương phản cũng có test thất bại trước khi chỉnh token rồi qua.
- Test quét màu ngoài `theme.css`, quyết định chế độ, bootstrap trước React, bộ nhớ bị chặn, NFC và toàn bộ test cũ đều qua.

Nghiệm thu cuối B:

| Lệnh trong `web/` | Kết quả |
| --- | --- |
| `npm run build` | Đạt, không cảnh báo |
| `npm run lint` | Đạt, 0 cảnh báo |
| `npx vitest run` | 20 tệp, 141/141 test qua |
| `node qa/browser-check.mjs b` | Đạt: 57 lượt chuyển lựa chọn, bốn kích thước, 0 lỗi JavaScript, 0 lỗi số đo |

Kiểm tra trình duyệt B còn bao gồm: thay đổi sáng/tối của hệ thống khi chọn Theo hệ thống; bộ lọc MEROPENEM và hội thoại giữ nguyên; nguồn trong hộp thoại và trợ lý; biểu đồ ở hai chế độ; menu màu khi thanh bên thu gọn; tải lại tối ở cả bốn kích thước với màu tối ngay từ lần đầu React thêm nội dung. Meta màu khớp biến nền, `color-scheme` khớp chế độ. Các bảng lâm sàng chi tiết giữ vùng cuộn nội bộ có sẵn; trang và bảng danh sách không tràn ngang.

Ảnh B: [thư mục ảnh](artifacts/b/), [kết quả số đo và từng chế độ](artifacts/b/layout.json). Ví dụ: [biểu đồ tối](artifacts/b/labs-1440-dark.png), [nguồn tối](artifacts/b/source-dialog-dark.png), [thanh bên thu gọn](artifacts/b/sidebar-collapsed-light.png), [tải lại tối 390px](artifacts/b/reload-dark-390.png).

## File đã tạo / sửa trong lần xử lý này

Tạo:

- `src/lib/demoSession.ts`, `src/lib/theme.ts`, `src/lib/contrast.ts`.
- `src/features/theme/ThemeProvider.tsx`, `ThemeControl.tsx`, `useTheme.ts`.
- `src/__tests__/demoSession.test.ts`, `unicode.test.ts`, `ordersTable.test.ts`, `theme.test.ts`, `theme-bootstrap.test.ts`, `theme-guard.test.ts`, `contrast.test.ts`.
- `qa/browser-check.mjs`, báo cáo này và ảnh/số đo trong `qa/artifacts/a/`, `qa/artifacts/b/`.

Sửa (một số tệp đã tồn tại dưới dạng thay đổi chưa commit từ T23):

- `index.html`, `package.json`, `package-lock.json` (hai tệp package chỉ để gỡ Fraunces trong A4).
- `src/App.tsx`; `src/api/types.ts`, `mockData.ts`.
- `src/app/AppShell.tsx`, `TopBar.tsx`, `WorkspacePage.tsx`, `router.tsx`.
- `src/components/ui/button.tsx`, `dialog.tsx`, `popover.tsx`, `tooltip.tsx`, `toaster.tsx`.
- `src/features/auth/AuthProvider.tsx`, `LoginPage.tsx`; `src/features/landing/HeroAnimation.tsx`, `LandingPage.tsx`.
- `src/features/assistant/AssistantPanel.tsx`; `src/features/sidebar/SidebarNav.tsx`.
- `src/features/order-detail/OrderDetailView.tsx`, `OrderHeaderStrip.tsx`, `SixFactorStrip.tsx`.
- `src/features/findings/EvidenceList.tsx`, `AiStatusBar.tsx`; `src/features/charts/LabTrendChart.tsx`.
- `src/lib/labChart.ts`, `orders.ts`, `prefs.ts`; `src/styles/globals.css`, `theme.css`.
- `src/__tests__/orders.test.ts`, `safety.test.ts` (ngoại lệ lưu trữ phiên chỉ cho module cờ demo; giữ nguyên các luật cấm thực thi động/chèn HTML).

Xoá sau khi tìm tham chiếu:

- `src/features/queue/QueuePanel.tsx`, `case-header/CaseHeader.tsx`, `summary/SummarySection.tsx`, `summary/MetricCard.tsx`, `detail/DetailTabs.tsx`, `assistant/ChatPanel.tsx`, `findings/FindingsSection.tsx`, `findings/SourceList.tsx`.
- `src/assets/hero.png`, `react.svg`, `vite.svg`.

## Điểm lệch, giới hạn và việc chưa làm

- Cài `@fontsource-variable/noto-serif` được A4 cho phép nhưng bị môi trường từ chối truy cập registry (`EACCES`). Không có gói mới được thêm; dùng phông hệ thống đã kiểm tra đủ chữ Việt, gỡ Fraunces. Đã xác nhận ba tiêu đề bằng ảnh; chưa phân tích sâu lỗi nội bộ của Fraunces.
- Công cụ mở trình duyệt có giao diện bị chặn quyền; dùng Chromium headless cục bộ sẵn có để dựng và đo giao diện. Script QA cần headless shell trong máy, có điều khiển khung vẽ vì môi trường không cấp GPU thông thường.
- `modern-web-guidance` đã được tìm ngoại tuyến cho bảng đáp ứng nhưng chưa có cache (`ENOTCACHED`); không tải công cụ hay tra cứu mạng ngoài phạm vi. Không có hướng dẫn từ công cụ này được áp dụng.
- Backend kiểm tra mã phiên Supabase và task thêm trường API là việc của task khác; không kiểm chứng đăng nhập mạng và không sửa backend. Không thay công thức, ngưỡng, liều hay nội dung y khoa mẫu.
- Không còn việc chưa làm trong phạm vi triển khai brief. Không có yêu cầu người dùng xác nhận thêm.
