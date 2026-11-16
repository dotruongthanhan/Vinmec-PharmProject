# BÁO CÁO TUẦN 1 & ĐỀ XUẤT ĐỊNH HƯỚNG KỸ THUẬT (GỬI MENTOR CÔNG NGHỆ)

**Chương trình:** Vinmec AI Exploration Sprint 6 Tuần (VinUni x Vinmec)  
**Đơn vị khảo sát:** Khoa Dược (S10) – Bệnh viện Đa khoa Quốc tế Vinmec Times City  
**Thực hiện:** Đỗ Trương Thành Ân & Vũ Gia Khải  
**Thời gian khảo sát Tuần 1:** 29/10/2026 – 05/11/2026  

---

## 1. Tóm tắt hoạt động khảo sát Tuần 1 (Summary of Week 1 Investigation)

Trong khuôn khổ chương trình **Vinmec AI Exploration Sprint**, nhóm được phân công khảo sát chuyên sâu tại **Khoa Dược (S10) – Bệnh viện Vinmec Times City**. Do đặc thù của Khoa Dược là trung tâm hậu cần – lâm sàng kết nối toàn viện, trong tuần đầu tiên (29/10 – 05/11), nhóm đã triển khai khảo sát diện rộng lẫn chiều sâu tại tất cả **5 bộ phận trực thuộc Khoa Dược** cùng **1 khoa lâm sàng**:

- **Hoạt động hiện trường (Shadowing & The Mom Test):**
  - Thực hiện **07 buổi quan sát trực tiếp (shadowing)** tại bàn làm việc của nhân viên y tế và **09 cuộc phỏng vấn sâu** theo nguyên tắc *The Mom Test* với đầy đủ các vai trò: *Dược sĩ lâm sàng (nội trú & ngoại trú), Dược sĩ Kho nội trú (Kho trung tâm B1 & Kho vệ tinh T6), Dược sĩ Nghiệp vụ Dược, Chuyên viên Quản lý Dược, Dược sĩ Nhà thuốc bệnh viện (vận hành 24/7)*, cùng *Bác sĩ điều trị & Điều dưỡng tại Khoa Miễn dịch – Dị ứng*.
- **Kết quả chuẩn hóa tài liệu:**
  - Xây dựng **08 lưu đồ quy trình nghiệp vụ (Clinical & Operational Process Maps)** mô tả luồng dữ liệu qua các hệ thống hiện hành (`OH`, `EMR`, `SAP`, `VIS Vinmec`, `Info Vinmec`, `Excel`).
  - Lập **Ma trận 16 Điểm nghẽn (Bottleneck Matrix `BN01`–`BN16`)** và **Bảng Từ điển Dữ liệu (Data Dictionary 8 bảng `B1`–`B8`)** kèm phương án ẩn danh hóa dữ liệu bệnh nhân (`PII`).
- **Rà soát chéo với dự án phần mềm mới SMH (do VSF phát triển):**
  - Nhóm đã tiếp cận tài liệu tiến độ của phần mềm **SMH** (mảng Dược lâm sàng) để đối chiếu và tránh đề xuất trùng lặp. Cụ thể, các vấn đề về phân mảnh đa mã hàng (`AA` dịch vụ / `AY` bảo hiểm / `Daycare`) dẫn đến hiện tượng *"âm ảo"* và một số tính năng duyệt đơn lâm sàng đã được đưa vào lộ trình của SMH. Do đó, nhóm đã lọc bỏ phần xử lý đa mã `AA`/`AY` và tái định hình danh sách các bài toán cần giải quyết bên dưới.

---

## 2. Các vấn đề trọng tâm phát hiện tại Khoa Dược (Problems Identified)

Sau khi loại trừ các vấn đề sẽ được giải quyết bởi kiến trúc cơ sở dữ liệu mới của **SMH**, nhóm xác định **05 nhóm vấn đề cốt lõi** đang gây tiêu tốn nhiều nguồn lực thủ công và tiềm ẩn rủi ro vận hành tại Khoa Dược:

### Vấn đề 1: Dự báo tồn kho bị động & Nguy cơ đứt gãy cung ứng do "Hàng xuất nhanh đột xuất" (`BN08`, `BN15`)
- **Hiện trạng:** Kho nội trú (`B1`, `T6`) và Nhà thuốc đang lập dự trù thường quy/đột xuất bằng cách xuất file từ `OH` ra `Excel` (mỗi 3–4 ngày tại kho nội trú, ngày 01 & 15 tại Nhà thuốc) và áp dụng công thức tĩnh dựa trên quá khứ:
  - Kho B1: $\text{Dự trù} = [\text{Xuất tháng trước} \times (1 + \text{Lead Time})] - \text{Tồn} - \text{Chờ nhập}$
  - Nhà thuốc: $\text{Dự trù} = (\text{Sales 30 ngày} \times 1{,}3) - \text{Tồn} - \text{Chờ nhập}$
- **Điểm nghẽn:**
  1. **Không bắt kịp biến động tiêu thụ đột biến (Velocity Spikes):** Khi lâm sàng phát sinh dịch bệnh hoặc chùm ca bệnh nặng khiến tốc độ xuất kho tăng vọt, công thức trung bình tháng trước bị trễ nhịp. Trong khi `Lead Time` đặt – giao hàng mất ~0.5 tháng (hoặc lâu hơn với cơ sở xa như Phú Quốc, Cần Thơ và thuốc kiểm soát đặc biệt), nếu dược sĩ kho không phát hiện thủ công bằng mắt sẽ dẫn đến đứt gãy thuốc kê đơn.
  2. **Bài toán tối ưu đa ràng buộc thủ công:** Rất khó tính nhẩm để vừa làm tròn theo quy cách đóng gói (hộp/lọ), vừa đạt ngưỡng giá trị tối thiểu để nhà cung cấp xuất hóa đơn (`MOQ`), vừa nằm trong trần ngân sách (`Budget`) được giao.
  3. **Kiểm soát thuốc cận hạn (`cận date`) và chậm luân chuyển:** Hàng ít giao dịch dễ bị bỏ sót dẫn tới cận hạn; ở khâu nhận hàng mới từ nhà cung cấp, kho thiếu công cụ ước tính nhanh tốc độ tiêu thụ dự kiến để quyết định nhận hay từ chối các lô hàng có hạn dùng ngắn.

### Vấn đề 2: Quá tải trích xuất và chuẩn hóa Báo cáo Tiêu thụ Kháng sinh chuẩn WHO (`ATC/DDD`)
- **Hiện trạng:** Định kỳ 6 tháng/lần (2 lần/năm), Dược sĩ lâm sàng phải lập báo cáo tiêu thụ kháng sinh toàn viện theo chỉ số chuẩn quốc tế `DDD / 1.000 ngày bệnh nhân` (*Defined Daily Dose per 1,000 patient-days*) trình Hội đồng Thuốc & Điều trị.
- **Điểm nghẽn:**
  - Phải trích xuất thủ công toàn bộ y lệnh kháng sinh từ `OH` và tổng số ngày giường điều trị nội trú (`Patient-days`) từ `EMR`.
  - Dữ liệu hàm lượng, liều dùng và đường dùng trên y lệnh không đồng nhất đơn vị (`mg`, `g`, `UI`, thuốc phối hợp nhiều hoạt chất), buộc dược sĩ phải quy đổi tay về đơn vị chuẩn `gam/ngày` và tra cứu thủ công bảng định mức `WHO ATC/DDD` trên `Excel` rất tốn thời gian và dễ sai số.

### Vấn đề 3: Phân mảnh dữ liệu nghiêm trọng khi lập Báo cáo Bộ 17 Chỉ số Dược Lâm Sàng hàng tháng (`BN06`)
- **Hiện trạng:** Cuối mỗi tháng, toàn bộ Dược sĩ lâm sàng các chuyên khoa và 01 dược sĩ đầu mối phải mất trung bình **~2 ngày làm việc** để tổng hợp Bộ 17 chỉ số hoạt động Dược lâm sàng.
- **Điểm nghẽn:**
  - **Dữ liệu nằm rải rác trên 5–6 nguồn không liên kết:** File xuất thuốc kê đơn từ `OH`, dữ liệu sự cố/phản ứng có hại (`ADR`) từ `Info Vinmec`, dữ liệu đào tạo, các bảng tính `Excel` rời rạc với format khác nhau gửi qua email từ các khoa phòng.
  - **Thiếu quyền truy cập dữ liệu liên khoa:** Một số chỉ số phụ thuộc vào dữ liệu của khoa khác mà Khoa Dược không tự trích xuất trực tiếp được (ví dụ: danh sách và số lượng ca phẫu thuật trong tháng để tính tỷ lệ sử dụng kháng sinh dự phòng hợp lý).
  - **Đối chiếu thủ công văn bản tự do trên `EMR`:** Để xác minh chỉ số *"Tỷ lệ kháng sinh hạn chế được hội chẩn đúng quy trình"*, sau khi lọc danh sách trên `OH`, dược sĩ phải copy từng mã bệnh nhân (`PID`/`HN`) sang `EMR`, mở đọc từng hồ sơ bệnh án để kiểm tra xem có *Biên bản hội chẩn* hợp lệ hay không.

### Vấn đề 4: Nhập liệu thủ công Hóa đơn Nhà cung cấp lên hệ thống `SAP` / `HIS` (`BN12`)
- **Hiện trạng:** Bộ phận Nghiệp vụ Dược tiếp nhận khối lượng lớn hóa đơn, chứng từ giao hàng bản giấy/PDF từ các nhà cung cấp mỗi ngày và phải gõ tay từng trường thông tin (mã thuốc, số lô, hạn sử dụng, đơn giá, số lượng, thuế) lên hệ thống `SAP` và `HIS`/`OH`.
- **Điểm nghẽn:** Vào các khung giờ cao điểm giao hàng hoặc cuối kỳ thanh toán, việc nhập liệu thủ công gây quá tải, dễ nhầm lẫn số lô/hạn dùng và tạo ra độ trễ dữ liệu (*"hàng treo"* — hàng vật lý đã nằm tại cửa kho B1 và khoa lâm sàng cần dùng gấp nhưng chứng từ chưa kịp lên hệ thống, dẫn đến xuất âm trên phần mềm).

### Vấn đề 5: Điểm nghẽn vận hành tại Nhà thuốc Bệnh viện 24/7 (`BN13`, `BN05`, `BN14`)
- **Kiểm kê kho bị "đóng băng" tĩnh trong môi trường bán hàng 24/7 (`BN13`):** Nhà thuốc phục vụ ~750 lượt khách/ngày và mở cửa 24/7. App kiểm kê thí điểm hiện tại chốt cứng ảnh chụp tồn kho (`Snapshot`) tại thời điểm bắt đầu kiểm kê; trong lúc nhân viên đi quét QR đếm thuốc trên kệ thì quầy vẫn bán thuốc liên tục, làm số đếm thực tế bị lệch ảo so với số chốt ban đầu. Khi phát hiện chênh lệch, bảng kiểm kê bị khóa không cho sửa trực tiếp mà phải mất 1–2 ngày truy tìm từng giao dịch.
- **Thẩm định đơn thuốc ngoại trú thiếu cơ chế phân luồng ưu tiên tự động (`BN05`):** Dược sĩ lâm sàng ngoại trú duyệt đơn từ xa trên phần mềm (~5 phút/đơn), không ngồi tại quầy. Hệ thống chưa tự động đẩy ưu tiên các đơn của bệnh nhân đã hoàn tất thủ tục BHYT/thu ngân và đang đứng chờ trực tiếp tại quầy Nhà thuốc, khiến nhân viên quầy phải gọi điện thúc giục thủ công và gây trễ 30–60 phút vào giờ cao điểm (`10h–12h`, `15h–17h30`).
- **Đếm thuốc lẻ thủ công dễ sai số (`BN14`):** Mỗi ngày Nhà thuốc phát sinh ~100 lượt chia thuốc lẻ từ lọ lớn vào túi zip. Việc đếm tay từng viên với các đơn `>20 viên` trong giờ cao điểm vừa tốn thời gian, vừa dễ nhầm số lượng (gây rủi ro cho người bệnh và làm lệch tồn kho).

---

## 3. Ý tưởng & Giải pháp AI / Tự động hóa đề xuất (Proposed Solutions)

Tương ứng với 5 vấn đề trên, nhóm đề xuất **05 dự án giải pháp công nghệ/AI** (sẽ được kiểm chứng số liệu định lượng và xác nhận ranh giới với đội phát triển **SMH** trong Tuần 2):

1. **Hệ thống Dự báo Tồn kho Động & Cảnh báo Hàng xuất nhanh (Dynamic Inventory Forecasting & Spike Alerting):**
   - **Dynamic Runway & Velocity Spike Alerting:** Tự động đo gia tốc tiêu thụ ngắn hạn (3–7–10 ngày) so với nền 30 ngày; tính toán *Số ngày tồn kho còn lại (Runway)* theo thời gian thực và phát cảnh báo sớm ngay khi $\text{Runway} \le \text{Lead Time NCC} + \text{Safety Buffer}$.
   - **Time-Series AI Forecasting:** Dự báo nhu cầu xuất kho kỳ tới dựa trên lịch sử tiêu thụ đa năm, yếu tố mùa vụ, dịch bệnh và công suất giường bệnh nội trú.
   - **Budget & MOQ Optimizer:** Thuật toán tối ưu hóa giỏ đặt hàng (Linear/Integer Programming) tự động làm tròn theo bội số quy cách đóng gói, thỏa mãn ngưỡng xuất hóa đơn tối thiểu (`MOQ`) của từng nhà cung cấp và không vượt trần ngân sách (`Budget`).
   - **Near-Expiry & Slow-Moving Advisor:** Cảnh báo danh mục hàng chậm luân chuyển/cận hạn và tích hợp công cụ tính nhanh tại khâu nhận hàng để khuyến nghị *Chấp nhận / Từ chối* lô hàng cận date dựa trên tốc độ tiêu thụ dự báo.

2. **Công cụ Tự động hóa & NLP lập Báo cáo Kháng sinh chuẩn WHO (`ATC/DDD`):**
   - Pipeline tự động kết nối dữ liệu y lệnh kháng sinh (`OH`/SMH) và ngày giường nội trú (`EMR`).
   - **Ứng dụng NLP / LLM Entity Resolution:** Tự động bóc tách chuỗi văn bản liều dùng phức tạp (đa đơn vị `mg`, `g`, `UI`, thuốc phối hợp nhiều hoạt chất), ánh xạ tự động tên thương mại + hoạt chất + đường dùng sang bảng mã chuẩn `WHO ATC/DDD`, tính toán chỉ số `DDD / 1.000 ngày bệnh nhân` và sinh nhận xét xu hướng bất thường cho Hội đồng Thuốc & Điều trị.

3. **Hệ thống Tự động Tổng hợp Báo cáo 17 Chỉ số Dược Lâm Sàng (kèm AI đọc bệnh án `EMR`):**
   - **Schema-Flexible Data Ingestion:** Tự động chuẩn hóa và gộp dữ liệu từ `OH`, `Info Vinmec`, các file `Excel` đa định dạng của từng khoa lâm sàng và dữ liệu ca phẫu thuật liên khoa.
   - **Clinical NLP / Information Extraction trên `EMR`:** Sử dụng mô hình ngôn ngữ nội bộ (On-premise LLM/NLP) quét tự động hồ sơ bệnh án `EMR` theo danh sách mã bệnh nhân (`PID`) để kiểm tra sự tồn tại và tính hợp lệ của *Biên bản hội chẩn kháng sinh hạn chế* / phiếu tư vấn, thay thế hoàn toàn thao tác mở đọc tay từng bệnh án trong 2 ngày.

4. **Công cụ OCR / Intelligent Document Processing (IDP) Bóc tách Hóa đơn Nhập kho:**
   - Ứng dụng mô hình **Document AI / VietOCR + LayoutLM / VLM nội bộ** để nhận diện và bóc tách tự động bảng chi tiết hóa đơn giao hàng từ nhà cung cấp (tên thuốc, hoạt chất, số lô, hạn dùng, đơn vị tính, số lượng, đơn giá, thành tiền).
   - Tự động đối chiếu chéo (Fuzzy Matching) với đơn đặt hàng/dự trù kho để kiểm tra sai lệch và đẩy dữ liệu nháp (staging) vào `SAP`/`HIS` chỉ với 1 bước phê duyệt của dược sĩ nghiệp vụ.

5. **Bộ Giải pháp Tối ưu Vận hành Nhà thuốc 24/7:**
   - **Real-Time Delta Stocktaking:** Thay cơ chế chốt kho tĩnh bằng đối soát tồn kho động theo đúng dấu thời gian quét mã QR (`Timestamped Live Inventory Comparison`), cho phép chỉnh sửa hậu kiểm có lưu vết (`Audit log`) và dùng thuật toán phát hiện bất thường để gợi ý kiểm kê cuốn chiếu các mặt hàng có tần suất lệch tồn cao.
   - **Smart Outpatient Queue Prioritization:** Thuật toán sắp xếp hàng đợi duyệt đơn ngoại trú theo điểm ưu tiên thời gian thực (bệnh nhân đã quét mã tại quầy Nhà thuốc + đã xong thủ tục BHYT + mức độ nguy cơ lâm sàng + thời gian chờ), kèm màn hình hiển thị trạng thái đơn minh bạch cho người bệnh.
   - **Computer Vision Pill-Counting Assistant:** Ứng dụng nhận diện ảnh (Object Detection trên thiết bị di động/máy tính bảng tại quầy) đếm nhanh số viên thuốc lẻ trên khay chỉ qua 1 ảnh chụp (kiểm chứng chéo cho các đơn `>20 viên`) và lưu ảnh làm minh chứng đối soát tồn kho, kết hợp tách luồng in nhãn túi zip độc lập.

---

## 4. Nhu cầu hỗ trợ từ Mentor Công nghệ (Support Needed)

Để chuẩn bị cho giai đoạn đánh giá khả thi kỹ thuật (Feasibility Study) và xây dựng PoC trong 5 tuần tới, nhóm rất mong nhận được sự định hướng và hỗ trợ của Mentor ở 4 khía cạnh:

1. **Đánh giá độ phức tạp kỹ thuật & Chốt phạm vi PoC 5 tuần:**
   - Tư vấn giúp nhóm lựa chọn và giới hạn phạm vi (scope) cho **01–02 bài toán khả thi nhất** trong 5 đề xuất trên để đảm bảo xây dựng được sản phẩm PoC chạy thực tế với dữ liệu thật của viện trong vòng 5 tuần.
2. **Định hướng kiến trúc AI On-Premise & Bảo mật dữ liệu y tế (`PII`):**
   - Theo quy định nghiêm ngặt của Vinmec, dữ liệu bệnh án/y lệnh chứa thông tin định danh (`HN`, `Patient_name`, ghi chú lâm sàng) tuyệt đối không được gửi lên các Public Cloud API bên ngoài. Nhóm mong Mentor tư vấn các giải pháp mô hình nhẹ chạy cục bộ (**Local/On-premise LLM, OCR, Time-series, hoặc Computer Vision**) phù hợp với hạ tầng phần cứng sẵn có.
3. **Kinh nghiệm thiết kế Pipeline xử lý dữ liệu không cấu trúc & đa nguồn:**
   - Tư vấn phương pháp thiết kế pipeline chuẩn hóa các bảng tính `Excel` có cấu trúc cột biến động giữa các khoa phòng và kỹ thuật bóc tách thông tin có cấu trúc từ văn bản bệnh án tiếng Việt (`EMR`) / hóa đơn dược phẩm (`Invoice OCR`).
4. **Hỗ trợ định hướng câu hỏi kỹ thuật khi làm việc với IT Bệnh viện & Đội phát triển SMH (VSF):**
   - Góp ý cho bộ câu hỏi khảo sát kỹ thuật (về cấu trúc Database, API/Export permissions của `OH`/`EMR`/`SAP`, và lộ trình kỹ thuật của phần mềm `SMH`) trước khi nhóm làm việc trực tiếp với phòng IT và đội dự án VSF vào tuần tới.
