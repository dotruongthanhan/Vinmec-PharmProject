# ĐỀ XUẤT & XÁC NHẬN PHẠM VI THỬ NGHIỆM (PROJECT SIGN-OFF)
## HỆ THỐNG AI AGENT HỖ TRỢ PHÂN TÍCH HỒ SƠ BỆNH ÁN VÀ QUYẾT ĐỊNH DUYỆT Y LỆNH

**Chương trình:** Vinmec AI Exploration Sprint (VinUni × Vinmec)  
**Đơn vị triển khai:** Khoa Dược (S10) – Bệnh viện Đa khoa Quốc tế Vinmec Times City  
**Nhóm thực hiện:** Team AI Thực chiến tại Khoa Dược (Đỗ Trương Thành Ân & Vũ Gia Khải)  
**Người hướng dẫn tại khoa:** ThS.DS Nguyễn Lê Trang – Trưởng khoa Dược  
**Lead cơ sở phụ trách:** Nguyễn Xuân Tài  

---

## 1. XÁC NHẬN ĐIỂM NGHẼN VẬN HÀNH (PAIN POINTS)

Qua quá trình khảo sát thực địa và quan sát trực tiếp quy trình làm việc tại Phòng Dược Lâm Sàng (29/10 – 12/11/2026), nhóm ghi nhận điểm nghẽn cốt lõi hiện tại:

* **Dược sĩ lâm sàng (DSLS) mất nhiều thời gian trong việc tra cứu các nguồn thông tin để xác nhận tính hợp lý của đơn thuốc hiện tại trên tình trạng của người bệnh**, cụ thể phải đối chiếu thủ công qua **5–6 phần mềm / công cụ rời rạc** (`OH`, `EMR`, `MIMS`, `UpToDate`, `MicroMedexSolutions`, `Calculate`/`MDCalc`, `Excel`) cho đầy đủ các yếu tố chuyên môn:
  1. **Hồ sơ bệnh án (`EMR`):** Lật tìm chẩn đoán, diễn tiến điều trị, mốc thời gian nhập viện, thông tin bệnh sử cũ, kết quả xét nghiệm chức năng gan/thận (`AST`, `ALT`, `Creatinine`), kết quả cấy vi sinh và tiền sử dị ứng (hiện chưa liên kết đồng bộ giữa `OH` và `EMR`).
  2. **Phác đồ điều trị theo chẩn đoán:** Đối chiếu mục đích kê thuốc với phác đồ điều trị chuẩn của từng chuyên khoa khi phần mềm `OH` chưa thể hiện trực tiếp lý do kê đơn.
  3. **Chỉ định thuốc & Chống chỉ định thuốc:** Đánh giá tính phù hợp của chỉ định và rà soát chống chỉ định theo tình trạng sinh lý, cơ địa đặc biệt, bệnh lý nền của người bệnh.
  4. **Tương tác thuốc (`Interactions`):** Kiểm tra toàn diện tương tác giữa **danh sách các thuốc người bệnh đang sử dụng** (bao gồm cả các đơn `active` / `pending` qua nhiều lượt khám) và **các thuốc trong y lệnh đang chờ duyệt**.
  5. **Điều kiện liều lượng phù hợp & Các phép tính liên quan:** Rà soát liều dùng tối ưu theo chức năng gan, thận, tuổi, cân nặng (trong khi dữ liệu liều Auto-test trên `OH` đã cũ, và ứng dụng `Calculate` thiếu dữ liệu đầu vào với các ca bệnh phức tạp nên dược sĩ phải tra thêm nguồn ngoài hoặc tính tay trên `Excel`).

---

## 2. XÁC NHẬN VẤN ĐỀ ĐÁNG ĐỂ GIẢI QUYẾT & MỤC TIÊU DỰ ÁN

* **Bài toán trọng tâm:** **Dược sĩ lâm sàng cần giảm tối ưu thời gian duyệt các y lệnh đang chờ nhưng vẫn đảm bảo chất lượng duyệt** (xem xét đầy đủ hết các tài liệu, hồ sơ bệnh án và tình huống lâm sàng liên quan), **để dành quỹ thời gian audit (hậu kiểm) lại các đơn ngoại trú đã được khu vực Nhà thuốc duyệt.**
* **Ý nghĩa vận hành thực tế:**
  * Hiện nay, theo phân quyền chuyên môn, các chuyên khoa thuộc danh sách phức tạp do DSLS duyệt trực tiếp; các trường hợp còn lại do khu vực Nhà thuốc duyệt và DSLS thực hiện hậu kiểm lại sau 24 giờ (cùng 100% y lệnh ngoài giờ hành chính).
  * Do thời gian đọc gom dữ liệu thủ công cho các y lệnh đang chờ quá lớn, **DSLS phải dành thêm thời gian ngoài giờ để audit các đơn ngoại trú**. Việc tự động hóa khâu tổng hợp bối cảnh bệnh án và phân tích hỗ trợ quyết định sẽ trực tiếp giải tỏa áp lực thời gian cho DSLS, giúp bảo đảm chuẩn chất lượng an toàn thuốc cho cả khu vực nội trú lẫn ngoại trú.

---

## 3. BẰNG CHỨNG & SỐ LIỆU ĐO ĐẠC THỰC TẾ TỪ TEAM

Nhu cầu triển khai dự án được xác thực trực tiếp qua các số liệu đo đạc và quan sát tại Phòng Dược Lâm Sàng trong 2 tuần khảo sát:

### 3.1. Số liệu thống kê từ Báo cáo Tuần 2 (`[S10]_[VMTC]_[Duoc]_[BAO_CAO_TUAN_2]`)

| Hạng mục theo dõi | Số lượt đã đo / Thời điểm | Thời gian thực tế | Khối lượng công việc |
| :--- | :--- | :--- | :--- |
| **Thẩm định y lệnh nội trú** (mỗi y lệnh) | `11 lượt` (10/11/2026) | Ca nhanh: `5–10 phút`<br/>Ca trung bình: `~20 phút`<br/>Ca phức tạp: `40–60 phút` *(theo lời kể)* | Tùy ngày: ít khoảng `30 y lệnh/ngày`, trung bình `60 y lệnh/ngày`, nhiều `80 y lệnh/ngày trở lên` |
| **Thẩm định đơn thuốc ngoại trú** (mỗi đơn) | `7 lượt` (10/11/2026) | Ngắn nhất: `3 phút` \| Dài nhất: `20 phút`<br/>Trung bình: `10 phút` *(và `~5 phút` theo lời kể)* | **Hơn 2.000 đơn thuốc ngoại trú/tháng** *(theo thống kê ước lượng của DSLS)* |

* **Phân rã thời gian từng bước cho 1 lượt thẩm định y lệnh nội trú** *(theo lời kể; mức trung bình lấy theo ca trung bình)*:
  1. *Bước 1 – Lấy y lệnh trên `OH`, lấy mã người bệnh và nhập tay sang `EMR`:* Trung bình `0.5 phút` (`0.5–0.5 phút`).
  2. *Bước 2 – Đọc gom bối cảnh trên `EMR` (chẩn đoán, dị ứng, xét nghiệm `AST`, `ALT`, `Creatinine`, vi sinh, diễn tiến):* Trung bình `5 phút` (`2–15 phút`).
  3. *Bước 3 – Tra cứu và tính liều ngoài hệ thống (`MIMS`, `UpToDate`, `Calculate`/`MDCalc`, `Excel`) để kiểm tra đầy đủ 7 yếu tố chuyên môn:* Trung bình `1 phút` (`0–3 phút`), gồm:
     - *(1) Nguy cơ dị ứng, quá mẫn thuốc;*
     - *(2) Trùng lặp thuốc (trùng hoạt chất, trùng nhóm điều trị);*
     - *(3) Tính phù hợp chỉ định (chỉ định/chống chỉ định, liều lượng, tần suất, cách dùng, đường dùng & quy định viện);*
     - *(4) Tương tác thuốc – thuốc, thuốc – thức ăn;*
     - *(5) Nguy cơ độc tính & chống chỉ định theo sinh lý;*
     - *(6) Đối chiếu chẩn đoán, cơ địa đặc biệt (mang thai, cho con bú, suy gan, suy thận) & tác động xét nghiệm (`AST`, `ALT`, `Creatinine`...);*
     - *(7) Các yếu tố chống kê đơn / bất hợp lý khác.*
  4. *Bước 4 – Liên lạc, lấy thông tin từ các bộ phận liên quan để bổ sung tình trạng bệnh nhân:* Trung bình `2.5 phút` (`0–30 phút`).
  * **Tổng thời gian 1 lượt:** Trung bình **`9 phút`** (dao động từ **`2.5 phút`** đến **`48.5 phút`**).
* **Bằng chứng hành vi thực tế:** DSLS hiện phải tự xoay xở bằng cách tham khảo tương tác thuốc qua **Claude / ChatGPT** (không đưa thông tin định danh người bệnh) để nhận bảng nhận định 3 cột; đồng thời Điều dưỡng nội trú (khảo sát 02/11) cũng phải tra cứu chéo trên 4 nguồn rời rạc trước khi tiêm/truyền.

### 3.2. Dữ liệu bấm giờ bổ trợ ngày 12/11 (Phiên theo dõi chi tiết tại Phòng Dược Lâm Sàng)

* **Tổng hợp trên 10 ca duyệt điển hình** *(trong tổng số `14 lượt` quan sát qua các khối Nội trú Tim mạch, Nội trú Thần kinh, Nội trú Ung bướu và Ngoại trú)*:
  * Thời gian duyệt trung bình: **`5.0 phút/ca`** (Lâu nhất: **`20 phút`** – 1 ca Ngoại trú phức tạp; Tỷ lệ ca đạt mức tiêu chuẩn: **`60.0%`** [`6/10 ca`]; Tổng số công thức tra cứu: **`2 công thức`**).
  * **Phân rã trung bình theo công đoạn:** Đọc bệnh án **`2.7 phút`** *(ghi nhận ca Tim mạch mất `6 phút` để tìm thông tin cũ, ca Thần kinh mất thời gian dò tìm mốc `"Vào viện lúc nào?"`)*; Tra cứu thông tin thuốc **`0.5 phút`** *(có ca Nội trú Ung bướu mất `2 phút` tra cứu tương tác qua `MicroMedexSolutions`)*; Tra công thức tính toán **`0.5 phút`**; Thời gian thao tác khác **`7.2 phút`** *(gọi điện xác nhận, kiểm tra tồn kho, soạn phiếu tư vấn bằng AI rồi chỉnh sửa định dạng/logo mất `7–12 phút` ở các ca Ngoại trú)*.
* **Ghi nhận thực tế về quy trình audit đơn ngoại trú:**
  * Để rà soát một đơn ngoại trú, DSLS phải mở đối chiếu chéo toàn bộ đơn `active`/`pending` trên `OH` (vốn chỉ lưu lịch sử thuốc) với các phiếu khám đúng chuyên khoa, đúng ngày, các *visit* trước và các chuyên khoa khác (nhiều phiếu khám có nội dung nhưng không có thông tin liên quan đến y lệnh cần duyệt vẫn buộc phải mở đọc mới biết — tốn nhiều thời gian nhưng không mang lại kết quả, lâu dần dễ tạo thói quen ngại đọc kỹ hết; đồng thời khó nhận biết thuốc đã bị bác sĩ khác cho `discontinue`).
  * Do khối lượng đơn ngoại trú và nội trú ban ngày quá lớn, **họ phải dành thêm thời gian ngoài giờ để audit đơn ngoại trú**.

---

## 4. XÁC NHẬN SẴN SÀNG THỬ NGHIỆM & PHẠM VI TRIỂN KHAI

Từ các điểm nghẽn và bằng chứng đo đạc xác thực nêu trên, **Team AI Thực chiến tại Khoa Dược – Bệnh viện Đa khoa Quốc tế Vinmec Times City xin phép được triển khai dự án:**

> **Tên dự án:** **Hệ thống AI Agent hỗ trợ phân tích hồ sơ bệnh án và quyết định duyệt y lệnh**

### Phạm vi & Nguyên tắc Cam kết khi Triển khai
1. **Nguyên tắc *Human-in-the-loop* (DSLS giữ toàn quyền quyết định & Không tự ý sửa liều):** Hệ thống AI Agent đóng vai trò tự động tổng hợp bối cảnh từ hồ sơ bệnh án & y lệnh, thực hiện các phép tính lâm sàng (`CrCl`/`eGFR`, `BSA`...), sàng lọc chỉ định – chống chỉ định – liều lượng – tương tác đa thuốc (bao gồm kiểm soát tổng lượng hoạt chất đưa vào cơ thể không vượt ngưỡng cho phép) và hiển thị **chuỗi suy luận logic tường minh kèm trích dẫn nguồn tài liệu**. Dược sĩ lâm sàng luôn là người kiểm chứng và ra quyết định duyệt cuối cùng (`Approved` / `Hold` / `Cancelled`). **Ứng dụng tuyệt đối không có quyền tự động chỉnh sửa trực tiếp liều lượng trên đơn thuốc** (tránh gây khó chịu cho bác sĩ như cơ chế tự động giảm liều/gộp đơn sáng – tối để giới hạn ngưỡng hoạt chất); mọi cảnh báo hoặc đề xuất điều chỉnh liều đều phải qua bước Dược sĩ nắm thông tin, duyệt và lưu lại.
2. **Bảo mật thông tin y tế (PII) & An toàn hệ thống:**
   * Giai đoạn Tuần 3 (so sánh phương án và xây dựng bản thử nghiệm đầu tiên) sử dụng **100% dữ liệu giả lập ẩn danh hoàn toàn (`Mock/Synthetic Data`)** kết hợp tri thức y khoa/dược thư công khai — **không sử dụng dữ liệu thật của người bệnh**.
   * Ở các giai đoạn đánh giá sâu hơn (nếu được Khoa và bộ phận liên quan cấp phép), dữ liệu chỉ được xử lý tuân thủ quy chuẩn bảo mật nội bộ của Vinmec, không truyền tải thông tin định danh người bệnh ra môi trường bên ngoài.
3. **Phi xâm lấn (Non-intrusive):** Hệ thống vận hành độc lập ở lớp hỗ trợ tham khảo cho DSLS, **không can thiệp ghi/xóa trực tiếp vào cơ sở dữ liệu lõi** của `OH` hay `EMR`.

---

## 5. PHẦN XÁC NHẬN TRIỂN KHAI

Kính trình **Lãnh đạo Khoa Dược / Mentor chuyên môn** và **Đầu mối Phòng Dược Lâm Sàng** xem xét các nội dung trên. Nếu Quý Anh/Chị đồng thuận với mô tả điểm nghẽn, mục tiêu bài toán và phạm vi triển khai thử nghiệm dự án **Hệ thống AI Agent hỗ trợ phân tích hồ sơ bệnh án và quyết định duyệt y lệnh**, kính nhờ Quý Anh/Chị phản hồi **"Xác nhận"** qua tin nhắn hoặc email để Team AI Thực chiến làm căn cứ triển khai các bước tiếp theo đúng tiến độ.
