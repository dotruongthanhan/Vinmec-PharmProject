# T47 – Bộ lọc nhiều lựa chọn, tự làm mới và lỗi giao diện

Mô hình: Codex `gpt-6.2-sol`, effort `high` (đã kiểm chạy được trên Codex CLI 0.170.0). Chạy bằng chế độ nền của app, không dùng `&`. **Không dừng giữa chừng để hỏi**: gặp điểm chưa rõ thì chọn cách ít rủi ro nhất, ghi vào báo cáo mục "Lựa chọn đã làm". Bám `plan/plan-1.4-he-thong-thiet-ke.md`.

## Phạm vi file
Được sửa/tạo: `web/src/**` (kể cả test mới) và `plan/reports/T47.md`.
Cấm đụng: `app/`, `db/`, `data/`, `tests/` (Python), `web/vite.config.ts`, hợp đồng API.

## Việc cần làm

### A. Bảng danh sách y lệnh: lọc nhiều lựa chọn (đánh dấu)
Hiện mỗi tiêu đề cột (Ưu tiên, Khoa, Trạng thái, Cảnh báo AI) mở một menu vừa Sắp xếp vừa Lọc, lọc chỉ chọn **một** giá trị (`OrderColumnFilters` ở `web/src/lib/orders.ts`, `features/orders/OrdersTable.tsx`).
1. Đổi lọc sang **chọn nhiều bằng ô đánh dấu**: dược sĩ tick cùng lúc hai mức ưu tiên, hai khoa, hai trạng thái... Cấu trúc đề xuất: `priority?: OrderPriorityLevel[]`, `khoa?: string[]`, `status?: OrderWorkflowStatus[]`, `aiWarning?: OrderAiWarningFilter[]`; mảng rỗng hoặc không có = không lọc ("Tất cả").
2. Menu mỗi cột có phần **Sắp xếp** (giữ chọn một như hiện tại) và phần **Lọc** gồm các ô đánh dấu. Có dòng "Tất cả" tự bỏ chọn khi tick giá trị cụ thể, hoặc nút "Chọn tất cả/Bỏ chọn". Menu không đóng sau mỗi lần tick (đóng bằng Esc hoặc bấm ra ngoài). Hiện số bộ lọc đang bật ngay trên tiêu đề cột (chấm hoặc số).
3. Nút "Xóa tất cả bộ lọc" khi có bộ lọc đang bật. Giữ bộ lọc khi chuyển giữa danh sách và chi tiết trong cùng phiên (trạng thái hiện nằm ở `WorkspacePage`; giữ nguyên cách lưu).
4. Cập nhật `filterOrders` và các hàm đếm nhận mảng. Giữ tương thích: nơi khác truyền giá trị đơn hoặc `'all'` vẫn chạy.
5. Hỗ trợ bàn phím và `aria` (menu checkbox: `role="menuitemcheckbox"` hoặc `Checkbox` sẵn có), trạng thái thấy rõ trên nền tối.
6. Test: hai mức ưu tiên cho ra hợp của hai tập; hai khoa; nhiều cột là giao giữa các cột; mảng rỗng = tất cả; xóa tất cả bộ lọc.

### B. Tự làm mới dữ liệu (gần thời gian thực)
7. Danh sách y lệnh và chi tiết ca đang mở **tự tải lại** mỗi 60 giây khi tab đang hiển thị, và ngay khi cửa sổ lấy lại tiêu điểm (`visibilitychange`/`focus`) nếu đã quá 30 giây từ lần tải trước. Không được làm mất: lựa chọn y lệnh (`?yl=`), tab đang xem, dòng thuốc đang lọc, phiên hội thoại, trạng thái AI đang chạy, phản hồi đang soạn. Không nhấp nháy khung tải: giữ dữ liệu cũ đến khi dữ liệu mới về. Lỗi tải nền không hiện hộp lỗi (ghi nhận, thử lại ở chu kỳ sau).
8. Chữ nhỏ ở chân danh sách: "Cập nhật lúc HH:mm:ss" (giờ +07), đổi mỗi lần làm mới; bấm vào thì làm mới ngay. Backend sắp trả thêm trường tùy chọn `lam_moi_luc` ở `GET /api/cases`; có thì ưu tiên hiển thị, không thì dùng giờ máy.
9. Test với bộ hẹn giờ giả (`vi.useFakeTimers`): tải lại sau 60 giây; tạm dừng khi tab ẩn; tải ngay khi lấy lại tiêu điểm sau trên 30 giây; giữ nguyên lựa chọn y lệnh.

### C. Lỗi giao diện nhỏ
10. **Bộ chọn y lệnh dùng bàn phím** (`MedicalRecordSections.tsx` ~47, ~78): mũi tên chỉ di chuyển/chọn trong danh sách, **không đóng** popover; popover đóng bằng Enter/Space/click trên mục hoặc Esc. Đừng đóng trong `onValueChange`. `aria-label` của nút mở và từng mục không được ghi đè nội dung hiển thị (dùng `aria-labelledby` hoặc bỏ `aria-label`).
11. **Số y lệnh cùng nguồn:** cột "Số y lệnh" ở danh sách hồ sơ (`MedicalRecordsList.tsx`) và nhãn `Y lệnh (n)` trong chi tiết phải cùng nghĩa: số y lệnh của **mọi lần vào viện**. Nếu danh sách chưa có số này thì đặt tiêu đề cột "Y lệnh (lần cuối)" để không gây nhầm; nêu lựa chọn trong báo cáo. Ở chế độ demo, y lệnh giả `YL-…-NEN` không được tính vào nhãn.
12. **Liên kết trong phiếu tới y lệnh không có trong danh sách** (`MedicalRecordSections.tsx` ~138): không chọn thầm y lệnh trọng tâm. Hiện chú thích nhỏ "Y lệnh <mã> không có trong danh sách" hoặc vô hiệu hóa liên kết. Khi bấm liên kết hợp lệ phải xóa bộ lọc dòng thuốc (`setSelectedDrug(null)`) như `handleSelectOrder`.
13. **Sidebar:** mục "Hồ sơ bệnh án" phải sáng cả khi đang xem chi tiết một hồ sơ mở từ trang hồ sơ (đi từ `/app/ho-so`); mục "Y lệnh" sáng khi vào chi tiết từ danh sách y lệnh. Dùng `location.state` hoặc tham số để nhớ nguồn; mặc định "Y lệnh". Dọn thuộc tính không còn dùng trong `SidebarNav` (`counts`, `activeFilter`, `onSelectFilter` nếu thật sự chết) mà không vỡ test.
14. **`?yl=` không bị xóa oan:** `OrderDetailView.tsx` ~313–321: chỉ xóa `yl` khi đổi sang **ca khác**; không xóa khi liên kết sâu `/app/y-lenh/B?yl=X` mở ca B; quay Back từ B về `A?yl=X` giữ `yl`. Giá trị `yl` không hợp lệ: về y lệnh trọng tâm và **sửa lại URL** (bỏ `yl` rác) kèm thông báo nhỏ.
15. **"Ra viện" khi đang điều trị:** ở mục II Quản lý người bệnh (`AdministrativeSections.tsx`), nếu lần vào viện hiện tại chưa có thời điểm kết thúc thì hiện "Đang điều trị" thay vì "Chưa ghi nhận" cho Ra viện, Hình thức ra viện, Tổng số ngày điều trị (có thể "Đang điều trị · N ngày" nếu tính được); Chuyển viện đến và Lý do ra viện hiện "Không áp dụng". Bảng lịch sử vào viện cùng quy tắc cho lần đang mở.
16. **Múi giờ cho ngày giờ không có offset:** `lib/displayFormat.ts` (`administrativeDate`) ghép `+07:00` khi chuỗi thiếu offset, hỗ trợ dạng `YYYY-MM-DD HH:mm` (thay khoảng trắng bằng `T`), dùng `hourCycle: 'h23'`; `formatHistoryTime` (`lib/historyTime.ts`) cùng quy tắc, cùng múi `Asia/Ho_Chi_Minh`. Test với chuỗi có/không có offset, có khoảng trắng.
17. **Bỏ trường thừa trong kiểu web:** nếu `TreatmentSheet` trong `web/src/api/types.ts` có `nguon_tep`/`nap_luc` thì bỏ (backend sẽ ngừng trả); giao diện không dùng chúng.

## Nghiệm thu (trong `web/`, dán kết quả)
- `npx vitest run`, `npx oxlint`, `npx tsc -b`, `npm run build` đều qua (hiện 262 test; thêm test cho từng mục trên).
- Mô tả ngắn cách kiểm bằng tay (menu lọc nhiều lựa chọn, tự làm mới, bộ chọn y lệnh bằng bàn phím).
- Báo cáo `plan/reports/T47.md`.

## Cấm làm
- Không commit/push, không đụng `.env`, không thêm thư viện, không dùng `&`, xóa tệp tạm của bạn.
