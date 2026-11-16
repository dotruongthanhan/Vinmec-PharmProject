# KẾ HOẠCH KHẢO SÁT & XÁC THỰC ĐỊNH LƯỢNG TUẦN 2 (WEEK 2 INVESTIGATION PLAN)

> **Mục tiêu cốt lõi Tuần 2:** Chuyển từ *quan sát định tính* sang **chứng minh bằng số liệu thống kê thực tế (Quantitative Validation & Baseline KPIs)** và **xác nhận lộ trình tính năng của phần mềm SMH (VSF)** để quyết định **Go / No-Go** (Đáng làm hay Loại bỏ) cho 5 đề xuất dự án.  
> *(Lưu ý: Vấn đề chia đa mã `AA`/`AY` đã được xác nhận sẽ giải quyết triệt để trên phần mềm mới nên nhóm bỏ qua toàn bộ nội dung liên quan đến cân/chia mã `AA`/`AY`).*

---

## I. BẢNG TIÊU CHÍ CHỨNG MINH DỰ ÁN "ĐÁNG LÀM HAY KHÔNG" (GO / NO-GO CRITERIA)

| Đề xuất dự án | Số liệu thống kê cần thu thập (Real Statistics Needed) | Ngưỡng "ĐÁNG LÀM" (Go Criteria) | Ngưỡng "LOẠI BỎ / DỪNG" (No-Go Criteria) |
| :--- | :--- | :--- | :--- |
| **1. Dự báo Tồn kho Động & Cảnh báo Hàng xuất nhanh** | - Thời gian (giờ/tuần) làm file kiểm soát tồn kho & tính dự trù tại B1, T6, Nhà thuốc (không tính phần cân mã `AA`/`AY`).<br>- Số vụ "xuất nhanh đột xuất" / chạm đáy tồn kho mỗi tháng.<br>- Số lượng & giá trị thuốc cận date / chậm luân chuyển. | - Tốn $\ge$ 4–6 giờ/tuần làm thủ công; HOẶC phát sinh $\ge$ 5–10 mã thuốc có nguy cơ đứt gãy/tháng; VÀ **SMH chưa có thuật toán dự báo chuỗi thời gian / cảnh báo Runway động**. | - SMH đã xây dựng sẵn module dự báo tự động & cảnh báo tốc độ xuất; HOẶC công thức Excel hiện tại đã đáp ứng tốt mà không tốn thời gian. |
| **2. Tự động hóa Báo cáo Kháng sinh WHO `ATC/DDD`** | - Ước lượng tổng số giờ/ngày công đã dùng để hoàn thành kỳ báo cáo DDD gần nhất.<br>- Tổng số dòng y lệnh kháng sinh trong file báo cáo mẫu (6 tháng).<br>- Tỷ lệ dòng y lệnh trong báo cáo mẫu phải quy đổi đơn vị (`mg`, `g`, `UI`, thuốc phối hợp) & tra mã `ATC/DDD` theo đường dùng. | - Mất $\ge$ 2–3 ngày công/kỳ (hoặc có nhu cầu theo dõi định kỳ hàng tháng thay vì 6 tháng/lần); có hàng nghìn dòng y lệnh phức tạp; VÀ **SMH chưa tự động hóa báo cáo DDD chuẩn WHO**. | - SMH đã có sẵn mẫu báo cáo tự động `ATC/DDD`; HOẶC mỗi kỳ chỉ mất vài giờ xử lý Excel đơn giản. |
| **3. Tự động hóa Báo cáo 17 Chỉ số Dược Lâm Sàng** | - Ước lượng số giờ công của các DSLS + người tổng hợp cho kỳ báo cáo đầu tháng vừa xong.<br>- Trong 17 chỉ số của bản báo cáo mẫu: bao nhiêu chỉ số lấy từ `OH`, bao nhiêu chỉ số phụ thuộc dữ liệu ngoài khoa (như ca phẫu thuật), bao nhiêu chỉ số phải mở `EMR`.<br>- Số lượng hồ sơ bệnh án (`PID`) thực tế đã phải mở đọc tay trong báo cáo tháng vừa rồi. | - Mất $\ge$ 16–24 giờ công tổng hợp toàn phòng/tháng; phải mở đọc tay $\ge$ 100 hồ sơ `EMR`/tháng; VÀ **SMH chưa tự động trích xuất được dữ liệu liên khoa (phẫu thuật) & biên bản hội chẩn trên `EMR`**. | - SMH đã tự động tính đủ 17 chỉ số; HOẶC không được cấp quyền trích xuất/đọc dữ liệu `EMR` và dữ liệu ca phẫu thuật dưới mọi hình thức. |
| **4. Bóc tách Hóa đơn Tự động (`Invoice OCR/IDP`)** | - Số lượng hóa đơn nhà cung cấp và tổng số dòng hàng (`line items`) nhận mỗi ngày/tháng.<br>- Thời gian trung bình nhập thông tin 1 hóa đơn lên `SAP` (phút) & độ trễ từ lúc hàng về kho B1 đến khi lên hệ thống (`giờ`).<br>- Tần suất nhầm số lô, hạn dùng, giá hoặc xuất âm do "hàng treo". | - Trung bình $\ge$ 20–30 hóa đơn/ngày (hoặc $\ge$ 200 dòng hàng/ngày), tốn $\ge$ 2–3 giờ nhập tay/ngày, gây trễ xuất kho B1; VÀ **SMH chưa có tính năng OCR/nhập hóa đơn tự động lên SAP**. | - SMH hoặc hệ thống e-Invoice của Vingroup/SAP đã có sẵn tính năng import XML/OCR hóa đơn tự động sắp golive. |
| **5. Hỗ trợ Kiểm kê Nhà thuốc 24/7 & Đếm viên lẻ bằng Computer Vision** | - **Ưu tiên 1 – Kiểm kê kho:** Số giờ/ngày xử lý chênh lệch mỗi đợt kiểm kê, số mã bị lệch ảo do bán hàng 24/7, và **số lượng lọ thuốc mở dở phải đổ ra đếm từng viên lẻ khi kiểm kê**.<br>- **Ưu tiên 2 (Mở rộng) – Chia thuốc lẻ khi bán:** Số đơn chia lẻ `>20 viên`/ngày, thời gian đếm 1 đơn. | - Kiểm kê mất 1–2 ngày xử lý lệch ảo và tốn nhiều công đếm tay các lọ thuốc viên mở dở; VÀ **app kiểm kê/SMH chưa giải quyết được đối soát thời gian thực & đếm viên bằng CV**. | - App kiểm kê QR mới đã cập nhật real-time và số lượng thuốc lẻ cần đếm khi kiểm kê không đáng kể. |

---

## II. PHÂN NHÓM CÂU HỎI & HOẠT ĐỘNG QUAN SÁT THEO 7 ĐƠN VỊ (GROUPED BY DEPARTMENT)

> [!IMPORTANT]
> **Lưu ý quan trọng dành cho người phỏng vấn (Interviewer Guidelines):**
> - **Hạn chế dùng các từ *"chính xác"*, *"cụ thể"*** khi đặt câu hỏi ban đầu (tránh gây cảm giác tra khảo hoặc tạo áp lực buộc người trả lời phải nhớ con số tuyệt đối ngay lập tức).
> - Hãy hỏi mở về trải nghiệm/lần gần nhất trước; **chỉ hỏi đào sâu vào chi tiết/con số sau khi đã xác nhận được ít nhất 1 lần thực tế người dùng gặp vấn đề đó**.

---

### 1. Dược sĩ Lâm sàng – Medical Pharmacists (`Phòng Dược Lâm Sàng`)
*(Trọng tâm kiểm chứng: **Dự án 2 - Báo cáo DDD** và **Dự án 3 - Báo cáo 17 chỉ số**)*

#### 🔍 Cần Quan sát & Đánh giá trên Mẫu báo cáo đã hoàn thành (Observe & Evaluate):
*(Do hiện tại đã qua đầu tháng và kỳ báo cáo vừa hoàn tất nên không bấm giờ trực tiếp quá trình làm từ đầu, mà tập trung mổ xẻ file báo cáo mẫu vừa làm xong):*
- **Phân tích File mẫu Báo cáo 17 chỉ số (Dự án 3):**
  - Xin xem **File tổng hợp Bộ 17 chỉ số của tháng vừa hoàn thành** và các file thành phần từ các khoa gửi về.
  - Rà soát nguồn dữ liệu của từng chỉ số trong 17 chỉ số: chỉ số nào lấy trực tiếp từ file xuất `OH`, chỉ số nào lấy từ `Info Vinmec`, chỉ số nào cần dữ liệu ngoài Khoa Dược (như danh sách ca phẫu thuật), và chỉ số nào bắt buộc phải mở hồ sơ bệnh án `EMR` để kiểm tra.
  - Đếm trực tiếp trên file báo cáo tháng vừa rồi: có tổng cộng **bao nhiêu hồ sơ bệnh án (`PID`)** mà dược sĩ đã phải mở `EMR` để tra cứu (ví dụ: số ca kháng sinh hạn chế cần kiểm tra biên bản hội chẩn).
  - Nhờ dược sĩ mở thử 3–5 hồ sơ bệnh án mẫu từ danh sách đó trên `EMR` để quan sát cấu trúc của *Biên bản hội chẩn kháng sinh* (nằm ở tab nào, là biểu mẫu có cấu trúc hay văn bản tự do cần NLP đọc) và ước lượng thời gian tra cứu 1 hồ sơ.
- **Phân tích File mẫu Báo cáo Kháng sinh WHO `ATC/DDD` (Dự án 2):**
  - Xin xem **File Excel tính Báo cáo Kháng sinh DDD** của kỳ gần nhất.
  - Đếm tổng số dòng y lệnh kháng sinh trong file và kiểm tra cấu trúc các cột xuất từ `OH`: xem trường `Hàm lượng`, `Liều dùng`, `Đường dùng` đang ở dạng số chuẩn hóa hay chuỗi văn bản tự do (ví dụ: *"Pha 2 lọ truyền TTM"*, thuốc phối hợp nhiều hoạt chất, đơn vị `UI`/`MU`) cần NLP bóc tách; kiểm tra xem viện đã có bảng ánh xạ sẵn từ `Mã thuốc OH` sang `Mã WHO ATC/DDD` (phân biệt đường uống `O` vs. tiêm truyền `P`) chưa.

#### 💬 Câu hỏi cần Phỏng vấn (Ask):
1. **Về Báo cáo 17 chỉ số (`BN06`):**
   - *"Trong đợt làm báo cáo đầu tháng vừa rồi, thường khâu nào khiến anh/chị và các dược sĩ phụ trách khoa mất nhiều thời gian xử lý nhất? Ước tính toàn phòng mất khoảng bao nhiêu thời gian để hoàn thiện xong báo cáo tháng vừa qua?"*
   - *(Sau khi xác nhận việc phải lấy dữ liệu ngoài khoa / mở `EMR`):* *"Với những dữ liệu mà Khoa Dược không tự xuất được như danh sách ca phẫu thuật, đợt vừa rồi anh/chị lấy dữ liệu đó từ đâu và có gặp vướng mắc gì không? Còn việc mở `EMR` kiểm tra biên bản hội chẩn thì trung bình mỗi tháng anh/chị phải xem khoảng bao nhiêu bệnh án?"*
2. **Về Báo cáo Kháng sinh WHO `ATC/DDD`:**
   - *"Ở kỳ làm báo cáo DDD gần nhất, quá trình xử lý số liệu từ lúc xuất file `OH` đến lúc ra được bảng chỉ số DDD mất khoảng bao lâu? Anh/chị có từng gặp trường hợp bị lệch số liệu hoặc vất vả khi phải quy đổi các đơn vị hàm lượng khác nhau (`mg`, `g`, `UI`) và tra mã `ATC/DDD` không?"*
   - *"Nếu có công cụ giúp tự động hóa việc tính DDD nhanh hơn (ví dụ theo dõi được hàng tháng thay vì 6 tháng/lần), điều đó có hỗ trợ thêm gì cho công tác quản lý kháng sinh của khoa không?"*

---

### 2. Kho Nội trú – Internal Storage (`Kho trung tâm B1 & Kho vệ tinh T6`)
*(Trọng tâm kiểm chứng: **Dự án 1 - Dự báo Tồn kho Động & Cảnh báo Hàng xuất nhanh**, và tác động của **Dự án 4 - Độ trễ hóa đơn**)*

#### 🔍 Cần Quan sát & Đo lường trực tiếp (Observe & Measure):
- **Bấm giờ thao tác làm file Kiểm soát tồn kho & Dự trù (Không tính phần cân mã `AA`/`AY`):**
  - Ngồi cạnh dược sĩ kho B1 trong 1 buổi làm kiểm soát tồn kho định kỳ (chu kỳ 3–4 ngày/lần): chỉ bấm giờ thời gian **xuất dữ liệu, tính toán số lượng dự trù, rà soát tốc độ xuất và kiểm tra hạn dùng** (bỏ qua thao tác cân đối mã `AA`/`AY`).
- **Thu thập thống kê lịch sử từ file Excel kho (3–6 tháng gần nhất):**
  - Đếm tổng số mặt hàng thuốc vật lý gốc (`SKU`) đang quản lý tại kho B1 và T6.
  - Xem lịch sử các tờ trình **Dự trù đột xuất** trong 3 tháng qua: đếm số đợt phải làm dự trù đột xuất mỗi tháng và số mặt hàng bị rơi vào tình trạng *"xuất nhanh đột xuất"* (tồn kho thực tế tụt xuống thấp hơn thời gian `Lead Time` giao hàng).
  - Xem danh sách theo dõi **Thuốc cận hạn (`cận date`) & Chậm luân chuyển**: đếm số lượng mặt hàng đang nằm trong danh sách cảnh báo cận date (< 6–12 tháng) hoặc chậm luân chuyển.

#### 💬 Câu hỏi cần Phỏng vấn (Ask):
1. **Về Quy trình Dự trù & Kiểm soát tồn kho khi không còn vướng mã `AA`/`AY`:**
   - *"Khi phần mềm mới giải quyết xong việc gộp mã `AA`/`AY`, những bước nào trong việc theo dõi tồn kho, tính toán dự trù và kiểm soát hạn dùng vẫn làm chị tốn nhiều thời gian và phải tính thủ công bằng kinh nghiệm?"*
2. **Về Hàng xuất nhanh đột xuất & Dự báo nhu cầu:**
   - *"Trong vài tháng gần đây, kho mình có gặp tình huống mặt hàng nào tiêu thụ tăng vọt bất ngờ khiến tồn kho chạm đáy hoặc suýt không kịp hàng cho lâm sàng trước khi nhà cung cấp giao tới không?"* *(Nếu có $\rightarrow$ hỏi thêm tần suất xảy ra mỗi tháng và các nhóm thuốc hay gặp).*
3. **Về Kiểm soát Cận date & Nhận hàng đầu vào:**
   - *"Khi nhận hàng mới ở cửa kho B1, chị có hay gặp các lô hàng hạn dùng còn ngắn (dưới 1 năm) mà phải đứng ước lượng xem kho có dùng hết kịp trước hạn an toàn để quyết định nhận hay trả lại không?"* *(Nếu có $\rightarrow$ hỏi thêm tần suất mỗi tuần/tháng).*
4. **Về Độ trễ nhập hóa đơn ("Hàng treo"):**
   - *"Gần đây kho có hay gặp cảnh hàng của nhà cung cấp đã giao tới cửa kho B1 và các tầng cần lĩnh gấp, nhưng phải chờ bên Nghiệp vụ nhập hóa đơn lên hệ thống dẫn tới bị ghi nhận xuất âm không?"* *(Nếu có $\rightarrow$ hỏi thêm tần suất mỗi tuần).*

---

### 3. Nhà thuốc Bệnh viện – External Storage / Retail Drug Store (`Nhà thuốc 24/7`)
*(Trọng tâm kiểm chứng: **Dự án 5 - Ưu tiên số 1 là Hỗ trợ Kiểm kê kho 24/7 & Đếm viên lẻ trong lọ bằng Computer Vision**; ưu tiên số 2 là Đếm viên khi phát thuốc; và **Dự án 1 - Dự trù Nhà thuốc**)*

#### 🔍 Cần Quan sát & Đo lường trực tiếp (Observe & Measure):
- **Trọng tâm số 1 – Xem dữ liệu Kiểm kê kho & Kiểm kê thuốc viên lẻ mở lọ (`BN13`):**
  - Xem file biên bản/bảng chênh lệch của **2 đợt kiểm kê gần nhất** tại Nhà thuốc:
    - Tổng số mặt hàng kiểm kê tại Nhà thuốc là bao nhiêu?
    - Có bao nhiêu mặt hàng phải **kiểm kê theo viên lẻ** (các lọ thuốc lớn đã mở nắp dùng dở phải đổ ra đếm từng viên còn lại trong lọ)?
    - Có bao nhiêu mặt hàng bị báo lệch ở lần xuất Snapshot đầu tiên, và trong đó bao nhiêu trường hợp là *"lệch ảo"* do quầy vẫn xuất bán 24/7 trong lúc đang đếm thuốc?
  - Quan sát thử thao tác dược sĩ đếm kiểm kê 5–10 lọ thuốc viên mở dở để xem hình dáng lọ/khay thuốc và bấm giờ thời gian đếm tay mỗi lọ (phục vụ đánh giá tính năng **Computer Vision đếm số viên còn lại trong lọ/khay khi kiểm kê**).
- **Trọng tâm số 2 (Bước mở rộng nếu dự án kiểm kê khả thi) – Chia thuốc lẻ khi bán (`BN14`):**
  - Quan sát trong 30–60 phút tại quầy: ghi nhận tần suất đơn thuốc phải lấy viên lẻ từ lọ lớn cho vào túi zip (đặc biệt các đơn `>20 viên`) và thời gian đếm trung bình.
- **Xem file Dự trù Nhà thuốc (`BN08`):**
  - Xem file Excel dự trù thường quy (ngày 01 & 15) và dự trù đột xuất (chu kỳ 10 ngày) của tháng gần nhất để đếm số lượng mặt hàng cần dự trù.

#### 💬 Câu hỏi cần Phỏng vấn (Ask):
1. **Về Kiểm kê kho 24/7 & Đếm viên lẻ tồn trong lọ (`BN13` – Ưu tiên 1):**
   - *"Trong đợt kiểm kê gần nhất bằng app QR, quá trình kiểm đếm và xử lý chênh lệch của Nhà thuốc diễn ra như thế nào, mất khoảng bao nhiêu thời gian của các anh/chị?"*
   - *(Sau khi xác nhận khó khăn khi kiểm kê):* *"Khi kiểm kê các lọ thuốc đã mở nắp (bán lẻ theo viên), hiện tại anh/chị đang đếm số viên còn lại trong lọ bằng cách nào? Nhà thuốc có khoảng bao nhiêu mặt hàng phải đổ ra đếm viên lẻ như vậy trong mỗi kỳ kiểm kê? Nếu có công cụ chụp ảnh qua điện thoại (Computer Vision) để đếm nhanh số viên còn lại trong lọ/khay và đối soát tồn kho trực tiếp theo thời gian thực ngay lúc quét QR thì sẽ giúp ích được những khâu nào?"*
   - *"Trong các mặt hàng bị lệch số liệu sau kiểm kê, nguyên nhân thường đến từ việc quầy vẫn bán hàng trong lúc kiểm kê hay do nhầm lẫn khi đếm thuốc lẻ hàng ngày?"*
2. **Về Chia thuốc lẻ khi bán (`BN14` – Ưu tiên 2 / Mở rộng):**
   - *"Hàng ngày khi chia thuốc viên lẻ vào túi zip cho khách, anh/chị có gặp trường hợp đơn nhiều viên dễ bị đếm nhầm dẫn tới lệch kho không?"*
3. **Về Dự trù Nhà thuốc (Dự án 1):**
   - *"Mỗi tháng việc làm dự trù thường quy (mùng 1 & 15) và các đợt dự trù đột xuất chiếm khoảng bao nhiêu thời gian của chị? Có hay xảy ra tình trạng thuốc tại quầy bán tăng vọt bất ngờ khiến phải làm dự trù đột xuất gấp không?"*

---

### 4. Phòng Nghiệp vụ Dược – Pharmacy Professional Practice (`Nghiệp vụ Dược`)
*(Trọng tâm kiểm chứng: **Dự án 4 - Bóc tách Hóa đơn Tự động `Invoice OCR/IDP`**)*

#### 🔍 Cần Quan sát & Đo lường trực tiếp (Observe & Measure):
- **Quan sát & Bấm giờ nhập Hóa đơn Nhà cung cấp lên `SAP` (`BN12` – Không tính phần chia mã `AA`/`AY`):**
  - Ngồi cạnh dược sĩ nghiệp vụ phụ trách hóa đơn trong 1–2 giờ: bấm giờ thực tế xử lý **10 bộ hóa đơn** liên tiếp, chỉ đo **thời gian đọc và gõ thông tin hóa đơn thuần túy** (mã thuốc, số lô, hạn dùng, đơn giá, số lượng, thuế vào `SAP`, bỏ qua bước chia mã `AA`/`AY`).
  - Quan sát định dạng thực tế của hóa đơn nhà cung cấp: là hóa đơn giấy, file PDF điện tử, hay có kèm file XML? Đếm trung bình 1 hóa đơn có bao nhiêu dòng mặt hàng (`line items`).

#### 💬 Câu hỏi cần Phỏng vấn (Ask):
1. **Về Khối lượng & Độ trễ Nhập Hóa đơn (`BN12`):**
   - *"Mỗi ngày phòng mình thường tiếp nhận và nhập khoảng bao nhiêu tờ hóa đơn từ các nhà cung cấp, và riêng việc gõ thông tin hóa đơn lên hệ thống chiếm khoảng bao nhiêu thời gian của anh/chị?"*
   - *"Vào những đợt hàng về nhiều, có khi nào hóa đơn dồn lại chưa kịp nhập ngay làm ảnh hưởng đến việc xuất kho dưới B1 hoặc dễ bị gõ nhầm các thông số như số lô, hạn dùng, đơn giá không?"*

---

### 5. Phòng Quản lý Dược – Pharmacy Management (`Quản lý Dược`)
*(Trọng tâm kiểm chứng: **Dự án 1 - Tối ưu Ngân sách, MOQ, Lead Time & Cảnh báo Hàng xuất nhanh / Chậm luân chuyển**)*

#### 🔍 Cần Quan sát & Đo lường trực tiếp (Observe & Measure):
- Xem cấu trúc **File trình duyệt Dự trù thường quy & Dự trù đột xuất** mà Kho B1 và Nhà thuốc gửi lên Phòng Quản lý Dược: ghi nhận các cột dữ liệu, cách thể hiện trần ngân sách (`Budget`), số lượng đặt hàng tối thiểu (`MOQ`) của nhà cung cấp và `Lead Time`.

#### 💬 Câu hỏi cần Phỏng vấn (Ask):
1. **Về Duyệt Dự trù, Ngân sách & MOQ (`BN15`):**
   - *"Mỗi tháng Phòng Quản lý Dược thường duyệt bao nhiêu đợt dự trù thường quy và đột xuất từ các kho/nhà thuốc? Khâu rà soát, cân đối lại số lượng cho khớp ngân sách và điều kiện giao hàng của nhà cung cấp thường mất khoảng bao lâu?"*
   - *"Hiện tại thông tin về `Lead Time` giao hàng thực tế và mức tối thiểu xuất hóa đơn (`MOQ`) của từng nhà cung cấp đã có bảng tổng hợp sẵn chưa hay anh/chị đang theo dõi ở đâu?"*
2. **Về Thiệt hại do Đứt hàng & Hàng Cận date / Chậm luân chuyển:**
   - *"Trong năm qua, viện mình có thống kê sơ bộ về tỷ lệ/giá trị thuốc phải đổi trả hoặc hủy do cận hạn dùng, giá trị hàng chậm luân chuyển, hoặc tần suất bác sĩ phải kê 'Thuốc mua ngoài' do hết hàng đột xuất không?"*

---

### 6. Phòng Công nghệ Thông tin Bệnh viện – Hospital IT (`Phòng IT`)
*(Trọng tâm kiểm chứng: **Khả năng trích xuất dữ liệu cho Dự án 1, 2, 3, 4 và Kiểm kê Nhà thuốc – Dự án 5**)*

#### 💬 Câu hỏi Kỹ thuật cần Phỏng vấn & Kiểm tra (Ask & Verify):
1. **Về Dữ liệu Lịch sử Xuất Nhập Tồn cho Dự báo Tồn kho (Dự án 1):**
   - *"Hệ thống `OH` (và phần mềm cũ `eHos` nếu cần) có hỗ trợ xuất lịch sử giao dịch Xuất – Nhập – Tồn theo ngày/tháng của khoảng **12–24 tháng gần nhất** (kèm số lô, hạn dùng, giá nhập) ra file Excel/CSV để phân tích chuỗi thời gian không?"*
2. **Về Khả năng Trích xuất Dữ liệu cho Báo cáo DDD (Dự án 2) & Báo cáo 17 chỉ số (Dự án 3):**
   - *"Trên hệ thống `EMR` và `OH`, Khoa Dược hoặc IT có thể xuất dữ liệu hàng loạt (batch export) đối với: (1) Tổng số ngày giường bệnh nhân nội trú (`Patient-days`) theo khoa/tháng, (2) Danh sách ca phẫu thuật trong tháng, và (3) Nội dung văn bản *Biên bản hội chẩn kháng sinh* trên `EMR` để phục vụ làm báo cáo tự động không?"*
3. **Về Dữ liệu Hóa đơn Điện tử & Import `SAP` (Dự án 4):**
   - *"Khi nhà cung cấp giao hàng và xuất hóa đơn điện tử, hệ thống của viện có nhận được file `.xml` gốc của hóa đơn không? Hệ thống `SAP`/`OH` hiện tại có chức năng Import bảng kê hóa đơn từ file Excel/CSV/XML thay vì phải gõ tay từng dòng không?"*
4. **Về Dữ liệu Giao dịch Thời gian thực cho Kiểm kê Nhà thuốc 24/7 (Dự án 5):**
   - *"Ở Nhà thuốc 24/7, khi nhân viên quầy xuất bán một đơn thuốc trên `OH`, số lượng tồn kho trong Database có được trừ tức thời (real-time kèm `timestamp` từng giây) để app kiểm kê có thể truy vấn đối soát ngay tại thời điểm quét mã QR không?"*

---

### 7. Đội Phát triển Phần mềm SMH thuộc VSF (`Phòng Phát triển Phần mềm VSF`)
*(Trọng tâm sống còn: **Chốt ranh giới 5 dự án với SMH để không làm trùng lặp**)*

#### 💬 Câu hỏi Chốt Ranh giới Sản phẩm (Scope Alignment Questions):
1. **Về Kế hoạch Quản trị Tồn kho & Dự trù trên SMH (Kiểm chứng Dự án 1):**
   - *"Hiện tại nhóm mới được xem tài liệu tiến độ của SMH cho mảng Dược lâm sàng, chưa được xem tài liệu mảng Quản lý Kho & Cung ứng. Đội dự án có thể chia sẻ lộ trình tính năng mảng Kho của SMH được không?"*
   - *"Ngoài việc giải quyết vấn đề gộp mã `AA`/`AY`, đối với bài toán kiểm soát tồn kho và dự trù, SMH có kế hoạch xây dựng các tính năng sau không (và nếu có thì theo công thức cố định hay dùng thuật toán AI/Tối ưu hóa):*
     1. *Dynamic Runway & Velocity Spike Alerting: Tự động tính số ngày tồn kho khả dụng (`Runway`) và cảnh báo sớm khi tốc độ xuất kho ngắn hạn tăng đột biến so với `Lead Time` từng nhà cung cấp?*
     2. *Time-Series AI Forecasting: Dự báo nhu cầu đặt hàng theo chuỗi thời gian, mùa vụ và công suất giường bệnh?*
     3. *Budget & MOQ Optimizer: Tự động tối ưu hóa giỏ đặt hàng theo trần ngân sách (`Budget`), quy cách đóng gói và ngưỡng xuất hóa đơn tối thiểu (`MOQ`) của nhà cung cấp?*
     4. *Near-Expiry & Slow-Moving Advisor: Cảnh báo sớm hàng chậm luân chuyển/cận date và công cụ tính toán tại khâu nhận hàng để khuyến nghị Chấp nhận/Từ chối lô hàng cận date dựa trên tốc độ tiêu thụ dự kiến?"*
2. **Về Module Báo cáo Tự động trên SMH (Kiểm chứng Dự án 2 & Dự án 3):**
   - *"Trong tài liệu của SMH có đề cập đến mục 'Công cụ báo cáo tự động' (Automatic Report Tool). Xin hỏi danh sách các báo cáo mà SMH dự kiến tự động hóa gồm những báo cáo nào?"*
   - *"SMH có bao gồm **Báo cáo Tiêu thụ Kháng sinh chuẩn WHO (`ATC/DDD` / 1.000 ngày bệnh nhân)** và **Báo cáo Bộ 17 Chỉ số Dược Lâm Sàng hàng tháng** không?"*
   - *"Nếu SMH có làm báo cáo 17 chỉ số, đội dự án dự kiến xử lý như thế nào với: (1) Các dữ liệu nằm ngoài Khoa Dược mà dược sĩ không tự lấy được (ví dụ: dữ liệu ca phẫu thuật từ các khoa ngoại/phòng mổ), và (2) Việc phải kiểm tra nội dung văn bản *Biên bản hội chẩn kháng sinh* trên hồ sơ bệnh án `EMR`?"*
3. **Về Nhập liệu Hóa đơn Nhà cung cấp (Kiểm chứng Dự án 4):**
   - *"SMH có bao gồm tính năng **OCR / Tự động bóc tách hóa đơn giao hàng của nhà cung cấp** (từ bản giấy/PDF/XML) để tự động đẩy dữ liệu số lô, hạn dùng, giá nhập vào hệ thống kho và đồng bộ sang `SAP` không?"*
4. **Về Kiểm kê Nhà thuốc 24/7 & Kiểm kê Thuốc viên lẻ (Kiểm chứng Dự án 5):**
   - *"Đối với Nhà thuốc bệnh viện, SMH có thay thế phần mềm `OH` và **App Kiểm kê kho QR** hiện tại bằng cơ chế đối soát tồn kho động theo thời gian thực (tránh lệch số liệu ảo khi quầy vừa bán hàng 24/7 vừa kiểm kê) không?"*
   - *"SMH có công cụ nào hỗ trợ kiểm đếm nhanh số viên thuốc lẻ còn lại trong các lọ thuốc đã mở nắp khi kiểm kê (hoặc khi chia thuốc lẻ tại quầy) không?"*
5. **Về Khả năng Phối hợp / Tích hợp PoC của Nhóm vào SMH:**
   - *"Với những tính năng nâng cao chưa nằm trong phạm vi ưu tiên hiện tại của SMH (ví dụ: Engine dự báo tồn kho động, NLP bóc tách báo cáo DDD/EMR, Invoice OCR, hoặc Computer Vision đếm viên thuốc khi kiểm kê), nhóm có thể phát triển thành các module PoC bổ trợ theo chuẩn đầu vào/đầu ra (API, JSON, Excel/CSV) nào để thuận tiện kết nối với SMH nhất?"*

---

## III. LỊCH TRÌNH HÀNH ĐỘNG ĐỀ XUẤT TRONG TUẦN 2 (SUGGESTED SCHEDULE)

| Ngày | Buổi sáng (08:00 – 12:00) | Buổi chiều (13:30 – 17:30) | Đầu ra bắt buộc cuối ngày (Deliverables) |
| :--- | :--- | :--- | :--- |
| **Thứ Hai** | **Làm việc với Đội dự án SMH (VSF) & Phòng IT:**<br>Chốt ranh giới tính năng của SMH (Inventory, DDD, 17 KPIs, Invoice OCR, Kiểm kê Nhà thuốc) và khả năng xuất dữ liệu `EMR`/`OH`. | **Họp Online với Mentor Y tế (ThS.DS Nguyễn Lê Trang):**<br>Trình bày tóm tắt Tuần 1 + thông tin từ SMH, lắng nghe bài toán ưu tiên của Trưởng khoa và xin phép thu thập số liệu thống kê. | Bảng đối chiếu **SMH vs. 5 Đề xuất của nhóm** (xác định rõ tính năng nào SMH chưa làm). |
| **Thứ Ba** | **Kho Nội trú B1/T6 & Phòng Quản lý Dược:**<br>Bấm giờ lập dự trù (không tính phần cân mã `AA`/`AY`), thống kê số vụ xuất nhanh đột xuất, cận date và quy tắc Budget/MOQ. | **Phòng Nghiệp vụ Dược:**<br>Bấm giờ nhập 10 hóa đơn lên `SAP` (không tính phần chia mã `AA`/`AY`), thống kê số hóa đơn/ngày, độ trễ "hàng treo". | Bộ số liệu định lượng (Baseline KPIs) cho **Dự án 1 (Inventory)** và **Dự án 4 (Invoice OCR)**. |
| **Thứ Tư** | **Phòng Dược Lâm Sàng:**<br>Xem file báo cáo mẫu **17 chỉ số** & **Báo cáo DDD** vừa hoàn thành đầu tháng; thống kê nguồn dữ liệu từng chỉ số và đếm số hồ sơ `EMR` phải mở. | **Nhà thuốc 24/7:**<br>Xem biên bản 2 đợt kiểm kê gần nhất (số mã lệch ảo, số lọ thuốc mở dở phải đếm viên lẻ); quan sát thao tác đếm viên lẻ để đánh giá bài toán **Computer Vision**. | Bộ số liệu định lượng (Baseline KPIs) cho **Dự án 2 (DDD)**, **Dự án 3 (17 KPIs)** và **Dự án 5 (Kiểm kê & CV đếm viên)**. |
| **Thứ Năm** | **Tổng hợp số liệu & Chấm điểm Ma trận Go/No-Go:**<br>Tính toán ROI (số giờ tiết kiệm/tháng, tỷ lệ giảm lỗi) cho từng dự án dựa trên số liệu thực tế vừa thu thập. | **Trao đổi với Mentor Công nghệ & Chốt 01 Bài toán PoC:**<br>Báo cáo số liệu thực tế và thống nhất phạm vi kỹ thuật cho 4 tuần xây dựng PoC tiếp theo. | **Báo cáo Tuần 2 hoàn chỉnh** & Bản đặc tả kỹ thuật cho dự án PoC được chọn. |
