# Danh mục dữ liệu

Từ 19/11/2026, thư mục `data/` không còn trên git, trừ `data/mock`, `data/gold`, `data/kb`. Vì vậy mọi thông tin **về** dữ liệu ghi ở đây, trong git, để cả nhóm đọc được mà không cần mở tệp.

## Quy tắc (người dùng chốt 19/11)

- **Mỗi bộ dữ liệu có một tệp `.md` riêng** trong thư mục này. Tệp ghi:
  - nguồn, giấy phép, tầng tin cậy, ngày lấy, lệnh tải và xử lý;
  - đường dẫn ba tầng: thô → trung gian → bộ tra;
  - **từng trường**: ý nghĩa, app có dùng không;
  - số dòng, kích thước, kết quả kiểm;
  - việc còn mở.
- Ai tải mới, cào thêm hay đổi cách xử lý thì **cập nhật tệp `.md` cùng lúc**. Áp dụng cho cả agent.
- Cần biết một bộ dữ liệu có gì thì **đọc tệp ở đây trước**, không mở dữ liệu ra dò lại. Nếu thấy tệp lỗi thời thì sửa nó.

## Danh mục

| Bộ dữ liệu | Tệp mô tả | Dùng cho | Trạng thái |
|:--|:--|:--|:--|
| DDInter 2.0 (tương tác) | [ddinter.md](ddinter.md) | Yếu tố 4 | ✅ cập nhật 19/11 |
| Cục Quản lý Dược (số đăng ký) | [dav.md](dav.md) | Từ điển thuốc | ✅ cập nhật 19/11 (T59) |
| RxNav / RxClass (RxNorm, ATC) | [rxnav.md](rxnav.md) | Trục hoạt chất, ATC | ✅ cập nhật 19/11 (T59) |
| Từ điển thuốc và bộ tra `tra_cuu.sqlite` | [tu-dien-tra-cuu.md](tu-dien-tra-cuu.md) | Bộ phân giải tên, yếu tố 2, 4 | ✅ cập nhật 19/11 (T59) |
| openFDA nhãn + NDC, đoạn RAG `chunks.jsonl`, cache nhúng | [openfda-rag.md](openfda-rag.md) | Căn cứ trích dẫn, RAG | ✅ cập nhật 19/11 (T59) |
| LiverTox | [livertox.md](livertox.md) | Yếu tố 5, 6 (sau demo) | ✅ cập nhật 19/11 (T59) |
| LactMed | [lactmed.md](lactmed.md) | Yếu tố 6 (hoãn) | ✅ cập nhật 19/11 (T59) |
| Văn bản Bộ Y tế (VBHN 15, TT 37, QĐ 5631) | [van-ban-byt.md](van-ban-byt.md) | Yếu tố 2, 3, 7 | ✅ cập nhật 19/11 (T59) |
| Ca giả lập, hồ sơ, đáp án | [ca-gia-lap.md](ca-gia-lap.md) | Toàn bộ | ✅ cập nhật 19/11 (T59) |
| Dị ứng chéo theo nhóm `data/kb/di_ung_cheo.json` (T60, D3) | [di-ung-cheo.md](di-ung-cheo.md) | Yếu tố 1 (dị ứng) | ⏳ chờ dược sĩ duyệt, cập nhật 19/11 |

Tài liệu cũ `data/kb_sources/README.md` (16–17/11) đã lỗi thời và không còn trên git; nội dung còn đúng được chuyển sang các tệp trên.
