# PLAN 1.4 – HỆ THỐNG THIẾT KẾ (DESIGN SYSTEM) CHO BẢN WEB

**Ngày:** 16/11/2026 (phiên 3) · **Trạng thái:** bản đầu, chờ người dùng xem
**Quan hệ với plan 1.2:** plan 1.2 quy định *hiện cái gì, ở đâu, câu chữ ra sao*. Bản này quy định *trông như thế nào* và *dựng bằng gì*. Chỗ nào hai bản lệch nhau về hình thức thì theo bản này; về nội dung và câu chữ thì theo plan 1.2.
**Thay mục 7 của plan 1.2** ở câu "React thuần và CSS thuần, không thêm thư viện giao diện".

Mọi agent làm giao diện phải đọc file này trước khi viết một dòng CSS hay JSX.

---

## 1. Quyết định công nghệ

| Hạng mục | Chọn | Lý do |
| :--- | :--- | :--- |
| Khung | **Giữ Vite + React 19 + TypeScript** | Xem 1.1 |
| CSS | **Tailwind CSS v4** (plugin `@tailwindcss/vite`), biến thiết kế khai báo trong `@theme` | Một nguồn duy nhất cho màu, cỡ chữ, khoảng cách; agent khó viết lệch |
| Thành phần nền | **Radix UI** (hộp thoại, tab, tooltip, popover, collapsible, scroll area, toggle group, radio group) theo cách tổ chức của **shadcn/ui**: mã thành phần nằm trong kho ở `web/src/components/ui/` | Bàn phím, tiêu điểm, đọc màn hình đã đúng sẵn; sửa được từng dòng |
| Biến thể kiểu dáng | `class-variance-authority`, `clsx`, `tailwind-merge` (hàm `cn`) | Khai báo biến thể nút, nhãn một chỗ |
| Biểu tượng | `lucide-react`, nét 1,75, cỡ 16 hoặc 18 | Một bộ duy nhất, không dùng ký tự emoji hay `▲ ⚠ ✓` làm biểu tượng |
| Phông chữ | `@fontsource-variable/inter` (giao diện), `@fontsource-variable/jetbrains-mono` (mã bản ghi) | Tự lưu trong gói, không gọi máy chủ phông ngoài; Inter có đủ dấu tiếng Việt và chữ số đều cột |
| Thông báo nổi | `sonner` | |

### 1.1. Vì sao chưa chuyển sang Next.js

Người dùng nêu khả năng dùng Next. Đề xuất **chưa chuyển**, vì:

- Phần "xấu" đến từ việc chưa có hệ thống thiết kế, không đến từ Vite. Đổi khung không làm đẹp hơn.
- Ứng dụng là công cụ nội bộ một trang, dữ liệu lấy từ FastAPI. Không cần dựng trang phía máy chủ, không cần tối ưu tìm kiếm.
- Hiện demo chạy **một tiến trình** (FastAPI phục vụ luôn `web/dist`). Next cần thêm máy chủ Node hoặc phải xuất tĩnh, thêm việc cấu hình trong khi demo là 20/11.
- Toàn bộ thành phần ở bản này (Tailwind, Radix, kiểu shadcn) dùng lại nguyên vẹn nếu sau demo chuyển sang Next: chỉ đổi lớp định tuyến và lấy dữ liệu.

Nếu người dùng vẫn muốn Next: làm sau demo, thành một task riêng.

---

## 2. Cá tính hình ảnh

**Một câu:** công cụ lâm sàng điềm tĩnh, chính xác, dày thông tin nhưng dễ thở.

| Nên | Không nên |
| :--- | :--- |
| Nền sáng trung tính, nhiều khoảng trắng có chủ đích | Nền màu, dải màu chuyển sắc, hình minh hoạ trang trí |
| Màu chỉ dùng để mang nghĩa (mức độ, nguồn gốc, hành động chính) | Tô màu cho đẹp; nhiều hơn một màu nhấn trên một vùng |
| Thứ bậc bằng cỡ chữ, độ đậm, khoảng cách | Thứ bậc bằng đường kẻ dày, khung lồng khung |
| Viền mảnh 1 px, bóng rất nhẹ | Bóng đậm, viền 2 px trở lên (trừ dải mức độ bên trái thẻ) |
| Chữ số đều cột, canh phải trong bảng | Số canh trái, số không kèm đơn vị |
| Chuyển động ngắn, có mục đích | Hiệu ứng nảy, trượt dài, nhấp nháy |

Chỉ làm **giao diện sáng**. Giao diện tối để sau; vì vậy mọi màu phải lấy qua biến ở mục 3, không viết mã màu trực tiếp trong thành phần.

---

## 3. Biến thiết kế (design tokens)

Khai báo trong `web/src/styles/theme.css` bằng `@theme` của Tailwind v4. Tên biến dưới đây là tên dùng trong lớp tiện ích (ví dụ `bg-surface`, `text-fg-muted`, `border-line`).

### 3.1. Màu nền, chữ, viền

| Biến | Giá trị | Dùng cho |
| :--- | :--- | :--- |
| `canvas` | `#F6F7F9` | Nền ứng dụng |
| `surface` | `#FFFFFF` | Thẻ, bảng, hộp thoại |
| `surface-muted` | `#F2F4F7` | Vùng phụ trong thẻ, đầu bảng, ô nhập chỉ đọc |
| `surface-hover` | `#F9FAFB` | Di chuột lên dòng, lên mục hàng đợi |
| `line` | `#E4E7EC` | Viền mặc định |
| `line-strong` | `#D0D5DD` | Viền ô nhập, viền nút phụ |
| `fg` | `#101828` | Chữ chính |
| `fg-muted` | `#475467` | Chữ phụ, nhãn |
| `fg-subtle` | `#667085` | Chú thích, thời điểm, đơn vị |
| `fg-disabled` | `#98A2B3` | Vô hiệu |

### 3.2. Màu nhấn (hành động chính)

| Biến | Giá trị | Dùng cho |
| :--- | :--- | :--- |
| `primary` | `#0E7C86` | Nút chính, liên kết, tab đang chọn, viền tiêu điểm |
| `primary-hover` | `#0B646C` | Di chuột |
| `primary-soft` | `#E9F6F7` | Nền mục đang chọn trong hàng đợi, nền nút mềm |
| `primary-line` | `#9BD5DA` | Viền mục đang chọn |

### 3.3. Màu mang nghĩa

Mỗi nghĩa có 4 biến: `-fg` (chữ, biểu tượng), `-bg` (nền nhãn, nền dải), `-line` (viền), `-solid` (dải dọc bên trái thẻ, chấm trạng thái).

| Nghĩa | `-fg` | `-bg` | `-line` | `-solid` | Biểu tượng lucide |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `danger` – Nghiêm trọng | `#B42318` | `#FEF3F2` | `#FDA29B` | `#D92D20` | `OctagonAlert` |
| `warning` – Cần lưu ý | `#B54708` | `#FFFAEB` | `#FEC84B` | `#F79009` | `TriangleAlert` |
| `missing` – Không đủ dữ liệu | `#175CD3` | `#EFF8FF` | `#84CAFF` | `#2E90FA` | `CircleHelp` |
| `offlabel` – Ngoài HDSD / phác đồ | `#5925DC` | `#F4F3FF` | `#BDB4FE` | `#7A5AF8` | `FileQuestion` |
| `success` – Đạt | `#067647` | `#ECFDF3` | `#75E0A7` | `#17B26A` | `CircleCheck` |
| `ai` – Nội dung do AI | `#3538CD` | `#EEF4FF` | `#A4BCFD` | `#6172F3` | `Sparkles` |
| `neutral` – Luật, thông tin | `#344054` | `#F2F4F7` | `#D0D5DD` | `#667085` | `Scale` (luật), `Info` |

Quy tắc: **không bao giờ dùng màu làm tín hiệu duy nhất** (P6 của plan 1.2). Nhãn mức độ luôn gồm biểu tượng + chữ. Mọi cặp `-fg` trên `-bg` và `fg` trên `surface` đạt tương phản tối thiểu 4,5:1.

### 3.4. Chữ

Phông: `Inter Variable`, dự phòng `system-ui, "Segoe UI", sans-serif`. Mã bản ghi: `JetBrains Mono Variable`.
Bật `font-feature-settings: "cv11", "ss01"` và `font-variant-numeric: tabular-nums` cho mọi con số.

| Tên | Cỡ / dòng | Đậm | Dùng cho |
| :--- | :--- | :-: | :--- |
| `text-2xs` | 11 / 16 | 500 | Nhãn chữ hoa nhỏ (đầu cột, tiêu đề nhóm), giãn chữ 0,04em |
| `text-xs` | 12 / 16 | 400–500 | Chú thích, đơn vị, thời điểm, nhãn (badge) |
| `text-sm` | 13 / 20 | 400 | Chữ trong bảng, mục hàng đợi, căn cứ |
| `text-base` | 14 / 22 | 400 | **Chữ thân bài mặc định**, nhận xét của nhận định |
| `text-md` | 16 / 24 | 600 | Tiêu đề thẻ, tiêu đề hộp thoại |
| `text-lg` | 18 / 28 | 600 | Tiêu đề vùng ("Bảng nhận định") |
| `text-metric` | 24 / 30 | 600 | Giá trị chỉ số (CrCl, eGFR…) |

Chỉ dùng ba độ đậm: 400, 500, 600. Không dùng chữ nghiêng cho nội dung lâm sàng. Không viết hoa cả câu, trừ nhãn `text-2xs`.

### 3.5. Khoảng cách, bo góc, bóng, chuyển động

- **Khoảng cách:** lưới 4 px. Bên trong thẻ: 16. Giữa các thẻ trong một vùng: 12. Giữa các vùng: 24. Giữa nhãn và giá trị: 4. Không dùng giá trị lẻ ngoài thang 2, 4, 6, 8, 12, 16, 20, 24, 32.
- **Bo góc:** `sm` 6 (nút, ô nhập, nhãn chữ nhật), `md` 10 (thẻ, bảng), `lg` 14 (hộp thoại), `full` (nhãn dạng viên, chấm).
- **Bóng:** `xs` `0 1px 2px rgba(16,24,40,.05)` cho thẻ; `md` `0 4px 12px rgba(16,24,40,.08)` cho popover; `xl` `0 20px 40px rgba(16,24,40,.16)` cho hộp thoại. Thẻ trong vùng nội dung chỉ dùng viền + `xs`.
- **Chuyển động:** 120 ms cho di chuột và đổi màu; 180 ms `ease-out` cho mở thu gọn, hộp thoại. Tôn trọng `prefers-reduced-motion`: tắt mọi chuyển động trừ đổi độ mờ.
- **Tiêu điểm bàn phím:** vòng 2 px màu `primary`, lệch 2 px, trên mọi phần tử tương tác. Không được tắt.

---

## 4. Bố cục

```text
┌───────────────────────────────────────────────────────────────────────────────┐
│ Thanh trên 48px: tên công cụ · nhãn chế độ (giả lập, AI bật/tắt) · vai trò   │
├────────────┬───────────────────────────────────────────────┬──────────────────┤
│ Hàng đợi   │ Dải định danh ca (dính khi cuộn, 56px)        │ Hỏi thêm         │
│ 304px      ├───────────────────────────────────────────────┤ 384px            │
│ thu gọn    │ Nội dung cuộn, rộng tối đa 920px, canh giữa   │ thu gọn được     │
│ còn 56px   │ Tóm tắt → Chỉ số → Bảng nhận định → Chi tiết  │                  │
└────────────┴───────────────────────────────────────────────┴──────────────────┘
```

- Màn hình mục tiêu: 1366 × 768 trở lên. Dưới 1280 px: khung "Hỏi thêm" thành ngăn trượt mở bằng nút; dưới 1024 px: hàng đợi cũng thành ngăn trượt.
- Mỗi vùng tự cuộn; trang không cuộn. Không bao giờ có thanh cuộn ngang.
- Vùng giữa có lề trong 24 px; nội dung không kéo giãn quá 920 px để dòng chữ không quá dài.
- Thanh trên: nền `surface`, viền dưới `line`. Bên trái: biểu tượng `Pill` + tên "Hỗ trợ thẩm định y lệnh". Giữa: không có gì. Bên phải: nhãn `Dữ liệu giả lập` (kiểu `warning` mềm), nhãn trạng thái AI (`ai` khi bật, `neutral` khi tắt), nút thu gọn hai bên.
- Dòng nhắc "Kết quả tham khảo. Dược sĩ kiểm chứng và quyết định." đặt ở **chân vùng giữa**, cỡ `text-xs`, màu `fg-subtle`, luôn nhìn thấy; không chiếm một dải lớn trên đầu.

### 4.1. Bố cục co giãn theo cột giữa (chủ kho chốt 27/11/2026)

Bật khung trợ lý thì cột giữa hẹp lại (đo 27/11: khoảng 632 px ở màn 1280, 792 px ở màn 1440). Khi đó chữ phải **xuống dòng**, không được bị đẩy ra ngoài vùng nhìn.

- Bố cục theo **bề rộng cột giữa** (container query trên `.workspace-center`), không theo bề rộng màn hình.
- Bảng nhiều cột có chế độ gọn: gộp cột phụ thành dòng phụ dưới cột chính. Giá trị bị gộp vẫn phải nhìn thấy ngay trên dòng hoặc trong ngăn chi tiết.
- Nội dung lâm sàng (tên thuốc, liều, chẩn đoán, diễn giải, căn cứ) không cắt bằng `…`. Chỉ mã ngắn, ngày giờ, huy hiệu mới giữ một dòng.
- Ngăn mở rộng nằm trong bảng phải rộng bằng vùng nhìn, không rộng theo bảng.
- Cuộn ngang chỉ là đường lùi khi cột giữa hẹp hơn 480 px.
- Nghiệm thu: đo ở 1280×800, 1440×900, 1920×1080 khi khung trợ lý mở; trong `main` không phần tử nào có `scrollWidth > clientWidth + 4` và không chữ nào vượt mép phải. Brief đầu tiên áp dụng: `plan/briefs/UI3-bo-cuc-co-gian-khi-mo-tro-ly.md`.

---

## 5. Thành phần

Thành phần nền đặt ở `web/src/components/ui/` (không biết gì về nghiệp vụ). Thành phần nghiệp vụ đặt ở `web/src/features/<vùng>/`.

### 5.1. Thành phần nền

| Thành phần | Quy định |
| :--- | :--- |
| `Button` | Biến thể: `primary` (nền `primary`, chữ trắng), `secondary` (nền `surface`, viền `line-strong`), `ghost` (không viền, di chuột nền `surface-muted`), `soft` (nền `primary-soft`, chữ `primary`), `danger-ghost`. Cỡ: `sm` cao 28, `md` cao 32 (mặc định), `lg` cao 40. Có chỗ cho biểu tượng trái; trạng thái đang chờ hiện `LoaderCircle` quay và vô hiệu nút |
| `Badge` | Dạng viên, cao 22, `text-xs` đậm 500, biểu tượng 14 + chữ. Biến thể theo 7 nghĩa ở 3.3, mỗi nghĩa có kiểu `soft` (nền `-bg`, chữ `-fg`, viền `-line`) và `outline` |
| `Card` | Nền `surface`, viền `line`, bo `md`, bóng `xs`. Có `CardHeader` (tiêu đề `text-md` + chỗ cho hành động bên phải), `CardBody` (lề 16) |
| `Dialog` | Radix. Rộng 640 (bản ghi) hoặc 800 (đoạn nguồn), bo `lg`, bóng `xl`, lớp phủ `rgba(16,24,40,.45)`. Đầu hộp: tiêu đề + nút đóng `X`. Thân cuộn riêng, cao tối đa 70vh. `Esc` đóng, tiêu điểm trả về nút đã mở |
| `Tabs` | Radix. Kiểu gạch chân: tab đang chọn chữ `primary` đậm 600, gạch 2 px; tab khác `fg-muted` |
| `SegmentedControl` | Radix toggle group. Dùng cho bộ lọc hàng đợi. Nền `surface-muted`, mục đang chọn nền `surface` + bóng `xs` |
| `Tooltip` | Radix. Trễ 300 ms, nền `fg`, chữ trắng `text-xs`. Mọi nút chỉ có biểu tượng phải có tooltip và `aria-label` |
| `Collapsible` / `Accordion` | Radix. Mũi tên `ChevronRight` xoay 90° khi mở |
| `DataTable` | Đầu bảng nền `surface-muted`, chữ `text-2xs` hoa. Dòng cao 36, viền dưới `line`, không kẻ sọc. Cột số canh phải, đều cột. Đầu bảng dính khi cuộn. Di chuột dòng: `surface-hover` |
| `Skeleton` | Khối `surface-muted` có ánh sáng lướt 1,2 giây. Hình dạng khớp nội dung sẽ hiện |
| `EmptyState` | Biểu tượng 32 màu `fg-disabled`, một dòng tiêu đề `text-md`, một dòng giải thích `text-sm`, tối đa một nút |
| `InlineAlert` | Dải một dòng trong nội dung: biểu tượng + câu + hành động tuỳ chọn. Biến thể theo nghĩa |
| `Toaster` | `sonner`, góc dưới phải, tự tắt sau 4 giây; lỗi không tự tắt |
| `Kbd` | Phím tắt: nền `surface-muted`, viền `line`, `text-2xs`, phông mono |
| `RecordId` | Mã bản ghi (`XN-DEMO02-01`): phông mono `text-xs`, màu `fg-subtle`, nền `surface-muted`, bo `sm`, lề ngang 6 |

### 5.2. Hàng đợi (`features/queue`)

- Tiêu đề "Y lệnh chờ thẩm định" + số lượng trong `Badge` trung tính. Bên dưới: `SegmentedControl` ba mục `Tất cả` · `Cần xem` · `Đã phản hồi`.
- Mỗi ca là một mục cao tối thiểu 76, lề 12:
  - Dòng 1: mã ca (`text-sm` đậm 600) bên trái; khoa (`text-xs`, `fg-subtle`) bên phải.
  - Dòng 2: các `Badge` đếm, chỉ hiện loại có số lớn hơn 0, theo thứ tự nghiêm trọng → cần lưu ý → thiếu dữ liệu. Ca không có gì: một `Badge` `success` "Đạt".
  - Dòng 3: mô tả ngắn, `text-sm`, `fg-muted`, tối đa 2 dòng rồi cắt bằng dấu ba chấm.
  - Bên trái mục có **dải dọc 3 px** màu `-solid` của mức cao nhất trong ca.
- Mục đang chọn: nền `primary-soft`, viền `primary-line`. Ca đã phản hồi hết: thêm biểu tượng `CheckCheck` màu `success` ở góc phải dòng 2.
- Bàn phím: `↑` `↓` đổi ca, `Enter` mở. Khi thu gọn còn 56 px: mỗi ca là một chấm tròn màu mức độ có tooltip mã ca.

### 5.3. Dải định danh ca (`features/case-header`)

Dính trên cùng vùng giữa, cao 56, nền `surface`, viền dưới `line`. Một hàng:

`DEMO-02` (`text-md` đậm) · `Nữ 75 tuổi` · `50,0 kg` · `Hô hấp, nội trú` — các mục cách nhau bằng dấu chấm giữa màu `fg-disabled`. Tiếp theo là hai ô nhấn:

- **CrCl:** ô nhỏ có nhãn `CrCl` (`text-2xs`) và giá trị; khi bất thường dùng kiểu `danger` mềm và biểu tượng `ArrowDown` (không dùng ký tự `▼`).
- **Dị ứng:** ba kiểu khác hẳn nhau: có dị ứng → `danger` + `ShieldAlert` + tên tác nhân; đã hỏi không có → `neutral` + `ShieldCheck`; chưa có thông tin → `missing` + `ShieldQuestion` + chữ `Chưa có thông tin dị ứng`.

Bên phải dải: ba số đếm dạng `Badge` (nghiêm trọng, cần lưu ý, thiếu dữ liệu).

### 5.4. Tóm tắt và chỉ số (`features/summary`)

- Ba thẻ ngang bằng nhau: **Chẩn đoán và cơ địa** · **Diễn biến mới nhất** · **Bất thường gần nhất**. Tiêu đề thẻ kiểu `text-2xs` hoa, `fg-subtle`. Nội dung `text-base`.
- Thẻ "Bất thường": mỗi xét nghiệm một dòng: tên, giá trị đậm kèm đơn vị, mũi tên `ArrowUp` / `ArrowDown` màu `danger`, dòng phụ `text-xs` "từ 150,0, sau 3 ngày · 10/11/2026 05:30".
- **Ô chỉ số** (4 ô một hàng): nhãn `text-xs` `fg-muted` ở trên; giá trị `text-metric` + đơn vị `text-xs` `fg-subtle` cùng dòng nền chữ; góc phải có nút biểu tượng `Calculator` mở popover "Đầu vào và công thức". Thiếu đầu vào: giá trị là `—`, bên dưới một `Badge` `missing` "Thiếu: cân nặng". Giá trị bất thường: chấm tròn 6 px màu `danger` cạnh nhãn.
- Popover công thức: bảng nhỏ ba cột (đầu vào, giá trị, thời điểm + `RecordId`), dưới cùng dòng trích dẫn tài liệu `text-xs` `fg-subtle`.

### 5.5. Thẻ nhận định (`features/findings`) – thành phần quan trọng nhất

```text
┃ ┌──────────────────────────────────────────────────────────────────────────┐
┃ │ [⛔ Nghiêm trọng] Cần xem          6 · Cơ địa và xét nghiệm    [⚖ Luật] │  ← đầu thẻ
┃ │                                                                          │
┃ │ Meropenem 1 g · truyền tĩnh mạch · 3 lần/ngày                            │  ← thuốc, text-sm, fg-muted
┃ │ CrCl 16,0 mL/phút: cần xem xét chỉnh liều theo chức năng thận.           │  ← nhận xét, text-base đậm 500
┃ │ Khuyến cáo trong nguồn: một nửa liều khuyến cáo, mỗi 12 giờ.             │
┃ │                                                                          │
┃ │ ┌ ✦ AI · đã kiểm chứng ──────────────────────────────────────────────┐   │  ← khối AI (nếu có)
┃ │ │ Diễn giải  …                                                       │   │
┃ │ │ Đề xuất    …                                                       │   │
┃ │ └────────────────────────────────────────────────────────────────────┘   │
┃ │                                                                          │
┃ │ › Căn cứ (3)   › Nguồn tài liệu (1)                                      │  ← mở thu gọn
┃ ├──────────────────────────────────────────────────────────────────────────┤
┃ │ Phản hồi:  [Đồng ý] [Bác bỏ] [Cần sửa]                                   │  ← chân thẻ, nền surface-muted
┃ └──────────────────────────────────────────────────────────────────────────┘
```

- **Dải dọc bên trái 4 px** màu `-solid` theo mức độ; đây là chỗ duy nhất dùng viền dày.
- **Đầu thẻ:** `Badge` mức độ (biểu tượng + chữ) rồi chữ kết luận `text-sm` `fg-muted`; bên phải là tên yếu tố (`text-xs`, `fg-subtle`, dạng `6 · Cơ địa và xét nghiệm`) và `Badge` nguồn gốc: `Luật` (kiểu `neutral`, biểu tượng `Scale`) hoặc `AI · đã kiểm chứng` (kiểu `ai`, biểu tượng `Sparkles`).
- **Thân thẻ không chia 3 cột có đầu cột nữa.** Bảng 3 cột "Thuốc | Yếu tố | Nhận xét" của bản cũ đọc như bảng tính và tốn chỗ. Thông tin vẫn đủ ba phần (thuốc, yếu tố, nhận xét) nhưng xếp dọc như hình trên: yếu tố lên đầu thẻ, thuốc là dòng phụ, nhận xét là dòng chính.
- **Khối AI:** nền `ai-bg`, viền `ai-line`, bo `sm`, lề 12. Tiêu đề khối: `Sparkles` + "AI · đã kiểm chứng" `text-xs` đậm 600 màu `ai-fg`. Hai dòng `Diễn giải` và `Đề xuất`: nhãn `text-xs` `fg-subtle` rộng cố định 72 px, nội dung `text-sm`.
- **Thẻ do AI thêm:** cùng bố cục, viền thẻ nét đứt màu `ai-line`, không có khối AI lồng bên trong (cả thẻ đã là của AI).
- **Căn cứ:** danh sách đánh số dạng dòng thời gian dọc: số trong vòng tròn 20 px nối nhau bằng đường kẻ 1 px `line`. Mỗi mục: `Badge` loại (`Dữ liệu ca` · `Phép tính` · `Tài liệu`) kiểu `outline`, câu mô tả `text-sm`, `RecordId` nếu có, nút `ghost` cỡ `sm` bên phải (`Mở bản ghi`, `Xem phép tính`, `Mở nguồn`).
- **Nguồn tài liệu:** mỗi mục có nhãn nguồn `text-sm` đậm 500 và câu trích trong khối có **viền trái 2 px `line-strong`**, chữ `text-sm` `fg-muted`.
- **Chân thẻ:** nền `surface-muted`, viền trên `line`. Chưa phản hồi: ba nút `secondary` cỡ `sm` có biểu tượng (`ThumbsUp`, `ThumbsDown`, `PencilLine`). Chọn `Bác bỏ` hoặc `Cần sửa`: mở tại chỗ nhóm lựa chọn lý do (radio dạng viên) + ô ghi chú + nút `Gửi`, `Huỷ`. Đã phản hồi: một dòng `CircleCheck` + "Đã phản hồi: Đồng ý · 16/11/2026 10:32" và nút `ghost` "Sửa".
- Giữa các thẻ cách 12. Tiêu đề vùng: "Bảng nhận định" `text-lg` + `Badge` số mục cần chú ý. Dòng "Chưa có luật kiểm tra cho yếu tố 3, 4, 5" là một `InlineAlert` trung tính ngay dưới tiêu đề.
- **Các mục đạt:** một `Collapsible` đóng sẵn, tiêu đề "Các mục đạt (3)" với `CircleCheck` màu `success`; mở ra là danh sách gọn mỗi mục một dòng (yếu tố, thuốc, nhận xét), không dùng thẻ đầy đủ.

### 5.6. Dải trạng thái AI

Đặt giữa tiêu đề "Bảng nhận định" và thẻ đầu tiên. `InlineAlert` kiểu `ai`:

- Đang chạy: `LoaderCircle` quay + "AI đang phân tích…" + các bước dạng chấm tiến độ (`Lấy nguồn` → `Tổng hợp` → `Kiểm chứng`); câu phụ "Bảng dưới đây là kết quả của bộ luật."
- Xong: `Sparkles` + câu tóm tắt + nút `ghost` "Chạy lại" (`RotateCw`).
- Lỗi: kiểu `warning`, `TriangleAlert` + câu + nút "Thử lại".

### 5.7. Chi tiết (`features/detail`)

Thẻ có `Tabs`: `Y lệnh` · `Xét nghiệm` · `Vi sinh` · `Diễn biến`. Bên trong dùng `DataTable`. Trong bảng xét nghiệm: giá trị ngoài ngưỡng đậm 600 màu `danger-fg` kèm mũi tên. Diễn biến: danh sách theo thời gian, mỗi mục có thời điểm (`text-xs`, `fg-subtle`), loại hồ sơ (`Badge` trung tính), nội dung là **văn bản thuần** giữ xuống dòng.

### 5.8. Khung hỏi thêm (`features/assistant`)

- Đầu khung: `MessageSquareText` + "Hỏi thêm về ca này" + nút `ghost` "Xoá hội thoại".
- Chưa có hội thoại: `EmptyState` nhỏ + các câu hỏi gợi ý dạng nút `soft` xếp dọc, canh trái, có `CornerDownRight`.
- Tin của người dùng: canh phải, nền `primary-soft`. Tin của hệ thống: canh trái, nền `surface`, viền `line`; trích dẫn đánh số dạng `Badge` bấm được.
- Ô soạn: dính đáy, ô nhập nhiều dòng tự giãn tối đa 6 dòng, nút gửi `primary` chỉ có biểu tượng `SendHorizontal`. Dòng nhắc `text-2xs`: "Trả lời tham khảo, có trích dẫn. Không dán dữ liệu người bệnh thật."
- Chưa nối được: `InlineAlert` trung tính "Chức năng hỏi thêm chưa sẵn sàng", ô soạn vô hiệu.

---

## 6. Trạng thái tải, rỗng, lỗi

| Tình huống | Hiển thị |
| :--- | :--- |
| Đang nạp danh sách ca | 5 `Skeleton` hình mục hàng đợi |
| Đang nạp một ca | `Skeleton` cho dải định danh, 3 thẻ tóm tắt, 4 ô chỉ số, 2 thẻ nhận định. Không dùng vòng quay giữa màn hình |
| Chưa chọn ca | `EmptyState` giữa vùng: `ClipboardList` + "Chọn một y lệnh ở danh sách bên trái" |
| Hàng đợi rỗng | `EmptyState`: "Không có y lệnh chờ thẩm định" |
| Ca lỗi dữ liệu | `InlineAlert` kiểu `danger` nêu tên tệp và lý do; các ca khác vẫn mở được |
| Mất kết nối API | `InlineAlert` kiểu `warning` ở đầu vùng + nút "Thử lại"; giữ nguyên dữ liệu đang hiện |
| Gửi phản hồi lỗi | Báo tại chỗ dưới nút, giữ nội dung đã nhập, và một thông báo nổi |

---

## 7. Khả năng tiếp cận và an toàn hiển thị

- Mọi thao tác làm được bằng bàn phím; thứ tự tab theo thứ tự đọc. Hộp thoại giữ tiêu điểm bên trong.
- Nút chỉ có biểu tượng phải có `aria-label` tiếng Việt và tooltip.
- Vùng trạng thái AI có `aria-live="polite"`.
- Cỡ chữ nhỏ nhất 11 px và chỉ dùng cho nhãn; nội dung lâm sàng không nhỏ hơn 13 px.
- Vùng bấm tối thiểu 28 × 28.
- **Chuỗi từ API là văn bản thuần** (P9 của plan 1.2): không chèn HTML thô, không diễn giải markdown, không tự biến chuỗi thành liên kết. Test `safety.test.ts` phải tiếp tục qua.

---

## 8. Tổ chức mã nguồn web

```text
web/src/
├─ app/                 # App.tsx, bố cục khung, nhà cung cấp (Tooltip, Toaster)
├─ components/ui/       # thành phần nền ở 5.1, không biết nghiệp vụ
├─ features/
│  ├─ queue/  case-header/  summary/  findings/  detail/  assistant/
├─ api/                 # giữ nguyên: types, client, mock
├─ state/               # giữ nguyên: các hook lấy dữ liệu
├─ lib/                 # cn(), hàm thuần trình bày; severity.ts ánh xạ mã → nghĩa → biểu tượng
└─ styles/
   ├─ theme.css         # @theme: toàn bộ biến ở mục 3
   └─ globals.css       # @import "tailwindcss"; nền, phông, kiểu gốc
```

- **Ánh xạ mức độ nằm ở đúng một chỗ:** `lib/severity.ts` nhận `ket_luan_ma`, `muc_do_ma`, `nguon_goc_ma` và trả về nghĩa (`danger`, `warning`, …), biểu tượng, nhãn. Thành phần không tự `if` theo mã.
- Không viết mã màu, cỡ chữ, khoảng cách bằng số trong thành phần; chỉ dùng lớp tiện ích sinh từ biến.
- Không còn file `.css` theo từng thành phần; các file ở `styles/` cũ bị thay bằng hai file trên.
- Web vẫn **không tự dịch mã, không tự làm tròn số**: mọi chuỗi hiển thị lấy từ API. Ngoại lệ duy nhất: thay ký tự `▲` `▼` trong dữ liệu bằng biểu tượng mũi tên, và bỏ các ký tự `⚠ ✓` đầu chuỗi nhãn nếu API còn gửi kèm.

---

## 9. Danh sách kiểm khi nghiệm thu giao diện

1. Ở 1366 × 768: không thanh cuộn ngang; dải định danh dính khi cuộn; thấy trọn ít nhất thẻ nhận định đầu tiên mà không phải cuộn.
2. Không còn ký tự `▲ ▼ ⚠ ✓ ⛔` dùng làm biểu tượng; không còn emoji.
3. Mọi nhãn mức độ có cả biểu tượng lẫn chữ.
4. Ba trạng thái dị ứng nhìn khác hẳn nhau.
5. Thẻ của luật và thẻ do AI thêm phân biệt được khi in đen trắng (viền đứt + nhãn).
6. Đi hết một ca chỉ bằng bàn phím: chọn ca, mở căn cứ, mở và đóng hộp thoại, gửi phản hồi.
7. Trong mã nguồn `web/src` (trừ `styles/theme.css`) không có mã màu dạng `#RRGGBB`, `rgb(`, `hsl(`.
8. `npm run build`, `npm run lint` (0 cảnh báo), `npx vitest run` đều đạt.
9. Người review chụp màn hình 6 ca demo và so với mục 5.
