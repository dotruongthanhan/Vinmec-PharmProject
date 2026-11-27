# UI3-fix-1 – Sửa đầu cột lệch, chữ lỗi mã hoá, mất thông tin ở danh sách hồ sơ

Người làm: Codex `gpt-6.1-terra` high. Đọc lại `plan/briefs/UI3-bo-cuc-co-gian-khi-mo-tro-ly.md` (yêu cầu gốc, giữ nguyên) và `plan/briefs/UI3-bao-cao.md`.

## Claude review UI3 (27/11, 5173, API thật, khung trợ lý mở)

**Đạt:** ở 1280×800, 1440×900 và 1920×1080, trên ca HS-042, DEMO-02, HS-011, trong `main` không còn vùng cuộn ngang và không còn chữ vượt mép phải. Ngăn chi tiết thuốc rộng 570/580, 730/740, 1158/1158 px (đúng bằng vùng nhìn). tsc sạch, build OK.

**Chưa đạt (sửa hết trong đợt này):**

1. **Đầu cột không gọn theo thân bảng.** Ở chế độ hẹp, các ô `ui3-lines-wide` / `ui3-labs-wide` bị ẩn nhưng `<th>` tương ứng vẫn hiện.
   - Bảng y lệnh ở 1280: thân còn 3 ô nhưng đầu cột vẫn đủ 9 tiêu đề. Kết hợp `table-layout: fixed`, cột tên thuốc bị ép còn khoảng 40 px: "Warfarin 5 mg" vỡ thành "War / 5 mg", huy hiệu "Chờ duyệt" đè lên tên thuốc, dòng phụ bị xé từng chữ.
   - Bảng xét nghiệm: đầu cột 7, thân 5.

   Yêu cầu: tiêu đề và ô ẩn hoặc hiện **cùng nhau**. Chế độ hẹp có tiêu đề riêng:
   - bảng y lệnh: **Thuốc · Trạng thái · Bắt đầu, kết thúc · Lịch dùng**, và bỏ tiêu đề Lịch dùng khi cột giữa < 640 px;
   - bảng xét nghiệm: **STT · Chỉ số xét nghiệm · Kết quả · Thời gian đo · Đánh giá**.

   Chia lại bề rộng cột cho chế độ hẹp sao cho tên thuốc không bị bẻ giữa chữ. Chỉ dùng `overflow-wrap: anywhere` cho mã dài, không dùng cho chữ thường; chữ thường dùng `break-words`.
2. **Chữ tiếng Việt và ký hiệu mới thêm bị ghi thành `?`** (lỗi mã hoá khi ghi tệp):
   - `OrderLineExpandedPanel.tsx`: `label: 'L?ch d?ng'` → `'Lịch dùng'`;
   - `UnifiedOrderLinesTable.tsx`: `.join(' ? ')` → `' · '` (dấu chấm giữa U+00B7, như chỗ khác trong kho);
   - `LabsTabContent.tsx`: hai chỗ `|| '?'` → dùng đúng ký tự thiếu dữ liệu mà tệp đang dùng ở chỗ khác (`—` hoặc hằng sẵn có). Trên giao diện hiện ra "2,4 ? 2,0 – 3,0".

   Rà **mọi** dòng bạn đã thêm hoặc sửa ở UI3: không còn `?` thay cho chữ có dấu. Ghi tệp bằng công cụ sửa tệp giữ UTF-8 (apply_patch), **không** ghi bằng PowerShell `Set-Content` / `Out-File` hay chuyển hướng `>`.
3. **Danh sách "Hồ sơ cần duyệt" mất thông tin khi hẹp.** Cột Mã BN, Ngày sinh, Khoa đã ẩn nhưng **không** có dòng phụ thay thế (test `ui3Responsive.test.tsx` › "giữ mã, ngày sinh và khoa ở dòng phụ" đang trượt). Theo brief gốc mục 4:
   - dưới "Người bệnh": mã BN (nút mở hồ sơ như cũ) và ngày sinh;
   - dưới "Chẩn đoán chính": khoa.
4. Chạy lại toàn bộ vitest sau khi sửa (lần này được chạy lại đến khi xanh).

## Test bổ sung

- Với mỗi bảng (y lệnh, xét nghiệm, danh sách hồ sơ): mọi `<th>` và `<td>` cùng vị trí có **cùng lớp ẩn/hiện** theo chế độ. Test đếm: số `th` có lớp chế độ hẹp bằng số `td` có lớp chế độ hẹp trên một dòng; tương tự cho chế độ rộng.
- Test đọc nội dung các tệp đã sửa ở UI3, khẳng định không có chuỗi `'?'` đứng một mình, `' ? '`, hay chữ Latin kề `?` kề chữ Latin (mẫu `[A-Za-z]\?[a-z]`) trong chuỗi hiển thị.
- Test "giữ mã, ngày sinh và khoa ở dòng phụ" phải xanh.

## Tệp

Được sửa: như brief UI3 (cùng danh sách tệp). Báo cáo: ghi tiếp vào `plan/briefs/UI3-bao-cao.md` mục "fix-1".
**Cấm:** như brief UI3. Thêm: không đổi các ngưỡng 1.000 / 760 / 640 / 900 / 480 px đã chốt.

## Nghiệm thu

```
cd web && npx tsc -b --noEmit && npx oxlint && npx vitest run && npx vite build
```

Claude đo lại trên trình duyệt ở 3 cỡ màn như UI3, thêm:
- số tiêu đề hiện bằng số ô hiện trên mỗi dòng;
- ảnh chụp bảng y lệnh ở 1280 không có chữ đè nhau.
