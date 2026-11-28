# Báo cáo T100 – Tiến trình hỏi đáp: giao diện web

## File đã tạo / sửa

### Mã nguồn ứng dụng (`web/src/`)
- `web/src/api/types.ts`: thêm interface `TienTrinhHoiDap { dang_chay: boolean; cac_buoc: BuocAI[]; da_chay_ms: number | null }`.
- `web/src/api/client.ts`:
  - Thêm `getAskProgress(caId: string, init?: { signal?: AbortSignal }): Promise<TienTrinhHoiDap>` vào interface `ReviewApiClient`.
  - Thêm hàm thuần `normalizeTienTrinhHoiDap` chuẩn hoá phản hồi thiếu trường (mặc định `dang_chay: false`, `cac_buoc: []`, `da_chay_ms: null`).
  - Triển khai `ApiClient.getAskProgress`: gọi `GET /cases/{caId}/ask/tien-trinh`, riêng `caId === '__global__'` gọi `GET /ask/tien-trinh`; lỗi mạng/404/HTTP trả mặc định, không ném lỗi lên người dùng.
- `web/src/api/index.ts`: chuyển tiếp `getAskProgress` trong `createLazyMockClient()`.
- `web/src/api/mock.ts`:
  - Theo dõi trạng thái mỗi lượt `ask` trong `askRuns[caId]`, gắn liền thời gian trôi qua (`Date.now() - startedAt`) với `this.askDelayMs`.
  - Triển khai `MockClient.getAskProgress`: trả về các bước thật theo thời gian chờ (`chuan_bi` → `truy_xuat` → `goi_mo_hinh` → `kiem_chung`; riêng `__global__` dùng nhãn `Tổng hợp danh sách y lệnh`), giữ kết quả đã xong 60 giây để web đọc lần cuối, dọn khi bị huỷ; từ khoá `"lỗi"` trong câu hỏi mô phỏng bước `goi_mo_hinh` ở trạng thái `loi` kèm `ly_do`, `goi_y` và `kiem_chung` ở trạng thái `bo_qua`.
- `web/src/state/useChat.ts`:
  - Thêm `ASK_PROGRESS_POLL_INTERVAL_MS = 1000`, `AskProgressSnapshot`, trường tuỳ chọn `cac_buoc?: BuocAI[]` và `da_chay_ms?: number | null` trên biến thể `he_thong` của `ChatMessage`, và `getProgress(caId)` trong `UseChatResult`.
  - Khi `sendingRef` đúng cho một phạm vi: hỏi `getAskProgress` mỗi 1000 ms, tạm dừng khi `document.hidden` và hỏi lại ngay khi tab hiện, huỷ khi gửi xong / `stopQuestion` / đổi `activeCaseId` / `clearChat` / unmount.
  - Khi `POST /ask` trả về (hoặc gặp lỗi không phải abort), đọc `getAskProgress` thêm một lần nữa rồi gắn `cac_buoc` vào tin nhắn trả lời nếu yêu cầu còn hợp lệ theo `requestSeq`. Lịch sử khôi phục từ `getConversations` không có `cac_buoc`.
- `web/src/features/findings/AiStepList.tsx` (mới): tách `AiStepStatusIcon`, `AiStepList` và `toStepStatusMap` từ `AiProgressPanel.tsx` để dùng chung, tránh lặp mã.
- `web/src/features/findings/AiProgressPanel.tsx`: dùng `AiStepList` và `toStepStatusMap` dùng chung.
- `web/src/features/assistant/AssistantPanel.tsx`:
  - Thêm `AssistantLiveProgress` (dùng `AiStepList`, đồng hồ `aria-hidden`, `motion-safe:animate-spin`, vùng `aria-live="polite"` chỉ thông báo khi bước đổi trạng thái) thay cho vòng xoay khi đã có bước; giữ nguyên dòng `"Đang tra cứu dữ liệu và nguồn…"` (với `motion-safe:animate-spin`) khi chưa có bước nào.
  - Thêm `AssistantMessageSteps` dưới tin nhắn trả lời có `cac_buoc` với nút ghost `"Xem các bước (n)"` / `"Ẩn các bước"` (`aria-expanded`, `aria-controls`), mặc định thu gọn.
  - Hiển thị `ly_do` và `goi_y` của bước lỗi ngay trong khung chat (`role="alert"`) và giữ nguyên nút `"Gửi lại"`.
- `web/src/app/WorkspacePage.tsx`: truyền `askProgress={chat.getProgress(currentChatId)}` vào `AssistantPanel`.

### Kiểm thử & báo cáo
- `web/src/__tests__/askProgress.test.tsx` (mới): kiểm tra `ApiClient.getAskProgress` (đường dẫn `/ask/tien-trinh` cho `__global__`, chuẩn hoá thiếu trường, không ném lỗi khi 404/lỗi mạng), `MockClient.getAskProgress` (4 bước theo thời gian thật của `ask`, từ khoá `"lỗi"`), `AssistantPanel` (khối đang chạy, fallback khi chưa có bước, nút `Xem các bước (n)` / `Ẩn các bước`, `ly_do` + `goi_y` + nút `Gửi lại`, thoát HTML an toàn, `aria-live` không chứa giây).
- `web/src/__tests__/useChat.test.ts`: bổ sung test polling 1000 ms, tạm dừng/tiếp tục theo `visibilitychange`, dừng khi `stopQuestion`/`clearChat`, đổi ca nhanh không lẫn bước, gắn bước lỗi và `retryLastQuestion`, và lịch sử khôi phục không có bước.
- `plan/briefs/T100-bao-cao.md` (mới): tệp báo cáo này.

## Quyết định tự chọn

1. **Tách `AiStepList.tsx` ở `web/src/features/findings/`**: giữ nguyên HTML và lớp CSS của `AiProgressPanel.tsx` để không làm gãy test cũ (`aiProgress.test.tsx`) và tránh sao chép mã giữa `AiProgressPanel` và `AssistantPanel`.
2. **Đọc `getAskProgress` lần cuối ngay cả khi `client.ask` ném lỗi không phải `AbortError`**: ngoài trường hợp trả `TraLoi` có `trang_thai: 'loi'`, nếu backend ném HTTP 5xx sau khi đã ghi bước lỗi vào `AskProgressRegistry`, `useChat` vẫn lấy được `cac_buoc` chứa `ly_do` và `goi_y` để hiển thị trong khung chat.
3. **Hiển thị `ly_do` và `goi_y` trực tiếp trong tin nhắn lỗi bên cạnh nút `"Xem các bước (n)"` thu gọn**: giữ nút xem các bước mặc định thu gọn đồng bộ cho mọi tin nhắn có `cac_buoc`, đồng thời đảm bảo dược sĩ thấy ngay lý do và gợi ý trong khung chat mà không phải bấm mở thêm.
4. **Giữ nguyên nhãn nút `"Gửi lại"` trong `AssistantPanel.tsx`**: tôn trọng nguyên tắc không đổi giao diện nút thử lại hiện có của khung chat.
5. **Fallback về `lastPolledSteps` nếu lần đọc `getAskProgress` cuối trả rỗng**: nếu các lượt hỏi trước đã thu được bước nhưng lần đọc cuối gặp lỗi mạng thoáng qua, vẫn giữ được tiến trình đã ghi thay vì mất trắng.

## Điều chưa chắc / cần Claude kiểm tra khi nghiệm thu

1. **Chưa chạy lệnh kiểm thử, biên dịch TypeScript và lint** do brief yêu cầu không gọi công cụ shell (`cd web && npm run test`, `npx tsc --noEmit`, `npm run lint`).
2. **Kiểm tra `oxlint` với `AiStepList.tsx`**: đã thêm chú thích `// oxlint-disable-next-line react/only-export-components` cho `toStepStatusMap` theo đúng mẫu `web/src/components/ui/button.tsx`, cần `npm run lint` xác nhận 0 cảnh báo.
3. **Hành vi `MockClient.ask` với từ khoá `"lỗi"`**: hiện kiểm tra `payload.cau_hoi.toLowerCase().includes('lỗi')` và trả `TraLoi` với `trang_thai: 'loi'` cùng bước `goi_mo_hinh` lỗi (thay vì ném `ApiError`). Nếu backend thật ném HTTP 5xx thay vì trả `trang_thai: 'loi'`, `useChat` đã xử lý cả hai nhánh như nhau.
