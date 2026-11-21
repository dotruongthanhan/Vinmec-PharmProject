# T98 – Tiến trình phân tích AI: giao diện web

Đọc `AGENTS.md`, `plan/plan-1.10-tien-trinh-ai-ui.md` (mục 4 hợp đồng, mục 6 giao diện), `plan/plan-1.4-he-thong-thiet-ke.md` (token, thành phần). Bạn chỉ làm phần `web/`. KHÔNG gọi shell, KHÔNG gọi mạng, KHÔNG cài gói. Claude sẽ tự chạy vitest, tsc, lint nên hãy tự đọc kỹ code. Một agent khác làm backend song song theo đúng hợp đồng mục 4; bạn chỉ dùng chế độ mock để thử.

## File được tạo hoặc sửa

- `web/src/api/types.ts` (thêm `BuocAI`, `NguonTomTat`, trường mới của `KetQuaAI`: `cac_buoc`, `da_chay_ms`, `thuong_le_ms`, đều bắt buộc có mặc định ở nơi dựng; ở chỗ đọc từ API phải chịu được thiếu trường: coi `cac_buoc` thiếu là `[]`)
- `web/src/api/client.ts` (chuẩn hoá phản hồi thiếu trường nếu cần)
- `web/src/api/mock.ts` (mô phỏng chuỗi bước theo thời gian: lấy nguồn → tổng hợp → kiểm chứng, có thể một ca mô phỏng lỗi ở bước tổng hợp; `startAi`, `getAi` trả `cac_buoc`, `da_chay_ms`, `thuong_le_ms`)
- `web/src/state/useAiReview.ts` (trả thêm `cacBuoc`, `daChayMs`, `thuongLeMs`; hỏi lại mỗi 1500 ms thay cho 2000 ms: đổi hằng `AI_POLL_INTERVAL_MS`; không hỏi khi `document.hidden`, hỏi lại ngay khi tab hiện; giữ nguyên trần 120 giây, logic chạy lại, chống đua ca)
- Tạo `web/src/features/findings/AiProgressPanel.tsx` và dùng trong `web/src/features/findings/AiStatusBar.tsx` (nhánh `dang_chay` và nhánh `xong` thu gọn, nhánh `loi`)
- `web/src/features/order-detail/OrderDetailView.tsx`: chỉ chuyền thêm prop (bước, thời gian) xuống `AiStatusBar`
- `web/src/lib/aiReview.ts`: hàm thuần cho định dạng thời gian ("14s", "1,2s"), ước lượng "thường mất" và cờ chậm
- Test mới/sửa: `web/src/__tests__/aiProgressPanel.test.tsx`, bổ sung `aiReview.test.ts`; sửa test cũ chỉ khi cần cho prop mới.

CẤM đụng: `app/` (backend), luật hiển thị bảng nhận định, token thiết kế (chỉ dùng token sẵn có), thư viện mới.

## Yêu cầu hiển thị (mục 6 plan)

- Danh sách bước theo thứ tự nhận từ API. Mỗi bước: biểu tượng (lucide-react: `Circle` chờ, `LoaderCircle` quay, `CircleCheck` xong, `CircleAlert`/`CircleX` lỗi, `CircleSlash` hoặc dấu gạch bỏ qua) kèm chữ tên bước, chi tiết, thời gian ở mép phải căn số tabular. Không dựa vào màu một mình.
- Bước lấy nguồn: hiện `chi_tiet` và các nhóm nguồn dạng "nhãn số" gọn, xuống dòng khi hẹp.
- Đồng hồ tổng và dòng "thường 20–40 s" khi có `thuong_le_ms` (khoảng từ 0,7× đến 1,5× trung vị, làm tròn 5 s; thiếu thì không hiện). Đồng hồ nội suy phía web giữa hai lần hỏi bằng `setInterval` 500 ms dựa trên `da_chay_ms` nhận được cộng thời gian trôi qua cục bộ (dọn timer khi huỷ). Đồng hồ `aria-hidden`; vùng `aria-live="polite"` chỉ chứa câu "Bước <tên>: <trạng thái>" khi bước đổi trạng thái, không chứa giây.
- Chậm: bước đang chạy quá 30 s hoặc tổng quá 1,5× `thuong_le_ms` thì thêm dòng "Bước <tên> đang lâu hơn thường lệ. Bảng luật vẫn dùng được." (`role="status"`).
- Luôn có dòng cuối "Bảng bên dưới là kết quả của bộ luật." khi đang chạy.
- Lỗi: bước `loi` hiện `ly_do` và `goi_y`; nút "Thử lại" giữ nguyên hành vi; nền cảnh báo (token `warning`), các bước xong vẫn hiện ✓; bước `bo_qua` mờ.
- Xong: dòng tóm tắt như hiện nay (`formatAiDoneMessage`) kèm nút ghost "Xem các bước (n)" / "Ẩn các bước" với `aria-expanded` và `aria-controls`; mặc định thu gọn. Nếu `cac_buoc` rỗng (API cũ, mock cũ) thì không hiện nút.
- `prefers-reduced-motion: reduce`: không quay, dùng biểu tượng tĩnh (dùng lớp `motion-safe:animate-spin`).
- Hiển thị tốt ở chiều rộng 360 px; không tràn ngang.
- Mọi chuỗi là văn bản thuần (không `innerHTML`, không `dangerouslySetInnerHTML`). Chuỗi từ API có thể bị cắt, không giả định độ dài.

## Nghiệm thu (Claude sẽ chạy)

`cd web && npm run test`, `npx tsc --noEmit`, lint của dự án. Test phải bao: từng trạng thái bước, chậm, lỗi (lý do + gợi ý + thử lại), thu gọn/mở, phản hồi API thiếu `cac_buoc`, cập nhật khi đổi bước, `useAiReview` hỏi 1500 ms và tạm dừng khi tab ẩn, hai ca đổi nhanh không lẫn bước. Test cũ giữ xanh (sửa khi chỉ đổi 2000 → 1500). Cuối việc viết `plan/briefs/T98-bao-cao.md`: file đổi, quyết định tự chọn, điều chưa chắc.
