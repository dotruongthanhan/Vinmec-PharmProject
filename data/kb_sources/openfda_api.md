# openFDA API – có gì, dùng được gì cho thẩm định y lệnh

Khảo sát ngày 17/11/2026 bằng lệnh gọi thật. Phản hồi mẫu lưu ở `data/kb_sources/openfda_api_mau/` (10 tệp `limit=1` của từng điểm cuối và 11 tệp truy vấn thử với meropenem). Lệnh tải dùng lại được: task T25 (`python -m app.kb.fetch`).

## 1. Cách gọi

- Gốc: `https://api.fda.gov/<nhóm>/<điểm cuối>.json`. Chỉ có `GET`, trả JSON gồm `meta` (ngày cập nhật, tổng số kết quả) và `results`.
- Tham số: `search=<trường>:<giá trị>` (nối bằng `AND`, `OR`; thêm `.exact` để khớp nguyên cụm), `sort=<trường>:desc`, `limit` (tối đa 1000), `skip` (tối đa 25000), `count=<trường>` (đếm theo giá trị, trả `term` và `count`).
- Không tìm thấy: mã **404** với `{"error": {"code": "NOT_FOUND"}}`. Phải coi là "không có kết quả", không phải lỗi mạng.
- Hạn mức (theo tài liệu của openFDA): không khoá 240 lượt/phút và 1.000 lượt/ngày mỗi địa chỉ IP; có khoá miễn phí 240 lượt/phút và 120.000 lượt/ngày. Nếu mở rộng danh mục hoạt chất nên xin khoá và đặt vào `.env` với tên `OPENFDA_API_KEY`.
- Cần toàn bộ dữ liệu thì tải tệp nén theo danh sách ở `https://api.fda.gov/download.json`, không phân trang qua API.
- Giấy phép: phạm vi công cộng (CC0). openFDA ghi rõ dữ liệu không dùng để ra quyết định lâm sàng trực tiếp.

## 2. Các điểm cuối về thuốc (đã gọi, đều trả 200)

| Điểm cuối | Số bản ghi | Cập nhật | Nội dung | Giá trị cho dự án |
| :--- | --: | :--- | :--- | :--- |
| `drug/label` | 264.800 (37.312 là thuốc kê đơn) | 16/11/2026 | Nhãn thuốc đã chia mục | **Nguồn chính (tầng 3).** Đang dùng |
| `drug/ndc` | 138.487 | 16/11/2026 | Danh mục sản phẩm: biệt dược, tên chung, hoạt chất và hàm lượng, dạng bào chế, đường dùng, nhóm dược lý | **Nên dùng.** Dựng bảng tên thuốc → hoạt chất và bảng nhóm dược lý |
| `drug/event` | 21.054.159 | 28/10/2026 | Báo cáo biến cố bất lợi tự nguyện (FAERS) | Chỉ làm tín hiệu tham khảo, xem mục 4 |
| `drug/drugsfda` | 29.460 | 16/11/2026 | Hồ sơ phê duyệt: sản phẩm, hãng, tình trạng lưu hành, mã tương đương điều trị | Thấp. Chỉ để biết thuốc gốc tham chiếu |
| `drug/enforcement` | 18.166 | 11/11/2026 | Thu hồi thuốc tại Mỹ | Thấp. Không liên quan thẩm định một y lệnh |
| `drug/shortages` | 1.583 | 16/11/2026 | Thiếu thuốc tại Mỹ | Không dùng (thị trường Mỹ) |
| `other/substance` | 167.385 | 09/09/2026 | Chất: tên gọi khác, mã, cấu trúc | Có thể dùng để chuẩn hoá tên hoạt chất, sau demo |
| `other/unii` | 177.347 | 16/11/2026 | Mã UNII ↔ tên chất | Khoá nối giữa các điểm cuối |
| `other/nsde` | 672.900 | 16/11/2026 | Mã NDC và thời gian lưu hành | Không dùng |
| `other/historicaldocument` | 8.858 | 20/03/2024 | Thông cáo báo chí cũ của FDA | Không dùng |

**Không có điểm cuối riêng cho tương tác thuốc.** Tương tác chỉ có dưới dạng văn bản trong mục `drug_interactions` của nhãn. Bảng tương tác có cấu trúc vẫn phải lấy từ nguồn khác (QĐ 5948/QĐ-BYT, DDInter để sàng lọc).

## 3. `drug/label` – nhãn thuốc

Thử với meropenem (kê đơn, tiêm tĩnh mạch): 25 nhãn. Nhãn mới nhất (hiệu lực 02/11/2026, `set_id` `31dd2160-7dbd-51fa-e054-00144ff88e88`) có các mục:

- Dùng trực tiếp cho thẩm định: `indications_and_usage`, `dosage_and_administration` và `dosage_and_administration_table` (bảng liều dạng HTML, có bảng chỉnh liều theo thận), `dosage_forms_and_strengths`, `contraindications`, `warnings_and_cautions`, `drug_interactions`, `adverse_reactions`, `use_in_specific_populations`, `pregnancy`, `pediatric_use`, `geriatric_use`, `overdosage`.
- Dược lý: `clinical_pharmacology`, `pharmacokinetics` và `pharmacokinetics_table`, `pharmacodynamics`, `mechanism_of_action`, `microbiology`.
- Khác: `clinical_studies`, `how_supplied`, `storage_and_handling`, `recent_major_changes`, `information_for_patients`.
- Khối `openfda`: tên chung, biệt dược, hãng, đường dùng, `substance_name`, `unii`, `rxcui`, `spl_set_id`.

Lưu ý:

- Tên mục **không cố định**: nhãn theo định dạng cũ và nhãn không kê đơn dùng tên khác (`warnings` thay cho `warnings_and_cautions`, không có `use_in_specific_populations`). Bản ghi `limit=1` mặc định là một nhãn không kê đơn, chỉ có 12 mục. Phải lọc `openfda.product_type:"HUMAN PRESCRIPTION DRUG"`.
- Một hoạt chất có nhiều nhãn của nhiều hãng, nội dung gần giống nhau. Cần quy tắc chọn một nhãn (T25 mục 2.2).
- Là nhãn Mỹ: chỉ định, hàm lượng, biệt dược có thể khác Việt Nam.

Mẫu truy vấn:

```
/drug/label.json?search=openfda.generic_name.exact:"MEROPENEM"
  AND openfda.product_type:"HUMAN PRESCRIPTION DRUG"
  AND openfda.route:"INTRAVENOUS"&sort=effective_time:desc&limit=1
```

## 4. `drug/event` – báo cáo biến cố bất lợi (đường dẫn người dùng gửi)

Mỗi bản ghi là một báo cáo: mức nghiêm trọng, nước báo cáo, tuổi và giới người bệnh, danh sách thuốc (`medicinalproduct`, `drugindication`, `drugcharacterization`, đường dùng), danh sách phản ứng theo thuật ngữ MedDRA.

Thử đếm theo phản ứng:

- Meropenem, 5 phản ứng được báo cáo nhiều nhất: DRUG INEFFECTIVE 4.620 · OFF LABEL USE 3.390 · PYREXIA 2.230 · PNEUMONIA 1.510 · SEPTIC SHOCK 1.472. Phần lớn là **bệnh nền của người bệnh**, không phải tác dụng của thuốc.
- Meropenem dùng cùng acid valproic: DRUG INTERACTION 115 · DRUG LEVEL DECREASED 31 · ANTICONVULSANT DRUG LEVEL DECREASED 28 · SEIZURE 26. Khớp với tương tác đã biết trong nhãn.

Giới hạn bắt buộc phải ghi khi dùng:

- Báo cáo tự nguyện: không có mẫu số, không chứng minh quan hệ nhân quả, nhiễu bởi bệnh nền và chỉ định, có báo cáo trùng.
- **Không dùng làm căn cứ kết luận.** Nếu đưa vào sản phẩm thì chỉ ở mức "tín hiệu tham khảo, cần đối chiếu" cho yếu tố tương tác và độc tính, luôn kèm số báo cáo và câu giới hạn trên.
- Chỉ lưu **số đếm tổng hợp** (truy vấn `count=`). Không tải, không lưu báo cáo từng người bệnh vào kho dù đã ẩn danh.

## 5. `drug/ndc` – danh mục sản phẩm

Meropenem: 54 sản phẩm; dạng bào chế: bột pha dung dịch tiêm 28 · thuốc tiêm 20 · bột 4 · dung dịch tiêm 2. Một bản ghi cho: biệt dược, hoạt chất `MEROPENEM` hàm lượng `1 g/1`, đường `INTRAVENOUS`, và **nhóm dược lý** `Carbapenems [CS]`, `Penem Antibacterial [EPC]`.

Dùng cho: (1) bảng tên biệt dược → hoạt chất; (2) bảng hoạt chất → nhóm dược lý, làm đầu vào cho luật dị ứng cùng nhóm và luật trùng nhóm. Nhóm dược lý lấy từ đây vẫn cần dược sĩ duyệt trước khi thành luật.

## 6. Đề xuất thứ tự làm

1. **Ngay (T25):** lệnh tải `drug/label` dùng lại được, đúng đường dùng, kèm báo cáo độ phủ từng mục; tải `drug/ndc`.
2. **Sau T25:** dựng bảng nhóm dược lý từ `drug/ndc`, nối vào luật dị ứng cùng nhóm.
3. **Sau demo:** tín hiệu từ `drug/event` (số đếm cho cặp thuốc trong y lệnh), hiển thị ở mức tham khảo.
4. **Không làm:** `enforcement`, `shortages`, `nsde`, `historicaldocument`.
