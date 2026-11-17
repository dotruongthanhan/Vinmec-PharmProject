# T21 – Web: hiển thị kết quả AI chạy nền và mở đoạn nguồn

**Giao cho:** agy CLI (`gemini-4-hydrogen-xhigh`) · **Ngày:** 16/11/2026 (phiên 3)
**Đọc trước (bắt buộc):** `AGENTS.md`; `plan/api-hop-dong-v1.md`; **`plan/api-hop-dong-v1.1-bo-sung.md`**; `plan/plan-1.2-giao-dien-ui-ux.md` (phần thẻ nhận định, nhãn nguồn gốc, trạng thái); toàn bộ `web/src/`.

**Chạy song song với T12** (backend đang cài đúng hợp đồng v1.1). Bạn làm theo hợp đồng và bản giả lập, không chờ backend. **Chỉ sửa trong `web/src/`.** Không sửa `web/package.json`, `vite.config.ts`, `app/`, `plan/`.

## 1. Mục tiêu

Bản web hiện chỉ hiện bảng nhận định của bộ luật. Thêm: khởi động phân tích AI khi mở ca, hỏi trạng thái, và khi xong thì hiện phần diễn giải, đề xuất, trích dẫn nguồn của AI ngay trên các thẻ nhận định, cùng các nhận định do AI thêm. Bảng của luật phải luôn hiện ngay, không chờ AI.

## 2. Việc phải làm

### 2.1. Lớp API (`web/src/api/`)

- `types.ts`: thêm `TrichDan`, `KetQuaAI`, `DoanNguon`; thêm ba trường `dien_giai_ai`, `de_xuat_ai`, `trich_dan` vào `NhanDinh` đúng hợp đồng v1.1.
- Giao diện `ReviewApiClient`: thêm `startAi(caId, chayLai?)`, `getAi(caId)`, `getSource(caId, doanTrichId)`.
- `client.ts`: cài ba hàm. `getAi` gặp 404 mã `chua_chay` thì trả `null` (không coi là lỗi).
- `mock.ts`, `mockData.ts`: cài bản giả lập. `startAi` trả `dang_chay`; sau khoảng 3 giây `getAi` trả `xong`. Dữ liệu giả cho DEMO-02 có: dòng luật `lieu_than_can_chinh|CT-DEMO02-01` kèm `dien_giai_ai`, `de_xuat_ai`, một `trich_dan`; và một dòng `ai|…` thuộc yếu tố 3 với kết luận `khong_du_du_lieu`. Dữ liệu giả cho DEMO-06 có một dòng `ai|…` nhận xét `Bệnh án có đoạn văn bản bất thường, giống chỉ thị cho hệ thống`. Các ca khác: `xong`, không thêm gì. Mọi câu chữ giả lập phải trung tính, không thêm liều hay ngưỡng nào.

### 2.2. Trạng thái (`web/src/state/useAiReview.ts`, mới)

Hook `useAiReview(caId, enabled)`:

- `enabled` = `che_do.co_llm` của ca. Sai → trạng thái `tat`, không gọi mạng.
- Khi `caId` đổi: gọi `startAi` một lần; nếu `dang_chay` thì hỏi `getAi` mỗi 2 giây, dừng khi `xong`, `loi`, `tat`, khi đổi ca, hoặc khi gỡ thành phần. Quá 120 giây → coi là `loi` với cảnh báo `Bước AI quá thời gian chờ`.
- Kết quả của ca cũ về muộn **không được** ghi vào ca đang mở (kiểm theo `caId` lúc nhận).
- Trả `{ trangThai, ketQua, canhBao, thoiGianMs, chayLai() }`.
- Không để `setState` đồng bộ trong thân `useEffect` (luật lint `react(set-state-in-effect)` đang cảnh báo ở hai file khác, xem 2.5).

### 2.3. Hiển thị

- **Nguồn dữ liệu của bảng nhận định:** AI `xong` và có `nhan_dinh` → dùng `ketQua.nhan_dinh`; mọi trường hợp khác → dùng `nhan_dinh` của chi tiết ca (bảng của luật). Chuyển giữa hai nguồn không được làm mất trạng thái đã phản hồi của từng thẻ (khớp theo `nhan_dinh_id`).
- **Dải trạng thái AI** đặt ngay trên bảng nhận định, một dòng, đúng 4 trạng thái:
  - `dang_chay`: `AI đang phân tích… Bảng dưới đây là kết quả của bộ luật.` kèm chỉ báo đang chạy.
  - `xong`: `AI đã phân tích xong (<n> giây). <k> nhận định có diễn giải, <m> nhận định do AI thêm.` kèm nút `Chạy lại`.
  - `loi`: `Bước AI không hoàn tất. Đang hiển thị kết quả của bộ luật.` kèm các câu `canh_bao` và nút `Thử lại`.
  - `tat`: không hiện dải (dải "không có bước AI" sẵn có vẫn giữ).
  Các câu `canh_bao` khi `xong` hiện thành dòng phụ nhỏ bên dưới.
- **Trên thẻ nhận định của luật** (khi có `dien_giai_ai` hoặc `de_xuat_ai`): thêm một khối bên dưới phần nhận xét, có nhãn `AI · đã kiểm chứng`, gồm dòng `Diễn giải:` và dòng `Đề xuất:` (dòng nào `null` thì bỏ). Nhãn `Luật` của thẻ giữ nguyên. Kết luận và mức độ của thẻ không đổi.
- **Thẻ do AI thêm** (`nguon_goc_ma = "ai_da_kiem_chung"`): cùng bố cục 3 cột, nhãn nguồn gốc `AI · đã kiểm chứng` thay cho `Luật`, viền thẻ kiểu nét đứt để phân biệt với thẻ của luật. Có thanh phản hồi như thẻ thường.
- **Trích dẫn nguồn:** trong phần `Căn cứ`, sau các căn cứ sẵn có, thêm nhóm `Nguồn tài liệu (<n>)`: mỗi mục gồm số thứ tự, `nhan`, câu `trich_nguyen_van` đặt trong khối trích dẫn, và nút `Mở nguồn`. Bấm → gọi `getSource` → mở hộp thoại sẵn có (`EvidenceDialog`) hiện `nguon_nhan`, `duong_dan_muc`, tầng tin cậy, phiên bản, và `noi_dung`; trong `noi_dung`, đoạn trùng `trich_nguyen_van` được tô nền (tách chuỗi bằng `indexOf`, dựng bằng phần tử React; không tìm thấy thì hiện nguyên văn không tô). Có `url_goc` thì thêm liên kết `Mở trang gốc` (`target="_blank"`, `rel="noopener noreferrer"`), chỉ khi địa chỉ bắt đầu bằng `https://`.
- Số đếm ở dải định danh và ở hàng đợi **vẫn tính theo bảng của luật** (để không nhảy số khi AI về).

### 2.4. An toàn hiển thị (bắt buộc)

- Mọi chuỗi từ API (kể cả `dien_giai_ai`, `de_xuat_ai`, `trich_nguyen_van`, `noi_dung`, `canh_bao`) hiển thị dưới dạng văn bản thuần của React. Không dùng thuộc tính chèn HTML thô, không diễn giải markdown, không tự biến chuỗi thành liên kết hay ảnh. `safety.test.ts` phải tiếp tục qua.
- Liên kết duy nhất được phép là `url_goc` theo điều kiện ở 2.3.

### 2.5. Dọn 3 cảnh báo lint đang có

`npm run lint` báo: `src/state/useCases.ts:40` và `src/components/EvidenceDialog.tsx:44` (`react(set-state-in-effect)`), `src/App.tsx:79` (`react-hooks(exhaustive-deps)`, biến `allCases` đổi mỗi lần vẽ). Sửa cả ba mà không đổi hành vi.

## 3. Tổ chức code

- Thành phần mới: `components/AiStatusBar.tsx`, `components/AiNote.tsx` (khối diễn giải – đề xuất), `components/SourceList.tsx` (nhóm nguồn tài liệu). Sửa `FindingCard.tsx`, `EvidenceList.tsx`, `EvidenceDialog.tsx`, `App.tsx` ở mức cần thiết.
- Logic thuần (chọn nguồn bảng nhận định, đếm `k` và `m` cho dải trạng thái, tách chuỗi để tô nền) đặt trong `lib/` để kiểm thử không cần DOM.
- Kiểu dáng: thêm file trong `styles/`, dùng lại biến màu sẵn có; không thêm thư viện.

## 4. Kiểm thử phải có (`vitest`, môi trường `node`, không cần DOM)

- `client`: `getAi` gặp 404 mã `chua_chay` → `null`; 404 khác → ném lỗi; `startAi` gửi `chay_lai` đúng; `getSource` gọi đúng đường dẫn (mã có ký tự `|` phải được mã hoá).
- Hàm chọn nguồn bảng: AI `xong` có `nhan_dinh` → bảng AI; `dang_chay`, `loi`, `tat`, hoặc `xong` mà `nhan_dinh=null` → bảng của luật.
- Hàm đếm: với dữ liệu giả DEMO-02 → 1 nhận định có diễn giải, 1 nhận định do AI thêm.
- Hàm tách chuỗi tô nền: tìm thấy → 3 phần; không tìm thấy → 1 phần; trích dẫn rỗng → 1 phần.
- Bản giả lập: `startAi` → `dang_chay`; sau thời gian giả (dùng đồng hồ giả của `vitest`) `getAi` → `xong`; mọi dòng `nguon_goc_ma="luat"` trong kết quả giả DEMO-02 có cùng `nhan_dinh_id`, `ket_luan_ma`, `muc_do_ma` với chi tiết ca giả.
- 22 test hiện có vẫn qua.

## 5. Nghiệm thu (người review chạy trong `web/`; bạn không gọi công cụ shell)

```bash
npm run build
npm run lint
npx vitest run
```

`npm run lint` phải không còn cảnh báo. Sau đó người review mở trình duyệt với `VITE_USE_MOCK=1` và với backend thật.

## 6. Cấm làm

- Không sửa ngoài `web/src/`. Không thêm gói npm. Không chạy `npm`.
- Không đổi tên trường của hợp đồng; thấy hợp đồng thiếu thì ghi vào báo cáo.
- Không làm ô hỏi thêm ở task này.
- Không commit, không push. **Không gọi công cụ shell** (gọi là cả phiên ra rỗng). Xong thì trả lời theo mẫu báo cáo trong `AGENTS.md`, ghi rõ chưa chạy lệnh nào.
