# PLAN 1.2 – GIAO DIỆN VÀ TRẢI NGHIỆM CHO DƯỢC SĨ

**Ngày viết:** 16/11/2026 · **Trạng thái:** đề xuất, làm ngay phần MVP (task T13).
**Quan hệ:** plan 1 (bối cảnh, nỗi đau N1–N12, tính năng F1–F8) · plan 1.1 (kiến trúc, mục 7.2 đồ thị hỏi thêm). Bản này thay phần mô tả giao diện ở brief T07.

---

## 1. Người dùng và ba câu hỏi họ cần trả lời

Người dùng là dược sĩ lâm sàng đang thẩm định y lệnh, bị ngắt quãng liên tục, mỗi ca có 1–4 phút (ca thường) tới 20 phút (ca phức tạp). Với mỗi ca họ cần trả lời theo thứ tự:

1. **Người bệnh này là ai, đang thế nào?** (đọc bệnh án là khâu tốn nhất: N1, N2)
2. **Đơn này có gì phải xem?** (bảng nhận định: N3, N5)
3. **Dựa vào đâu mà nói vậy?** (căn cứ, nguồn: N11)

Mọi quyết định bố cục dưới đây đều để ba câu này trả lời được **không cần cuộn, không cần bấm** cho ca thường, và trong **tối đa hai lần bấm** cho ca phức tạp.

## 2. Nguyên tắc thiết kế

| # | Nguyên tắc | Hệ quả cụ thể |
| :-: | :--- | :--- |
| P1 | **Thứ cần xem nằm trên cùng.** | Mục nghiêm trọng trước, rồi cần lưu ý, rồi không đủ dữ liệu, rồi ngoài HDSD. Mục đạt gom lại, đóng sẵn |
| P2 | **Thiếu dữ liệu phải nhìn thấy được.** | "Chưa có thông tin dị ứng" hiển thị khác hẳn "Đã hỏi, không dị ứng". Ô chỉ số thiếu đầu vào ghi rõ thiếu gì. Không bao giờ để trống hoặc ghi "đạt" khi thiếu |
| P3 | **Mỗi nhận định đi kèm căn cứ, mở được trong một lần bấm.** | Dữ liệu ca → phép tính → đoạn nguồn, đúng thứ tự suy luận |
| P4 | **Nói rõ ai nói.** | Mỗi nhận định có nhãn nguồn gốc: `Luật` · `AI, đã kiểm chứng` · `AI, chưa kiểm chứng`. Mỗi dòng tri thức chưa được dược sĩ duyệt có ghi chú |
| P5 | **Dược sĩ quyết định.** | Không có nút "duyệt đơn". Chỉ có phản hồi trên từng nhận định. Dải thông báo cố định nhắc đây là kết quả tham khảo |
| P6 | **Không dùng màu làm tín hiệu duy nhất.** | Mức độ luôn có chữ và biểu tượng kèm màu |
| P7 | **Tiếng Việt của người làm nghề, không có mã nội bộ.** | Không hiện `can_xem`, `truc_tiep`, `lieu_than_can_chinh`. Số dùng dấu phẩy thập phân, luôn kèm đơn vị và thời điểm |
| P8 | **Hệ thống đang làm gì thì nói ra.** | Khi chạy có từng bước: lấy bối cảnh → tính chỉ số → chạy luật → tra nguồn → tổng hợp → kiểm chứng. Chạy chế độ thiếu (không LLM, chỉ từ khoá) thì ghi rõ |
| P9 | **Văn bản từ bệnh án là dữ liệu, không phải giao diện.** | Hiển thị dạng văn bản thuần; không diễn giải markdown, liên kết, ảnh (phòng chèn lệnh) |

## 3. Bố cục màn hình

```text
┌──────────────┬──────────────────────────────────────────────┬─────────────────────────┐
│ HÀNG ĐỢI     │ A. DẢI ĐỊNH DANH CA (luôn ở trên)            │ D. HỎI THÊM VỀ CA NÀY   │
│              │ DEMO-02 · Nữ 75 tuổi · 50 kg · Hô hấp, nội trú│                         │
│ Lọc:         │ CrCl 16,0 mL/phút ▼ · DỊ ỨNG: không ghi nhận │ [gợi ý câu hỏi]         │
│ ○ Tất cả     │ 1 nghiêm trọng · 0 cần lưu ý · 0 thiếu dữ liệu│                         │
│ ○ Cần xem    ├──────────────────────────────────────────────┤ hội thoại, câu trả lời  │
│              │ B. TÓM TẮT (3 cột, không cuộn)               │ có trích dẫn [1][2]     │
│ ● DEMO-02 🔴1│ Chẩn đoán · Diễn biến mới nhất · XN bất thường│                         │
│   DEMO-06 🔴1├──────────────────────────────────────────────┤ ▸ Hệ thống đã tra gì    │
│   DEMO-05 🟡1│ C. BẢNG NHẬN ĐỊNH                            │                         │
│   DEMO-03 ⚪1│ ┌ thẻ nhận định nghiêm trọng ──────────────┐ │                         │
│   DEMO-01 ✓  │ │ Thuốc | Yếu tố | Nhận xét  [Luật]        │ │                         │
│   DEMO-04 ✓  │ │ ▸ Căn cứ (3)   Đồng ý · Bác bỏ · Cần sửa │ │ ┌─────────────────────┐ │
│              │ └──────────────────────────────────────────┘ │ │ Nhập câu hỏi…       │ │
│              │ ▸ Các mục đạt (3)                            │ └─────────────────────┘ │
│              ├──────────────────────────────────────────────┤                         │
│              │ E. CHI TIẾT (thẻ chuyển)                     │                         │
│              │ Y lệnh | Xét nghiệm | Vi sinh | Diễn biến    │                         │
└──────────────┴──────────────────────────────────────────────┴─────────────────────────┘
```

Tỉ lệ cột chính : cột hỏi thêm khoảng 5 : 3. Cột hỏi thêm thu gọn được để nhường chỗ cho bảng nhận định.

### 3.1. Hàng đợi (thanh bên)

- Mỗi ca một dòng: mã ca, khoa, mô tả ngắn, và **huy hiệu mức cao nhất** kèm số lượng (`🔴 1`, `🟡 1`, `⚪ 1 thiếu dữ liệu`, `✓`).
- **Sắp xếp mặc định theo mức ưu tiên**: nghiêm trọng → cần lưu ý → thiếu dữ liệu → đạt; cùng mức thì theo thời điểm kê. Dược sĩ thấy ca cần xem trước tiên.
- Bộ lọc: Tất cả · Cần xem · Đã phản hồi hết.
- Ca đã phản hồi đủ mọi nhận định có dấu "đã xem".

### 3.2. A – Dải định danh ca

Một dòng, luôn hiện, chứa đúng những thứ dược sĩ liếc lại nhiều nhất: mã ca, giới, tuổi, cân nặng, khoa và nội trú / ngoại trú, **CrCl** (kèm mũi tên khi bất thường), **trạng thái dị ứng** (ba trạng thái, ba cách hiển thị khác hẳn nhau), và ba con số đếm nhận định theo mức.

Dị ứng:

| Trạng thái | Hiển thị |
| :--- | :--- |
| Có dị ứng | Nền đỏ, biểu tượng cảnh báo: `DỊ ỨNG: penicillin (mày đay)` |
| Đã hỏi, không có | Chữ thường: `Dị ứng: đã hỏi, không ghi nhận` |
| Chưa có thông tin | Nền vàng: `CHƯA CÓ THÔNG TIN DỊ ỨNG` |

### 3.3. B – Tóm tắt

Ba cột, chiều cao cố định, đọc trong 10 giây:

1. **Chẩn đoán và cơ địa:** chẩn đoán chính (kèm ICD-10), chẩn đoán kèm, cơ địa đặc biệt (thai, cho con bú, suy gan, suy thận), ngày vào viện và **số ngày nằm viện**.
2. **Diễn biến mới nhất:** thời điểm + nội dung ghi chép gần nhất; liên kết "xem tất cả" nhảy tới thẻ Diễn biến.
3. **Bất thường gần nhất:** tối đa 5 xét nghiệm ngoài ngưỡng, mỗi dòng có giá trị, đơn vị, mũi tên, thời điểm, và **xu hướng so với lần trước** nếu có (`212 ▲ từ 150, sau 3 ngày`). Bốn chỉ số đã tính (CrCl, eGFR, BMI, BSA) nằm ở đây, bấm vào từng số để xem đầu vào và công thức.

### 3.4. C – Bảng nhận định (trọng tâm)

Một thẻ cho mỗi nhận định cần chú ý:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ ⛔ NGHIÊM TRỌNG · Cần xem                        [Luật] · Yếu tố 6      │
│                                                                         │
│ Thuốc                  Yếu tố kiểm tra        Nhận xét                  │
│ Meropenem 1 g          Cơ địa và xét nghiệm   CrCl 16,0 mL/phút: cần    │
│ truyền TM, 3 lần/ngày                         xem xét chỉnh liều theo   │
│                                               thận (một nửa liều, mỗi   │
│                                               12 giờ)                   │
│                                                                         │
│ ▾ Căn cứ (3)                                                            │
│   1. Dữ liệu ca   Creatinin máu 212 µmol/L, 10/11 05:30   [XN-DEMO02-01]│
│   2. Tính toán    CrCl Cockcroft-Gault = 16,0 mL/phút     [xem phép tính]│
│   3. Tài liệu     Nhãn FDA MERREM IV, mục liều khi suy thận [mở nguồn]  │
│      ⚠ Dòng luật này chưa được dược sĩ duyệt                            │
│                                                                         │
│ [ Đồng ý ]  [ Bác bỏ ]  [ Cần sửa ]                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

- **Ba cột Thuốc · Yếu tố kiểm tra · Nhận xét** giữ nguyên: đó là dạng bảng dược sĩ đang quen (N8).
- **Nhãn mức độ và kết luận** ở góc trái trên; **nhãn nguồn gốc** (P4) và yếu tố ở góc phải.
- **Căn cứ** đóng sẵn với ca thường, mở sẵn với mục nghiêm trọng. Thứ tự luôn là dữ liệu ca → tính toán → tài liệu.
- "Còn thiếu: …" hiện ngay dưới nhận xét khi kết luận là không đủ dữ liệu, kèm gợi ý lấy ở đâu.
- Mục đạt gom trong một khối đóng sẵn, dạng bảng gọn. Vẫn phải xem được: dược sĩ cần biết hệ thống **đã kiểm** những gì.
- Khi chưa có mục nào cần chú ý: ghi rõ `Không có mục cần chú ý trong phạm vi N luật đã chạy`, kèm danh sách yếu tố **chưa được kiểm** (ví dụ tương tác thuốc khi chưa có bảng tương tác). Không để dược sĩ hiểu nhầm im lặng là an toàn.

### 3.5. Phản hồi trên từng nhận định

- Ba nút: **Đồng ý · Bác bỏ · Cần sửa**.
- "Đồng ý" ghi ngay. "Bác bỏ" và "Cần sửa" mở một ô chọn nhanh lý do (`Không phù hợp lâm sàng` · `Đã biết, đã xử lý` · `Sai dữ liệu đầu vào` · `Sai nguồn hoặc nguồn cũ` · `Khác`) và ô ghi chú; phải chọn lý do mới ghi được.
- Sau khi ghi: thẻ hiện trạng thái `Đã phản hồi: Đồng ý lúc 10:32`, các nút đổi thành "Sửa phản hồi". Bấm lại không tạo phản hồi trùng mà ghi dòng mới thay thế (dòng cũ vẫn giữ trong nhật ký).

### 3.6. Xem nguồn

Bấm "mở nguồn" mở hộp thoại:

- tên nguồn, **tầng tin cậy** (`Tầng 1 · Bộ Y tế`, `Tầng 3 · Nhãn FDA`), phiên bản và ngày hiệu lực, đường dẫn mục;
- **nguyên văn đoạn nguồn**, phần được trích dẫn tô nền;
- liên kết tới bản gốc; ghi chú giấy phép nếu nguồn chỉ để sàng lọc;
- khi hai nguồn nói khác nhau: hiện cả hai, tầng cao đứng trước, không tự chọn.

### 3.7. D – Khung hỏi thêm (agent)

Mục đích: hỏi về **ca đang mở**, nhận câu trả lời có trích dẫn. Không phải chatbot tự do.

- **Câu hỏi gợi ý** sinh từ ca, hiện khi chưa có hội thoại: `Vì sao kê kháng sinh này?` · `Thuốc nào cần chỉnh liều theo chức năng thận?` · `Có tương tác nào giữa các thuốc đang dùng?` · `Tóm tắt diễn biến 3 ngày gần nhất`.
- **Câu trả lời** gồm: nội dung, số trích dẫn `[1] [2]` bấm mở đúng hộp thoại nguồn ở 3.6 hoặc đúng bản ghi của ca; cuối câu trả lời có khối đóng sẵn **"Hệ thống đã tra gì"** liệt kê công cụ đã gọi và kết quả tóm tắt (minh bạch, P8).
- **Không hiện chữ trước khi kiểm chứng xong.** Trong lúc chờ hiện từng bước đang chạy.
- **Trả lời không có nguồn thì nói không có nguồn:** `Không tìm thấy căn cứ trong kho nguồn hiện có.` Không trả lời bằng kiến thức chung của mô hình.
- **Ngoài phạm vi thì từ chối rõ:** câu hỏi về ca khác, yêu cầu ghi y lệnh, yêu cầu gửi tin đều nhận câu `Hệ thống chỉ đọc và chỉ trả lời về ca đang mở.`
- Hội thoại gắn với ca; đổi ca thì khung hỏi thêm đổi theo; có nút xoá hội thoại.
- Dải chú thích cố định dưới ô nhập: `Trả lời tham khảo, có trích dẫn. Không dán dữ liệu người bệnh thật.`

### 3.8. E – Chi tiết

Bốn thẻ chuyển, chỉ để tra khi cần:

- **Y lệnh:** y lệnh chờ duyệt (thuốc, liều, tần suất, đường dùng, lịch dùng theo mốc giờ) và thuốc đang dùng kèm trạng thái, **kể cả thuốc đã ngừng** (N9). Dòng có nhận định được đánh dấu và nối sang thẻ nhận định.
- **Xét nghiệm:** bảng theo thời gian, mới nhất trước, dòng ngoài ngưỡng có mũi tên.
- **Vi sinh:** bệnh phẩm, vi khuẩn, kháng sinh đồ; kháng sinh đang kê được tô nổi trong kháng sinh đồ (trả lời N3: vì sao kê thuốc này).
- **Diễn biến:** dòng thời gian các ghi chép, mới nhất trước.

### 3.9. Tab Thẩm định: điều hướng theo 8 mục ở thanh bên (chốt 22/11/2026, T104)

- **Chỉ ở tab Thẩm định**, nửa dưới thanh bên trái (chỗ thẻ thông tin người bệnh) đổi thành **danh sách 8 mục**: Tổng quan, rồi 7 yếu tố. Các tab khác vẫn giữ thẻ người bệnh. Không thêm dải người bệnh thu gọn: dược sĩ xem chỉ số ở tab Hồ sơ hoặc Y lệnh (một cú bấm); tách đôi màn hình là tính năng sau.
- **Mỗi mục** có số thứ tự, tên, biểu tượng và màu trạng thái (Có vấn đề / Thiếu dữ liệu / Đạt / Chưa có luật), và số nhận định cần chú ý. Mục có nhận định Nghiêm trọng được tô đỏ. Cuối danh sách là "N luật đã chạy".
- **Mục đang mở nằm trên URL** (`?yt=tong_quan|1..7`, mặc định Tổng quan), nên tải lại hay gửi liên kết vẫn đúng chỗ.
- **Tổng quan:** dải trạng thái AI, mọi nhận định cần chú ý sắp theo mức độ (mỗi thẻ có nút đi tới mục của nó), bảng các mục đạt.
- **Từng yếu tố:** chỉ nhận định và mục đạt của yếu tố đó. Yếu tố 4 thêm bảng tương tác ở cuối. Yếu tố chưa có luật hiện "Chưa có luật", không bao giờ ghi "đạt".
- Bỏ dải 7 ô "Bảy yếu tố thẩm định" trong vùng nội dung, vì thanh bên đã đảm nhận vai trò đó.
- Thanh bên thu gọn (56 px): danh sách chỉ còn số và biểu tượng, rê chuột thì hiện tên.

## 4. Các trạng thái phải thiết kế

| Trạng thái | Hiển thị |
| :--- | :--- |
| Đang chạy | Danh sách bước với dấu tích lần lượt (P8); không màn hình trắng |
| Ca lỗi dữ liệu | Thông báo nêu tên tệp và lý do; các ca khác vẫn mở được |
| Không có LLM | Dải ghi `Đang chạy không có bước AI: bảng nhận định do bộ luật sinh ra`; khung hỏi thêm ghi rõ chưa dùng được |
| Truy xuất chạy chế độ từ khoá | Dải ghi `Tra nguồn bằng từ khoá (dịch vụ nhúng không phản hồi)` |
| Nhận định AI chưa kiểm chứng | Viền đứt, nhãn `AI, chưa kiểm chứng`, đặt **dưới** mọi nhận định đã kiểm chứng |
| Hàng đợi rỗng | `Không có y lệnh chờ thẩm định` |
| Phản hồi không ghi được | Báo lỗi tại chỗ, giữ nguyên nội dung đã nhập |

## 5. Ngôn ngữ, số và thời gian

- Kết luận: `Đạt` · `Cần xem` · `Không đủ dữ liệu` · `Ngoài HDSD / phác đồ`. Mức độ: `Nghiêm trọng` · `Cần lưu ý`.
- Số: dấu phẩy thập phân; CrCl, eGFR, BMI một số lẻ; BSA hai số lẻ; luôn kèm đơn vị.
- Thời điểm: `10/11/2026 05:30`; nơi cần so sánh thêm khoảng cách (`3 ngày trước`).
- Câu ngắn, bắt đầu bằng sự việc: `CrCl 16,0 mL/phút: cần xem xét chỉnh liều`. Không dùng câu khẳng định thay dược sĩ (`phải giảm liều`); dùng `cần xem xét`, `đề nghị đối chiếu`.
- Bảng nhãn tiếng Việt cho mọi mã nội bộ nằm ở một chỗ (`app/ui/labels.py`); mã chưa có nhãn thì hiện mã và test báo thiếu.

## 6. Tổ chức code giao diện

```text
app/ui/
├─ streamlit_app.py        # chỉ lắp bố cục, không có logic
├─ services.py             # ReviewService, AskService (Protocol) + bản cài cho hôm nay
├─ state.py                # trạng thái phiên: ca đang chọn, kết quả đã tính, hội thoại, phản hồi
├─ labels.py               # mọi nhãn tiếng Việt
├─ view_model.py           # hàm thuần chuẩn bị dữ liệu hiển thị (không import streamlit)
└─ components/
   ├─ queue.py  case_header.py  summary.py  findings.py
   ├─ evidence_dialog.py  feedback.py  chat.py  detail_tabs.py  status.py
```

- **Giao diện chỉ nói chuyện với `services.py`.** Hôm nay `ReviewService` gọi `app.pipeline.run_case`; khi đồ thị (plan 1.1 mục 7) xong thì đổi bản cài, không sửa thành phần nào.
- `AskService.ask(ca, cau_hoi, lich_su) -> TraLoi` với `TraLoi{noi_dung, trich_dan[], cong_cu_da_goi[], trang_thai}`. Trước khi backend hỏi thêm xong, bản cài tạm trả `trang_thai="chua_san_sang"` và giao diện hiện đúng trạng thái đó; **không giả câu trả lời**.
- Mỗi thành phần là một hàm `render_*(…)` nhận dữ liệu đã chuẩn bị từ `view_model`; mọi tính toán hiển thị nằm ở `view_model` để test được không cần trình duyệt.
- Kết quả thẩm định của một ca được giữ trong trạng thái phiên; bấm nút phản hồi hay gõ câu hỏi **không** chạy lại cả đường chạy.

## 7. Công nghệ

**Người dùng chốt 16/11: giao diện chính là một bản web thật; bản Streamlit giữ lại để tham khảo và làm đường lui.**

- **Bản web chính:** Vite + React + TypeScript ở `web/`, React thuần và CSS thuần, không thêm thư viện giao diện. Lấy dữ liệu qua API FastAPI ở `app/api/`, hợp đồng dữ liệu ở `plan/api-hop-dong-v1.md`. Backend chuẩn bị sẵn mọi chuỗi hiển thị (dùng lại `app/ui/view_model.py` và `app/ui/labels.py`), web không tự dịch mã hay làm tròn số, nên hai giao diện luôn hiện cùng một câu chữ.
- **Bản đóng gói:** `npm run build` sinh `web/dist`, FastAPI phục vụ luôn ở cổng 8000; demo chỉ cần một tiến trình.
- **Bản Streamlit** (`app/ui/`, đã xong đợt 1): không phát triển thêm tính năng; dùng để đối chiếu hành vi và để demo nếu bản web trục trặc.
- Bản web làm được các điểm Streamlit không làm được: dải định danh dính khi cuộn, chọn ca bằng bàn phím, hộp thoại căn cứ trả tiêu điểm đúng chỗ, bố cục co giãn theo màn hình.

## 8. Tiêu chí nghiệm thu trải nghiệm

| # | Tiêu chí | Cách kiểm |
| :-: | :--- | :--- |
| U1 | Mở một ca: thấy trạng thái dị ứng, CrCl và số mục cần xem mà không cuộn (màn hình 1366 × 768) | Chụp màn hình 6 ca demo |
| U2 | Từ một nhận định tới nguyên văn đoạn nguồn: tối đa 2 lần bấm | Đếm bước |
| U3 | Không còn mã nội bộ trên màn hình | Test quét nhãn + soát tay |
| U4 | Ba trạng thái dị ứng phân biệt được khi in đen trắng | Chụp, chuyển thang xám |
| U5 | Bấm phản hồi không làm trang chạy lại đường chạy | Đo thời gian, xem số lần gọi |
| U6 | Ca thiếu dữ liệu không có chỗ nào ghi "đạt" cho yếu tố thiếu | DEMO-03 |
| U7 | Dược sĩ dùng thử lần đầu tìm được căn cứ của một nhận định mà không cần chỉ | Buổi dùng thử, 2–3 dược sĩ (sau demo) |

## 9. Thứ tự làm

| Đợt | Việc | Khi nào |
| :-: | :--- | :-: |
| 1 (T13) | Tách thành phần theo mục 6; bố cục mục 3; dải định danh; tóm tắt có xu hướng xét nghiệm; thẻ nhận định mới; phản hồi có lý do và trạng thái; hàng đợi sắp theo ưu tiên; thẻ chi tiết; khung hỏi thêm ở trạng thái "chưa sẵn sàng"; hộp thoại căn cứ cho dữ liệu ca và phép tính | 16–17/11 |
| 2 | Nối hộp thoại nguồn với kho đoạn trích; nhãn nguồn gốc `AI, đã kiểm chứng`; các bước chạy thật; nối khung hỏi thêm với đồ thị | 18/11, sau T04–T06, T12 |
| 3 | Chế độ nhanh cho ngoại trú (F4), mẫu phiếu tư vấn (F6), buổi dùng thử với dược sĩ | Tuần 4–5 |
