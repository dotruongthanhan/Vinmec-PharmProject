# T25 – Kết quả nghiệm thu ngày 17/11/2026

**TRẠNG THÁI: CHƯA XONG phần tải dữ liệu thực tế.** Đã triển khai lệnh, cấu hình 50 hoạt chất, kiểm thử ngoại tuyến, báo cáo độ phủ và dựng lại kho hiện có. Không commit, push hoặc thay đổi nhánh.

## Lệnh đã chạy và kết quả

| Lệnh | Mã thoát | Kết quả |
| --- | --- | --- |
| `uv run ruff check app/kb tests/kb` | 0 | `All checks passed!` |
| `uv run ruff format --check app/kb tests/kb` | 0 | `26 files already formatted` |
| `uv run pytest -q tests/kb -p no:cacheprovider` | 0 | `49 passed in 2.06s` |
| `uv run python -m app.kb.fetch openfda --dry-run` | 0 | `bo_qua=42 se_lay=8`, không gọi mạng/ghi nguồn |
| `uv run python -m app.kb.fetch openfda` | 1 | `bo_qua=42 that_bai=8`, mỗi lỗi là `Lỗi kết nối openFDA (ConnectError)` |
| `uv run python -m app.kb.fetch ndc` | 1 | `that_bai=50`, cùng lỗi kết nối, không tạo tệp NDC giả |
| `uv run python -m app.kb.fetch report` | 0 | `labels=50 missing_routes=8`, chạy ngoại tuyến |
| `uv run python -m app.kb.build` | 0 | Dựng 50 nhãn, 3.738 đoạn; dòng đầy đủ ở cuối `openfda_do_phu.md` |
| `uv run pytest -q -p no:cacheprovider` | 0 | `649 passed, 1 warning in 44.46s` |

Cảnh báo của suite toàn dự án: `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` Không thêm thư viện vì brief cấm.

## Môi trường chạy

- Cache mặc định của `uv` bị từ chối ghi; dùng `UV_CACHE_DIR=D:/create/Vinmec-PharmProject/tests/kb/.tmp/uv-cache`.
- Dùng `UV_OFFLINE=1` và `UV_NO_SYNC=1` để chạy thư viện trong `.venv` sẵn có, không cài thêm hoặc sửa `pyproject.toml`/lockfile. Lần thử `uv run` không có `UV_NO_SYNC` đã thất bại vì cache thiếu `hatchling`; đây là lỗi chuẩn bị môi trường, chưa chạy test.
- Đặt `PYTHONIOENCODING=utf-8` cho đầu ra tiếng Việt. `tests/kb/conftest.py` đặt thư mục tạm trong `tests/kb/.tmp/` khi không có `--basetemp`. Suite toàn dự án dùng `PYTEST_ADDOPTS=--basetemp=tests/kb/.tmp/t25-full-suite`.
- Kiểm tra trực tiếp endpoint `https://api.fda.gov/drug/label.json` xác nhận chuỗi nguyên nhân `httpx.ConnectError` → `httpcore.ConnectError` → `PermissionError`, `errno=13`, `winerror=10013`. Môi trường từ chối kết nối mạng; không phải HTTP 429 hay hết số lần thử lại.
- Hai trang tài liệu API bắt buộc trong brief đã đọc qua công cụ web; không lấy dữ liệu nhãn/NDC từ nguồn thay thế.

## Dữ liệu và độ phủ

- Không tải thành công nhãn mới hoặc NDC. Giữ nguyên tệp nguồn và manifest hiện có; không tự điền ngày lấy/số ứng viên cho nhãn cũ chưa được lấy lại.
- Tám mục chưa có nhãn khớp toàn bộ tên, thành phần, loại sản phẩm và đường dùng cấu hình: `acyclovir`, `ciprofloxacin`, `enoxaparin`, `fluconazole`, `insulin_glargine`, `ketorolac`, `levofloxacin`, `metoprolol_tartrate`.
- `enoxaparin` hiện có đường `SUBCUTANEOUS`, nhưng tên chung nguồn là `ENOXAPARIN SODIUM INJECTION,USP`; cấu hình dùng tên hoạt chất `enoxaparin sodium` đã có trong danh mục nên cần lấy lại bằng tên chính xác này. Nhãn insulin hiện tại có hậu tố tương tự sinh học, không khớp `insulin glargine`.
- Báo cáo từng nhãn, từng ô có/không và số ký tự, số bảng liều, chỉ dấu mục thận, thiếu nhãn và thiếu từ hai mục: `openfda_do_phu.md` / `.json`. Chỉ dấu thận là phép dò văn bản trong mục liều/nhóm đặc biệt, chưa xác nhận một quy tắc chỉnh liều đã được dược sĩ duyệt.
- Trước / sau dựng kho: **50 / 50 nhãn**, **3.738 / 3.738 đoạn**. **0 mã đoạn cũ bị thay**, **0 mã của nội dung và đường dẫn không đổi bị thay**.
- Log từng mục nằm trong `openfda_fetch_openfda.json` và `openfda_fetch_ndc.json`; không ghi khóa API.

## Kiểm thử và rà soát

Kiểm thử dùng JSON phản hồi mẫu trong `tests/kb/fixtures/` và `httpx.MockTransport`, không gọi mạng. Bao phủ chọn đơn chất/phối hợp khai báo, số mục → ngày → set_id, thứ tự ứng viên, mã hóa truy vấn, SHA-256/refresh, manifest ổn định từng byte, 429/5xx và hết bốn lần thử lại, giới hạn tốc độ, khóa tùy chọn, dry-run, NDC bỏ trùng/phân trang, báo cáo độ phủ và bảo toàn mã đoạn.

Rà soát độc lập phát hiện ba lỗi; đã tái hiện bằng test thất bại rồi sửa và chạy lại đạt:

1. Cùng set_id cho nhiều đường dùng có thể giữ phiên bản cũ: bộ dựng chọn ngày nguồn mới nhất trước khi cắt đoạn; manifest tên cũ chỉ thôi được nạp khi đủ các nhãn thay thế, tệp gốc cũ vẫn giữ trên đĩa.
2. `results: [null]` có thể dừng cả lượt: máy khách xác minh từng phần tử và ghi lỗi, tiếp tục hoạt chất kế tiếp.
3. Trang NDC rỗng sớm có thể được coi là thành công: giữ tổng số bản ghi đã biết, từ chối ghi tệp khi thiếu trang.

Việc đọc khóa dùng lại `app.config.settings.get_secret`, không đọc môi trường trực tiếp trong module fetch; ba test ranh giới import/cấu hình cũng đạt. Chỉ sửa bộ dựng kho ở phần hỗ trợ nhiều nhãn, bảo toàn mã và số liệu báo cáo; không sửa bộ đọc nhãn gốc.

## Điểm cần chốt và việc còn lại

- Chạy lại `openfda`, `ndc`, `report`, `build` khi môi trường kết nối được `api.fda.gov`. Dùng `openfda --refresh` nếu cần đánh giá lại đủ tối đa 25 ứng viên cho cả 50 nhãn tải tay và bổ sung siêu dữ liệu manifest từ lượt lấy thực tế.
- README chưa nêu đường dùng cụ thể cần thay cho methotrexate; giữ `ORAL` và ghi thiếu quyết định này trong cấu hình/báo cáo, không tự chọn đường tiêm.
- Yêu cầu metoprolol dạng tiêm được đặt cho mục `metoprolol_tartrate`; giữ mục `metoprolol_succinate` là `ORAL`. Không thêm hoạt chất ngoài đúng 50 mã đã có.

```text
[openfda] status=OK labels=50/50 chunks=3738 text=3506 table=232 over_max=0 under_50=0 empty_act=0 q3_warn=18 missing_set_id=0
```
