# T85 – Mã nhận định trùng khi thuốc phối hợp; nhãn công thức không dấu

Agent: **agy Gemini 4 Hydrogen high**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.**

## 1. Mã nhận định trùng (Claude thấy trên web, console React)

HS-056: thuốc phối hợp "Sulfamethoxazol + trimethoprim 800/160 mg" (dòng `CT-HS-056-05-01`) sinh **hai** nhận định `lieu_toi_da_khong_co_nguon` (một cho sulfamethoxazole, một cho trimethoprim) – đúng về luật. Nhưng `nhan_dinh_id` dựng từ `ca_id::ma_luat|chi_tiet_y_lenh_id` (xem `app/api/presenter.py`) → **trùng**: `HS-056::lieu_toi_da_khong_co_nguon|CT-HS-056-05-01`. Hậu quả: React cảnh báo trùng khoá; **phản hồi dược sĩ, liên kết "Mở nhận định", kết quả AI gắn theo `nhan_dinh_id` có thể nhầm giữa hai nhận định.**

Sửa: `nhan_dinh_id` phải duy nhất trong một ca **và ổn định giữa các lần chạy** (phản hồi đã lưu dùng nó). Giữ nguyên dạng hiện tại cho nhận định không trùng (không làm hỏng phản hồi cũ); khi trùng, thêm hậu tố ổn định suy từ nội dung phân biệt (ví dụ hoạt chất trong nhận định: `…|CT-HS-056-05-01|trimethoprim`, hoặc băm ngắn của `mo_ta`), không dùng thứ tự xuất hiện. Kiểm mọi nơi tạo hoặc so `nhan_dinh_id` (presenter, AI review, phản hồi, ghi `ket_qua_nhan_dinh`). Test: HS-056 có 2 id khác nhau, chạy hai lần cho cùng id; toàn bộ 66 ca không có id trùng.

## 2. Nhãn công thức không dấu (trang Tính toán)

Trang `/app/cong-thuc/cockcroft_gault` hiện nhãn "loai can nang" và lựa chọn "thuc te / ly tuong / hieu chinh". Thêm nhãn hiển thị tiếng Việt có dấu cho các trường và lựa chọn trong `config/kb/cong_thuc.yaml` (ví dụ `nhan: "Loại cân nặng"`, `nhan_lua_chon: {thuc_te: "Thực tế", ly_tuong: "Lý tưởng", hieu_chinh: "Hiệu chỉnh"}`), trả qua `GET /api/cong-thuc` (cập nhật hợp đồng v1.8 + schema) và để web hiện nhãn đó (giữ giá trị gửi đi như cũ). Rà toàn bộ 14 công thức (`co_truong`, `nao_gan`, giới tính…).

## Phạm vi

`app/api/presenter.py` và nơi liên quan tới `nhan_dinh_id`, `app/api/formulas.py`, `app/api/schemas.py`, `config/kb/cong_thuc.yaml` (chỉ thêm nhãn), `plan/api-hop-dong-v1.8-tra-cuu.md`, `web/src/features/lookup/FormulaPages.tsx`, `web/src/api/types.ts`, test liên quan. Báo cáo `plan/reports/T85.md`.
