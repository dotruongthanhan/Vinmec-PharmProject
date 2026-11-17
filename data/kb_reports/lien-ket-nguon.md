# Kiểm tra liên kết nguồn DailyMed

Chạy bằng web/scripts/verifySourceLinks.ts trên 50 nhãn, 3730 đoạn nguồn.

| Chỉ số | Kết quả |
| :--- | :--- |
| Đoạn có số mục (sinh được neo) | 3080/3730 (82.6%) |
| Neo `section-N` có thật trên trang | 3077/3080 (99.9%) |
| Câu trích mô phỏng tìm thấy đủ hai đầu, đúng thứ tự | 2885/3730 (77.3%) |
| Đạt cả hai (neo đúng nếu có, và câu trích thấy) | 2883/3730 (77.3%) |
| Trong số tìm thấy, phần mở đầu xuất hiện nhiều lần trên trang (có thể tô sáng sai chỗ) | 953/2885 (33.0%) |

## Lỗi theo nguyên nhân

### Câu trích không tìm thấy trên trang (khác khoảng trắng, ký tự lạ, hoặc nằm trong bảng): 845

- DT-30337ccc5cbc · Indications and Usage
- DT-aea88b622cee · Dosage and Administration > 2.4 Recommended Dosage for Treatment of Fever in Neonates and
- DT-31f0f9f8b656 · Adverse Reactions > 6.1 Clinical Trial Experience
- DT-71788a0225c9 · Adverse Reactions > 6.1 Clinical Trial Experience
- DT-5305fab25484 · Clinical Pharmacology > 12.1 Mechanism of Action
- DT-f9c89d0bcd21 · Clinical Pharmacology > 12.3 Pharmacokinetics Distribution
- DT-402d080feaab · Indications and Usage
- DT-c763ed001e71 · Dosage and Administration
- DT-06bddd09c3c9 · Dosage and Administration
- DT-2cfee8812b5c · Dosage and Administration
- DT-c32cf07f98f3 · Contraindications
- DT-4fc92fafc244 · Precautions
- DT-c04cd66ee295 · Drug Interactions
- DT-7467cf9e9ef1 · Adverse Reactions
- DT-cac282d70b8a · Adverse Reactions
- … và 830 đoạn nữa

### Neo mục không có trên trang (trang chưa đánh số kiểu section-N, hoặc đánh số lại): 2

- DT-f60cc7532104 · Clinical Pharmacology
- DT-504022b16657 · Clinical Pharmacology
