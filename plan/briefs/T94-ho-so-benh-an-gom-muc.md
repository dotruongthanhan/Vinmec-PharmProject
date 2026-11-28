# T93 – Tab "Hồ sơ bệnh án": gom thành các mục I–III đóng/mở, mặc định thu gọn

Agent: **agy Gemini 4 Hydrogen xhigh**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.**

## Bối cảnh

Nhánh `fix/ui-adjustments` (commit `29b0b33`) gom tab "Hồ sơ bệnh án" của trang ca thành 3 khối đóng/mở kiểu OH: **I. Hành chính · II. Chẩn đoán · III. Quản lý người bệnh**, mặc định thu gọn, có mũi tên xoay. Người dùng (20/11) chọn đưa **riêng phần này** về nhánh `vukhai248`. Phần "khung người bệnh cố định" (`PatientPinnedHeader`) **chưa** lấy – vì vậy các trường họ tên, tuổi, BHYT, chỉ số… phải **giữ lại** trong tab này, không được bỏ như nhánh kia.

Bản tham khảo (chỉ đọc, đuôi `.txt` để không lọt vào build; **không sửa thư mục này**): `plan/briefs/T93-tham-khao/AdministrativeSections.tsx.txt`, `OrderDetailView.tsx.txt` (hàm `MedicalRecordTabContent`, biến `diagnosisSection`), `globals.css.txt` (khối `.record-disclosure*`), `administrative.test.tsx.txt`.

Đọc trước: `AGENTS.md` (gồm mục Bảo mật), `plan/plan-1.4-he-thong-thiet-ke.md`, bản hiện tại của 4 tệp trong phạm vi.

## Phạm vi – CHỈ 4 tệp này

1. `web/src/features/order-detail/AdministrativeSections.tsx`
2. `web/src/features/order-detail/OrderDetailView.tsx` – **chỉ** hàm `MedicalRecordTabContent` và import cần thiết. Không đụng phần thẻ, thẩm định, chat, điều hướng.
3. `web/src/styles/globals.css` – **chỉ thêm** khối `.record-disclosure*` ở cuối tệp; không sửa dòng khác (không lấy phần độ rộng cột `.orders-table` của nhánh kia).
4. `web/src/__tests__/administrative.test.tsx`

**Cấm đụng** (phiên bảo mật đang sửa song song): `app/`, `web/src/api/*` (kể cả `types.ts`), `web/src/state/*`, `web/src/lib/*`, `web/src/features/lookup/*`, `web/index.html`, `web/public/*`, `web/vercel.json`, mọi tệp test khác, `AGENTS.md`, `CLAUDE.md`, `plan/` (trừ báo cáo). Không thêm thư viện.

## Yêu cầu

1. `RecordSection`: dùng `<details>` nguyên bản, **mặc định thu gọn**, `summary` có `ChevronRight` (lucide, đã có) xoay 90° khi mở, ẩn dấu tam giác mặc định, `focus-visible` rõ, hover nền nhẹ; hiệu ứng trượt chỉ khi `prefers-reduced-motion: no-preference` – lấy theo bản tham khảo.
2. **I. Hành chính** – giữ **đủ** các trường hiện có của bản local (họ tên, ngày sinh, tuổi, giới, cân nặng, chiều cao, dân tộc, ngoại kiều/quốc tịch, nghề nghiệp, địa chỉ, đối tượng, số thẻ + hạn BHYT, nhóm máu, bố mẹ khi < 16 tuổi). Gộp người nhà báo tin thành một dòng "Liên lạc khẩn cấp" (họ tên · quan hệ · điện thoại) như bản tham khảo; thêm "Khoa / giường" (nhãn tiếng Việt, **không** dùng chữ "Ward").
   - **Không** thêm trường CCCD / số điện thoại người bệnh (backend không có trường này; thêm định danh nhạy cảm cần quyết định bảo mật riêng).
3. **II. Chẩn đoán** – truyền qua prop `diagnosisSection` như bản tham khảo: chẩn đoán (toàn bộ danh sách kèm ICD-10 từ `detail.tom_tat.chan_doan`; rỗng thì "Chưa ghi nhận"), dị ứng, cơ địa đặc biệt. Bỏ hai `section` "III. Chẩn đoán" và "Cơ địa đặc biệt" rời rạc hiện nay.
4. **III. Quản lý người bệnh** – theo bản tham khảo: "1/ Thông tin lần khám gần nhất" (ngày đến viện, ngày rời viện, lý do ra viện, khoa điều trị dạng danh sách, lịch sử chuyển khoa / chuyển viện) và "2/ Lịch sử các lần vào viện (N lần)" (bảng hiện có, giữ chi tiết y lệnh / phiếu điều trị từng lần). Giữ thêm các trường quản lý hiện có không nằm trong bản tham khảo (hình thức vào, nơi giới thiệu, vào khoa lúc, số giường, số lưu trữ, mã y tế, bác sĩ điều trị, tổng số ngày điều trị) – đặt trong mục 1/.
5. Phần **"Chỉ số lâm sàng tính từ hồ sơ"** (`MetricsTable`) và **"Giá trị cận lâm sàng ngoài ngưỡng"** giữ nguyên, hiển thị bên dưới 3 khối, không đóng gói vào `details`.
6. Mọi chữ hiển thị bằng tiếng Việt; thiếu dữ liệu ghi "Chưa ghi nhận". Không dùng `dangerouslySetInnerHTML`.

## Test (`administrative.test.tsx`)

- Có đúng 3 khối với tiêu đề "I. Hành chính", "II. Chẩn đoán", "III. Quản lý người bệnh", **mặc định đóng** (`details` không có `open`).
- Trường họ tên, số thẻ BHYT, nhóm máu vẫn hiển thị trong khối I.
- Không còn chuỗi "Ward", không có nhãn "CCCD".
- Khối II chứa dị ứng và cơ địa; khối III có "Lịch sử các lần vào viện" khi có lịch sử, không có khi rỗng.
- Giữ / sửa các test cũ của tệp này cho khớp.

Nghiệm thu (Claude chạy): `tsc -b`, `oxlint`, `vitest` toàn bộ sạch; xem trên trình duyệt ca có lịch sử vào viện.

## Bảo mật

Chỉ đổi trình bày, không thêm điểm cuối, không thêm trường dữ liệu, không ghi log. Không hiển thị thêm định danh nhạy cảm so với hiện tại.

Báo cáo: `plan/reports/T93.md` (tệp đã sửa, quyết định, kết quả kiểm nếu có).
