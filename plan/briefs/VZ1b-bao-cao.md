# VZ1b – Báo cáo

TRẠNG THÁI: CHƯA XONG

## Đã thực hiện

- Bổ sung kiểu khối minh hoạ vào câu trả lời, mock DEMO-02 dùng mẫu thực được cung cấp; chế độ chung không trả hình.
- Hỗ trợ mh-0 và mh-1, tra khoảng theo cột biên và cờ bao gồm, cột logic, nhãn và căn cứ. Test mẫu thực, creatinin 212, năm điểm biên và hiệu năng lưới 2.000 dòng.
- Hiển thị hình dưới trích dẫn, tải bộ vẽ bằng lazy, quan sát khung nhìn, thu gọn hình của câu trả lời cũ, dùng giá trị trì hoãn khi kéo, và thông báo lịch sử không lưu hình.
- Chunk `KhungMinhHoa-CcU1jy89.js`: 54,52 kB, gzip 15,92 kB theo Vite build.

## Lệnh và kết quả

- `npx --no-install tsc -b`: PowerShell từ chối chạy `npx.ps1` do execution policy; `npx.cmd --no-install tsc -b` thành công.
- `npx.cmd --no-install oxlint`: thành công, một cảnh báo có sẵn `react(set-state-in-effect)` tại `src/features/lookup/InteractionLookupPage.tsx:111` ngoài phạm vi.
- `npx.cmd --no-install vitest run`: 48 tệp đạt, một tệp thất bại; 399 test đạt, một test biên thất bại do dữ liệu thử không khớp bộ lọc. Sau khi sửa dữ liệu thử và xử lý biên không giới hạn, `npx.cmd --no-install vitest run src/features/minh-hoa/__tests__/mh1.test.ts`: 3/3 đạt. Chưa chạy lại toàn bộ theo giới hạn một lần trong brief.
- `npx.cmd --no-install vite build`: thành công.
- `rg -n 'innerHTML|dangerouslySetInnerHTML|new Function|eval\(|iframe' web/src/features/minh-hoa web/src/features/assistant`: không có kết quả.

## Chưa hoàn tất / hạn chế

- Khung giữ chỗ hiện cao cố định 320 px; chưa bảo đảm đúng chiều cao của mọi hình và trạng thái điều khiển như brief yêu cầu.
- Chưa kiểm tra trực quan, bàn phím, tràn ngang ở 320 px, chế độ sáng/tối, mạng/chunk và hiệu năng kéo khi giảm CPU 6 lần trên trình duyệt. Chưa xác minh thời gian dựng hình dưới 100 ms.
- Hướng dẫn modern-web-guidance yêu cầu `npx -y` và mạng; không thực hiện vì người dùng và AGENTS.md cấm tải gói và mạng.
