# BỘ CÂU HỎI PHỎNG VẤN KHẢO SÁT CHUYÊN SÂU: DỰ TRÙ TỒN KHO
*(Đã cập nhật toàn bộ câu trả lời từ các buổi phỏng vấn thực tế)*

> **Tình trạng khảo sát:** Đã hoàn tất giải đáp 100% các câu hỏi chuyên sâu về nghiệp vụ Dự trù & Quản lý tồn kho tại Kho Nội trú (B1), Kho T6 và Phòng Quản lý Dược.

---

## I. Xác định Thời điểm & Nhu cầu Dự trù Thuốc

### 1. Tổng quan Thời điểm & Cơ chế Kích hoạt (General Triggers)

* `Tồn < 10 ngày -> Thực tế có kịp hàng về?`
  * **[ĐÃ TRẢ LỜI]:** Thực tế kho không đợi đến dưới 10 ngày mới làm dự trù mà theo dõi chỉ số **"ngày trụ" < 15 ngày** (tính theo tốc độ xuất 5–10 ngày gần nhất) để làm **Dự trù đột xuất (DTĐX) với tần suất cách ngày làm 1 lần**.
  * *Nguyên tắc phủ tồn hiện tại:*
    * **Dự trù thường quy (DTTQ):** Dự trù lượng dùng đến ngày 30 (hết tháng); riêng Vaccine nhân hệ số an toàn **1.8**.
    * **Dự trù đột xuất (DTĐX):** Nếu làm từ ngày 01–15 thì dự trù lượng dùng đến ngày 30 tháng này; nếu làm từ ngày 15–30 thì dự trù lượng dùng đến ngày 10 của tháng sau.

* `Tồn > 10 ngày -> Thuốc nào vẫn phải đặt sớm?`
  * **[ĐÃ TRẢ LỜI]:** Vẫn phải đặt sớm đối với:
    * *Ca bệnh đặc biệt:* Các ca lớn như **ghép gan** có danh mục thuốc bắt buộc phải đảm bảo; khi có thông tin "đánh động" (báo trước) từ lâm sàng là kho phải nhìn lại danh mục và dự trù ngay dù lượng tồn còn nhiều.
    * *Cảnh báo đứt hàng:* Khi có thông tin từ Quản lý Dược về tình trạng đứt mạch hàng / hàng về chậm từ nhà cung cấp.
    * *Thuốc dùng không đều hoặc thuốc chỉ order theo ca bệnh.*

* `Nhu cầu tăng vọt -> Mất bao lâu phát hiện thiếu?`
  * **[ĐÃ TRẢ LỜI]:** Phát hiện nhanh thông qua việc rà soát "ngày trụ" (lượng xuất 5–10 ngày) trong các đợt DTĐX cách ngày 1 lần để xem thuốc có bị biến động đột biến không. Với ca mổ lớn (ghép gan), bác sĩ báo trước ("đánh động"); với thuốc chỉ định theo ca bệnh thì bác sĩ yêu cầu là kho tiến hành làm dự trù ngay.

* `Dự trù đột xuất -> Do tăng dùng hay vendor trễ?`
  * **[ĐÃ TRẢ LỜI]:** Xuất phát từ **cả hai nguyên nhân**:
    * *Do tăng dùng:* Ca bệnh đột xuất (ghép gan), thuốc kê theo người bệnh phát sinh theo yêu cầu bác sĩ.
    * *Do nhà cung cấp (NCC) giao trễ:* Trình dược viên quên đặt đơn, NCC chờ hàng xuất kho rồi quên xuất, NCC chặn đơn... Khi trễ hàng, kho yêu cầu Quản lý Dược push nhà cung cấp; nếu vẫn không giao kịp thì kho phải tự xoay xở bằng cách **đi vay nợ thuốc** từ các viện khác.

---

### 2. Độ trễ Cung ứng & Dòng luân chuyển (Lead Time & Pipeline)

* `Lead Time cố định -> Thực tế có update bao giờ?`
  * **[ĐÃ TRẢ LỜI]:** Thời gian Lead Time **không được cập nhật liên tục** trên file mà chỉ **cập nhật định kỳ mỗi năm một lần (annual update)**. Trong năm, chỉ có ghi chú (note) riêng khi Phòng Quản lý Dược nhận được thông tin phản hồi chính thức từ nhà cung cấp.

* `Nhóm thuốc khác nhau -> Lead Time thực tế lệch mấy ngày?`
  * **[ĐÃ TRẢ LỜI]:** Có sự chênh lệch rõ ràng. Trong công thức DTTQ, mỗi mặt hàng đều có một giá trị **"Hệ số"** thể hiện thời gian Lead Time trung bình từ khi gửi dự trù cho đến khi nhận hàng thực tế. Hệ số này được cấu hình chi tiết **theo từng mặt hàng (SKU level)** chứ **không gom chung theo nhóm hàng**.

* `Lập dự trù -> Làm sao biết hàng đang kẹt PO?`
  * **[ĐÃ TRẢ LỜI]:** Kho theo dõi qua link phản hồi của Quản lý Dược để nắm tình trạng hàng dạo này (đứt mạch, về chậm). Tuy nhiên, với các lô đã về kho vật lý mà file Kiểm soát tồn kho (KSTK) báo trạng thái "Về chưa lên", dược sĩ vẫn phải mất công đi tìm hiểu nội bộ xem vì sao hàng chưa lên hệ thống.

* `Hàng về tới kho -> Kẹt PO mấy ngày chưa lên?`
  * **[ĐÃ TRẢ LỜI]:** Thời gian kẹt PO trung bình khoảng **1 – 2 ngày**.
  * *Phạm vi ảnh hưởng:* Kho T6 (kho vệ tinh) chịu ảnh hưởng tương tự Kho B1 vì B1 là kho nội trú trung tâm nhận hàng từ NCC, còn T6 chỉ nhận hàng điều chuyển lên từ B1.
  * *Hệ quả nghiêm trọng:*
    * Gây **xuất âm** (bác sĩ cần gấp mà hệ thống chưa có tồn khả dụng).
    * Gây **nhiễu loạn điều hành** cho nhân sự xuất kho T6 (không nắm được tình hình cung ứng thực tế, tưởng hết hàng).
    * Dược sĩ làm file KSTK mất nhiều công sức đi tìm hiểu lý do hàng về chưa lên.
    * Dẫn đến **xuất lệch số lô** thực tế so với sổ sách, phải đi kiểm tra lại để chỉnh tay.

* `Lên dự trù B1 -> Có thấy tồn kho Nhà thuốc?`
  * **[ĐÃ TRẢ LỜI]:** Kho B1 **có xem được tồn kho Nhà thuốc**, nhưng hiện tại mọi người chỉ tra cứu thủ công **theo từng mặt hàng thuốc**, hoặc phải xuất file Excel ra để lọc chứ chưa có màn hình tổng hợp đối soát tự động giữa các kho.

* `Tồn kho liên viện/kho -> Có xảy ra thừa thiếu chéo?`
  * **[ĐÃ TRẢ LỜI]:** Có xảy ra tình trạng thiếu hàng cấp bách cục bộ buộc bệnh viện phải đi **vay nợ thuốc** từ các bệnh viện/cơ sở khác khi NCC không giao kịp; đồng thời có phát sinh nhu cầu "điều chuyển thuốc theo yêu cầu" giữa các kho/khoa phòng nội bộ.

---

### 3. Logic Tính toán & Hiệu chỉnh Số lượng (Calculation & Heuristics)

* `Số lượng Excel tính -> Vì sao dược sĩ sửa tay?`
  * **[ĐÃ TRẢ LỜI]:** Dược sĩ phải sửa tay vì công thức Excel chỉ tính toán cơ học, không bao quát được các yếu tố thực tế:
    * *Tính chất dùng đều hay không đều:* Paracetamol dùng đều thì dễ tính, các thuốc khác nhu cầu biến động mạnh thì công thức không phản ánh đúng.
    * *Lịch sử cung ứng & Bệnh nhân trả về:* Ví dụ **Sữa** doanh số xuất (sales) rất cao nhưng do phần mềm OH tự động fill đơn theo chu kỳ (fill routine) nên thực tế bệnh nhân không dùng hết và trả về kho nhiều $\rightarrow$ nếu chỉ nhìn sales trên Excel sẽ dự trù dư thừa lớn.
    * *Hạn dùng / Thuốc cận date:* Phải xem hạn dùng có phù hợp không để ưu tiên xuất tăng nhanh, tránh đặt thêm.
    * *Tình hình đứt mạch hàng:* Căn cứ vào link thông tin từ Quản lý Dược để gia giảm số lượng.
    * *Giá trị đơn hàng lớn (con số lớn):* Phải cân nhắc kỹ ngân sách trước khi chốt số lượng.
    * *Thuốc chỉ order theo ca bệnh và điều chuyển theo yêu cầu.*
    * *Vaccine có công thức riêng:* Phải nhân hệ số an toàn **1.8**.

* `Ghi chú "hàng tt / theo dõi" -> Căn cứ vào đâu?`
  * **[ĐÃ TRẢ LỜI]:**
    * *Ghi chú "Cần theo dõi thêm":* Căn cứ vào so sánh lượng xuất 5–10 ngày xem thuốc có bị biến động đột biến không, lượng tồn hiện tại có dùng đều không để quyết định chưa nhập vội.
    * *Ghi chú "hàng tt" & Cận hạn NCC:* Căn cứ vào thông tin hàng thay thế; riêng đối với NCC, nếu hàng giao có **hạn dùng còn < 1 năm** thì NCC bắt buộc phải báo trước và kho phải xác nhận đồng ý thì mới tiếp nhận.

* `Thuốc theo ca bệnh -> Bác sĩ báo qua kênh nào?`
  * **[ĐÃ TRẢ LỜI]:** Kênh liên lạc giữa bác sĩ và dược sĩ hiện mang tính chất tự do, phổ biến nhất là trao đổi qua **Zalo hoặc gọi điện thoại trực tiếp**. Phần mềm `OH` chỉ được dùng để đánh dấu trạng thái y lệnh: **Thông qua (Approved), Tạm giữ (Hold), hoặc Bỏ (Cancelled)**.

* `Bác sĩ yêu cầu cơ số -> Kho quản lý ở đâu?`
  * **[ĐÃ LÀM RÕ]:** Tại kho B1 **không có quy trình / danh mục quản lý chính thức nào gọi là "Cơ số tối thiểu của Bác sĩ"** (nhân sự kho không dùng khái niệm này). Các yêu cầu riêng của bác sĩ thực chất là nhu cầu thuốc theo từng ca bệnh cụ thể hoặc ca phẫu thuật đặc thù (như ghép gan), được trao đổi trực tiếp để kho lập DTĐX ngay.

---

### 4. Ràng buộc Nhà cung cấp & Ngoại lệ (Vendor Constraints & Edge Cases)

* `Cần gấp 1 thuốc -> Chưa đủ MOQ vendor xử lý sao?`
  * **[ĐÃ TRẢ LỜI]:** Khi cần gấp 1 mặt hàng cho điều trị mà chưa đủ giá trị/số lượng tối thiểu (MOQ) của nhà cung cấp, dược sĩ sẽ **chủ động đẩy tăng số lượng lên cho đủ mức MOQ của Vendor** để đơn được kích hoạt giao hàng khẩn cấp.

* `Quy định MOQ vendor -> Đang lưu đâu, nhớ bằng tay?`
  * **[ĐÃ TRẢ LỜI]:** Bảng quy định MOQ của các Vendor hiện đang được lưu trữ tại **1 file Excel phối hợp dùng chung giữa Phòng Quản lý Dược và Kho Nội trú (Kho B1)**.

* `Vendor báo đứt hàng -> Khi nào biết, đổi thuốc sao?`
  * **[ĐÃ TRẢ LỜI]:** Kho nắm bắt qua link phản hồi của Quản lý Dược về tình trạng đứt mạch hàng / về chậm. Khi hàng trễ/đứt, Quản lý Dược sẽ push nhà cung cấp; nếu NCC vẫn không giao kịp thì kho chủ động đi **vay nợ thuốc** từ các viện khác. Ngoài ra, NCC nếu giao hàng hạn < 1 năm thì phải báo trước và nhận được phản hồi đồng ý từ kho trước khi giao.
