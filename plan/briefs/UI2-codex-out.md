**TRẠNG THÁI: CHƯA XONG**

Đã triển khai nút mở rộng dùng chung, chuyển nút hình sang góc tiêu đề và đổi nhãn tab bộ dữ liệu. Kiểm thử đã được sửa sau một lỗi về thứ tự fixture, nhưng chưa được chạy lại vì brief chỉ cho phép chạy Vitest một lần.

**FILE ĐÃ TẠO / SỬA:**

- [expand-button.tsx](/D:/create/Vinmec-PharmProject/web/src/components/ui/expand-button.tsx)
- [ClinicalMarkdown.tsx](/D:/create/Vinmec-PharmProject/web/src/components/ui/ClinicalMarkdown.tsx)
- [KhungMinhHoa.tsx](/D:/create/Vinmec-PharmProject/web/src/features/minh-hoa/KhungMinhHoa.tsx), [nguPhap.ts](/D:/create/Vinmec-PharmProject/web/src/features/minh-hoa/nguPhap.ts)
- [ui2.test.tsx](/D:/create/Vinmec-PharmProject/web/src/features/minh-hoa/__tests__/ui2.test.tsx), [clinicalMarkdown.test.tsx](/D:/create/Vinmec-PharmProject/web/src/__tests__/clinicalMarkdown.test.tsx), [clinicalMarkdownLayout.test.tsx](/D:/create/Vinmec-PharmProject/web/src/__tests__/clinicalMarkdownLayout.test.tsx)
- [UI2-bao-cao.md](/D:/create/Vinmec-PharmProject/plan/briefs/UI2-bao-cao.md)

**LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:** Trong `web/`, `tsc -b` và `vite build` đạt; `oxlint` đạt với một cảnh báo ở `InteractionLookupPage.tsx:111`. Vitest chạy một lần: **408 test đạt, 1 test trượt** do kiểm thử mới kỳ vọng sai thứ tự fixture. Đã sửa kỳ vọng nhưng chưa xác nhận lại bằng Vitest.

**ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO:** Tệp `mau/khoi-that-demo02.json` được nêu trong brief không có tại đường dẫn dự kiến. Fixture `khoi-that-demo02-da-chinh.json` hiện có thứ tự `ds-3`, `ds-4`, `ds-2`, khác thứ tự trong brief.

**VIỆC CHƯA LÀM / CÂU HỎI:** Cần chạy lại Vitest để xác nhận kiểm thử đã sửa và kiểm tra tooltip, đóng bằng Esc, trả tiêu điểm trên trình duyệt theo bước nghiệm thu của brief.