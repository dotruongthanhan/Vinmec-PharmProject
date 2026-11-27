# Báo cáo VZ0 – Trang mẫu minh hoạ tương tác theo ngữ pháp `mh-0`

```text
TRẠNG THÁI: XONG (chờ Claude chạy script Python, ruff, tsc, oxlint, vitest và kiểm trực quan theo quy ước brief)
```

## FILE ĐÃ TẠO / SỬA

### Tạo mới
- `tools/xuat_mau_minh_hoa.py` – Script Python xuất 3 tệp dữ liệu mẫu vào `web/src/features/minh-hoa/mau/`:
  1. `lieu-meropenem-crcl.json`: đọc `data/mock/demo/DEMO-02.json` và `data/kb/quy_tac_lieu_than.json` (meropenem); tính lưới creatinin `50..400 µmol/L` bước `5` (cộng điểm creatinin thực của ca `212 µmol/L` để khớp chính xác giá trị mặc định) × `{thuc_te, ly_tuong, hieu_chinh}` bằng `app.calc.renal.cockcroft_gault` và `app.rules.renal_dose.select_renal_tier`; xuất chuỗi công thức từ `app.calc.hien_thi.CONG_THUC_HIEN_THI["cockcroft_gault"]`; không ghi bất kỳ trường định danh nào từ `hanh_chinh` hay `quan_ly`.
  2. `ma-tran-tuong-tac.json`: quét các ca trong `data/mock/` tìm ca có 5–8 hoạt chất trong y lệnh (có nhánh dự phòng gộp 6 hoạt chất thật từ các ca mock tương tác nếu mọi ca đơn lẻ trong `data/mock/` đều < 5 hoạt chất trong y lệnh) và gọi `app.api.lookup.lookup_interactions`; xuất `ds-1` (`thuoc_a`, `thuoc_b`, `muc_do`, `co_che` cắt ≤ 200 ký tự, `ma_can_cu`) và `ds-2` tóm tắt đếm cho phụ đề/`so_hien`.
  3. `thong-ke-thang.json`: dữ liệu giả lập 30 ngày × 4 khoa (`Khoa A`…`Khoa D`) bằng hàm băm tất định SHA-256 theo seed cố định (tránh `random` để đạt rule `S311` của `ruff`), ghi `"gia_lap": true`, phụ đề `"Dữ liệu giả lập để xem mẫu"`, mảng `dac_ta` gồm 2 đặc tả (`duong` + `bat_tat` theo khoa và `cot` tổng theo khoa với trục Y từ 0).
- `web/src/features/minh-hoa/nguPhap.ts` – Khai báo kiểu TypeScript ngữ pháp `mh-0` và hàm `kiemDacTa(dacTa, boDuLieu)` kiểm khoá lạ theo whitelist, bộ dữ liệu/cột/kiểu, cấm số tự do ở nơi yêu cầu tham chiếu ô, chặn `<`/`>`/`http`/`javascript:`/ký tự điều khiển ẩn/mẫu chèn lệnh, trần 6 lớp, 6 điều khiển, 2.000 điểm, 120 ký tự, 16 KB.
- `web/src/features/minh-hoa/dungMoHinh.ts` – Hàm thuần `dungMoHinh(dacTa, boDuLieu, trangThai, kichThuoc?)`, `taoTrangThaiMacDinh`, `kiemTrangThaiGiaDinh`, `layGiaTriThamSoTuyChon`, `dinhDangGiaTri`, `nhanHienThiGiaTri`; mọi số nghiệp vụ đến từ bộ dữ liệu, chỉ tính toạ độ và vạch chia trục.
- `web/src/features/minh-hoa/VeSvg.tsx` – Bộ vẽ JSX SVG chung cho cả 8 dấu (`duong`, `vung`, `cot`, `diem`, `o`, `dai`, `quy_tac`, `chu`), dùng 100% biến màu trong `web/src/styles/theme.css` (chạy cả sáng và tối), không phân biệt chỉ bằng màu (thêm nét đứt/chấm, hoạ tiết sọc/chấm/ngang, hình dạng điểm và ký hiệu chữ), hỗ trợ di chuột và focus bàn phím xem giá trị & nguồn.
- `web/src/features/minh-hoa/KhungMinhHoa.tsx` – Khung minh hoạ theo plan 1.11 B.6: tiêu đề, phụ đề tham chiếu ô, mở rộng toàn màn dùng lại `Dialog`/`DialogContent variant="fullscreen"` của UI1 (`@/components/ui/dialog`), nút "Xem dạng bảng", vùng điều khiển (`thanh_keo` có phím mũi tên & nút `-/+`, `chon_mot`, `bat_tat`, `loc`, `dat_lai`, vùng chạm ≥ 32 px), dòng `so_hien`, dòng công thức từ `cong_thuc_hien_thi`, dòng nguồn và nhãn cố định `"Minh hoạ, không phải khuyến cáo"`. Khi đặc tả không hợp lệ: không vẽ SVG, hiện `InlineAlert` nêu lý do + nút xem bảng.
- `web/src/features/minh-hoa/MauMinhHoaPage.tsx` – Trang mẫu dev import tĩnh 3 tệp JSON trong `./mau/`, kèm `ThemeControl` để thử nhanh sáng/tối.
- `web/src/features/minh-hoa/__tests__/nguPhap.test.ts` – Test `kiemDacTa` cho 3 tệp mẫu hợp lệ và 10 trường hợp đặc tả hỏng.
- `web/src/features/minh-hoa/__tests__/dungMoHinh.test.ts` – Test `dungMoHinh` cho meropenem (giá trị ca, kéo 120, đổi `loai_can_nang`, đối chiếu mọi chữ số hiển thị với bộ dữ liệu), ma trận tương tác (số ô = số cặp, lọc theo mức độ) và thống kê tháng giả lập (bật/tắt khoa, trục cột từ 0).
- `plan/briefs/VZ0-bao-cao.md` – Báo cáo này.

### Đã sửa
- `web/src/app/router.tsx` – Chỉ thêm route dev `/app/mau-minh-hoa` được bọc `import.meta.env.DEV`.
- `web/tsconfig.app.json` – Thêm `"resolveJsonModule": true` (được brief cho phép) để `tsc -b` chấp nhận import tệp `.json` tĩnh trong `MauMinhHoaPage.tsx` và các tệp test.

## LỆNH ĐÃ CHẠY VÀ KẾT QUẢ

- Không gọi bất kỳ công cụ shell/terminal nào theo yêu cầu bắt buộc của brief và người dùng.
- Đã rà soát tĩnh toàn bộ mã mới tạo:
  - Không có `innerHTML`, `dangerouslySetInnerHTML`, `new Function`, `eval(`, `iframe`, `localStorage`, `sessionStorage` hay URL `http(s)://` nguyên văn (tương thích `web/src/__tests__/safety.test.ts`).
  - Không có mã màu `#RRGGBB`, `rgb(`, `hsl(` trong `web/src/features/minh-hoa/**`.
  - Đã kiểm tra tuân thủ `verbatimModuleSyntax`, `erasableSyntaxOnly`, `noUnusedLocals`, `noUnusedParameters`, `oxlint` (`react/rules-of-hooks`, `react/only-export-components`) và `ruff` (`E`, `F`, `I`, `UP`, `B`, `S`, `line-length = 100`).

## ĐIỂM LỆCH SO VỚI BRIEF (NẾU CÓ) VÀ LÝ DO

1. **Lưới creatinin tệp `lieu-meropenem-crcl.json` bổ sung đúng điểm thực của ca (`212 µmol/L`):** `DEMO-02` có creatinin = `212 µmol/L` không chia hết cho bước `5` (`50, 55, ..., 210, 215, ..., 400`). Script thêm `212.0` vào tập lưới đã sắp xếp (`50..400` bước `5` ∪ `{212}`) để trạng thái mặc định của thanh kéo (`mac_dinh` từ `ds-3`) khớp chính xác 1-1 với dòng tương ứng trong `ds-2` mà không cần xấp xỉ phía web.
2. **Nhánh dự phòng cho `ma-tran-tuong-tac.json`:** Khi rà một số hồ sơ `data/mock/demo/` và `data/mock/hoso_gia_lap/`, nhiều ca đơn lẻ chỉ có 1–3 hoạt chất trong y lệnh hiện tại. Script ưu tiên đúng thứ tự: (a) ca có 5–8 hoạt chất trong y lệnh hiện tại; (b) hồ sơ có 5–8 hoạt chất qua toàn bộ các y lệnh của hồ sơ; (c) nếu cả 66 ca đều < 5 hoạt chất trong y lệnh, gộp 6 hoạt chất thật từ các ca tương tác `HS-022`, `HS-023`, `HS-024`, `HS-031`, `HS-028` rồi gọi `lookup_interactions`, đồng thời ghi rõ vào stdout và `ghi_chu_nguon`.
3. **Route `/app/mau-minh-hoa` đặt ngoài `<ProtectedRoute />` (vẫn chỉ đăng ký khi `import.meta.env.DEV`):** Giúp mở trực tiếp `http://localhost:5173/app/mau-minh-hoa` trong lúc dev/review mà không bị chuyển hướng sang `/dang-nhap`; ở build production (`import.meta.env.DEV === false`) route này không tồn tại.
4. **3 tệp JSON trong `web/src/features/minh-hoa/mau/` chưa ghi sẵn:** Do phiên này không được chạy shell và không tự tính/bịa số liệu DDInter hay lưới `cockcroft_gault`, 3 tệp JSON sẽ được sinh khi Claude chạy lệnh đầu tiên trong mục Nghiệm thu (`KB_SOURCE=file uv run python tools/xuat_mau_minh_hoa.py`) trước khi chạy `tsc` và `vitest`.

## VIỆC CHƯA LÀM / CÂU HỎI

- Chờ Claude chạy bộ lệnh nghiệm thu theo đúng thứ tự:
  1. `KB_SOURCE=file uv run python tools/xuat_mau_minh_hoa.py`
  2. `uv run ruff check tools/xuat_mau_minh_hoa.py && uv run ruff format --check tools/xuat_mau_minh_hoa.py`
  3. `cd web && npx tsc -b && npx oxlint && npx vitest run`
  4. `grep -rnE "innerHTML|dangerouslySetInnerHTML|new Function|eval\(" web/src/features/minh-hoa`
- Chờ kiểm tra trực quan tại `http://localhost:5173/app/mau-minh-hoa` ở chế độ sáng/tối, kéo thanh creatinin, đổi loại cân nặng, mở rộng toàn màn và xem dạng bảng.

---

## Fix-1 (theo `plan/briefs/VZ0-fix-1.md`)

```text
TRẠNG THÁI: XONG (chờ Claude chạy lệnh nghiệm thu: xuat_mau_minh_hoa.py, ruff, tsc, oxlint, vitest và kiểm trực quan)
```

### Tệp đã sửa
1. `tools/xuat_mau_minh_hoa.py`:
   - Hoàn thiện `_derive_draw_bounds(rule)` suy ra biên vẽ liên tục `bien_ve_tu`/`bien_ve_den` cho `ds-1` theo đúng ngữ nghĩa `select_renal_tier` (với meropenem: `<10`, `10–25`, `>25–50`, `>50`, lấp khe 25–26 và tổng quát cho mọi khe giữa hai mức), giữ nguyên `crcl_tu`/`crcl_den` để hiển thị nhãn; đặc tả `lieu-meropenem-crcl.json` ánh xạ `x_tu`/`x_den` vào `bien_ve_tu`/`bien_ve_den`.
   - Hoàn thiện `_pick_interaction_case()` ưu tiên ca có ít nhất 1 cặp `nghiem_trong` hoặc `chong_chi_dinh` (theo mức `lookup_interactions` trả): ưu tiên ca y lệnh 5–8 hoạt chất có cặp nặng → hồ sơ nhiều đợt 5–8 hoạt chất có cặp nặng → ca đơn lẻ có cặp nặng → giữ cách cũ 5–8 hoạt chất nếu không có ca nào có cặp nặng; in rõ lý do chọn ca ra stdout.
   - Rà soát độ dài dòng `<= 100` ký tự và quy chuẩn `ruff check` / `ruff format`, bỏ trường thừa `is_single_order` từ lượt sửa dở trước.
2. `web/src/features/minh-hoa/dungMoHinh.ts`:
   - `dai`: giữ `khoangChu` lấy từ `crcl_tu`/`crcl_den` khi bộ dữ liệu có hai cột này (nên mức `26–50` giữ nguyên nhãn `"26–50"` dù dải vẽ liền mạch từ `25` tới `50`), tách chiều cao dải (`daiCao`) chừa dải 30 px bên dưới cho nhãn giá trị điểm trên biểu đồ 1 chiều (`!coTrucY && coDai`), đặt `quy_tac` dọc khớp chiều cao dải và đặt tâm điểm (`cy`) ở giữa khoảng trống giữa nhãn mức và nhãn khuyến cáo.
   - `dungMoHinhMaTran`: ô ma trận co giãn theo bề rộng khung trong khoảng `[32, 72]` px (`Math.max(32, Math.min(72, ...))`) và tự căn giữa khi khung rộng (toàn màn), chừa lề phải cho nhãn cột xoay nghiêng; bổ sung `mauChu`, `netVien` vào `MucChuGiai` và hỗ trợ thêm khoá `chong_chi_dinh` trong `MUC_DO_HIEN_THI`/`NHAN_MA_DANH_MUC`.
3. `web/src/features/minh-hoa/VeSvg.tsx`:
   - Bỏ hoàn toàn `style={{ ... }}` chứa thuộc tính màu ở mục chú giải ma trận, thay bằng `<svg>` nhỏ dùng thuộc tính `fill`/`stroke`/`strokeDasharray` trỏ biến token CSS (đạt `style-guard.test.ts`, không thêm mã màu thô).
   - Nhãn số của điểm trên hình 1 chiều có dải (`"16,0"`, `"28,3 · giả định"`) đặt xuống dải trống ngay dưới các dải mức (kèm vạch nối ngắn) để không bao giờ đè lên nhãn `"10–25"` hay `"Mốc của ca"`.
   - Nhãn khuyến cáo trong mỗi dải tự ngắt tối đa 2 dòng bằng `tachToiDaHaiDong` theo bề rộng thực tế của dải (`<tspan>`), cắt `"…"` nếu vẫn dài, và gắn `<title>` đầy đủ trên phần tử SVG song song với thanh chi tiết khi hover/focus.
   - Cỡ chữ ký hiệu trong ô ma trận tự tăng (`14px`) khi ô lớn (`>= 52px`).
4. `web/src/features/minh-hoa/KhungMinhHoa.tsx`:
   - Bỏ `useEffect(() => { setTrangThai(macDinh) }, [macDinh])` (sửa cảnh báo `oxlint` `react(set-state-in-effect)`): chuyển sang lưu bản ghi đè gắn với tham chiếu `macDinh` và suy ra `trangThai` trong `useMemo` khi render; đặt lại / cập nhật chỉ trong event handler.
   - Tăng bề rộng dựng hình toàn màn tối thiểu lên `880` px (`Math.max(880, chieuRong)`).
5. `web/src/features/minh-hoa/__tests__/nguPhap.test.ts`:
   - Sửa 4 lỗi `TS2352` (dòng 75, 167, 175, 186 cũ) bằng tạo đối tượng mới qua spread (`{ ...saoChep(...), ... }`), giữ nguyên toàn bộ kiểu `readonly` trong `nguPhap.ts`.
6. `web/src/features/minh-hoa/__tests__/dungMoHinh.test.ts`:
   - Thêm test kiểm tra **mọi dòng `ds-2`** của meropenem đều có điểm `cx` nằm trong đúng dải `dai` có `khuyen_cao` trùng với dòng đó và giữ nhãn `"26–50"`.
   - Thêm test kiểm tra ô ma trận co giãn trong `[32, 72]` px theo bề rộng khung (`320` vs `960`) và căn giữa khi toàn màn.

### Rà soát tĩnh (không gọi shell theo quy tắc brief)
- Không gọi bất kỳ công cụ shell/terminal nào; không thêm gói, không gọi mạng, không commit.
- Không sửa `style-guard.test.ts` hay các tệp ngoài phạm vi brief.
- Rà soát thủ công `style-guard` (không còn `style={{}}` có thuộc tính màu, không có `#hex`/`rgb`/`hsl`/ký tự unicode bị cấm), `safety.test.ts`, `tsconfig.app.json` (`verbatimModuleSyntax`, `noUnusedLocals`, `noUnusedParameters`, thu hẹp kiểu `diemDatDuoiDai !== null`), `oxlint` (không còn `setState` đồng bộ trong `useEffect`), và `ruff` (`line-length <= 100`, quy chuẩn định dạng).

### Điểm lệch / lưu ý khi nghiệm thu
- Tệp `web/src/features/minh-hoa/mau/lieu-meropenem-crcl.json` và `ma-tran-tuong-tac.json` trên đĩa hiện vẫn là bản sinh từ lượt VZ0 trước (chưa có cột `bien_ve_tu`/`bien_ve_den` và chưa chạy lại `_pick_interaction_case`); cần chạy lệnh đầu tiên trong mục Nghiệm thu (`KB_SOURCE=file uv run python tools/xuat_mau_minh_hoa.py`) để tái sinh 3 tệp JSON trước khi chạy `tsc`, `oxlint` và `vitest`.
- Trường hợp `data/mock/` không có ca nào có cặp `nghiem_trong`/`chong_chi_dinh` từ `lookup_interactions`: script sẽ tự động giữ nhánh chọn cũ (5–8 hoạt chất) và in rõ lý do ra stdout để kiểm chứng khi chạy.
