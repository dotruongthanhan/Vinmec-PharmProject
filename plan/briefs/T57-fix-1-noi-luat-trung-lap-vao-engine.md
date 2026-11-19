# T57-fix-1 – Nối luật yếu tố 2 mới vào đường chạy thật

Mô hình: Codex `gpt-6.1-sol`, effort `xhigh`. Không có mạng.

Đọc: `AGENTS.md`, `plan/briefs/T57-yeu-to-2-trung-nhom-dieu-tri.md`, `plan/reports/T57.md` (mục "Việc còn lại").

## Bối cảnh

Luật mới qua registry đã đúng trên 66 ca. Nhưng `app/rules/engine.py` (`run_rules_with_matrix`) vẫn gọi `duplicate.check(ca)` không truyền resolver, nên `GET /api/cases/HS-016` trả luật cũ (`dat`). Brief T57 thiếu phạm vi tệp này (lỗi của Claude). **Claude cho phép sửa.**

## Phạm vi

**Được sửa:**
- `app/rules/engine.py`: chỉ lời gọi yếu tố 2. Truyền resolver từ ngữ cảnh luật khi có; khi vắng thì giữ nhánh một tham số như cũ.
- Hai test API so toàn bộ yếu tố khác 4 với luật cũ: loại yếu tố 2 khỏi phép so với nhánh không resolver, và thêm kiểm riêng yếu tố 2 mới.
- `tests/rules/test_duplicate_runtime.py`, test mới cho đường chạy.
- Mục "## T57-fix-1" cuối `plan/reports/T57.md`; cập nhật mục "Trạng thái" và dòng "Lượt cuối … đang chạy".

**Cấm đụng:** luật khác, `app/kb/**`, `app/llm/**`, `app/orchestration/**`, `data/**`, hợp đồng API, `app/rules/types.py`.

## Yêu cầu và nghiệm thu (dán vào báo cáo)

1. `GET /api/cases/HS-016` (TestClient, `AUTH_MODE=off`, `CASE_SOURCE=file`, ca ghi ra thư mục tạm ngoài kho) trả `trung_nhom_dieu_tri`, nhóm chống đông, mức nghiêm trọng. Dán nguyên văn `nhan_xet` và `can_cu`.
2. Cũng qua API, chạy đủ 66 ca. Bảng kết luận yếu tố 2 phải khớp bảng qua registry trong báo cáo: `dat` 56, `can_xem` 7, `khong_du_du_lieu` 3. Chỉ HS-014/015/016/017 có `trung_nhom_dieu_tri`.
3. Thêm test đường chạy: `run_case` có resolver → HS-016 ra `trung_nhom_dieu_tri`; không có resolver → luật cũ, không lỗi.
4. `uv run ruff check .`, `ruff format --check` các tệp sửa, `uv run pytest -q -p no:cacheprovider --basetemp=<thư mục trong %TEMP%>` toàn kho **0 trượt**. Không tạo `.pytest_*` trong kho.

## Cấm làm

Không gọi mạng. Không commit. Không dùng `&`. Không xoá hay bỏ qua test. Không đổi kết luận các luật khác. Không hỏi lại người dùng về phạm vi `engine.py`: đã cho phép ở brief này.
