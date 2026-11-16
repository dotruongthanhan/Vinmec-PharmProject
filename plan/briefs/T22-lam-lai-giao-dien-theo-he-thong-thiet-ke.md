# T22 – Làm lại giao diện web theo hệ thống thiết kế (plan 1.4)

**Giao cho:** Gemini 4 Hydrogen xhigh (người dùng tự chạy phiên này) · **Ngày viết:** 16/11/2026 (phiên 3)
**Điều kiện bắt đầu:** T21 đã xong và đã được review (T21 cũng sửa `web/src/`; chạy cùng lúc sẽ giẫm nhau).

## 0. Trước khi viết code

### 0.1. Tài liệu phải đọc, theo thứ tự

1. `AGENTS.md` – quy tắc chung cho agent.
2. **`plan/plan-1.4-he-thong-thiet-ke.md` – đọc trọn, đây là đặc tả hình thức của task này.**
3. `plan/plan-1.2-giao-dien-ui-ux.md` – nội dung, câu chữ, nguyên tắc P1–P9, các trạng thái.
4. `plan/api-hop-dong-v1.md` và `plan/api-hop-dong-v1.1-bo-sung.md` – dữ liệu web nhận được.
5. Toàn bộ `web/src/` hiện có – hiểu hành vi đang chạy trước khi thay hình thức.

### 0.2. Cài gói (chạy trong thư mục `web/`)

```bash
npm install tailwindcss @tailwindcss/vite @radix-ui/react-dialog @radix-ui/react-tabs @radix-ui/react-tooltip @radix-ui/react-popover @radix-ui/react-collapsible @radix-ui/react-scroll-area @radix-ui/react-toggle-group @radix-ui/react-radio-group @radix-ui/react-slot @radix-ui/react-label class-variance-authority clsx tailwind-merge lucide-react sonner @fontsource-variable/inter @fontsource-variable/jetbrains-mono
```

Nếu phiên của bạn không chạy được lệnh: dừng lại, báo người dùng chạy lệnh trên, rồi mới tiếp tục. Không thêm gói nào ngoài danh sách này. Không dùng lệnh `npx shadcn`; thành phần nền viết tay theo mục 5.1 của plan 1.4.

### 0.3. Chụp mốc trước khi sửa

Chạy `npm run build`, `npm run lint`, `npx vitest run` và ghi lại số test đang qua. Sau task, số test cũ **không được giảm** (trừ test bị thay bằng test tương đương, phải nêu rõ).

## 1. Mục tiêu

Bản web hiện chạy đúng nhưng hình thức thô: CSS viết tay từng file, ký tự `▲ ⚠ ✓` làm biểu tượng, bảng 3 cột có đầu cột trong thẻ nhận định, viền đỏ dày, không có thứ bậc chữ rõ ràng. Người dùng đánh giá "xấu, không có gì bảo đảm".

Task này **thay toàn bộ lớp hình thức** theo plan 1.4, **giữ nguyên hành vi và dữ liệu**. Không đổi hợp đồng API, không đổi logic lấy dữ liệu, không đổi câu chữ do API gửi.

Kết quả mong muốn: một công cụ lâm sàng nhìn chuyên nghiệp, điềm tĩnh, đọc nhanh; một dược sĩ mở ca DEMO-02 thấy ngay trong 3 giây: ai, thuốc gì, vấn đề gì, mức nào, căn cứ ở đâu.

## 2. Phạm vi file

Được tạo, sửa, xoá:

```text
web/src/**                    (trừ api/types.ts: chỉ sửa khi hợp đồng yêu cầu, và api/mockData.ts: không đổi dữ liệu)
web/vite.config.ts            (thêm plugin @tailwindcss/vite và bí danh "@" → "src")
web/tsconfig.app.json         (thêm "paths" cho bí danh "@")
web/index.html                (tiêu đề, lang="vi", bỏ tham chiếu thừa)
web/package.json              (chỉ do lệnh npm ở 0.2 thay đổi)
```

Không đụng: `app/`, `plan/`, `config/`, `data/`, `tests/`, `docs/`, `CLAUDE.md`, `AGENTS.md`.

## 3. Các bước, làm đúng thứ tự

Sau **mỗi** bước: `npm run build` phải qua. Đừng để dồn lỗi đến cuối.

### Bước 1 – Nền móng

1. `vite.config.ts`: thêm `tailwindcss()` từ `@tailwindcss/vite`; thêm `resolve.alias` `"@"` → `./src`. Giữ nguyên phần `server.proxy` và `test`.
2. `src/styles/theme.css`: khối `@theme` chứa **toàn bộ** biến ở mục 3 của plan 1.4 (màu nền, chữ, viền, nhấn, 7 nghĩa × 4 biến, cỡ chữ, bo góc, bóng). Đặt tên để lớp tiện ích sinh ra đọc được, ví dụ `--color-canvas`, `--color-fg-muted`, `--color-danger-fg`, `--color-danger-bg`, `--color-danger-line`, `--color-danger-solid`, `--text-metric`, `--radius-md`, `--shadow-xs`.
3. `src/styles/globals.css`: `@import "tailwindcss";` rồi `@import "./theme.css";`; nhập hai phông `@fontsource-variable/*`; kiểu gốc cho `html, body, #root` (cao 100%, nền `canvas`, chữ `fg`, cỡ 14/22, chữ số đều cột); vòng tiêu điểm; quy tắc `prefers-reduced-motion`.
4. `src/lib/cn.ts`: hàm `cn(...inputs)` = `twMerge(clsx(inputs))`.
5. `src/lib/severity.ts`: **nguồn duy nhất** ánh xạ mã → hình thức:
   - `toneOfFinding({ ket_luan_ma, muc_do_ma })` → `"danger" | "warning" | "missing" | "offlabel" | "success" | "neutral"` theo bảng: `can_xem` + `nghiem_trong` → `danger`; `can_xem` + `can_luu_y` → `warning`; `can_xem` + mức khác → `warning`; `khong_du_du_lieu` → `missing`; `ngoai_hdsd` → `offlabel`; `dat` → `success`.
   - `toneOfOrigin(nguon_goc_ma)` → `"neutral"` cho `luat`, `"ai"` cho `ai_da_kiem_chung` và `ai_chua_kiem_chung`.
   - `toneOfAllergy(di_ung_ma)` → `danger` / `neutral` / `missing`.
   - `ICON_OF_TONE`: ánh xạ nghĩa → thành phần biểu tượng lucide đúng cột cuối bảng 3.3.
   - Mã lạ → `neutral`, không ném lỗi.
6. Xoá các file trong `src/styles/` cũ và `App.css`, `index.css` sau khi mọi thành phần đã chuyển xong (ở bước 4), không xoá sớm.

### Bước 2 – Thành phần nền (`src/components/ui/`)

Viết đủ các thành phần ở mục 5.1 của plan 1.4: `button.tsx`, `badge.tsx`, `card.tsx`, `dialog.tsx`, `tabs.tsx`, `segmented-control.tsx`, `tooltip.tsx`, `collapsible.tsx`, `popover.tsx`, `data-table.tsx`, `skeleton.tsx`, `empty-state.tsx`, `inline-alert.tsx`, `toaster.tsx`, `kbd.tsx`, `record-id.tsx`, `scroll-area.tsx`.

Yêu cầu chung:

- Dùng Radix cho mọi thành phần có hành vi (hộp thoại, tab, tooltip, popover, collapsible, toggle group, radio group, scroll area). Không tự viết bẫy tiêu điểm hay xử lý `Esc`.
- Biến thể khai báo bằng `cva`; nhận `className` và gộp bằng `cn`.
- `Badge` nhận `tone` (7 nghĩa) và `variant` (`soft` | `outline`), tuỳ chọn `icon`.
- `Button` nhận `variant`, `size`, `loading`, `iconLeft`. `loading` → hiện `LoaderCircle` quay, `disabled`, `aria-busy`.
- Nút chỉ có biểu tượng: bắt buộc `aria-label`; viết thành phần `IconButton` bọc sẵn `Tooltip` để không quên.
- Không thành phần nền nào import từ `api/`, `state/`, `features/`.

### Bước 3 – Khung ứng dụng (`src/app/`)

Theo mục 4 của plan 1.4:

- `AppShell`: thanh trên 48 px; lưới ba cột `304px minmax(0,1fr) 384px`; mỗi cột tự cuộn; trang không cuộn. Hai cột bên thu gọn được (hàng đợi còn 56 px, khung hỏi thêm ẩn hẳn), trạng thái thu gọn lưu bằng cơ chế sẵn có ở `lib/prefs.ts`.
- Dưới 1280 px: khung hỏi thêm thành ngăn trượt (dùng `Dialog` của Radix kiểu trượt từ phải). Dưới 1024 px: hàng đợi cũng vậy.
- Thanh trên: `Pill` + tên công cụ; nhãn `Dữ liệu giả lập`; nhãn trạng thái AI lấy từ `che_do`; hai nút thu gọn.
- Bọc ứng dụng bằng `TooltipProvider` và đặt `Toaster`.
- Dòng nhắc "Kết quả tham khảo…" chuyển xuống chân vùng giữa.

### Bước 4 – Thành phần nghiệp vụ (`src/features/`)

Chuyển từng vùng, mỗi vùng một thư mục, theo đúng mục 5.2 → 5.8 của plan 1.4. Logic và các hook ở `state/` giữ nguyên; chỉ viết lại phần hiển thị.

| Vùng | Thư mục | Thay cho file cũ | Điểm phải đúng |
| :--- | :--- | :--- | :--- |
| Hàng đợi | `features/queue/` | `components/Queue.tsx` | Dải dọc 3 px theo mức cao nhất; chỉ hiện nhãn đếm có số > 0; mục đang chọn nền `primary-soft`; phím `↑ ↓ Enter`; bản thu gọn là cột chấm màu có tooltip |
| Dải định danh | `features/case-header/` | `CaseHeader.tsx` | Dính khi cuộn; ô CrCl; **ba trạng thái dị ứng khác hẳn nhau** (5.3) |
| Tóm tắt, chỉ số | `features/summary/` | `Summary.tsx`, `MetricCard.tsx` | Ba thẻ bằng nhau; ô chỉ số có giá trị `text-metric`, popover công thức; thiếu đầu vào hiện `—` + nhãn `missing` |
| Bảng nhận định | `features/findings/` | `FindingCard.tsx`, `EvidenceList.tsx`, `FeedbackBar.tsx`, `PassedList.tsx`, và các thành phần AI của T21 (`AiStatusBar`, `AiNote`, `SourceList`) | Đúng sơ đồ 5.5: dải dọc 4 px; đầu thẻ; thân xếp dọc (bỏ bảng 3 cột có đầu cột); khối AI; căn cứ dạng dòng thời gian đánh số; chân thẻ phản hồi; thẻ AI viền đứt; mục đạt gom gọn |
| Hộp thoại căn cứ, đoạn nguồn | `features/findings/` | `EvidenceDialog.tsx` | Dùng `Dialog` nền; bản ghi là bảng hai cột nhãn – giá trị; đoạn nguồn có tô nền câu trích (giữ hàm tách chuỗi của T21) |
| Chi tiết | `features/detail/` | `DetailTabs.tsx` | `Tabs` + `DataTable`; giá trị ngoài ngưỡng đậm, màu `danger-fg`, có mũi tên |
| Hỏi thêm | `features/assistant/` | `ChatPanel.tsx` | Đúng 5.8; trạng thái chưa sẵn sàng là `InlineAlert` + ô soạn vô hiệu; **không giả câu trả lời** |
| Trạng thái | `components/ui/` + từng vùng | `StateViews.tsx`, `StatusBanner.tsx` | Đúng bảng mục 6: khung xương khi tải, trạng thái rỗng, lỗi tại chỗ |

Quy tắc khi chuyển:

- Mọi chỗ đang `if` theo `ket_luan_ma`, `muc_do_ma`, `nguon_goc_ma`, `di_ung_ma` để chọn màu hay biểu tượng → gọi hàm ở `lib/severity.ts`.
- Ký tự `▲ ▼` trong dữ liệu (`huong`, `gia_tri_text`) → hiện bằng biểu tượng `ArrowUp` / `ArrowDown` và bỏ ký tự khỏi chuỗi hiển thị. Ký tự `⚠ ✓` đứng đầu một chuỗi nhãn do API gửi → bỏ ký tự, thay bằng biểu tượng tương ứng. Viết hai việc này thành hàm thuần trong `lib/` có test. Ngoài hai ngoại lệ này, **không sửa câu chữ** của API.
- Thứ tự thẻ, cách phân nhóm "cần chú ý" / "đạt", số đếm: giữ nguyên logic hiện có.
- Trạng thái đã phản hồi của từng thẻ không được mất khi bảng chuyển từ kết quả của luật sang kết quả có AI.
- Xoá file cũ ngay khi vùng đó chuyển xong; không để hai bản cùng tồn tại.

### Bước 5 – Rà soát

1. Tìm trong `web/src` (trừ `styles/theme.css`): không còn chuỗi `#` theo sau 3–8 chữ số hex dùng làm màu, không còn `rgb(`, `hsl(`. Không còn file `.css` nào ngoài hai file ở `styles/`.
2. Không còn ký tự `▲ ▼ ⚠ ✓ ⛔ ℹ` hay emoji trong mã nguồn giao diện (dữ liệu giả lập trong `api/mockData.ts` được giữ vì mô phỏng API).
3. Mọi `IconButton` có `aria-label`.
4. Đi hết ca DEMO-02 bằng bàn phím: chọn ca → mở "Căn cứ" → mở hộp thoại bản ghi → `Esc` → tiêu điểm về đúng nút → gửi phản hồi.
5. Kiểm ở ba bề rộng: 1366, 1280, 1024. Không có thanh cuộn ngang.

## 4. Kiểm thử phải có (`vitest`, môi trường `node`)

- `lib/severity.ts`: đủ mọi tổ hợp ở bước 1.5; mã lạ → `neutral`.
- Hàm bỏ ký tự và suy ra hướng mũi tên: `"212,0 ▲"` → giá trị `"212,0"`, hướng lên; chuỗi không có ký tự → giữ nguyên, không hướng; `"⚠ Có nhận định"` → `"Có nhận định"` + nghĩa `warning`.
- `cn`: gộp lớp trùng (lớp sau thắng).
- Test tĩnh mới `style-guard.test.ts`: đọc mọi file `.ts` / `.tsx` trong `src/` (trừ thư mục `__tests__` và `api/mockData.ts`) và khẳng định: không có mã màu hex, `rgb(`, `hsl(`; không có các ký tự biểu tượng ở mục 5.2; không có `style={{` chứa thuộc tính màu.
- `safety.test.ts` hiện có phải tiếp tục qua nguyên vẹn.
- Toàn bộ test logic hiện có (`api`, `queue`, `presentation`, và test của T21) tiếp tục qua; nếu đổi đường dẫn import thì chỉ sửa đường dẫn.

## 5. Nghiệm thu

Trong `web/`:

```bash
npm run build
npm run lint
npx vitest run
```

Cả ba đạt, `lint` 0 cảnh báo. Sau đó người review:

1. `npm run build` rồi `uv run uvicorn app.api.main:app --port 8000`, mở `http://localhost:8000/` ở 1366 × 768.
2. Chụp màn hình 6 ca demo, đối chiếu từng mục 5.2 → 5.8 và danh sách kiểm mục 9 của plan 1.4.
3. So hành vi với bản trước: số ca, thứ tự ca, số đếm, nội dung từng thẻ, hộp thoại bản ghi, phản hồi phải giống hệt.

## 6. Cấm làm

- Không đổi hợp đồng API, không sửa backend, không đổi dữ liệu giả lập.
- Không thêm gói ngoài danh sách 0.2. Không thêm thư viện biểu đồ, hoạt hoạ, bộ giao diện khác (MUI, Ant, Chakra…).
- Không chuyển sang Next.js (đã quyết ở mục 1.1 của plan 1.4).
- Không làm giao diện tối, không làm bản điện thoại.
- Không thêm tính năng mới (không làm ô hỏi thêm thật, không thêm trang).
- Không chèn HTML thô, không diễn giải markdown từ dữ liệu.
- Không tự dịch mã nội bộ hay tự làm tròn số ở web.
- Không commit, không push.

## 7. Báo cáo khi xong

Theo mẫu trong `AGENTS.md`, thêm:

- Danh sách file đã xoá và file thay thế tương ứng.
- Kết quả ba lệnh nghiệm thu (hoặc ghi rõ chưa chạy được và vì sao).
- Những chỗ plan 1.4 thiếu hoặc mâu thuẫn mà bạn phải tự quyết, mỗi chỗ một dòng: đã chọn gì, vì sao.
- Những chỗ dữ liệu API khiến hình thức không làm đúng đặc tả (ví dụ câu căn cứ còn thô như `212.0 umol/L lúc 2026-11-10T05:30:00+07:00`): liệt kê, **không tự sửa ở web**; đó là việc của backend.
