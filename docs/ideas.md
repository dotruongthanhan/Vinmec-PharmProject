# ĐỀ XUẤT Ý TƯỞNG DỰ ÁN CHUYỂN ĐỔI SỐ & AI KHOA DƯỢC (VINMEC)

> **Cơ sở xây dựng:** Tổng hợp từ kết quả khảo sát và phỏng vấn thực tế ngày 29/10, 30/10 và 31/10 tại Phòng Dược Lâm Sàng, Phòng Quản lý Dược, Phòng Nghiệp vụ Dược & Điều chế, Kho Dược Nội trú (B1 & T6) và Nhà thuốc Bệnh viện.  
> **Nguyên tắc ghi nhận:** Ghi theo vai trò chuyên môn, không nêu tên cá nhân.

---

## TỔNG QUAN 2 DỰ ÁN TRỌNG TÂM

| Tiêu chí | Dự án 1: CDSS Hỗ trợ Duyệt & Thực thi Y lệnh Nội trú | Dự án 2: Dự báo Tồn kho Động & Cảnh báo Hàng xuất nhanh |
| :--- | :--- | :--- |
| **Mảng nghiệp vụ** | Dược lâm sàng & An toàn sử dụng thuốc nội trú | Quản trị chuỗi cung ứng, Kho dược & Mua sắm dược phẩm |
| **Đối tượng chính** | Dược sĩ lâm sàng (kết nối Bác sĩ nội trú & Điều dưỡng) | Kho Dược nội trú (B1/T6), Phòng Quản lý Dược, Nhà thuốc |
| **Giá trị cốt lõi** | Tăng tốc độ & chất lượng thẩm định ca bệnh phức tạp; giảm sai sót y lệnh và giảm quá tải hỏi đáp thủ công | Chống đứt gãy thuốc lâm sàng do xuất đột biến; xóa bỏ thao tác copy-paste thủ công; tối ưu ngân sách & hạn dùng |
| **Định hướng công nghệ** | Data Fusion + Rule Engine + Explainable AI / RAG | Data Unification + Smart Velocity Alerting + Time-series AI & Optimization |

---

## DỰ ÁN 1: HỆ THỐNG HỖ TRỢ RA QUYẾT ĐỊNH LÂM SÀNG (CDSS) HỖ TRỢ DUYỆT Y LỆNH NỘI TRÚ

### 1. Ai đang gặp vấn đề? (Đối tượng liên quan)
* **Đối tượng trực tiếp (Trọng tâm số 1):** **Dược sĩ lâm sàng (DSLS)** thuộc Phòng Dược Lâm Sàng — người chịu trách nhiệm rà soát hồ sơ bệnh án, kiểm tra tính an toàn/hợp lý của thuốc và ra quyết định Phê duyệt (`Approve`) hoặc Tạm dừng (`Hold đơn`) y lệnh nội trú.
* **Đối tượng liên đới trong cùng luồng nghiệp vụ:**
  * **Bác sĩ điều trị nội trú:** Người kê y lệnh ban đầu dưới áp lực thời gian đi buồng lớn, dễ thiếu thông tin dược lý/chỉ số xét nghiệm mới nhất dẫn đến phải chỉnh sửa lại đơn khi bị *Hold*.
  * **Điều dưỡng nội trú:** Người trực tiếp pha truyền, cho người bệnh dùng thuốc và theo dõi tại giường; thường xuyên cần tra cứu nhanh cách dùng, dung môi, tương kỵ đường truyền trước khi thực hiện.

### 2. Pain point đang gặp là gì? (Hiện trạng nỗi đau)
* **Mất nhiều thời gian đọc gom dữ liệu & khó nắm bắt mục đích y lệnh:** Dữ liệu phục vụ duyệt đơn (chẩn đoán, kết quả và hình ảnh xét nghiệm, chỉ số sinh tồn, báo cáo điều dưỡng, lịch sử dùng thuốc) nằm rải rác ở nhiều mục trên HIS/EMR, buộc DSLS phải mở đọc và tổng hợp thủ công từng ca.
* **Thao tác tính toán và tra cứu bị phân mảnh trên nhiều công cụ ngoài:** DSLS phải nhập tay chỉ số bệnh nhân lên web *MDCalc* (tính độ thanh thải creatinin `CrCl`), nhập tay vào bảng *Excel* riêng (tính công thức dinh dưỡng), tra cứu liều/tương tác trên *UpToDate*, *MIMS* và đối chiếu điều kiện thanh toán BHYT trên `vis.vinmec.com`.
* **Chưa có công cụ đủ sâu cho các ca bệnh nội trú phức tạp:** Thực tế chưa có AI hỗ trợ trong quy trình duyệt sâu; công cụ sàng lọc sơ bộ (nếu có) chỉ dừng ở tra cứu thông tin cơ bản, không giải quyết được bài toán phối hợp đa thuốc (thuốc đang dùng + y lệnh mới) trên nền bệnh nhân suy thận, hậu phẫu nặng.
* **Quá tải giao tiếp thủ công khi can thiệp và hỗ trợ khoa phòng:** Khi phát hiện bất thường, DSLS phải tạm dừng đơn và gọi điện trực tiếp cho bác sĩ kê đơn; đồng thời liên tục giải đáp các câu hỏi lặp lại của bác sĩ, điều dưỡng về tương tác và cách dùng thuốc.
* **Tra cứu quy chuẩn nội bộ hạn chế:** Hệ thống lưu trữ tài liệu hiện tại chỉ tìm kiếm theo tiêu đề/từ khóa (chưa tìm theo ngữ nghĩa) và đang bị quá tải dung lượng lưu trữ.

### 3. Mục tiêu của dự án
* **Tập trung hóa & Tự động hóa thẩm định y lệnh:** Gom toàn bộ dữ liệu bệnh án, thuốc và công cụ tính toán về một luồng công việc thống nhất, giúp DSLS nắm bắt bối cảnh tức thì và rút ngắn đáng kể thời gian duyệt mỗi ca phức tạp.
* **Thiết lập mô hình an toàn thuốc 3 lớp (Shift-Left Safety):** Hỗ trợ Bác sĩ kê đơn chuẩn xác ngay từ đầu → giúp DSLS thẩm định chuyên sâu với căn cứ rõ ràng → giúp Điều dưỡng kiểm tra thực hành an toàn trước khi tiêm truyền.
* **Chuẩn hóa tuân thủ phác đồ & BHYT:** Giảm tỷ lệ phải *Hold đơn* muộn, giảm tải hỏi đáp thủ công qua điện thoại và hạn chế rủi ro xuất toán BHYT.

### 4. Dự án giải quyết nguyên nhân gốc rễ nào của Pain point?
* **Giải quyết sự phân mảnh dữ liệu bệnh án (Data Silos):** Tự động kết nối và tổng hợp ngữ cảnh từ 3 nguồn (Hồ sơ bệnh án EMR + Đơn thuốc/Y lệnh + Cơ sở dữ liệu tri thức thuốc) thay vì để nhân sự tự đọc gom thủ công.
* **Giải quyết sự rời rạc của công cụ chuyên môn:** Tích hợp trực tiếp các công thức tính toán y khoa (`CrCl`, dinh dưỡng...) và bộ đối chiếu phác đồ/tương tác vào ngay màn hình xử lý y lệnh.
* **Giải quyết độ vênh thông tin ("không rõ ý đồ kê đơn") giữa Bác sĩ và DSLS:** Cung cấp cảnh báo sớm tinh gọn lúc kê đơn và cho phép bác sĩ gắn nhanh lý do lâm sàng khi chỉ định liều đặc biệt để DSLS thấy ngay mà không cần gọi điện xác minh lại.
* **Giải quyết giới hạn tìm kiếm từ khóa của kho tài liệu nội bộ:** Ứng dụng tìm kiếm ngữ nghĩa (Semantic Search / RAG) có kiểm soát bảo mật và giữ nguyên vẹn tài liệu gốc của bệnh viện.

### 5. Các Feature dự kiến trong dự án
1. **Tổng hợp bối cảnh lâm sàng tự động (Patient Clinical Snapshot):** Tự động trích xuất và đặt cạnh y lệnh các thông tin cốt lõi gần nhất: chẩn đoán, tiền sử dị ứng, diễn tiến hậu phẫu/ghi chú điều dưỡng, sinh hiệu, xét nghiệm bất thường và toàn bộ thuốc đang dùng.
2. **Tự động tính toán chỉ số & công thức lâm sàng (Auto-Clinical Calculators):** Tự động tính độ thanh thải creatinin (`CrCl` / `eGFR`), diện tích da (`BSA`), cân nặng hiệu chỉnh và lập công thức dinh dưỡng nội trú ngay khi có dữ liệu xét nghiệm mới trên HIS (thay thế *MDCalc* và *Excel*).
3. **Sàng lọc an toàn thuốc đa chiều & Kiểm tra điều kiện BHYT:**
   * Phát hiện mâu thuẫn hoạt chất, quá liều/thiếu liều theo chức năng thận - gan - tuổi - cân nặng, và tương tác có ý nghĩa lâm sàng giữa *thuốc đang dùng + y lệnh mới*.
   * Đối chiếu tự động với Guideline nội bộ Vinmec (như kiểm soát nguy cơ hậu phẫu, kháng sinh) và rà soát điều kiện chi trả BHYT để hỗ trợ chuẩn bị thông tin giải trình sớm.
4. **Hiển thị "Chuỗi suy luận logic" tường minh & Trích dẫn nguồn (Explainable AI):** Trình bày rõ ngay từ đầu: *Dấu hiệu bất thường từ chỉ số nào (ngày giờ nào) → Thuốc và liều đang dùng → Căn cứ điều khoản nào trong Guideline/Dược thư → Đề xuất chỉnh sửa cụ thể*, tuyệt đối không cảnh báo kiểu "hộp đen".
5. **Giao diện phân vai 3 góc nhìn (chống "Nhờn cảnh báo" - Alert Fatigue) & Trợ lý hỏi đáp nội bộ:**
   * *Góc nhìn Bác sĩ:* Chỉ hiển thị gợi ý liều nhanh và cảnh báo mức độ Nghiêm trọng + ô tích nhanh *"Lý do lâm sàng"* khi vượt cảnh báo.
   * *Góc nhìn DSLS:* Phân luồng ưu tiên ca nguy cơ cao lên đầu hàng đợi (Triage); màn hình thẩm định đầy đủ; nút thao tác `[Duyệt]` hoặc `[Hold đơn & Gửi đề xuất chỉnh sửa chuẩn hóa cho Bác sĩ]`.
   * *Góc nhìn Điều dưỡng & Chatbot tri thức nội bộ (kiểu NotebookLM bảo mật):* Tra cứu nhanh dung môi pha, tốc độ truyền, tương kỵ truyền chung dây chữ Y, dấu hiệu cần theo dõi sau dùng thuốc và hỏi đáp thông minh trên kho tài liệu quy chuẩn Vinmec.

---

## DỰ ÁN 2: HỆ THỐNG DỰ BÁO TỒN KHO ĐỘNG & CẢNH BÁO HÀNG HÓA XUẤT NHANH

### 1. Ai đang gặp vấn đề? (Đối tượng liên quan)
* **Nhân sự vận hành Kho Dược nội trú (Kho trung tâm B1 & Kho vệ tinh T6):** Người trực tiếp kiểm tra tồn kho định kỳ 3–4 ngày/lần, điều chuyển hàng giữa B1 và T6, kiểm soát số lô/hạn dùng và lập dự trù mua hàng.
* **Nhân sự phụ trách Phòng Quản lý Dược (Hệ thống):** Người quản lý danh mục, tổ chức thầu/hợp đồng với nhà cung cấp (NCC), cân đối ngân sách và phê duyệt dự trù định kỳ/đột xuất từ các kho và nhà thuốc.
* **Quản lý & Dược sĩ Nhà thuốc bệnh viện (vận hành 24/7):** Người theo dõi tồn kho trên phần mềm OH và lập dự trù thường quy (chu kỳ 30 ngày) và dự trù đột xuất (chu kỳ 10 ngày) trên *Excel*.
* **Các bên liên đới:** Bác sĩ điều trị & người bệnh (chịu tác động trực tiếp nếu hết thuốc kê đơn); Phòng Nghiệp vụ Dược (liên quan nhập hóa đơn HIS/SAP, quản lý thầu BHYT và hồ sơ dự trù thuốc gây nghiện/hướng thần trình Sở Y tế).

### 2. Pain point đang gặp là gì? (Hiện trạng nỗi đau)
* **Nguy cơ đứt gãy tồn kho do "xuất nhanh đột xuất":** Hàng hóa dự kiến đủ dùng 2 tháng nhưng phát sinh tiêu thụ lâm sàng tăng vọt khiến tồn kho sụt giảm nhanh (chỉ còn đủ ~30 ngày trong khi `Lead Time` đặt - nhận hàng mất ~0.5 tháng, hoặc lâu hơn với thuốc kiểm soát đặc biệt). Nếu nhân sự kho không kịp phát hiện thủ công sẽ dẫn đến hết thuốc cho bác sĩ kê đơn.
* **Tốn nhiều thời gian gom dữ liệu rời rạc & Copy-paste thủ công:** Nhân viên kho phải rà soát dày đặc 3–4 ngày/lần, mở nhiều nguồn (tồn kho B1, tồn kho T6, dữ liệu OH, bảng hệ số cố định, danh mục biến động) và liên tục sao chép - dán giữa các bảng *Excel* để tính dự trù rồi trình duyệt qua nhiều cấp.
* **Khó kiểm soát tồn kho do phân mảnh mã quản lý (1 mặt hàng vật lý = tối đa 4 mã):** Một loại thuốc thực tế bị tách thành 4 mã theo diện chi trả (`AY` - BHYT vs `AA` - Tự nguyện) và hình thức điều trị (`D-CARE` vs `non-D-CARE`), không có cơ chế tự động bù trừ/chuyển đổi linh hoạt giữa các mã, gây nghẽn khi nhập/xuất và làm méo mó bức tranh tồn kho thực.
* **Độ trễ dữ liệu "hàng treo" & Khó kiểm soát lô/cận date:** Hàng đã giao tới kho nhưng chờ nhập hóa đơn thủ công lên HIS/SAP làm sai lệch số tồn trên hệ thống; hàng chậm luân chuyển ít giao dịch dễ bị bỏ sót dẫn tới cận date; áp lực cấp phát nhanh gây lệch số lô thực tế trên kệ so với lô hệ thống tự trừ theo lý thuyết.
* **Phức tạp khi cân đối ngân sách với điều kiện giao hàng của NCC:** Khó tính toán thủ công để vừa nằm trong hạn mức ngân sách (Budget), vừa làm tròn theo bội số quy cách đóng gói (hộp/lọ), vừa đủ ngưỡng tối thiểu để NCC chịu xuất hóa đơn giao hàng (MOQ).

### 3. Mục tiêu của dự án
* **Triệt tiêu rủi ro bỏ sót "xuất nhanh đột xuất":** Tự động giám sát tốc độ tiêu thụ thực tế đối chiếu với `Lead Time` giao hàng để kích hoạt cảnh báo đặt hàng/điều chuyển sớm, đảm bảo không đứt gãy cung ứng thuốc lâm sàng.
* **Tự động hóa quy trình lập và duyệt dự trù:** Giảm tối đa thao tác gom file và copy-paste *Excel* thủ công mỗi 3–4 ngày tại Kho B1, T6 và Nhà thuốc.
* **Tối ưu hiệu quả vốn tồn kho & Giảm hủy cận date:** Cân đối chính xác giữa mức dự trữ an toàn, trần ngân sách (Budget), điều kiện xuất hóa đơn của NCC (MOQ), hạn mức thầu BHYT và vòng đời hạn sử dụng của thuốc.

### 4. Dự án giải quyết nguyên nhân gốc rễ nào của Pain point?
* **Giải quyết phương pháp dự báo cơ học, bị động theo quá khứ:** Thay thế cách lấy số xuất tháng trước gán cứng cho tháng này bằng cơ chế đo gia tốc tiêu thụ ngắn hạn kết hợp mô hình dự báo chuỗi thời gian có tính biến động lâm sàng và mùa vụ.
* **Giải quyết sự phụ thuộc vào theo dõi thủ công của con người:** Thay thế việc nhân viên phải tự mở bảng tính dò tìm hàng cạn kho 3–4 ngày/lần bằng hệ thống tự động tính *Số ngày tồn kho còn lại (Days of Supply)* liên tục mỗi ngày.
* **Giải quyết tình trạng phân tán nguồn dữ liệu & chia cắt mã quản lý:** Xây dựng lớp hợp nhất dữ liệu tự động gom tồn kho đa điểm (B1, T6, OH, hàng đang đặt, hàng chờ nhập hóa đơn) và quy chiếu đồng thời 4 mã hạch toán (`AA`, `AY`, `D-CARE`, `non-D-CARE`) về cùng 1 mặt hàng vật lý gốc.
* **Giải quyết bài toán tính toán đa ràng buộc thủ công:** Tự động hóa quy tắc làm tròn quy cách đóng gói, kiểm tra ngưỡng xuất hóa đơn tối thiểu của NCC và tối ưu phân bổ ngân sách.

### 5. Các Feature dự kiến trong dự án
1. **Bảng tổng hợp tồn kho hợp nhất & Quy chiếu đa mã (Unified Inventory & Multi-code Mapping):**
   * Tự động kết nối số liệu tồn kho thời gian thực từ Kho B1, Kho T6, Nhà thuốc (OH) cùng dữ liệu `Hàng đã đặt chưa về` và `Hàng đã về chưa nhập hóa đơn`.
   * Hiển thị song song **Tồn kho vật lý thực tế (gộp SKU)** và **Tồn kho từng mã thành phần (`AA/AY`, `D-CARE/non-D-CARE`)** kèm theo dõi tiến độ hạn mức thầu BHYT.
2. **Động cơ cảnh báo sớm "Xuất nhanh đột xuất" theo Lead Time (Dynamic Runway & Spike Alerting):**
   * Liên tục so sánh tốc độ xuất ngắn hạn (3–7–10 ngày) với mức nền 30 ngày để phát hiện sớm hiện tượng tiêu thụ tăng đột biến.
   * Tự động tính **Số ngày tồn kho còn lại (Runway)** và phát cảnh báo ngay khi `Runway <= Lead Time NCC + Ngưỡng đệm an toàn` (hỗ trợ cấu hình `Lead Time` riêng cho từng NCC, khoảng đệm 8 ngày của Nhà thuốc, và thời gian duyệt Sở Y tế đối với thuốc gây nghiện/hướng thần).
   * Đề xuất **điều chuyển nội bộ trước khi mua mới** (cảnh báo đẩy hàng từ B1 lên T6, hoặc cảnh báo khi 1 mã con cạn hàng trong khi các mã còn lại của cùng loại thuốc vẫn dồi dào để xử lý cân đối theo quy chế).
3. **Dự báo nhu cầu bằng AI & Tự động sinh phiếu dự trù (Smart Requisition Automation):**
   * Dự báo nhu cầu xuất kho kỳ tới dựa trên dữ liệu lịch sử, xu hướng cùng kỳ năm trước, mùa bệnh và công suất điều trị nội trú.
   * Tự động tạo sẵn bảng nháp **Dự trù thường quy** và **Dự trù đột xuất** (đã tự động quy đổi làm tròn theo bội số quy cách đóng gói hộp/lọ) kèm luồng phê duyệt trực tuyến từ Kho/Nhà thuốc lên Quản lý và Phòng Quản lý Dược.
4. **Tối ưu hóa giỏ đặt hàng theo Ngân sách & Ngưỡng xuất hóa đơn NCC (Budget & MOQ Optimizer):**
   * Tự động gom đơn theo từng nhà cung cấp, kiểm tra điều kiện số lượng/giá trị tối thiểu để NCC xuất hóa đơn và gợi ý điều chỉnh cơ cấu đặt hàng tối ưu trong hạn mức Budget được giao.
5. **Cảnh báo Thuốc chậm luân chuyển, Cận date & Hỗ trợ kiểm soát hạn dùng đầu vào:**
   * Tự động lọc danh sách các lô hàng chậm luân chuyển hoặc chạm mốc cận hạn dùng (VD: còn 6 tháng) để kịp thời điều phối sử dụng hoặc làm việc với NCC đổi/trả.
   * Công cụ tính nhanh ngay tại khâu tiếp nhận hàng mới: ước tính ngày dùng hết lô hàng dựa trên tốc độ tiêu thụ dự báo để khuyến nghị **chấp nhận hay từ chối nhận** các lô hàng cận date từ NCC (đảm bảo tiêu thụ hết trước mốc an toàn 3 tháng cuối hạn dùng).

