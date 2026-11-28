# UI3-fix-2 – Cột bị ép khi mở ngăn chi tiết; test cũ của danh sách hồ sơ

Người làm: Codex `gpt-6.1-terra` high. Đọc `plan/briefs/UI3-bo-cuc-co-gian-khi-mo-tro-ly.md`, `UI3-fix-1.md`, `UI3-bao-cao.md`.

## Claude review UI3-fix-1 (27/11, 5173, khung trợ lý mở, 1280×800)

**Đạt:**
- Số tiêu đề hiện bằng số ô hiện ở cả 3 bảng:
  - danh sách hồ sơ: 6/6, dòng phụ "NB-DEMO-02 · 06/11/1951" và khoa "Hô hấp" đã có;
  - bảng y lệnh: 3/3 (Thuốc · Trạng thái · Bắt đầu, kết thúc);
  - bảng xét nghiệm: 5/5.
- Hết chữ `?`. 0 vùng cuộn ngang, 0 chữ vượt mép.

**Chưa đạt:**

1. **Mở một dòng thuốc thì cột bị ép.** Ở chế độ hẹp, khi chưa mở dòng nào, 3 cột chia 220/180/180 px (đúng). Khi mở một dòng, ô ngăn chi tiết `<td colSpan={9}>` làm bảng (`table-layout: fixed`) dựng lại **9 cột**. 6 cột không có ô hiện vẫn được chia chỗ, nên cột "Trạng thái" và "Bắt đầu, kết thúc" chỉ còn **45 px** mỗi cột ("10/11/2026" vỡ thành 3 dòng), và bên phải dòng thuốc bỏ trống khoảng 270 px. Claude đo bằng `getBoundingClientRect` trên HS-042.

   Yêu cầu: dù mở hay đóng dòng, các cột hiện phải chia hết bề rộng bảng, bề rộng không đổi giữa hai trạng thái (sai lệch ≤ 2 px). Cách làm do bạn chọn, ghi trong báo cáo. Gợi ý:
   - đặt bề rộng phần trăm cho các tiêu đề hiện ở từng chế độ, tổng 100%, và tiêu đề ẩn bề rộng 0; hoặc
   - render hai `<td>` ngăn chi tiết với `colSpan` khác nhau, mỗi cái chỉ hiện ở chế độ của nó (9 cho rộng; 4 hoặc 3 cho hẹp); hoặc
   - bỏ `table-layout: fixed` ở chế độ hẹp nếu vẫn giữ được việc chữ xuống dòng.

   Áp dụng cùng nguyên tắc cho chế độ < 640 px (3 cột) và 640–999 px (4 cột).
2. **Test cũ trượt:** `web/src/__tests__/ordersTable.test.ts:132` mong `Chưa ghi nhận` nhưng đọc được cả dòng phụ đang ẩn bằng CSS. **Được phép sửa test này**: truy vấn đúng phần tử của chế độ rộng (hoặc chế độ hẹp), không xoá ý của test.

## Test

- Toàn bộ `npx vitest run` xanh.
- Thêm test markup: ngăn chi tiết ở mỗi chế độ có `colSpan` (hoặc bề rộng cột) khớp số cột hiện của chế độ đó.

## Tệp

Như brief UI3, thêm `web/src/__tests__/ordersTable.test.ts` (chỉ sửa truy vấn ở test trượt). Báo cáo: ghi tiếp vào `plan/briefs/UI3-bao-cao.md` mục "fix-2". Ghi tệp giữ UTF-8 (apply_patch).
**Cấm:** như brief UI3.

## Nghiệm thu

```
cd web && npx tsc -b --noEmit && npx oxlint && npx vitest run && npx vite build
```

Claude đo lại ở 1280, 1440, 1920 khi trợ lý mở: bề rộng từng cột khi mở và khi đóng dòng chênh ≤ 2 px; tổng bề rộng cột hiện bằng bề rộng bảng; chụp ảnh.
