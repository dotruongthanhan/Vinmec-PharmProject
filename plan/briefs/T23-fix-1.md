# T23-fix-1 – Sửa lỗi của bản giao diện mới, rồi làm chế độ sáng / tối

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort xhigh) · **Ngày:** 17/11/2026
**Đọc trước:** `AGENTS.md`; `plan/briefs/T23-trang-chu-dang-nhap-va-bo-cuc-ba-cot.md`; `plan/briefs/T23-bo-sung-1-che-do-sang-toi.md`; `plan/plan-1.4-he-thong-thiet-ke.md`; `plan/api-hop-dong-v1.2-hoi-dap.md` (mục 4 mới); toàn bộ `web/src/`.

Làm theo thứ tự: **phần A (sửa lỗi) xong và qua nghiệm thu rồi mới làm phần B (chế độ sáng / tối)**.

## Phần A – lỗi tìm thấy khi review T23

Người review đã chạy `npm run build`, `npm run lint`, `npx vitest run` và mở trình duyệt ở 1440 × 900.

| # | Lỗi | Bằng chứng và yêu cầu |
| :-: | :--- | :--- |
| A1 | Build hỏng | `src/features/order-detail/OrderDetailView.tsx(14,10): TS6133 'Button' is declared but its value is never read` |
| A2 | Lint còn 4 cảnh báo | `EvidenceList.tsx:110` (`react(immutability)`: gán lại biến sau khi vẽ); `HeroAnimation.tsx:77` và `AssistantPanel.tsx:131` (`react(set-state-in-effect)`); `OrderDetailView.tsx:14`. Sửa nguyên nhân, không tắt luật |
| A3 | 1 test trượt | `style-guard.test.ts`: `lib/labChart.ts` chứa ký tự `▲` (U+25B2). Thay bằng chữ hoặc biểu tượng lucide ở tầng thành phần; không sửa test |
| A4 | **Dấu tiếng Việt vỡ ở chữ tiêu đề (Fraunces)** | Trên màn hình: `Tấ t cả y lệnh`, `truy vế t đầ y đủ`, `đố i chiế u và quyế t định`. Các chữ có hai dấu chồng (ấ, ầ, ố, ế) bị tách rời. Tìm nguyên nhân (thiếu tập ký tự tiếng Việt khi nhập phông; chuỗi ở dạng tách dấu NFD; hoặc phông không có đủ chữ). Nếu Fraunces không hiển thị đúng **toàn bộ** chữ tiếng Việt thì thay bằng một phông có chân hỗ trợ tiếng Việt đầy đủ (được phép `npm install` đúng một gói `@fontsource-variable/*` cho việc này và gỡ gói Fraunces). Thêm test: mọi chuỗi tiếng Việt viết cứng trong `web/src` ở dạng NFC. Chụp lại ba tiêu đề trên để xác nhận |
| A5 | Tải lại trang ở chế độ demo bị đá về đăng nhập | Mở thẳng `/app/y-lenh/DEMO-02` hoặc bấm F5 → về `/dang-nhap`. Giữ trạng thái demo trong `sessionStorage` (chỉ một cờ, không phải mã phiên), đăng xuất thì xoá. Có test cho hàm quyết định |
| A6 | Bảng danh sách y lệnh tràn ngang | Ở 1440px với trợ lý mở, cột `Kết quả` bị cắt và có thanh cuộn ngang. Bảng phải vừa vùng giữa ở mọi bề rộng ≥ 560px: cột tóm tắt co lại và cắt ba chấm, các cột khác giữ bề rộng tối thiểu |
| A7 | Danh sách thiếu cột của y lệnh | API sắp trả thêm `ma_y_lenh`, `thoi_diem_ke`, `nguoi_benh_tom_tat`, `thuoc` (hợp đồng v1.2 mục 4; task T24-fix-1 đang cài ở backend). Thêm vào `types.ts` (đều tuỳ chọn), `mockData.ts`, và bảng: cột theo đúng brief T23 mục 6.2 (thời điểm kê, mã y lệnh, người bệnh, khoa, thuốc `+n`, kết quả, phản hồi). Trường nào `null` hoặc vắng thì ô để trống, không vỡ bố cục. Cột tóm tắt bỏ khỏi bảng, chuyển thành chú giải của dòng |
| A8 | Dải người bệnh ở chi tiết rối | Nút `Y lệnh trước` / `Y lệnh sau` rơi xuống dòng riêng, đường dẫn trên thanh trên bị cắt thành `Y l… › YL-DEM…`. Sắp lại: hàng 1 gồm nút quay lại, mã, tuổi – giới – cân nặng – khoa, và hai nút trước / sau căn phải; hàng 2 gồm dị ứng, chẩn đoán chính và bốn chỉ số. Đường dẫn không được cắt mã y lệnh |
| A9 | Nhãn sáu yếu tố bị cắt | `Dị ứng, quá…`, `Trùng lặp…`, `Chỉ định, liều,…`. Cho xuống hai dòng, tên đầy đủ, sáu ô cao bằng nhau |
| A10 | File chết | Xoá `features/queue/` và các file cũ không còn được nhập (`CaseHeader.tsx`, `SummarySection.tsx`, `MetricCard.tsx`, `DetailTabs.tsx`, `ChatPanel.tsx`, `FindingsSection.tsx`, `SourceList.tsx`, `App.tsx` cũ nếu không còn dùng, `lib/queue.ts` nếu chỉ còn test dùng). Kiểm bằng tìm kiếm trước khi xoá; test của logic còn dùng thì giữ |

Thêm cho phần A: mở trình duyệt (hoặc dựng bằng công cụ bạn có) ở 1440, 1180, 900, 390px, soát năm màn (trang chủ, đăng nhập, danh sách, chi tiết DEMO-02, trợ lý) theo danh sách cấm ở mục 3.2 của brief T23; thấy gì vi phạm thì sửa và liệt kê trong báo cáo.

## Phần B – chế độ sáng / tối

Làm đúng `plan/briefs/T23-bo-sung-1-che-do-sang-toi.md`.

## Phạm vi file

`web/**` (được sửa `web/package.json` chỉ cho việc A4). **Cấm đụng:** `app/`, `db/`, `data/`, `config/`, `plan/`, `pyproject.toml`. Một task khác đang sửa `app/api/` song song.

## Nghiệm thu (chạy trong `web/`)

```bash
npm run build
npm run lint
npx vitest run
```

Cả ba sạch: build đạt, lint 0 cảnh báo, mọi test qua. Báo cáo ghi riêng kết quả phần A và phần B.

## Cấm làm

Không đổi tên trường hợp đồng. Không bịa nội dung y khoa hay số liệu. Không đọc tệp `.env` ở gốc kho. Không commit, không push. Trả lời theo mẫu trong `AGENTS.md`.
