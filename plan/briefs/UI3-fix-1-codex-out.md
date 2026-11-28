**TRẠNG THÁI: CHƯA XONG**

**FILE ĐÃ SỬA:** Các tệp bảng y lệnh, xét nghiệm, danh sách hồ sơ, CSS, test UI3 và [báo cáo UI3](D:/create/Vinmec-PharmProject/plan/briefs/UI3-bao-cao.md). Đã giữ nguyên thay đổi TR2a trong `app/`, `db/`, `config/`.

**LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:**

- TypeScript và build: đạt.
- Oxlint: đạt, còn một cảnh báo có sẵn tại `InteractionLookupPage.tsx:111`.
- Test UI3: 4/4 đạt.
- Toàn bộ Vitest: **420/421 test đạt**. Test cũ `ordersTable.test.ts:132` mong `Chưa ghi nhận`, nhưng đọc được `Chưa ghi nhận— · Chưa ghi nhận` vì nó tính cả dòng phụ bị ẩn bằng CSS.

**ĐIỂM LỆCH SO VỚI BRIEF:** Vitest chưa xanh. Test cũ cần được cập nhật để phân biệt dòng phụ; brief chỉ cho phép tạo test mới trong thư mục test nên tôi chưa sửa test đó. Các lệnh `npx` dùng `--no-install` để tránh tải gói.

**VIỆC CHƯA LÀM / CÂU HỎI:** Cần cho phép sửa test cũ rồi chạy lại toàn bộ Vitest. Việc đo và chụp ảnh trình duyệt ở ba kích thước chưa thực hiện; brief giao bước này cho Claude.