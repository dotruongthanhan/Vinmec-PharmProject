# Dữ liệu tham khảo ngoài (không phải dữ liệu của dự án)

## `mimic-iv-demo/` – MIMIC-IV Clinical Database Demo 2.2
- Nguồn: https://physionet.org/content/mimic-iv-demo/2.2/ (PhysioNet; MIT Laboratory for Computational Physiology). DOI dự án MIMIC-IV: https://doi.org/10.13026/07hj-2a80
- Giấy phép: **ODC Open Database License (ODbL) 1.0** (xem `LICENSE.txt` trong thư mục giải nén). Khi dùng phải **ghi nguồn**; cơ sở dữ liệu phái sinh nếu công bố phải giữ cùng giấy phép.
- Nội dung: 100 bệnh nhân thật đã khử nhận dạng (Beth Israel Deaconess, Boston, 2011–2016), 275 lượt nhập viện; không có ghi chú văn bản tự do.
- Tải ngày 18/11/2026, tệp `mimic-iv-demo-2.2.zip` (16.189.661 byte), kiểm `SHA256SUMS.txt` đủ 34 tệp, 0 sai.
- Tải lại: `curl -L -o mimic-iv-demo-2.2.zip https://physionet.org/static/published-projects/mimic-iv-demo/mimic-iv-clinical-database-demo-2.2.zip`

### Quy định dùng trong dự án
1. **Chỉ để tham khảo** cấu trúc y lệnh, liều, đường dùng, tần suất, lịch giờ, chuỗi thay đổi y lệnh. **Không chép nguyên dòng** vào hồ sơ giả lập (`data/mock/**`); dữ liệu của dự án vẫn 100% giả lập.
2. Thư mục dữ liệu bị `.gitignore`, không commit; chỉ README này được commit.
3. Bản MIMIC-IV đầy đủ **không** nằm trong kho (cần credentialed, không chia sẻ lại).
