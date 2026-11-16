## NỘI DUNG SLIDES

### SLIDE 1: TRANG TIÊU ĐỀ (TITLE)

**Tiêu đề chính:**  
**DỰ ÁN HỆ THỐNG CDSS TỔNG HỢP VÀ PHÂN TÍCH BỐI CẢNH BỆNH ÁN HỖ TRỢ DUYỆT Y LỆNH LÂM SÀNG**

**Phụ đề (đồng bộ theo biên bản Sign-off):**  
Hệ thống AI Agent hỗ trợ phân tích hồ sơ bệnh án và quyết định duyệt y lệnh

* **Chương trình:** Vinmec AI Exploration Sprint (VinUni × Vinmec)
* **Đơn vị triển khai:** Khoa Dược (S10) – Bệnh viện Đa khoa Quốc tế Vinmec Times City
* **Nhóm thực hiện:** Team AI Thực chiến tại Khoa Dược (Đỗ Trương Thành Ân & Vũ Gia Khải)
* **Hướng dẫn chuyên môn:** ThS.DS Nguyễn Lê Trang – Trưởng khoa Dược | **Lead cơ sở:** Nguyễn Xuân Tài

---

### SLIDE 2: CÂU CHUYỆN THỰC TẾ – NHỮNG CHIA SẺ ĐÁNG LƯU Ý TỪ PHÒNG DƯỢC LÂM SÀNG

*(Tổng hợp nhận định & lời kể ghi nhận trong quá trình khảo sát thực địa 29/10 – 12/11/2026)*

1. **Vừa tra vừa đối chiếu thủ công qua 5–6 nền tảng rời rạc:**  
   > *"Để thẩm định một y lệnh, chúng tôi phải lấy mã người bệnh từ `OH` gõ tay sang `EMR` đọc hồ sơ, rồi mở song song `MIMS`, `UpToDate`, `MicroMedexSolutions`, qua `Calculate`/`MDCalc` hay bảng `Excel` để tính liều — nhiều ca phức tạp `Calculate` còn thiếu dữ liệu đầu vào nên lại phải quay vào `EMR` đào sâu thêm."*
2. **Quá nhiều thông tin cần mở đọc, quá ít thời gian để duyệt hết:**  
   > *"Lý tưởng là phải đọc hết mọi *visit* và các phiếu khám liên quan của người bệnh, nhưng khối lượng đơn quá lớn (30–80+ y lệnh nội trú/ngày và hơn 2.000 đơn ngoại trú/tháng). Có những phiếu khám mở ra mới biết không liên quan đến y lệnh cần duyệt — quá nhiều thông tin mà thời gian quá ít nên rất dễ nảy sinh tâm lý ngại đọc kỹ hết, nhiều hôm phải làm thêm ngoài giờ để audit đơn ngoại trú."*
3. **Tự xoay xở bằng Claude/ChatGPT nhưng đứt gãy dữ liệu bệnh án và thiếu đồng bộ:**  
   > *"Một số dược sĩ tự copy dữ liệu thuốc (đã ẩn danh thông tin người bệnh) vào Claude hoặc ChatGPT để xuất bảng nhận định 3 cột cho nhanh. Nhưng vì không được đưa dữ liệu bệnh án thật lên công cụ ngoài nên AI không đối chiếu được với kết quả xét nghiệm hay diễn tiến trên `EMR`, thao tác hoàn toàn thủ công và cũng không phải dược sĩ nào cũng quen dùng để ra kết quả đồng nhất."*
4. **Áp lực duyệt đơn chiếm mất quỹ thời gian thăm khám nội trú cho người bệnh:**  
   > *"Mỗi DSLS phụ trách một khoa cần trực tiếp lên thăm khám, hỏi thăm người bệnh nội trú để xác định khả năng tiếp nhận, tuân thủ và đáp ứng thuốc (như kiểm tra người bệnh có dùng đúng cách, có gặp tác dụng phụ như cồn ruột, chậm nhịp tim hay kém đáp ứng để kịp phối hợp bác sĩ chỉnh phác đồ). Nhưng thời gian đọc gom và duyệt y lệnh trên máy đã chiếm gần hết quỹ thời gian ban ngày."*

---

### SLIDE 3: SỐ LIỆU CHỨNG MINH TỪ KHẢO SÁT & BẤM GIỜ THỰC TẾ

*(Dữ liệu đo đạc ngày 10/11 và phiên bấm giờ trực tiếp ngày 12/11/2026 tại Phòng Dược Lâm Sàng)*

* **Thời gian duyệt trung bình trong các y lệnh đã ghi lại:**
  * **Phiên bấm giờ trực tiếp (12/11 – `10 ca điển hình` trong `14 lượt` quan sát ở Nội trú Tim mạch, Thần kinh, Ung bướu & Ngoại trú):** Thời gian duyệt trung bình **`5.0 phút/ca`** *(lâu nhất **`20 phút`**, tỷ lệ ca đạt mức tiêu chuẩn **`60.0%`** [`6/10 ca`])*.
  * **Đối chiếu dữ liệu khảo sát (10/11):** Nội trú (`11 lượt`) có ca nhanh `5–10 phút`, ca trung bình `~20 phút`, ca phức tạp **`40–60 phút`** *(theo lời kể; phân rã ca trung bình là **`9 phút/lượt`**, dao động `2.5–48.5 phút`)*; Ngoại trú (`7 lượt`) trung bình **`10 phút/đơn`** *(dao động `3–20 phút`, và `~5 phút` theo lời kể)*.
* **Lưu ý quan trọng về phạm vi đo đếm:**
  * Con số bấm giờ `5.0 phút/ca` chủ yếu phản ánh các ca **"duyệt xong là xong"** ngay trong một lần xử lý.
  * Với các trường hợp **"làm một lần chưa xong"** — phải tạm giữ (`Hold`), chờ xét nghiệm bổ sung, hoặc gọi điện xác minh thêm với bác sĩ/điều dưỡng/kho *(như bước liên lạc dao động `0–30 phút` theo lời kể ở Mục 3.1 hoặc ca phức tạp `40–60 phút`)* — **không thể bấm giờ liên tục bằng tay được**, nên thời gian xử lý thực tế còn kéo dài hơn nhiều.
* **Bước mất nhiều thời gian trung bình nhất:**
  * **Trong dữ liệu bấm giờ (12/11):** **`Thời gian thao tác khác`** có mức trung bình cao nhất khi phát sinh (**`7.2 phút`**) — gồm gọi điện kiểm tra tồn kho T6/Nhà thuốc, xác nhận với nhân sự lâm sàng, hoặc dùng AI ngoài soạn phiếu tư vấn rồi chèn logo và sửa định dạng thủ công *(chiếm `7–12 phút` ở các ca Ngoại trú `14–20 phút`)*.
  * **Trong phân rã ca nội trú trung bình theo lời kể (Mục 3.1):** **`Đọc gom bối cảnh trên EMR`** là bước tốn thời gian trung bình lớn nhất (**`5 phút`** / `9 phút`, chiếm hơn 55% tổng thời gian).
* **Bước "tưởng ít mà nhiều" (Trung bình nhỏ, nhưng khi lớn thì rất lớn – Bước Đọc bệnh án):**
  * Trong phiên bấm giờ `12/11`, bước **Đọc bệnh án** có trung bình chung **`2.7 phút/ca`**; ở phần lớn các ca thường quy chỉ mất **`1–2 phút`** *(nhìn trung bình tưởng ít)*.
  * **Nhưng ở nhóm ca có bệnh sử dài / ngoại trú phức tạp (đuôi trên – Q3 lớn):** thời gian đọc bệnh án **tăng vọt gấp 3–3.5 lần lên `6–7 phút`** *(Ca 12 Nội trú Tim mạch mất `6 phút` chỉ để dò tìm thông tin cũ; Ca 7 & 8 Ngoại trú mất `7 phút/ca`; Ca 10 Thần kinh mất thời gian tìm mốc hành chính `"Vào viện lúc nào?"`)* — khớp với biên độ **`2–15 phút`** được ghi nhận qua lời kể ở Mục 3.1.

---

### SLIDE 4: ĐỀ XUẤT GIẢI PHÁP – HỆ THỐNG AI AGENT / CDSS HỖ TRỢ DUYỆT Y LỆNH

* **Tóm tắt giải pháp:**
  * Ngay khi có y lệnh mới gửi về trên `OH`, **AI tự động kích hoạt để gom dữ liệu và tóm tắt bối cảnh bệnh án (`OH` + `EMR` theo `PID`)** trên một màn hình thống nhất.
  * Tự động tính các chỉ số lâm sàng (`CrCl`/`eGFR`, `BSA`, công thức dinh dưỡng) và **xuất sẵn Bảng nhận định theo Ma trận 7 yếu tố chuyên môn** *(dị ứng, trùng lặp hoạt chất, chỉ định/chống chỉ định, tương tác đa thuốc, độc tính sinh lý, liều theo gan/thận & xét nghiệm `AST`/`ALT`/`Creatinine`, kiểm tra lịch dùng sáng–tối)* kèm **chuỗi suy luận logic tường minh và trích dẫn nguồn tài liệu**.
  * Vận hành **phi xâm lấn (Non-intrusive)**, bảo mật **PII nội bộ** *(giai đoạn thử nghiệm Tuần 3 dùng 100% dữ liệu giả lập `Mock/Synthetic Data`)*.
* **Thay đổi trong quy trình:**
  * **Không làm thay đổi quy trình duyệt hiện hành (`Zero workflow disruption`).**
  * Tuân thủ nguyên tắc ***Human-in-the-loop***: Dược sĩ lâm sàng vẫn trực tiếp kiểm chứng trên bảng tóm tắt/suy luận và **tự vào xác nhận kết quả duyệt cuối cùng** (`Approved` / `Hold` / `Cancelled`).
  * Hệ thống **tuyệt đối không tự động duyệt đơn và không tự ý chỉnh sửa liều lượng** trên đơn thuốc của bác sĩ.
* **Mục tiêu hướng tới:**
  * **Giảm thời gian duyệt từng ca, tăng hiệu suất xử lý** (tăng số y lệnh được thẩm định mỗi ngày và giải tỏa áp lực làm thêm ngoài giờ để audit >2.000 đơn ngoại trú chuẩn 24h).
  * **Giữ nguyên chuẩn chất lượng & an toàn dùng thuốc:** Không bỏ sót thông tin trọng yếu, ngăn ngừa biến cố bất lợi của thuốc (`ADR`).
  * **Giải phóng quỹ thời gian cho DSLS thăm khám bệnh nhân nội trú:** Giúp DSLS có thêm điều kiện lên khoa đánh giá khả năng tiếp nhận, tuân thủ và đáp ứng thuốc trên **nhiều người bệnh hơn**, mở rộng phạm vi người bệnh được hưởng dịch vụ chăm sóc dược lâm sàng.

---
