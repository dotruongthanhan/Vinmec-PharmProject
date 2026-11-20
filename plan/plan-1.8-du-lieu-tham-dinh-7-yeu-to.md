# Plan 1.8 – Dữ liệu thật cho thẩm định 7 yếu tố: từ điển thuốc, cào nguồn, luật từng yếu tố

Ngày lập: 18/11/2026. Người lập: Claude (vai trò viết plan, không viết code). Trạng thái: **bản nháp chờ người dùng duyệt**.

Plan này đứng **trước** plan 1.9 (Agentic RAG, trước đây đánh số 1.8). Người dùng chốt ngày 18/11: làm xong phần dữ liệu và luật của 7 yếu tố, ổn thoả rồi mới chuyển kiến trúc agent.

Liên quan: plan 1.3 (4 tầng xử lý, chuẩn hoá tên, gộp nguồn; plan này **kế thừa và chi tiết hoá**, không thay), plan 1.6 (nạp Supabase), plan 1.1 mục 5–6 (RAG, lớp luật), `data/kb_sources/README.md`, `docs/so-do-tham-dinh-y-lenh.md`, ghi chép khảo sát `D:\create\Khoa dược\Khảo sát\survay.md` (mục 3.0.2, 3.1.3, phần "OH chạy 5 test").

---

## 1. Vì sao cần plan này

### 1.1. Hiện trạng đã kiểm (18/11)

| # | Yếu tố | Luật đang có | Dữ liệu đang dựa vào | Vấn đề |
|:-:|:--|:--|:--|:--|
| 1 | Dị ứng, quá mẫn | `app/rules/allergy.py`: trùng hoạt chất, cùng nhóm, thiếu thông tin | `nhom_duoc_ly` **ghi tay trong từng tệp ca** | Dị ứng chéo chỉ so chuỗi tên nhóm; không có bảng dị ứng chéo |
| 2 | Trùng lặp | `duplicate.py`: chỉ trùng hoạt chất | `thanh_phan` trong tệp ca | **Không bắt trùng nhóm điều trị** (2 PPI, 2 NSAID, 2 thuốc chống đông) |
| 3 | Chỉ định, liều, đường dùng | `antibiotic.py` – thực ra là đối chiếu kháng sinh với kháng sinh đồ | Vi sinh | **Gắn nhầm yếu tố**; không có liều tối đa, đường dùng, chỉ định |
| 4 | Tương tác | **Không có** | Bảng `tri_thuc.tuong_tac_sang_loc` (235k cặp DDInter, chỉ tên + mức) đã nạp nhưng không ai đọc | Ma trận giao diện toàn ô "Chưa kiểm" |
| 5 | Độc tính | **Không có** | Không có | Trống |
| 6 | Cơ địa, xét nghiệm | `renal_dose.py` + `app/calc` (CG, CKD-EPI 2021, BMI, BSA, IBW, AdjBW) | `quy_tac_lieu_than.json`: **1 thuốc (meropenem)** | Không có gan, không có ngưỡng xét nghiệm, không có thuốc–bệnh |
| 7 | Lịch dùng, yếu tố khác | `schedule.py` | Lịch dùng trong ca | Chạy được; thiếu thời gian dùng, kháng sinh hạn chế, điều kiện BHYT |

Thêm:

- **Không có từ điển thuốc chung.** Mỗi tệp ca tự khai `danh_muc_thuoc` (56 tên, 45 hoạt chất, 8 phối hợp trên 69 tệp). Một thuốc có nhiều cách viết ("Amoxicilin" / "Amoxicillin", "Insulin glargin" / "glargine"). Mã hoạt chất trong ca (`HC-CEFTRIAXONE`) **khác** mã trong kho tri thức (`ceftriaxone`). `data/kb/hoat_chat.json` chỉ có 54 hoạt chất.
- Thuốc không có trong danh mục (ví dụ "Natri clorid 0,9% 500 mL") thì mọi yếu tố đều "?": hệ thống không biết nó gồm hoạt chất gì.
- Kết luận: phần lớn nội dung thẩm định đang là **dữ liệu mock gắn sẵn trong ca**, không phải tra cứu.

### 1.2. Dược sĩ thật đang làm gì (khảo sát)

- Chuyển qua 5–6 công cụ: OH, EMR, MIMS, UpToDate (Lexicomp), Calculate / MDCalc, Excel. OH chạy sẵn 4–5 "test" dựa CSDL MIMS: lặp hoạt chất, tương tác, dị ứng, điều kiện chẩn đoán. **Dữ liệu liều của OH đã cũ**, nên dược sĩ tra thêm UpToDate, FDA, eMC.
- Tra hoạt chất theo **Thông tư 20** và mã BHYT của Bộ khi lập danh mục.
- Tính liều chủ yếu là **CrCl / eGFR** rồi tra bảng chỉnh liều.
- Đã thử trang tra tương tác (bản sao Lexicomp, chỉ quan sát hành vi, **không lấy dữ liệu**):
  - Nhập tên chung, kể cả thuốc phối hợp như một mục ("Amoxicillin and Clavulanate"). Gõ biệt dược "Augmentin" không ra.
  - Bấm phân tích thì hệ thống tự tách phối hợp thành thành phần và đối chiếu **theo nhóm** ("Vitamin K Antagonists / Penicillins").
  - Mỗi cặp có: mức rủi ro X/D/C/B/A, mức nặng, độ tin cậy, xử trí, thành viên nhóm và ngoại lệ, bàn luận, tài liệu.
  - Hệ thống của mình phải làm được đúng chuỗi đó: **tên thuốc → thành phần → hoạt chất → nhóm → tra cặp**.

---

## 2. Nguyên tắc (giữ nguyên các bất biến của dự án)

1. **Luật và công thức chạy bằng code; LLM không tính, không tự tạo luật.** LLM chỉ được dùng ở bước **rút nháp** từ văn bản nguồn. Mọi dòng nháp phải kèm trích nguyên văn và qua kiểm bằng code (mục 4.3).
2. **Bốn trạng thái kết luận** cho mọi yếu tố: `dat` · `can_xem` · `khong_du_du_lieu` · `ngoai_hdsd`. Không có dữ liệu để tra thì là `khong_du_du_lieu` (giao diện: "Chưa kiểm" / "Thiếu dữ liệu"), **không bao giờ là "đạt"**.
3. **Tầng tin cậy nguồn:**
   - Tầng 1: Bộ Y tế (QĐ 5948, Thông tư 20 / 37, Cục Quản lý Dược).
   - Tầng 2: Dược thư Quốc gia.
   - Tầng 3: nhãn FDA (openFDA, DailyMed), tờ hướng dẫn sử dụng được Cục Quản lý Dược công bố.
   - Tầng 4: DDInter, RxNav (sàng lọc, ánh xạ).
   - Tầng thấp không được hạ hay xoá kết luận của tầng cao (plan 1.3 mục 7.2).
4. **Không sao chép UpToDate, Lexicomp, MIMS, Micromedex** (kể cả bản sao trên doctorabad). Chỉ học hành vi giao diện.
5. **Dữ liệu cấu trúc có trạng thái** `nhap | sang_loc | da_duyet`. Dòng chưa duyệt vẫn dùng được, nhưng giao diện ghi rõ "sàng lọc / chưa dược sĩ duyệt".
6. **Mỗi lần cào là tầng 0 bất biến**:
   - Lưu phản hồi gốc, có `manifest.json` (nguồn, URL, ngày lấy, SHA-256, giấy phép).
   - Tầng 1–2 là tệp đọc được bằng mắt.
   - Mỗi lệnh có báo cáo chạy với số vào / ra / bị loại và lý do.
7. **Cào lịch sự:**
   - Tối đa 1–2 yêu cầu/giây và có thể chạy tiếp sau khi dừng.
   - Lưu đệm phản hồi, thử lại có giãn cách.
   - User-Agent chung, **không ghi email hay tên người dùng**.
   - Không vượt qua đăng nhập hay CAPTCHA.
8. **Mỗi đợt review kỹ rồi mới sang đợt sau** (người dùng chốt 18/11). Cổng review ở mục 6.

---

## 3. Nguồn đã khảo sát (nhật ký tra cứu ngày 18/11)

Bảng dưới là **mọi nguồn đã xem**, giữ lại làm lịch sử. Danh sách **chốt dùng** nằm ở mục 3.1.

| Nguồn | Truy cập | Có gì | Dùng cho yếu tố | Giấy phép / lưu ý |
|:--|:--|:--|:-:|:--|
| **Cục Quản lý Dược – công bố số đăng ký** (`dichvucong.dav.gov.vn/congbothuoc`) | API JSON công khai `POST /api/services/app/soDangKy/GetAllPublicServerPaging`, **55.030 bản ghi**, phân trang | Tên thuốc, số đăng ký, `hoatChatChinh` (văn bản tự do, có muối, "tương đương"), hàm lượng, dạng bào chế, quy cách, công ty, `urlHuongDanSuDung` / `urlNhan` (tờ hướng dẫn sử dụng tiếng Việt, khi có) | Nền (tên thuốc VN → hoạt chất), 3 (dạng bào chế → đường dùng), căn cứ tiếng Việt | Dữ liệu công bố của cơ quan nhà nước; ghi nguồn. Trường đường dùng thường rỗng |
| **RxNav / RxNorm, RxClass** (NLM) | API REST miễn phí, không khoá (đã thử: `Augmentin` → amoxicillin + clavulanate; warfarin → ATC `B01AA`) | Tên Mỹ → thành phần (IN), mã `rxcui`, lớp **ATC** đến mức 4, lớp MoA/EPC | Nền (ATC, nhóm), 1, 2 | Công khai, ghi nguồn NLM. API tương tác của RxNav đã ngừng từ 01/2024, không dùng |
| **openFDA** | `drug/label`, `drug/ndc`, `drug/event`, `drug/enforcement`, `drug/shortages`; đã có 50 nhãn + 46 NDC | Văn bản nhãn đủ mục (chỉ định, liều, bảng liều, chống chỉ định, cảnh báo đóng khung, tương tác, nhóm đặc biệt, quá liều), `pharm_class_epc/moa` | 1–7 (căn cứ văn bản); 2 (nhóm có cấu trúc); 5 (FAERS chỉ là tín hiệu) | Phạm vi công cộng. Nhãn Mỹ, khác biệt dược VN |
| **DDInter 2.0** (`ddinter2.scbdd.com`) | CSV (5 cột, đã tải) + **điểm JSON của trang**: `POST /server/interact-with/<id>/`, `-dis/`, `-food/`, `-multi/`; trang cặp `/server/interact/<n>/`. Không có `robots.txt` | 2.568 thuốc (ATC, mô tả, CAS); thuốc–thuốc có **cơ chế**; trang cặp có **hậu quả, xử trí, tài liệu, thuốc thay thế cùng ATC, gợi ý CYP**; **thuốc–bệnh**; **thuốc–thức ăn** (mô tả, xử trí, cơ chế) | 4, 6 (thuốc–bệnh), 5 | **CC BY-NC-SA 4.0, phi thương mại**: dùng cho bản thử học thuật; vận hành ở viện phải xin phép |
| **QĐ 5948/QĐ-BYT** (30/12/2021) | Bản gốc phải đăng nhập (luatvietnam); cổng `tuongtacthuoc.ehealth.gov.vn` **vẫn không kết nối được ngày 18/11** | 25 cặp chống chỉ định (11 tuyệt đối, 14 tương đối, theo bài báo; cần đối chiếu bản gốc) | 4 (tầng 1) | Nhờ Khoa Dược cấp bản chính thức |
| **Thông tư 20/2022/TT-BYT** (Phụ lục I), hợp nhất 15/VBHN-BYT, TT 37/2024 | Văn bản công khai, PDF / HTML | Hoạt chất, **đường dùng / dạng dùng**, hạng bệnh viện, tỷ lệ và **điều kiện thanh toán** (ghi chú chỉ định) | Nền, 3, 7 | Văn bản quy phạm, dùng được |
| Danh mục thuốc của viện (mã HIS, tên, hoạt chất, đường dùng) | Chỉ Khoa Dược có | Đúng tên thuốc trong y lệnh thật | Nền | **Câu hỏi Q10**; chưa có thì dùng danh mục giả lập dựng từ nguồn Cục Quản lý Dược |
| LiverTox, LactMed (NCBI Bookshelf) | Công khai | Độc gan; thai kỳ, cho con bú | 5, 6 | Phạm vi công cộng |
| Bảng chất nền / chất ức chế / chất cảm ứng CYP của FDA | Trang FDA công khai | Phân loại CYP3A4, 2C9, 2D6… | 4 (cơ chế), 5 | Công khai |
| Công thức (MDCalc) | **Không có API công khai**. Người dùng chốt 19/11: lấy công thức theo trang MDCalc, người dùng tự lấy và báo lại | — | 3, 6 | Tự cài; kiểm chéo MedCalc-Bench (CC BY-SA, **có hơn 20 lỗi đã được chỉ ra**), gói R `egfr` (MIT) |
| doctorabad (bản sao Lexicomp) | — | — | — | **Không dùng dữ liệu**, chỉ học hành vi (mục 1.2) |

### 3.1. Nguồn dữ liệu chốt (nhóm chốt ngày 18/11)

Tiêu chí:
- (a) Dược sĩ nhận ra và tin nguồn đó.
- (b) Truy lại được câu gốc để làm căn cứ.
- (c) Thật sự cần cho ít nhất một yếu tố.

Bản quyền: nhóm chấp nhận dùng cho bản thử. Về sau, nếu dự án được duyệt, viện sẽ nạp tài liệu của Bệnh viện X.

Mỗi nguồn có một trong ba vai trò:
- **Căn cứ:** hiện cho dược sĩ, kèm trích dẫn.
- **Sàng lọc:** hiện kèm nhãn "cần đối chiếu".
- **Ánh xạ:** chỉ dùng bên trong để nối tên và mã, không hiện cho dược sĩ.

#### A. Nguồn dùng ngay

| # | Nguồn | Tầng | Vai trò | Đóng góp | Yếu tố | Tiến độ (19/11) |
|:-:|:--|:-:|:--|:--|:-:|:--|
| 1 | **QĐ 5948/QĐ-BYT** – danh mục tương tác chống chỉ định | 1 | Căn cứ | 25 cặp (cần đối chiếu bản gốc). Cặp nào có ở đây thì kết luận "chống chỉ định theo Bộ Y tế", đè lên mọi mức sàng lọc | 4 | ❌ Không có bản công khai (chỉ luatvietnam, cần đăng nhập) – cần người trong nhóm tải |
| 2 | **Thông tư 20/2022/TT-BYT Phụ lục I** + hợp nhất **15/VBHN-BYT** + **TT 37/2024** | 1 | Căn cứ + ánh xạ | **Danh sách hoạt chất chuẩn tiếng Việt** (xương sống của từ điển), **đường dùng / dạng dùng** theo từng hoạt chất, nhóm tác dụng, hạng bệnh viện, điều kiện và tỷ lệ thanh toán (nguyên văn) | Nền, 2, 3, 7 | ⚠️ VBHN 15 (chứa Phụ lục I) là PDF ảnh quét, cần OCR; TT 20 gốc và phụ lục TT 37 chưa lấy được (cần đăng nhập) |
| 3 | **QĐ 5631/QĐ-BYT** (31/12/2020) – hướng dẫn quản lý sử dụng kháng sinh trong bệnh viện | 1 | Căn cứ | **Thay cho quy định nội bộ của viện** (nhóm không được cấp): phân nhóm kháng sinh phải phê duyệt trước / cần giám sát | 7 | ⚠️ Bản sao thứ cấp chưa ký (ĐH Duy Tân); Phụ lục 2 chữ sạch, tách được |
| 4 | **Cục Quản lý Dược** – công bố số đăng ký (+ tờ hướng dẫn sử dụng tiếng Việt khi có) | 1 | Ánh xạ + căn cứ | 55.030 thuốc lưu hành: tên thuốc → thành phần, hàm lượng, dạng bào chế. **Thay cho danh mục thuốc của viện** | Nền, 3 | ✅ Tải đủ 55.030 (T50); tách + ánh xạ xong; độ phủ 65,7% → T52 đang nâng; PDF tờ hướng dẫn chưa tải |
| 5 | **openFDA** – `drug/label`, `drug/ndc` | 3 | Căn cứ chính | Chỉ định, liều, bảng liều thận / gan, chống chỉ định, cảnh báo đóng khung, tương tác, nhóm đặc biệt; nhóm dược lý. Đã xin phép | 1, 3, 4, 5, 6 | ⚠️ 50 nhãn + 50 NDC (16/11), đã cắt 3.730 đoạn RAG; **chưa** mở rộng theo trục 1.219 hoạt chất; khoá nhãn chưa nối trục (mục 3.2.7) |
| 6 | **LiverTox** (NCBI Bookshelf) | 3 | Căn cứ | Phía **thuốc**: thuốc nào gây độc gan và mức khả năng (A–E). Bổ sung cho công thức Child-Pugh (phía **người bệnh**: gan đang suy mức nào) | 5, 6 | ✅ Đã tải đủ. **Giảm tải (19/11):** trước demo không tách; sau demo chỉ dùng bảng Likelihood Score (một cột A–E theo hoạt chất), chưa tách chuyên luận |
| 7 | **LactMed** (NCBI Bookshelf) | 3 | Căn cứ | An toàn khi cho con bú theo hoạt chất | 6 | ✅ Đã tải đủ. **Hoãn tới sau demo (19/11):** chỉ dùng khi ca có cơ địa cho con bú; nhãn FDA mục 8.2 tạm thay |
| 8 | **DDInter 2.0** (cào đủ trường) | 4 | Sàng lọc | Mọi cặp tương tác (cơ chế, hậu quả, xử trí, tài liệu, thuốc thay thế), thuốc–bệnh, thuốc–thức ăn, mã ATC | 4, 6 | ✅ Cấp thuốc đủ 1.971 + 860 trang cặp ưu tiên (T51); ⏳ ~25k cặp một bên, ~235k toàn bộ; 🔄 bảng gộp ở T55 |
| 9 | **Công thức theo MDCalc** (người dùng chốt 19/11: nguồn công thức **chỉ lấy trên MDCalc**; Cockcroft-Gault, CKD-EPI 2021, Child-Pugh, BMI, BSA, IBW, AdjBW, QTc…) | — | Căn cứ (tự tính) | Hiện từng bước tính, trích trang MDCalc | 3, 6 | ⏳ **Chờ người dùng lấy công thức từ MDCalc** và báo lại danh sách; code hiện có CG, CKD-EPI 2021, BMI, BSA, IBW, AdjBW sẽ đối chiếu lại theo MDCalc |
| 10 | **RxNav / RxClass** (NLM) | — | Ánh xạ | Cầu nối tên Mỹ ↔ hoạt chất (`rxcui`), mã ATC | Nền, 1, 2 | ✅ 5.195 tên tra + danh sách 18.406 IN/PIN (T50, T52) |

#### B. Nguồn nên nạp khi có bản

| Nguồn | Đóng góp | Ghi chú | Tiến độ (19/11) |
|:--|:--|:--|:--|
| **Dược thư Quốc gia Việt Nam** | Chuyên luận tiếng Việt theo hoạt chất: chỉ định, chống chỉ định, thận trọng, liều (cả liều suy thận, trẻ em), tương tác, quá liều. **Có các hoạt chất không lưu hành ở Mỹ** (ví dụ cefoperazon + sulbactam). Là nguồn tầng 2, đứng trên nhãn FDA. Chính tả hoạt chất tiếng Việt chuẩn | **Không bắt buộc để chạy**, nhưng là nguồn bù tốt nhất cho chỗ trống của nhãn FDA (mục 3.2). Ưu tiên cao khi có bản PDF | ⏳ Chưa có |
| **Tóm tắt đặc tính sản phẩm của EMA / eMC (Anh)** | Nhãn được cơ quan quản lý châu Âu duyệt, **đồng cấp với nhãn FDA**. Dược sĩ đang tra eMC (khảo sát) | Đề xuất làm nguồn bù đồng cấp khi thuốc không có nhãn FDA. Cần nhóm duyệt | ⏳ Chưa có |
| Tài liệu Bệnh viện X (phác đồ, danh mục, quy định) | Thay dần nguồn 3 và 4 khi dự án được duyệt | Không có trong giai đoạn thử | ⏳ Chưa có |

#### C. Bỏ

| Nguồn | Lý do |
|:--|:--|
| openFDA `drug/event` (FAERS) | Báo cáo tự nguyện, không chứng minh nguyên nhân, dễ hiểu sai |
| openFDA `drug/enforcement`, `drug/shortages` | Thị trường Mỹ, không liên quan y lệnh |
| Bảng CYP của FDA | DDInter đã có cơ chế cho từng cặp |
| MedCalc-Bench, gói R `egfr` | Không phải nguồn dữ liệu, chỉ dùng trong test để kiểm chéo công thức |
| Danh mục thuốc và quy định nội bộ của viện | Nhóm không được cấp; thay bằng nguồn 2, 3, 4 |
| doctorabad / Lexicomp, UpToDate, MIMS, Micromedex | Không lấy dữ liệu |
| `tuongtacthuoc.ehealth.gov.vn` | Không kết nối được; dùng văn bản QĐ 5948 |

#### D. Độ phủ theo yếu tố

| Yếu tố | Nguồn căn cứ | Nguồn sàng lọc / ánh xạ | Phần cần dược sĩ duyệt |
|:-:|:--|:--|:--|
| 1 Dị ứng | Nhãn FDA (chống chỉ định) | Cục Quản lý Dược, TT 20, RxClass (nhóm) | Bảng dị ứng chéo |
| 2 Trùng lặp | TT 20 (nhóm tác dụng) | Cục Quản lý Dược, RxClass (ATC) | Bảng nhóm trùng |
| 3 Liều, đường dùng, chỉ định | Nhãn FDA, TT 20 (đường dùng), tờ hướng dẫn của Cục Quản lý Dược, công thức | — | Liều tối đa |
| 4 Tương tác | **QĐ 5948**, nhãn FDA | DDInter | Cặp Major xuất hiện trong ca |
| 5 Độc tính | Nhãn FDA (cảnh báo đóng khung), **LiverTox** | — | Danh sách độc thận, kéo dài QT |
| 6 Cơ địa, xét nghiệm | Nhãn FDA (bảng thận / gan), **LactMed**, LiverTox, công thức | DDInter (thuốc–bệnh) | Bảng liều thận, ngưỡng xét nghiệm |
| 7 Lịch dùng, bất hợp lý | **QĐ 5631**, TT 20 (điều kiện thanh toán), nhãn (khoảng cách liều) | — | — |

### 3.2. Đồng bộ dữ liệu giữa các nguồn (phần khó nhất)

Mỗi nguồn gắn ở một **cấp** khác nhau, nên không nối thẳng được với nhau:

| Nguồn | Cấp gắn tự nhiên | Ví dụ |
|:--|:--|:--|
| Cục Quản lý Dược | **Chế phẩm** (tên thuốc + hàm lượng + dạng) | "Ceftriaxon Panpharma 1 g, bột pha tiêm" |
| TT 20 | **Hoạt chất + đường dùng** (tiếng Việt) | "Ceftriaxon – tiêm" |
| Nhãn FDA | **Hoạt chất (hoặc phối hợp) + đường dùng + nhà sản xuất** (Mỹ) | "CEFTRIAXONE for injection" |
| DDInter, LiverTox, LactMed, RxNorm | **Hoạt chất** (tên quốc tế) | "Ceftriaxone" |
| QĐ 5948 | **Hoạt chất hoặc nhóm** | "Ceftriaxon – các thuốc chứa calci (đường tĩnh mạch)" |

#### 3.2.1. Một trục chung: hoạt chất, không phải tên thuốc

- Thực thể trung tâm là **`hoat_chat`** (khoá INN). Hai trục phụ là **`hoat_chat + duong_dung`** (cho liều, dạng dùng) và **`thuoc`** (chế phẩm, cho y lệnh).
- Mỗi nguồn nối vào trục qua **bảng ánh xạ có bằng chứng**: `nguon`, `ma_ban_ghi_nguon`, `hoat_chat_id`, `cach_khop` (`ma_chuan` · `ten_chinh_xac` · `bo_muoi` · `rxnav` · `tay`), `do_tin_cay`, `nguoi_duyet`.
- Không có cột "tên" nào được dùng để nối khi chưa qua bảng này.

#### 3.2.2. Chống "bản ghi ma"

Bản ghi ma là thực thể chỉ sinh ra do ghép nối, không nguồn nào thật sự nói về nó. Ví dụ: một chế phẩm "có" hoạt chất do tách sai, hay một cặp tương tác giữa hai tên không tồn tại. Quy tắc chặn:

1. **Một thực thể chỉ được tồn tại khi có nguồn neo khẳng định nó:**
   - Chế phẩm: Cục Quản lý Dược (hoặc dữ liệu ca giả lập, có đánh dấu).
   - Hoạt chất: TT 20, RxNorm hoặc Dược thư.
   - Tương tác: QĐ 5948, nhãn hoặc DDInter.
   - Không nguồn nào được **tạo** thực thể ở cấp khác cấp của mình, chỉ được **gắn** vào thực thể đã có.
2. **Mỗi dòng tầng 2 có `nguon_ban_ghi_ids`** trỏ về dòng tầng 0. Kiểm bằng code: 0 dòng mồ côi.
3. **Không ghép mờ tự động.** Khớp gần đúng (khoảng cách chuỗi) chỉ đưa vào hàng đợi `cho_duyet`, không ghi vào bảng ánh xạ.
4. **Không suy ngược.** Ví dụ: không suy chế phẩm VN có trong DDInter vì hoạt chất của nó có trong DDInter. Kết quả tra luôn nói rõ dữ kiện ở cấp hoạt chất.

#### 3.2.3. Ma trận độ phủ

- Sau mỗi lần dựng, sinh `data/kb_reports/do_phu.csv`: một dòng mỗi hoạt chất, một cột mỗi nguồn × loại dữ kiện (có nhãn? có bảng thận? có trong DDInter? có LiverTox? có trong TT 20?).
- Giao diện quản trị và báo cáo review đọc từ đây. **Ô trống là chỗ cần bù**, không phải "an toàn".

#### 3.2.4. Bù chỗ trống bằng nguồn uy tín ngang hoặc cao hơn

Khi thuốc A có hoạt chất A1 mà nguồn chính không có A1, tra **nguồn thay thế theo thứ tự đã định trước cho từng loại dữ kiện**. Không tra tự do.

| Loại dữ kiện | Thứ tự nguồn (dừng ở nguồn đầu tiên có) | Điều kiện được dùng nguồn thay thế |
|:--|:--|:--|
| Tên → thành phần | Cục Quản lý Dược → TT 20 → RxNorm → Dược thư | Cùng hoạt chất sau chuẩn hoá muối |
| Liều, chỉnh liều thận / gan | Dược thư → nhãn FDA → tóm tắt đặc tính sản phẩm EMA / eMC → tờ hướng dẫn của Cục Quản lý Dược | **Phải cùng hoạt chất + cùng đường dùng + cùng dạng muối nếu muối đổi liều.** Không lấy liều thuốc uống cho thuốc tiêm. Không lấy liều của một thành phần cho thuốc phối hợp |
| Chống chỉ định, cảnh báo, độc tính | Dược thư → nhãn FDA → EMA / eMC → LiverTox (riêng độc gan) | Cùng hoạt chất. Khác đường dùng thì ghi rõ |
| Tương tác | QĐ 5948 → nhãn FDA → DDInter | Theo **từng thành phần** của thuốc phối hợp (được phép, vì tương tác gắn với hoạt chất) |
| Đường dùng hợp lệ | TT 20 → dạng bào chế của Cục Quản lý Dược → `route` của nhãn | — |
| Cho con bú | LactMed → mục nhãn | — |

Ghi nhận khi bù:

- Mỗi trường lưu **`nguon_truong`** (nguồn của chính trường đó, không chỉ của bản ghi).
- Giao diện hiện rõ khi căn cứ đến từ nguồn thay thế, ví dụ: "Liều lấy từ tóm tắt đặc tính sản phẩm EMA vì nhãn FDA không có hoạt chất này".
- Hết nguồn thì kết luận `khong_du_du_lieu`. **Không được bù bằng LLM hay bằng nguồn tầng thấp hơn** cho dữ kiện liều.

#### 3.2.5. Hai nguồn cùng có nhưng lệch nhau

- Không gộp, không lấy trung bình. Giữ cả hai, dòng chính theo tầng cao hơn, đánh `xung_dot: true` (plan 1.3 mục 7.2).
- Giao diện hiện cả hai kèm nguồn. Đưa vào danh sách dược sĩ rà.

#### 3.2.6. Kiểm đồng bộ ở cổng review của mỗi đợt

- [L] 0 dòng mồ côi.
- [L] 0 hoạt chất trong ca không có trong trục.
- [L] Mọi trường bù có `nguon_truong`.
- [K] Lấy 20 dòng có bù, mở nguồn thay thế bằng trình duyệt và xác nhận đúng hoạt chất, đúng đường dùng.
- [K] Lấy 20 chế phẩm phối hợp, kiểm từng thành phần.


#### 3.2.7. Kết quả kiểm đồng bộ lần đầu (Claude, 19/11)

Kiểm chéo 48 hoạt chất có trong ca giả lập qua 5 nguồn: Cục Quản lý Dược (số chế phẩm), RxNorm (`rxcui`), ATC, DDInter (`ddinter_id`), nhãn openFDA. Kết quả lần đầu: 36 đủ, 12 thiếu. **Sau khi sửa cách kiểm nhãn FDA: 44 đủ nhãn; thiếu thật ở 4 hoạt chất (cefoperazone, sulbactam, gabapentin, penicillin G)**, cộng các lệch về DDInter / ATC ở bảng dưới.

| Loại lệch | Hoạt chất | Bản chất | Xử lý |
|:--|:--|:--|:--|
| ~~Có dữ liệu nhưng chưa nối~~ **(kiểm nhầm, đã sửa 19/11)** | amoxicillin, clavulanic acid, piperacillin, tazobactam, sulfamethoxazole, trimethoprim, metoprolol, valproic acid | Lần kiểm đầu dò theo **tên tệp** nhãn (`amoxicillin_and_clavulanate_potassium.json`…) nên báo thiếu. Kiểm lại: đoạn RAG của nhãn đã gắn `hoat_chat_ids` theo **từng thành phần**, và 53/53 khoá đều có trên trục. **Không phải lỗi đồng bộ** | Ma trận độ phủ (D0.8) phải đọc liên kết từ `hoat_chat_ids` của đoạn, không đọc tên tệp |
| **Nguồn thật sự không có** | cefoperazone, sulbactam (không lưu hành ở Mỹ: không có nhãn FDA; sulbactam không có trong DDInter) | Đúng tình huống "bù nguồn" ở mục 3.2.4 | Bù bằng Dược thư / EMA / tờ hướng dẫn của Cục Quản lý Dược khi có; trước đó kết luận "thiếu dữ liệu" |
| **Chưa tải** | gabapentin, penicillin G: không có trong 50 nhãn tạm | Danh mục nhãn cũ chỉ 50 hoạt chất | Tải thêm nhãn theo trục (sau D0, cần mạng) |
| **Xung đột ánh xạ** | penicillin G ↔ DDInter (3 bản ghi benzylpenicillin: gốc, kali, natri) | Một-nhiều, nên bộ phân giải không tự nối | Quy tắc: bản ghi không muối là gốc; cần duyệt |
| **Thiếu ATC** | clavulanic acid, valproic acid | RxClass không trả ATC đơn chất (clavulanic chỉ có trong mã phối hợp J01CR02) | Lấy ATC từ DDInter hoặc bảng tay có duyệt |

**Nguyên tắc rút ra:**
- **Hoạt chất thừa** (có trong nguồn, không có thuốc nào dùng) không gây hại: chỉ là dữ liệu chưa dùng.
- **Hai kiểu thiếu gây hại**, vì có thể bị hiểu nhầm thành "an toàn":
  - (1) **Thuốc không ra được hoạt chất.**
  - (2) **Hoạt chất không có dữ liệu ở một nguồn.**
- Cả hai kiểu đều phải ra "thiếu dữ liệu", không bao giờ ra "đạt" hay "không phát hiện". Bộ phân giải (`khong_nhan_dien`) và luật yếu tố 4 (`khong_phat_hien` chỉ khi DDInter đã cào đủ cho **cả hai** hoạt chất) đã bám nguyên tắc này. Các luật D2–D7 phải bám tương tự.

---

## 4. Kiến trúc dữ liệu

### 4.1. Từ điển thuốc (nền cho cả 7 yếu tố)

Chuỗi tra cứu bắt buộc, giống hành vi Lexicomp:

```text
ten trong y lệnh ("Augmentin 1g", "Ceftriaxon 1 g", "Natri clorid 0,9% 500 mL")
   │  bộ phân giải tên (resolver)
   ▼
thuoc (chế phẩm)  ── thuoc_thanh_phan ──►  hoat_chat (INN, khoá nội bộ)
                                                │
                ┌───────────────┬──────────────┼──────────────┬───────────────┐
                ▼               ▼              ▼              ▼               ▼
         nhom (ATC L3–L5)   rxcui (RxNorm)  ddinter_id   openfda set_id   dong_nghia (VN, muối, viết tắt, biệt dược)
```

Bảng ở lược đồ `tri_thuc` (bổ sung, không phá bảng hiện có):

| Bảng | Trường chính | Ghi chú |
|:--|:--|:--|
| `hoat_chat` (đã có, mở rộng) | `hoat_chat_id` (INN snake_case), `ten_inn`, `ten_viet`, `rxcui`, `ma_atc[]`, `ddinter_id`, `nhom_duoc_ly`, `loai` (`thuoc` · `dich_truyen_dien_giai` · `vitamin_khoang` · `tpcn` · `vaccin_sinh_pham`), `trang_thai` | Mỗi hoạt chất có thể nhiều mã ATC |
| `dong_nghia` | `khoa_chuan_hoa` → `hoat_chat_id` hoặc `thuoc_id`, `loai` (`inn` · `viet` · `muoi` · `biet_duoc` · `viet_tat`), `nguon` | Plan 1.3 mục 5 |
| `thuoc` | `thuoc_id`, `ten_thuoc`, `so_dang_ky`, `ham_luong`, `dang_bao_che`, `duong_dung_suy_ra[]`, `nguon` (`dav` · `vien` · `gia_lap`), `url_hdsd` | Dựng từ Cục Quản lý Dược; về sau thay bằng danh mục viện |
| `thuoc_thanh_phan` | `thuoc_id`, `hoat_chat_id`, `ham_luong`, `don_vi`, `dang_muoi` | Phối hợp = nhiều dòng |
| `nhom_atc` | `ma_atc`, `ten`, `cap` (1–5) | Từ RxClass / DDInter |
| `nhom_dieu_tri_trung` | `nhom_id`, `ma_atc_tien_to[]`, `muc` (`trung_nhom` · `cung_co_che`), `ngoai_le[]`, `trang_thai` | Do dược sĩ duyệt; phục vụ yếu tố 2 |

**Bộ phân giải tên** (`app/kb/resolver` – mới) đi theo thứ tự sau; bước nào khớp thì dừng:

1. Khớp mã thuốc của y lệnh (`thuoc_id`) → `thuoc_thanh_phan`.
2. Khớp tên thuốc chuẩn hoá (bỏ hàm lượng, dạng, dấu, muối) với `dong_nghia`.
3. Tách tên phối hợp theo dấu `+`, `/`, "và" rồi khớp từng phần.
4. Không khớp thì trả `khong_nhan_dien` kèm lý do. Yếu tố liên quan ra `khong_du_du_lieu`, **không đoán**. Không dùng LLM ở đường thẩm định.

Đầu ra cho mỗi dòng y lệnh có dạng `{thuoc_id, thanh_phan:[{hoat_chat_id, ham_luong}], nhom_atc[], do_tin_cay, nguon_khop}`. Kết quả này được lưu kèm nhận định, để dược sĩ thấy hệ thống đã hiểu thuốc thành gì.

### 4.2. Bảng tri thức cho từng yếu tố

| Bảng | Yếu tố | Lược đồ tóm tắt |
|:--|:-:|:--|
| `tuong_tac` | 4 | Theo plan 1.3 mục 7.2. Thêm: `co_che_loai` (Antagonism…), `hau_qua`, `xu_tri`, `tai_lieu[]`, `thay_the_a[]`, `thay_the_b[]`, `ma_trang_nguon` |
| `tuong_tac_thuc_an` | 4 | `hoat_chat_id`, `thuc_an`, `muc_do`, `mo_ta`, `xu_tri`, `co_che`, `tai_lieu`, `nguon` |
| `tuong_tac_benh` | 6 | `hoat_chat_id`, `ten_benh`, `ma_icd10[]` (ánh xạ tay, có duyệt), `muc_do`, `mo_ta`, `tai_lieu`, `nguon` |
| `nhom_di_ung_cheo` | 1 | Plan 1.3 mục 7.4: nhóm ATC hoặc chuỗi bên R1 (beta-lactam), `muc` (`cung_nhom` · `nhom_lien_quan`), `trang_thai` |
| `quy_tac_lieu` | 3, 6 | Plan 1.3 mục 7.3 (thận, gan, tuổi, cân nặng) + `lieu_toi_da_lan`, `lieu_toi_da_ngay`, `lieu_theo_kg`, `khoang_cach_toi_thieu_gio` |
| `duong_dung_hop_le` | 3 | `hoat_chat_id` + `dang_bao_che` → `duong_dung[]`, `nguon` (nhãn, TT20, Cục Quản lý Dược) |
| `chi_dinh` | 3 | `hoat_chat_id`, `chi_dinh` (văn bản), `ma_icd10[]` (nháp, duyệt), `nguon`, `doan_trich_id` |
| `canh_bao_doc_tinh` | 5 | `hoat_chat_id`, `loai` (`hop_den` · `doc_than` · `doc_gan` · `keo_dai_qt` · `uc_che_tuy` · `khoang_dieu_tri_hep`), `dieu_kien`, `theo_doi` (xét nghiệm, nồng độ), `nguon`, `trich` |
| `nguong_xet_nghiem` | 6 | `hoat_chat_id` hoặc nhóm, `xet_nghiem` (K, INR, tiểu cầu, ALT…), `toan_tu`, `nguong`, `don_vi`, `khuyen_cao`, `nguon`, `trang_thai` |
| `quy_dinh_thanh_toan` | 7 | Từ TT 20 / 37: `hoat_chat_id`, `duong_dung`, `hang_bv`, `ty_le`, `dieu_kien` (nguyên văn) |
| `khang_sinh_han_che` | 7 | Phân nhóm kháng sinh phải phê duyệt trước / cần giám sát theo **QĐ 5631/QĐ-BYT** (nguyên văn phụ lục) |

Tất cả theo 4 tầng của plan 1.3: `data/kb_sources/<nguon>/` → `data/kb_staging/` → `data/kb_curated/` → Supabase `tri_thuc` (và tệp JSON cho chế độ tệp, vì đến demo ứng dụng vẫn đọc tệp; plan 1.6).

### 4.3. Rút nháp từ văn bản (dùng chung cho yếu tố 3, 5, 6)

Theo plan 1.3 mục 7.3, nhắc lại vì là chỗ dễ sai nhất:

1. Code lọc đoạn ứng viên bằng từ khoá (`creatinine clearance`, `Child-Pugh`, `maximum`, `not to exceed`, `boxed warning`, …).
2. LLM rút theo lược đồ JSON, **bắt buộc kèm `trich_nguyen_van`**.
3. Code kiểm:
   - Mọi số trong dòng nháp có mặt trong trích dẫn.
   - Trích dẫn là chuỗi con đúng nguyên văn của đoạn nguồn.
   - Đơn vị hợp lệ.
   - Các khoảng phủ kín, không chồng nhau.
   - Hỏng bất kỳ điểm nào thì loại, ghi lý do.
4. Dòng qua kiểm ở trạng thái `nhap`. Dược sĩ duyệt thì thành `da_duyet`.

---

## 5. Các đợt làm (mỗi đợt có cổng review; chưa qua cổng thì không sang đợt kế)

Ký hiệu nghiệm thu: **[L]** = lệnh chạy được, **[K]** = Claude kiểm độc lập (tự tính lại / so trang gốc), **[DS]** = cần dược sĩ.

### 5.0. Bảng tiến độ (cập nhật 19/11 tối)

Ký hiệu: ✅ xong và đã qua review · 🔄 đang làm · ⚠️ xong một phần · ⏳ chưa bắt đầu.

| Bước | Việc | Task | Tiến độ |
|:-:|:--|:-:|:--|
| D0.1 | Cào Cục Quản lý Dược | T50 | ✅ 55.030 bản ghi, 54.910 số đăng ký |
| D0.2 | Tách thành phần | T50 | ✅ 87,3% tách được; kiểm tay 50 mẫu, 0 khớp sai |
| D0.3 | RxNav / ATC, trục hoạt chất | T50 | ✅ 1.219 hoạt chất, 980 có ATC mức 4 |
| D0.3b | Nâng độ phủ (thêm "e", vitamin, dược liệu, ứng viên ngữ nghĩa offline, hàng duyệt) | T52 | ⚠️ fix-1 đạt: 36.099 → 39.230 (71,4%), 0 lùi; nhúng thật `gemini-embedding-2` + hiệu chuẩn xong (T62): 0 nhận sai chỉ ở ngưỡng 0,99 (6 tên) → không tự nhận, 2.788 tên vào hàng duyệt tay |
| D0.4 | Bảng chuyển mã `HC-…` → trục | T53 | ✅ 50/50 mã |
| D0.5 | Phân loại dịch truyền / dược liệu / vitamin | T52, T53 | ⚠️ Đã có loại `dich_truyen_dien_giai`, `duoc_lieu`; Oresol, Ringer lactat, Oxy chưa nhận diện |
| D0.6 | Bộ phân giải tên | T53 | ✅ 117/167 dòng ca phân giải, 47 không áp dụng, 3 chưa nhận diện; API HTTP tra thuốc để sau |
| D0.7 | Nối nhãn openFDA ↔ trục | — | ✅ Đã có sẵn qua `hoat_chat_ids` của đoạn RAG (53/53 khoá có trên trục); lần kiểm đầu báo nhầm |
| D0.8 | **Ma trận độ phủ đa nguồn** cho mọi hoạt chất (mục 3.2.3, 3.2.7) | T56 | ✅ `python -m app.kb.coverage report`; ca 42/48 đủ nguồn; toàn trục: nhãn FDA 53/1.255, DDInter 776, ATC 980 |
| D0.9 | Đẩy bộ tra cuối lên DB (AWS RDS) | T75 | ✅ 19/11: `tri_thuc.tra_cuu_*` (54.910 thuốc, 1.255 hoạt chất) khớp 100%; app đọc từ DB |
| D1.1 | Cào DDInter cấp thuốc | T51 | ✅ 1.971 thuốc, 0 lỗi |
| D1.2 | Chi tiết cặp ưu tiên | T51 | ✅ 27.936 trang (hai bên + một bên ưu tiên), 0 lỗi phân tích, lệch đếm / đối xứng 0; bảng dựng lại có 27.644 cặp kèm hậu quả, xử trí |
| D1.3 | Cào toàn bộ cặp | — | ⏳ ~235k trang, chạy nền nhiều ngày |
| D1.4 | Tương tác từ nhãn FDA | — | ⏳ |
| D1.5 | QĐ 5948 | T54 | ❌ Không có bản công khai; chờ nhóm tải (cần đăng nhập luatvietnam) |
| D1.6 | Gộp bảng tương tác | T55 | ✅ 291.876 cặp, mức cao nhất + cờ lệch |
| D1.7 | Luật yếu tố 4 | T55 | ✅ 66 ca: 0 cặp chưa kiểm; HS-024 amiodaron × digoxin nghiêm trọng |
| D1.8 | Nối ma trận giao diện (hợp đồng API v1.6) | T55 | ✅ Endpoint thật trả `ma_tran_tuong_tac`; toàn kho 1.254 test qua; chưa xem bằng mắt trên trình duyệt; T55-fix-4 ✅ bỏ 'Hậu quả: None', ngoặc lồng (1.262 test qua) |
| R01 | **Review tổng D0 + D1** | — | ✅ 19/11 sáng: backend 1.254 qua, web 293 qua, tsc, ruff; endpoint thật 3 ca; bất biến 'không phát hiện' 0 vi phạm |
| D2 | Trùng hoạt chất qua bộ phân giải + trùng nhóm điều trị theo ATC | T57 | ✅ API 66 ca: chỉ HS-014…017 trùng nhóm, đúng mức; Oxy/Ringer/Oresol → không đủ dữ liệu; 1.301 test qua; [DS] chờ duyệt bảng nhóm |
| D3 | Dị ứng, dị ứng chéo | T60, T63 | ✅ Dữ liệu (T60: 26 nhóm, 57 nguồn) + luật (T63): API 66 ca → 5 ca dị ứng đều báo, 3 ca chưa khai thác → không đủ dữ liệu; sửa bộ phân giải Cephalexin/Paracetamol; [DS] chờ duyệt bảng chéo |
| D4 | Thận, gan, xét nghiệm, thuốc–bệnh | T65, T65-T66-ht, T67, T67-T68-fix-1 | ✅ (chờ [DS]) **Dữ liệu**: thận 1 quy tắc duyệt + 17 chờ duyệt (CrCl phủ kín, 0 chồng / 0 hở), gan 24, xét nghiệm 15, thuốc–bệnh 300 cặp → ICD-10; 103/103 trích khớp nhãn. **Luật** đã nối engine (T69): DEMO-02 meropenem CrCl 16 `nghiem_trong`, HS-027/058 metformin eGFR < 30, thuốc–bệnh DDInter 7 ca. ⏸️ Child-Pugh: công thức đã cài (T73) nhưng ca chưa có cổ trướng, bệnh não gan, albumin |
| D5 | Đường dùng, liều tối đa | T66, T65-T66-ht, T68, T67-T68-fix-1 | ✅ (chờ [DS]) **Dữ liệu**: đường dùng 62 dòng / 37 hoạt chất, liều tối đa 40 dòng + 21 định nghĩa đối tượng. **Luật** đã nối: đủ 3 tình huống plan (levofloxacin uống kê tiêm `nghiem_trong`; HS-019 paracetamol 6.000 > 4.000 mg/ngày, xem được trên web; gentamicin chỉ có trần theo điều kiện + thiếu cân nặng → `khong_du_du_lieu` có `can_nang`). Kiểm chỉ định dời sang plan 1.9 |
| D6 | Độc tính | T70, T71, T71-fix-1 | ✅ (chờ [DS]) **Dữ liệu** (T70): độc thận 7, kéo dài QT 4, khoảng điều trị hẹp 5, LiverTox 38; 59/59 trích khớp. **Luật** đã nối: HS-028 methotrexat + ibuprofen `nghiem_trong`, HS-029 valproat ALT 280, 7 dòng chưa theo dõi nồng độ; gentamicin + vancomycin và 2 thuốc QT có ca tổng hợp trong test (66 ca không có) |
| D7 | Lịch dùng, kháng sinh quản lý, trường bắt buộc | T70, T72 | ✅ (chờ [DS]) **Dữ liệu**: QĐ 5631 (bản sao thứ cấp) Nhóm 1 phê duyệt trước 20, Nhóm 2 giám sát 12, 13 tên chưa ánh xạ. **Luật** đã nối: 7 kháng sinh Nhóm 1 chưa thấy hội chẩn (DEMO-02 meropenem…); thiếu trường bắt HS-040. Chưa có ngưỡng thời gian kháng sinh (chưa nguồn); ngoại lệ carbapenem (***) chưa mã hoá |
| T69 | Nối luật D4–D7 vào `engine.py` / `registry.py`, kháng sinh đồ → yếu tố 6 | T69 | ✅ API thật 66 ca: 0 lỗi luật, 0 "đạt" khi thiếu dữ liệu, đủ 7 yếu tố có luật; web 5173 (backend 8000 mới) HS-019 hiện "14 luật đã chạy", yếu tố 3 "Có vấn đề" vượt liều paracetamol. Gold đổi 3 dòng kháng sinh đồ (DEMO-04, HS-048, HS-051) sang yếu tố 6 |
| CT1 | Công thức đợt 1 (MDCalc làm danh mục, bài gốc làm nguồn) | T73 | ✅ Child-Pugh, QTc ×5, canxi hiệu chỉnh; 6 công thức cũ khớp MDCalc; danh mục `config/kb/cong_thuc.yaml` 14 mục. Chưa nối luật (ca thiếu albumin, canxi, QT, cổ trướng, não gan). Cào đầy đủ chờ MDCalc cho phép |
| DB1 | **Toàn bộ dữ liệu plan 1.8 lên AWS RDS; app chạy chỉ bằng DB** | T75–T78 | ✅ 19/11: D0 `tra_cuu_*`, D1 `ddinter_*` (tra theo cặp), D1–D7 bảng luật quan hệ (24 bảng, dựng lại == tệp), đoạn nguồn + vector, hồ sơ/y lệnh, phản hồi, hỏi đáp, kết quả thẩm định. Ẩn mọi thư mục dữ liệu: 66 ca 577 nhận định khớp 100%. Còn: metformin cần tự tính eGFR; bảng cũ plan 1.6 chưa dọn |

#### 5.0.1. Quy tắc chuyển đợt (người dùng chốt 19/11)

- Chỉ sang D2 khi **D0 và D1 xong hết** các bước làm được (trừ bước phụ thuộc bên ngoài: D0.9 cần đồng ý ghi DB, D1.3 chạy nền, D1.5 cần bản gốc QĐ 5948), **và** Claude đã làm thêm **một vòng review tổng** trên cả D0 + D1:
  - Chạy toàn bộ test web và backend.
  - Chạy thẩm định thật trên các ca demo.
  - Kiểm lại bất biến.
  - So mẫu với nguồn.
- Đạt thì Claude **tự sang đợt kế mà không cần hỏi** (người dùng cho phép, vì vắng mặt). Mỗi đợt sau vẫn có cổng review riêng (mục 6).
- Vẫn phải hỏi trước: commit / push, ghi Supabase, xoá dữ liệu, và mọi việc ngoài plan.
- **Quy tắc 3 lần (người dùng chốt 19/11, tính từ thời điểm này; các lượt trước không tính):** một việc đã giao / sửa **3 lượt liên tiếp mà chỉ số mục tiêu không cải thiện** (ví dụ độ phủ, số test trượt, số lỗi) thì dừng việc đó. Đánh dấu ⏸️ trong bảng 5.0 kèm lý do và trạng thái cuối, ghi TRACKING, rồi chuyển sang việc khác. Việc bị dừng không chặn việc chuyển đợt, trừ khi là điều kiện an toàn (ví dụ luật báo "đạt" khi thiếu dữ liệu).

### Đợt D0 – Từ điển thuốc và bộ phân giải tên (nền, làm trước tiên)

Mục tiêu: mọi dòng thuốc trong 69 tệp ca và trên Supabase phân giải được ra hoạt chất. Thuốc nào không phân giải được thì có lý do, không còn ô "?" vì thiếu dữ liệu.

| Bước | Việc | Đầu ra |
|:-:|:--|:--|
| D0.1 | Cào Cục Quản lý Dược (55k bản ghi, ~550 trang × 100, 1 yêu cầu/giây, khoảng 10 phút) | `data/kb_sources/dav/` + manifest |
| D0.2 | Tách `hoatChatChinh`: bỏ "(dưới dạng …)", "tương đương", tiêu chuẩn (USP, BP); tách phối hợp; tách hàm lượng. Code làm trước, ca khó cho LLM rút nháp có trích dẫn. Không chắc thì `chua_khop` | `kb_staging/dav_thanh_phan.jsonl`, báo cáo tỷ lệ tách được |
| D0.3 | Ánh xạ tên hoạt chất (VN, có muối) → INN → `rxcui` qua RxNav (`approximateTerm`, `related?tty=IN`) → ATC qua RxClass → `ddinter_id` (khớp tên + ATC với 2.568 thuốc DDInter) | `hoat_chat` mở rộng (mục tiêu ≥ 300 hoạt chất thường dùng nội trú, trước hết toàn bộ hoạt chất của ca) |
| D0.4 | Thống nhất mã: bỏ hai hệ `HC-…` (ca) và `…` (kho); viết bảng chuyển, cập nhật dữ liệu ca và seed DB | Một hệ khoá duy nhất |
| D0.5 | Phân loại thuốc "không có hoạt tính cần tra": dịch truyền, điện giải, vitamin (`loai`). Các yếu tố vẫn chạy nhưng có quy tắc riêng, ví dụ natri clorid không tra tương tác DDInter mà ghi "không áp dụng" thay cho "?" | Danh sách `loai` đã duyệt |
| D0.6 | Bộ phân giải tên + API đọc (`GET /api/thuoc/tra?ten=` cho tra cứu, dùng lại ở plan 1.9) | Module + test |

Nghiệm thu:

- [L] 100% dòng thuốc của `data/mock/demo` và `hoso_gia_lap` phân giải được, hoặc có `khong_nhan_dien` kèm lý do (mục tiêu: 0 dòng không nhận diện với danh mục giả lập).
- [L] Các cặp viết khác nhau cùng ra một hoạt chất: "Amoxicilin"/"Amoxicillin", "glargin"/"glargine", "Cotrimoxazol" → sulfamethoxazole + trimethoprim, "Augmentin" → amoxicillin + clavulanic acid.
- [K] Lấy ngẫu nhiên 50 bản ghi Cục Quản lý Dược, so tay thành phần tách ra với trang gốc: ≥ 98% đúng; mọi sai đều là loại "chưa khớp", không có loại "khớp sai".
- [K] 30 hoạt chất ngẫu nhiên: mã ATC khớp tra cứu RxClass trực tiếp.
- [DS] Duyệt danh sách `loai` và bảng `nhom_dieu_tri_trung` (đầu vào D2).

### Đợt D1 – Yếu tố 4: tương tác thuốc (ưu tiên vì giao diện ma trận đã có)

| Bước | Việc |
|:-:|:--|
| D1.1 | **Cào DDInter cấp thuốc**: 2.568 thuốc × 4 điểm JSON (thuốc–thuốc kèm cơ chế, thuốc–bệnh, thuốc–thức ăn, chế phẩm phối hợp) + trang thông tin thuốc (ATC, mô tả). Khoảng 13k yêu cầu, ~2–4 giờ chạy nền, có thể chạy tiếp sau khi dừng |
| D1.2 | **Cào trang chi tiết cặp, đợt ưu tiên**: mọi cặp có ít nhất một bên thuộc danh mục hoạt chất D0 (ước vài chục nghìn trang) → hậu quả, xử trí, tài liệu, thuốc thay thế, gợi ý CYP |
| D1.3 | **Cào cặp còn lại (đủ ~235k trang)**: chạy nền nhiều ngày ở 1–2 yêu cầu/giây; không chặn demo |
| D1.4 | Rút mục `drug_interactions` (+ bảng) của nhãn FDA thành dòng `tuong_tac` nháp có trích dẫn (mục 4.3) |
| D1.5 | QĐ 5948: khi Khoa Dược cấp bản gốc thì nhập tay hai người độc lập rồi so; trước đó **không nạp từ bài báo** |
| D1.6 | Gộp nguồn theo plan 1.3 mục 7.2. Ánh xạ mức: Major → `nghiem_trong`, Moderate → `can_luu_y`, Minor → `nhe`, Unknown → `chua_ro`; QĐ 5948 → `chong_chi_dinh` |
| D1.7 | Luật `interaction.py` (yếu tố 4) |
| D1.8 | Nối giao diện ma trận |

Luật `interaction.py`:

- Lấy mọi thuốc **đang hiệu lực** của ca (không chỉ y lệnh đang xét) qua bộ phân giải tên.
- Mở thành tập hoạt chất, xét mọi cặp. Gồm cả cặp **trong cùng một thuốc phối hợp** (chỉ báo khi nguồn có), và cặp hoạt chất trùng nhau bỏ qua (thuộc yếu tố 2).
- Mỗi cặp ra một trạng thái:
  - `N` nghiêm trọng / chống chỉ định → `can_xem`.
  - `L` cần lưu ý → `can_xem`, mức thấp.
  - `K` không phát hiện: **chỉ khi cả hai hoạt chất có trong DDInter với danh sách tương tác đầy đủ** và cặp không có.
  - `T` thiếu dữ liệu: một bên không có trong nguồn, hoặc mức Unknown.
  - `?` chưa kiểm: thuốc không phân giải được.
- Thuốc–thức ăn ra một dòng riêng dưới ma trận.
- Căn cứ mỗi ô: nguồn, tầng, mức, hậu quả, xử trí, liên kết trang gốc. DDInter luôn ghi "sàng lọc, cần đối chiếu".

Nối giao diện (`InteractionMatrix.tsx`): ô có màu theo mức. Bấm ô thì mở thẻ có hậu quả, xử trí, nguồn. Thuốc dịch truyền hiện "không áp dụng". **Không đổi hợp đồng API khi chưa sửa `plan/api-hop-dong-*` trước.**

Nghiệm thu:

- [L] Mỗi ca demo có ít nhất 1 tương tác thật theo nguồn: clarithromycin–simvastatin, amiodarone–digoxin, meropenem–valproate, warfarin–amoxicillin…
- [L] Ca Levetiracetam + Natri clorid + Paracetamol (ảnh người dùng gửi 18/11) không còn ô "?". Các ô ra `K`, `T` hoặc "không áp dụng" kèm lý do.
- [K] Lấy ngẫu nhiên 40 cặp đã cào, so từng trường (mức, cơ chế, hậu quả, xử trí) với trang DDInter mở bằng trình duyệt: 100% khớp nguyên văn.
- [K] Kiểm số lượng: số cặp của 10 thuốc bằng "total N items" trên trang thuốc.
- [K] Đối xứng: (A, B) và (B, A) cho cùng kết quả.
- [DS] Duyệt 20 cặp Major xuất hiện trong ca demo.

### Đợt D2 – Yếu tố 2: trùng lặp hoạt chất và trùng nhóm điều trị

- Trùng hoạt chất: giữ luật cũ, nhưng chạy trên kết quả của bộ phân giải tên (bắt được "Augmentin" + "Amoxicillin 500 mg").
- Trùng nhóm: hai hoạt chất khác nhau cùng một `nhom_dieu_tri_trung` (theo tiền tố ATC mức 4, ví dụ `A02BC` PPI, `M01A` NSAID, `B01AB` heparin / `B01AF` DOAC / `B01AA` kháng vitamin K, `C09` hai thuốc ức chế RAS).
- Ngoại lệ có duyệt, ví dụ phối hợp cố định có chủ đích, chuyển đổi thuốc trong cùng ngày có lịch ngừng.
- Nghiệm thu:
  - [L] Tình huống thử: omeprazol + esomeprazol; enoxaparin + rivaroxaban; ibuprofen + ketorolac; losartan + enalapril.
  - [K] Kiểm tay ATC của từng cặp.
  - [DS] Duyệt bảng nhóm.

### Đợt D3 – Yếu tố 1: dị ứng, quá mẫn

- Dị ứng ghi theo tên (có khi là biệt dược) → bộ phân giải tên → hoạt chất.
- Bảng `nhom_di_ung_cheo`:
  - Penicillin ↔ cephalosporin theo **chuỗi bên R1** (ví dụ amoxicillin–cefadroxil), carbapenem, sulfonamid kháng khuẩn, NSAID (phản ứng chéo ức chế COX-1), thuốc chống động kinh nhân thơm.
  - Nguồn là nhãn FDA (chống chỉ định, cảnh báo) cùng tài liệu tổng quan đã công bố. Dược sĩ duyệt từng dòng.
- Bỏ `nhom_duoc_ly` ghi tay trong ca, lấy từ từ điển.
- Mục chống chỉ định "quá mẫn với … hoặc tá dược" của nhãn thành căn cứ văn bản.
- Nghiệm thu:
  - [L] Dị ứng "Augmentin" + y lệnh amoxicillin → `can_xem`.
  - [L] Dị ứng penicillin + ceftriaxon → `nhom_lien_quan`.
  - [L] Tình trạng dị ứng chưa khai thác → `khong_du_du_lieu`.
  - [DS] Duyệt bảng chéo.

### Đợt D4 – Yếu tố 6: cơ địa, chẩn đoán và xét nghiệm

| Phần | Việc |
|:--|:--|
| Thận | Rút `quy_tac_lieu` theo CrCl cho **toàn bộ hoạt chất có ngưỡng thận trong nhãn** (34/50 nhãn đã có, plan 1.3). Ưu tiên kháng sinh, chống đông, thuốc có khoảng điều trị hẹp. Ghi đúng `chi_so` (CG hay eGFR) |
| Gan | Cài **Child-Pugh** (Pugh 1973; 5 thành phần; thiếu thành phần nào thì `khong_du_du_lieu`) + rút ngưỡng gan từ nhãn (7/50 nhãn) |
| Xét nghiệm | `nguong_xet_nghiem` theo nhãn: K⁺ với spironolacton / ức chế RAS; INR với warfarin; tiểu cầu với heparin / enoxaparin; ALT/AST với thuốc độc gan; natri; glucose với insulin, metformin + eGFR |
| Thuốc–bệnh | Từ DDInter `interact-with-dis` (D1.1). Ánh xạ tên bệnh → ICD-10 bằng bảng tay có duyệt; so với `chan_doan` của ca |
| Nhóm đặc biệt | Thai kỳ, cho con bú (LactMed, mục nhãn), tuổi (trẻ em, người cao tuổi) |

Nghiệm thu:

- [K] Tự tính lại CrCl, Child-Pugh cho 10 ca.
- [K] Mỗi dòng quy tắc có trích dẫn khớp nguyên văn nhãn.
- [K] Các khoảng phủ kín, không chồng nhau.
- [DS] Duyệt bảng thận cho 15 hoạt chất đầu.

### Đợt D5 – Yếu tố 3: chỉ định, liều, đường dùng

| Phần | Cách làm | Ghi chú |
|:--|:--|:--|
| Đường dùng | Đường dùng của y lệnh so với `duong_dung_hop_le` (từ dạng bào chế của Cục Quản lý Dược, `route` của NDC / nhãn, cột đường dùng của TT 20) | Luật chắc chắn, làm đầu tiên |
| Liều tối đa | `lieu_moi_lan × so_lan_moi_ngay` so với `lieu_toi_da_ngay`; liều theo kg (cần cân nặng, thiếu thì `khong_du_du_lieu`) | Rút từ nhãn (mục 4.3) |
| Tần suất / khoảng cách | So với khoảng cách liều trong nhãn hoặc bảng thận đã chọn ở D4 | Nối với yếu tố 7 |
| Chỉ định | Đoạn chỉ định của nhãn hoặc tờ hướng dẫn sử dụng VN qua RAG + chẩn đoán ICD-10 của ca. **Không luật hoá cứng.** LLM chỉ gợi ý "không thấy chỉ định khớp", luôn ở mức `can_xem` và kèm trích dẫn | Ngoài nhãn ≠ sai; ghi `ngoai_hdsd` |
| Quy định viện / BHYT | Điều kiện thanh toán TT 20 / 37 (nguyên văn) | Hiển thị tham khảo |
| Công thức | Giữ `app/calc`; thêm Child-Pugh (D4), liều theo kg / diện tích da, QTc (Bazett, Fridericia), canxi hiệu chỉnh khi có luật cần | Mỗi công thức: trích bài báo gốc, ca kiểm từ bài báo, kiểm chéo MedCalc-Bench (bản đã sửa lỗi) hoặc gói R `egfr` |
| Kháng sinh – kháng sinh đồ | Chuyển `antibiotic.py` **ra khỏi yếu tố 3** (sang yếu tố 6 "xét nghiệm, vi sinh"); cập nhật giao diện thẻ yếu tố | Sửa gắn nhầm |

Nghiệm thu:

- [L] Tình huống: levofloxacin dạng uống kê tiêm; paracetamol 1 g × 6 lần/ngày (vượt 4 g); gentamicin theo kg thiếu cân nặng → `khong_du_du_lieu`.
- [K] Tự tính lại liều ngày.
- [DS] Duyệt bảng liều tối đa.

### Đợt D6 – Yếu tố 5: độc tính và chống chỉ định theo sinh lý

- `canh_bao_doc_tinh` rút từ cảnh báo đóng khung, cảnh báo và quá liều của nhãn, cộng LiverTox.
- Luật:
  - **Cộng dồn độc thận**: ≥ 2 thuốc độc thận (aminoglycosid, vancomycin, NSAID, colistin, thuốc cản quang…) cùng lúc, nặng hơn khi CrCl giảm.
  - **Cộng dồn kéo dài QT**: ≥ 2 thuốc có cảnh báo QT trên nhãn.
  - **Khoảng điều trị hẹp** cần theo dõi nồng độ (vancomycin, digoxin, phenytoin, valproat, aminoglycosid): có nồng độ / xét nghiệm gần đây không.
  - **Thuốc nguy cơ cao** (insulin, chống đông, opioid, kali tiêm…).
- openFDA `drug/event` (FAERS) **không dùng** (mục 3.1 C). Độc gan lấy từ LiverTox (mức phân hạng + kiểu tổn thương), có trích dẫn.
- Nghiệm thu:
  - [L] Gentamicin + vancomycin + CrCl 30 → `can_xem`.
  - [K] Đối chiếu danh sách QT với mục cảnh báo nhãn.
  - [DS] Duyệt danh sách nhóm.

### Đợt D7 – Yếu tố 7: lịch dùng và bất hợp lý khác

- Giữ `schedule.py`.
- Thêm:
  - Kháng sinh nhóm phải phê duyệt trước theo QĐ 5631 mà ca chưa có hội chẩn / phê duyệt → `can_xem`.
  - Thời gian dùng kháng sinh vượt ngưỡng: chỉ khi có ngưỡng trong nguồn đã chốt; không có thì `khong_du_du_lieu` (không có phác đồ viện).
  - Kháng sinh hạn chế cần hội chẩn (`khang_sinh_han_che`).
  - Thuốc kê nhưng thiếu trường bắt buộc (liều, đường dùng, tần suất).
  - Trùng giờ dùng gây thiếu liều qua đêm (ví dụ quan sát 03/11: kê sáng – sáng hôm sau).
- Nghiệm thu: [L] mỗi luật có ca dương tính và ca âm tính.

---

## 6. Cổng review sau mỗi đợt (Claude làm, không sửa code)

1. Đọc diff. Đọc báo cáo chạy (số vào / ra / loại và lý do).
2. `uv run pytest`, `uv run ruff check .`. Với web: `npx vitest run`, `npx tsc -b`, `npm run build`.
3. **Kiểm độc lập**:
   - Mở trang nguồn gốc bằng trình duyệt, so mẫu ngẫu nhiên (số mẫu ghi ở từng đợt).
   - Tự tính lại công thức.
   - Đếm tổng so với số nguồn công bố.
4. Chạy thẩm định thật trên 6 ca demo + 10 ca hồ sơ giả lập. Chụp giao diện từng yếu tố, kiểm không còn ô "?" do thiếu từ điển.
5. Kiểm bất biến:
   - Không có `dat` khi thiếu dữ liệu.
   - LLM không đổi kết luận luật.
   - Không có dữ liệu người bệnh trong prompt hay log.
6. Ghi `plan/TRACKING.md`. Đạt mới mở đợt kế; chưa đạt thì viết `Dx-fix-n`.

---

## 7. Lịch và phạm vi theo mốc demo

Hôm nay 18/11. Đóng băng tính năng trưa 19/11. Demo 20/11. Không thể xong cả 8 đợt trước demo. Đề xuất:

| Mốc | Phạm vi |
|:--|:--|
| **Trước trưa 19/11 (bản demo)** | D0 (Cục Quản lý Dược + RxNav cho các hoạt chất trong ca; thống nhất mã) · D1.1 + D1.2 ở phạm vi hoạt chất trong ca · luật yếu tố 4 + ma trận thật · D2 (trùng nhóm). Các yếu tố khác giữ luật cũ nhưng chạy trên bộ phân giải tên mới |
| Sau demo, tuần kế | D1.3 (cào đủ chạy nền), D3, D4, D5 |
| Tiếp theo | D6, D7, QĐ 5948 và Dược thư khi Khoa Dược cấp |
| Sau khi D0–D7 qua cổng | Plan 1.9 (Agentic RAG): các bảng trên trở thành công cụ riêng (`tra_tuong_tac`, `tra_thuoc`, `tra_lieu_than`, …) có phân quyền |

---

## 8. Giao việc dự kiến (brief viết sau khi người dùng duyệt plan)

| Mã | Việc | Agent đề xuất | Song song được với |
|:--|:--|:--|:--|
| T50 | D0.1–D0.3: cào Cục Quản lý Dược, tách thành phần, RxNav / ATC, từ điển | Codex (`gpt-6.2-sol`, high) | T51 |
| T51 | D1.1–D1.2: cào DDInter cấp thuốc + chi tiết cặp ưu tiên, tầng 0–1 | Sonnet / Haiku (chỉ cào, có thể chạy tiếp sau khi dừng) | T50 |
| T52 | D0.4–D0.6: thống nhất mã, bộ phân giải tên, cập nhật dữ liệu ca | Codex | sau T50 |
| T53 | D1.6–D1.8: gộp tương tác, luật yếu tố 4, nối ma trận | Codex + agent web | sau T51, T52 |
| T54 | D2: trùng nhóm điều trị | Sonnet | sau T52 |

---

## 9. Rủi ro

| Rủi ro | Giảm thiểu |
|:--|:--|
| Tách `hoatChatChinh` của Cục Quản lý Dược sai (văn bản tự do) | Code trước, LLM có trích dẫn sau; "không chắc thì không khớp"; kiểm mẫu 50 bản ghi |
| DDInter chặn hoặc chậm khi cào nhiều | 1 yêu cầu/giây, lưu đệm, chạy tiếp sau khi dừng; đợt ưu tiên đủ cho demo |
| DDInter phi thương mại | Ghi giấy phép ở mọi căn cứ; vận hành thật phải xin phép hoặc thay bằng QĐ 5948 và nhãn |
| Nhãn FDA khác biệt dược VN | Ưu tiên tờ hướng dẫn sử dụng của Cục Quản lý Dược khi có; ghi "nhãn Mỹ" trên căn cứ |
| Không có dược sĩ duyệt kịp | Mọi dòng ở `nhap` / `sang_loc`, giao diện ghi rõ; không chặn demo |
| Tràn phạm vi trước demo | Chỉ làm phần ở mục 7 trước trưa 19/11 |

## 10. Câu hỏi cần người dùng / Khoa Dược

1. Duyệt plan và phạm vi trước demo (mục 7).
2. Bản gốc QĐ 5948 (bản đăng nhập trên luatvietnam hoặc cổng Bộ Y tế) để nhập tay. Danh mục thuốc và quy định của viện **không được cấp**: dùng Cục Quản lý Dược, TT 20 / 37 và QĐ 5631 thay thế (mục 3.1).
3. Dược sĩ duyệt dòng: bảng nhóm trùng, dị ứng chéo, liều thận, liều tối đa.
4. Có đưa dữ liệu cào (DDInter ~ vài trăm MB khi đủ, Cục Quản lý Dược ~ vài chục MB) vào git không. Đề xuất: **không**, chỉ đưa manifest và lệnh cào lại.
