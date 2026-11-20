# T23 – Trang chủ, đăng nhập, và bố cục ba cột mới của bàn làm việc

**Giao cho:** agy CLI (`gemini-4-hydrogen-xhigh`) · **Ngày:** 17/11/2026
**Đọc trước (bắt buộc):** `AGENTS.md`; `plan/plan-1.4-he-thong-thiet-ke.md` (biến thiết kế, thành phần, a11y, an toàn hiển thị – vẫn có hiệu lực, trừ mục 4 "Bố cục" được brief này thay); `plan/plan-1.2-giao-dien-ui-ux.md`; `plan/api-hop-dong-v1.md`, `v1.1`, **`v1.2-hoi-dap.md`**; toàn bộ `web/src/`.

**Chỉ sửa trong `web/`** (trừ `web/package.json`, `web/package-lock.json`: người review đã cài sẵn gói, xem mục 2). Không sửa `app/`, `plan/`, `config/`. **Không gọi công cụ shell** (gọi là cả phiên ra rỗng).

---

## 1. Vì sao làm lại

Người dùng xem bản hiện tại và nhận xét: sơ sài, trông "như bot làm", bố cục chưa giống một ứng dụng thật. Yêu cầu mới:

1. Có **trang chủ** giới thiệu sản phẩm, thiết kế có đầu tư.
2. Có **đăng nhập**; đăng nhập xong mới vào bàn làm việc.
3. Bàn làm việc ba cột: **trái** là thanh điều hướng tính năng (kiểu thanh bên của các ứng dụng làm việc hiện đại: mục điều hướng ở trên, các nhóm danh sách ở giữa, tài khoản ở đáy); **giữa** là danh sách y lệnh, mỗi y lệnh một dòng ngắn như phần mềm bệnh viện thật, bấm vào thì mở chi tiết; **phải** là trợ lý AI để dược sĩ gõ câu hỏi.
4. Tránh mọi dấu hiệu "giao diện do AI sinh" (mục 3.2).

Công nghệ: **giữ Vite + React + TypeScript + Tailwind v4 + Radix**, không chuyển Next.js (trang chủ tĩnh và ứng dụng sau đăng nhập không cần dựng phía máy chủ; backend là FastAPI; còn 3 ngày tới demo). Thêm định tuyến phía trình duyệt.

## 2. Gói đã được cài sẵn (bạn chỉ `import`, không chạy `npm`)

`react-router-dom`, `motion` (import từ `motion/react`), `@supabase/supabase-js`, `@fontsource-variable/fraunces`. Nếu khi viết code thấy `web/package.json` chưa có gói nào trong bốn gói này thì vẫn viết code bình thường và ghi rõ trong báo cáo. Không thêm gói nào khác; biểu đồ tự vẽ bằng SVG.

## 3. Định hướng thiết kế

### 3.1. Cá tính

Một công cụ lâm sàng cho người làm nghề: **điềm tĩnh, dày thông tin, chính xác**. Hình dung một tờ phiếu thẩm định được in cẩn thận, không phải trang quảng cáo phần mềm. Đẹp đến từ nhịp chữ, căn lề, tương phản và chi tiết nhỏ, không đến từ hiệu ứng.

- **Chữ:** Inter cho toàn bộ giao diện; JetBrains Mono cho mã, liều, số đo, thời điểm; **Fraunces** (chữ có chân) chỉ dùng cho tiêu đề lớn ở trang chủ, trang đăng nhập và tên màn hình. Số trong bảng dùng `tabular-nums`.
- **Màu:** giữ nguyên bảng màu theo nghĩa của `theme.css`. Thêm ba biến: `--color-ink: #0E1A1C` (nền thanh bên và các khối tối), `--color-ink-soft: #16272A`, `--color-paper: #FAF8F4` (nền trang chủ và trang đăng nhập). Màu nhấn duy nhất vẫn là `--color-primary`. Màu AI (`--color-ai-*`) chỉ dùng cho nhãn nguồn gốc AI, không dùng làm màu trang trí.
- **Thanh bên nền tối** (`--color-ink`), chữ sáng; vùng làm việc nền sáng. Tương phản này là nét nhận diện của ứng dụng.
- **Đường kẻ thay cho hộp:** ưu tiên đường kẻ mảnh 1px và khoảng trắng để chia vùng. Không bọc mọi thứ trong thẻ bo góc có bóng. Bo góc tối đa 8px cho thẻ, 6px cho nút và ô nhập. Bóng chỉ cho lớp nổi (hộp thoại, bảng chọn).
- **Chuyển động:** ngắn (120–220ms), có mục đích: mở dòng, trượt khung, số đếm thay đổi. Tôn trọng `prefers-reduced-motion`. Riêng trang chủ có một đoạn diễn hoạt chính (mục 4.2).

### 3.2. Danh sách cấm (dấu hiệu "AI slop")

- Dải màu chuyển tím – xanh, chữ tô dải màu, nền hạt sáng, hình cầu mờ, hiệu ứng kính mờ.
- Biểu tượng cảm xúc. Biểu tượng lấp lánh cạnh chữ "AI" (trừ một nhãn nguồn gốc `AI · đã kiểm chứng` đang có).
- Lưới ba thẻ giống hệt nhau, mỗi thẻ một biểu tượng trong ô vuông bo tròn, một tiêu đề, hai dòng mô tả.
- Số liệu thành tích, lời khen của khách hàng, logo đối tác, huy hiệu chứng nhận: **không có dữ liệu thật thì không được dựng**. Không dùng logo Bệnh viện X, Đơn vị đào tạo X; chỉ ghi tên bằng chữ.
- Câu sáo rỗng: "cách mạng hoá", "nâng tầm", "sức mạnh của AI", "liền mạch", "thông minh vượt trội". Câu chữ phải nói đúng việc hệ thống làm.
- Mọi thẻ đều có viền trái màu; mọi tiêu đề đều viết hoa giãn chữ; nút nào cũng có biểu tượng.
- Tính năng giả: mục điều hướng dẫn tới trang trống, nút bấm không làm gì, số đếm bịa. Thứ gì chưa có dữ liệu thật thì không hiện.
- Ảnh minh hoạ lấy từ kho ảnh, ảnh bác sĩ, hình người 3D.

## 4. Trang chủ (`/`)

Nền `--color-paper`. Bề rộng nội dung tối đa 1120px. Thanh trên cùng: tên sản phẩm bằng chữ ở trái, nút `Đăng nhập` ở phải.

### 4.1. Nội dung, theo thứ tự

1. **Mở đầu.** Tiêu đề Fraunces cỡ lớn, một câu nói đúng việc: hỗ trợ dược sĩ lâm sàng thẩm định y lệnh, mỗi nhận định đi kèm căn cứ mở ra được. Một đoạn mô tả hai câu. Một nút chính `Đăng nhập để vào bàn làm việc`. Bên cạnh hoặc bên dưới là **đoạn diễn hoạt chính** (4.2).
2. **Một nhận định đi từ đâu ra.** Trình bày đúng một ca (ca giả lập DEMO-02) như một vết truy theo chiều dọc, có đường nối giữa các bước: dữ liệu ca (creatinin 212 µmol/L) → công thức tính bằng code (CrCl 16,0 mL/phút, Cockcroft-Gault) → bộ luật đối chiếu bảng liều → đoạn nguồn trích nguyên văn từ nhãn thuốc → AI viết diễn giải → bước kiểm chứng trích dẫn và con số → dược sĩ quyết định. Mỗi bước ghi rõ ai làm: `code`, `tài liệu`, `AI`, `dược sĩ`. Số liệu lấy từ `mockData.ts`, không bịa thêm.
3. **Sáu yếu tố thẩm định.** Danh sách đánh số 1–6 (dùng tên yếu tố đang có trong ứng dụng), mỗi dòng ghi **trạng thái thật**: `đã có luật` hoặc `chưa có luật`. Hiện tại yếu tố 3, 4, 5 chưa có luật; ghi đúng như vậy. Đây là bảng kẻ dòng, không phải lưới thẻ.
4. **Giới hạn và nguyên tắc.** Bốn câu ngắn, trình bày như điều khoản đánh số: dược sĩ là người quyết định; hệ thống không ghi vào hồ sơ bệnh án, không gửi y lệnh; dữ liệu trong bản thử là giả lập; thiếu dữ liệu thì hệ thống nói thiếu chứ không ghi "đạt".
5. **Chân trang.** Một dòng: bản thử nghiệm học thuật trong chương trình AI Sprint 6 tuần (Đơn vị đào tạo X × Bệnh viện X), Khoa Dược; năm 2026. Không tên người, không logo.

### 4.2. Đoạn diễn hoạt chính

Dựng bằng chính các thành phần của ứng dụng (không dùng ảnh chụp): một dòng y lệnh `Meropenem 1 g · truyền tĩnh mạch · 3 lần/ngày` hiện ra; chỉ số CrCl đếm tới 16,0; nhãn `Nghiêm trọng · Cần xem` gắn vào dòng; một đoạn trích nguồn trượt ra với cụm `10-25 | One-half recommended dose | Every 12 hours` được tô nền. Chạy một lần khi vào khung nhìn, dừng ở trạng thái cuối; có nút nhỏ `Xem lại`. Khi `prefers-reduced-motion`: hiện luôn trạng thái cuối.

Các mục 2–5 hiện dần khi cuộn tới (mờ và trượt 8px, một lần). Không có hiệu ứng nào chạy lặp vô hạn.

## 5. Đăng nhập (`/dang-nhap`)

- Bố cục hai nửa trên màn hình rộng: nửa trái nền `--color-ink` với tên sản phẩm và một câu Fraunces; nửa phải là biểu mẫu trên nền `--color-paper`. Màn hình hẹp: chỉ còn biểu mẫu.
- Biểu mẫu: thư điện tử, mật khẩu (có nút hiện/ẩn), nút `Đăng nhập`. Nhãn nằm trên ô nhập; lỗi hiện ngay dưới ô, bằng chữ, có `aria-describedby`. Nút ở trạng thái đang gửi thì khoá và hiện chỉ báo.
- Xác thực bằng **Supabase Auth** (`signInWithPassword`), đọc `import.meta.env.VITE_SUPABASE_URL` và `VITE_SUPABASE_ANON_KEY`. Tạo `web/.env.example` chỉ có hai tên biến này. **Không đọc tệp `.env` ở gốc kho, không ghi giá trị khoá vào bất kỳ tệp nào.**
- Thiếu hai biến trên: không dựng máy khách Supabase; trang đăng nhập hiện một dải thông báo `Chưa cấu hình xác thực. Đang ở chế độ demo, không kiểm tra tài khoản.` và một nút `Vào bản demo`. Ở chế độ demo, thanh trên của bàn làm việc luôn hiện nhãn `Demo · không xác thực`.
- Không có đăng ký, không có quên mật khẩu, không có đăng nhập mạng xã hội (chưa có thật thì không hiện).
- Phiên đăng nhập do Supabase giữ; `AuthProvider` + `useAuth()` đặt ở `web/src/features/auth/`. Tuyến `/app/*` được bảo vệ: chưa đăng nhập thì chuyển về `/dang-nhap` và nhớ đường dẫn để quay lại. Đăng xuất ở đáy thanh bên.
- Ghi chú trong báo cáo: backend chưa kiểm tra mã phiên của Supabase; đây là việc của task sau.

## 6. Bàn làm việc (`/app`)

```
┌───────────┬──────────────────────────────────────┬─────────────────┐
│ THANH BÊN │ VÙNG GIỮA                            │ TRỢ LÝ          │
│ 248px     │ co giãn, tối thiểu 560px             │ 400px (320–560) │
│ nền tối   │ /app            → danh sách y lệnh   │ kéo đổi rộng,   │
│ thu 56px  │ /app/y-lenh/:id → chi tiết y lệnh    │ thu gọn được    │
└───────────┴──────────────────────────────────────┴─────────────────┘
```

Thanh trên cùng của vùng giữa cao 48px: đường dẫn (`Y lệnh` › mã y lệnh), ô tìm kiếm, nhãn chế độ (`Dữ liệu giả lập`, `AI bật/tắt`, `Demo`), nút mở/đóng trợ lý. Trạng thái thu gọn của hai cột bên và bề rộng trợ lý lưu bằng `lib/prefs.ts`.

### 6.1. Thanh bên trái

Từ trên xuống:

1. Tên sản phẩm (chữ, không logo) và nút thu gọn.
2. **Tìm kiếm** (`Ctrl K`): đưa con trỏ vào ô tìm của danh sách; lọc phía trình duyệt theo mã y lệnh, tên thuốc, khoa, tóm tắt.
3. Nhóm **Y lệnh** – các bộ lọc thật của danh sách, mỗi mục có số đếm thật: `Tất cả`, `Cần xem` (có nhận định nghiêm trọng hoặc cần lưu ý), `Thiếu dữ liệu`, `Đạt`, `Đã phản hồi`.
4. Nhóm **Theo khoa** – sinh từ dữ liệu `/api/cases` (các khoa có trong danh sách, kèm số đếm).
5. Nhóm **Hội thoại gần đây** – các ca đã có ít nhất một câu hỏi trong phiên này (lấy từ trạng thái trò chuyện phía trình duyệt); bấm vào thì mở ca đó. Không có thì ẩn cả nhóm.
6. Đáy: thư điện tử của người dùng (hoặc `Chế độ demo`), nút `Đăng xuất`.

Thu gọn còn 56px: chỉ còn biểu tượng, có chú giải khi rê chuột. Mục đang chọn: nền `--color-ink-soft`, vạch 2px màu nhấn ở mép trái. Điều hướng bằng bàn phím đầy đủ. **Không thêm mục nào khác** (không có trang cài đặt, báo cáo, tra cứu thuốc: chưa có tính năng thật).

### 6.2. Danh sách y lệnh (vùng giữa, `/app`)

Một bảng dày, mỗi y lệnh **một dòng cao 44px**, không phải thẻ. Cột:

| Cột | Nội dung | Ghi chú |
| :--- | :--- | :--- |
| (chấm màu) | Mức cao nhất của y lệnh | Kèm chữ ẩn cho trình đọc màn hình; màu không phải tín hiệu duy nhất vì cột "Kết quả" có chữ |
| Thời điểm kê | `05:50 · 10/11` | Chữ đơn cách |
| Mã y lệnh | `YL-DEMO-02` | Chữ đơn cách |
| Người bệnh | `Nữ, 75 tuổi` | Không hiện họ tên |
| Khoa | `Hô hấp` | |
| Thuốc | Thuốc đầu tiên, có `+n` nếu nhiều hơn | Cắt bằng dấu ba chấm, có chú giải đủ |
| Kết quả | Nhãn mức và số lượng: `1 nghiêm trọng`, `Đạt`, `Thiếu dữ liệu` | Dùng `Badge` sẵn có |
| Phản hồi | Dấu đã phản hồi hoặc trống | |

- Dùng đúng dữ liệu `/api/cases` đang có; mỗi ca demo là một y lệnh. Trường nào danh sách không trả về thì bỏ cột đó và ghi vào báo cáo, **không tự đổi hợp đồng API, không bịa dữ liệu**.
- Tiêu đề cột dính trên; sắp xếp mặc định: mức nghiêm trọng giảm dần rồi thời điểm kê; bấm tiêu đề cột `Thời điểm kê` và `Kết quả` để đổi thứ tự.
- Phía trên bảng: tên bộ lọc đang chọn (Fraunces), số y lệnh, ô tìm.
- Bàn phím: `↑` `↓` chuyển dòng, `Enter` mở, dòng đang có tiêu điểm có viền rõ. Cả dòng bấm được.
- Trạng thái: đang tải (khung xương đúng hình dòng), rỗng theo bộ lọc, lỗi mạng có nút thử lại. Dùng lại `features/states`.

### 6.3. Chi tiết y lệnh (vùng giữa, `/app/y-lenh/:caId`)

Sắp lại các thành phần sẵn có, **y lệnh đứng trước nhận định**:

1. **Dải người bệnh** dính trên: tuổi, giới, cân nặng, khoa, dị ứng, chẩn đoán chính, và bốn chỉ số tính toán (CrCl, eGFR, BMI, BSA) thành một hàng gọn chữ đơn cách; bấm một chỉ số mở phép tính như hiện nay. Nút `‹ Y lệnh trước` / `Y lệnh sau ›` và nút quay về danh sách.
2. **Hàng thẻ chuyển:** `Thẩm định` (mặc định) · `Xét nghiệm` · `Vi sinh` · `Diễn biến`. Thẻ đang mở ghi vào tham số đường dẫn.
3. Trong thẻ **Thẩm định**:
   - Bảng **Y lệnh**: mỗi thuốc một dòng (thuốc, liều, tần suất, đường dùng, lịch dùng, nhãn kết quả). Bấm một dòng để chỉ hiện nhận định của thuốc đó; bấm lại để bỏ lọc.
   - **Dải sáu yếu tố**: sáu ô đánh số trên một hàng, mỗi ô một trong bốn trạng thái có chữ và biểu tượng riêng: `có vấn đề`, `đạt`, `thiếu dữ liệu`, `chưa có luật`. Thay cho dòng thông báo "Chưa có luật kiểm tra cho các yếu tố…" hiện nay. Bấm một ô để cuộn tới nhận định của yếu tố đó.
   - Dải trạng thái AI, rồi các **thẻ nhận định** như hiện nay, thêm nút `Hỏi về mục này` trên mỗi thẻ (mục 6.4). Sửa trong thẻ: gộp căn cứ loại "Tài liệu" với nhóm "Nguồn tài liệu" để không lặp; bỏ câu "Nguyên văn đoạn nguồn sẽ có khi nối kho tri thức" khi thẻ đã có trích dẫn nguồn.
   - Mục `Các mục đạt` thu gọn ở cuối.
4. Thẻ **Xét nghiệm**: với mỗi chỉ số có từ 2 kết quả trở lên, vẽ **biểu đồ đường bằng SVG** phía trên bảng: trục thời gian, vùng tô nhạt cho khoảng tham chiếu, điểm ngoài ngưỡng tô màu cảnh báo và có nhãn giá trị, một vạch dọc đánh dấu thời điểm kê y lệnh. Có `<title>`/`aria-label` mô tả xu hướng bằng chữ. Chỉ số chỉ có 1 kết quả: không vẽ. Không ngoại suy, không vẽ đường dự đoán.
5. Dọn chữ thô ở tầng hiển thị (`lib/displayFormat.ts`): thời điểm dạng ISO → `05:30 · 10/11/2026`; `umol/L` → `µmol/L`; `thuc_te` / `ly_tuong` / `hieu_chinh` → `thực tế` / `lý tưởng` / `hiệu chỉnh`; số thập phân dùng dấu phẩy. Bỏ dòng "Thời gian chạy" ở chân trang.

### 6.4. Trợ lý AI (cột phải)

- Đầu khung: tiêu đề `Trợ lý`, hai thẻ `Hỏi đáp` · `Nguồn`, nút thu gọn.
- **Chưa mở y lệnh nào:** trạng thái rỗng, một câu: `Mở một y lệnh để hỏi về ca đó.` Ô nhập khoá.
- **Đã mở y lệnh:** dòng ngữ cảnh ngay trên ô nhập: `Đang hỏi về: YL-DEMO-02`; nếu dược sĩ bấm `Hỏi về mục này` trên một thẻ nhận định thì thêm một nhãn gỡ được ghi tên nhận định, và gửi `nhan_dinh_id` theo hợp đồng v1.2.
- Hội thoại giữ riêng theo từng ca trong phiên; đổi ca không lẫn tin. Câu trả lời về muộn của ca cũ không được ghi vào ca đang mở.
- Tin của dược sĩ căn phải, nền `--color-surface-muted`. Tin của trợ lý **không dùng bong bóng**: chữ thường trên nền khung, có đường kẻ mảnh ngăn cách, phía dưới là danh sách trích dẫn đánh số. Dấu `[n]` trong `noi_dung` dựng thành nút nhỏ (tách chuỗi rồi dựng bằng phần tử React, không chèn HTML); bấm → mở thẻ `Nguồn` cùng khung, hiện đoạn nguồn với câu trích được tô nền (`getSource`), hoặc mở bản ghi của ca nếu trích dẫn là dữ liệu ca.
- Theo `trang_thai`: `ok` hiện bình thường; `khong_co_nguon`, `ngoai_pham_vi` hiện `noi_dung` kèm nhãn trung tính tương ứng; `loi` hiện thông báo và nút `Gửi lại`; `chua_san_sang` hiện một dòng `Máy chủ chưa bật trợ lý.` và khoá ô nhập.
- Đang chờ: một dòng `Đang tra cứu dữ liệu ca và nguồn…` có chỉ báo; nút gửi đổi thành `Dừng` (huỷ yêu cầu bằng `AbortController`).
- Câu hỏi gợi ý: tối đa ba, sinh từ dữ liệu ca (ví dụ từ nhận định cần xem đầu tiên: `Vì sao cần xem lại liều <tên thuốc>?`); bấm là điền vào ô nhập, không tự gửi.
- Ô nhập nhiều dòng, `Enter` gửi, `Shift Enter` xuống dòng, giới hạn 1000 ký tự có bộ đếm khi còn dưới 100. Dưới ô nhập một dòng nhỏ: `Trả lời để tham khảo. Dược sĩ kiểm chứng và quyết định.`
- Bản giả lập (`mock.ts`): trả lời sau khoảng 1,5 giây theo đúng lược đồ v1.2, có một trích dẫn tài liệu và một trích dẫn dữ liệu ca cho DEMO-02; các ca khác trả `khong_co_nguon`.
- Màn hình hẹp hơn 1180px: trợ lý thành lớp trượt đè từ phải, mở bằng nút trên thanh trên; hẹp hơn 900px: thanh bên cũng thành lớp trượt.

## 7. Tổ chức mã nguồn

- Định tuyến ở `web/src/app/router.tsx`: `/`, `/dang-nhap`, `/app`, `/app/y-lenh/:caId`, và trang không tìm thấy. Trang chủ và trang đăng nhập nạp lười (`lazy`) để không kéo mã bàn làm việc.
- Thư mục mới: `features/landing/`, `features/auth/`, `features/sidebar/`, `features/orders/` (danh sách), `features/order-detail/` (bọc lại `case-header`, `summary`, `findings`, `detail`), `features/charts/` (biểu đồ SVG). `features/queue/` bỏ sau khi chuyển xong; không để lại file chết.
- Logic thuần đặt ở `lib/` để kiểm thử không cần DOM: lọc và đếm theo bộ lọc, sắp xếp danh sách, tách `[n]` trong câu trả lời, tính toạ độ biểu đồ (thang đo, vùng tham chiếu), định dạng hiển thị, quyết định trạng thái của sáu yếu tố.
- Lớp API: thêm trường v1.2 vào `types.ts`, `client.ts`, `mock.ts`. Không đổi tên trường nào.
- Phần xác thực không được làm bộ test hiện có cần mạng: máy khách Supabase dựng lười và bọc sau một giao diện nhỏ để thay bằng bản giả khi thử.

## 8. An toàn hiển thị (bắt buộc, như plan 1.4 mục 7)

Mọi chuỗi từ API hiển thị dưới dạng văn bản thuần của React. Không chèn HTML thô, không diễn giải markdown, không tự biến chuỗi thành liên kết hay ảnh. Liên kết ngoài duy nhất là `url_goc` bắt đầu bằng `https://`. `safety.test.ts` phải tiếp tục qua. Không lưu mật khẩu, mã phiên vào `localStorage` bằng code tự viết (để Supabase tự quản).

## 9. Kiểm thử phải có (`vitest`, môi trường `node`)

- Bộ lọc và số đếm của thanh bên với dữ liệu giả 6 ca: tổng các nhóm đúng; ca có cả nghiêm trọng và thiếu dữ liệu được đếm đúng ở từng nhóm.
- Sắp xếp danh sách: mức giảm dần rồi thời điểm; ổn định khi bằng nhau.
- Tìm kiếm: không phân biệt hoa thường và dấu tiếng Việt.
- Tách `[n]`: `a [1] b [2].` → 5 phần; số không có trong `trich_dan` giữ nguyên là chữ; chuỗi không có dấu ngoặc → 1 phần.
- Biểu đồ: thang đo với 2 điểm, với các giá trị bằng nhau (không chia cho 0), điểm ngoài khoảng tham chiếu được đánh dấu.
- Định dạng: thời điểm ISO có múi giờ, đơn vị `umol/L`, ba loại cân nặng, số thập phân.
- Trạng thái sáu yếu tố: yếu tố không có luật → `chưa có luật`, không bao giờ ra `đạt`.
- Trò chuyện: hội thoại tách theo ca; trả lời về muộn của ca cũ bị bỏ; `chua_san_sang` khoá ô nhập (kiểm ở hàm thuần quyết định trạng thái).
- Bảo vệ tuyến: hàm thuần quyết định chuyển hướng theo (đã đăng nhập, chế độ demo, đường dẫn).
- Toàn bộ test hiện có vẫn qua.

## 10. Nghiệm thu (người review chạy trong `web/`)

```bash
npm run build
npm run lint
npx vitest run
```

`npm run lint` không còn cảnh báo. Sau đó người review mở trình duyệt ở 1440px, 1180px, 900px, 390px và soát theo danh sách kiểm của plan 1.4 mục 9 cộng danh sách cấm ở mục 3.2 của brief này.

## 11. Cấm làm

- Không sửa ngoài `web/`. Không sửa `package.json`. Không chạy `npm`. Không gọi công cụ shell.
- Không đổi tên trường của hợp đồng; thấy thiếu thì ghi vào báo cáo.
- Không bịa nội dung y khoa, số liệu, tên người, lời chứng thực. Câu chữ y khoa ở trang chủ chỉ lấy từ `mockData.ts`.
- Không đọc, không ghi tệp `.env` nào có giá trị khoá.
- Không commit, không push. Xong thì trả lời theo mẫu báo cáo trong `AGENTS.md`, ghi rõ chưa chạy lệnh nào.
