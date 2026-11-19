# T77 – Bảng luật D1–D7 thành bảng quan hệ trong `tri_thuc` (plan 1.8 mục 4.2); app đọc từ DB

Agent: **agy Gemini 4 Hydrogen xhigh**. **KHÔNG gọi công cụ shell, không gọi mạng; chỉ đọc và ghi tệp.** Chạy **sau T76**; đọc `plan/reports/T75.md`, `T76.md`, plan 1.8 mục 4.1–4.2 trước.

## Bối cảnh

Người dùng chốt (19/11): production chỉ có code + `DATABASE_URL`; **mọi dữ liệu truy vấn trong Postgres**. Bảng luật đang là tệp:

| Tệp | Danh sách quy tắc (mỗi phần tử → một dòng) | Hàm nạp |
|:--|:--|:--|
| `data/kb/quy_tac_lieu_than.json` | `quy_tac`, `quy_tac_cho_duyet`, `khong_co_nguong` | `renal_dose.load_renal_rules` |
| `data/kb/quy_tac_gan.json` | `quy_tac` | `d4_config.load_hepatic_config` |
| `data/kb/nguong_xet_nghiem.json` | `quy_tac` | `d4_config.load_lab_threshold_config` |
| `data/kb/thuoc_benh_icd.json` | `cap_thuoc_benh`, `anh_xa`, `cap_khop_chan_doan_ca` | `d4_config.load_drug_disease_config` |
| `data/kb/duong_dung_hop_le.json` | `nhom`, `bang_chuan_hoa_duong_dung` | `d5_config.load_route_config` |
| `data/kb/lieu_toi_da.json` | `nhom`, `khong_ghi_toi_da`, `khong_ghi_toi_da_theo_duong_trong_ca`, `doi_tuong_dinh_nghia` | `d5_config.load_max_dose_config` |
| `data/kb/doc_tinh.json` | `doc_than`, `keo_dai_qt`, `khoang_dieu_tri_hep`, `doc_gan_livertox`, `khong_co_nguon` | `d6_config.load_toxicity_config` |
| `data/kb/khang_sinh_quan_ly.json` | `khang_sinh`, `nhom`, `khong_anh_xa`, `nguon_van_ban` | `d7_config.load_stewardship_config` |
| `data/kb/di_ung_cheo.json` | `nhom`, `ten_nhom_di_ung_sang_hoat_chat` | `allergy_config.load_allergy_config` |
| `data/kb/hoat_chat.json` | `hoat_chat`, `nhan` | `app/kb/names.py::DrugNameIndex.load` |
| `config/kb/nhom_dieu_tri_trung.yaml`, `atc_bo_sung.yaml` | `nhom`, `ma_atc` | `duplicate_config.load_duplicate_config` |

(Danh sách khoá trên do Claude liệt kê; đọc tệp thật để lấy đủ.)

## Yêu cầu

### 1. Lược đồ `db/schema.sql` – bảng quan hệ, mỗi quy tắc một dòng

- Một bảng cho mỗi danh sách quy tắc, đặt tên theo plan 1.8 mục 4.2 khi khớp: `tri_thuc.quy_tac_lieu_than_v2` (tránh đụng bảng cũ `quy_tac_lieu_than`; hoặc đổi tên bảng cũ nếu không còn ai dùng – ghi rõ quyết định), `quy_tac_gan`, `nguong_xet_nghiem`, `tuong_tac_benh` (`cap_thuoc_benh`) + `anh_xa_benh_icd`, `duong_dung_hop_le`, `lieu_toi_da` + `doi_tuong_dinh_nghia`, `canh_bao_doc_tinh` (cột `loai` ∈ `doc_than`, `keo_dai_qt`, `khoang_dieu_tri_hep`, `doc_gan_livertox`, `khong_co_nguon`), `khang_sinh_han_che`, `nhom_di_ung_cheo`, `nhom_dieu_tri_trung`, …
- **Cột:** khoá dòng (`id` hoặc khoá tự nhiên), các trường vô hướng thường tra cứu (`hoat_chat_id`, `duong_dung`, `xet_nghiem`, `muc_do`, `trang_thai`, …) thành cột riêng có chỉ mục `hoat_chat_id`; các trường lồng (`dieu_kien`, `trich`, `nguon`, khoảng liều…) để `jsonb`; thêm `thu_tu integer` giữ thứ tự trong tệp, `phien_ban`.
- Bảng `tri_thuc.bang_luat_meta (ma text PRIMARY KEY, phien_ban, ngay, trang_thai, phan_khac jsonb, sha256_tep)` giữ các khoá không phải danh sách quy tắc (`ghi_chu`, `huong_giai_thich`, `thong_ke`, `tinh_huong_kiem`, …) để **dựng lại được nguyên tài liệu**.
- RLS + REVOKE theo khối điều kiện vai trò (mẫu T74–T75). Cập nhật các test đếm bảng / khối `DO`.

### 2. Nạp – `python -m app.db.cli load bang-luat`

Đọc từng tệp, **kiểm bằng mô hình pydantic của hàm nạp** trước khi ghi, tách thành dòng, `TRUNCATE` + chèn trong một giao dịch. Sau khi chèn, **dựng lại tài liệu từ DB và so bằng (`==`) với dict đọc từ tệp**; khác → rollback, thoát ≠ 0. In số dòng mỗi bảng.

### 3. Đọc khi chạy

Hàm chung `app/db/bang_luat.py::load_document(conn, ma) -> dict` dựng lại tài liệu (đúng thứ tự `thu_tu`). Mỗi hàm nạp ở bảng trên nhận nguồn DB theo `app.kb_source` của T75 (`auto` / `file` / `db`), nạp một lần mỗi tiến trình, lỗi DB → luật đó báo thiếu dữ liệu như khi thiếu tệp + một cảnh báo log, không sập app. Không đổi logic luật.

### 4. Test

Với **mỗi tệp thật trong kho**: tách dòng → dựng lại == tệp gốc (round-trip, không cần PostgreSQL). Bộ nạp từ DB giả cho cùng đối tượng cấu hình với đọc tệp. CLI từ chối tệp hỏng.

## Phạm vi

Sửa: `db/schema.sql`, `app/db/cli.py`, tạo `app/db/bang_luat.py`, `app/rules/*_config.py`, `app/rules/renal_dose.py`, `app/kb/names.py` (chỉ hàm nạp), `app/container.py`, `app/api/main.py`, `app/api/service.py`, `app/orchestration/ask.py`, `app/ui/streamlit_app.py` (chỉ chỗ gọi hàm nạp), test schema/mapping; tạo test, `plan/reports/T77.md`. Cấm: `data/`, `config/`, `web/`, logic luật.

## Nghiệm thu (Claude chạy)

`ruff`, `pytest` 0 trượt. Xoá và dựng lại DB RDS, nạp đủ; **ẩn `data/kb/`, `data/kb_curated/`, `data/cache/`, `config/kb/`**: 66 ca ra đúng các nhận định như khi đọc tệp.

## Bổ sung (Claude)

`ruff format --check` còn báo 4 tệp lệch sau T76-fix-1: định dạng lại (chỉ khoảng trắng).
