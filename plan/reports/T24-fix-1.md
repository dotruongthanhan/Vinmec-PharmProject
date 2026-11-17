TRẠNG THÁI: **CHƯA XONG**

FILE ĐÃ TẠO / SỬA:
- `app/orchestration/ask.py`
- `app/api/{presenter,schemas,service}.py`
- `config/prompts/hoi_them.v1.md`
- `tests/api/{test_routes,test_contract,test_ask_routes}.py`
- `tests/orchestration/test_ask.py`

Đã thêm log chẩn đoán an toàn, thử lại toàn bộ câu trả lời đúng một lần khi kiểm chứng lỗi, phân biệt thiếu nguồn với ngoài phạm vi và bổ sung bốn trường hàng đợi.

LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:

- `uv run ruff check app/api app/orchestration app/verify tests/api tests/orchestration tests/verify` → sạch.
- `uv run ruff format --check app/api app/orchestration app/verify tests/api tests/orchestration tests/verify` → đạt, 32 file.
- `uv run pytest -q -p no:cacheprovider tests/api tests/orchestration tests/verify tests/llm` → **107 passed**, một cảnh báo Starlette/httpx.
- `uv run ruff check app tests --exclude tests/architecture/.tmp --exclude tests/kb/.tmp` → sạch.
- Đã chạy `uvicorn` cổng 8011, gọi ban đầu ít nhất 3 lần và gọi tiếp 5 lần liên tiếp. **Đã dừng máy chủ**, xác nhận cổng được giải phóng.

Cả 5 lần cuối đều có log:
```text
step=llm reason=provider_connection_error chunks=6
```

Nguyên JSON của 5 kết quả, theo thứ tự:
```json
[
  {
    "trang_thai": "loi",
    "noi_dung": "Đã xảy ra lỗi hoặc quá thời gian khi xử lý câu hỏi. Dược sĩ vui lòng thử lại hoặc xem trực tiếp bảng nhận định bên trái.",
    "trich_dan": [],
    "cong_cu_da_goi": ["du_lieu_ca", "bo_luat", "truy_xuat"],
    "thoi_gian_ms": 5268
  },
  {
    "trang_thai": "loi",
    "noi_dung": "Đã xảy ra lỗi hoặc quá thời gian khi xử lý câu hỏi. Dược sĩ vui lòng thử lại hoặc xem trực tiếp bảng nhận định bên trái.",
    "trich_dan": [],
    "cong_cu_da_goi": ["du_lieu_ca", "bo_luat", "truy_xuat"],
    "thoi_gian_ms": 4609
  },
  {
    "trang_thai": "loi",
    "noi_dung": "Đã xảy ra lỗi hoặc quá thời gian khi xử lý câu hỏi. Dược sĩ vui lòng thử lại hoặc xem trực tiếp bảng nhận định bên trái.",
    "trich_dan": [],
    "cong_cu_da_goi": ["du_lieu_ca", "bo_luat", "truy_xuat"],
    "thoi_gian_ms": 4643
  },
  {
    "trang_thai": "loi",
    "noi_dung": "Đã xảy ra lỗi hoặc quá thời gian khi xử lý câu hỏi. Dược sĩ vui lòng thử lại hoặc xem trực tiếp bảng nhận định bên trái.",
    "trich_dan": [],
    "cong_cu_da_goi": ["du_lieu_ca", "bo_luat", "truy_xuat"],
    "thoi_gian_ms": 4599
  },
  {
    "trang_thai": "loi",
    "noi_dung": "Đã xảy ra lỗi hoặc quá thời gian khi xử lý câu hỏi. Dược sĩ vui lòng thử lại hoặc xem trực tiếp bảng nhận định bên trái.",
    "trich_dan": [],
    "cong_cu_da_goi": ["du_lieu_ca", "bo_luat", "truy_xuat"],
    "thoi_gian_ms": 4721
  }
]
```

Dòng DEMO-02 từ `GET /api/cases`:
```json
{
  "ca_id": "DEMO-02",
  "khoa": "Hô hấp",
  "mo_ta": "Nữ 75 tuổi, viêm phổi, suy giảm chức năng thận nhưng liều meropenem chưa chỉnh",
  "uu_tien": 0,
  "huy_hieu": "⛔ 1 nghiêm trọng",
  "so_nghiem_trong": 1,
  "so_can_luu_y": 0,
  "so_thieu_du_lieu": 0,
  "da_phan_hoi_het": true,
  "ma_y_lenh": "YL-DEMO-02",
  "thoi_diem_ke": "2026-11-10T05:50:00+07:00",
  "nguoi_benh_tom_tat": "Nữ, 75 tuổi",
  "thuoc": ["Meropenem 1 g"]
}
```

ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO: Chưa xác định được nguyên nhân lỗi `khong_co_nguon` ban đầu. Kết nối TCP tới DeepSeek bị chặn với `PermissionError`, `WinError 10013`, nên yêu cầu dừng trước bước kiểm chứng. Chưa đạt tiêu chí ít nhất 4/5 lần trả `ok`. Các bước kiểm số, mã và câu trích được giữ nguyên.

VIỆC CHƯA LÀM / CÂU HỎI: Cần chạy lại ở môi trường cho phép kết nối DeepSeek để xác định nguyên nhân ban đầu, sửa theo bằng chứng và nghiệm thu 4/5 cùng nguồn mở được.

Bộ kiểm duyệt tự động đã chặn việc xoá `tests/api/.tmp` với lý do “blocked by policy”; thư mục tạm được giữ lại.