# VZ2-fix-1 – Test ví dụ kỹ năng, kháng sinh chưa bắt đầu

Người làm: Codex `gpt-6.1-terra` high. Đọc `plan/briefs/VZ2-lay-du-lieu-ca-dong-thoi-gian.md`, `plan/briefs/VZ2-bao-cao.md`.

## Claude review VZ2 lượt 3 (27/11)

**Đạt:**
- ruff check + format sạch.
- pytest: `tests/agent` 263, `tests/orchestration` 84, `tests/tracing` 26, `tests/api` 218 (2 bỏ qua), `tests/eval` 28: đều qua.
- tsc sạch, oxlint 0 lỗi, vite build OK.
- Claude chạy tool trên DEMO-02:
  - creatinin 150 → 212 µmol/L sau 72 giờ: `creatinin_tang_nhanh` = False (không tăng ≥ 26,5 trong 48 giờ, 212 < 1,5 × 150) – đúng;
  - meropenem 3 × 1 g, tổng 24 giờ trượt 3.000 mg – đúng; không có liều tối đa trong `lieu_toi_da.json` nên null – đúng;
  - `moc_ca` không có nội dung diễn biến, không có mã người bệnh.

**Chưa đạt:**

1. **vitest trượt 1:** `web/src/features/minh-hoa/__tests__/mh1.test.ts:18` mong đúng 3 ví dụ trong `ky_nang_minh_hoa.v1.md`, nay có 5 (đã thêm 2 ví dụ VZ2). Sửa test để kiểm **mọi** ví dụ trong tệp kỹ năng đều qua `kiemDacTa` và có ít nhất 5 ví dụ; không xoá ví dụ.
2. **Kháng sinh kê mới chưa bắt đầu dùng** (DEMO-02: kê 05:50, liều đầu 06:00): bộ `khang_sinh` ra `ngay_thu = null`, `dang_dung = False`, và văn bản cho LLM là "ngày thứ thiếu; thiếu ket_thuc hoặc chưa bắt đầu" – mơ hồ, LLM dễ hiểu là thiếu dữ liệu.
   - Thêm cột logic `chua_bat_dau` (true khi `bat_dau` > mốc tham chiếu).
   - Văn bản tóm tắt nói rõ: "Meropenem 1 g: chưa bắt đầu (liều đầu dự kiến 10/11 06:00, sau thời điểm kê)"; dòng đang dùng: "ngày thứ N"; dòng đã ngưng: "đã ngưng ngày dd/mm". Không dùng chữ "thiếu" khi dữ liệu thực ra có.
   - Test: ba trường hợp trên.

Không đổi gì khác.

## Tệp

Được sửa: `app/agent/tools/lay_du_lieu_ca.py`, `tests/agent/test_tool_lay_du_lieu_ca.py`, `web/src/features/minh-hoa/__tests__/mh1.test.ts`. Báo cáo: ghi tiếp mục "fix-1" vào `plan/briefs/VZ2-bao-cao.md`.

**Cấm:** như brief VZ2. Thêm: **không gọi `load_env_file()`, không đọc `.env`, không kết nối DB** (lượt 3 đã lỡ chạy một lệnh gọi `load_env_file()`).

## Nghiệm thu

```
uv run ruff check app tests && uv run pytest -q -p no:cacheprovider tests/agent/test_tool_lay_du_lieu_ca.py
cd web && npx vitest run src/features/minh-hoa
```
