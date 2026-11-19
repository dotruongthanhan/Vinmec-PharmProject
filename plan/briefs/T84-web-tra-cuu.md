# T84 – Web: bỏ trang Hồ sơ bệnh án, thu gọn ma trận tương tác; 3 trang tra cứu mới

Đọc trước: `AGENTS.md`, `plan/plan-1.4-he-thong-thiet-ke.md`, `plan/reports/T82.md`, `web/src/features/sidebar/SidebarNav.tsx`, `web/src/app/*`, `web/src/features/detail/` (ma trận tương tác), `web/src/api/`.

## Đợt A (làm ngay, không phụ thuộc API mới)

1. **Bỏ tính năng "Hồ sơ bệnh án"** (trang danh sách `MedicalRecordsList` và mục điều hướng; người dùng 20/11: thừa vì đã có "Hồ sơ cần duyệt"). Gỡ route, mục sidebar, phím tắt / tìm kiếm trỏ tới trang đó, test liên quan. **Giữ** tab "Hồ sơ bệnh án" **bên trong** trang chi tiết một ca (hành chính, phiếu điều trị…), chỉ bỏ trang danh sách. Đường dẫn cũ của trang danh sách chuyển hướng về `/app`.
2. **Ma trận "Yếu tố 4 · Tương tác thuốc"** trong tab Thẩm định của trang ca: mặc định **thu gọn**; tiêu đề có mũi tên (chevron) + tóm tắt một dòng (ví dụ "3 thuốc · 1 cặp nghiêm trọng"); bấm mới mở bảng chú giải + ma trận + chi tiết cặp. Nút có `aria-expanded`, điều khiển bằng bàn phím. Liên kết "Mở nhận định" / nhận định trỏ tới ma trận thì tự mở.
3. Chừa chỗ trong sidebar cho 3 mục mới của đợt B (chưa thêm mục nếu chưa có trang).

## Đợt B (sau T83 – dùng `plan/api-hop-dong-v1.8-tra-cuu.md`)

Thêm 3 mục sidebar dưới "Hồ sơ cần duyệt": **Tra cứu thuốc**, **Tra tương tác**, **Tính toán (công thức)**.
- **Tra cứu thuốc** (`/app/thuoc`, `/app/thuoc/:hoat_chat_id`): ô tìm + bảng (phân trang 30, như bảng hồ sơ cần duyệt): hoạt chất, tên Việt, ATC, số chế phẩm, có nhãn FDA, số quy tắc. Bấm dòng → trang chi tiết: thẻ định danh; các mục gập/mở theo nhóm (Chỉ định, Chống chỉ định, Liều, Liều suy thận, Liều suy gan, Cảnh báo, Tương tác, Thai kỳ – cho con bú, Nhi – cao tuổi, Tác dụng phụ, Quá liều, Dược lý); mục "Quy tắc thẩm định" (thận, gan, xét nghiệm, đường dùng, liều tối đa, độc tính, kháng sinh, dị ứng chéo) có nhãn trạng thái duyệt; mục chế phẩm Cục QLD; tóm tắt tương tác DDInter. Mỗi đoạn nhãn FDA hiện nguồn + liên kết DailyMed. Văn bản tiếng Anh của nhãn giữ nguyên, không dịch tự động.
- **Tra tương tác** (`/app/tuong-tac`): nhập nhiều tên thuốc (ô nhập dạng thẻ, Enter để thêm, 2–12 thuốc) → nút "Kiểm tra" → **tái dùng thành phần ma trận của trang ca** (cùng chú giải N/L/T/K/–/?, cùng thẻ chi tiết cặp, cùng căn cứ DDInter). Tên không nhận diện được hiện cảnh báo bên cạnh thẻ.
- **Tính toán** (`/app/cong-thuc`, `/app/cong-thuc/:ma`): danh sách công thức theo nhóm (cơ thể, thận, gan, tim mạch, điện giải); trang một công thức: biểu mẫu sinh từ `dau_vao` (số + chọn đơn vị, lựa chọn), nút Tính, kết quả lớn + đơn vị + ghi chú + `thieu_dau_vao` + tham khảo bài gốc + liên kết tham chiếu MDCalc. Nhãn rõ "Kết quả tham khảo, dược sĩ kiểm chứng".
- Trạng thái tải / lỗi / rỗng dùng `features/states`; tối / sáng đều đúng; bàn phím.

## Kiểm

`tsc -b`, `oxlint`, `vitest` sạch; test cho: sidebar không còn "Hồ sơ bệnh án", ma trận thu gọn / mở, (đợt B) bảng thuốc, trang chi tiết, tra tương tác dùng cùng thành phần ma trận, biểu mẫu công thức. Báo cáo `plan/reports/T84.md`.
