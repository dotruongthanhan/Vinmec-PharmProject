# Báo cáo UI1

**Trạng thái: CHƯA XONG.** Đã triển khai bảng và nghiệm thu tĩnh, nhưng chưa xác minh đầy đủ tương tác và hiệu năng theo brief.

## Tệp đã sửa

- `web/src/components/ui/ClinicalMarkdown.tsx`: phân tích bảng, giới hạn nội dung, hiển thị và mở hộp thoại.
- `web/src/components/ui/dialog.tsx`: thêm biến thể `fullscreen`.
- `web/src/features/assistant/HistoryDialog.tsx`: hiển thị câu trả lời qua `ClinicalMarkdown`.
- `web/src/__tests__/clinicalMarkdown.test.tsx`: kiểm tra bảng, căn lề, ô thiếu/thừa, ký tự thoát, XSS và giới hạn.
- `plan/reports/UI1.md`: báo cáo này.

## Quyết định

- Giữ hợp đồng callback trích dẫn hiện tại: đối tượng trích dẫn và nút được nhấn. Dùng Radix Dialog để quản lý Esc và trả tiêu điểm; đóng đồng bộ trước khi gọi callback từ bảng mở rộng.
- Dùng `title` làm tooltip gốc cho nút mở rộng; màu dùng các token giao diện hiện có. Không thực hiện mục tùy chọn mở rộng khối mã.
- Không chạy công cụ modern-web-guidance vì công cụ yêu cầu tải và chạy gói qua mạng, trái quy tắc dự án.

## Lệnh và kết quả

- `npx --no-install tsc -b`: PowerShell chặn `npx.ps1` bởi execution policy; chạy lại bằng `npx.cmd --no-install tsc -b`: đạt.
- `npx.cmd --no-install oxlint`: mã thoát 0; một cảnh báo `react(set-state-in-effect)` tại `src/features/lookup/InteractionLookupPage.tsx:111`, ngoài phạm vi brief.
- `npx.cmd --no-install vitest run`: đạt 45 tệp, 376 bài test.
- `node -e` kiểm tra `require.resolve('jsdom')`: không tìm thấy jsdom.

## Chưa làm và điểm lệch

- Chưa có kiểm thử DOM cho callback trích dẫn, mở/đóng bằng Esc, trả tiêu điểm, callback sau khi đóng, hoặc bảng trong lịch sử; chưa đo render 1.000 dòng dưới 500 ms trong jsdom. Không cài jsdom vì brief và quy tắc dự án cấm thêm gói. Bài test hiện có chỉ kiểm tra số dòng qua HTML render phía máy chủ.
- Gói cần cho phép đo được chỉ định: `jsdom`, phiên bản chưa xác định vì chưa được chủ kho duyệt. Đã xét render phía máy chủ bằng `react-dom/server` sẵn có, nhưng cách đó không kiểm tra được DOM, tiêu điểm hay thời gian trong jsdom.
- Đã đọc nhầm một tệp hướng dẫn kỹ năng dưới `~/.codex`, trái quy tắc không đọc thư mục đó trong AGENTS.md; không sửa tệp này.

## UI1-fix-1

**Trạng thái: XONG phần sửa và nghiệm thu tự động; chờ Claude đo lại trên giao diện thật theo brief.**

- Đã sửa `ClinicalMarkdown.tsx`, `AssistantPanel.tsx`, `HistoryDialog.tsx`; thêm `web/src/__tests__/clinicalMarkdownLayout.test.tsx` và mục báo cáo này.
- Chọn cách (b): chỉ ép con trực tiếp của viewport Hỏi đáp thành block, tránh thay đổi hành vi của ScrollArea khác. Đã rà toàn bộ nơi dùng: Hỏi đáp, Lịch sử và Nguồn đều nằm trong `AssistantPanel.tsx`; hai viewport Lịch sử và Nguồn cùng component ScrollArea dùng chung không đổi.
- Ràng chiều rộng các khối tin nhắn và lịch sử; bảng cuộn ngang riêng, ô rộng tối thiểu 8rem, tối đa 28rem trong chat và không giới hạn tối đa khi mở rộng. Ưu tiên heading Markdown, nếu không có thì dùng dòng in đậm đứng riêng ngay trước bảng (có thể cách dòng trống). Đưa JSDoc về đúng component.
- Hướng dẫn modern-web-guidance yêu cầu tải và chạy gói qua mạng; không thực hiện vì quy tắc bảo mật dự án và yêu cầu không thêm gói.
- Tại `web`, với `npm_config_offline=true`: `npx.cmd tsc -b` đạt; `npx.cmd oxlint` đạt, còn cảnh báo sẵn có `react(set-state-in-effect)` tại `src/features/lookup/InteractionLookupPage.tsx:111`; `npx.cmd vitest run` đạt 46 tệp, 378 test. Test riêng mới đạt 2 test. Lần đầu chạy test riêng thất bại do ghi nhầm đường dẫn `web/web/...`, không tạo tệp; đã sửa đường dẫn và chạy lại đạt.
- Chưa đo kích thước và cuộn trên giao diện thật; Claude thực hiện bước đo lại theo brief. Không thêm gói, không commit.
