# Hướng dẫn đóng gói & phát hành Chrome Web Store (Unlisted)

Tiện ích đã đáp ứng đầy đủ cấu trúc Manifest V3 (`extension/dist/`) để phân phối nội bộ theo hình thức **Unlisted** (không hiển thị khi tìm kiếm công khai, cài đặt bằng 1 cú nhấp qua đường dẫn riêng và tự động cập nhật nền cho đồng đội).

## Bảng kiểm trước khi nộp (CWS Checklist)

1. Kiểm tra sạch mã nguồn & gói build:
   ```bash
   npm --prefix extension ci
   npm --prefix extension run lint
   npm --prefix extension run build
   cd extension && npx vitest run
   ```
2. Nén thư mục build (`extension/dist/`):
   ```bash
   (cd extension/dist && zip -r ../bvienx-cdss-extension-v1.10.0.zip .)
   ```
3. Đảm bảo trong gói ZIP **chỉ chứa** các tệp đầu ra của `extension/dist/` (`manifest.json`, `service-worker.js`, `sidepanel/index.html`, `assets/*`, `icons/icon-{16,48,128}.png`) — không có `eval`, không có `<script>` nội tuyến.

## Giải trình quyền (Permission Justifications) cho Google Review

- **`sidePanel`**: Hiển thị bảng thẩm định y lệnh lâm sàng ngay cạnh tab bệnh án mà không che khuất nội dung làm việc của dược sĩ.
- **`tabs`**: Liệt kê tiêu đề và URL các tab đang mở trong cửa sổ hiện tại để dược sĩ chọn các tab hồ sơ cần trích xuất.
- **`scripting`**: Chạy tập lệnh trích xuất DOM (`textContent`) chỉ vào đúng những tab mà dược sĩ chủ động tích chọn và cấp quyền.
- **`storage`**: Lưu bộ nhớ đệm danh sách **tên nhãn trường** không nhạy cảm (`schemaHash` trong `chrome.storage.local`), khung cắt bảng OH mặc định, và giữ trạng thái phiên làm việc tạm thời trong `chrome.storage.session` (tự xoá khi đóng trình duyệt hoặc bấm "Xoá phiên").
- **`optional_host_permissions` (`https://*/*`, `http://localhost/*`, `http://127.0.0.1/*`)**: Chỉ yêu cầu quyền đọc nội dung trang khi dược sĩ chủ động bấm nút **"Đọc tab & che PII"** cho tên miền EMR đang dùng.

## Cam kết quyền riêng tư (Single Purpose & Zero-Retention)

- **Single Purpose:** Hỗ trợ dược sĩ lâm sàng kiểm tra an toàn y lệnh từ các tab bệnh án đang mở và ảnh chụp bảng thuốc OH.
- **Data Handling:** Mọi thông tin định danh cá nhân (họ tên, CCCD, BHYT, ngày sinh, số điện thoại, địa chỉ, tên bác sĩ) đều bị loại bỏ tại trình duyệt trước khi gửi văn bản đã che (`[TEN_1]`, `[CCCD_1]`, ...) tới máy chủ thẩm định phi trạng thái (`Zero-Retention`, chỉ lưu trong RAM tạm tối đa 30 phút).
