> **LỖI THỜI từ 19/11/2026.** Tệp này viết ngày 16–17/11. Mô tả hiện hành của từng nguồn ở `docs/du-lieu/` (DDInter: `docs/du-lieu/ddinter.md`, Cục Quản lý Dược: `dav.md`, openFDA: `openfda-rag.md`…). Thư mục `data/kb_sources/` không còn trên git, chỉ giữ tệp README này. CSV DDInter cũ đã chuyển sang `data/_luu_tru/ddinter_csv_2026-11-16/`.

# data/kb_sources – tệp nguồn tri thức thuốc

Tệp gốc tải từ nguồn chính thống, **chưa qua xử lý**. Mọi tệp có dòng trong `manifest.json` (nguồn, tầng tin cậy, giấy phép, phiên bản, đường dẫn gốc, mã băm SHA-256). Kho tri thức dựng lại từ thư mục này bằng `python -m app.kb.build` (plan 1.1 mục 5–6, task T04a).

Ngày lấy: 16/11/2026. Không có dữ liệu người bệnh trong thư mục này.

## 1. Đã có

| Thư mục | Nguồn | Tầng | Giấy phép | Nội dung | Dùng cho |
| :--- | :--- | :-: | :--- | :--- | :--- |
| `openfda/` | openFDA Drug Label API (`api.fda.gov/drug/label.json`) | 3 | Phạm vi công cộng | 50 nhãn tải tay ngày 16/11 (42 nhãn đã khớp cấu hình; 8 mục cần lấy lại gồm 6 nhãn đổi đường dùng, `insulin_glargine` bản gốc, và `enoxaparin` có `generic_name` dài). Đã có lệnh tải lại nhiều bậc (`T25-fix-1`) | Căn cứ trích dẫn cho yếu tố 1, 3, 4, 5, 6; rút bảng chỉnh liều theo thận / gan |
| `openfda_ndc/` | openFDA NDC Directory API (`api.fda.gov/drug/ndc.json`) | 3 | Phạm vi công cộng | 46 tệp sản phẩm đã tải ở T25; 4 mục thiếu (`imipenem_and_cilastatin`, `meropenem`, `valproate`, `warfarin`) đã có truy vấn nhiều bậc ở T25-fix-1 để tải bổ sung | Dựng bảng biệt dược → hoạt chất và nhóm dược lý |
| `ddinter/` | DDInter 2.0 (`ddinter2.scbdd.com/download/`), 14 tệp CSV theo nhóm ATC | 4 | CC BY-NC-SA 4.0, **phi thương mại** | 507.655 dòng, 234.981 cặp không trùng. Chỉ có **tên hai thuốc và mức độ** (Major 39.082 · Moderate 143.748 · Minor 9.736 · Unknown 42.415); không có cơ chế hay xử trí | Sàng lọc yếu tố 4. Luôn ghi "cần đối chiếu"; không dùng làm căn cứ kết luận |

Danh sách 50 hoạt chất là **danh sách tạm** trong lúc chờ câu Q10 (dược sĩ chốt): 6 hoạt chất của ca demo cộng kháng sinh cần chỉnh liều theo thận, chống đông, tim mạch khoảng điều trị hẹp, giảm đau opioid, chống động kinh, và thuốc thường gặp.

T25 / T25-fix-1 ngày 17/11/2026: đã có danh mục `config/kb/hoat_chat_can_lay.yaml`, lệnh tải nhãn/NDC nhiều bậc và báo cáo `data/kb_reports/openfda_do_phu.md` / `.json`. Sau khi người review chạy lại các lệnh tải ở mục 6, các nhãn đổi đường dùng và 4 tệp NDC còn thiếu sẽ được cập nhật kèm bậc truy vấn trong `manifest.json` và báo cáo trong `data/kb_reports/openfda_fetch_openfda.json` / `openfda_fetch_ndc.json`.

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

## 6. Tải lại openFDA và lập báo cáo (T25)

Chạy từ thư mục gốc dự án:

```bash
uv run python -m app.kb.fetch openfda --dry-run
uv run python -m app.kb.fetch openfda
uv run python -m app.kb.fetch ndc
uv run python -m app.kb.fetch report
uv run python -m app.kb.build
```

- Danh mục khởi tạo đúng 50 mã đang có; dược sĩ sửa `hoat_chat`, `ma`, `duong_dung`, `ghi_chu` khi chốt. `hoat_chat` là tên chung tiếng Anh chính xác theo API. Dạng phối hợp phải khai báo thêm `thanh_phan` khớp từng `openfda.substance_name`; không tự chấp nhận phối hợp khác.
- `--only meropenem,vancomycin` giới hạn hoạt chất cần tải. `--refresh` lấy lại kể cả khi SHA-256 khớp; dùng `uv run python -m app.kb.fetch openfda --refresh` để đánh giá lại tối đa 25 ứng viên cho toàn bộ nhãn tải tay. Không cần khóa; nếu có, đặt biến môi trường `OPENFDA_API_KEY`. Khóa không được ghi vào câu truy vấn lưu manifest hoặc log.
- Mặc định bỏ qua tệp khớp mã băm và đúng tên, thành phần, loại sản phẩm, đường dùng trong cấu hình. Tệp cũ sai đường dùng hoặc tên vẫn được lấy lại và thay thế trực tiếp theo quy tắc đặt tên (mã đoạn của nhãn bị thay sẽ đổi và được đếm trong báo cáo dựng kho).
- Chiến lược truy vấn nhiều bậc (T25-fix-1), dừng ở bậc đầu tiên có ứng viên qua quy tắc chọn: (1) `generic_name.exact` viết hoa; (2) `substance_name.exact` (nhãn) hoặc `active_ingredients.name.exact` (NDC) viết hoa; (3) `generic_name:"<tên>"` không `.exact`; (4) như bậc 3 với tên đã bỏ phần muối. Điều kiện `product_type` và `route` không dùng `.exact`.
- Kết cục và mã thoát của lệnh tải: `0` khi toàn bộ `da_lay` / `bo_qua`; `1` khi có `loi_ket_noi` (lỗi mạng, quá lượt thử lại 429/5xx, phản hồi hỏng); `2` khi có `khong_co_ung_vien_hop_le` (có kết quả API nhưng không ứng viên nào qua quy tắc chọn; báo cáo ghi lý do loại của 3 ứng viên đầu); `3` khi có `khong_tim_thay` (API trả 404 ở mọi bậc). Mỗi mục vẫn chạy tiếp khi mục khác lỗi, không thay tệp cũ nếu thất bại.
- T25-fix-3: phản hồi HTTP 200 hỏng JSON hoặc sai cấu trúc được tách thành `phan_hoi_sai_cau_truc`, kèm lý do cụ thể và dòng riêng trong báo cáo, dùng chung mã thoát `1` (cần chạy lại) với `loi_ket_noi`; không ghi đè tệp nguồn cũ và vẫn chạy hoạt chất kế.
- Một đường dùng giữ `<ma>.json`; nhiều đường dùng lưu `<ma>__intravenous.json`, `<ma>__oral.json`, v.v. Khi đủ nhãn thay thế cho các đường dùng, bỏ mục manifest tên cũ, giữ tệp gốc cũ trên đĩa để đối chiếu. Cùng `set_id` được dựng thành đoạn một lần từ phiên bản mới nhất.
- Chỉ chọn đơn chất khớp tên sau chuẩn hóa muối đã có trong dự án, hoặc đúng các thành phần phối hợp đã khai báo (kể cả ở bậc truy vấn lỏng). Ưu tiên số nhóm mục hiện diện (chỉ định, liều, chống chỉ định, cảnh báo, tương tác, nhóm đặc biệt, bảng liều), rồi `effective_time` mới nhất, rồi `set_id` tăng dần. Giữ nguyên đối tượng JSON nhãn được chọn trong `results[0]`; không dịch hay sửa nội dung.
- NDC được phân trang, lọc theo quy tắc đơn chất/phối hợp và loại sản phẩm, bỏ trùng theo biệt dược, tên chung, thành phần/hàm lượng, dạng bào chế và đường dùng. Trường nguồn thiếu giữ `null` hoặc danh sách rỗng; không suy diễn hàm lượng. Manifest ghi `bac_truy_van`, `truy_van` không có khóa, số ứng viên, ngày lấy, SHA-256 và siêu dữ liệu nguồn.
- `report` quét nhãn trên đĩa, không gọi mạng; báo cả nhãn gốc cũ giữ để đối chiếu. Chỉ dấu mục thận dựa vào văn bản, chưa phải quy tắc liều đã duyệt. Sau `build`, cuối báo cáo có số nhãn/đoạn trước và sau, số mã bị thay, số mã của nội dung không đổi bị thay, và dòng nghiệm thu.
- Cấu hình dùng `INTRAVENOUS` cho sáu khoảng thiếu dạng tiêm trong README; metoprolol dùng mục `metoprolol_tartrate`, giữ `metoprolol_succinate` là `ORAL`. README chưa xác định đường dùng thay thế cho methotrexate nên giữ `ORAL`, ghi rõ cần dược sĩ chốt trong cấu hình/báo cáo.
