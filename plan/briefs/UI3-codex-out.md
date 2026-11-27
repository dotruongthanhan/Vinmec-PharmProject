**TRẠNG THÁI: CHƯA XONG**

Đã bổ sung bố cục co giãn cho ba bảng, dòng phụ cho các cột được gộp và kiểm thử markup. Các thay đổi TR2a trong `app/`, `db/` và `config/` được giữ nguyên.

**FILE ĐÃ TẠO / SỬA:** Các thành phần bảng trong `web/src/features/orders/`, `web/src/features/order-detail/`, `PassedList.tsx`, `globals.css`, test [ui3Responsive.test.tsx](/D:/create/Vinmec-PharmProject/web/src/__tests__/ui3Responsive.test.tsx) và [báo cáo UI3](/D:/create/Vinmec-PharmProject/plan/briefs/UI3-bao-cao.md).

**LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:**

- TypeScript và Vite build: đạt.
- Oxlint: đạt, có một cảnh báo tại `InteractionLookupPage.tsx:111`.
- Vitest chạy một lần, tuần tự: **419 đạt, 1 trượt**. Test trượt phát hiện thiếu dòng phụ hồ sơ; đã sửa sau đó nhưng chưa chạy lại theo yêu cầu chỉ chạy Vitest một lần.

**ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO:** Chiều rộng ngăn chi tiết dùng `sticky` với giới hạn `100cqw - 50px`; chưa xác nhận được nó khớp chính xác vùng nhìn của bảng trong mọi bố cục. Không chạy tra cứu `modern-web-guidance` vì bước đó yêu cầu tải gói và dùng mạng, trái với brief.

**VIỆC CHƯA LÀM / CÂU HỎI:** Cần chạy lại test sau bản sửa và đo trên trình duyệt theo các kích thước trong brief để xác nhận không tràn và chiều rộng ngăn chi tiết.