# Plan 1.10 – Tiến trình phân tích AI minh bạch (giao diện + API)

Ngày 21/11/2026. Người dùng chốt phương án A: làm ngay, mô hình bước tổng quát, chạy trên đồ thị 3 nút hiện tại; agentic RAG (plan 1.9) sau này chỉ phát thêm bước.

## 1. Vì sao

Dược sĩ muốn biết AI đang làm gì, còn bao lâu, dựa vào nguồn nào, và hỏng thì làm gì. Hiện tại dải `AiStatusBar` chỉ có vòng xoay và ba chấm cố định "Lấy nguồn · Tổng hợp · Kiểm chứng" (độ mờ vẽ sẵn, không phản ánh bước thật). API chỉ trả `dang_chay | xong | loi`, đồ thị chạy `invoke` một mạch nên không biết bước nào đang chạy.

## 2. Mục tiêu / không mục tiêu

Mục tiêu: danh sách bước thật, từng bước có trạng thái (chờ, đang chạy, xong, lỗi, bỏ qua), chi tiết ngắn, thời gian; đồng hồ tổng; ước lượng "thường mất"; bước lấy nguồn nói rõ nguồn nào; bước lỗi nói lý do và việc nên làm; thu gọn thành một dòng khi xong; bảng luật luôn dùng được.

Không mục tiêu: hiện suy nghĩ thô hay nội dung mô hình đang viết; phần trăm tiến độ; SSE hay WebSocket (vẫn hỏi lại định kỳ); mở đoạn trích từ danh sách bước (kết quả cuối đã có trích dẫn); đụng logic luật, kiểm chứng, đồ thị.

Phản mục tiêu: giao diện giả vờ chạy (đồng hồ giả, bước giả). Lỗi phải là lỗi thật.

## 3. Phương án đã cân nhắc

- **A (chọn)**: danh sách sự kiện nối thêm ở backend, web vẽ danh sách. Có minh bạch ngay; agentic RAG chỉ thêm dòng.
- B: đợi agentic RAG. Chưa rõ thời gian, AI vẫn "im" lúc giám khảo chấm, thiết kế khi chưa biết dạng sự kiện.
- C: chỉ sửa web bằng đồng hồ giả. Không thật, trái mục tiêu.

## 4. Hợp đồng API (bổ sung v1.10, chỉ thêm trường, tương thích ngược)

`KetQuaAI` (POST và GET `/api/cases/{ca_id}/ai`) thêm ba trường có mặc định:

| Trường | Kiểu | Ý nghĩa |
| :--- | :--- | :--- |
| `cac_buoc` | `BuocAI[]` (mặc định `[]`) | Các bước theo thứ tự nối thêm; có ở mọi trạng thái trừ `tat` |
| `da_chay_ms` | `number \| null` | Thời gian đã chạy tại thời điểm trả lời (đang chạy) hoặc tổng (xong, lỗi) |
| `thuong_le_ms` | `number \| null` | Trung vị thời gian của các lượt xong gần nhất (tối đa 20, cần ít nhất 3 lượt), ngược lại `null` |

`BuocAI`:

| Trường | Kiểu | Ghi chú |
| :--- | :--- | :--- |
| `ma` | string | `thu_thap_nguon`, `tong_hop_1`, `kiem_chung_1`, `tong_hop_2`, `kiem_chung_2`, ... |
| `ten` | string | Tiếng Việt, hiển thị thẳng |
| `trang_thai` | `cho \| dang_chay \| xong \| loi \| bo_qua` | |
| `chi_tiet` | string \| null | Tối đa 160 ký tự. Chỉ số đếm, tên nhãn nguồn, mã lỗi |
| `nguon` | `{nhan: string, so_doan: int}[]` (mặc định `[]`) | Chỉ ở bước lấy nguồn |
| `thoi_gian_ms` | number \| null | Bước xong: thời lượng; đang chạy: đã chạy tới lúc trả lời |
| `ly_do` | string \| null | Chỉ bước lỗi, tiếng Việt, không lộ dữ liệu ca |
| `goi_y` | string \| null | Chỉ bước lỗi, việc dược sĩ nên làm |

Bộ bước ban đầu (đăng ký sẵn ở trạng thái `cho` khi tác vụ khởi động): `thu_thap_nguon` "Lấy nguồn", `tong_hop_1` "Tổng hợp nhận định", `kiem_chung_1` "Kiểm chứng trích dẫn". Khi vòng thử lại của bộ tổng hợp chạy lần 2 trở đi thì nối thêm `tong_hop_n` ("Tổng hợp lại, lần n") và `kiem_chung_n` ("Kiểm chứng lại, lần n"). Khi tác vụ kết thúc, mọi bước còn `cho` hoặc `dang_chay` được chốt: tác vụ lỗi thì bước đang chạy thành `loi`, bước chờ thành `bo_qua`; tác vụ xong thì bước chờ thành `bo_qua`.

## 5. Thiết kế backend

- Mô-đun mới `app/orchestration/progress.py`: mô hình `BuocTienTrinh`, `NguonTomTat`, lớp `TienTrinh` (an toàn đa luồng, nối thêm, `dang_ky`, `bat_dau`, `xong`, `loi`, `chot`, `chup(now)`), và `ContextVar` `tien_trinh_hien_tai` cùng hàm tiện ích `ghi_buoc(...)` không làm gì khi không có bộ ghi. Dùng ContextVar để KHÔNG đổi chữ ký `AiRunner.run`, `Synthesizer.run`, `EvidenceCollector.collect` (nhiều test dùng bản giả).
- `AiJobManager` (`app/orchestration/jobs.py`): mỗi tác vụ tạo một `TienTrinh`, đặt vào ContextVar trong luồng nền trước khi gọi `fn()`, lưu vào `AiJobState.tien_trinh`; chốt khi kết thúc; lưu thời lượng các lượt xong (tối đa 20) để tính `thuong_le_ms`.
- Điểm ghi sự kiện: `ThuThapNguon` (đầu/cuối, tên nhãn nguồn và số đoạn nhóm theo `Chunk.nguon`), `Synthesizer._run_with_llm` (mỗi lượt: bắt đầu gọi mô hình, nhận đầu ra, kiểm chứng "x/y dòng đạt", lỗi nhà cung cấp với `goi_y`). Nhánh `an_toan` bắt lỗi nút thì đánh dấu bước đang chạy là `loi`.
- `service._present_job_state`, `start_ai`, `get_ai` gắn `cac_buoc`, `da_chay_ms`, `thuong_le_ms` vào `KetQuaAI` (kể cả khi `xong` qua `present_ai_result`).

### Bảo mật (bắt buộc)

- `chi_tiet`, `nguon`, `ly_do`, `goi_y` chỉ chứa số đếm, nhãn nguồn công khai, mã lỗi đã lọc (`isidentifier`), thời gian. Cấm đưa: nội dung hồ sơ, tên thuốc theo ca, nội dung prompt hay đầu ra mô hình, thông điệp ngoại lệ thô. Có test cố ý đưa chuỗi tên người bệnh vào ca rồi khẳng định không xuất hiện trong JSON `cac_buoc`.
- Mọi chuỗi bị cắt 160 ký tự; số bước tối đa 40 (chặn vòng lặp vô hạn); không ghi nội dung bước vào log.
- Quyền truy cập: thừa hưởng GET/POST `/ai` hiện có (người gọi hợp lệ, kiểm ca tồn tại). Không có điểm cuối mới.
- Hỏi lại định kỳ: giữ nguyên giới hạn tốc độ đang có cho GET; web hỏi mỗi 1,5 giây khi đang chạy (không hỏi khi tab ẩn).

## 6. Thiết kế giao diện

Thay nhánh `dang_chay` của `AiStatusBar` bằng thành phần `AiProgressPanel`:

```
✦ AI đang phân tích ca này            14s · thường 20–40s
 ✓ Lấy nguồn            12 đoạn · openFDA 6, Bộ Y tế 4, DDInter 2   1,2s
 ◌ Tổng hợp nhận định   đang gọi mô hình…                           8,4s
 ○ Kiểm chứng trích dẫn
 ─ Bảng bên dưới là kết quả của bộ luật, vẫn dùng được.
```

- Biểu tượng + chữ, không dựa vào màu một mình. `prefers-reduced-motion`: bỏ xoay, dùng chấm tĩnh.
- Đồng hồ nội suy phía web giữa hai lần hỏi (không đọc to trong `aria-live`); vùng `aria-live="polite"` chỉ thông báo khi bước đổi trạng thái.
- Chậm: bước đang chạy quá 30 giây hoặc tổng vượt `thuong_le_ms` × 1,5 thì hiện dòng "Bước X đang lâu hơn thường lệ. Bảng luật vẫn dùng được." Không tự hủy, vẫn tôn trọng trần 120 giây hiện có.
- Lỗi: bước lỗi nền cảnh báo (không đỏ cả khối), nêu `ly_do` và `goi_y`, nút "Thử lại" như hiện tại; bước bỏ qua mờ đi.
- Xong: thu thành một dòng tóm tắt (như `AiStatusBar` hiện tại) kèm nút "Xem các bước (n)" mở lại danh sách, `aria-expanded`.
- Dùng token thiết kế sẵn (`bg-ai`, `text-ai-fg`, `size-4`, lucide-react), bám plan 1.4.
- Chế độ mock (`web/src/api/mock.ts`) mô phỏng chuỗi bước theo thời gian để xem và test không cần backend.

## 7. Kiểm thử và nghiệm thu

Backend: `uv run pytest tests/orchestration tests/api -q` và `uv run ruff check .` xanh; test mới cho `TienTrinh` (thứ tự, chốt, giới hạn), cho ContextVar không rò sang tác vụ khác, cho `cac_buoc` trong JSON ở trạng thái đang chạy/xong/lỗi, test riêng chuỗi nhạy cảm không lọt.

Web: `npm run test`, `npx tsc --noEmit`, lint sạch; test cho `AiProgressPanel` (từng trạng thái bước, chậm, lỗi, thu gọn/mở, reduced motion), `useAiReview` (cập nhật bước theo lần hỏi, hỏi 1,5 giây).

Kiểm tay: chạy thật trên 5173 với API thật, mở DEMO-02, quan sát danh sách bước thật.

## 8. Việc để người xây tự quyết

Từ ngữ chi tiết từng bước, bố cục chính xác, tên lớp CSS, cách nội suy đồng hồ, trong khuôn khổ trên.

## 9. Liên hệ plan 1.9

Khi thêm công cụ agentic: mỗi lần gọi công cụ là một bước nối thêm qua `ghi_buoc` (ví dụ `cong_cu_tra_cuu_n`); không phải đổi hợp đồng hay giao diện.
