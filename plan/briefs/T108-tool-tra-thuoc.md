# T108 – Tool `tra_thuoc` (định danh + quy định theo hoạt chất)

Người làm: sub Claude Sonnet (medium). Làm **sau khi T107 đạt**.
Đọc trước: `AGENTS.md`, plan 1.9 mục 4.4, 5.3 (B1, B6–B10), **5.10**; `plan/briefs/T106-bao-cao.md`, `T107-bao-cao.md`.

## 1. Bối cảnh

Plan cũ tách `tra_thuoc` và `tra_quy_dinh`. Duyệt 22/11 gộp làm một vì cả hai đã có sẵn trong `app/api/lookup.py`:
- `suggest_drugs` / `DrugSuggestIndex` (T105): tên tự do, biệt dược, sai chính tả → hoạt chất, có mức khớp `chinh_xac | tien_to | gan_dung`.
- `drug_detail(hoat_chat_id)`: định danh (INN, tên Việt, ATC, DDInter), chế phẩm Cục QLD, nhãn FDA, `quy_tac` = `_rules_for()` gom mọi bảng luật theo hoạt chất (`_RULE_SECTIONS`: liều thận, gan, ngưỡng xét nghiệm, thuốc–bệnh, đường dùng, liều tối đa, độc tính, kháng sinh quản lý, dị ứng chéo, nhóm trùng điều trị), mỗi dòng có `bang_luat`, `phan`, `trang_thai`, `du_lieu`.

## 2. Thiết kế

Tham số (`extra="forbid"`): `ten` str 1–120; `phan`: list 1–3 trong `dinh_danh | quy_tac | che_pham`, mặc định `["dinh_danh", "quy_tac"]`; `nhom_quy_tac`: list tuỳ chọn trong các `nhom` của `_RULE_SECTIONS` cộng `nhom_trung_dieu_tri` (bỏ `thuoc_benh`: đã thuộc `tra_tuong_tac`), dùng `Literal` để LLM thấy danh sách.

Phân giải:
- Khớp `chinh_xac` hoặc `tien_to` về đúng **một** tập hoạt chất → dùng.
- Nhiều tập, hoặc chỉ khớp `gan_dung` → `trang_thai="khong_co"`, nội dung liệt kê ≤ 5 ứng viên (nhãn + hoạt chất + mức khớp) và câu "cần hỏi lại dược sĩ thuốc nào", **không tự chọn**. Không có gì → "không tìm thấy trong danh mục".
- Biệt dược nhiều hoạt chất (ví dụ amoxicillin + acid clavulanic): trả cho từng hoạt chất, tối đa 3.

Nội dung:
- `dinh_danh`: một dòng mỗi hoạt chất, có mức khớp phân giải.
- `quy_tac`: mỗi dòng bảng luật một dòng, mở đầu `[bang:<bang_luat>:<khoa>]`, tóm tắt các trường số và điều kiện của `du_lieu` (không đổ nguyên JSON), **luôn ghi `trang_thai`** (ví dụ "chờ dược sĩ duyệt") và nguồn/URL nếu dòng có. Khoá ổn định (dùng định danh dòng nếu có, không thì `<hoat_chat>:<phan>:<chỉ số>`).
- `che_pham`: ≤ 5 chế phẩm đầu (tên, số đăng ký, hàm lượng), ghi tổng số.
- Trần 25 dòng bảng; vượt thì ghi "còn N dòng".
- `CanCu(loai="bang", ma, nhan, noi_dung)` cho mỗi dòng quy tắc và dòng định danh (đường kiểm chứng `bang` đã có từ T106).
- `chi_tiet_tien_trinh`: "1 hoạt chất, 6 quy tắc" hoặc "3 ứng viên, cần hỏi lại". Không có tên thuốc.

Không gọi `drug_detail` nguyên khối nếu nó chạy truy vấn nhãn FDA và chế phẩm không cần: tách hàm nhỏ hoặc gọi riêng `_catalog`, `_rules_for`, `_products` theo `phan`. Không sửa hành vi các điểm cuối `/api/thuoc*` (test `tests/api/test_tra_cuu.py` phải giữ nguyên kết quả).

Prompt `tac_tu.v1.md`: một câu khi nào gọi (hỏi thuốc là gì, ngưỡng liều/thận/gan, đường dùng, kháng sinh cần duyệt, dị ứng chéo) và nhắc: ngưỡng tool trả **không phải** kết luận cho ca; so với ca đã có ở phát hiện của bộ luật.

## 3. Tệp

Tạo: `app/agent/tools/tra_thuoc.py`, `tests/agent/test_tool_tra_thuoc.py`. Sửa: `app/container.py`, `config/tool_policy.yaml`, `config/prompts/tac_tu.v1.md`, `app/agent/tools/__init__.py`, `app/api/lookup.py` (chỉ tách hàm công khai, không đổi hành vi).
Cấm: như T106.

## 4. Bảo mật và nghiệm thu

Như T106 (tham số lạ, PII tham số, quyền, không f-string SQL). Test: biệt dược có thật trong `tra_cuu_thuoc` → đúng hoạt chất; tên sai chính tả chỉ khớp gần đúng → `khong_co` kèm ứng viên; hoạt chất có quy tắc thận chờ duyệt → dòng ghi trạng thái; số trong câu trả lời không có trong dòng → `kiem_chung_tra_loi` chặn.

```
uv run ruff check app tests
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider
```

Báo cáo: `plan/briefs/T108-bao-cao.md`.
