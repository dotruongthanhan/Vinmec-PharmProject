# T109 – Tool `tinh_chi_so` (chỉ chế độ ca)

Người làm: sub Claude Sonnet (medium). Làm **sau khi T108 đạt**.
Đọc trước: `AGENTS.md`, plan 1.9 mục 5.4 (C3), 5.7, **5.10**; `plan/briefs/T106-bao-cao.md`.

## 1. Bối cảnh

Gói ca (`chuan_bi_ngu_canh_ca`) đã có CrCl Cockcroft–Gault, eGFR CKD-EPI 2021, BMI, BSA Mosteller với giả định mặc định (`allowed_calc_ids`). Tool này chỉ để trả lời câu "nếu dùng cân nặng lý tưởng / hiệu chỉnh thì sao", "QTc theo Fridericia", "canxi hiệu chỉnh". **LLM không truyền số**: chỉ chọn công thức và giả định từ danh sách cố định; mọi đầu vào lấy từ `ctx.ca` (giá trị mới nhất, như cách gói ca đang lấy: tìm và dùng lại đúng hàm chọn đầu vào hiện có, không viết lại).

## 2. Thiết kế

- `che_do_cho_phep = {"ca"}`; chính sách cấm ở chế độ `chung`.
- Tham số (`extra="forbid"`): `cong_thuc`: `Literal["cockcroft_gault", "egfr_ckd_epi_2021", "bmi", "bsa_mosteller", "bsa_dubois", "ibw_devine", "adjusted_body_weight", "qtc_bazett", "qtc_fridericia", "qtc_framingham", "qtc_hodges", "calcium_corrected"]`; `can_nang`: `Literal["thuc_te", "ly_tuong", "hieu_chinh"]` mặc định `thuc_te` (chỉ có nghĩa với `cockcroft_gault`; công thức khác mà truyền khác `thuc_te` → `loi` `sai_tham_so`). Không có trường số nào.
- Gọi hàm trong `app/calc/` (đã có trích dẫn bài báo, kiểm biên). Thiếu đầu vào (không có QT, không có chiều cao…) → `trang_thai="khong_co"`, nêu thiếu gì, **không** đoán.
- Nội dung: kết quả, đơn vị, công thức, từng đầu vào đã dùng kèm mã bản ghi ca dạng tạm (dùng `RecordIdMap`/mã tạm mà gói ca đang dùng, không lộ mã thật), giả định cân nặng.
- Căn cứ: `CanCu(loai="tinh", ma="tinh:<cong_thuc>:<can_nang>", nhan=<tên công thức + giả định>, noi_dung=<kết quả và đầu vào>)`. Mở rộng `KiemChung`/`kiem_chung_tra_loi` để `loai="tinh"` đi cùng đường với `bang` (mã phải có trong lượt; số trong câu trả lời được phép nếu có trong `noi_dung`). Ra API: `loai_ma="tinh_toan"` nếu web (`web/src/features/assistant/AssistantPanel.tsx`) hiển thị được mà không cần `ban_ghi_id` khớp công thức mặc định; không thì `loai_ma="tai_lieu"` không bấm được. Không sửa web, không đổi hợp đồng; ghi lựa chọn vào báo cáo.
- Prompt: một câu khi nào gọi; nhắc không tự tính.

## 3. Tệp

Tạo: `app/agent/tools/tinh_chi_so.py`, `tests/agent/test_tool_tinh_chi_so.py`. Sửa: `app/container.py`, `config/tool_policy.yaml` (cấm ở `chung`), `config/prompts/tac_tu.v1.md`, `app/agent/nodes.py` (`KiemChung`), `app/orchestration/ask.py` (chỉ phần `kiem_chung_tra_loi` nhận thêm loại), `app/agent/tools/__init__.py`.
Cấm: `app/calc/` (không sửa công thức), `graph.py`, `web/`, `data/`, commit, push, cài gói.

## 4. Nghiệm thu

Test: CrCl `thuc_te` của tool bằng đúng số trong gói ca cho cùng ca; `ly_tuong` khác và bằng tay tính lại từ `app/calc`; ca thiếu chiều cao → `khong_co`; gọi ở chế độ `chung` → Gateway `khong_co_quyen`; tham số có trường số lạ → `sai_tham_so`; câu trả lời nêu số khác kết quả → bị chặn.

```
uv run ruff check app tests
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider
```

Báo cáo: `plan/briefs/T109-bao-cao.md`.
