# T44 – Bộ chọn y lệnh trong hồ sơ + phiếu điều trị lên DB và giao diện

**Thứ tự: làm SAU T45** (T45 đổi tab Hồ sơ bệnh án, lược đồ `nguoi_benh`/`dot_dieu_tri` và API; T44 xây tiếp trên nền đó, đọc lại hợp đồng `plan/api-hop-dong-v1.5-hanh-chinh.md` và `plan/reports/T45.md` trước khi làm, không ghi đè phần của T45).

Mô hình giao: `gpt-6.1-sol`, effort `high` (`gpt-6.2-sol` không dùng được trên tài khoản này). Chạy bằng chế độ nền của app, không dùng `&`.

## Bối cảnh
Ca bệnh nay đọc từ Supabase (`CASE_SOURCE=db`, T43). Mỗi ca là một hồ sơ; y lệnh trọng tâm (chờ duyệt) dựng `CaBenh` từ **lần vào viện cuối**. Hai thiếu sót cần xử lý, thấy trên giao diện:

1. **Tab "Y lệnh" nhãn sai và thiếu y lệnh.** Nhãn `Y lệnh (n)` đang đếm **dòng thuốc** (chờ duyệt + đang dùng), không phải y lệnh. Hồ sơ HS-022 có 7 y lệnh (lần 1: YL-HS-022-06, -07; lần 2: -01…-05) nhưng API chỉ trả y lệnh chờ duyệt và thuốc đang dùng. Cần **bộ chọn y lệnh** trong hồ sơ; mặc định chọn y lệnh dược sĩ mở từ danh sách ngoài (y lệnh trọng tâm).
2. **Phiếu điều trị mới có trong tệp, chưa lên DB.** 333 phiếu theo ngày nằm ở khóa `phieu_dieu_tri` trong từng phần tử `dot_dieu_tri` của `data/mock/hoso_gia_lap/HS-*.json` (cấu trúc xem `plan/briefs/T42-sinh-phieu-dieu-tri.md`). Tab "Phiếu điều trị" đang `(0)`.

Ngữ cảnh đọc: `db/schema.sql`, `app/db/{mapping,sources,engine,cli,reader}.py`, `app/api/{schemas,service,routes}.py`, `plan/api-hop-dong-v1.md` (+ bản bổ sung), `web/src/features/order-detail/OrderDetailView.tsx`, `web/src/lib/uiTypes.ts`, `web/src/api/`, `plan/plan-1.4-he-thong-thiet-ke.md`.

## Nguyên tắc thiết kế (bắt buộc)
- **Không đụng đường thẩm định AI.** `CaBenh` (domain) và pipeline giữ nguyên. Dữ liệu mới (toàn bộ y lệnh, phiếu điều trị) lấy qua đường đọc riêng, **không** nhét vào `CaBenh`.
- Chế độ `CASE_SOURCE=file` (EC2 mặc định) vẫn chạy: khi không có DB thì danh sách y lệnh suy từ `CaBenh` (y lệnh chờ duyệt + thuốc đang dùng) và phiếu điều trị trả mảng rỗng, không lỗi.
- Chỉ **thêm** vào hợp đồng API, không đổi tên hay xóa trường cũ.
- Dữ liệu 100% giả lập; không in dữ liệu người bệnh ra log.

## Phần A – Phiếu điều trị lên DB
1. `db/schema.sql`: thêm bảng `nghiep_vu.phieu_dieu_tri` (`phieu_dieu_tri_id` PK, `dot_dieu_tri_id` FK, `ngay_dieu_tri` int, `thoi_diem_lap` timestamptz, `vai_tro_nguoi_lap` có CHECK, `dien_bien`, `danh_gia`, `huong_xu_tri` text, `y_lenh_trong_ngay` text[] hoặc bảng nối `phieu_y_lenh` (chọn cách có FK đến `y_lenh`; nêu lựa chọn trong báo cáo), `che_do_cham_soc`, `che_do_an`, `theo_doi` jsonb/text[], `dan_do`, `nap_luc`, `nguon_tep`), có RLS bật không policy và REVOKE giống các bảng khác. Thêm vào lệnh nạp từ đầu.
2. `app/db/mapping.py`, `sources.py`, `engine.py`, `cli.py`: đọc `phieu_dieu_tri` của từng đợt và nạp. Thêm lệnh **chỉ nạp bảng này** (không `--reset`, idempotent: upsert theo khóa), ví dụ `uv run python -m app.db phieu-dieu-tri`, để thêm vào Supabase đang chạy mà không xóa dữ liệu khác. Thêm `--dry-run`.
3. Test: `tests/db/` cho ánh xạ, nạp thử trong bộ nhớ, ràng buộc FK; số đếm trên dữ liệu thật phải là 333 phiếu / 60 hồ sơ.

## Phần B – API (thêm vào hợp đồng)
Cập nhật `plan/api-hop-dong-v1.4-ho-so-y-lenh-phieu.md` (tạo mới, mô tả phần thêm). Thêm vào phản hồi chi tiết ca hiện có (hoặc endpoint con `GET /api/cases/{ca_id}/ho-so`, chọn cách ít phá vỡ nhất, nêu lý do):
- `danh_sach_y_lenh`: toàn bộ y lệnh của **mọi lần vào viện** của người bệnh, mỗi phần tử: `y_lenh_id`, `dot_dieu_tri_id`, `thu_tu_dot`, `thoi_diem_ke`, `trang_thai`, `loai`, `vai_tro_nguoi_ke`, `khoa_ke_don`, `luong_duyet`, `ly_do_ngung`, `thoi_diem_ngung`, `thay_the_y_lenh_id`, `la_trong_tam` (true cho y lệnh có `ca_id` bằng ca đang mở), và `dong` dùng **cùng cấu trúc dòng thuốc** như phần `chi_tiet.y_lenh` hiện có (liều, tần suất, đường dùng, lịch dùng…). Sắp theo `thu_tu_dot`, rồi `thoi_diem_ke`.
- `phieu_dieu_tri`: danh sách phiếu của mọi lần vào viện, mỗi phiếu có đủ các trường ở Phần A, kèm `dot_dieu_tri_id`, `thu_tu_dot`. Sắp theo lần vào viện rồi ngày.
- Đọc DB bằng truy vấn chỉ-đọc trong `app/db/reader.py` (hoặc module cùng thư mục), gộp truy vấn theo danh sách đợt (tránh N+1), dựng được **không cần dựng `CaBenh`**. Có test không cần kết nối (hàm dựng thuần từ các hàng).
- Giữ xác thực và phân quyền như các route khác; không lộ lỗi hệ thống.
- Lệnh kiểm trên Supabase thật (chỉ đọc): mở rộng `python -m app.db.reader verify-read` hoặc thêm `verify-ho-so`: mỗi ca phải có `số y lệnh` bằng số y lệnh của người bệnh trong DB (HS-022 = 7) và `số phiếu` bằng số phiếu đã nạp.

## Phần C – Giao diện (`web/`)
Bám `plan/plan-1.4-he-thong-thiet-ke.md` (nền tối, token màu, thành phần sẵn có).
1. **Tab Y lệnh:**
   - Nhãn `Y lệnh (n)` với `n` = **số y lệnh** (từ `danh_sach_y_lenh`), không phải số dòng thuốc.
   - Thêm **bộ chọn y lệnh** đầu tab: danh sách các y lệnh nhóm theo lần vào viện (nhãn "Lần vào viện 2 · 10/11/2026" …), mỗi mục hiện mã, thời điểm kê, trạng thái (nhãn màu như cột "Trạng thái"), thuốc chính (tên 1–2 thuốc). Dùng thành phần chọn sẵn có (Select/Popover/Tabs); phải dùng được bằng bàn phím và có `aria-label`.
   - **Mặc định chọn y lệnh trọng tâm** (`la_trong_tam`), tức y lệnh dược sĩ đã bấm ở danh sách ngoài. Có thể đổi sang y lệnh khác; chọn xong hiện đúng thông tin y lệnh đó (khoa kê, luồng, thời điểm kê, trạng thái, lý do ngưng/y lệnh thay thế nếu có) và bảng dòng thuốc kèm lịch dùng.
   - Lưu lựa chọn trên URL (`?tab=y_lenh&yl=<y_lenh_id>`) để tải lại vẫn giữ; đổi ca thì quay về y lệnh trọng tâm.
   - Giữ hành vi "bấm một dòng thuốc để chuyển sang thẻ Thẩm định" **chỉ khi y lệnh đang xem là trọng tâm** (các y lệnh khác không có nhận định AI).
   - Các khối "Chi tiết y lệnh chờ duyệt" và "Thuốc đang dùng và đã ngừng" hiện nay: giữ cho y lệnh trọng tâm; y lệnh khác hiển thị dòng thuốc của chính nó.
2. **Tab Phiếu điều trị:** nhãn `Phiếu điều trị (n)` với `n` = số phiếu. Nhóm theo lần vào viện, mỗi phiếu là một thẻ theo ngày: ngày điều trị + thời điểm lập + vai trò người lập; diễn biến, đánh giá, hướng xử trí (đoạn văn); chế độ chăm sóc, chế độ ăn, theo dõi (danh sách), dặn dò; các y lệnh trong ngày là liên kết nhỏ chuyển sang tab Y lệnh với `yl=` tương ứng. Rỗng thì dùng trạng thái rỗng sẵn có.
3. Sửa nhỏ: ở "Dữ liệu đầu vào" của bảng chỉ số lâm sàng, "68,0 tuoi" phải là "68,0 tuổi".
4. Cập nhật kiểu và `mockData` của web cho các trường mới (để chế độ demo không đổi hành vi, trường mới tùy chọn).

## Nghiệm thu (chạy và dán kết quả vào báo cáo)
- Python: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -q --basetemp=.pytest_tmp` đều sạch (hiện 932 test qua; thêm test mới).
- Web (trong `web/`): `npx vitest run`, `npx oxlint`, `npx tsc -b`, `npm run build` đều qua; thêm test: nhãn số y lệnh đúng số y lệnh; mặc định chọn y lệnh trọng tâm; đổi y lệnh đổi nội dung; `?yl=` giữ lựa chọn; tab Phiếu điều trị đếm và nhóm theo lần vào viện; rỗng khi không có dữ liệu.
- `uv run python -m app.db all --dry-run` và `uv run python -m app.db phieu-dieu-tri --dry-run`: 0 dòng loại, 333 phiếu.
- Chạy thử thật với `CASE_SOURCE=file AUTH_MODE=off`: `GET` chi tiết ca vẫn đúng và `phieu_dieu_tri` rỗng, không lỗi. (Việc nạp phiếu lên Supabase thật và kiểm với DB thật do Claude làm sau khi review; Codex không kết nối DB thật được.)
- Báo cáo `plan/reports/T44.md`: danh sách tệp, lựa chọn thiết kế (bảng nối hay mảng cho `y_lenh_trong_ngay`, endpoint con hay mở rộng phản hồi), lệnh đã chạy và kết quả, điểm chưa xong.

## Cấm làm
- Không commit, không push, không ghi vào DB thật, không `--reset`, không đụng `.env` hay bí mật.
- Không đổi `CaBenh`, pipeline AI, prompt, quy tắc, `data/mock/hoso_gia_lap` (trừ khi chỉ đọc), `data/gold/`.
- Không thêm thư viện mới. Không dùng `&` để chạy nền. Xóa tệp tạm (`.pytest_tmp*`).
- Không dừng giữa chừng để hỏi: gặp điểm chưa rõ thì tự chọn cách ít rủi ro nhất, ghi vào báo cáo mục "Lựa chọn đã làm", rồi làm hết.
