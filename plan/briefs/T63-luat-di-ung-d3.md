# T63 – Luật yếu tố 1 (dị ứng) dùng bộ phân giải và bảng dị ứng chéo (plan 1.8 đợt D3, phần code)

Agent: agy `gemini-4-hydrogen-xhigh` (Codex hết quota tới 24/11). **Không gọi shell, không gọi mạng.** Chỉ ghi tệp; Claude chạy `uv`, `ruff`, `pytest` khi review.

Đọc trước:
- `AGENTS.md`
- `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md`: mục 2, **Đợt D3**
- `docs/du-lieu/di-ung-cheo.md`, `plan/reports/T60.md`: bảng `data/kb/di_ung_cheo.json` và kiểm kê dị ứng 66 ca
- `app/rules/allergy.py` (luật cũ)
- `app/rules/duplicate.py`, `app/rules/duplicate_config.py`: **mẫu đã duyệt** cho cách dùng `ctx.resolver`, nạp cấu hình, lùi về luật cũ, xử lý thiếu dữ liệu
- `app/rules/registry.py`, `app/rules/engine.py`: chỗ gọi `allergy.check(ca)`. **Bài học T57:** phải nối cả engine, nếu không đường chạy thật vẫn dùng luật cũ.
- `app/kb/resolver/resolver.py`

## Bối cảnh

Dữ liệu ca (theo kiểm kê T60):
- 5 ca có dị ứng: Penicillin ×3, Sulfonamid, "Sulfamethoxazol (sulfonamide)".
- 3 ca chưa khai thác dị ứng: DEMO-03, HS-012, HS-038.
- Còn lại đã hỏi, không dị ứng.
- Tên dị ứng thường là **tên nhóm**, nên `resolve_name` nhận 0/5. Bảng có khoá `ten_nhom_di_ung_sang_hoat_chat` để đổi tên nhóm ra hoạt chất.

Bảng `di_ung_cheo.json`:
- `nhom[]`: mỗi nhóm có `ma_nhom`, `ten_nhom`, `hoat_chat_ids`, `hoat_chat_lien_quan[]` (`hoat_chat_ids`, `muc_cheo`: `cao` / `thap` / `rat_thap`, `muc_canh_bao_nhan`, `ly_do`), `huong` (`mot_chieu` / `hai_chieu`), `co_so`, `nguon[]` (có `trich_nguyen_van`, `url`, `set_id` hoặc DOI), `trang_thai: cho_duoc_si_duyet`.
- Mọi khoá hoạt chất đều có trên trục `tra_cuu.sqlite`.

## Phạm vi

**Được tạo / sửa:**
- `app/rules/allergy.py`
- Mô-đun nạp bảng mới, ví dụ `app/rules/allergy_config.py`: đọc `data/kb/di_ung_cheo.json` qua lớp cấu hình, nạp một lần
- `app/rules/registry.py` (chỉ `AllergyRule`), `app/rules/engine.py` (chỉ lời gọi yếu tố 1)
- `app/kb/resolver/resolver.py`: **chỉ** sửa lỗi nêu ở yêu cầu 5
- Test mới hoặc sửa trong `tests/rules/`, `tests/kb/` (bộ phân giải). Test API chỉ đổi khi kỳ vọng đổi vì hành vi mới; liệt kê từng thay đổi trong báo cáo
- `plan/reports/T63.md`

**Cấm:**
- Sửa `data/**`
- Sửa luật khác
- Đổi hợp đồng API (`ma_luat` là chuỗi tự do, được thêm mã mới)
- Sửa `app/llm/**`, `app/orchestration/**`
- Commit

## Yêu cầu

1. **Đổi tác nhân dị ứng ra hoạt chất**, theo thứ tự:
   1. `hoat_chat_id` của bản ghi, qua bảng `chuyen_ma_ca` nếu là mã `HC-…`
   2. `resolve_name(tac_nhan)`
   3. Bỏ phần trong ngoặc rồi `resolve_name` lại
   4. `ten_nhom_di_ung_sang_hoat_chat` (khớp tên đã chuẩn hoá, không dấu, chữ thường)

   Không ra được hoạt chất nào thì xử lý như yêu cầu 4.
2. **Đối chiếu từng dòng chờ duyệt.** Lấy hoạt chất của dòng qua `ctx.resolver.resolve_line`.
   - **Trùng hoạt chất:** giữ `ma_luat="di_ung_trung_hoat_chat"`, `can_xem`, `nghiem_trong`. Ví dụ dị ứng "Augmentin" + y lệnh amoxicillin.
   - **Cùng nhóm hoặc dị ứng chéo theo bảng:** dùng `ma_luat="di_ung_cheo"`, `ket_luan="can_xem"`. Mức theo `muc_cheo`:
     - `cao` → `nghiem_trong`
     - `thap` → `can_luu_y`
     - `rat_thap` → `can_luu_y`, kèm câu "nguy cơ chéo rất thấp theo nguồn"

     Tôn trọng `huong`: `mot_chieu` chỉ áp dụng chiều từ `hoat_chat_ids` sang `hoat_chat_lien_quan`.
     - Mô tả mẫu: `Dị ứng Penicillin; y lệnh Ceftriaxon 1 g (ceftriaxone): nguy cơ dị ứng chéo thấp (penicillin ↔ cephalosporin R1 khác). Bảng chéo chờ dược sĩ duyệt.`
     - Căn cứ:
       - bản ghi dị ứng (`du_lieu`);
       - **mỗi nguồn** của dòng bảng thành một `CanCu(loai="tai_lieu")`, gồm câu trích nguyên văn, URL, `set_id` hoặc DOI;
       - câu "chờ dược sĩ duyệt".
     - Không bịa căn cứ ngoài bảng.
   - Một dòng khớp nhiều nhóm thì lấy mức cao nhất, gộp căn cứ, **một** phát hiện cho mỗi cặp (dị ứng, dòng).
3. **Giữ các nhánh cũ:**
   - `chua_co_thong_tin` → `khong_du_du_lieu` (`di_ung_thieu_thong_tin`)
   - `khong_di_ung_da_hoi` → `dat`
   - dị ứng thức ăn hoặc loại khác: không đối chiếu thuốc
4. **Bất biến an toàn:**
   - Dị ứng thuốc mà không phân giải được hoạt chất **và** không khớp tên nhóm → không được kết luận `dat` cho dòng đó.
     - Trả `khong_du_du_lieu`, ghi rõ: `Chưa nhận diện được hoạt chất của tác nhân dị ứng "<tên>"`.
   - Dòng y lệnh không phân giải được → `khong_du_du_lieu` cho cặp đó.
   - Dòng `khong_ap_dung` (dịch truyền, điện giải) → bỏ qua.
5. **Sửa bộ phân giải.** T60 phát hiện `resolve_name("Cephalexin")` và `resolve_name("Paracetamol")` trả `khong_nhan_dien` với lý do "tên ứng với nhiều công thức", trong khi "Cefalexin" thì ra bình thường.
   - Tìm nguyên nhân: tên khớp nhiều sản phẩm có cùng **một** hoạt chất nhưng khác hàm lượng hoặc dạng. Trường hợp đó phải trả hoạt chất đó (`da_phan_giai`).
   - Chỉ báo nhập nhằng khi các ứng viên ra **tập hoạt chất khác nhau**.
   - Thêm test cho hai tên này. Chạy lại để chắc số dòng ca phân giải không giảm: T53 ghi 117 / 47 / 3.
6. **Không có resolver hoặc thiếu bảng:** chạy luật cũ, không lỗi, có test.

## Nghiệm thu (Claude chạy)

- `uv run ruff check .`; `uv run ruff format --check` các tệp sửa; `uv run pytest -q -p no:cacheprovider`: 0 trượt.
- Test bắt buộc:
  - Augmentin ↔ amoxicillin ra `di_ung_trung_hoat_chat`.
  - Penicillin ↔ ceftriaxone ra `di_ung_cheo`, `can_luu_y`, có căn cứ nhãn FDA.
  - Penicillin ↔ cefadroxil (R1 giống) ra mức cao hơn.
  - Sulfonamid ↔ furosemide ra `rat_thap` hoặc không báo, theo bảng.
  - Chưa khai thác dị ứng ra `khong_du_du_lieu`.
  - Tên dị ứng lạ ra `khong_du_du_lieu`.
  - Thiếu resolver chạy luật cũ.
  - Hai tên Cephalexin / Paracetamol phân giải được.
- Báo cáo có bảng 66 ca: kết luận yếu tố 1 trước và sau, các `ma_luat`. Lấy bằng cách gọi luật qua registry trong test hoặc script trong test. Claude sẽ kiểm lại qua API.
