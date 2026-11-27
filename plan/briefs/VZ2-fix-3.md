# VZ2-fix-3 – Lỗi thấy khi thử trên giao diện thật

Người làm: Codex `gpt-6.1-terra` high. Đọc `plan/briefs/VZ2-lay-du-lieu-ca-dong-thoi-gian.md`, `VZ2-bao-cao.md`, `plan/api-hop-dong-v1.10-minh-hoa.md`.

## Claude thử trên web thật (27/11 đêm, 5173 + API 8000 `CDSS_PROFILE=e2e`, DB RDS, `gemini-3.5-flash-lite`, 1440×900)

**Đạt:**
- DEMO-02 "Creatinin diễn tiến thế nào, vẽ biểu đồ": hình "Diễn tiến creatinin" hiện trong khung chat; mở rộng toàn màn được; "Bảng 1/Bảng 2" khớp số (150, 212 µmol/L).
- Tổng liều meropenem: 3.000 mg; 06:00 / 14:00 / 22:00, có trích dẫn.
- Không lỗi console. Mọi `/api/` trả 200.

**Chưa đạt:**

1. **Cột logic hiện sai nghĩa** (`web/src/features/minh-hoa/dungMoHinh.ts:350`, `:358`). Mọi giá trị bool bị dịch thành "Cần chỉnh liều"/"Không cần chỉnh", nên `ngoai_nguong = true` hiện "Cần chỉnh liều" và `creatinin_tang_nhanh = false` hiện "Không cần chỉnh". Sai nghĩa lâm sàng.
   - Mặc định bool → **"Có"/"Không"**.
   - Chỉ cột tên `can_chinh` (thang liều thận VZ1) giữ nhãn liều. Tốt hơn là lấy nhãn từ dữ liệu: thêm khoá tuỳ chọn `nhan_dung`/`nhan_sai` vào `CotDuLieu` (máy chủ + `types.ts`); thiếu thì "Có"/"Không".
   - Rà dòng 1022–1028 (chú giải) theo cùng nguyên tắc.
2. **Tiêu đề cột trong "Xem dạng bảng" là tên kỹ thuật** (`thoi_diem`, `gia_tri`, `nguong_duoi`…). `lay_du_lieu_ca` phải điền `nhan` tiếng Việt cho **mọi** cột (ví dụ "Thời điểm", "Giá trị", "Ngưỡng dưới", "Ngoài ngưỡng", "Creatinin tăng nhanh (KDIGO)"), và web dùng `nhan` khi có. Kiểm cả bộ dữ liệu của `tinh_chi_so`, `tra_thuoc`, `tra_tuong_tac`.
3. **Thời gian trong bảng hiện chuỗi ISO** (`2026-11-07T05:30:00+07:00`). Cột `kieu = thoi_gian` hiện `dd/MM/yyyy HH:mm` giờ Việt Nam. Dữ liệu gốc giữ nguyên.
4. **Trục và chú giải hình đường:**
   - nhãn trục x ở hai đầu bị đè/cắt ("10:00 06-11" đè "05:30 07-11"; "05:30 10-" bị cắt mép phải): chừa lề, bỏ nhãn trùng khi quá gần, định dạng thống nhất `dd/MM HH:mm`;
   - chú giải "Chuỗi" vô nghĩa: lấy `nhan` cột y hoặc `tieu_de` lớp;
   - trục y không có đơn vị: lấy `don_vi` của cột y;
   - đường dọc nét đứt (mốc) không có nhãn: hiện nhãn ngắn của mốc (cột `nhan` của `moc_ca`) khi di chuột, và trong chú giải.
5. **Câu trả lời nhắc tới hình nhưng không có hình.** DEMO-04 "Kháng sinh ngày thứ mấy… Vẽ dòng thời gian kháng sinh và vi sinh". Các bước: `lay_du_lieu_ca` rồi lập kế hoạch rồi kiểm chứng, **không gọi `ve_bieu_do`**. Vậy mà câu trả lời viết "Mời dược sĩ xem hình bên dưới". Sửa hai lớp:
   - **Máy chủ:** sau kiểm chứng, nếu `minh_hoa == []` mà câu trả lời có cụm nhắc hình ("xem hình", "hình bên dưới", "biểu đồ dưới", "minh hoạ dưới"…) thì bỏ **câu** đó, như cách đang lọc cụm cấm (không gọi lại LLM). Nếu người dùng đã xin vẽ, thêm một dòng cố định "Chưa dựng được hình cho câu hỏi này." Có test.
   - **Kỹ năng prompt:** nhắc rõ "chỉ nhắc tới hình khi đã gọi `ve_bieu_do` thành công trong lượt"; người dùng yêu cầu vẽ và có `bo_du_lieu` phù hợp thì phải gọi `ve_bieu_do`.

## Test

- vitest: bool → "Có"/"Không"; cột có `nhan_dung`/`nhan_sai` dùng nhãn riêng; tiêu đề bảng dùng `nhan`; thời gian hiện `dd/MM/yyyy HH:mm`; chú giải dùng nhãn cột y; nhãn trục x không chồng nhau ở dữ liệu DEMO-02 (2 điểm + mốc vào viện).
- pytest: mọi cột của `lay_du_lieu_ca` có `nhan`; lọc câu nhắc hình khi `minh_hoa` rỗng; giữ nguyên khi có hình.

## Tệp

Được sửa: `web/src/features/minh-hoa/**`, `web/src/api/types.ts` (chỉ `CotDuLieu`), `app/agent/minh_hoa/models.py`, `app/agent/minh_hoa/kiem.py` (nếu cần cho khoá mới), `app/agent/tools/**`, `app/agent/nodes.py` (lọc câu nhắc hình), `config/prompts/ky_nang_minh_hoa.v1.md`, `tests/agent/**`, `plan/api-hop-dong-v1.10-minh-hoa.md` (chỉ thêm `nhan_dung`/`nhan_sai`). Báo cáo: mục "fix-3" trong `plan/briefs/VZ2-bao-cao.md`.

**Cấm:** như brief VZ2. Không đọc `.env`, không gọi `load_env_file()`, không mạng.

## Nghiệm thu

```
uv run ruff check app tests && uv run pytest -q -p no:cacheprovider tests/agent
cd web && npx tsc -b --noEmit && npx oxlint && npx vitest run && npx vite build
```

Claude thử lại trên 5173 với 3 câu ở trên, chụp ảnh hình và bảng.
