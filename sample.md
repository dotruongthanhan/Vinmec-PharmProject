Với dự án **CDSS hỗ trợ duyệt y lệnh nội trú**, bạn **không cần** làm việc với *Dược sĩ kho thuốc* hay *Dược sĩ nhà thuốc* (vì nghiệp vụ của họ nằm ở khâu hậu cần/cấp phát sau khi đơn đã duyệt).

Thay vào đó, bạn chỉ cần tập trung vào **4 nhóm đối tượng liên quan trực tiếp** theo thứ tự ưu tiên:
1. **Dược sĩ lâm sàng - DSLS** *(Trọng tâm số 1 — cả quan sát lẫn phỏng vấn sâu)*
2. **Nhân sự CNTT / Quản trị hệ thống HIS** *(Bắt buộc phỏng vấn để chốt khả thi kỹ thuật & bảo mật)*
3. **Lãnh đạo Khoa Dược / Phụ trách Dược lâm sàng** *(Phỏng vấn về bản quyền dữ liệu, pháp lý & phạm vi PoC)*
4. **Bác sĩ nội trú & Điều dưỡng tại 1 khoa trọng điểm** *(Quan sát & hỏi nhanh để kiểm chứng luồng kê đơn - thực hiện)*

Dưới đây là bảng tách bạch chi tiết những gì bạn **tự nhìn/đo đếm được bằng mắt** và những gì **phải đặt câu hỏi trực tiếp**:

---

## I. NỘI DUNG CÓ THỂ QUAN SÁT TRỰC TIẾP (Shadowing tại chỗ)
*Mục tiêu: Thu thập bằng chứng khách quan ngay trên màn hình làm việc thực tế mà không cần hỏi lý thuyết (rất đắt giá cho mục "Bằng chứng mới" trong báo cáo tuần).*

### 1. Quan sát tại bàn làm việc của Dược sĩ lâm sàng (DSLS)
* **Cấu trúc dữ liệu thật trên màn hình HIS/EMR:**
  * Nhìn vào 1 y lệnh trên màn hình: Liều lượng, đường dùng, tần suất, dung môi nằm ở **từng ô dữ liệu riêng biệt (dropdown/số)** hay bác sĩ gõ gộp thành 1 câu văn tự do?
  * Mục Chẩn đoán có hiển thị sẵn mã **ICD-10** không?
  * Các trường **Cân nặng, Chiều cao, Tiền sử dị ứng** trên thực tế có được điền đầy đủ không hay thường xuyên bị bỏ trống?
  * Kết quả xét nghiệm (`Creatinin`, men gan...) hiển thị dạng bảng số liệu trực tiếp trên HIS hay DSLS phải bấm mở file ảnh/PDF scan?
* **Luồng thao tác & Công cụ rời rạc:**
  * Đếm số phần mềm/tab trình duyệt DSLS phải mở song song để duyệt 1 ca phức tạp (HIS, *UpToDate*, *MIMS*, *MDCalc*, file *Excel* tính dinh dưỡng, cổng BHYT `vis.vinmec.com`).
  * Xem trực tiếp cấu trúc bảng tính *Excel* dinh dưỡng họ đang nhập tay gồm những biến số và công thức gì.
* **Kiểm chứng "công cụ AI sơ bộ" hiện có:** Quan sát xem trên màn hình HIS lúc duyệt đơn có hiện ra pop-up/cảnh báo tự động nào không (như ghi nhận ngày 29/10 trong [10-29.md](file:///Users/dotruongthanhan/Documents/GitHub/Vinmec-PharmProject/docs/notes/10-29.md)) và cách DSLS phản ứng với nó.
* **Bấm giờ đo lường thực tế (Baseline KPIs):**
  * Đo thời gian thực tế DSLS xử lý 10–15 hồ sơ liên tiếp: Ca thường quy mất bao nhiêu giây? Ca phức tạp mất bao nhiêu phút?
  * Nhìn số lượng y lệnh tồn đọng trên hàng đợi vào khung giờ cao điểm (thường 9h00–11h00 sáng sau giờ bác sĩ đi buồng).
  * Quan sát trực tiếp 1 tình huống DSLS **Hold đơn** và gọi điện cho bác sĩ (mất bao lâu để kết nối và xử lý xong).

### 2. Quan sát ngắn tại khoa lâm sàng: Bác sĩ nội trú & Điều dưỡng
* **Quan sát Bác sĩ (lúc nhập y lệnh trên HIS):** Xem bác sĩ thao tác kê đơn mất bao lâu, chọn thuốc/liều từ danh mục gợi ý hay gõ tay tự do; màn hình kê đơn hiện tại có bật cảnh báo nào gây cản trở không; khi sửa lại đơn bị *Hold* phải qua mấy bước.
* **Quan sát Điều dưỡng (trước khi tiêm/truyền & khi ghi hồ sơ):** Xem điều dưỡng đọc y lệnh trên phiếu in hay màn hình máy tính/máy tính bảng tại xe tiêm; xem cách họ nhập báo cáo theo dõi bệnh nhân lên HIS (chọn theo biểu mẫu có sẵn hay gõ đoạn văn tự do).

---

## II. NỘI DUNG PHẢI HỎI TRỰC TIẾP (Phỏng vấn đúng vai trò)
*Mục tiêu: Xác nhận các quy định ngầm, tần suất thống kê dài hạn, bản quyền, hạ tầng kỹ thuật và ranh giới dự án mà mắt thường không nhìn thấy được.*

### 1. Hỏi Dược sĩ lâm sàng (DSLS)
* **Thống kê lỗi & Can thiệp:** Trung bình mỗi tuần/tháng tỷ lệ y lệnh phải *Hold* hoặc gọi bác sĩ điều chỉnh là bao nhiêu? **Top 3 nhóm lỗi phổ biến nhất** là gì (quá liều trên bệnh nhân suy thận, tương tác thuốc, kháng sinh, chống đông, dinh dưỡng, hay vướng điều kiện BHYT)?
* **Lý do công cụ cũ chưa hiệu quả:** Công cụ sàng lọc sơ bộ từng được nhắc tới là gì và tại sao thực tế lại không dùng được (báo động giả quá nhiều, thiếu dữ liệu xét nghiệm đi kèm, hay dữ liệu cũ)?
* **Nguồn tài liệu nội bộ:** Bộ Guideline nội bộ của viện hiện lưu trữ ở đâu, có bao nhiêu phác đồ trọng tâm, định dạng Word/PDF chữ hay ảnh scan?
* **Bài toán ưu tiên số 1 cho PoC:** Nếu chọn **1 khoa lâm sàng** và **1–2 nhóm thuốc** đau đầu nhất để làm thử nghiệm trước trong 1 tháng, DSLS muốn chọn bài toán nào? Chấp nhận được tối đa bao nhiêu % cảnh báo dư thừa (*False Positive*)?

### 2. Hỏi Bác sĩ nội trú & Điều dưỡng (hỏi nhanh 10–15 phút)
* **Với Bác sĩ:** Khi đang vội kê đơn, bác sĩ **chỉ muốn thấy** loại cảnh báo nào hiện lên màn hình (VD: dị ứng nặng, tự động gợi ý liều theo `CrCl` mới nhất)? Nếu có nút tích chọn nhanh *"Lý do lâm sàng khi kê liều đặc biệt"* để DSLS không phải gọi điện hỏi lại, bác sĩ có sẵn sàng tích không?
* **Với Điều dưỡng:** Những câu hỏi nào điều dưỡng hay phải gọi điện hỏi DSLS nhất trong ca trực (cách pha hoàn nguyên, dung môi tương hợp, truyền chung dây chữ Y, tốc độ truyền, có được nghiền viên qua ống thông dạ dày không)?

### 3. Hỏi Lãnh đạo Khoa Dược / Phụ trách chuyên môn (Cấp quản lý & Pháp lý)
* **Bản quyền dữ liệu thuốc:** Tài khoản *UpToDate* và *MIMS* bệnh viện đang mua chỉ cho phép đọc trên web hay có gói **tích hợp API/Cơ sở dữ liệu**? Nếu không có API thương mại, Hội đồng Thuốc & Điều trị cho phép dùng nguồn chính thống nào làm chuẩn gốc cho AI (Dược thư Quốc gia, Tờ HDSD được Cục Quản lý Dược duyệt, Guideline nội bộ Vinmec)?
* **Cơ chế phê duyệt & Ranh giới dự án:** Hội đồng nào sẽ đứng ra thẩm định độ an toàn y khoa của CDSS trước khi thử nghiệm? Đơn vị công nghệ nội bộ (như VSF) hiện có đang phát triển module CDSS tương tự nào không để tránh dẫm chân nhau?

### 4. Hỏi Nhân sự CNTT / Quản trị HIS & An ninh thông tin (Chốt chặn kỹ thuật sống còn)
*(Không thuộc khối lâm sàng nhưng bắt buộc phải hỏi để chứng minh dự án làm được về mặt kỹ thuật)*
* **Khả năng lấy dữ liệu & Tích hợp giao diện:** Hệ thống HIS hiện tại có mở được API/Database đọc thời gian thực (bệnh án, xét nghiệm LIS, y lệnh) không? Có cho phép nhúng cảnh báo vào màn hình HIS không, hay giai đoạn PoC bắt buộc phải làm **Web Dashboard chạy độc lập bên cạnh HIS**?
* **Chuẩn hóa danh mục:** Danh mục thuốc trên HIS đã được gắn mã hoạt chất chuẩn (mã ATC / tên gốc INN) chưa?
* **Bảo mật dữ liệu bệnh nhân & Hạ tầng máy chủ:** Quy định an ninh thông tin của Tập đoàn có cho phép gửi dữ liệu lâm sàng (đã ẩn danh thông tin cá nhân) lên dịch vụ Cloud AI Enterprise không, hay **bắt buộc 100% đặt mô hình On-premise nội bộ**? Nếu chạy nội bộ thì hạ tầng máy chủ GPU hiện đã có sẵn chưa?

---

### 📌 Tóm tắt nhanh lịch trình khảo sát gợi ý

| Đối tượng cần gặp | Hình thức | Thời lượng gợi ý | Đầu ra cần cầm về |
| :--- | :--- | :---: | :--- |
| **Dược sĩ lâm sàng** | Quan sát màn hình + Phỏng vấn | 60–90 phút | Cấu trúc trường dữ liệu HIS thực tế, thời gian duyệt trung bình/ca, file mẫu công thức tính tay, chốt 1 bài toán PoC hẹp. |
| **Bác sĩ & Điều dưỡng (1 khoa)** | Quan sát nhanh + Hỏi ngắn | 20–30 phút | Thao tác kê đơn/thực hiện y lệnh thực tế, danh sách thông tin cần hiển thị không gây phiền (*Alert Fatigue*). |
| **Quản trị IT / HIS** | Phỏng vấn kỹ thuật | 30–45 phút | Khả năng trích xuất dữ liệu HIS/LIS, phương án giao diện (nhúng hay độc lập), quy định bảo mật Cloud vs. On-prem. |
| **Lãnh đạo Khoa Dược** | Phỏng vấn quản lý | 20–30 phút | Pháp lý bản quyền dữ liệu thuốc chuẩn, hội đồng nghiệm thu y khoa, ranh giới với dự án của VSF. |