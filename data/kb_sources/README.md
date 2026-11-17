# data/kb_sources – tệp nguồn tri thức thuốc

Tệp gốc tải từ nguồn chính thống, **chưa qua xử lý**. Mọi tệp có dòng trong `manifest.json` (nguồn, tầng tin cậy, giấy phép, phiên bản, đường dẫn gốc, mã băm SHA-256). Kho tri thức dựng lại từ thư mục này bằng `python -m app.kb.build` (plan 1.1 mục 5–6, task T04a).

Ngày lấy: 16/11/2026. Không có dữ liệu người bệnh trong thư mục này.

## 1. Đã có

| Thư mục | Nguồn | Tầng | Giấy phép | Nội dung | Dùng cho |
| :--- | :--- | :-: | :--- | :--- | :--- |
| `openfda/` | openFDA Drug Label API (`api.fda.gov/drug/label.json`), bản nhãn mới nhất theo `effective_time` | 3 | Phạm vi công cộng | 50 nhãn thuốc kê đơn, mỗi hoạt chất một tệp JSON đã chia mục: chỉ định, liều, chống chỉ định, cảnh báo, tương tác, nhóm đặc biệt (thận, gan, thai kỳ, nhi, cao tuổi), bảng liều dạng HTML | Căn cứ trích dẫn cho yếu tố 1, 3, 4, 5, 6; rút bảng chỉnh liều theo thận / gan |
| `ddinter/` | DDInter 2.0 (`ddinter2.scbdd.com/download/`), 14 tệp CSV theo nhóm ATC | 4 | CC BY-NC-SA 4.0, **phi thương mại** | 507.655 dòng, 234.981 cặp không trùng. Chỉ có **tên hai thuốc và mức độ** (Major 39.082 · Moderate 143.748 · Minor 9.736 · Unknown 42.415); không có cơ chế hay xử trí | Sàng lọc yếu tố 4. Luôn ghi "cần đối chiếu"; không dùng làm căn cứ kết luận |

Danh sách 50 hoạt chất là **danh sách tạm** trong lúc chờ câu Q10 (dược sĩ chốt): 6 hoạt chất của ca demo cộng kháng sinh cần chỉnh liều theo thận, chống đông, tim mạch khoảng điều trị hẹp, giảm đau opioid, chống động kinh, và thuốc thường gặp.

## 2. Đã kiểm khi tải

- **Bảng chỉnh liều meropenem theo thận** trong `data/kb/quy_tac_lieu_than.json` đã đối chiếu với nhãn gốc (`openfda/meropenem.json`, Meropenem for Injection, `set_id` `31dd2160-7dbd-51fa-e054-00144ff88e88`, hiệu lực 02/11/2026): CrCl > 50 liều khuyến cáo mỗi 8 giờ · 26–50 liều khuyến cáo mỗi 12 giờ · 10–25 một nửa liều mỗi 12 giờ · < 10 một nửa liều mỗi 24 giờ. **Khớp cả 4 mức.** Vẫn cần dược sĩ duyệt.
- Ba nhãn lấy nhầm sản phẩm ở lượt đầu đã lấy lại bằng tên chính xác: `cefepime` (lượt đầu ra phối hợp zidebactam), `acetaminophen` (lượt đầu ra phối hợp oxycodon; đã lấy bản truyền tĩnh mạch đơn chất), `amikacin` (lượt đầu ra dạng hít; đã lấy bản tiêm).
- DDInter: thử vài cặp đã biết, mức độ hợp lý (clarithromycin – simvastatin Major, meropenem – acid valproic Major, amiodaron – digoxin Major).

## 3. Lưu ý khi dùng

- Nhãn FDA là nhãn Mỹ: biệt dược, hàm lượng, chỉ định được duyệt có thể khác Việt Nam. Liều và chống chỉ định phải được dược sĩ duyệt trước khi thành luật.
- Mỗi tệp openFDA là **một** nhãn của **một** nhà sản xuất (bản cập nhật gần nhất), không phải nhãn biệt dược gốc. Một số là dạng uống trong khi viện dùng dạng tiêm (`levofloxacin`, `ciprofloxacin`, `metoprolol`, `fluconazole`, `acyclovir`, `ketorolac`); `insulin_glargine` là bản tương tự sinh học; `methotrexate` là dung dịch uống. Khi chốt danh mục cần lấy đúng dạng bào chế viện dùng.
- DDInter có giấy phép phi thương mại: dùng được cho bản thử học thuật; đưa vào vận hành ở bệnh viện tư phải xin phép tác giả. Cân nhắc không đưa thư mục `ddinter/` (22 MB) vào git.
- Mức `Unknown` của DDInter nghĩa là **chưa có dữ liệu**, không phải "không tương tác".

## 4. Chưa lấy được

| Nguồn | Tình trạng | Việc cần làm |
| :--- | :--- | :--- |
| Quyết định 5948/QĐ-BYT (danh mục tương tác chống chỉ định) | Không tìm thấy bản PDF có chữ ký trên trang Bộ Y tế; `luatvietnam.vn` yêu cầu đăng nhập; trang tra cứu `tuongtacthuoc.ehealth.gov.vn` không kết nối được ngày 16/11 | **Nhờ Khoa Dược cấp bản chính thức** rồi nhập tay thành bảng `tuong_tac`. Đây là nguồn tầng 1 cho yếu tố 4 |
| Dược thư Quốc gia Việt Nam (lần xuất bản thứ ba) | Chưa có bản chính thức và quyền dùng | Hỏi Khoa Dược (câu Q4) |
| Thực phẩm chức năng: NIH Office of Dietary Supplements | API trả mã 403 khi gọi bằng lệnh | Tải tay từ `ods.od.nih.gov` hoặc xin khoá; để sau demo |
| LiverTox, LactMed (NCBI Bookshelf) | Chưa tải | Sau demo, theo danh mục hoạt chất đã chốt |
| Bảng dị ứng chéo có cấu trúc | Không có nguồn mở có cấu trúc | Rút từ mục chống chỉ định của nhãn, dược sĩ duyệt |

## 5. Nguồn không dùng

`doctorabad.com/uptodate/`: bản sao Lexicomp Drug Interactions của Wolters Kluwer, dữ liệu đóng băng 04/2018. Không tải, không nạp. Lý do ở `plan/TRACKING.md` (nhật ký 16/11).
