# T42 – Sinh phiếu điều trị cho 60 hồ sơ giả lập

## Bối cảnh
Plan 1.7: 60 hồ sơ ở `data/mock/hoso_gia_lap/HS-001..060.json` (87 đợt điều trị, 222 y lệnh). Mỗi đợt hiện chỉ có vài dòng `dien_bien` ngắn (trung bình 2,5 dòng, loại "Tờ điều trị", "Phiếu khám"). Chưa có phiếu điều trị theo ngày. Cần sinh **phiếu điều trị đúng nghĩa**, bám sát hồ sơ và y lệnh của chính đợt đó, dài và chi tiết hơn, giống bệnh án thật.

Ngữ cảnh đọc trước: `plan/plan-1.7-du-lieu-benh-an-gia-lap.md` (mục 5, 6), `data/mock/hoso_gia_lap/BANG_TRA.md` (kịch bản, lỗi cài, đáp án từng hồ sơ), `data/gold/hoso_gia_lap/` (đáp án). Tham khảo cách ghi nhận theo thời gian ở `data/tham_khao/mimic-iv-demo/` (chỉ tham khảo cấu trúc, không chép dòng; giấy phép ODbL).

## Phạm vi file
Được sửa/tạo:
- `data/mock/hoso_gia_lap/HS-001..060.json`: **chỉ thêm khóa `phieu_dieu_tri` vào từng phần tử của `dot_dieu_tri`**. Không đổi bất kỳ khóa nào khác (kiểm bằng băm phần còn lại trước và sau).
- `tools/kiem_phieu_dieu_tri.py` (mới): script kiểm của task này.
- `tools/kiem_ho_so_gia_lap.py`: chỉ để cho phép khóa `phieu_dieu_tri` trong `DOT_KEYS` (tùy chọn); không đổi logic khác.
- `plan/reports/T42.md`.

Cấm đụng: `app/`, `db/`, `web/`, `tests/`, `data/gold/`, `data/mock/demo/`, `_kich_ban.json`, mọi khóa khác trong hồ sơ.

## Cấu trúc mỗi phiếu (phần tử của `phieu_dieu_tri`, mỗi đợt một danh sách theo ngày)
```
{
  "phieu_dieu_tri_id": "PDT-HS-001-1-01",      // PDT-<ho_so>-<thu_tu_dot>-<so_ngay hai chu so>
  "ngay_dieu_tri": 1,                           // ngày thứ mấy của đợt (từ 1)
  "thoi_diem_lap": "2026-11-12T08:30:00+07:00", // trong [bat_dau, ket_thuc] của đợt
  "vai_tro_nguoi_lap": "bac_si_dieu_tri",       // hoặc "bac_si_truc", "hoi_chan"
  "dien_bien": "…",            // chủ quan + khách quan: triệu chứng, sinh hiệu, thăm khám (3–6 câu)
  "danh_gia": "…",             // đánh giá bệnh, đáp ứng điều trị, vấn đề tồn đọng (2–4 câu)
  "huong_xu_tri": "…",         // kế hoạch ngày: tiếp tục/đổi/ngưng thuốc, xét nghiệm cần làm, hẹn (2–4 câu)
  "y_lenh_trong_ngay": ["YL-HS-001-01", …],   // mã y lệnh có hiệu lực hoặc được kê trong ngày đó, có thật trong đợt
  "che_do_cham_soc": "cấp 2",   // cấp 1 / cấp 2 / cấp 3 (ngoại trú: null)
  "che_do_an": "Cơm mềm, ít muối",
  "theo_doi": ["Huyết áp 2 lần/ngày", …],     // 1–4 mục theo dõi phù hợp bệnh và thuốc
  "dan_do": "…"                // dặn dò người bệnh/điều dưỡng, 1–2 câu (có thể null)
}
```

## Số lượng phiếu
- Nội trú: một phiếu mỗi ngày điều trị, từ ngày 1 đến `so_ngay_dieu_tri` (tối đa 10 phiếu mỗi đợt; đợt dài hơn thì lấy ngày 1, các ngày có sự kiện quan trọng như đổi y lệnh, và ngày cuối).
- Ngoại trú: 1 phiếu cho buổi khám.
- Ngày có đổi hoặc ngưng y lệnh phải có phiếu và nêu lý do (khớp `ly_do_ngung`).

## Yêu cầu nhất quán (cốt lõi)
1. Mọi số liệu nêu trong phiếu (huyết áp, mạch, nhiệt độ, SpO2, creatinin, K, …) **phải khớp** `sinh_hieu`, `xet_nghiem`, `vi_sinh` của đợt đó nếu có cùng thời điểm; chỉ số chưa có trong hồ sơ thì chỉ nói định tính, không bịa số mới trái với hồ sơ.
2. Tên thuốc, liều, đường dùng, tần suất nhắc trong phiếu phải khớp dòng chi tiết y lệnh tương ứng (xem `y_lenh[].chi_tiet`). `y_lenh_trong_ngay` chỉ chứa mã y lệnh có thật trong đợt, có hiệu lực trong ngày đó (`thoi_diem_ke` ≤ ngày ≤ `thoi_diem_ngung` nếu ngưng).
3. Y lệnh đang **chờ duyệt** (trọng tâm, `trang_thai = cho_duyet`) chỉ xuất hiện ở phiếu của ngày kê, ghi là "chỉ định/đề nghị", không được mô tả là đã dùng. Các phiếu sau thời điểm kê không cần viết (đợt cuối kết thúc ở thời điểm kê).
4. Không để phiếu "sửa lỗi" cho lỗi cài: lỗi cài (tương tác, liều, dị ứng…) của y lệnh trọng tâm giữ nguyên; phiếu không nhắc "đã phát hiện sai sót", không phản bác hay xác nhận lỗi; chỉ mô tả bệnh cảnh như bác sĩ điều trị bình thường.
5. Dị ứng, thai kỳ, chức năng thận/gan, cân nặng nêu trong phiếu khớp `tinh_trang_di_ung`, `co_dia`, `chan_doan` của hồ sơ.
6. Diễn tiến theo thời gian hợp lý: ngày 1 nặng hơn, các ngày sau đáp ứng hoặc biến chứng theo kịch bản; phiếu ngày cuối phù hợp `tong_ket` và `hinh_thuc` ra viện của đợt. Không mâu thuẫn với các dòng `dien_bien` đã có (đối chiếu, không sửa chúng).
7. Văn phong tiếng Việt y khoa thực tế (viết tắt BN, HA, SpO2, XN…), mỗi phiếu khác nhau về câu chữ, không lặp một câu mẫu qua nhiều phiếu, không dùng mẫu thế chỗ ghép. Tổng chiều dài một phiếu khoảng 500–1200 ký tự cho ba trường văn bản.
8. Không tên thật, không mã người bệnh thật, không số điện thoại. Nhân sự chỉ ghi theo vai trò.

## Nghiệm thu
- `tools/kiem_phieu_dieu_tri.py` bạn tự viết, kiểm tự động: đủ trường và kiểu; ID duy nhất và đúng mẫu; `thoi_diem_lap` trong đợt và tăng dần theo ngày; số phiếu đúng quy tắc; `y_lenh_trong_ngay` tồn tại và hiệu lực; không còn khóa lạ; phần còn lại của hồ sơ không đổi (so băm với bản git `HEAD`); chiều dài trường văn bản trong khoảng; không có hai phiếu trùng nguyên văn; mọi số `HA`, `mạch`, `nhiệt độ`, `SpO2`, `creatinin`… nêu trong phiếu phải có trong sinh hiệu/xét nghiệm cùng đợt (kiểm bằng regex ở mức hợp lý, ghi rõ mức kiểm). Kết quả mục tiêu: `0 hồ sơ lỗi`.
- Chạy và dán kết quả: `PYTHONUTF8=1 uv run python tools/kiem_phieu_dieu_tri.py`, `PYTHONUTF8=1 uv run python tools/kiem_ho_so_gia_lap.py` (0 hồ sơ lỗi), `uv run pytest tests/db -q --basetemp=.pytest_tmp`, `uv run python -m app.db all --dry-run` (0 dòng loại; nếu loader lỗi vì khóa mới, **dừng và báo**, không sửa `app/db`).
- Tự đọc lại ngẫu nhiên 8 hồ sơ (gồm HS-019, HS-028, HS-037, HS-040) để chắc câu chữ không mâu thuẫn với hồ sơ/y lệnh.
- Báo cáo `plan/reports/T42.md`: số phiếu, số hồ sơ, lệnh đã chạy và kết quả, các chỗ nghi ngờ.

## Cấm làm
- Không commit, không push. Không đụng khóa/bí mật. Không nạp DB.
- Không dùng LLM bên ngoài (OpenRouter/DeepSeek) để sinh; tự viết nội dung.
- Xóa mọi tệp tạm (`.pytest_tmp*`).

## Bổ sung 1 (18/11, sau lần chạy đầu dừng vì thiếu quy tắc)
1. **Đợt đang mở** (nội trú mà thiếu `so_ngay_dieu_tri` và `thoi_diem_ket_thuc`, khoảng 50 đợt): điểm cuối để tính là `thoi_diem_ke` của y lệnh muộn nhất trong đợt (thường là y lệnh trọng tâm chờ duyệt). Số ngày = số ngày lịch từ `thoi_diem_bat_dau` đến điểm đó, tối thiểu 1, tối đa 10 phiếu (áp quy tắc chọn ngày quan trọng như brief). Mọi `thoi_diem_lap` phải ≤ điểm cuối này. **Không điền** `so_ngay_dieu_tri`/`thoi_diem_ket_thuc` vào hồ sơ.
2. **Bản gốc bất biến để so băm**: hồ sơ chưa được git theo dõi nên không so với `HEAD`. Thay vào đó so với bản sao nguyên trạng ở `data/mock/_goc_hoso_truoc_T42/HS-*.json` (đã chép sẵn, **cấm sửa**). Kiểm: bỏ khóa `phieu_dieu_tri` khỏi từng đợt thì tệp mới phải bằng bản gốc (so JSON đã chuẩn hóa).
3. Không dừng giữa chừng để hỏi: nếu gặp điểm chưa rõ khác, tự chọn cách hợp lý nhất, ghi rõ trong `plan/reports/T42.md` mục "Lựa chọn đã làm", rồi làm hết.
