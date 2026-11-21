# T41 – Thanh bên trái: mục "Y lệnh" và "Hồ sơ bệnh án"

## Bối cảnh
Thanh bên trái của bàn làm việc (`web/src/features/sidebar/SidebarNav.tsx`) đang để trống ở giữa (khối `flex-1` có `aria-hidden`). Dược sĩ cần hai mục điều hướng ở đó:

1. **Y lệnh**: về danh sách y lệnh (`/app`), hành vi như hiện tại.
2. **Hồ sơ bệnh án**: mở trang danh sách hồ sơ bệnh án; bấm một hồ sơ thì xem hồ sơ bệnh án của ca đó trước (không cần vào tab Thẩm định).

Dữ liệu vẫn đọc từ API hiện có (tệp `data/mock/demo`, 6 ca). KHÔNG nối Supabase trong task này.

## Phạm vi file (được sửa/tạo)
- `web/src/features/sidebar/SidebarNav.tsx` (thêm hai mục, hỗ trợ trạng thái thu gọn 56 px có tooltip, trong drawer cũng hiện).
- `web/src/app/router.tsx` (thêm route `/app/ho-so` dưới `ProtectedRoute`).
- `web/src/app/WorkspacePage.tsx` và `AppShell.tsx` nếu cần truyền cờ mục đang chọn.
- Thư mục mới `web/src/features/medical-records/` (trang danh sách hồ sơ).
- Test mới/cập nhật trong `web/src/__tests__/` (cập nhật `sidebarSession.test.tsx` nếu vỡ).

Cấm đụng: `app/` (Python), `data/`, `db/`, `plan/` ngoài báo cáo, `web/vite.config.ts`, hợp đồng API.

## Yêu cầu
1. Hai mục dùng icon `lucide-react` (ví dụ `ClipboardList`, `FileText`), đặt dưới tiêu đề sản phẩm, trên vùng trống. Mục đang chọn tô nổi, có `aria-current="page"`. Bám `plan/plan-1.4-he-thong-thiet-ke.md` (token màu nền tối `ink`).
2. Chọn mục đang sáng theo route: `/app` và `/app/y-lenh/:caId` → "Y lệnh"; `/app/ho-so` → "Hồ sơ bệnh án".
3. Trang `/app/ho-so`: bảng danh sách hồ sơ dùng dữ liệu danh sách ca đã có (cùng nguồn với danh sách y lệnh): mã BN, người bệnh (giới, tuổi), khoa, chẩn đoán chính, thời điểm vào viện, số y lệnh. Có ô tìm kiếm của thanh trên vẫn hoạt động nếu dễ; không bắt buộc.
4. Bấm một dòng → `navigate('/app/y-lenh/<caId>?tab=ho_so_benh_an')` (tab này đã tồn tại, xem `OrderDetailView.tsx`). Nếu danh sách ca chưa có trường nào ở trên thì dùng trường sẵn có, thiếu thì để "—", không đổi API.
5. Trạng thái tải, rỗng, lỗi dùng các thành phần trạng thái sẵn có (`web/src/features/states`).
6. Không đổi hành vi đăng nhập/đăng xuất, phím tắt, ngăn kéo di động.

## Nghiệm thu (chạy trong `web/`)
- `npm test -- --run` qua hết (hiện 231 test); thêm test: hai mục hiện, mục đúng được chọn theo route, bấm "Hồ sơ bệnh án" đi `/app/ho-so`, bấm dòng đi đúng URL có `tab=ho_so_benh_an`.
- `npx oxlint`, `npx tsc -b`, `npm run build` đều sạch.
- Ghi báo cáo vào `plan/reports/T41.md` (file đã đổi, lệnh đã chạy, kết quả).

## Cấm làm
- Không commit, không push.
- Không thêm thư viện mới. Không đụng khóa/bí mật.
