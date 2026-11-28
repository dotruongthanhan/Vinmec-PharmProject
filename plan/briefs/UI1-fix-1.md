# UI1-fix-1 – Bảng làm cả cột tin nhắn nở rộng, chữ bị cắt ở hai mép

Agent: Codex `gpt-6.1-terra`, effort **high**, `-s workspace-write`. Đọc trước:
- `AGENTS.md`
- `plan/briefs/UI1-bang-trong-chat-mo-rong.md`, `plan/reports/UI1.md`
- `web/src/components/ui/ClinicalMarkdown.tsx`, `web/src/components/ui/scroll-area.tsx`
- `web/src/features/assistant/AssistantPanel.tsx`

## Claude đo trên giao diện thật (26/11, `localhost:5173`, chế độ demo, ca DEMO-02, khung nhìn 1440×900)

Hỏi trợ lý một câu cần lập bảng; LLM trả về bảng 3 cột. Kết quả:

- **Đạt:**
  - bảng hiện thành `<table>` thật;
  - nút "Mở rộng bảng" mở hộp thoại toàn màn chỉ chứa bảng, đủ 3 cột;
  - Esc đóng hộp thoại và trả tiêu điểm về nút;
  - `thead` có `position: sticky`.
- **Lỗi:** đi từ `table` lên các phần tử cha (`getComputedStyle`):

  | Phần tử | Lớp CSS | `clientWidth` / `scrollWidth` | Ghi chú |
  | :--- | :--- | :--- | :--- |
  | `table` | `w-full min-w-max …` | 1051 / 1050 | |
  | `div` bọc bảng | `max-h-80 max-w-full overflow-auto` | 1051 / 1051 | không cuộn được vì đã nở bằng bảng |
  | `div` | `flex flex-col … break-words` (gốc `ClinicalMarkdown`) | 1052 | |
  | 3 `div` | `flex flex-col` của khối tin nhắn, `min-width: auto` | 1052 | |
  | `div` | không có lớp, `min-width: 100%` | 1052 | **lớp bọc của Radix ScrollArea viewport, `display: table`**, nở theo nội dung |
  | `div` | `size-full rounded-[inherit] p-4` (viewport) | 399 / 1084, `overflow-x: hidden` | |

  Hệ quả:
  - cả cột tin nhắn rộng 1052 px trong một panel 399 px;
  - chữ của **mọi** tin nhắn bị cắt ở mép phải, và sau khi cuộn thì bị cắt cả mép trái (Claude có ảnh chụp);
  - thanh cuộn ngang riêng của bảng không bao giờ xuất hiện.

  Đây đúng là triệu chứng "phải kéo sang mới thấy" mà chủ kho phản ánh, nay nặng hơn vì bảng dùng `min-w-max`.

## Việc phải làm
1. **Chặn nở rộng ở gốc.** Lớp bọc `display: table` của Radix ScrollArea phải không nở theo nội dung. Cách gợi ý, chọn một và ghi lý do:
   - (a) trong `scroll-area.tsx`, viewport chỉ cuộn dọc thì ép con trực tiếp `display: block` (`[&>div]:!block`), hoặc thêm prop `orientation`/`fitContent` mặc định không thay đổi cho các chỗ khác đang dùng;
   - (b) chỉ áp cho ScrollArea của khung trợ lý trong `AssistantPanel.tsx`.

   Phải rà mọi chỗ dùng `ScrollArea` và xác nhận không có chỗ nào đổi hành vi ngoài ý muốn (liệt kê trong báo cáo).
2. **Ràng chiều rộng chuỗi cha:** các `div flex flex-col` của khối tin nhắn và gốc `ClinicalMarkdown` đặt `min-w-0`, `max-w-full`. Kết quả: khung bảng bằng đúng chiều rộng panel trừ padding, và **chỉ khung bảng** cuộn ngang (`overflow-x: auto`).
3. Ô bảng nên xuống dòng hợp lý thay vì `min-w-max` cứng. Gợi ý: `min-w-full` cho bảng; ô có `min-width` khoảng 8rem và `max-width` khoảng 28rem với `break-words`. Bảng ít cột thì vừa khung, không cần cuộn; bảng nhiều cột thì khung bảng cuộn ngang. Trong hộp thoại toàn màn, ô được rộng hơn (`max-width` lớn hơn hoặc không giới hạn).
4. **Tiêu đề hộp thoại:** nếu ngay trước bảng là một dòng in đậm đứng riêng (`**…**`) thì dùng dòng đó làm tiêu đề khi không có heading Markdown. Ví dụ thật: "**Bảng tối thiểu theo nguồn hiện có**" đang thành tiêu đề "Bảng".
5. Sửa vị trí chú thích JSDoc: khối chú thích của `ClinicalMarkdown` hiện nằm trên `MarkdownTable`.
6. `HistoryDialog` chịu cùng ràng buộc chiều rộng: bảng trong lịch sử không làm nở danh sách tin nhắn.

## Phạm vi tệp
**Được sửa:**
- `web/src/components/ui/ClinicalMarkdown.tsx`
- `web/src/components/ui/scroll-area.tsx` (chỉ khi chọn cách a)
- `web/src/features/assistant/AssistantPanel.tsx` (chỉ các lớp CSS bố cục của khối tin nhắn và ScrollArea)
- `web/src/features/assistant/HistoryDialog.tsx`
- test trong `web/src/__tests__/`

**Cấm:** thêm gói, sửa `app/**`, `config/**`, đổi hành vi khác của khung chat.

## Tiêu chí nghiệm thu
- `cd web && npx.cmd tsc -b && npx.cmd oxlint && npx.cmd vitest run` qua toàn bộ.
- Test tĩnh (không cần jsdom) khẳng định:
  - bảng không còn `min-w-max`;
  - khung bảng có `overflow-x-auto` và `max-w-full`;
  - gốc `ClinicalMarkdown` có `min-w-0`;
  - tiêu đề hộp thoại lấy dòng in đậm đứng trước bảng.
- **Claude đo lại trên giao diện thật:**
  - khung bảng có `clientWidth` ≤ chiều rộng viewport của panel (399 px ở 1440×900);
  - bảng 8 cột thì `scrollWidth > clientWidth` (cuộn riêng);
  - viewport của panel có `scrollWidth == clientWidth` (không còn tràn);
  - chữ các tin nhắn khác không bị cắt.

## Báo cáo
Thêm mục "UI1-fix-1" vào `plan/reports/UI1.md`. Không commit, không đọc `~/.codex`.
