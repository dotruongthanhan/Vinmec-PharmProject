# Báo cáo UI2

TRẠNG THÁI: CHƯA XONG

Đã thêm nút mở rộng dùng chung, chuyển nút hình và bảng sang giao diện theo brief, đổi nhãn tab dữ liệu và bổ sung kiểm thử. Chỉ sửa các tệp thuộc phạm vi brief; các thay đổi sẵn có trong workspace được giữ nguyên.

Kiểm tra trong web bằng npx.cmd --no-install (PowerShell chặn npx.ps1):
- tsc -b: đạt.
- oxlint: đạt, còn một cảnh báo có sẵn tại src/features/lookup/InteractionLookupPage.tsx:111.
- vitest run: đã chạy đúng một lần; 49 tệp đạt, 1 tệp trượt; 408 test đạt, 1 test trượt. Lỗi test mới: kỳ vọng tab đầu là Lưới CrCl theo creatinin, nhưng fixture thực tế bắt đầu bằng Giá trị của ca.
- vite build: đạt.

Tệp mau/khoi-that-demo02.json nêu trong brief không tồn tại ở web/src/features/minh-hoa/mau. Fixture khoi-that-demo02-da-chinh.json có thứ tự ds-3, ds-4, ds-2, tương ứng Giá trị của ca, Mức liều, Lưới CrCl theo creatinin. Đã sửa kỳ vọng test theo thứ tự thực tế; chưa chạy lại Vitest vì brief chỉ cho chạy một lần. Chưa kiểm tra trình duyệt, tooltip và trả tiêu điểm bằng thao tác thực tế; brief giao bước này cho Claude.

Hướng dẫn modern-web-guidance yêu cầu chạy npx -y và truy cập mạng; không thực hiện do yêu cầu cấm mạng và cài gói. Không dùng mạng hay thêm gói.
