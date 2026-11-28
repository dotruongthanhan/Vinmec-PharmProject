# T78 – Ghi kết quả thẩm định của hệ thống vào DB

Agent: **agy Gemini 4 Hydrogen xhigh**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Chạy **sau T77**; đọc `plan/reports/T75.md`…`T77.md`.

## Bối cảnh

Người dùng muốn: thêm một hồ sơ mới vào DB → thẩm định → **kết quả được lưu trong DB**. Hiện tại `CaseService.get_case` (`app/api/service.py`) chạy luật và chỉ giữ kết quả trong bộ nhớ tiến trình; không ghi gì vào DB. Các bảng `nghiep_vu.lan_tham_dinh`, `nhan_dinh`, `nhan_dinh_thuoc`, `can_cu` đang chứa **đáp án mẫu (gold)** nạp từ `data/gold` – không phải kết quả hệ thống, **không ghi kết quả vào đó**.

## Yêu cầu

1. Lược đồ: `nghiep_vu.ket_qua_tham_dinh` (`ket_qua_id` uuid/text PK, `ca_id` FK, `thoi_diem timestamptz`, `phien_ban_luat` (sha256 hoặc phiên bản các bảng luật đã dùng), `so_luat_da_chay`, `che_do` (`file`/`db`), `tom_tat jsonb` (số mục theo kết luận / yếu tố)) và `nghiep_vu.ket_qua_nhan_dinh` (`ket_qua_id` FK, `thu_tu`, `ma_luat`, `yeu_to`, `ket_luan`, `muc_do`, `chi_tiet_y_lenh_id jsonb`, `nhan_xet`, `can_cu jsonb`, `du_lieu_thieu jsonb`, các trường khác của phát hiện theo mô hình trả API). RLS + REVOKE theo mẫu. Ghi chú trong lược đồ: bảng `lan_tham_dinh`/`nhan_dinh` là đáp án mẫu.
2. Khi `CASE_SOURCE=db`: mỗi lần **chạy luật thật** (không phải lần đọc bộ đệm) cho một ca, ghi một `ket_qua_tham_dinh` + các `ket_qua_nhan_dinh` trong một giao dịch, qua kết nối ghi (không phải `read_pool` chỉ đọc – xem cách T76 ghi phản hồi). Ghi lỗi → log cảnh báo, **không** làm hỏng phản hồi API.
3. API đọc: `GET /api/cases/{id}/lich-su-tham-dinh` trả danh sách lần thẩm định (thời điểm, tóm tắt) – thêm vào `plan/api-hop-dong-v1.md` phần bổ sung nếu cần; không bắt buộc sửa web.
4. Chế độ tệp giữ nguyên (không ghi).

## Test

Kết nối giả: chạy `get_case` hai lần trong thời gian bộ đệm → ghi một lần; hết hạn / xoá bộ đệm → ghi lần hai; nội dung dòng ghi khớp phát hiện trả về API; lỗi ghi không làm API lỗi.

## Phạm vi

Sửa: `db/schema.sql`, `app/api/service.py`, `app/api/routes*` (endpoint mới), module lưu trữ (`app/storage/` hoặc `app/db/`), test schema/mapping; tạo test, `plan/reports/T78.md`. Cấm: `data/`, `web/`, `app/rules/`.

## Nghiệm thu (Claude chạy)

`ruff`, `pytest` 0 trượt. Trên RDS: nạp hồ sơ thử mới, mở trên web → có dòng trong `ket_qua_tham_dinh`, số dòng `ket_qua_nhan_dinh` = số nhận định trên màn hình.

## Bổ sung (Claude)

`ruff format --check` còn 3 tệp lệch sau T77-fix-1: định dạng lại (chỉ khoảng trắng). Lưu ý T74–T77: áp lược đồ phải chạy được trên DB đã có dữ liệu (`IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`).
