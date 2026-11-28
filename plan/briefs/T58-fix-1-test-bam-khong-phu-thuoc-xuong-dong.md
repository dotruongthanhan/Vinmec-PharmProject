# T58-fix-1 – Test băm dữ liệu ca không phụ thuộc kiểu xuống dòng

Mô hình: Codex `gpt-6.1-sol`, effort `xhigh`. Không có mạng.

Đọc: `AGENTS.md`, `plan/reports/T58.md`.

## Bối cảnh (Claude kiểm bằng bản clone sạch ngày 19/11)

Claude clone kho ra thư mục tạm (không dữ liệu, không `.env`) và chạy pytest với `conftest.py` của T58. Kết quả: **1 trượt**, 1.197 qua, 103 bỏ qua.

- Test trượt: `tests/db/test_administrative.py::test_generator_is_deterministic_additive_and_preserves_originals`.
- Test này băm **từng byte** của `data/mock/_goc_truoc_T45/*.json` rồi so với một mã cố định.
- Trên máy Khải, một số tệp ca đang xuống dòng CRLF, số khác là LF. Git lưu LF, còn Windows có `core.autocrlf=true` sẽ đổi khi checkout. Vì vậy mã băm chỉ khớp trên đúng máy Khải.
- Claude đã thêm `.gitattributes` ở gốc kho (`* text=auto eol=lf`) để mọi máy checkout ra LF. **Không sửa tệp này.**

Rà thêm các test khác có băm / so byte trên tệp văn bản trong `data/` hoặc `tests/` (`hashlib`, `read_bytes`, `sha256`) và sửa cùng cách nếu có.

## Phạm vi

- **Được sửa:** `tests/db/test_administrative.py`, các test cùng loại tìm được, mục "## T58-fix-1" cuối `plan/reports/T58.md`.
- **Cấm:** sửa dữ liệu trong `data/**`, mã ứng dụng, `.gitattributes`, `conftest.py`.

## Yêu cầu

1. Trước khi băm, chuẩn hoá nội dung: `read_bytes().replace(b"\r\n", b"\n")`. Tính lại mã băm kỳ vọng trên nội dung đã chuẩn hoá. Kiểm bằng nội dung git: `git show HEAD:<path>` lưu LF.
2. Test vẫn phải bắt được khi nội dung ca gốc bị sửa thật. Thêm một kiểm: đổi một ký tự thì mã băm khác.
3. Nghiệm thu, dán kết quả vào báo cáo:
   - `uv run pytest -q -p no:cacheprovider --basetemp=<%TEMP%>` trong kho: **0 trượt**.
   - Clone sạch, chạy với biến môi trường như CI (`CDSS_PROFILE=test`, `CDSS_AI=off`, `CASE_SOURCE=file`, `AUTH_MODE=off`):
     1. `git clone . <%TEMP%\x>`
     2. Chép `tests/conftest.py`, `pyproject.toml`, `.gitattributes` và các test đã sửa sang bản clone.
     3. Chạy `git rm -r -q --cached . && git reset -q --hard` trong bản clone. Bước này để checkout lại theo `.gitattributes`. Nó sẽ hoàn tác các tệp vừa chép, nên **chép lại một lần nữa** sau bước này.
     4. Chạy `uv sync --frozen` rồi pytest.
     - Kỳ vọng: **0 trượt**, chỉ có bỏ qua.
   - `uv run ruff check .`.

## Cấm làm

Không gọi mạng. Không commit. Không dùng `&`. Không xoá test.
