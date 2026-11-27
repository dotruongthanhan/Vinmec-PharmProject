TRẠNG THÁI: **CHƯA XONG** — phần máy chủ và web đã được sửa, nhưng kiểm thử vitest bổ sung cho ba ví dụ prompt chưa được chạy bằng vitest, và bố cục chưa được đo trên trình duyệt.

FILE ĐÃ TẠO / SỬA: Bộ kiểm máy chủ, prompt minh hoạ, kiểm thử Python, các tệp web minh hoạ và mock trong phạm vi brief. Mẫu demo đã được tách thành bản vi phạm và bản đã chỉnh. Chi tiết có trong [báo cáo VZ1-fix-1](/D:/create/Vinmec-PharmProject/plan/briefs/VZ1-fix-1-bao-cao.md).

LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:

- Hai tệp pytest chạy riêng với `--basetemp` trong `%TEMP%`: **40 đạt** và **19 đạt**. Tệp đồ thị ban đầu có 10 lỗi do ví dụ prompt chưa được sửa vì lỗi mã hoá; sau khi sửa, chạy lại đạt.
- Ruff check và format check: đạt. TypeScript và build web: đạt. Oxlint đạt, còn một cảnh báo ở tệp ngoài phạm vi sửa.
- Lượt `vitest run` duy nhất: **49 tệp, 406 kiểm thử đạt**.
- Kiểm tra độc lập bằng Node: ba ví dụ prompt được bộ kiểm web chấp nhận; ở creatinin 121, CrCl đang xem và mức liều khớp cùng dữ liệu tra.

ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO: Kiểm thử vitest cho ba ví dụ prompt được thêm sau lượt chạy duy nhất; các ví dụ đã được kiểm bằng Node nhưng chưa chạy qua vitest. Bố cục 320 và 399 px mới được kiểm tĩnh qua lớp CSS.

VIỆC CHƯA LÀM / CÂU HỎI: Cần chạy kiểm thử vitest bổ sung và xác nhận độ dài dòng, tràn ngang trên trình duyệt khi thực hiện e2e.