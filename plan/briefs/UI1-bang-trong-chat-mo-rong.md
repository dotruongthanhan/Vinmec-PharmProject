# UI1 – Bảng trong khung chat: hiển thị bảng thật và nút mở rộng toàn màn

Mã `UI*` thuộc phiên Claude đang làm plan 1.11. Phiên làm tool agent dùng mã `T1xx`.

Agent: Codex `gpt-6.1-terra`, effort **high**, `-s workspace-write`. Đọc trước: `AGENTS.md`, `plan/plan-1.4-he-thong-thiet-ke.md` (mục 3, 5, 7), `web/src/components/ui/ClinicalMarkdown.tsx`, `web/src/components/ui/dialog.tsx`, `web/src/components/ui/data-table.tsx`, `web/src/features/assistant/AssistantPanel.tsx` (dòng 590–700), `web/src/features/assistant/HistoryDialog.tsx`, `web/src/__tests__/clinicalMarkdown.test.tsx`, `web/src/__tests__/safety.test.ts`.

## Bối cảnh

Chủ kho phản ánh rằng trong khung trợ lý, bảng do LLM trả về **chật**: dược sĩ phải kéo ngang mới xem hết. Chủ kho muốn có **nút mở rộng**: bấm vào thì **chỉ bảng** được mở ra toàn màn hình, giống nút "Expand table" của ứng dụng Claude.

Claude đã khảo sát (26/11):
- `ClinicalMarkdown` (`parseBlocks`, dòng 254) chỉ nhận diện `paragraph | ordered-list | unordered-list | heading | code-block | quote`. **Không có bảng.** Bảng Markdown dạng `| a | b |` đang hiện thành đoạn văn có dấu `|`.
- LLM được dặn trả Markdown (`config/prompts/tac_tu.v1.md` mục 6), và thực tế có trả bảng. Ví dụ: T110 trích nguyên văn "Bảng 3" liều imipenem theo CrCl.
- Cửa sổ lịch sử (`HistoryDialog.tsx` dòng 94, 102) hiện `noi_dung` dạng văn bản thô, chưa qua `ClinicalMarkdown`.

## Phạm vi tệp

**Được sửa hoặc tạo:**
- `web/src/components/ui/ClinicalMarkdown.tsx`;
- tệp mới `web/src/components/ui/markdown-table.tsx` (nếu tách);
- `web/src/components/ui/dialog.tsx` (chỉ **thêm** biến thể `fullscreen`);
- `web/src/features/assistant/HistoryDialog.tsx` (dùng `ClinicalMarkdown` cho câu trả lời);
- `web/src/__tests__/clinicalMarkdown.test.tsx` và test mới trong `web/src/__tests__/`.

**Cấm đụng:** `app/**`, `config/**`, `plan/**` (trừ báo cáo), `web/package.json` (**không thêm gói**), các tệp web khác ngoài danh sách trên.

## Yêu cầu
1. **Phân tích bảng kiểu GFM:**
   - Nhận diện khi có dòng tiêu đề `| … |`, ngay sau là dòng phân cách `|---|:---:|---:|`, rồi các dòng thân.
   - Hỗ trợ căn lề trái, giữa, phải theo dấu `:`.
   - Hỗ trợ ký tự `\|` thoát trong ô.
   - Dòng thiếu ô thì bù ô rỗng; dòng thừa ô thì cắt bỏ phần thừa.
   - Thiếu dòng phân cách thì giữ nguyên là đoạn văn như hiện nay.
   - Nội dung **từng ô** vẫn đi qua bộ tách token nội dòng hiện có: trích dẫn `[n]` (gọi `onCitationClick`), chip mã, `**đậm**`, `` `mã` ``, công thức `$…$`.
   - Giới hạn: tối đa 200 dòng và 20 cột mỗi bảng, ô dài quá 1.000 ký tự thì cắt kèm dấu `…`. Vượt giới hạn thì hiện phần đầu và dòng "Bảng đã rút gọn: hiện N/M dòng".
2. **Hiển thị trong khung chat:**
   - Bảng nằm trong khung cuộn ngang riêng (không làm tràn cả khung chat).
   - Tiêu đề cột dính trên đầu khi cuộn dọc.
   - Chữ cỡ nhỏ theo plan 1.4, viền mảnh, dòng xen màu nhẹ. Màu lấy token trong `theme.css`, chạy được cả nền sáng và nền tối.
   - Dùng lại kiểu của `data-table.tsx` nếu phù hợp.
3. **Nút mở rộng:**
   - Đặt ở góc trên phải mỗi bảng: icon `Maximize2` của lucide, `aria-label="Mở rộng bảng"`, có tooltip "Mở rộng bảng".
   - Bấm vào thì mở `Dialog` biến thể mới `fullscreen` (cách mép màn hình 16 px, bo góc, có nút đóng).
   - Trong dialog **chỉ có bảng đó**, rộng hết khung, cuộn được cả hai chiều. Tiêu đề dialog lấy tiêu đề Markdown gần nhất phía trên bảng nếu có, nếu không thì ghi "Bảng".
   - Esc hoặc nút X để đóng, xong trả tiêu điểm về nút mở rộng.
   - Bấm trích dẫn `[n]` trong dialog thì đóng dialog trước rồi gọi `onCitationClick(n)`.
4. **Khối mã (`code-block`) dài ngang:** thêm nút mở rộng giống hệt khi khối mã có dòng dài hơn 80 ký tự. Việc này không bắt buộc; làm thì ghi vào báo cáo.
5. **Lịch sử:** `HistoryDialog` hiện câu trả lời bằng `ClinicalMarkdown`, để bảng và nút mở rộng cũng có ở đó.
6. **Không đổi** giao diện hay hành vi của các khối khác.

## Bảo mật
- **Không** dùng `dangerouslySetInnerHTML`, `innerHTML`, `eval`, `new Function`. `safety.test.ts` phải vẫn qua.
- Nội dung ô là văn bản thuần, React tự escape. Thêm test: ô chứa `<img src=x onerror=alert(1)>` và `<script>…</script>` thì hiện nguyên chữ, không tạo phần tử `img` hay `script`.
- Ô chứa `javascript:` hoặc link Markdown không được biến thành thẻ `<a>`.
- Giới hạn kích thước ở yêu cầu 1 để chống bảng khổng lồ làm treo trình duyệt. Thêm test với 1.000 dòng: thời gian render dưới 500 ms trong jsdom, và DOM chỉ có tối đa 200 dòng.

## Tiêu chí nghiệm thu (Claude chạy)
- `cd web && npx tsc -b && npx oxlint && npx vitest run` qua toàn bộ.
- Test mới bao gồm:
  - bảng 3 cột có căn lề;
  - `\|` thoát trong ô;
  - dòng thiếu và thừa ô;
  - không có dòng phân cách thì vẫn là đoạn văn;
  - trích dẫn `[2]` trong ô gọi `onCitationClick(2)`;
  - bấm nút mở rộng thì dialog mở và chỉ chứa bảng; Esc đóng và tiêu điểm trở về nút;
  - bấm trích dẫn trong dialog thì dialog đóng và callback được gọi;
  - ca XSS;
  - 1.000 dòng bị rút còn 200;
  - `HistoryDialog` hiện bảng.
- Claude sẽ chụp màn hình khung chat thật với một câu trả lời có bảng liều theo CrCl.

## Báo cáo
Ghi `plan/reports/UI1.md`: tệp đã sửa, quyết định thiết kế, kết quả lệnh. Không commit.
