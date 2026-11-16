# Giao diện web thẩm định y lệnh (React + TypeScript)

Ứng dụng web hỗ trợ dược sĩ lâm sàng thẩm định y lệnh theo 7 yếu tố, bám sát thiết kế ở `plan/plan-1.2-giao-dien-ui-ux.md` và hợp đồng dữ liệu ở `plan/api-hop-dong-v1.md`.

## Cách chạy

Chạy các lệnh sau bên trong thư mục `web/`:

- **Chạy độc lập với dữ liệu giả lập (không cần backend):**
  ```bash
  VITE_USE_MOCK=1 npm run dev
  ```
  Trên PowerShell (Windows):
  ```powershell
  $env:VITE_USE_MOCK="1"; npm run dev
  ```
- **Chạy nối backend FastAPI thật (cổng 8000):**
  1. Ở thư mục gốc dự án, bật backend: `uv run uvicorn app.api.main:app --port 8000`
  2. Trong `web/`, chạy: `npm run dev` (mở `http://localhost:5173`, Vite tự chuyển tiếp `/api` sang `http://localhost:8000`).
- **Đóng gói và kiểm tra:**
  ```bash
  npm run build
  npm run lint
  npx vitest run
  ```

## Cấu trúc thư mục `src/`

- `api/`: kiểu dữ liệu hợp đồng (`types.ts`), `ApiClient` gọi `/api` (`client.ts`), dữ liệu và client giả lập (`mockData.ts`, `mock.ts`, `index.ts`).
- `lib/`: hàm thuần xử lý hàng đợi (`queue.ts`), ánh xạ kiểu hiển thị theo mã và trích dẫn (`presentation.ts`), kiểu UI dùng chung (`uiTypes.ts`), lưu lựa chọn giao diện (`prefs.ts`).
- `state/`: các hook quản lý hàng đợi, chi tiết ca đệm trong phiên, phản hồi và hội thoại tách theo ca (`useCases.ts`, `useCaseDetail.ts`, `useFeedback.ts`, `useChat.ts`).
- `components/`: các thành phần giao diện (`StatusBanner`, `Queue`, `CaseHeader`, `Summary`, `MetricCard`, `FindingCard`, `EvidenceList`, `EvidenceDialog`, `FeedbackBar`, `PassedList`, `DetailTabs`, `ChatPanel`, `StateViews`).
- `styles/`: biến thiết kế (`tokens.css`), CSS nền (`base.css`) và CSS theo từng thành phần.

## Quy tắc an toàn hiển thị

- Không dùng `dangerouslySetInnerHTML`, `innerHTML`, `eval`, hay `new Function`.
- Mọi chuỗi từ API (kể cả nội dung diễn biến hay nhận xét có câu chèn lệnh) được hiển thị như nút văn bản thuần của React; không diễn giải markdown, không tự tạo liên kết, giữ xuống dòng bằng `white-space: pre-wrap`.
- Không lưu dữ liệu ca bệnh vào `localStorage` hay `sessionStorage` (`lib/prefs.ts` chỉ lưu mã ca đang chọn, bộ lọc hàng đợi và trạng thái thu gọn cột).
- Không gọi mạng tới địa chỉ ngoài `/api` và không nhúng tài nguyên bên ngoài.
