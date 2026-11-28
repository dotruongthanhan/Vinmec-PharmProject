# VZ1b – Hiện khối minh hoạ trong khung chat, có ngân sách hiệu năng cho máy công sở

Người làm: Codex gpt-6.1-terra high (được chạy `npx tsc -b`, `npx oxlint`, `npx vitest run` trong `web/`; không cài gói, không mạng, không commit).
Đọc trước: `AGENTS.md`; `plan/api-hop-dong-v1.10-minh-hoa.md` (**hợp đồng**); `plan/plan-1.4-he-thong-thiet-ke.md`; `plan/briefs/VZ0-bao-cao.md`; `web/src/features/minh-hoa/**` (bộ vẽ VZ0 đã duyệt); `web/src/features/assistant/AssistantPanel.tsx`, `HistoryDialog.tsx`; `web/src/api/types.ts`, `client.ts`, `mock.ts`; `web/src/__tests__/style-guard.test.ts`, `safety.test.ts`.
Phụ thuộc: VZ1a xong (API đã trả `minh_hoa`).

## Yêu cầu

1. **Kiểu và API:** `TraLoi.minh_hoa?: KhoiMinhHoa[]` theo hợp đồng v1.10 (thiếu trường → coi như `[]`). Mock (`mock.ts`) trả một khối mẫu (dùng `mau/lieu-meropenem-crcl.json`) cho câu hỏi chứa "minh hoạ" hoặc "meropenem" để dev không cần backend.
2. **Ngữ pháp `mh-1`:** mở rộng `nguPhap.ts` / `dungMoHinh.ts` cho `o_theo_khoang` (so sánh theo `bien_ve_tu/den`, `bao_gom_tu/den`; không phép tính số nào ngoài so sánh) và bộ dữ liệu có `can_cu`, cột `nhan`, kiểu `logic`. Test như VZ0 (tra khoảng đúng ở biên: 10, 25, 25.01, 50, 50.01).
3. **Trong khung chat:** dưới nội dung trả lời và trích dẫn, mỗi khối hiện bằng `KhungMinhHoa` (bản thu gọn cho bề rộng khung chat, mở rộng toàn màn như VZ0). Khối không qua `kiemDacTa` → "Không hiển thị được hình" + nút xem bảng. Lịch sử hội thoại: ghi "Hình minh hoạ không lưu trong lịch sử".
4. **Ngân sách hiệu năng (máy dược sĩ yếu) – bắt buộc:**
   - **Tải lười:** mã minh hoạ (`features/minh-hoa/**`) tách chunk riêng bằng `lazy()`; trang chat không có hình thì không tải chunk này. Ghi kích thước chunk (gzip) vào báo cáo; mục tiêu ≤ 35 KB gzip.
   - **Chỉ dựng khi nhìn thấy:** khối chưa vào khung nhìn (dùng `IntersectionObserver`, có đường lui khi không có) thì hiện khung giữ chỗ đúng chiều cao, chưa dựng SVG.
   - **Tin cũ thu gọn:** chỉ khối của **2 câu trả lời gần nhất** ở dạng tương tác; khối cũ hơn hiện thẻ gọn (tiêu đề + "Mở hình") để bấm mới dựng.
   - **Kéo thanh:** cập nhật bằng `requestAnimationFrame` hoặc `useDeferredValue`, không dựng lại cả khung chat; `dungMoHinh` được ghi nhớ theo (đặc tả, trạng thái điều khiển).
   - **Không hiệu ứng động** khi kéo (bỏ transition trên phần tử SVG); tôn trọng `prefers-reduced-motion`.
   - Test thuần: `dungMoHinh` cho lưới 2.000 dòng chạy < 30 ms trên máy test (đo `performance.now()`, chạy 5 lần lấy trung vị; ngưỡng ghi trong test).
5. **Trợ năng và giao diện:** theo plan 1.4, sáng/tối, không phân biệt chỉ bằng màu, phím mũi tên cho thanh kéo, vùng chạm ≥ 32 px, bề rộng khung chat tối thiểu 320 px không tràn ngang.
6. Gỡ route dev `/app/mau-minh-hoa`? **Không** – giữ để so sánh.

## Tệp

Được tạo/sửa: `web/src/features/minh-hoa/**`, `web/src/features/assistant/**`, `web/src/api/types.ts`, `web/src/api/mock.ts`, test trong `web/src/**/__tests__/`. Báo cáo `plan/briefs/VZ1b-bao-cao.md`.
Cấm: `app/**`, `tests/**` Python, `data/**`, `.env`, `plan/**` (trừ báo cáo); sửa `style-guard.test.ts`, `safety.test.ts`; thêm gói npm; `innerHTML`, `dangerouslySetInnerHTML`, `eval`, `new Function`, `iframe`; mạng; commit.

## Nghiệm thu (Claude chạy)

```
cd web && npx tsc -b && npx oxlint && npx vitest run && npx vite build
grep -rnE "innerHTML|dangerouslySetInnerHTML|new Function|eval\(|iframe" web/src/features/minh-hoa web/src/features/assistant   # rỗng
```
Claude kiểm e2e trên trình duyệt (API thật + DeepSeek, engine agentic): hỏi DEMO-02 về meropenem → hình hiện trong chat, kéo thanh, xem bảng, toàn màn, sáng/tối; Chrome giảm CPU 6× (DevTools) → kéo thanh không giật rõ, dựng hình < 100 ms (Performance); câu hỏi một con số → không có hình; tab Network: chunk minh hoạ chỉ tải khi có hình.

## Bổ sung 27/11 tối (Claude, sau khi VZ1a xong)

- Máy chủ đã trả `TraLoi.minh_hoa` thật (VZ1a-2 → VZ1a-5). Có một khối thật do DeepSeek tạo cho DEMO-02, đã qua bộ kiểm máy chủ: `C:\Users\Admin\AppData\Local\Temp\vzlive\khoi-that.json`. Khối có 3 bộ dữ liệu (lưới Cockcroft-Gault 195 dòng × 3 loại cân nặng, giá trị của ca, 4 mức liều meropenem), dùng `o` và `o_theo_khoang`, có 3 điều khiển. Claude đã tự tính lại 11 dòng lưới (khớp) và quét định danh (0).
  - **Chép khối này** thành `web/src/features/minh-hoa/mau/khoi-that-demo02.json`, rồi dùng nó làm mẫu cho mock và cho test: `kiemDacTa` phải đạt, và dựng mô hình ở creatinin 212 phải ra mức "Một nửa liều khuyến cáo, mỗi 12 giờ".
- `nguPhap.ts` hiện chỉ nhận `mh-0`; khối thật có `phien_ban: "mh-1"`. Bản web phải nhận cả hai.
- Máy chủ chỉ trả hình ở **hỏi đáp theo ca, engine agentic**. Chế độ chung luôn `[]`.
- RAM: chạy `vitest` một lần cho cả bộ là được; không chạy song song với lệnh nặng khác.
