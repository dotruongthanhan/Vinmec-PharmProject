# T70 – Dữ liệu D6 (độc tính) + D7 (kháng sinh quản lý): hai bảng có trích dẫn

Agent: **sub Sonnet** (việc dữ liệu). Không viết code ứng dụng. Mạng: chỉ khi cần kiểm lại một nhãn openFDA / DailyMed; nguồn chính đã có trong máy.

Chạy song song với T65-T66 hoàn thiện (đụng tệp khác) và hai agent code T71 (luật D6), T72 (luật D7). Hai agent code đọc bảng của bạn theo **đúng lược đồ dưới đây**, nên tên khoá phải đúng chính tả.

## Đọc trước

- `AGENTS.md` (quy tắc 9), `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md` mục 2, **Đợt D6**, **Đợt D7**.
- `docs/du-lieu/README.md`, `openfda-rag.md`, `livertox.md`, `van-ban-byt.md`, `tu-dien-tra-cuu.md`, `ca-gia-lap.md`, `di-ung-cheo.md` (mẫu bảng có trích).
- `data/kb/nguong_xet_nghiem.json`, `data/kb/quy_tac_gan.json` (D4 đã có: **không lặp lại** ngưỡng nồng độ digoxin / phenytoin và khuyến cáo suy gan ở bảng mới).

Phạm vi hoạt chất: mọi hoạt chất của 66 ca (lấy bằng `app.db.reader.load_source_cases(Path("."))` + bảng chuyển mã / trục `tra_cuu.sqlite`; không đọc thẳng `HS-*.json`, không đếm `_kich_ban.json`). Khoá hoạt chất là `hoat_chat_id` trên trục.

## Việc 1 – `data/kb/doc_tinh.json` (D6)

```json
{
  "phien_ban": "D6-v1", "ngay": "2026-11-19", "trang_thai": "cho_duoc_si_duyet", "ghi_chu": "...",
  "doc_than":   [ {"hoat_chat_id": "...", "nhom": "aminoglycosid|glycopeptid|nsaid|polymyxin|...", "nguon": [NGUON], "trang_thai": "cho_duoc_si_duyet"} ],
  "keo_dai_qt": [ {"hoat_chat_id": "...", "muc_nhan": "boxed_warning|warnings_and_cautions|...", "nguon": [NGUON], "trang_thai": "..."} ],
  "khoang_dieu_tri_hep": [ {"hoat_chat_id": "...", "ma_xet_nghiem_nong_do": ["digoxin"], "nguon": [NGUON], "trang_thai": "..."} ],
  "doc_gan_livertox": [ {"hoat_chat_id": "...", "likelihood_score": "A|B|C|D|E|E*|X", "nguon": [NGUON], "trang_thai": "..."} ],
  "khong_co_nguon": [ {"hoat_chat_id": "...", "danh_sach": "doc_than|keo_dai_qt|...", "ly_do": "..."} ]
}
```

`NGUON` = `{"loai": "nhan_fda|livertox", "ten_nhan": ..., "set_id": ..., "tep": "<đường dẫn tệp trong kho>", "truong_nhan": ..., "ma_chuyen_luan": ..., "trich_nguyen_van": "...", "url": "...", "ngay_lay": "2026-11-19"}`.

Quy tắc:
- **`doc_than`**: chỉ đưa vào khi nhãn FDA của hoạt chất có câu về độc thận / tổn thương thận do thuốc (nephrotoxicity, acute kidney injury, renal failure do thuốc) ở mục boxed warning / warnings / adverse reactions. Trích nguyên văn câu đó.
- **`keo_dai_qt`**: chỉ khi nhãn có câu về kéo dài QT / torsades de pointes ở boxed warning hoặc warnings and precautions (không lấy từ adverse reactions đơn lẻ). Trích nguyên văn.
- **`khoang_dieu_tri_hep`**: chỉ khi nhãn khuyến cáo theo dõi nồng độ thuốc trong máu (serum concentration / trough / drug level monitoring). `ma_xet_nghiem_nong_do` là mã xét nghiệm dự kiến trong ca (ca đã có `digoxin`, `phenytoin`; với vancomycin, gentamicin, valproic acid dùng `vancomycin`, `gentamicin`, `valproat` và ghi trong `ghi_chu` là mã dự kiến). **Không** ghi khoảng đích (đã ở D4).
- **`doc_gan_livertox`**: lấy "Likelihood score" trong chuyên luận NXML (`data/kb_sources/livertox/giai_nen/...`, tra theo `muc_luc.csv`). Trích nguyên văn câu chứa điểm. `url` dạng `https://www.ncbi.nlm.nih.gov/books/<ID chương>/` nếu NXML có ID; không có thì để URL trang sách NBK547852 và ghi mã chương.
- Hoạt chất được xét mà không thấy câu nhãn: ghi vào `khong_co_nguon`. **Không suy từ kiến thức chung**, không thêm hoạt chất vì "ai cũng biết là độc thận".

## Việc 2 – `data/kb/khang_sinh_quan_ly.json` (D7, QĐ 5631/QĐ-BYT)

Nguồn: `data/kb_sources/van_ban_byt/qd5631_2020/qd5631_duytan.pdf` (bản sao thứ cấp; chữ tiếng Việt có ký tự lạ, xem `van-ban-byt.md`). Tách phụ lục danh mục kháng sinh **phải phê duyệt trước khi sử dụng** và danh mục **ưu tiên quản lý / giám sát** (đúng tên nhóm như văn bản).

```json
{
  "phien_ban": "D7-v1", "ngay": "2026-11-19", "trang_thai": "cho_duoc_si_duyet",
  "nguon_van_ban": {"so_hieu": "5631/QĐ-BYT", "ngay": "2020-12-31", "tep": "...", "ban_sao_thu_cap": true, "url": "..."},
  "ghi_chu": "...",
  "nhom": [ {"ma_nhom": "phe_duyet_truoc|uu_tien_quan_ly|...", "ten_nhom_van_ban": "<nguyên văn tên phụ lục>", "yeu_cau": "<nguyên văn yêu cầu với nhóm này>", "trang_pdf": 0} ],
  "khang_sinh": [ {"ten_trong_van_ban": "<nguyên văn>", "hoat_chat_ids": ["..."], "ma_nhom": "...", "trang_pdf": 0, "trang_thai": "cho_duoc_si_duyet"} ],
  "khong_anh_xa": [ {"ten_trong_van_ban": "...", "ly_do": "..."} ]
}
```

- Ánh xạ tên trong văn bản sang `hoat_chat_id` qua bộ phân giải (`app.kb.resolver`) hoặc trục; không ánh xạ được thì vào `khong_anh_xa`.
- Chữ trích lỗi do PDF: sửa chính tả hiển thị được, nhưng ghi trong `ghi_chu` cách đã sửa, và giữ `trang_pdf` để đối chiếu.
- Văn bản ghi điều kiện (ví dụ "sau hội chẩn", "phê duyệt của …") thì chép nguyên văn vào `yeu_cau`.

## Việc 3 – Kiểm bằng script (để ở scratchpad, không để trong kho)

- Mỗi `trich_nguyen_van` của nhãn FDA / LiverTox là chuỗi con của tệp nguồn sau khi gộp khoảng trắng.
- Mỗi `hoat_chat_id` có trên trục `tra_cuu.sqlite`.
- Đếm theo 66 ca: bao nhiêu ca có ≥ 2 thuốc `doc_than` cùng lúc (y lệnh chờ duyệt + thuốc đang dùng còn hiệu lực), ≥ 2 thuốc `keo_dai_qt`, có thuốc `khoang_dieu_tri_hep` mà thiếu xét nghiệm nồng độ, có kháng sinh nhóm `phe_duyet_truoc`.

## Việc 4 – Tài liệu, báo cáo

- `docs/du-lieu/doc-tinh-khang-sinh.md` theo mẫu `di-ung-cheo.md`; thêm dòng vào `docs/du-lieu/README.md` (tệp README đang được T65-T66 sửa song song: chỉ **thêm một dòng**, đọc lại tệp ngay trước khi ghi).
- Báo cáo `plan/reports/T70.md`: số dòng mỗi danh sách, kết quả việc 3, danh sách `khong_co_nguon`, `khong_anh_xa`.

## Cấm

- Sửa `app/`, `tests/`, `config/`, `web/`; dữ liệu ca; `chunks.jsonl`; `tra_cuu.sqlite`; sáu tệp D4/D5 trong `data/kb/`.
- Bịa trích dẫn, điểm LiverTox, nhóm kháng sinh.
- Commit; in khoá API; chạy `du` / `find` trong `data/kb_sources/ddinter_web`.
