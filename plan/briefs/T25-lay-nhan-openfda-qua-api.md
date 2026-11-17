# T25 – Lệnh lấy nhãn openFDA qua API, dùng lại được, kèm báo cáo độ phủ

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort xhigh) · **Ngày:** 17/11/2026
**Đọc trước (bắt buộc):** `AGENTS.md`; `data/kb_sources/README.md`; `data/kb_sources/manifest.json`; `plan/plan-1.3-du-lieu-thu-thap-tong-hop-tien-xu-ly.md`; `app/kb/sources/openfda.py`, `app/kb/build.py`; `data/kb/hoat_chat.json`; tài liệu API tại `https://open.fda.gov/apis/drug/label/` và `https://open.fda.gov/apis/drug/ndc/`.

## 1. Bối cảnh

50 nhãn trong `data/kb_sources/openfda/` được tải tay một lượt ngày 16/11, không có lệnh để tải lại. Người dùng đánh giá dữ liệu còn thiếu. Các chỗ thiếu đã biết:

- Mỗi hoạt chất chỉ có **một** nhãn của một nhà sản xuất; 6 nhãn sai dạng bào chế so với nhu cầu (`levofloxacin`, `ciprofloxacin`, `metoprolol`, `fluconazole`, `acyclovir`, `ketorolac` là dạng uống trong khi cần dạng tiêm), `insulin_glargine` là bản tương tự sinh học, `methotrexate` là dung dịch uống.
- Không biết nhãn nào thiếu mục nào (liều, chỉnh liều theo thận, tương tác…).
- Chưa có bảng tên biệt dược, hàm lượng, đường dùng của từng hoạt chất.

## 2. Việc phải làm

### 2.1. Danh sách hoạt chất cần lấy (`config/kb/hoat_chat_can_lay.yaml`)

Mỗi mục: `hoat_chat` (tên chung tiếng Anh dùng để truy vấn), `ma` (tên tệp), `duong_dung` (danh sách đường dùng cần lấy theo từ vựng của openFDA, ví dụ `INTRAVENOUS`, `ORAL`), `ghi_chu`. Khởi tạo từ đúng 50 hoạt chất đang có; với các hoạt chất nêu ở mục 1, điền đường dùng cần có theo `data/kb_sources/README.md`. **Không tự thêm hoạt chất mới**: danh mục do dược sĩ chốt, người dùng sẽ tự thêm vào file này.

### 2.2. Lệnh `python -m app.kb.fetch openfda`

- Với mỗi hoạt chất và mỗi đường dùng: gọi `https://api.fda.gov/drug/label.json` với điều kiện tên chung chính xác, loại sản phẩm `HUMAN PRESCRIPTION DRUG`, đường dùng tương ứng; lấy tối đa 25 ứng viên.
- **Quy tắc chọn nhãn** (xác định, ghi lại được): (1) chỉ nhận nhãn đơn chất (`openfda.substance_name` đúng một phần tử khớp hoạt chất), trừ khi cấu hình ghi rõ là dạng phối hợp; (2) ưu tiên nhãn có đủ nhiều mục nhất trong nhóm mục cần cho thẩm định (chỉ định, liều và cách dùng, chống chỉ định, cảnh báo, tương tác, dùng cho nhóm đặc biệt, bảng liều); (3) hoà thì lấy `effective_time` mới nhất; (4) hoà nữa thì theo `set_id` tăng dần.
- Ghi mỗi nhãn được chọn vào `data/kb_sources/openfda/<ma>[__<đường dùng>].json`, giữ nguyên JSON gốc của API. Hoạt chất chỉ có một đường dùng thì giữ tên tệp cũ để không làm đổi mã đoạn đang có.
- Cập nhật `data/kb_sources/manifest.json`: nguồn, tầng 3, giấy phép, `set_id`, `effective_time`, đường dùng, câu truy vấn đã dùng, ngày lấy, mã băm SHA-256, số ứng viên đã xét.
- Tham số: `--only <ma,ma>` (lấy vài hoạt chất), `--refresh` (lấy lại cả khi tệp đã có), `--dry-run` (chỉ in sẽ lấy gì). Mặc định bỏ qua tệp đã có và mã băm khớp manifest.
- Giới hạn tốc độ: không quá 3 yêu cầu mỗi giây; gặp 429 hoặc lỗi 5xx thì lùi dần và thử lại tối đa 4 lần. Có biến môi trường `OPENFDA_API_KEY` thì gửi kèm, không có vẫn chạy. Không in khoá.
- Không tìm thấy nhãn phù hợp: không ghi tệp, ghi vào báo cáo; lệnh vẫn chạy tiếp các hoạt chất khác.

### 2.3. Lệnh `python -m app.kb.fetch ndc`

Gọi `https://api.fda.gov/drug/ndc.json` cho từng hoạt chất, lưu `data/kb_sources/openfda_ndc/<ma>.json` gồm tên biệt dược, tên chung, hàm lượng, dạng bào chế, đường dùng (bỏ trùng). Dùng để dựng bảng tên thuốc → hoạt chất ở bước sau; task này chỉ tải và lập manifest.

### 2.4. Báo cáo độ phủ (`data/kb_reports/openfda_do_phu.md` và `.json`)

Bảng: mỗi dòng một nhãn, mỗi cột một mục cần cho thẩm định; ô ghi có hoặc không và số ký tự. Thêm: số bảng liều tách được, có mục chỉnh liều theo thận hay không, có mục tương tác hay không, đường dùng, `effective_time`. Cuối báo cáo: danh sách hoạt chất thiếu nhãn cho đường dùng cần có; danh sách nhãn thiếu từ 2 mục trở lên. Báo cáo sinh từ dữ liệu trên đĩa, chạy lại được bằng `python -m app.kb.fetch report` mà không gọi mạng.

### 2.5. Dựng lại kho

Sau khi tải: chạy `uv run python -m app.kb.build`. Nếu `app/kb/build.py` hoặc `app/kb/sources/openfda.py` cần sửa nhỏ để đọc được nhiều nhãn cho một hoạt chất thì sửa, giữ nguyên `doan_trich_id` của các đoạn không đổi nội dung. Ghi vào báo cáo: số nhãn, số đoạn trước và sau, số mã đoạn bị đổi.

## 3. Phạm vi file

Được tạo, sửa: `app/kb/fetch/**` (mới), `app/kb/sources/openfda.py` và `app/kb/build.py` (chỉ mức cần cho 2.5), `config/kb/hoat_chat_can_lay.yaml` (mới), `tests/kb/**`, `data/kb_sources/openfda/`, `data/kb_sources/openfda_ndc/`, `data/kb_sources/manifest.json`, `data/kb_sources/README.md` (cập nhật mục "Đã có" và cách tải lại), `data/kb_curated/`, `data/kb_reports/`.
**Cấm đụng:** `web/`, `app/api/`, `app/orchestration/`, `app/db/`, `db/`, `app/retrieval/`, `pyproject.toml`, `plan/`, `data/kb_sources/ddinter/`.

## 4. Kiểm thử phải có (không gọi mạng; dùng phản hồi mẫu lưu trong `tests/kb/fixtures/`)

- Quy tắc chọn nhãn: loại nhãn phối hợp; chọn nhãn nhiều mục hơn; hoà thì theo ngày; kết quả không phụ thuộc thứ tự ứng viên.
- Dựng câu truy vấn: tên có khoảng trắng và ký tự đặc biệt được mã hoá đúng.
- Bỏ qua tệp đã có khi mã băm khớp; `--refresh` thì lấy lại.
- 429 → thử lại; quá số lần → ghi nhận thất bại, không dừng cả lượt.
- Manifest sau khi chạy hai lần liên tiếp giống nhau từng byte (trừ trường ngày lấy của tệp mới).
- Báo cáo độ phủ với 2 nhãn mẫu: đúng ô có và không.

## 5. Nghiệm thu

```bash
uv run ruff check app/kb tests/kb
uv run ruff format --check app/kb tests/kb
uv run pytest -q tests/kb -p no:cacheprovider
uv run python -m app.kb.fetch openfda --dry-run
uv run python -m app.kb.fetch openfda
uv run python -m app.kb.fetch ndc
uv run python -m app.kb.fetch report
uv run python -m app.kb.build
```

Dòng tóm tắt của lệnh cuối phải có `over_max=0`, `under_50=0`, `empty_act=0`. Dán vào báo cáo phần cuối của `openfda_do_phu.md`.

## 6. Cấm làm

Không sửa, dịch, tóm tắt nội dung nhãn. Không lấy dữ liệu từ nguồn nào ngoài `api.fda.gov`. Không thêm thư viện (dùng `httpx` sẵn có). Không commit, không push. Trả lời theo mẫu trong `AGENTS.md`.
