# T98 – Báo cáo thực hiện: Tiến trình phân tích AI (giao diện web)

## File đã tạo / sửa

- `web/src/api/types.ts`: thêm `TrangThaiBuocAI`, `NguonTomTat`, `BuocAI`; bổ sung `cac_buoc`, `da_chay_ms`, `thuong_le_ms` vào `KetQuaAI` (bắt buộc ở kiểu dữ liệu để mọi nơi dựng đều có mặc định).
- `web/src/api/client.ts`: thêm `normalizeKetQuaAI` chuẩn hoá phản hồi `startAi` và `getAi` (chịu được API cũ thiếu `cac_buoc`, `da_chay_ms`, `thuong_le_ms`, `nguon`, trả mặc định `[]` / `null`).
- `web/src/api/mock.ts`: mô phỏng chuỗi bước `thu_thap_nguon` → `tong_hop_1` → `kiem_chung_1` theo thời gian, kèm `nguon`, `da_chay_ms`, `thuong_le_ms` (`25_000` ms khi `aiDelayMs > 0`), và mô phỏng lỗi ở bước tổng hợp trên `DEMO-04` ở lần chạy đầu (bấm "Thử lại" sẽ chạy lại thành công), đồng thời hỗ trợ `failAiCases` trong `MockClientOptions`.
- `web/src/lib/aiReview.ts`: thêm các hàm thuần `formatAiDuration`, `formatAiElapsedClock`, `formatAiTypicalRange`, `evaluateSlowAi`, `formatStepStatusAnnouncement`, `pickStepStatusAnnouncement` và hằng `AI_STEP_SLOW_MS`, `AI_STEP_STATUS_LABELS`.
- `web/src/state/useAiReview.ts`: đổi `AI_POLL_INTERVAL_MS` từ `2000` sang `1500`; trả thêm `cacBuoc`, `daChayMs`, `thuongLeMs`; tạm dừng hỏi khi `document.hidden` và hỏi lại ngay khi tab hiện (`visibilitychange`); tách `runAiReviewSession` để giữ nguyên trần 120 giây, chống đua ca và dễ kiểm thử trong Vitest môi trường `node`.
- `web/src/features/findings/AiProgressPanel.tsx`: thành phần mới hiển thị tiến trình từng bước (`Circle`, `LoaderCircle` với `motion-safe:animate-spin`, `CircleCheck`, `CircleAlert`, `CircleSlash`), nhãn nguồn dạng `"nhãn số"`, đồng hồ tổng `aria-hidden` nội suy mỗi `500 ms` bằng `setInterval`, dòng `"thường a–b s"`, cảnh báo chậm (`role="status"`), dòng cuối `"Bảng bên dưới là kết quả của bộ luật."`, vùng `aria-live="polite"` chỉ đọc `"Bước <tên>: <trạng thái>"` khi đổi trạng thái, nhánh `loi` với `ly_do`/`goi_y`/nút `"Thử lại"`, nhánh `xong` thu gọn mặc định kèm nút `"Xem các bước (n)"`/`"Ẩn các bước"` (`aria-expanded`, `aria-controls`).
- `web/src/features/findings/AiStatusBar.tsx`: giữ nguyên chữ ký props cũ (thêm prop tuỳ chọn `cacBuoc`, `daChayMs`, `thuongLeMs`) và uỷ quyền hiển thị cho `AiProgressPanel` ở các nhánh `dang_chay`, `xong`, `loi`.
- `web/src/features/order-detail/OrderDetailView.tsx`: nhận thêm prop tuỳ chọn `aiCacBuoc`, `aiDaChayMs`, `aiThuongLeMs` và truyền xuống `AiStatusBar`.
- `web/src/app/WorkspacePage.tsx`: truyền thêm `aiCacBuoc`, `aiDaChayMs`, `aiThuongLeMs` từ `useAiReview` xuống `OrderDetailView`.
- `web/src/__tests__/aiReview.test.ts`: cập nhật 4 đối tượng mẫu `KetQuaAI` cho đủ 3 trường mới; bổ sung test chuẩn hoá API thiếu trường, `MockClient` chuỗi bước và ca lỗi, và các hàm thuần thời gian / ước lượng / cờ chậm.
- `web/src/__tests__/aiProgressPanel.test.tsx`: kiểm thử `AiProgressPanel`, `AiStatusBar`, 5 trạng thái bước, chậm, lỗi (`ly_do`, `goi_y`, `"Thử lại"`), thu gọn/mở, `cac_buoc` rỗng, thoát chuỗi HTML an toàn, cập nhật thông báo bước, `runAiReviewSession` hỏi `1500 ms`, tạm dừng khi `document.hidden`, và đổi ca nhanh không lẫn bước.

## Quyết định tự chọn

- **Truyền prop từ `WorkspacePage.tsx`**: ngoài `OrderDetailView.tsx`, đã truyền thêm `aiCacBuoc`, `aiDaChayMs`, `aiThuongLeMs` tại chỗ gọi `OrderDetailView` trong `WorkspacePage.tsx` (giữ các prop này tuỳ chọn trên `OrderDetailView` và `AiStatusBar` để không làm gãy nơi gọi hoặc test khác nếu có).
- **Đồng hồ tổng và bước chạy**: dùng `formatAiElapsedClock` (giây nguyên `Math.floor(ms / 1000)` + `s`) cho đồng hồ tổng nội suy mỗi 500 ms để tránh nhảy chữ `.5s` liên tục, và `formatAiDuration` (`1,2s` dưới 10 s, làm tròn giây `14s` từ 10 s trở lên) cho thời lượng từng bước.
- **Khoảng "thường a–b s"**: làm tròn `0,7×` và `1,5×` trung vị về bội số `5 s`, kẹp dưới tối thiểu `5 s` và `high >= low`; nếu `low === high` thì hiện `thường <low> s`.
- **Ca lỗi trong mock**: chọn `DEMO-04` lỗi ở bước `tong_hop_1` trong lần chạy đầu của chế độ mock (và thành công khi bấm "Thử lại"), đồng thời hỗ trợ tuỳ chọn `failAiCases` trong `MockClientOptions` cho test; giữ `DEMO-02`, `DEMO-05`, `DEMO-06` hoàn tất bình thường như test cũ.
- **Kiểm thử trong môi trường `node` của Vitest**: kho chưa cài `jsdom` / `@testing-library/react`, nên `aiProgressPanel.test.tsx` dùng `renderToStaticMarkup` (`react-dom/server`) cho phần render/ARIA/XSS và `runAiReviewSession` + `vi.useFakeTimers()` + `vi.stubGlobal('document', ...)` cho luồng polling `1500 ms`, ẩn tab và chống đua ca.
- **Sửa nhỏ phát sinh trong `WorkspacePage.tsx`**: không có sửa khác ngoài 3 prop truyền xuống `OrderDetailView`.

## Điều chưa chắc

- Do ràng buộc không gọi shell trong lượt này, chưa chạy trực tiếp `npm run test`, `npx tsc --noEmit` và `npm run lint` (`oxlint`).
- Do không dùng công cụ shell để liệt kê toàn bộ thư mục `web/src/__tests__/`, chưa đọc được hết mọi tệp test khác ngoài các tệp đã kiểm tra (`aiReview.test.ts`, `api.test.ts`, `assistant.test.ts`, `authClient.test.ts`, `caseRefresh.test.ts`, `displayFormat.test.ts`, `orderDetail.test.ts`, `orders.test.ts`, `presentation.test.ts`, `queue.test.ts`, `safety.test.ts`); nếu có tệp test cũ khác tự dựng đối tượng `KetQuaAI` thiếu 3 trường mới hoặc kiểm tra hằng `2000`, Claude cần kiểm tra khi chạy `tsc` / `vitest`.
- Bố cục thực tế ở chiều rộng `360 px` trên trình duyệt chưa được chạy kiểm tra trực quan (đã dùng `flex-wrap`, `min-w-0`, `break-words` trên dòng bước và nhóm nguồn để tránh tràn ngang).
