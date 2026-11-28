# Báo cáo UI3

## Thay đổi
- Bổ sung container query cho bảng y lệnh, xét nghiệm và danh sách hồ sơ; đưa các giá trị gộp vào dòng phụ và lịch dùng đầy đủ vào ngăn chi tiết.
- Ngăn chi tiết dùng `position: sticky; left: 0`, chiều rộng giới hạn bằng `100cqw - 50px`; lưới thông tin chuyển một cột khi hẹp. Giá trị 50 px dựa trên phần đệm vùng nội dung, chưa được đo xác nhận với mọi bố cục và chưa chứng minh bằng đúng vùng nhìn của bảng.
- Bổ sung kiểm thử markup; cho một số ô nội dung dài ở bảng khác xuống dòng.

## Nghiệm thu
- `npx.cmd --no-install tsc -b --noEmit`: đạt (sau sửa cuối).
- `npx.cmd --no-install oxlint`: đạt, có một cảnh báo có sẵn tại `InteractionLookupPage.tsx:111`.
- `npx.cmd --no-install vitest run --maxWorkers=1 --no-file-parallelism`: 53 tệp đạt, 1 tệp trượt; 419 test đạt, 1 test trượt. Test mới phát hiện thiếu dòng phụ hồ sơ. Đã thêm dòng phụ và sửa kỳ vọng mã BN theo dữ liệu mẫu sau lần chạy; chưa chạy lại do yêu cầu chỉ chạy Vitest một lần.
- `npx.cmd --no-install vite build`: đạt.
- Chưa đo trình duyệt, chưa chụp ảnh và chưa xác nhận điều kiện không tràn. Phần nghiệm thu trình duyệt brief giao Claude.

## Giới hạn
- Chưa thể kết luận hoàn thành: cần xác nhận lại test sau sửa và đo chiều rộng ngăn chi tiết, các bảng ở các kích thước brief yêu cầu.
- Skill modern-web-guidance yêu cầu tải gói và mạng; không chạy vì brief và AGENTS.md cấm.

## fix-1

- Đồng bộ lớp ẩn của tiêu đề và ô dữ liệu; thêm nhãn Thuốc ở chế độ hẹp, phân bổ lại cột tên thuốc và giữ nguyên các ngưỡng container. Chữ thông thường dùng `overflow-wrap: break-word`, mã dài mới dùng `anywhere`.
- Sửa các chuỗi lỗi mã hóa, thêm mã hồ sơ có nút mở, ngày sinh và khoa vào dòng phụ. Bổ sung test đối chiếu lớp ẩn theo từng vị trí và kiểm tra chuỗi hiển thị.
- `npx.cmd --no-install tsc -b --noEmit`: đạt. `npx.cmd --no-install oxlint`: đạt, còn một cảnh báo có sẵn tại `InteractionLookupPage.tsx:111`. `npx.cmd --no-install vite build`: đạt.
- `npx.cmd --no-install vitest run --reporter=dot`: 53/54 tệp đạt, 420/421 test đạt. Test `ordersTable.test.ts:132` trượt: mong `Chưa ghi nhận`, nhận `Chưa ghi nhận— · Chưa ghi nhận`. Test cũ lấy toàn bộ văn bản HTML, kể cả dòng phụ bị CSS ẩn; nếu vượt qua kiểm tra này thì kỳ vọng tại dòng 134 cũng xung đột với khoa trong dòng phụ. Brief chỉ cho phép test mới trong `web/src/__tests__/`, nên chưa sửa test cũ. Test UI3 riêng: 4/4 đạt.
- CHƯA XONG: toàn bộ Vitest chưa xanh; cần cho phép cập nhật test cũ để phân biệt nội dung dòng phụ. Chưa đo trình duyệt hoặc chụp ảnh; phần này brief giao Claude.
- Không chạy tìm kiếm `modern-web-guidance` vì yêu cầu tải gói và mạng bị AGENTS.md cấm. Các lệnh `npx` dùng `--no-install` để tránh tải gói.

## fix-2

- Render ba ô ngăn chi tiết với `colSpan` 9, 4 và 3; container query chỉ hiện ô tương ứng với số cột của từng chế độ. Thêm kiểm thử markup cho cả ba giá trị.
- Sửa truy vấn test cũ để chỉ đọc nội dung chế độ rộng, bỏ dòng phụ ẩn trước khi kiểm tra các ô.
- Trong `web`, chạy lần lượt `npx.cmd --no-install tsc -b --noEmit`, `npx.cmd --no-install oxlint`, `npx.cmd --no-install vitest run`, `npx.cmd --no-install vite build`: đều đạt. Vitest: 54 tệp, 421 test đạt. Oxlint còn một cảnh báo có sẵn tại `InteractionLookupPage.tsx:111`.
- Chưa đo độ rộng cột hoặc chụp ảnh trên trình duyệt; brief giao Claude đo lại ở 1280, 1440 và 1920. Không chạy tìm kiếm modern-web-guidance vì lệnh yêu cầu tải gói và mạng bị quy tắc dự án cấm.
