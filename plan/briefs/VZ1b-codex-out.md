**TRẠNG THÁI: CHƯA XONG**

**FILE ĐÃ TẠO / SỬA:** Các tệp được phép trong `web/src/features/minh-hoa/`, `web/src/features/assistant/`, `web/src/api/types.ts`, `web/src/api/mock.ts`; báo cáo tại [VZ1b-bao-cao.md](/D:/create/Vinmec-PharmProject/plan/briefs/VZ1b-bao-cao.md).

Đã nối minh hoạ vào chat, hỗ trợ `mh-1` và tra khoảng, dùng mẫu DEMO-02, tải lười bộ vẽ và thu gọn hình cũ. Chunk bộ vẽ đo được **15,92 kB gzip**, dưới mục tiêu 35 kB.

**LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:**

- TypeScript và build thành công. Oxlint thành công, có một cảnh báo ở tệp ngoài phạm vi brief.
- Bộ Vitest đầy đủ: **399 đạt, 1 trượt**. Sau khi sửa, test `mh1.test.ts` chạy riêng đạt **3/3**; chưa chạy lại toàn bộ vì brief giới hạn một lượt.
- Tìm các mẫu mã bị cấm bằng `rg`: không có kết quả.

**ĐIỂM LỆCH SO VỚI BRIEF:** Khung giữ chỗ hiện cao cố định 320 px, chưa bảo đảm đúng chiều cao của mọi hình. Bước tra cứu của modern-web-guidance không chạy vì yêu cầu tải công cụ qua mạng.

**VIỆC CHƯA LÀM / CÂU HỎI:** Chưa kiểm tra trực quan và hiệu năng trên trình duyệt: sáng/tối, bàn phím, tràn ngang ở 320 px, tải chunk theo Network, kéo khi giảm CPU 6 lần và thời gian dựng hình dưới 100 ms.