# T03 – Bộ luật v0 (dị ứng, trùng hoạt chất, kháng sinh – vi sinh, chỉnh liều theo thận, lịch dùng)

**Giao cho:** agy CLI (`gemini-4-hydrogen-xhigh`) · **Ngày:** 16/11/2026
**Đọc trước:** `AGENTS.md` (bắt buộc); `app/domain/models.py`, `app/domain/loader.py`, `app/calc/renal.py`, `app/calc/types.py` (đã có, **chỉ đọc**); 6 ca ở `data/mock/demo/` và đáp án ở `data/gold/demo/`.

## 1. Mục tiêu

Bước B4: các luật chạy hoàn toàn bằng code, không có LLM. Mỗi luật nhận một `CaBenh` và trả danh sách phát hiện có căn cứ. Phát hiện của luật là lớp an toàn chính của hệ thống: về sau LLM không được xoá hay hạ mức chúng.

## 2. Phạm vi file được tạo hoặc sửa

```text
app/rules/__init__.py
app/rules/types.py
app/rules/allergy.py
app/rules/duplicate.py
app/rules/antibiotic.py
app/rules/renal_dose.py
app/rules/schedule.py
app/rules/engine.py
app/rules/__main__.py
data/kb/quy_tac_lieu_than.json
tests/rules/__init__.py
tests/rules/test_allergy.py
tests/rules/test_duplicate.py
tests/rules/test_antibiotic.py
tests/rules/test_renal_dose.py
tests/rules/test_schedule.py
tests/rules/test_engine_demo.py
pyproject.toml        (chỉ thêm đúng 1 dòng, xem mục 9)
```

Không sửa `app/domain/`, `app/calc/`, `data/mock/`, `data/gold/`. Nếu thấy mô hình hoặc ca demo có lỗi khiến luật không viết được, **dừng và ghi vào báo cáo**, không tự sửa.

## 3. Kiểu dữ liệu – `app/rules/types.py`

```python
class CanCu(BaseModel):
    loai: Literal["du_lieu", "tinh_toan", "tai_lieu"]
    ban_ghi_id: str | None = None   # ví dụ "XN-0142"; với tinh_toan là mã công thức
    mo_ta: str                      # câu ngắn, có giá trị và thời điểm nếu có

class PhatHien(BaseModel):
    ma_luat: str                    # xem từng luật
    yeu_to: int                     # 1–7
    ket_luan: Literal["dat", "can_xem", "khong_du_du_lieu", "ngoai_hdsd"]
    muc_do: Literal["nghiem_trong", "can_luu_y", "thong_tin"] | None
    chi_tiet_y_lenh_id: list[str]
    mo_ta: str
    can_cu: list[CanCu]
    thong_tin_con_thieu: list[str] = []
```

Quy tắc chung:

- "Dòng đang xét" = các dòng trong `ca.y_lenh_cho_duyet.chi_tiet`.
- "Dòng đang hiệu lực" = dòng đang xét + các dòng trong `ca.thuoc_dang_dung` có `trang_thai_dong` là `active` hoặc `pending`.
- Hoạt chất của một dòng lấy bằng `ingredients_of` trong `app/domain/loader.py`.
- So sánh chuỗi (`nhom_duoc_ly`) không phân biệt hoa thường, bỏ khoảng trắng hai đầu.
- Luật là hàm thuần `check(ca: CaBenh, ...) -> list[PhatHien]`; không đọc file, không in.
- `ket_luan="khong_du_du_lieu"` luôn có `muc_do=None` và `thong_tin_con_thieu` không rỗng.

## 4. Các luật

### 4.1. Dị ứng – `allergy.py`, yếu tố 1

| Tình huống | Kết quả |
| :--- | :--- |
| `tinh_trang_di_ung.trang_thai == "chua_co_thong_tin"` | 1 phát hiện: `ma_luat="di_ung_thieu_thong_tin"`, `khong_du_du_lieu`, gắn mọi dòng đang xét, `thong_tin_con_thieu=["tinh_trang_di_ung"]` |
| `"khong_di_ung_da_hoi"` | 1 phát hiện: `ma_luat="di_ung_khong_co"`, `dat`, `thong_tin`, gắn mọi dòng đang xét |
| `"co_di_ung"`, dòng có hoạt chất trùng `hoat_chat_id` với một dị ứng `loai_tac_nhan="thuoc"` | Mỗi cặp (dòng, dị ứng) 1 phát hiện: `ma_luat="di_ung_trung_hoat_chat"`, `can_xem`, `nghiem_trong` |
| `"co_di_ung"`, không trùng hoạt chất nhưng `nhom_duoc_ly` của hoạt chất trong dòng bằng `nhom_duoc_ly` của dị ứng (cả hai không rỗng) | Mỗi cặp 1 phát hiện: `ma_luat="di_ung_cung_nhom"`, `can_xem`, `nghiem_trong` |
| `"co_di_ung"`, không dòng nào khớp | 1 phát hiện: `ma_luat="di_ung_khong_khop"`, `dat`, `thong_tin` |

Một cặp (dòng, dị ứng) chỉ sinh một phát hiện: trùng hoạt chất được ưu tiên hơn cùng nhóm. `can_cu` có một mục `du_lieu` trỏ `di_ung_id` và nêu tác nhân, phản ứng. Dòng không có `thuoc_id` (sản phẩm gõ tay) không khớp được: nếu trạng thái là `co_di_ung` và có dòng như vậy, thêm 1 phát hiện `ma_luat="di_ung_san_pham_khong_ro"`, `khong_du_du_lieu`, `thong_tin_con_thieu=["thanh_phan_san_pham"]` cho dòng đó.

### 4.2. Trùng hoạt chất – `duplicate.py`, yếu tố 2

Trong các dòng đang hiệu lực: nếu cùng một `hoat_chat_id` có mặt ở từ 2 dòng khác nhau trở lên, và ít nhất một trong số đó là dòng đang xét → 1 phát hiện cho mỗi hoạt chất: `ma_luat="trung_hoat_chat"`, `can_xem`, `can_luu_y`, `chi_tiet_y_lenh_id` gồm mọi dòng liên quan. Không có trùng → 1 phát hiện `ma_luat="trung_hoat_chat_khong_co"`, `dat`, `thong_tin`.

### 4.3. Kháng sinh và vi sinh – `antibiotic.py`, yếu tố 3

Chỉ xét dòng đang xét có thuốc với `la_khang_sinh == True`. Lấy các bản ghi `ViSinh` có `vi_khuan` khác `None`.

| Tình huống | Kết quả |
| :--- | :--- |
| Không có bản ghi vi sinh dương tính nào | **Không sinh phát hiện** (để bước sau xử lý) |
| Có kháng sinh đồ cho hoạt chất của dòng, kết quả `S` | `ma_luat="khang_sinh_vi_sinh_nhay"`, `dat`, `thong_tin` |
| Kết quả `R` | `ma_luat="khang_sinh_vi_sinh_khang"`, `can_xem`, `nghiem_trong` |
| Kết quả `I` | `ma_luat="khang_sinh_vi_sinh_trung_gian"`, `can_xem`, `can_luu_y` |
| Có vi sinh dương tính nhưng kháng sinh đồ không có hoạt chất của dòng | `ma_luat="khang_sinh_khong_co_ksd"`, `khong_du_du_lieu`, `thong_tin_con_thieu=["khang_sinh_do"]` |

Nếu nhiều bản ghi vi sinh cho cùng hoạt chất: lấy bản có `thoi_diem_lay_mau` mới nhất. `can_cu`: một mục `du_lieu` trỏ `vi_sinh_id`, nêu bệnh phẩm, vi khuẩn, kết quả S/I/R.

### 4.4. Chỉnh liều theo thận – `renal_dose.py`, yếu tố 6

**Bảng luật** nằm ở `data/kb/quy_tac_lieu_than.json`. Tạo file với đúng nội dung sau, không thêm hoạt chất nào khác:

```json
{
  "phien_ban": "0.1",
  "ghi_chu": "Ban MVP. Chua duoc duoc si duyet.",
  "quy_tac": [
    {
      "ten_quoc_te": "meropenem",
      "nguon": "Nhan thuoc FDA: MERREM IV (meropenem for injection), muc Dosage and Administration - Use in Adult Patients with Renal Impairment",
      "nguoi_duyet": null,
      "muc": [
        {"crcl_tu": 50, "crcl_den": null, "bao_gom_can_duoi": false, "can_chinh": false, "khuyen_cao": "Lieu khuyen cao, moi 8 gio"},
        {"crcl_tu": 26, "crcl_den": 50, "bao_gom_can_duoi": true, "can_chinh": true, "khuyen_cao": "Lieu khuyen cao, moi 12 gio"},
        {"crcl_tu": 10, "crcl_den": 25, "bao_gom_can_duoi": true, "can_chinh": true, "khuyen_cao": "Mot nua lieu khuyen cao, moi 12 gio"},
        {"crcl_tu": null, "crcl_den": 10, "bao_gom_can_duoi": false, "can_chinh": true, "khuyen_cao": "Mot nua lieu khuyen cao, moi 24 gio"}
      ]
    }
  ]
}
```

Cách chọn mức theo CrCl (mL/min), để không có khe hở giữa các mức: `CrCl > 50` → mức 1; `25 < CrCl ≤ 50` → mức 2; `10 ≤ CrCl ≤ 25` → mức 3; `CrCl < 10` → mức 4. Viết hàm chọn mức theo đúng bốn điều kiện này và có test ở các biên 50, 50.01, 25, 25.01, 10, 9.99.

Định nghĩa mô hình pydantic cho file này trong `renal_dose.py` cùng hàm `load_renal_rules(path: Path)`. Hàm luật: `check(ca, rules) -> list[PhatHien]`.

Với mỗi dòng đang xét có hoạt chất mà `HoatChat.ten_quoc_te` (không phân biệt hoa thường) khớp một `ten_quoc_te` trong bảng:

1. Lấy `tuoi`, `gioi_tinh` từ `ca.nguoi_benh`; cân nặng = `latest_vital(ca, "can_nang")`; creatinin = `latest_lab(ca, "creatinin")` (dùng `gia_tri_so` và `don_vi`).
2. Gọi `cockcroft_gault(..., loai_can_nang="thuc_te")`.
3. Nếu `ket_qua is None` → phát hiện `ma_luat="lieu_than_thieu_du_lieu"`, `khong_du_du_lieu`, `thong_tin_con_thieu` = `thieu_dau_vao` của kết quả tính.
4. Nếu `cockcroft_gault` ném `ValueError` → phát hiện `ma_luat="lieu_than_so_lieu_bat_thuong"`, `khong_du_du_lieu`, `thong_tin_con_thieu=["so_lieu_hop_le"]`, `mo_ta` chứa thông báo lỗi.
5. Chọn mức. `can_chinh == true` → `ma_luat="lieu_than_can_chinh"`, `can_xem`, `nghiem_trong`. `can_chinh == false` → `ma_luat="lieu_than_khong_can_chinh"`, `dat`, `thong_tin`.
6. `mo_ta` của trường hợp cần chỉnh phải chứa: giá trị CrCl làm tròn 1 chữ số thập phân, và câu `khuyen_cao` của mức.
7. `can_cu` gồm đủ 3 mục theo thứ tự: `du_lieu` (trỏ `xet_nghiem_id` của creatinin, nêu giá trị, đơn vị, thời điểm) → `tinh_toan` (`ban_ghi_id="cockcroft_gault"`, nêu kết quả và loại cân nặng) → `tai_lieu` (`mo_ta` = trường `nguon` của bảng luật).

Dòng có hoạt chất không nằm trong bảng: không sinh phát hiện.

### 4.5. Lịch dùng – `schedule.py`, yếu tố 7

Chỉ xét dòng đang xét.

| Tình huống | Kết quả |
| :--- | :--- |
| `lich_dung` rỗng, hoặc chỉ có 1 mốc | Không sinh phát hiện |
| Có `khoang_cach_gio` và tồn tại hai mốc liên tiếp (sắp theo thời gian) cách nhau hơn `1.5 × khoang_cach_gio` | `ma_luat="lich_dung_thieu_lieu"`, `can_xem`, `can_luu_y` |
| Có `so_lan_moi_ngay`, mốc cuối cách mốc đầu ít nhất 24 giờ, và số mốc trong khoảng `[mốc đầu, mốc đầu + 24 giờ)` nhỏ hơn `so_lan_moi_ngay` | Cùng phát hiện trên |
| Còn lại | `ma_luat="lich_dung_phu_hop"`, `dat`, `thong_tin` |

Mỗi dòng tối đa một phát hiện (hai điều kiện "thiếu liều" cùng đúng vẫn chỉ ra một). `mo_ta` nêu tần suất kê và khoảng cách thực tế lớn nhất tính bằng giờ.

## 5. Bộ chạy – `engine.py` và `__main__.py`

- `run_rules(ca: CaBenh, renal_rules) -> list[PhatHien]`: gọi 5 luật theo thứ tự 4.1 → 4.5, gộp kết quả, rồi sắp ổn định theo: `can_xem` + `nghiem_trong` → `can_xem` + `can_luu_y` → `khong_du_du_lieu` → `ngoai_hdsd` → `dat`.
- Một luật ném ngoại lệ không lường trước thì **không được làm mất kết quả các luật khác**: bắt ngoại lệ, thêm phát hiện `ma_luat="loi_luat"`, `khong_du_du_lieu`, `yeu_to` của luật đó, `thong_tin_con_thieu=["luat_chay_loi"]`, `mo_ta` nêu tên luật và loại ngoại lệ.
- `python -m app.rules <đường dẫn file ca JSON>`: in ra JSON (UTF-8, `ensure_ascii=False`, thụt 2) danh sách phát hiện. Đường dẫn bảng luật thận mặc định là `data/kb/quy_tac_lieu_than.json`, đổi được bằng `--renal-rules`. Phải ghi ra stdout bằng UTF-8 kể cả trên Windows (dùng `sys.stdout.reconfigure(encoding="utf-8")`).

## 6. Kiểm thử trên 6 ca demo – `test_engine_demo.py`

Gọi "tập vấn đề" của một ca = tập các cặp `(yeu_to, ket_luan)` của những phát hiện có `ket_luan != "dat"`.

| Ca | Tập vấn đề phải bằng đúng | Yêu cầu thêm |
| :-: | :--- | :--- |
| DEMO-01 | rỗng | |
| DEMO-02 | `{(6, "can_xem")}` | phát hiện đó `nghiem_trong`, `ma_luat="lieu_than_can_chinh"`, `mo_ta` chứa `"16.0"`, có đủ 3 căn cứ đúng thứ tự, căn cứ `du_lieu` trỏ đúng `xet_nghiem_id` của kết quả creatinin 212 (không phải kết quả cũ 150) |
| DEMO-03 | `{(1, "khong_du_du_lieu")}` | |
| DEMO-04 | rỗng | có một phát hiện `dat` với `ma_luat="khang_sinh_vi_sinh_nhay"` |
| DEMO-05 | `{(7, "can_xem")}` | `ma_luat="lich_dung_thieu_lieu"` |
| DEMO-06 | `{(1, "can_xem")}` | `nghiem_trong`, `ma_luat="di_ung_cung_nhom"` |

Thêm một test so với đáp án: với mỗi ca, tập vấn đề do luật sinh ra bằng tập `(yeu_to, ket_luan)` của các mục có `ket_luan != "dat"` trong `data/gold/demo/<ca>.json`.

Nếu một ca demo không cho ra đúng kết quả trên vì dữ liệu ca thiếu hoặc sai (ví dụ thiếu `ten_quoc_te`), **không sửa dữ liệu, không nới luật**: để test đó trượt và ghi rõ nguyên nhân trong báo cáo.

## 7. Kiểm thử từng luật

Tự dựng `CaBenh` nhỏ trong test (viết một hàm trợ giúp tạo ca tối thiểu trong `tests/rules/__init__.py` hoặc `conftest.py` đặt trong `tests/rules/`; nếu dùng `conftest.py` thì đó là file được phép tạo thêm). Mỗi dòng trong các bảng ở mục 4 phải có ít nhất một test. Bắt buộc có thêm:

- Dị ứng: trùng hoạt chất được ưu tiên hơn cùng nhóm (một cặp chỉ một phát hiện).
- Trùng hoạt chất: thuốc đang dùng đã `discontinued` không bị tính.
- Liều thận: thiếu cân nặng → `khong_du_du_lieu` với `can_nang_kg` trong `thong_tin_con_thieu`; creatinin `212` đơn vị `mg/dL` → `lieu_than_so_lieu_bat_thuong`.
- Lịch dùng: 3 lần/ngày với mốc 06:00, 14:00, 22:00 → `dat`.
- Bộ chạy: giả lập một luật ném `RuntimeError` (dùng `monkeypatch`) → vẫn có phát hiện của các luật khác và có một `loi_luat`.

## 8. Nghiệm thu

Người review sẽ chạy (bạn không cần chạy lệnh shell):

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python -m app.rules data/mock/demo/DEMO-02.json
```

## 9. Sửa `pyproject.toml`

Trong mục `[tool.ruff]`, thêm đúng một dòng ngay dưới `line-length = 100`:

```toml
extend-exclude = ["plan", "docs"]
```

Không sửa gì khác trong file này.

## 9b. Một sửa định dạng được phép trong `app/domain/models.py`

`ruff format` đang báo đúng một chỗ: câu `raise ValueError(...)` trong vòng `for du in self.di_ung` bị ngắt thành 3 dòng. Gộp lại thành một dòng:

```python
                raise ValueError(f"Thiếu hoat_chat_id '{du.hoat_chat_id}' trong danh_muc_hoat_chat")
```

Đây là thay đổi duy nhất được phép trong `app/domain/`.

## 10. Cấm làm

- Không thêm hoạt chất, ngưỡng, liều vào bảng luật ngoài nội dung mục 4.4.
- Không gọi LLM, không gọi mạng.
- Không so liều kê với liều khuyến cáo (để task sau).
- Không sửa ca demo, đáp án, mô hình, công thức.
- Không commit.
