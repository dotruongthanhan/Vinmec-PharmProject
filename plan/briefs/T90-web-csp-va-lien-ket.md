# T90 – Web: CSP và chống nhúng khung (T2), bỏ dữ liệu giả khỏi bundle (L1), kiểm `https:` cho `url_goc` (L4)

Nguồn: `docs/bao-cao-bao-mat-2026-11-20.md` mục T2, L1, L4. Agent: agy `gemini-4-hydrogen-xhigh`. **Không gọi shell, không gọi mạng; chỉ đọc và ghi tệp.**

Song song: T91 sửa `web/src/state/useChat.ts` – **không đụng** tệp đó. Không đụng thư mục ngoài `web/`.

## Phạm vi tệp

Tạo: `web/vercel.json`, `web/public/theme-init.js`, test vitest cần thiết. Sửa: `web/index.html`, `web/src/api/index.ts` (và nơi gọi nó nếu cần đổi sang bất đồng bộ), `web/src/features/lookup/DrugDetailPage.tsx`, `web/src/lib/sourceLink.ts` (chỉ khi cần xuất hàm kiểm).

## 1. T2 – Tiêu đề bảo mật trên Vercel

Hiện tại `web/vercel.json` chỉ có trên nhánh `deploy/vercel`, nội dung:

```json
{
  "rewrites": [
    { "source": "/api/:path*", "destination": "https://vinmec-pharm.duckdns.org/api/:path*" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

Tạo `web/vercel.json` trên nhánh này: **giữ nguyên `rewrites`** ở trên, thêm `headers` cho `"source": "/(.*)"`:

- `Content-Security-Policy`: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data:; connect-src 'self' https://rfxatrybcoerbqxpziob.supabase.co; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'`
- `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`.

Script chọn giao diện sáng/tối đang nội tuyến trong `web/index.html` (thẻ `<script>` đầu tiên trong `<head>`) sẽ bị `script-src 'self'` chặn. **Chuyển nguyên văn** nội dung script đó sang `web/public/theme-init.js` và thay bằng `<script src="/theme-init.js"></script>` cùng vị trí (đồng bộ, không `defer`/`async`, để không nháy màu). Không còn script nội tuyến nào trong `index.html`.

Tìm trong `web/src` mọi nguồn ngoài khác mà trang tải hoặc gọi (`fetch` tuyệt đối, `new URL(` tới host khác, ảnh ngoài, font khác) và ghi vào báo cáo; nếu có thì thêm vào CSP tương ứng.

## 2. L1 – Chunk `mockData` có trong bundle production

`web/src/api/index.ts` nhập tĩnh `MockClient` (dòng 3, xuất lại dòng 10–11). Đổi để **chỉ** khi `import.meta.env.VITE_USE_MOCK === '1'` mới `await import('./mock.ts')`. Giữ API công khai cho test (test có thể nhập thẳng `./mock.ts`). Nếu hàm tạo client phải thành bất đồng bộ thì sửa nơi gọi tối thiểu; giải thích trong báo cáo. Bỏ xuất lại `MockClient` từ `index.ts` nếu chỉ test dùng (sửa import trong test sang `./mock.ts`).

## 3. L4 – `url_goc` vào `href` không kiểm `https:`

`DrugDetailPage.tsx` dòng ~154–156 đưa `part.url_goc` thẳng vào `href`. Dùng chung hàm kiểm `https:` mà `web/src/lib/sourceLink.ts` đang dùng cho `buildSourceLink` (xuất hàm đó nếu chưa xuất). Không phải `https:` → hiện văn bản không có liên kết.

## 4. Test (vitest)

- `index.html` không còn `<script>` nội tuyến (đọc tệp bằng `fs` trong test).
- `vercel.json` hợp lệ JSON, có đủ 5 tiêu đề, CSP có `frame-ancestors 'none'` và không có `'unsafe-eval'`, giữ 2 `rewrites`.
- Liên kết `url_goc` `javascript:alert(1)` và `http://…` không thành `<a>`; `https://…` thành `<a target="_blank" rel="noopener noreferrer">` (đối chiếu cách `buildSourceLink` đang đặt `rel`).

## 5. Nghiệm thu (Claude chạy)

```
cd web && npx tsc -b --noEmit && npx oxlint && npx vitest run && npm run build
```
Claude kiểm `dist/assets` không còn chunk `mockData`, và mở bản build với đúng tiêu đề CSP trong trình duyệt để soát lỗi CSP trên console (đăng nhập, danh sách ca, tra cứu thuốc).

## 6. Cấm

Không cài gói. Ghi `plan/reports/T90.md` theo mẫu `AGENTS.md`.
