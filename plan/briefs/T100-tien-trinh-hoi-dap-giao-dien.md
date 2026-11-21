# T100 – Tiến trình hỏi đáp: giao diện web

Đọc `AGENTS.md`, `plan/plan-1.10-tien-trinh-ai-ui.md` (mục 4, 6 và đặc biệt mục 10), `plan/plan-1.4-he-thong-thiet-ke.md`, và code đã có của T98: `web/src/features/findings/AiProgressPanel.tsx`, `web/src/lib/aiReview.ts`, `web/src/state/useAiReview.ts`. Bạn chỉ làm `web/`. KHÔNG gọi shell, KHÔNG gọi mạng, KHÔNG cài gói. Một agent khác làm backend song song theo hợp đồng mục 10; bạn chỉ dùng chế độ mock để thử. Claude sẽ tự chạy vitest, tsc, lint.

## File được tạo hoặc sửa

- `web/src/api/types.ts`: `TienTrinhHoiDap { dang_chay: boolean; cac_buoc: BuocAI[]; da_chay_ms: number | null }`.
- `web/src/api/client.ts`: `getAskProgress(caId: string, init?: { signal?: AbortSignal }): Promise<TienTrinhHoiDap>` vào interface `ReviewApiClient` và bản HTTP: `GET /cases/{caId}/ask/tien-trinh`, riêng `caId === '__global__'` thì `GET /ask/tien-trinh`; chuẩn hoá phản hồi thiếu trường (mặc định `dang_chay=false`, `cac_buoc=[]`); lỗi mạng/404 không ném lỗi lên người dùng (trả mặc định).
- `web/src/api/index.ts`, `web/src/api/mock.ts` (và `mockLookup.ts` nếu cần): mô phỏng chuỗi bước hỏi đáp theo thời gian khi `ask` mock đang chờ (chuẩn bị → tra cứu nguồn → soạn câu trả lời → kiểm chứng), kèm một câu hỏi chứa từ khoá "lỗi" để mô phỏng bước lỗi có `ly_do` và `goi_y`.
- `web/src/state/useChat.ts`: trong lúc `sendingRef` đúng cho một phạm vi, hỏi `getAskProgress` mỗi 1000 ms (không hỏi khi `document.hidden`, hỏi lại ngay khi tab hiện; huỷ khi gửi xong, huỷ yêu cầu, đổi ca hoặc `clearChat`); lưu `progressByCase`; trả thêm `getProgress(caId)` (bước, `daChayMs`); khi POST trả về thì đọc một lần nữa để lấy bước cuối rồi gắn `cac_buoc` vào tin nhắn trả lời (trường tuỳ chọn `cac_buoc?: BuocAI[]` và `da_chay_ms?: number | null` trên biến thể `he_thong` của `ChatMessage`); phục hồi lịch sử thì không có bước (bình thường). Giữ nguyên chống đua theo `requestSeq`, huỷ, thử lại.
- `web/src/features/assistant/AssistantPanel.tsx`: thay khối vòng xoay "Đang tra cứu dữ liệu và nguồn…" bằng danh sách bước thu gọn (dùng lại dòng bước/biểu tượng của `AiProgressPanel`: tách thành thành phần dùng chung nếu cần, không sao chép mã); nếu chưa có bước nào thì giữ dòng chữ cũ. Dưới tin nhắn trả lời có `cac_buoc` hiện nút ghost "Xem các bước (n)" / "Ẩn các bước" (`aria-expanded`, `aria-controls`), mặc định thu gọn. Bước lỗi hiện `ly_do` và `goi_y` trong khung chat; nút "Thử lại" giữ nguyên.
- Nơi chuyền props: chỉ file cần thiết (`WorkspacePage.tsx`, nơi gọi `AssistantPanel`).
- Test: `web/src/__tests__/askProgress.test.tsx` (mới), bổ sung `useChat.test.ts`; sửa test cũ chỉ khi cần cho interface mới.

CẤM đụng: `app/`, luật hiển thị khác, token thiết kế (chỉ dùng token sẵn), thư viện mới, hành vi gửi/huỷ/thử lại hiện có.

## Yêu cầu hiển thị

- Biểu tượng + chữ, không dựa vào màu một mình; `motion-safe:animate-spin`; `aria-live="polite"` chỉ thông báo khi bước đổi trạng thái ("Bước <tên>: <trạng thái>"), đồng hồ `aria-hidden`.
- Hiển thị tốt ở chiều rộng khung chat hẹp (≈ 360 px), không tràn ngang.
- Chuỗi từ API là văn bản thuần (không `innerHTML`); không giả định độ dài.
- Mock phải thật: bước chỉ đổi theo thời gian mock, không phải đồng hồ giả chạy độc lập với `ask`.

## Nghiệm thu (Claude sẽ chạy)

`cd web && npm run test`, `npx tsc --noEmit`, `npm run lint`. Test phải bao: bước hiện trong lúc gửi, hỏi 1000 ms và dừng khi tab ẩn/xong/huỷ/đổi ca, gắn `cac_buoc` vào tin nhắn trả lời, thu gọn/mở, bước lỗi (lý do + gợi ý + thử lại), API thiếu trường, hai ca đổi nhanh không lẫn bước, `getAskProgress` dùng đúng đường dẫn chung (`/ask/tien-trinh`) cho `__global__`. Cuối việc viết `plan/briefs/T100-bao-cao.md`: file đổi, quyết định tự chọn, điều chưa chắc.
