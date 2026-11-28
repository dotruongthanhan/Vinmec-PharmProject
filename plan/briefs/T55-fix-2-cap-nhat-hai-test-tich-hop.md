# T55-fix-2 – Cập nhật kỳ vọng hai test tích hợp sau khi nối luật yếu tố 4

Mô hình: Codex `gpt-6.1-sol`, effort `xhigh`. Không có mạng.

Đọc: `AGENTS.md`, `plan/reports/T55.md` (mục T55-fix-1), `plan/api-hop-dong-v1.6-ma-tran-tuong-tac.md`.

## Bối cảnh

Sau T55-fix-1, toàn kho có 1.243 test qua và 2 trượt. Cả hai là kỳ vọng cũ của đường chạy 5 luật:

- `tests/api/test_routes.py::test_demo02_detail`: kỳ vọng `"4. Tương tác thuốc"` nằm trong `yeu_to_chua_kiem`.
- `tests/db/test_reader.py::test_cache_refresh_and_review`: kỳ vọng `ma_tran_tuong_tac` là `None` và danh sách `phat_hien` của 5 luật.

## Phạm vi

- **Chỉ được sửa:** `tests/api/test_routes.py`, `tests/db/test_reader.py`, và thêm mục "## T55-fix-2" cuối `plan/reports/T55.md`.
- **Cấm sửa mã ứng dụng.** Nếu thấy hành vi mới có vẻ sai (không chỉ là kỳ vọng cũ), **không** sửa test cho khớp. Dừng lại và ghi rõ vào báo cáo.

## Yêu cầu

1. Cập nhật đúng hai test theo hành vi đã nối:
   - DEMO-02 (một dòng thuốc): yếu tố 4 đã chạy, không còn trong `yeu_to_chua_kiem`; ma trận có 1 thuốc, 0 cặp.
   - `test_reader`: `ma_tran_tuong_tac` có giá trị theo lược đồ v1.6, `phat_hien` có thêm phát hiện yếu tố 4 nếu có.
2. Kiểm tra cụ thể **mô tả của phát hiện yếu tố 4 khi y lệnh chỉ có một thuốc**: phải nói rõ "không có cặp để đối chiếu", không được ngụ ý đã đối chiếu tương tác. Dán nguyên văn `mo_ta` vào báo cáo. Nếu mô tả không nói rõ thì **ghi vào báo cáo, không sửa mã**.
3. Không xoá hay bỏ qua test.

## Nghiệm thu

`uv run pytest -q --basetemp=.pytest_t55f2` toàn kho **0 trượt**; `uv run ruff check tests`. Dán kết quả vào báo cáo.

## Cấm làm

Không gọi mạng. Không commit. Không dùng `&`.
