# T81 – Yếu tố 5 (độc tính) hiện "Chưa có luật" dù luật đã chạy; trang giới thiệu ghi trạng thái cũ

Agent: **agy Gemini 4 Hydrogen high**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.**

## Lỗi (Claude kiểm DEMO-02, DEMO-06 trên web)

- Luật độc tính `app/rules/toxicity.py` (T71) đã nối engine và chạy cho mọi ca, nhưng **chỉ sinh nhận định khi thuốc nằm trong danh sách** (độc thận, kéo dài QT, khoảng điều trị hẹp, độc gan LiverTox, nguy cơ cao). Ca không có thuốc nào trong danh sách (DEMO-02 meropenem, DEMO-06 amoxicillin) → không có nhận định yếu tố 5 → web (`web/src/lib/orderDetail.ts::computeSixFactorsStatus`) hiện **"Chưa có luật"**. Sai: luật có chạy.
- Các luật khác đều có nhận định `dat` khi không phát hiện (ví dụ `di_ung_khong_co` trong `app/rules/allergy.py`).

## Sửa

1. `app/rules/toxicity.py`: khi ca có ít nhất một dòng thuốc đang hiệu lực đã phân giải được hoạt chất, và **không** dòng nào sinh nhận định yếu tố 5, thêm **một** nhận định `ma_luat="doc_tinh_khong_thuoc_danh_sach"`, `yeu_to=5`, `ket_luan="dat"`, `muc_do="thong_tin"`, `chi_tiet_y_lenh_id` = các dòng đã xét, mô tả: "Không thuốc nào thuộc danh sách theo dõi độc tính (độc thận, kéo dài QT, khoảng điều trị hẹp, độc gan LiverTox) trong nguồn đã lấy", căn cứ là bảng `doc_tinh` (phiên bản). Dòng chưa phân giải được hoạt chất → **không** tính là đạt (giữ nguyên quy tắc "thiếu dữ liệu không ghi đạt"); nếu mọi dòng đều chưa phân giải → không sinh nhận định này.
2. `web/src/features/landing/LandingPage.tsx` dòng ~30–36: mảng `FACTORS` còn ghi yếu tố 4 `ready: false`, yếu tố 5 "Chưa có luật trong bản thử nghiệm". Cập nhật theo hiện trạng: cả 7 yếu tố đã có luật (4: tương tác DDInter; 5: độc thận, QT, khoảng điều trị hẹp, độc gan; 6: thận, gan, xét nghiệm, thuốc–bệnh; 7: kháng sinh quản lý, trường bắt buộc). Ghi chú ngắn, không hứa quá.
3. Cập nhật test có kiểm số nhận định / danh sách `ma_luat` bị ảnh hưởng (so tập con hoặc tính theo luật, như T69-fix-1). Thêm test: ca chỉ có meropenem → đúng 1 nhận định `doc_tinh_khong_thuoc_danh_sach`; ca có gentamicin → không có nhận định này; ca mọi dòng chưa phân giải → không có.

## Phạm vi

`app/rules/toxicity.py`, `web/src/features/landing/LandingPage.tsx`, test liên quan (`tests/rules/test_toxicity.py`, test API/engine đếm nhận định, test web nếu có cho landing). Cấm `data/`, lược đồ. Định dạng `ruff format`; web giữ `oxlint`, `tsc` sạch. Báo cáo `plan/reports/T81.md`.
