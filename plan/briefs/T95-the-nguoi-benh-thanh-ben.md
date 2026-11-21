# T95 – Thử nghiệm: thẻ thông tin người bệnh ở nửa dưới thanh bên trái

Agent: **agy Gemini 4 Hydrogen xhigh**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.**

## Bối cảnh

Nhánh `fix/ui-adjustments` có khung thông tin người bệnh cố định **trên cùng** trang ca (`PatientPinnedHeader`, bản tham khảo: `plan/briefs/T95-tham-khao/PatientPinnedHeader.tsx.txt` – chỉ đọc, không sửa). Người dùng (20/11) muốn thử đặt khung đó **ở thanh bên trái** để khỏi tốn chiều cao vùng làm việc:

- **Nửa trên** thanh bên: các mục điều hướng hiện có (Hồ sơ cần duyệt, Tra cứu thuốc, Tra tương tác, Tính toán; sau này thêm mục khác).
- **Nửa dưới**: thẻ thông tin cơ bản của người bệnh đang mở – chỉ hiện khi đang ở trang một ca (`/app/y-lenh/:ca_id`) và chi tiết ca đã tải xong.

Đọc trước: `AGENTS.md` (gồm mục Bảo mật), `plan/plan-1.4-he-thong-thiet-ke.md` (màu theo nghĩa, thang chữ, `Badge`), `web/src/features/sidebar/SidebarNav.tsx`, `web/src/app/WorkspacePage.tsx` (chỗ dựng `SidebarNav` – `sidebarSlot` và bản trong ngăn kéo `inDrawer`), `web/src/app/AppShell.tsx` (độ rộng / thu gọn thanh bên), `web/src/api/types.ts` (`ChiTietCa`, `FullIdentity`, `ChiSo` – **chỉ đọc**), `web/src/lib/displayFormat.ts`, `web/src/lib/severity.ts` (**chỉ đọc**, dùng hàm có sẵn).

## Phạm vi

Được tạo / sửa:
1. **Tạo** `web/src/features/sidebar/PatientSidebarCard.tsx`.
2. `web/src/features/sidebar/SidebarNav.tsx` – thêm prop tùy chọn (ví dụ `patient?: ChiTietCa | null`, `onOpenEvidence?`) và bố cục hai nửa.
3. `web/src/app/WorkspacePage.tsx` – **chỉ** truyền chi tiết ca đang mở (`detail && detail.ca_id === activeCaseId ? detail : null`) vào cả hai chỗ dựng `SidebarNav`.
4. **Tạo** `web/src/__tests__/patientSidebarCard.test.tsx`.
5. `web/src/styles/globals.css` – chỉ **thêm** cuối tệp nếu thật cần.

**Cấm đụng** (phiên bảo mật đang sửa song song): `app/`, `web/src/api/*`, `web/src/state/*`, `web/src/lib/*`, `web/src/features/lookup/*`, `web/src/features/order-detail/*`, `web/src/app/LookupWorkspace.tsx`, `web/src/app/AppShell.tsx`, `web/index.html`, `web/public/*`, `web/vercel.json`, mọi tệp test khác, `AGENTS.md`, `CLAUDE.md`, `plan/` (trừ báo cáo). Không thêm thư viện. **Không** gỡ khối thông tin hiện có trong trang ca (đây là thử nghiệm; người dùng so rồi mới quyết).

## Yêu cầu

### Bố cục thanh bên
- Thanh bên chia **hai vùng theo chiều dọc**: vùng điều hướng ở trên (chiều cao theo nội dung), vùng thẻ người bệnh ở dưới chiếm phần còn lại, **cuộn riêng** (`overflow-y-auto`, `min-h-0`), ngăn cách bằng đường kẻ `border-line`. Chân thanh bên (tài khoản `admin · Quản trị`, cài đặt) giữ nguyên ở đáy.
- Không có ca đang mở (danh sách, tra cứu…) → không hiện vùng dưới, điều hướng như hiện nay.
- Thanh bên **thu gọn** (`collapsed`) → ẩn thẻ; chỉ hiện một nút biểu tượng người bệnh có `aria-label` "Thông tin người bệnh" + tooltip tên in hoa và tuổi/giới (bấm → mở rộng thanh bên nếu có sẵn hàm, không thì chỉ tooltip).
- Ngăn kéo di động (`inDrawer`) → hiện đầy đủ như khi mở rộng.

### Thẻ người bệnh (`PatientSidebarCard`) – gọn, vừa độ rộng thanh bên hiện tại, chữ `text-xs`/`text-sm`
Theo thứ tự, mỗi dòng nhãn mờ (`text-fg-subtle`) + giá trị; thiếu → "Chưa ghi nhận":
1. **Họ tên in hoa** (đậm, cỡ lớn nhất trong thẻ, ngắt dòng được) và dưới đó: `Nam · 67 tuổi`.
2. **Mã hồ sơ** (`ca_id`, phông `mono`) · **Ngày sinh**.
3. **Cân nặng** · **Chiều cao** (hai cột).
4. **BHYT**: số thẻ (`mono`, ngắt được) + "hạn dd/mm/yyyy".
5. **Dị ứng**: `Badge` theo `toneOfAllergy` / `iconOfAllergy` như bản tham khảo.
6. **Chẩn đoán**: danh sách từ `detail.tom_tat.chan_doan`, chẩn đoán chính trước, kèm mã ICD-10 (`mono`); quá 3 dòng thì thu gọn, có nút "Xem thêm / Thu gọn" (`aria-expanded`).
7. **Chỉ số** dạng lưới 2 cột ô nhỏ: BMI, BSA, CrCl, eGFR – lấy từ `detail.chi_so` theo khóa như bản tham khảo (`bmi`, `bsa_mosteller`, `cockcroft_gault`, `egfr_ckd_epi_2021`), giá trị + đơn vị, ô CrCl tô cảnh báo khi `dinh_danh.crcl_bat_thuong`; bấm ô mở căn cứ bằng `onOpenEvidence` nếu bản tham khảo / `MetricsTable` có sẵn cách gọi, không có thì chỉ hiển thị.
- Dùng hàm định dạng có sẵn (`administrativeDate`, dấu phẩy thập phân kiểu Việt). Không tự tính chỉ số (chỉ hiển thị số backend trả).
- Tối / sáng đều đúng (token màu, không mã màu cứng). Bàn phím: mọi nút có `focus-visible`.

## Test (`patientSidebarCard.test.tsx`)

- Có `patient` → hiện họ tên in hoa, mã hồ sơ, số BHYT, chẩn đoán kèm ICD, 4 nhãn BMI/BSA/CrCl/eGFR.
- Thiếu trường → "Chưa ghi nhận", không vỡ.
- Chẩn đoán > 3 → có nút "Xem thêm" với `aria-expanded="false"`.
- `SidebarNav` không có `patient` → không có vùng thẻ; `collapsed` → không có họ tên đầy đủ, có nút "Thông tin người bệnh".

Nghiệm thu (Claude chạy): `tsc -b`, `oxlint`, `vitest` toàn bộ sạch; xem trên trình duyệt một ca (mở rộng / thu gọn / màn hẹp).

## Bảo mật

Chỉ trình bày dữ liệu đã có trong `ChiTietCa` (đã qua xác thực). Không thêm điểm cuối, không thêm trường, không ghi log, không lưu thông tin người bệnh vào `localStorage`. Không hiển thị thêm định danh nhạy cảm (không CCCD, không số điện thoại).

Báo cáo: `plan/reports/T95.md`.
