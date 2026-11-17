# T23-bổ-sung-1 – Chế độ sáng và tối cho toàn bộ bản web

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort xhigh) làm chính; dự phòng agy `gemini-4-hydrogen-xhigh` · **Ngày:** 17/11/2026
**Điều kiện:** chỉ bắt đầu sau khi T23 đã xong (cùng sửa `web/src/`).
**Đọc trước (bắt buộc):** `AGENTS.md`; `plan/plan-1.4-he-thong-thiet-ke.md` mục 3 và 7; `plan/briefs/T23-trang-chu-dang-nhap-va-bo-cuc-ba-cot.md` mục 3; `web/src/styles/theme.css`, `globals.css`; toàn bộ `web/src/`.

## 1. Mục tiêu

Người dùng yêu cầu: nền tối là **một chế độ** của giao diện, có nút chuyển sáng / tối. Áp dụng cho cả trang chủ, trang đăng nhập và bàn làm việc. Không chuyển sang Next.js.

## 2. Yêu cầu

### 2.1. Cơ chế

- Ba lựa chọn: `Sáng`, `Tối`, `Theo hệ thống` (mặc định). Lưu bằng `lib/prefs.ts`.
- Chế độ đặt bằng thuộc tính `data-theme="light" | "dark"` trên `<html>`. `Theo hệ thống` thì theo `prefers-color-scheme` và đổi theo ngay khi hệ điều hành đổi.
- **Không nháy sai màu khi tải trang:** một đoạn mã ngắn đặt trong `web/index.html`, chạy trước khi React dựng, đọc lựa chọn đã lưu và đặt `data-theme`. Đoạn mã bọc `try/catch` (bộ nhớ trình duyệt có thể bị chặn), không dùng `innerHTML`.
- Đặt `color-scheme` tương ứng để thanh cuộn và ô nhập của trình duyệt đổi theo; thêm `<meta name="theme-color">` đổi theo chế độ.
- Nút chuyển: ở đáy thanh bên của bàn làm việc và ở thanh trên của trang chủ, trang đăng nhập. Là một điều khiển ba lựa chọn dùng `segmented-control` sẵn có, có nhãn chữ cho trình đọc màn hình; khi thanh bên thu gọn thì là một nút biểu tượng mở bảng chọn.
- Chuyển chế độ không tải lại trang, không mất trạng thái (ca đang mở, hội thoại, bộ lọc).

### 2.2. Biến màu

- Mọi màu trong mã giao diện đi qua biến của `theme.css`. Rà toàn bộ `web/src/`: không còn mã màu viết cứng (`#…`, `rgb(…)`, lớp Tailwind màu mặc định như `bg-white`, `text-gray-*`, `border-slate-*`) ngoài `theme.css`. Thêm một test quét mã nguồn để giữ điều này.
- Định nghĩa lại **toàn bộ** biến cho chế độ tối dưới `:root[data-theme="dark"]`:
  - Nền theo ba bậc độ sáng tăng dần: nền trang, bề mặt, bề mặt nổi. Không dùng đen tuyệt đối; dùng tông mực ngả xanh lục lam cùng họ với `--color-ink` để giữ nhận diện.
  - Chữ chính không dùng trắng tuyệt đối.
  - Màu nhấn và bảy bộ màu theo nghĩa (`danger`, `warning`, `missing`, `offlabel`, `success`, `ai`, `neutral`): giữ đúng sắc độ nhận biết, chỉnh độ sáng để chữ `-fg` trên nền `-bg` đạt tương phản tối thiểu 4,5:1; nền `-bg` ở chế độ tối là màu trầm, không phải màu phấn nhạt của chế độ sáng.
  - Bóng đổ ở chế độ tối gần như không thấy: dùng viền và bậc độ sáng của bề mặt để tách lớp.
- Thanh bên: ở chế độ sáng vẫn nền tối (`--color-ink`) như T23; ở chế độ tối, thanh bên tối hơn vùng làm việc một bậc và có đường kẻ ngăn cách.
- Trang chủ và trang đăng nhập: `--color-paper` có giá trị riêng cho chế độ tối; đoạn diễn hoạt chính và các khối tối đổi theo cho hài hoà.
- Biểu đồ xét nghiệm, phần tô nền câu trích dẫn, khung xương khi tải, viền tiêu điểm bàn phím: đều phải đọc rõ ở cả hai chế độ.

### 2.3. Kiểm tương phản bằng code

Thêm `lib/contrast.ts` (hàm thuần tính tỉ lệ tương phản theo WCAG từ hai mã màu) và một test đọc `theme.css`, lấy giá trị biến của từng chế độ rồi khẳng định:

- Chữ chính, chữ phụ trên nền trang và trên bề mặt: ≥ 4,5:1.
- Với cả bảy bộ màu theo nghĩa: `-fg` trên `-bg` ≥ 4,5:1.
- Chữ trên nút chính: ≥ 4,5:1.
- Viền tiêu điểm so với nền kề nó: ≥ 3:1.

Test phải chạy cho **cả hai** chế độ. Cặp nào không đạt thì chỉnh giá trị biến, không nới ngưỡng.

## 3. Phạm vi file

`web/src/**`, `web/index.html`. Không sửa `web/package.json`, không thêm gói. Không sửa `app/`, `plan/`, `config/`.

## 4. Kiểm thử phải có

- Hàm quyết định chế độ: (lựa chọn đã lưu, hệ thống đang tối hay sáng) → `light` hoặc `dark`; giá trị lưu hỏng → `Theo hệ thống`.
- Tính tương phản: đen trên trắng = 21; hai màu giống nhau = 1; một cặp đã biết.
- Test tương phản của `theme.css` ở mục 2.3.
- Test quét mã nguồn: không có mã màu viết cứng ngoài `theme.css`.
- Toàn bộ test hiện có vẫn qua; `safety.test.ts` vẫn qua.

## 5. Nghiệm thu (chạy trong `web/`)

```bash
npm run build
npm run lint
npx vitest run
```

Sau đó người review mở trình duyệt, chuyển từng chế độ ở trang chủ, trang đăng nhập, danh sách y lệnh, chi tiết DEMO-02 (thẻ nhận định, biểu đồ, hộp thoại nguồn) và khung trợ lý; tải lại trang ở chế độ tối để kiểm không nháy.

## 6. Cấm làm

Không đổi bố cục, câu chữ, hành vi nào khác của T23. Không thêm thư viện. Không commit, không push. Trả lời theo mẫu trong `AGENTS.md`.
