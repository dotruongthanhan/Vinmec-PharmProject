# T20 – Bản web chính (React + TypeScript)

**Giao cho:** agy CLI (`gemini-4-hydrogen-xhigh`) · **Ngày:** 16/11/2026
**Đọc trước (bắt buộc):** `AGENTS.md`; `plan/plan-1.2-giao-dien-ui-ux.md` (**bản thiết kế**, đọc toàn bộ); `plan/api-hop-dong-v1.md` (**hợp đồng dữ liệu**, làm đúng từng tên trường); `web/package.json`, `web/vite.config.ts`, `web/tsconfig*.json`, `web/src/` (khung Vite đã dựng sẵn). **Tham khảo, không sửa:** `app/ui/components/*.py` và `app/ui/streamlit_app.py` (bản Streamlit đang chạy đúng, dùng để xem từng phần hiển thị gì và câu chữ ra sao).

**Không gọi công cụ shell / terminal / command dưới bất kỳ hình thức nào** (kể cả `ls`, `cat`, `npm`, `node`, `git`): phiên này không có quyền đó và gọi là mất toàn bộ kết quả. Chỉ dùng công cụ đọc file, liệt kê thư mục, ghi và sửa file. Người review sẽ tự chạy `npm run build`.

**Nhiều task khác đang chạy song song.** Bạn chỉ tạo và sửa file trong `web/` theo mục 2. Không đụng bất cứ gì ngoài `web/`.

## 1. Mục tiêu

Bản web thật cho dược sĩ, thay giao diện Streamlit làm giao diện chính. Dựng toàn bộ màn hình ở mục 3 của plan 1.2 (hàng đợi, dải định danh, tóm tắt, bảng nhận định, phản hồi, xem căn cứ, khung hỏi thêm, chi tiết) trên dữ liệu lấy từ API theo hợp đồng. Backend đang được viết song song, nên phải có **dữ liệu mẫu** để web chạy được một mình.

## 2. Phạm vi và ràng buộc kỹ thuật

- Khung đã có: Vite 8, React 19, TypeScript 7, vitest 5, oxlint. **Không sửa `package.json`, `package-lock.json`, `tsconfig*.json`; không thêm thư viện nào** (không thư viện giao diện, không router, không thư viện quản lý trạng thái, không thư viện gọi mạng, không Tailwind). Dùng React thuần, `fetch`, CSS thuần.
- TypeScript chặt: không `any`, không `// @ts-ignore`, không biến khai báo mà không dùng (khung bật `noUnusedLocals`, `noUnusedParameters`, `verbatimModuleSyntax`: kiểu phải import bằng `import type`). Code phải qua `tsc -b` ngay lần đầu vì bạn không tự chạy được: viết cẩn thận, kiểu tường minh ở mọi biên.
- Xoá nội dung mẫu của Vite trong `web/src/` (`App.css`, ảnh mẫu trong `assets/`, nội dung mẫu của `App.tsx`, `index.css`) và thay bằng code của bạn. `web/index.html`: `lang="vi"`, tiêu đề `Hỗ trợ thẩm định y lệnh`.
- `web/vite.config.ts`: thêm `server.proxy` chuyển `/api` sang `http://localhost:8000`, và cấu hình `test` của vitest (`environment: "node"`); dùng `defineConfig` từ `vitest/config`.

Cấu trúc:

```text
web/src/
├─ main.tsx  App.tsx
├─ api/types.ts          # chép đúng mọi type và interface từ hợp đồng
├─ api/client.ts         # ApiClient: getCases, getCase, getRecord, sendFeedback, ask; lỗi → ApiError(ma, thong_bao, status)
├─ api/mock.ts           # MockClient cùng giao diện với ApiClient, dữ liệu mẫu ở api/mockData.ts
├─ api/index.ts          # chọn client: import.meta.env.VITE_USE_MOCK === "1" thì MockClient, ngược lại ApiClient
├─ state/                # hook: useCases, useCaseDetail, useChat (hội thoại tách theo ca), useFeedback
├─ lib/                  # hàm thuần có test: sắp xếp và lọc hàng đợi, chọn kiểu hiển thị theo mã, tìm ChiSo theo cong_thuc
├─ components/           # Queue, CaseHeader, Summary, MetricCard, FindingCard, EvidenceList, EvidenceDialog,
│                        # FeedbackBar, PassedList, DetailTabs, ChatPanel, StatusBanner, StateViews (đang tải / lỗi / rỗng)
└─ styles/               # tokens.css (biến màu, cỡ chữ, khoảng cách), base.css, và CSS theo thành phần
```

## 3. Yêu cầu màn hình

Làm đúng plan 1.2 mục 2 (nguyên tắc P1–P9), mục 3 (bố cục và từng vùng), mục 4 (các trạng thái), mục 5 (ngôn ngữ). Các điểm bắt buộc:

1. **Bố cục ba vùng:** hàng đợi bên trái (rộng cố định khoảng 280 px, thu gọn được), vùng chính ở giữa, khung hỏi thêm bên phải (khoảng 360 px, thu gọn được). **Dải định danh ca dính ở trên** khi cuộn vùng chính (`position: sticky`). Ở màn hình 1366 × 768 phải thấy trạng thái dị ứng, CrCl và ba con số đếm mà không cuộn. Dưới 1100 px khung hỏi thêm chuyển thành ngăn trượt mở bằng nút.
2. **Hàng đợi:** thứ tự lấy nguyên từ API; bộ lọc `Tất cả · Cần xem · Đã phản hồi hết`; mỗi dòng có `ca_id`, khoa, mô tả, `huy_hieu`; ca đang chọn nổi bật; chọn ca bằng chuột và bằng phím mũi tên lên / xuống khi hàng đợi đang được chọn.
3. **Dải định danh:** `gioi_tuoi`, `can_nang`, `khoa_loai`, `crcl` (kèm `▼` khi `crcl_bat_thuong`), dị ứng theo `di_ung_ma` với **ba kiểu khác hẳn nhau** (nền đỏ có biểu tượng; chữ thường; nền vàng chữ in hoa), ba con số đếm.
4. **Tóm tắt:** ba cột như mục 3.3; bốn ô chỉ số, bấm vào mở đầu vào, ghi chú và trích dẫn; chỉ số thiếu hiện `—` kèm `Thiếu: …`.
5. **Bảng nhận định:** dòng `Chưa có luật kiểm tra cho các yếu tố: …` ngay dưới tiêu đề, luôn hiện khi `yeu_to_chua_kiem` khác rỗng. Mỗi `NhanDinh` trong `can_chu_y` là một thẻ: nhãn mức độ có **biểu tượng + chữ + màu**, nhãn `nguon_goc_nhan`, ba cột Thuốc · Yếu tố kiểm tra · Nhận xét, dòng `Còn thiếu: …` khi có, danh sách căn cứ (mở sẵn khi `muc_do_ma === "nghiem_trong"`), thanh phản hồi. `nguon_goc_ma === "ai_chua_kiem_chung"` thì viền đứt. Khối `Các mục đạt (n)` đóng sẵn, dạng bảng gọn. Không có mục cần chú ý thì ghi `Không có mục cần chú ý trong phạm vi {so_luat_da_chay} luật đã chạy.`
6. **Căn cứ:** `mo_duoc` và `loai_ma === "du_lieu"` → gọi `getRecord` và hiện `BanGhi` trong hộp thoại; `tinh_toan` có `cong_thuc` → hộp thoại hiện `ChiSo` tương ứng; `tai_lieu` → hiện `mo_ta` và `ghi_chu`. Hộp thoại dùng phần tử `<dialog>`, đóng được bằng phím Esc và nút đóng, trả tiêu điểm về nút đã mở.
7. **Phản hồi:** `Đồng ý` gửi ngay; `Bác bỏ` và `Cần sửa` mở chọn lý do (từ `nhom_ly_do` của ca) và ô ghi chú, chưa chọn lý do thì nút gửi bị khoá. Đang gửi thì khoá nút; lỗi thì báo tại chỗ và giữ nguyên nội dung đã nhập; thành công thì thẻ hiện `Đã phản hồi: {phan_hoi_nhan} lúc {thoi_diem_text}` và nút `Sửa phản hồi`, đồng thời cập nhật `da_phan_hoi_het` của hàng đợi mà **không tải lại cả ca**.
8. **Khung hỏi thêm:** câu gợi ý bấm được khi hội thoại rỗng; ô nhập (Enter gửi, Shift + Enter xuống dòng); trong lúc chờ hiện trạng thái đang xử lý; hiển thị theo `trang_thai` (`chua_san_sang`, `khong_co_nguon`, `ngoai_pham_vi`, `loi` mỗi loại một kiểu); trích dẫn `[n]` bấm mở căn cứ; khối đóng sẵn `Hệ thống đã tra gì` khi `cong_cu_da_goi` khác rỗng; hội thoại tách theo ca; nút xoá hội thoại; dải chú thích cố định `Trả lời tham khảo, có trích dẫn. Không dán dữ liệu người bệnh thật.`
9. **Chi tiết:** bốn thẻ `Y lệnh · Xét nghiệm · Vi sinh · Diễn biến`; dòng xét nghiệm ngoài ngưỡng có mũi tên; kháng sinh `dang_ke` tô nổi; thẻ chuyển được bằng bàn phím (vai trò `tablist` / `tab` / `tabpanel`).
10. **Trạng thái:** đang tải (khung xương, không màn hình trắng), lỗi tải (thông báo + nút thử lại), hàng đợi rỗng, ca lỗi dữ liệu (`loi_nap` hiện ở đầu hàng đợi), các dải `che_do.thong_bao` cố định ở trên cùng cạnh dải `Kết quả tham khảo từ dữ liệu giả lập. Dược sĩ kiểm chứng và quyết định.`
11. **Không có nút duyệt đơn, không có chức năng sửa ca.**

## 4. An toàn hiển thị (bắt buộc)

- Không dùng `dangerouslySetInnerHTML`, `innerHTML`, `eval`, `new Function` ở bất kỳ đâu.
- Mọi chuỗi từ API hiển thị như nút văn bản của React. Không biến văn bản thành liên kết, không diễn giải markdown. Xuống dòng trong văn bản giữ bằng CSS `white-space: pre-wrap`.
- Không lưu dữ liệu ca vào `localStorage` / `sessionStorage` (chỉ được lưu lựa chọn giao diện: ca đang chọn, bộ lọc, cột thu gọn).
- Không gọi địa chỉ nào ngoài `/api`. Không nhúng phông chữ, ảnh, mã từ mạng ngoài (dùng phông hệ thống).

## 5. Thiết kế hình ảnh

Giao diện nghiệp vụ lâm sàng: sáng, mật độ thông tin cao, yên tĩnh. Nền trung tính, một màu nhấn; màu chỉ dùng cho mức độ (đỏ nghiêm trọng, hổ phách cần lưu ý, xám xanh thiếu dữ liệu, tím ngoài HDSD, lục đạt) và luôn đi kèm biểu tượng + chữ. Cỡ chữ nền 14 px, số liệu dùng chữ số đều cột (`font-variant-numeric: tabular-nums`). Tương phản chữ đạt mức AA. Mọi phần tử bấm được có trạng thái tiêu điểm nhìn thấy rõ. Biến màu, khoảng cách, bo góc khai báo một lần ở `styles/tokens.css`.

## 6. Dữ liệu mẫu

`api/mockData.ts` chứa `DanhSachCa` với 6 ca và `ChiTietCa` đầy đủ cho ít nhất 3 ca, kiểu khớp hợp đồng, nội dung chép theo các ca thật trong `data/mock/demo/`:

- DEMO-02: 1 nhận định nghiêm trọng yếu tố 6 (meropenem, CrCl 16,0 mL/phút), 3 căn cứ, creatinin `212,0 ▲ (từ 150,0, sau 3 ngày)`.
- DEMO-03: dị ứng `chua_co_thong_tin`, 1 nhận định `khong_du_du_lieu` có `thong_tin_con_thieu`.
- DEMO-06: dị ứng `co_di_ung`, 1 nhận định nghiêm trọng yếu tố 1.

`MockClient` trả dữ liệu sau một khoảng trễ ngắn, ghi phản hồi trong bộ nhớ, `ask` trả `chua_san_sang`. Chạy `VITE_USE_MOCK=1 npm run dev` thì web chạy được không cần backend.

## 7. Kiểm thử (vitest, chỉ hàm thuần, không cần DOM)

- Lọc hàng đợi theo ba lựa chọn; giữ nguyên thứ tự từ API.
- Chọn kiểu hiển thị theo `muc_do_ma`, `ket_luan_ma`, `di_ung_ma`: mỗi mã ra một lớp CSS và một biểu tượng khác nhau; ba trạng thái dị ứng ra ba kết quả khác nhau.
- Tìm `ChiSo` theo `cong_thuc`; không có thì trả `undefined`.
- `ApiClient` (thay `fetch` bằng hàm giả): 200 trả dữ liệu; 404 với thân `{"loi": {...}}` ném `ApiError` có `ma` và `status`; thân không phải JSON vẫn ném `ApiError` với `ma === "loi_he_thong"`; `sendFeedback` gửi đúng phương thức, đường dẫn và thân.
- Dữ liệu mẫu: mỗi `ChiTietCa` có đúng 4 `chi_so`; mọi `nhan_dinh_id` trong một ca là duy nhất; mọi `DongHangDoi.ca_id` có hoặc không có chi tiết đều được `MockClient.getCase` xử lý (không có thì ném `ApiError` 404).
- Test tĩnh: đọc mọi file `.ts` / `.tsx` trong `src/` (dùng `import.meta.glob` với `query: "?raw"`), không file nào chứa `dangerouslySetInnerHTML`, `innerHTML`, `eval(`, `localStorage.setItem` với dữ liệu ca (cho phép đúng một module `lib/prefs.ts` dùng `localStorage`).

## 8. Nghiệm thu (người review chạy trong `web/`)

```bash
npm run build      # tsc -b && vite build: 0 lỗi
npm run lint       # oxlint: 0 lỗi
npx vitest run     # toàn bộ qua
```

rồi chạy `VITE_USE_MOCK=1 npm run dev` và chạy với backend thật, xem cả 6 ca theo tiêu chí U1–U6 ở mục 8 của plan 1.2.

Viết `web/README.md` ngắn: cách chạy (mock và thật), cấu trúc thư mục, quy tắc an toàn hiển thị.

## 9. Cấm làm

- Không sửa gì ngoài `web/`. Không thêm thư viện. Không gọi mạng ngoài.
- Không giả câu trả lời ở khung hỏi thêm ngoài trạng thái `chua_san_sang`.
- Không đổi tên trường của hợp đồng; thấy hợp đồng thiếu thì làm theo cách hợp lý nhất và **ghi rõ trong báo cáo**.
- Không commit, không push.

Xong thì trả lời theo mẫu báo cáo trong `AGENTS.md`, ghi rõ là chưa chạy lệnh nào.
