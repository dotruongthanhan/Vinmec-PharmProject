# T81-fix-1 – Test độc tính dựng y lệnh rỗng; câu chữ thanh trạng thái AI

Agent: **agy Gemini 4 Hydrogen high**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.**

## 1. Test trượt (Claude review T81: 1.541 qua, 1 trượt)

`tests/rules/test_toxicity.py::test_all_unresolved_lines_do_not_emit_dat_and_partial_excludes_unresolved` dòng ~931: `make_minimal_case(chi_tiet=[], ...)` → `ValidationError: YLenh.chi_tiet List should have at least 1 item`. Mô hình bắt buộc y lệnh có ≥ 1 dòng (đúng). Sửa **test**: giữ ý "dòng đang dùng chưa phân giải không làm ra đạt" bằng một y lệnh có ít nhất một dòng chưa phân giải (ví dụ `trang_thai_dong="pending"`) cộng `thuoc_dang_dung` chưa phân giải; không sửa mô hình, không sửa `toxicity.py`.

## 2. Câu chữ thanh trạng thái AI (người dùng thấy nhầm ở DEMO-02)

`web/src/features/findings/AiStatusBar.tsx:114` hiện "AI đã phân tích xong (53,6 giây). 9 nhận định có diễn giải, …" trong khi phần đầu trang chỉ có 3 mục cần chú ý (6 mục đạt nằm trong phần "Đạt" thu gọn). Sửa `countAiSummary` (`web/src/lib/aiReview.ts:72`) trả thêm số có diễn giải theo nhóm (`can_chu_y`, `dat`) và câu thành: "**9 nhận định có diễn giải (3 cần chú ý, 6 đạt)**". Nhóm có 0 thì bỏ phần đó (ví dụ "(3 cần chú ý)"). Giữ nguyên phần "… nhận định do AI thêm". Cập nhật `web/src/__tests__/aiReview.test.ts` và thêm test cho câu mới.

## Phạm vi

`tests/rules/test_toxicity.py`, `web/src/lib/aiReview.ts`, `web/src/features/findings/AiStatusBar.tsx`, `web/src/__tests__/aiReview.test.ts`. `tsc`, `oxlint` sạch. Thêm mục "fix-1" vào `plan/reports/T81.md`.
