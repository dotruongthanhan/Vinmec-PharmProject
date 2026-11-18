# Plan 1.7 – Dữ liệu hồ sơ bệnh án giả lập (60 hồ sơ người bệnh)

Trạng thái: **bản nháp v2 chờ duyệt (18/11/2026)**. Chưa tạo dữ liệu. Bản v2 theo chỉnh sửa của người dùng: **60 hồ sơ** (không phải 100); **một hồ sơ có nhiều lần vào viện**; **một lần vào viện có nhiều y lệnh**, y lệnh có **phần riêng (mục 5.2, chưa làm)**. Bản này giữ 60 như mục 8.1 plan gốc nhưng đổi đơn vị đếm (mục 3.0) và mở rộng mô hình `CaBenh` cho sát hồ sơ bệnh án thật. Quan hệ với plan khác: plan 1.3 (nguồn tri thức), plan 1.6 (nạp Supabase; Q-D1 giữ tệp mock đến hết demo 20/11), `docs/erd.md`.

---

## 1. Mục tiêu và ranh giới

1. Có bộ **60 hồ sơ người bệnh** giả lập **trông và chứa trường như hồ sơ bệnh án nội trú thật** (mỗi hồ sơ gồm một hoặc nhiều lần vào viện, mỗi lần có nhiều y lệnh), để dược sĩ nhìn vào thấy quen và để hệ thống có đủ bối cảnh chạy 7 yếu tố.
2. Mỗi ca có **đáp án chuẩn** (lỗi cài sẵn, yếu tố, mức độ) để đo hệ thống.
3. **Chỉ lấy trường phục vụ thẩm định y lệnh.** Hệ thống không phải phần mềm bệnh án; không cần mô phỏng toàn bộ giấy tờ hành chính, BHYT, thanh toán.
4. 100% giả lập, không có người bệnh thật, không sao chép bệnh án thật (CLAUDE.md mục 6).

## 2. Nguồn tham chiếu đã tìm và giới hạn

| Nguồn | Dùng để | Giới hạn |
| :--- | :--- | :--- |
| Ảnh người dùng gửi: **Bệnh án nhi khoa, MS 02/BV-01** | Khung phần I–III (hành chính, quản lý người bệnh, chẩn đoán) | Chỉ thấy nửa trên trang đầu |
| Thông tư 32/2023/TT-BYT, Phụ lục XXVIII: **29 mẫu bệnh án** (nội khoa 01/BV-01, nhi 02/BV-01, ngoại khoa 10/BV1…) thay Quyết định 4069/2001 (hết hiệu lực 01/01/2024) | Xác nhận khung pháp lý; bệnh án chia theo chuyên khoa nhưng chung phần I–IV | **Chưa lấy được toàn văn các mẫu**: trang pháp luật yêu cầu đăng nhập hoặc chỉ có mục lục |
| Quyết định 3730/QĐ-BYT (2021) | Danh mục phiếu đi kèm: Tờ điều trị, Phiếu sơ kết 15 ngày, Phiếu theo dõi truyền dịch, Phiếu theo dõi chức năng sống | Chỉ là danh mục, không có cột chi tiết |
| Thông tư 23/2011/TT-BYT | Phiếu lĩnh thuốc (MS 01D/BV-01), Phiếu công khai thuốc (MS 18D/BV-01): tên thuốc, số lượng/ngày, giường | Có thể đã sửa đổi, cần đối chiếu |
| Thông tư 33/2025/TT-BYT, 13/2025/TT-BYT | Lưu trữ 10/20/30 năm; hồ sơ điện tử từ 01/07/2025 | Không ảnh hưởng thiết kế dữ liệu |
| Synthea (FHIR: `Patient`, `Condition`, `Observation`, `MedicationRequest`) | Tham khảo cách tách tài nguyên; **không dùng trực tiếp**: thuốc sinh ra không giống thực hành kê đơn Việt Nam | Mã SNOMED/LOINC, không có ICD-10 Việt |

**Việc cần người có tay nghề làm:** nhờ dược sĩ hoặc khoa lấy **một bệnh án nội trú thật đã ẩn danh hoàn toàn** (hoặc mẫu trống in từ phần mềm của viện) để đối chiếu cột chi tiết của tờ điều trị và phiếu thực hiện y lệnh. Đây là nguồn tốt nhất và mình không thể thay bằng tìm web.

## 3.0. Đơn vị đếm: hồ sơ, lần vào viện, y lệnh

Ngoài thực tế, mỗi người bệnh có một mã định danh trong bệnh viện (mã HN) và **mỗi lần vào viện có một bệnh án riêng**, gắn với nhau qua mã đó. Vì nhiệm vụ của hệ thống là **tổng hợp thông tin** (dị ứng đã ghi lần trước, thuốc dùng lần trước, xu hướng creatinin qua các lần), nên **có cần** cho một người bệnh nhiều lần vào viện. Mô hình:

```
HỒ SƠ NGƯỜI BỆNH (1)  ──<  LẦN VÀO VIỆN / ĐỢT ĐIỀU TRỊ (n)  ──<  Y LỆNH (n)  ──<  DÒNG THUỐC (n)
```

Khớp với `docs/erd.md` (`NGUOI_BENH → DOT_DIEU_TRI → Y_LENH → CHI_TIET_Y_LENH`); phần mã hiện tại (`CaBenh`) mới chứa **một** đợt và **một** y lệnh chờ duyệt.

| Đơn vị | Số lượng | Ghi chú |
| :--- | :-: | :--- |
| Hồ sơ người bệnh | **60** | Đơn vị chính, đếm theo yêu cầu |
| Lần vào viện | khoảng 87 | 38 hồ sơ một lần; 17 hồ sơ hai lần; 5 hồ sơ ba lần |
| Y lệnh | 222 (thực tế sau khi sinh) | Trung bình 3 y lệnh mỗi lần vào viện (ngoại trú 1–2, nội trú 3–6) |
| **Y lệnh trọng tâm có đáp án** | **60** | Mỗi hồ sơ có **đúng một** y lệnh chờ thẩm định, là mục tiêu đo; y lệnh còn lại là bối cảnh (đã duyệt, đã ngưng, lần vào viện trước) |

Nhờ đó "ca" để đo vẫn là 60 như cũ, và bảng phân bố ở mục 6 giữ nguyên ý nghĩa.

## 3. Cấu trúc hồ sơ bệnh án nội trú (tổng hợp)

Mức chắc chắn: **cao** cho phần I–III (thấy trên ảnh), **trung bình** cho phần còn lại (kiến thức chung về bệnh án Việt Nam, chưa đối chiếu toàn văn).

**A. Trang đầu – hành chính và quản lý người bệnh**
- I. Hành chính: họ tên, ngày sinh/tuổi, giới, nghề nghiệp, dân tộc, ngoại kiều, địa chỉ, nơi làm việc; với nhi: họ tên, nghề nghiệp, trình độ học vấn của bố/mẹ; đối tượng (BHYT/thu phí/miễn/khác); số thẻ BHYT, giá trị đến ngày; người nhà cần báo tin, điện thoại.
- II. Quản lý người bệnh: giờ vào viện; trực tiếp vào (cấp cứu / khám bệnh / khoa điều trị); nơi giới thiệu (cơ quan y tế, tự đến, khác); vào khoa nào, ngày giờ vào từng khoa; chuyển khoa; chuyển viện (tuyến trên/dưới, CK); ra viện (ra viện, xin về, bỏ về, đưa về); tổng số ngày điều trị.
- III. Chẩn đoán (có mã ICD-10): nơi chuyển đến, KKB/cấp cứu, khi vào khoa điều trị, ra viện (bệnh chính, bệnh kèm), có tai biến, biến chứng, phẫu thuật/thủ thuật.
- IV. Tình trạng ra viện: kết quả điều trị (khỏi, đỡ, không thay đổi, nặng hơn, tử vong), giải phẫu bệnh, nguyên nhân tử vong.

**B. Phần bệnh án (do bác sĩ)**
- Lý do vào viện; hỏi bệnh: bệnh sử, tiền sử bản thân (dị ứng, thuốc đang dùng, bệnh mạn tính, phẫu thuật, thói quen), tiền sử gia đình; nhi thêm: sản khoa, tiêm chủng, dinh dưỡng.
- Khám bệnh: toàn thân (mạch, nhiệt độ, huyết áp, nhịp thở, cân nặng, chiều cao, BMI), từng cơ quan; các cơ quan liên quan chuyên khoa.
- Tóm tắt bệnh án; chẩn đoán khi vào khoa; tiên lượng; hướng điều trị.
- Cận lâm sàng: xét nghiệm, chẩn đoán hình ảnh, thăm dò chức năng, vi sinh.
- Tổng kết bệnh án khi ra viện (quá trình bệnh, phương pháp điều trị, tình trạng ra viện, hướng điều trị tiếp, ghi chú thuốc).

**C. Phiếu theo thời gian (đây là nơi thẩm định thuốc lấy dữ liệu nhiều nhất)**
- **Tờ điều trị**: mỗi ngày một dòng: ngày giờ, diễn biến, **y lệnh** (thuốc, liều, đường, giờ, xét nghiệm), chữ ký.
- **Phiếu chăm sóc / thực hiện y lệnh**: điều dưỡng ghi đã dùng thuốc lúc mấy giờ.
- **Phiếu theo dõi chức năng sống**: mạch, nhiệt, huyết áp, nhịp thở, SpO2, cân nặng, nước tiểu.
- **Phiếu theo dõi truyền dịch**; **phiếu lĩnh thuốc**; **phiếu công khai thuốc**; phiếu xét nghiệm, phiếu chẩn đoán hình ảnh, phiếu sơ kết 15 ngày, biên bản hội chẩn, phiếu phẫu thuật/gây mê (ca ngoại).

## 4. So sánh với trường hiện có (`CaBenh` trong `app/domain/models.py`)

Chú giải: ✔ đã có · ◐ có một phần · ✘ chưa có · ⊘ **cố ý không đưa** (danh tính, không phục vụ thẩm định).

| Nhóm trên bệnh án thật | Hiện có | Nhận xét | Đề xuất |
| :--- | :--- | :--- | :--- |
| Tuổi, giới | ✔ `NguoiBenh.tuoi`, `gioi_tinh` | Đủ | Thêm `nhom_tuoi` suy ra (sơ sinh, nhi, người lớn, cao tuổi) để phân tầng bộ ca |
| Họ tên, địa chỉ, điện thoại, nghề, dân tộc, nơi làm việc, người nhà | ⊘ | Danh tính; CLAUDE.md cấm | Không đưa |
| Đối tượng BHYT, số thẻ | ⊘ | Số thẻ là định danh | Chỉ giữ `doi_tuong` (BHYT/thu phí) nếu luật kê thuốc cần |
| Giờ vào viện, ngày vào khoa, ngày ra | ◐ `thoi_diem_bat_dau` | Thiếu ngày ra, tổng ngày điều trị | Thêm `thoi_diem_ket_thuc`, `so_ngay_dieu_tri` |
| Vào qua cấp cứu/khám bệnh/chuyển khoa | ✘ | Ảnh hưởng ưu tiên duyệt | Thêm `hinh_thuc_vao` |
| Chuyển khoa (nhiều khoa theo thời gian) | ✘ | Y lệnh khác nhau theo khoa | Thêm `lich_su_khoa[]` |
| Chẩn đoán chính/kèm + ICD-10 | ✔ `ChanDoan` | Thiếu thời điểm chẩn đoán (khi vào, khi ra) | Thêm `thoi_diem`, `giai_doan` |
| Lý do vào viện, bệnh sử, tiền sử | ◐ chỉ `dien_bien` văn bản tự do | Chưa tách, LLM khó tìm | Thêm `benh_su`, `tien_su` (bản thân, gia đình, thuốc đang dùng) |
| Dị ứng 3 trạng thái | ✔ | Tốt, giữ | Giữ |
| Cơ địa (thai, bú, suy gan, thận) | ✔ `CoDia` | Giữ | Giữ |
| Sinh hiệu, cân nặng, chiều cao | ✔ `SinhHieu` | Là danh sách rời, thiếu chuỗi theo ngày | Giữ; sinh **chuỗi theo ngày** cho ca dài |
| Khám bệnh từng cơ quan | ✘ | Phần lớn không cần cho thuốc | Chỉ thêm `kham_benh` văn bản tự do (để đọc, không bóc trường) |
| Xét nghiệm, ngưỡng | ✔ `KetQuaXetNghiem` | Thiếu `muc_canh_bao` và bệnh phẩm | Thêm `muc_canh_bao` (suy ra từ ngưỡng) |
| Vi sinh, kháng sinh đồ | ✔ `ViSinh` | Đủ | Giữ |
| Chẩn đoán hình ảnh, thăm dò | ✘ | Cần cho một số chỉ định (chống chỉ định thuốc cản quang…) | Thêm `can_lam_sang_khac[]` mức văn bản |
| Tờ điều trị: diễn biến theo ngày | ◐ `DienBien` | Thiếu gắn người ghi (bác sĩ/điều dưỡng) và ngày | Thêm `nguoi_ghi_vai_tro`; sinh **mỗi ngày một dòng** |
| Y lệnh thuốc: liều, đường, giờ, đợt | ✔ `ChiTietYLenh` + `LichDung` | Mạnh | Giữ |
| Nhiều lần vào viện của một người bệnh | ✘ (`CaBenh` chỉ một `dot_dieu_tri`) | Chưa tổng hợp được thông tin xuyên các lần | Mục 5.1: thêm `HoSoNguoiBenh` chứa `dot_dieu_tri[]` |
| Nhiều y lệnh trong một lần vào viện, lịch sử đổi/ngưng | ◐ chỉ `y_lenh_cho_duyet` (1) + `thuoc_dang_dung` | Không có chuỗi y lệnh, không thấy ai thay ai | **Phần riêng, mục 5.2 (chưa làm)** |
| Phiếu thực hiện y lệnh (đã dùng lúc nào) | ✘ | Cần cho lỗi "thiếu liều tối" | Thêm `thuc_hien_y_lenh[]` mức đơn giản, chỉ ca cần |
| Phiếu lĩnh/công khai thuốc | ✘ | Là sản phẩm phụ của y lệnh | **Không tạo**, suy ra từ y lệnh nếu cần |
| Tổng kết ra viện | ✘ | Chỉ ca đã ra viện | Thêm `tong_ket` văn bản, chỉ ca ngoại trú/ra viện |
| Tiên lượng, hướng điều trị | ✘ | Bối cảnh cho LLM | Thêm vào `tom_tat` văn bản |
| Mã nguồn, độ giả lập | ✘ | Cần để tránh nhầm với thật (Q-D5 plan 1.6) | Thêm `la_gia_lap: true`, `kich_ban_id`, `phien_ban_sinh` |

**Kết luận so sánh:** mô hình hiện có đã đủ cho **lõi thẩm định** (dị ứng, cơ địa, xét nghiệm, vi sinh, y lệnh). Thiếu chủ yếu ba thứ: (1) **chiều thời gian** (nhiều ngày, nhiều khoa, y lệnh cũ đã ngưng), (2) **bối cảnh văn bản** (bệnh sử, tiền sử, tóm tắt, tổng kết) giống thật, (3) **đánh dấu giả lập và nguồn gốc kịch bản**. Hành chính và danh tính cố ý bỏ.

## 5. Mô hình mở rộng đề xuất (mức 1 bắt buộc, mức 2 nên có)

- **Mức 1 (bắt buộc, cần cho 60 hồ sơ):** `thoi_diem_ket_thuc`, `so_ngay_dieu_tri`, `lich_su_khoa[]`, `benh_su`, `tien_su`, `tom_tat`, `muc_canh_bao` cho xét nghiệm, `la_gia_lap`, `kich_ban_id`, cộng cấu trúc nhiều lần vào viện (5.1) và y lệnh (5.2).
- **Mức 2 (nên có):** `hinh_thuc_vao`, `kham_benh` văn bản, `can_lam_sang_khac[]`, `thuc_hien_y_lenh[]`, `tong_ket`, `nguoi_ghi_vai_tro`.
- **Không làm:** phiếu công khai thuốc, phiếu lĩnh, mọi trường hành chính/BHYT/danh tính.
- Tất cả trường mới **tùy chọn** để 6 ca `DEMO-xx` hiện có vẫn hợp lệ (`extra="forbid"` vẫn giữ). Đổi mô hình = một task Codex riêng (T-H1), kèm cập nhật hợp đồng API nếu API trả thêm trường.

### 5.1. Hồ sơ người bệnh nhiều lần vào viện (đề xuất)

- Thêm lớp `HoSoNguoiBenh`: `nguoi_benh`, `tinh_trang_di_ung` và `di_ung` (cấp người bệnh, cập nhật theo lần), `dot_dieu_tri[]` (mỗi phần tử gồm thông tin lần vào viện hiện có: khoa, thời điểm, chẩn đoán, cơ địa, sinh hiệu, xét nghiệm, vi sinh, diễn biến, **y lệnh**), `danh_muc_thuoc`, `danh_muc_hoat_chat`.
- **`CaBenh` giữ nguyên làm "lát cắt thẩm định"**: loader dựng một `CaBenh` từ `HoSoNguoiBenh` + `y_lenh_id` cần duyệt (lần vào viện hiện tại + tóm tắt các lần trước). Nhờ đó phần luật, API, web đang chạy không phải viết lại; `ca_id` = mã y lệnh trọng tâm.
- Quy tắc tổng hợp xuyên lần (đây là thứ cần thử): dị ứng ghi ở lần trước phải hiện ở lần sau; thuốc đã ngưng vì tác dụng phụ ở lần trước; creatinin lần trước làm mốc xu hướng; chẩn đoán mạn tính nhắc lại.
- Ca bẫy xuyên lần (đưa vào bộ): 5 hồ sơ mà lỗi chỉ thấy được khi đọc **lần vào viện trước** (ví dụ dị ứng ghi ở lần 1, lần 2 để trống).

### 5.2. Y lệnh – phần riêng (**CHƯA LÀM**, ghi để làm sau khi duyệt)

Hiện trạng: `YLenh` chỉ có một y lệnh chờ duyệt, thuốc đang dùng là danh sách dòng thuốc rời, không có khái niệm "chuỗi y lệnh".

Cần thiết kế riêng (một brief và một task, không gộp vào T-H1):
1. **Nhiều y lệnh trong một lần vào viện**: `y_lenh[]` theo thời gian (ngày giờ kê, khoa kê, vai trò người kê: bác sĩ điều trị/trực/hội chẩn, **không ghi tên**), loại (thường quy, cấp cứu, khi cần, hội chẩn), luồng duyệt (trực tiếp/hậu kiểm), mức ưu tiên.
2. **Vòng đời y lệnh**: trạng thái (`cho_duyet`, `da_duyet`, `dang_thuc_hien`, `ngung`, `hoan_tat`), `thay_the_y_lenh_id` (y lệnh mới thay y lệnh nào), `ly_do_ngung`, thời điểm ngưng.
3. **Dòng thuốc trong y lệnh**: giữ `ChiTietYLenh` hiện có (liều, tần suất, đường, `lich_dung`, nguồn thuốc), thêm liên kết về y lệnh gốc.
4. **Quan hệ với trường cũ**: `y_lenh_cho_duyet` thành `y_lenh_id` trỏ tới y lệnh trọng tâm; `thuoc_dang_dung` dựng từ các y lệnh còn hiệu lực tại thời điểm kê.
5. **Quy tắc sinh dữ liệu**: mỗi lần vào viện 1–6 y lệnh; có chuỗi thay đổi liều, đổi thuốc, ngưng thuốc; đúng một y lệnh trọng tâm; không có hai y lệnh hiệu lực trùng hoạt chất trừ ca cố ý (yếu tố 2).
6. **Cập nhật cần kéo theo**: loader, `docs/erd.md` (đã có `Y_LENH`/`CHI_TIET_Y_LENH`, cần thêm quan hệ thay thế), hợp đồng API nếu web hiện lịch sử y lệnh.

Trạng thái: **chưa làm, chưa giao việc**. Làm sau Q-H duyệt, trước bộ sinh T-H2 vì bộ sinh cần biết cấu trúc y lệnh.

## 6. Chiến lược tạo 60 hồ sơ

### 6.1. Nguyên tắc
1. **Kịch bản trước, văn bản sau.** Mỗi hồ sơ xuất phát từ một **kịch bản** do người thiết kế (bệnh, thuốc, lỗi cài sẵn, yếu tố 1–7, mức độ, đáp án, và nếu nhiều lần vào viện thì lần nào mang lỗi). Số liệu (cân nặng, creatinin, liều, giờ dùng) do **code sinh theo quy tắc có seed**, không để LLM bịa số. LLM chỉ viết văn bản tự do từ số liệu đã chốt.
2. **Đáp án sinh cùng lúc với kịch bản**, không suy ra sau. Dược sĩ duyệt đáp án **trước** khi xem kết quả hệ thống.
3. **Chống tự chấm bài:** dùng mô hình và prompt khác với phần chạy trong app; giữ 9 hồ sơ làm **đề thi kín** (người viết prompt app không xem).
4. **Độ bẩn có chủ đích:** trường trống, viết tắt, lệch đơn vị, phiếu khám rỗng, thuốc đã ngưng, thiếu cân nặng.
5. **Thuốc phải có thật trong danh mục** và có trong tri thức (3.730 đoạn, DDInter); thuốc ngoài danh mục chỉ dùng cho ca "ngoài HDSD".
6. **Mỗi hồ sơ đúng một y lệnh trọng tâm có đáp án**; y lệnh khác và lần vào viện khác là bối cảnh (mục 3.0).

### 6.2. Phân bố đề xuất (tổng 60 hồ sơ, tính theo y lệnh trọng tâm)

| Nhóm | Số | Ghi chú |
| :--- | :-: | :--- |
| **Sạch** (không lỗi, đo báo nhầm) | 9 | Đủ dữ liệu, gồm 2 ca "trông giống lỗi nhưng đúng" |
| **Lỗi theo yếu tố 1–7** | 28 | 4 hồ sơ mỗi yếu tố; một nửa có hai lỗi chồng nhau |
| **Thiếu dữ liệu có chủ đích** (kết luận "không đủ dữ liệu") | 6 | Thiếu cân nặng, không rõ dị ứng, thiếu creatinin |
| **Lỗi lịch dùng** (gộp sáng–tối, thiếu liều tối) | 4 | Dùng `lich_dung` |
| **Kháng sinh có vi sinh** | 5 | Kháng sinh đồ S/I/R, hạ bậc |
| **Ngoài HDSD** | 3 | Kê ngoài chỉ định hoặc thuốc ngoài danh mục |
| **Chèn lệnh trong văn bản** | 5 | Văn bản diễn biến chứa mệnh lệnh giả (nối tiếp DEMO-06) |

Tổng 9 + 28 + 6 + 4 + 5 + 3 + 5 = 60; mỗi hồ sơ thuộc đúng một nhóm chính. **Trong 60 hồ sơ, có 5 hồ sơ bẫy xuyên lần** (lỗi chỉ thấy khi đọc lần vào viện trước), tính vào các nhóm trên.

**Chiều phân tầng:**
- Khoa của lần vào viện trọng tâm: tim mạch 9, hô hấp/truyền nhiễm 9, thận–nội tiết 7, thần kinh 6, ung bướu 6, ngoại có kháng sinh dự phòng 9, nhi 6, sản 3, hồi sức 5 (= 60).
- Nhóm tuổi: nhi 7, người lớn 32, cao tuổi ≥ 65: 21.
- Lần vào viện trọng tâm: nội trú 42, ngoại trú 18. Số thuốc trong y lệnh trọng tâm cộng thuốc đang dùng: 1–2 thuốc 12, 3–6 thuốc 30, từ 7 thuốc trở lên 18.
- Mức nghiêm trọng của 28 ca lỗi yếu tố 1–7: nghiêm trọng 8, cần lưu ý 14, thông tin 6.
- Số lần vào viện: 1 lần 38 hồ sơ, 2 lần 17, 3 lần 5.

### 6.3. Quy trình sản xuất (3 lớp)

1. **Ma trận kịch bản** (bảng tính hoặc YAML): `kich_ban_id · khoa · tuổi/giới · bệnh+ICD-10 · thuốc · lỗi cài · yếu tố · mức độ · đáp án · nguồn tri thức làm căn cứ`. 60 dòng (mỗi dòng một hồ sơ, ghi riêng từng lần vào viện và y lệnh). Người thiết kế: Claude soạn ma trận, **dược sĩ duyệt**.
2. **Bộ sinh có seed** (Codex viết code, task T-H2): từ mỗi dòng kịch bản sinh số liệu hợp sinh lý (cân nặng theo tuổi, creatinin liên hệ với tuổi và bệnh, huyết động theo diễn biến) và chuỗi theo ngày; xuất JSON theo mô hình mở rộng.
3. **Viết văn bản** (agy/LLM khác app): bệnh sử, tiền sử, diễn biến theo ngày, tóm tắt, tổng kết; có **mẫu văn phong bệnh án Việt** (viết tắt, câu cụt, lỗi gõ nhẹ).

### 6.4. Kiểm chứng (cổng chất lượng)
1. **Cấu trúc:** pydantic, toàn vẹn tham chiếu (đã có).
2. **Lâm sàng:** bộ kiểm tra tự động (creatinin–tuổi–cân nặng hợp lý; liều trong 0,1–10 lần khoảng thường gặp; không thuốc chống chỉ định tuyệt đối nằm ngoài ca lỗi; thai chỉ ở nữ trong độ tuổi sinh sản).
3. **Không rò danh tính:** quét họ tên, số điện thoại, số thẻ, địa chỉ thật; mọi tên là giả có tiền tố.
4. **Lấy mẫu dược sĩ:** duyệt đáp án 100% (nhanh vì chỉ đọc dòng kịch bản); đọc kỹ hồ sơ đầy đủ 12 hồ sơ.
5. **Giống thật:** đưa 4 hồ sơ cho dược sĩ không biết nguồn, hỏi "ca nào là giả"; ca nào bị nhận ra thì sửa văn phong.
6. **Chạy thử hệ thống** trên bộ, đo bắt lỗi nghiêm trọng, nhiễu mỗi ca (ngưỡng ở plan gốc mục 8.2).

### 6.5. Phân đợt (sau demo 20/11; giữ mock hiện có trước đó, theo Q-D1)
| Đợt | Nội dung | Ca lũy kế |
| :--- | :--- | :-: |
| H0 | Duyệt plan, quyết định Q-H1…Q-H6, lấy mẫu bệnh án thật đã ẩn danh | 6 |
| H1a | **Thiết kế y lệnh riêng (mục 5.2)** + mô hình `HoSoNguoiBenh` (5.1) | 6 |
| H1 | Mở rộng mô hình (mức 1, mức 2) + cập nhật loader, API, web; 6 ca cũ vẫn hợp lệ | 6 |
| H2 | Ma trận kịch bản 60 dòng + dược sĩ duyệt đáp án | 6 |
| H3 | Bộ sinh số liệu + mẫu 12 hồ sơ thử, dược sĩ rà | 12 |
| H4 | Sinh đủ 60 hồ sơ + văn bản + cổng chất lượng | 60 |
| H5 | Chạy hệ thống, đo chỉ số, sửa ca hoặc luật | 60 |
| H6 | Nạp Supabase theo plan 1.6 (`la_gia_lap = true`) | 60 |

## 7. Rủi ro

| Rủi ro | Giảm thiểu |
| :--- | :--- |
| Giả lập quá "sạch" nên điểm đo cao ảo | Độ bẩn có chủ đích, đề thi kín, ca nhận diện giả/thật |
| LLM bịa số hoặc thuốc sai | Số do code sinh; thuốc lấy từ danh mục; bộ kiểm lâm sàng tự động |
| Mô hình mở rộng làm gãy API, web | Mọi trường mới tùy chọn; hợp đồng API cập nhật trước; chạy toàn bộ test |
| Thiếu mẫu thật nên cấu trúc tờ điều trị lệch | Nhờ khoa cho mẫu ẩn danh trước H1 |
| Tốn quota LLM cho 60 hồ sơ, nhiều lần vào viện, văn bản dài | Văn bản ngắn, tái dùng mẫu, sinh theo lô, đo chi phí ở H3 |

## 8. Quyết định cần duyệt

| Mã | Câu hỏi | Đề xuất |
| :--- | :--- | :--- |
| Q-H1 | Số hồ sơ | **60** (người dùng chốt 18/11) |
| Q-H2 | Mở rộng mô hình mức nào | Mức 1 + mức 2; bỏ hành chính |
| Q-H3 | Thời điểm bắt đầu | Sau demo 20/11 (giữ 6 ca mock đến hết demo) |
| Q-H4 | Ai thiết kế ma trận, ai duyệt | Claude soạn, dược sĩ duyệt đáp án |
| Q-H5 | Có lấy một bệnh án thật ẩn danh làm mẫu cấu trúc không | Có, nếu khoa đồng ý; chỉ lấy cấu trúc, không lấy nội dung |
| Q-H6 | Có làm chuỗi theo ngày (tờ điều trị mỗi ngày) cho lần vào viện nội trú | Có cho lần nội trú trọng tâm (42 hồ sơ); lần cũ chỉ tóm tắt |
| Q-H7 | Một người bệnh có nhiều hồ sơ (nhiều lần vào viện)? | **Có** (người dùng chốt, phục vụ tổng hợp): 38 hồ sơ 1 lần, 17 hồ sơ 2 lần, 5 hồ sơ 3 lần |
| Q-H8 | Y lệnh làm thế nào | Phần riêng mục 5.2, **chưa làm**, thiết kế trước T-H2 |

## 9. Bảng theo dõi

| Mã | Việc | Người | Trạng thái |
| :--- | :--- | :--- | :--- |
| P1.7 | Soạn plan 1.7 | Claude | xong (bản nháp 18/11) |
| H0 | Người dùng duyệt plan, Q-H1…Q-H8 | Người dùng | chờ duyệt |
| H0b | Xin mẫu bệnh án thật ẩn danh | Người dùng | chờ |
| H1a | **Thiết kế y lệnh riêng (mục 5.2)** và `HoSoNguoiBenh` nhiều lần vào viện | Claude (brief) + Codex | **chưa làm** |
| T-H1 | Mở rộng `CaBenh` (mức 1, 2) + loader + API + web | Codex | chưa giao |
| T-H2 | Bộ sinh số liệu có seed + bộ kiểm lâm sàng | Codex | chưa giao |
| H2 | Ma trận 60 kịch bản + dược sĩ duyệt | Claude + dược sĩ | chưa làm |
| H4 | Sinh 60 hồ sơ + văn bản + cổng chất lượng | Codex/agy | chưa làm |
| H5 | Chạy hệ thống, đo | Claude | chưa làm |

## 10. Đối chiếu lược đồ Supabase `nghiep_vu` (18/11/2026, đọc `information_schema`, chỉ đọc)

Hiện có 19 bảng, đều bật RLS; chỉ có 6 ca `DEMO-xx` (6 người bệnh, 6 đợt, 6 y lệnh, 6 dòng thuốc).

**Đã hỗ trợ sẵn về quan hệ:** `nguoi_benh (1) → dot_dieu_tri (n)` (FK `nguoi_benh_id`), `dot_dieu_tri (1) → y_lenh (n)`, `y_lenh (1) → chi_tiet_y_lenh (n)`, `chi_tiet_y_lenh (1) → lich_dung (n)`. Nghĩa là **một người bệnh nhiều lần vào viện, một lần nhiều y lệnh không cần đổi cấu trúc cha-con**.

**Phải sửa trước khi nạp 60 hồ sơ:**

| # | Vấn đề hiện tại | Đề xuất |
| :-: | :--- | :--- |
| 1 | `dot_dieu_tri.ca_id` **NOT NULL UNIQUE** và là đích FK của `lan_tham_dinh.ca_id`, `phan_hoi.ca_id`: một đợt = một ca. Đợt cũ không có ca, một đợt có nhiều y lệnh | Chuyển khái niệm "ca" sang **y lệnh trọng tâm**: thêm `y_lenh.ca_id` (UNIQUE, nullable); `ca_id` ở `dot_dieu_tri` thành nullable hoặc bỏ; trỏ lại FK của `lan_tham_dinh`, `phan_hoi` sang `y_lenh(ca_id)` |
| 2 | `dot_dieu_tri` thiếu: `thu_tu`, `thoi_diem_ket_thuc`, `so_ngay_dieu_tri`, `hinh_thuc_vao`, `lich_su_khoa`, `ly_do_vao_vien`, `benh_su`, `tien_su`, `kham_benh`, `tom_tat`, `tong_ket`; `mo_ta_ngan` đang NOT NULL | Thêm các cột (text/jsonb, nullable); `mo_ta_ngan` lấy từ `tom_tat` |
| 3 | `y_lenh` thiếu: `vai_tro_nguoi_ke`, `loai`, `trang_thai`, `thay_the_y_lenh_id` (khóa ngoại tự tham chiếu), `ly_do_ngung`, `thoi_diem_ngung` | Thêm cột; ràng buộc kiểm `trang_thai` |
| 4 | `chi_tiet_y_lenh.thuoc_dang_dung` NOT NULL và `dot_dieu_tri_id` NOT NULL (lặp thông tin của `y_lenh`) | Giữ `dot_dieu_tri_id`; `thuoc_dang_dung` suy ra từ trạng thái y lệnh (hoặc view), không lưu tay |
| 5 | `nguoi_benh` thiếu `la_gia_lap`, `kich_ban_id`, `phien_ban_sinh` (Q-D5 plan 1.6 đã định dùng `la_gia_lap`); `tuoi` chỉ một giá trị | Thêm 3 cột; tuổi giữ ở lần cuối, thêm `tuoi_luc_vao` ở `dot_dieu_tri` nếu cần |
| 6 | **Mã hoạt chất lệch**: FK `thuoc_hoat_chat`, `di_ung`, `khang_sinh_do` → `tri_thuc.hoat_chat` (61 dòng: 50 mã chuẩn kiểu `amoxicillin` + mã `HC-…` của 6 ca demo, như `HC-AMLODIPIN`, `HC-CEFTRIAXON`). Hồ sơ mới dùng `HC-<TÊN QUỐC TẾ HOA>` (ví dụ `HC-CEFTRIAXONE`) nên không khớp mã nào | Khi nạp, **ánh xạ về mã chuẩn của tri thức** (bảng ánh xạ do mình soạn); gộp mã `HC-…` của demo về mã chuẩn |
| 7 | Hoạt chất ngoài tri thức (`gabapentin`, `cefoperazon`, `sulbactam` của 3 hồ sơ ngoài HDSD) làm **vi phạm FK** | Thêm dòng `tri_thuc.hoat_chat` với `can_duyet = true`, hoặc cho FK nullable ở các bảng nghiệp vụ |
| 8 | `chan_doan` không có thời điểm; `dien_bien` không có vai trò người ghi | Thêm `thoi_diem`, `nguoi_ghi_vai_tro` (nullable) |

**Giữ nguyên:** `co_dia` (jsonb, theo từng đợt), `di_ung` (theo người bệnh), `ket_qua_xet_nghiem`, `sinh_hieu`, `vi_sinh`, `khang_sinh_do`, `lich_dung`, `thuoc`, `thuoc_hoat_chat`, `lan_tham_dinh`, `nhan_dinh`, `nhan_dinh_thuoc`, `can_cu`, `phan_hoi` (cấu trúc con).

**Việc kéo theo:** tệp `db/schema.sql`, ánh xạ trong `app/db/mapping.py`, nguồn nạp `app/db/sources.py` (đang đọc `data/mock/demo`) cần sửa; một task Codex (T-H3) và kiểm lại 6 ca demo sau khi đổi khóa `ca_id`. Mọi thay đổi lược đồ qua migration, không sửa tay trên Supabase; thực hiện sau khi người dùng check tay xong.

## 11. Đánh giá MIMIC-IV v3.1 làm nguồn dữ liệu (18/11/2026)

Kết luận: **không thay được bộ 60 hồ sơ giả lập**, nhưng **nên dùng làm tham chiếu cấu trúc y lệnh** cho mục 5.2.

| Nhu cầu của dự án | MIMIC-IV v3.1 | Ghi chú |
| :--- | :-: | :--- |
| Nhiều lần vào viện của một người | ✔ | `subject_id` → `hadm_id`; 364.627 bệnh nhân, 546.028 lượt nhập viện (v3.0) |
| Chuyển khoa | ✔ | `transfers`, `services` |
| Chẩn đoán ICD | ◐ | `diagnoses_icd` là mã tổng kết lúc ra viện, không có giờ |
| Y lệnh, dòng thuốc, liều, đường, tần suất | ✔ | `poe`, `prescriptions` (`dose_val_rx`, `route`, `doses_per_24_hrs`), `pharmacy` (`frequency`, `disp_sched`, `duration`, `status`) |
| Dược sĩ xác nhận y lệnh | ◐ | `pharmacy.entertime`, `verifiedtime` (có giờ, không có kết quả can thiệp) |
| Đã dùng thuốc lúc nào | ✔ | `emar` (`charttime`, `scheduletime`, `event_txt`: Administered/Delayed/Not Given); chỉ có từ khoảng 2011–2013 |
| Xét nghiệm | ✔ | `labevents` + `d_labitems` |
| Vi sinh, kháng sinh đồ S/I/R, MIC | ✔ | `microbiologyevents` (`org_name`, `ab_name`, `interpretation`, `dilution_value`) |
| Cân nặng, chiều cao | ◐ | `omr` (chủ yếu ngoại trú) và `chartevents` của ICU; nhiều lượt không có |
| Sinh hiệu | ◐ | Chủ yếu bệnh nhân ICU |
| **Dị ứng** | ✘ | Không có bảng riêng; chỉ trong văn bản (module Note, cần cấp quyền riêng) |
| **Thai, cho con bú, suy gan** | ✘ | Phải suy từ ICD và xét nghiệm |
| **Diễn biến theo ngày (tờ điều trị)** | ✘ | Chỉ có tóm tắt ra viện và báo cáo hình ảnh |
| **Đáp án chuẩn về lỗi y lệnh** | ✘ | Không có nhãn; dùng luật để gán nhãn thì tự chấm bài |
| Ngôn ngữ, thực hành kê đơn | ✘ | Tiếng Anh, bệnh viện Mỹ; khác danh mục thuốc và phác đồ Việt Nam |

**Ràng buộc truy cập và sử dụng** (theo trang PhysioNet; cần đọc DUA đầy đủ):
1. Phải có tài khoản **credentialed**, hoàn thành khóa CITI và ký DUA; từng thành viên tự làm.
2. Dữ liệu và bộ phái sinh được coi là nhạy cảm, **không chia sẻ lại**. Đưa vào kho git hoặc Supabase của dự án cần xác minh DUA cho phép.
3. Dùng với LLM: PhysioNet khuyến nghị mô hình chạy cục bộ; API đám mây chỉ khi xác minh được không lưu dữ liệu, không huấn luyện, không người xem lại. **Không áp dụng cho DeepSeek / OpenRouter đang dùng**, nên không đưa văn bản MIMIC qua hai dịch vụ này.
4. Trái nguyên tắc dự án "100% giả lập, không dữ liệu người bệnh thật" (CLAUDE.md mục 6) nếu dùng làm dữ liệu demo; cần chủ kho và bên Vinmec/VinUni đồng ý.

**Cách dùng đề xuất:**
- **Dùng ngay, không cần quyền:** đọc **tài liệu công khai** của `poe`, `poe_detail`, `prescriptions`, `pharmacy`, `emar` để bổ sung mục 5.2: tách **y lệnh (đặt) – dòng thuốc – xác nhận của dược sĩ – ghi nhận đã dùng**; thêm bảng thực hiện y lệnh nếu cần ca "thiếu liều tối".
- **Cân nhắc sau demo:** xin quyền MIMIC-IV để (a) tham khảo phân bố liều, đường, tần suất khi chỉnh bộ sinh số liệu, (b) kiểm tra cấu trúc hệ thống trên dữ liệu thật, chạy **mô hình cục bộ**, không dùng API ngoài.
- Bản **MIMIC-IV Demo** (100 bệnh nhân, truy cập mở, theo trí nhớ, chưa xác minh trang) có thể xem trước dữ liệu thật mà không cần credentialed.

### 11.1. Đã tải MIMIC-IV Demo 2.2 để tham khảo (18/11/2026)
Lưu ở `data/tham_khao/mimic-iv-demo/` (ODbL, `.gitignore`, xem `data/tham_khao/README.md`). Chỉ dùng tham khảo cấu trúc và tập quán kê đơn; **không chép dòng** vào hồ sơ giả lập. Các trường còn thiếu so với dự án (dị ứng, thai/cho con bú, diễn biến theo ngày, đáp án lỗi) sẽ **suy luận và tự tạo** trong bộ sinh.

Quan sát từ bản demo (100 bệnh nhân, 275 lượt nhập viện, 45.154 dòng `poe`, 18.087 dòng `prescriptions`, 15.306 dòng `pharmacy`, 35.835 dòng `emar`):
- **Nhiều lần vào viện:** 52 người 1 lần, 20 người 2 lần, 9 người 3 lần, 19 người từ 4 đến 20 lần.
- **Y lệnh có vòng đời:** `poe.transaction_type` = New (34.625), Change (5.521), D/C (4.989); `discontinue_of_poe_id` / `discontinued_by_poe_id` nối y lệnh cũ và mới. **Khớp** với `thay_the_y_lenh_id` ở mục 5.2.
- **Y lệnh thuốc là phần lớn** (20.328 / 45.154); còn lại xét nghiệm, chăm sóc, truyền dịch, chẩn đoán hình ảnh… Mỗi y lệnh thuốc nối `prescriptions` (dòng thuốc, `drug_type` MAIN/BASE/ADDITIVE), `pharmacy` (xác nhận `verifiedtime`, `frequency`, `disp_sched`, trạng thái) và `emar` (giờ dự kiến `scheduletime` và giờ thật `charttime`; có `Not Given` 2.486 dòng).
- **Trạng thái y lệnh ở `pharmacy`:** Discontinued, Discontinued via patient discharge, Expired, Inactive (Due to a change order). Gợi ý thêm trạng thái "hết hạn" và "ngưng do ra viện".
- **Tần suất thực tế:** ONCE, DAILY, BID, Q8H, TID, PRN, Q6H, Q4H:PRN; có nhiều y lệnh khi cần (PRN).
- **Đường dùng:** IV 8.219, PO/NG 3.841, PO 2.191, SC 1.249, IV DRIP 1.026, IM 370.
- **Liều thực tế mẫu:** vancomycin 1000 mg phổ biến nhất (170/291 dòng); ceftriaxon 1 g (39) và 2 g (18); warfarin 5 mg (34), 2,5 mg, 3 mg; furosemide 20 mg (202), 40 mg (132); metoprolol 12,5 / 25 / 50 mg.
- **Thuốc trong bộ 50 của dự án có mặt:** vancomycin (291), warfarin (129), furosemide (511), metoprolol (449), heparin (600), amiodaron (113), ceftriaxon (58), piperacillin (59), meropenem (43), levofloxacin (33)…; ít hoặc không có: gentamicin (2), metformin (18), spironolacton (21).
- **Xét nghiệm:** creatinin của cả 100 bệnh nhân (3.003 dòng, đơn vị mg/dL, có khoảng tham chiếu và cờ `abnormal`). Cân nặng ở `omr`: 69/100 bệnh nhân (đơn vị lb), chiều cao ít hơn. Hồ sơ mới của dự án dùng umol/L và kg: cần quy đổi khi tham khảo.
- **Vi sinh:** 43/100 bệnh nhân có kháng sinh đồ; S 818, R 190, I 28; vi khuẩn hay gặp E. coli, S. aureus, Klebsiella, Pseudomonas.

**Tác động lên thiết kế (mục 5.2 và bộ sinh):**
1. Thêm `loai_thay_doi` (New/Change/D/C) hoặc suy ra từ `thay_the_y_lenh_id` và `ly_do_ngung`.
2. Thêm bảng/mảng `thuc_hien_y_lenh` kiểu `emar`: `thoi_diem_du_kien`, `thoi_diem_thuc_te`, `ket_qua` (đã dùng / không dùng / trì hoãn). Dùng để sinh ca "thiếu liều tối" thật hơn là chỉ sai lịch dùng.
3. Thêm `thoi_diem_duoc_si_xac_nhan` ở y lệnh (tương ứng `pharmacy.verifiedtime`).
4. Bộ sinh lấy liều, đường, tần suất theo bảng phân bố thật (ví dụ vancomycin 1000 mg), thay cho số do LLM nghĩ ra.
5. Thêm y lệnh khi cần (`PRN`) và y lệnh một lần (`ONCE`) vào bộ.
