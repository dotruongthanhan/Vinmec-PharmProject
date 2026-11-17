# T25-fix-1 – Lệnh tải openFDA báo "không tìm thấy" cho nhãn có thật

**Giao cho:** agy CLI (`gemini-4-hydrogen-xhigh`) · **Ngày:** 17/11/2026
**Đọc trước:** `AGENTS.md`; `plan/briefs/T25-lay-nhan-openfda-qua-api.md`; `data/kb_sources/openfda_api.md`; `app/kb/fetch/**`; `config/kb/hoat_chat_can_lay.yaml`; `tests/kb/**`; các tệp mẫu thật ở `data/kb_sources/openfda_api_mau/`.

**Bạn không chạy lệnh, không gọi mạng, không gọi công cụ shell** (gọi là cả phiên ra rỗng). Người review chạy lệnh tải thật sau khi bạn xong.

## 1. Kết quả review (người review đã chạy trên máy có mạng)

- Lint, định dạng: sạch. `python -m app.kb.build`: `labels=50/50 chunks=3738 over_max=0 under_50=0 empty_act=0`, 0 mã đoạn đổi.
- `python -m app.kb.fetch ndc`: lấy được 46, **"không tìm thấy" 4** (trong đó có `warfarin`, `valproate`).
- `python -m app.kb.fetch openfda`: bỏ qua 42, **"không tìm thấy" 8**: đúng 8 hoạt chất cần đổi đường dùng (ví dụ `levofloxacin` đường `INTRAVENOUS`). Tệp trên đĩa của `levofloxacin`, `ciprofloxacin` vẫn là nhãn uống.
- Đối chứng bằng lệnh gọi trực tiếp:
  - `openfda.generic_name.exact:"LEVOFLOXACIN" AND openfda.product_type:"HUMAN PRESCRIPTION DRUG" AND openfda.route:"INTRAVENOUS"` → **10 nhãn**.
  - `openfda.generic_name:"levofloxacin" AND … AND openfda.route:"INTRAVENOUS"` → **11 nhãn**.
  - `drug/ndc.json?search=generic_name:"warfarin"` → **153 sản phẩm**.
- Câu truy vấn lệnh đang dựng: `openfda.generic_name.exact:"levofloxacin" AND openfda.product_type.exact:"HUMAN PRESCRIPTION DRUG" AND openfda.route.exact:"INTRAVENOUS"`.

## 2. Nguyên nhân cần xử lý

1. Trường `.exact` **phân biệt hoa thường** và khớp cả chuỗi; giá trị trong dữ liệu viết hoa (`LEVOFLOXACIN`), còn cấu hình viết thường. Tên chung của nhãn tiêm còn có thể là dạng dài hơn (ví dụ có thêm dung môi), nên khớp cả chuỗi dễ trượt.
2. Cấu hình ghi tên muối (`warfarin sodium`, `valproate sodium`) trong khi tên chung trong NDC có thể khác cách viết.

## 3. Việc phải làm

- **Chiến lược truy vấn nhiều bậc, dừng ở bậc đầu tiên có ứng viên qua được quy tắc chọn:** (1) `openfda.generic_name.exact` với tên viết hoa; (2) `openfda.substance_name.exact` với tên viết hoa; (3) `openfda.generic_name:"<tên>"` không `.exact`; (4) như bậc 3 với tên đã bỏ phần muối. Điều kiện loại sản phẩm và đường dùng dùng dạng không `.exact`. Ghi vào manifest bậc nào đã cho kết quả và câu truy vấn đã dùng.
- Quy tắc chọn nhãn giữ như T25 mục 2.2 (đơn chất, đúng đường dùng, nhiều mục nhất, mới nhất, `set_id`). Vì bậc 3–4 khớp lỏng hơn, bước lọc đơn chất và so hoạt chất sau khi bỏ muối là bắt buộc; thêm test cho ứng viên là dạng phối hợp bị loại ở bậc lỏng.
- NDC: áp dụng cùng chiến lược nhiều bậc với trường `generic_name` và `active_ingredients.name`.
- Phân biệt rõ ba kết cục trong báo cáo và mã thoát: `khong_tim_thay` (API trả 404 ở mọi bậc), `khong_co_ung_vien_hop_le` (có kết quả nhưng không nhãn nào qua quy tắc chọn; ghi lý do loại của 3 ứng viên đầu), `loi_ket_noi`.
- Khi tìm được nhãn đúng đường dùng cho hoạt chất đang có nhãn sai đường dùng: thay tệp theo quy tắc đặt tên của T25, cập nhật manifest; mã đoạn của nhãn bị thay sẽ đổi, điều đó được phép và phải được đếm trong báo cáo dựng kho.
- Test **không được** tạo thư mục tạm bên trong kho (`tests/kb/.tmp/` đang bị khoá quyền và làm 24 test báo lỗi khi dọn dẹp). Dùng `tmp_path` mặc định của pytest; bỏ mọi cấu hình `basetemp` trỏ vào kho.
- Test mới dùng phản hồi mẫu thật có sẵn (`mero_label_rx_iv.json`, `mero_ndc.json`, `err_404.json`) và phản hồi dựng tay tối thiểu cho trường hợp tên viết hoa, tên dài hơn, dạng phối hợp.

## 4. Phạm vi file

`app/kb/fetch/**`, `tests/kb/**`, `config/kb/hoat_chat_can_lay.yaml` (chỉ sửa cách ghi tên nếu cần, không thêm hoạt chất), `data/kb_sources/README.md` (cách tải lại). **Cấm đụng:** `web/`, `app/api/`, `app/orchestration/`, `app/db/`, `db/`, `plan/`, `pyproject.toml`, các tệp JSON trong `data/kb_sources/`.

## 5. Nghiệm thu (người review chạy)

```bash
uv run ruff check app/kb tests/kb --exclude tests/kb/.tmp
uv run ruff format --check app/kb tests/kb --exclude tests/kb/.tmp
uv run pytest -q tests/kb -p no:cacheprovider --ignore=tests/kb/.tmp
uv run python -m app.kb.fetch openfda
uv run python -m app.kb.fetch ndc
uv run python -m app.kb.fetch report
uv run python -m app.kb.build
```

Đích: 8 hoạt chất cần đổi đường dùng có nhãn đúng đường dùng (hoặc có lý do loại cụ thể); NDC đủ 50 hoặc có lý do cụ thể; `pytest` không còn lỗi do thư mục tạm; dòng dựng kho còn `over_max=0 under_50=0 empty_act=0`.

## 6. Cấm làm

Không sửa nội dung nhãn. Không thêm thư viện. Không commit, không push. Trả lời theo mẫu trong `AGENTS.md`, ghi rõ chưa chạy lệnh nào.
