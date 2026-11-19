# T82 – Trang "Y lệnh" thành "Hồ sơ cần duyệt": bảng kiểu hồ sơ bệnh án, phân trang 30 dòng

Agent: **agy Gemini 4 Hydrogen xhigh**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Đọc trước `plan/plan-1.4-he-thong-thiet-ke.md` (thành phần bảng), `web/src/features/orders/OrdersTable.tsx`, `web/src/features/medical-records/MedicalRecordsList.tsx`, `web/src/lib/orders.ts`, `web/src/features/sidebar/SidebarNav.tsx`.

## Người dùng muốn (19/11)

Dược sĩ tìm việc theo **hồ sơ người bệnh**, không theo mã y lệnh. Trang hiện tại "Y lệnh – Tất cả y lệnh" đổi thành **"Hồ sơ cần duyệt"**: chỉ hiện hồ sơ **đang có y lệnh chờ duyệt**, hồ sơ có y lệnh mới / ưu tiên cao lên đầu – **đúng logic sắp xếp, lọc của bảng y lệnh hiện tại**. Giao diện là bảng giống "Hồ sơ bệnh án", ghép thêm các cột của bảng y lệnh.

## Yêu cầu

1. **Tên:** mục điều hướng bên trái "Y lệnh" → "Hồ sơ cần duyệt" (biểu tượng giữ hoặc đổi sang biểu tượng hồ sơ có dấu kiểm); tiêu đề trang "Hồ sơ cần duyệt", bộ đếm "N hồ sơ"; breadcrumb trang chi tiết "Hồ sơ cần duyệt › …". Đường dẫn (`/app`, `/app/y-lenh/:ca_id`) **giữ nguyên** để không gãy liên kết.
2. **Cột** (theo thứ tự): Ưu tiên · Thời điểm kê (y lệnh chờ duyệt mới nhất) · Mã BN · Người bệnh (tên in hoa nếu có + giới, tuổi – như bảng hồ sơ) · Ngày sinh · Khoa · Chẩn đoán chính · Trạng thái · Cảnh báo AI. **Bỏ** "Mã y lệnh", "Thời điểm vào viện", "Y lệnh (lần cuối)". Dữ liệu lấy từ cùng `DongHangDoi` đang dùng (đã có `ngay_sinh`, `chan_doan_chinh`, `ho_ten`…); thiếu trường nào thì ghi "Chưa ghi nhận" như bảng hồ sơ.
3. **Giữ nguyên hành vi** của `OrdersTable`: sắp xếp theo cột, menu lọc từng cột, ô cảnh báo AI, bấm dòng mở trang chi tiết (`/app/y-lenh/:ca_id`), tìm kiếm Ctrl K. Ưu tiên tái dùng `OrdersTable` (đổi cấu hình cột) thay vì viết bảng mới.
4. **Phân trang 30 dòng/trang** (phía web): sắp xếp và lọc trên **toàn bộ** danh sách rồi mới cắt trang; thanh phân trang dưới bảng ("1–30 / 67", Trước / Sau, số trang); đổi bộ lọc / sắp xếp / tìm kiếm → về trang 1; giữ trang hiện tại khi quay lại từ trang chi tiết (lưu trong URL `?trang=2`). Trang "Hồ sơ bệnh án" thêm phân trang 30 dòng như vậy.
5. Trang "Hồ sơ bệnh án" giữ nguyên cột và hành vi.

## Thêm – test backend còn trượt (T81-fix-1)

`tests/rules/test_toxicity.py::test_all_unresolved_lines_do_not_emit_dat_and_partial_excludes_unresolved` dòng ~942–949: kỳ vọng `== []` nhưng luật trả đúng một nhận định `doc_than_cong_don_thieu_du_lieu` (`khong_du_du_lieu`) cho thuốc đang dùng chưa phân giải. Ý của test là **không có nhận định `dat`** → sửa assert thành: không có `ket_luan == "dat"` và không có `doc_tinh_khong_thuoc_danh_sach`. Không sửa `app/`.

## Test

Cập nhật / thêm test web (`web/src/__tests__/ordersTable.test.ts`, `medicalRecords.test.tsx`, sidebar): nhãn mới; cột mới / cột bị bỏ; 67 dòng → trang 1 có 30, trang 3 có 7; đổi bộ lọc về trang 1; sắp xếp áp dụng trước khi cắt trang. `tsc -b`, `oxlint`, `vitest` sạch.

## Phạm vi

`web/src/` (orders, medical-records, sidebar, order-detail breadcrumb, lib), test web, `tests/rules/test_toxicity.py`. Cấm `app/`, `data/`. Báo cáo `plan/reports/T82.md`.
