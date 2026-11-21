# Báo cáo T71-fix-1 – Luật D6: bỏ nhận định "thiếu ALT/AST" thừa, sửa định dạng

## Tóm tắt thay đổi

1. [app/rules/toxicity.py](file:///D:/create/Vinmec-PharmProject/app/rules/toxicity.py):
   - Trong `_doc_gan_livertox`: khi ca bệnh không có kết quả ALT hoặc AST dạng số (`not numeric_labs`), trả về `[]` ngay, bỏ nhánh sinh `PhatHien` mã `doc_gan_thieu_xet_nghiem` với `thong_tin_con_thieu=["alt_ast"]`.
   - Giữ nguyên nhánh `doc_gan_men_gan_tang`, `doc_gan_men_gan_binh_thuong` và nhánh có kết quả dạng số nhưng thiếu `nguong_tren` (`doc_gan_thieu_xet_nghiem`, `thong_tin_con_thieu=["nguong_tren_alt_ast"]`).
   - Trong `_crcl_evidences` (quanh dòng 164–170): tách `cr_time = creatinin_lab.thoi_diem_ket_qua.isoformat()` để chuỗi `mo_ta=f"Creatinin máu: {val} {unit} lúc {cr_time}"` nằm gọn trên một dòng (< 100 ký tự), bỏ ghép chuỗi nhiều dòng trong ngoặc tròn quanh dòng 169.
2. [tests/rules/test_toxicity.py](file:///D:/create/Vinmec-PharmProject/tests/rules/test_toxicity.py):
   - Trong `test_livertox_elevated_normal_missing_and_score_c`: cập nhật kỳ vọng `_amio_case([])` trả về `[]`, bổ sung kiểm tra trường hợp chỉ có ALT dạng chữ (`gia_tri_so=None`) cũng trả về `[]`, và giữ nguyên kiểm tra thiếu `nguong_tren` (`nguong_tren_alt_ast`).

## Kiểm chứng

- Chưa chạy lệnh `ruff` hoặc `pytest` vì brief và yêu cầu người dùng cấm gọi công cụ shell / mạng; các lệnh nghiệm thu ở mục `## Nghiệm thu (Claude chạy)` do Claude thực hiện sau bước này.
