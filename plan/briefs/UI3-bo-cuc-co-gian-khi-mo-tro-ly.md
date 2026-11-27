# UI3 – Bố cục co giãn: mở khung trợ lý thì chữ xuống dòng, không bị khuất

Người làm: Codex `gpt-6.1-terra` high (chạy được `npx tsc`, `oxlint`, `vitest`, `vite build`; **không cài gói, không gọi mạng**).
Đọc trước: `AGENTS.md`; `plan/plan-1.4-he-thong-thiet-ke.md` (mục "Bố cục co giãn theo cột giữa", Claude vừa thêm); `web/src/styles/globals.css` (`.workspace-center` đã là `container-type: inline-size`, đã có vài `@container`); `web/src/components/ui/data-table.tsx`; các tệp trong phạm vi bên dưới.

## Vấn đề (Claude đo 27/11 trên 5173, API thật, khung trợ lý mở, rộng 400 px)

Cột giữa (`.workspace-center`) chỉ còn khoảng **632 px ở màn 1280×800** và **792 px ở 1440×900**. Ba bảng rộng hơn cột nên phải cuộn ngang, chữ ở bên phải bị khuất:

| Chỗ | Tệp | Rộng nội dung / khung nhìn (1280) |
| :--- | :--- | :--- |
| Danh sách "Hồ sơ cần duyệt" (9 cột) | `features/orders/OrdersTable.tsx` + `.orders-table` trong `globals.css` | 930 / 572 |
| Bảng "Chi tiết y lệnh" (9 cột) **và ngăn chi tiết thuốc** (`<td colSpan={9}>`) | `features/order-detail/UnifiedOrderLinesTable.tsx`, `OrderLineExpandedPanel.tsx` | 1.054–1.198 / 580 |
| "Bảng xét nghiệm" (7 cột) | `features/order-detail/LabsTabContent.tsx` | 693–744 / 590 |

Lỗi nặng nhất: ngăn chi tiết thuốc nằm trong ô `colSpan` nên **rộng theo bảng** (1.198 px). Phần "Khoa kê", "Loại y lệnh", nửa phải của diễn giải AI và căn cứ đều khuất, dược sĩ phải kéo ngang mới đọc được.

Không tràn: các tab Hồ sơ bệnh án, Vi sinh, Diễn biến, Thẩm định; trang Tra cứu thuốc, Tra tương tác, Tính toán.

## Nguyên tắc (chủ kho chốt 27/11)

Cột giữa **co giãn theo chỗ còn lại**: khung hẹp thì chữ xuống dòng nhiều hơn và bảng gọn cột lại, **không** đẩy chữ ra ngoài vùng nhìn. Cuộn ngang chỉ là đường lùi khi cột giữa hẹp hơn 480 px.

- Dùng **container query theo cột giữa** (`@container` của Tailwind v4 hoặc CSS trong `globals.css`), **không** dùng media query theo bề rộng màn hình, vì bật hay tắt khung trợ lý không đổi bề rộng màn hình.
- Ô dữ liệu cho phép xuống dòng (`break-words`, bỏ `whitespace-nowrap`). Chỉ giữ một dòng cho mã ngắn (mã y lệnh, mã BN), ngày giờ, huy hiệu trạng thái.
- Không cắt chữ bằng `truncate` hay `…` với nội dung lâm sàng (tên thuốc, liều, chẩn đoán, diễn giải, căn cứ).
- Không giấu thông tin: cột nào bị gộp hoặc ẩn khi hẹp thì giá trị của nó phải hiện ở chỗ khác ngay trên dòng (dòng phụ) hoặc trong ngăn chi tiết.

## Yêu cầu

1. **Bảng "Chi tiết y lệnh"**:
   - Cột giữa **≥ 1.000 px**: giữ nguyên 9 cột như hiện tại.
   - Cột giữa **< 1.000 px**: gọn còn 4 cột:
     - **Thuốc**: tên thuốc đậm, dòng phụ "Liều · Tần suất · Đường dùng", mã y lệnh chữ nhỏ;
     - **Trạng thái**: huy hiệu, dòng phụ là ngày kê;
     - **Bắt đầu, kết thúc**: xuống dòng được;
     - **Lịch dùng**: tối đa 2 dòng, còn lại xem trong ngăn chi tiết.
   - Cột giữa **< 640 px**: bỏ thêm cột Lịch dùng; lịch dùng đầy đủ nằm trong ngăn chi tiết.
   - Tô nền theo mức cảnh báo, bấm mở 1 dòng/lúc, `aria-expanded`, phím Enter/Space: giữ nguyên.
2. **Ngăn chi tiết thuốc** (`OrderLineExpandedPanel`):
   - Luôn rộng **bằng vùng nhìn của bảng**, không rộng theo bảng. Ở chế độ 9 cột nếu bảng còn cuộn ngang thì dùng `position: sticky; left: 0` với chiều rộng bằng khung cuộn, hoặc cách khác tương đương; ghi trong báo cáo đã chọn cách nào.
   - Lưới thông tin (Thuốc dùng, Trạng thái, Khoa kê, Luồng, Loại y lệnh, Người kê…): 2 cặp nhãn–giá trị mỗi hàng khi rộng, 1 cặp khi cột giữa < 640 px.
   - Thẻ nhận định, diễn giải AI, căn cứ: chữ xuống dòng trong khung.
3. **Bảng xét nghiệm**: cột giữa < 760 px thì gộp "Đơn vị" vào "Kết quả" (`2,4 mmol/L`), đưa "Khoảng tham chiếu" thành dòng phụ dưới kết quả, cột "Thời gian đo" xuống dòng. Hành vi bấm dòng để mở đồ thị và in đậm dòng chọn giữ nguyên. Đồ thị rộng theo cột giữa.
4. **Danh sách "Hồ sơ cần duyệt"**: cột giữa < 900 px thì
   - "Mã BN" và "Ngày sinh" thành dòng phụ dưới "Người bệnh";
   - "Thời điểm kê" xuống dòng;
   - "Khoa" thành dòng phụ dưới "Chẩn đoán chính";
   - "Ưu tiên", "Trạng thái", "Cảnh báo AI" giữ cột riêng.

   Sắp xếp theo cột, bấm dòng mở ca, phím tắt: giữ nguyên. Cột nào ẩn khi hẹp thì vẫn sắp xếp được ở chế độ rộng; ở chế độ hẹp được phép bỏ nút sắp xếp của cột đã gộp.
5. **Kiểm nhanh các bảng còn lại** dùng `DataTable` trong `features/order-detail/` và `features/findings/` (`DetailSections.tsx`, `PassedList.tsx`, `EvidenceDialog.tsx`): nếu ô nào có `whitespace-nowrap` với nội dung dài thì cho xuống dòng. **Không** đổi bố cục các bảng này.
6. Không đổi màu, thang chữ hay token của plan 1.4. Không thêm gói.

## Test

- Vitest: render `UnifiedOrderLinesTable`, `LabsTabContent`, `OrdersTable` với dữ liệu mẫu có sẵn. Khẳng định:
  - markup có đủ phần tử cho cả chế độ rộng và hẹp, ẩn hiện bằng lớp container query (jsdom không tính container query, nên test lớp và nội dung, không test bề rộng);
  - giá trị của mọi cột bị gộp đều có mặt trong dòng phụ: liều, tần suất, đường dùng, ngày kê, đơn vị, khoảng tham chiếu, mã BN, ngày sinh, khoa;
  - không ô nội dung lâm sàng nào có lớp `truncate`.
- Test cũ giữ xanh: `npx vitest run`.

## Tệp

Được sửa: `web/src/features/orders/OrdersTable.tsx`, `web/src/features/order-detail/{UnifiedOrderLinesTable,OrderLineExpandedPanel,LabsTabContent,DetailSections}.tsx`, `web/src/features/findings/{PassedList,EvidenceDialog,FindingCard}.tsx` (chỉ lớp xuống dòng), `web/src/styles/globals.css` (chỉ phần `.orders-table` và thêm quy tắc `@container`), `web/src/components/ui/data-table.tsx` (chỉ khi cần thêm tuỳ chọn, không đổi mặc định cho bảng khác), test mới trong `web/src/__tests__/`. Báo cáo: `plan/briefs/UI3-bao-cao.md`.

**Cấm:** sửa `app/**`, `config/**`, `db/**`, `web/src/api/**`, `web/src/features/assistant/**`, `web/src/features/minh-hoa/**`, `web/src/components/ui/ClinicalMarkdown.tsx`, `plan/plan-*`; thêm gói; gọi mạng; commit; dùng `innerHTML` hay `dangerouslySetInnerHTML`.

## Nghiệm thu

Codex chạy:
```
cd web && npx tsc -b --noEmit && npx oxlint && npx vitest run && npx vite build
```

Claude đo trên trình duyệt (5173, API thật, khung trợ lý mở), ở 1280×800, 1440×900, 1920×1080, ca HS-042, DEMO-02, HS-011:
- trong `main` không còn phần tử nào có `scrollWidth > clientWidth + 4` ở danh sách hồ sơ, bảng y lệnh (cả khi mở ngăn chi tiết) và bảng xét nghiệm;
- không có nút chữ nào có cạnh phải vượt mép phải của `main`;
- tắt khung trợ lý ở 1920×1080 thì bảng y lệnh hiện lại đủ 9 cột;
- chụp ảnh từng chỗ để chủ kho xem.
