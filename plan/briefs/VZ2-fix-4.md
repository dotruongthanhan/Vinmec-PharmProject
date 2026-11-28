# VZ2-fix-4 – Đường mốc thời gian vẽ sai vị trí, trục y thiếu đơn vị, định dạng ruff

Người làm: Codex `gpt-6.1-terra` high. Đọc `plan/briefs/VZ2-fix-3.md`, mục "fix-3" trong `plan/briefs/VZ2-bao-cao.md`.

## Claude thử lại trên web thật (28/11, 5173 + API e2e DB + Gemini Flash Lite, 1440×900)

**Đạt so với fix-3:**
- tiêu đề cột tiếng Việt;
- cột logic hiện "Có"/"Không";
- thời gian trong bảng `dd/MM/yyyy HH:mm`;
- nhãn trục x hết đè (`06/11 10:00`, `07/11 05:30`, `10/11 05:30`);
- chú giải có tên ("Giá trị", "Vào viện", "creatinin", "Phiếu điều trị", "Meropenem 1 g").
- pytest agent 271, api + orchestration 302 (2 bỏ qua), vitest 428/428, tsc, build đạt.

**Chưa đạt:**

1. **Mọi đường mốc dọc (`quy_tac` theo thời gian) vẽ ở cùng một chỗ, mép trái trục.** DEMO-02, hình "Diễn tiến creatinin" mở rộng: Claude đọc SVG thấy 5 `<line stroke-dasharray>` đều `x1 = x2 = 72` (đúng toạ độ của `06/11 10:00`, điểm đầu miền). 5 nhãn mốc đều `x = 106`, chồng lên nhau thành một khối chữ không đọc được. Mốc thật nằm ở 06/11 10:00, 07/11 05:30, 10/11 05:30, 10/11 05:40, 10/11 05:50.
   - Sửa `dungMoHinh.ts`/`VeSvg.tsx`: giá trị mốc kiểu `thoi_gian` (chuỗi ISO) phải đổi sang toạ độ bằng **cùng thang thời gian** với trục x, không ép về số rồi kẹp về đầu miền.
   - Mốc ngoài miền dữ liệu của lớp chính: mở rộng miền để chứa mốc (có lề), hoặc bỏ mốc và ghi trong chú giải; chọn một, ghi trong báo cáo.
   - Nhãn mốc gần nhau (< 40 px) không được chồng. Chỉ hiện nhãn đầy đủ khi di chuột/focus; trên hình hiện số thứ tự ngắn (①②…) khớp với chú giải, hoặc xếp so le theo chiều dọc.
   - Test vitest với đúng dữ liệu DEMO-02 (2 điểm creatinin + 5 mốc): 5 đường có 5 toạ độ x khác nhau, đúng thứ tự thời gian, nằm trong vùng vẽ; nhãn không chồng (hộp bao không giao nhau).
2. **Trục y chưa có đơn vị:** SVG không có chữ `umol/L`/`µmol/L`. Thêm tiêu đề trục y từ `nhan` + `don_vi` của cột y (ví dụ "Giá trị (umol/L)"), và test.
3. **Định dạng ruff:** `uv run ruff format --check app tests/agent` báo 3 tệp cần định dạng lại (trong đó `app/agent/tools/lay_du_lieu_ca.py`, khối `_LABELS`). Chạy `uv run ruff format` cho đúng các tệp đã sửa ở VZ2.

## Tệp

`web/src/features/minh-hoa/**`, các tệp Python của VZ2 cần định dạng lại. Báo cáo: mục "fix-4" trong `plan/briefs/VZ2-bao-cao.md`.
**Cấm:** như brief VZ2. Không đọc `.env`, không gọi `load_env_file()`, không mạng.

## Nghiệm thu

```
uv run ruff check app tests && uv run ruff format --check app tests/agent
cd web && npx tsc -b --noEmit && npx oxlint && npx vitest run && npx vite build
```
Claude mở lại hình DEMO-02 trên 5173: 5 mốc ở 5 vị trí, nhãn đọc được, trục y có đơn vị.
