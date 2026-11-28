# T48 – Che PII theo trường, gửi tối thiểu, mã tạm và khôi phục

Mô hình: Codex `gpt-6.2-sol`, effort `high`. Chạy nền, không dừng để hỏi; điểm chưa rõ thì chọn cách ít rủi ro nhất, ghi vào báo cáo mục "Lựa chọn đã làm".

## Bối cảnh
- Bộ che hiện tại (`app/deid/scrubber.py`) chỉ đoán bằng mẫu. Claude đã thử: lọt `Nguyễn Thị Lan vào viện` (không có danh xưng), `người nhà Lê Văn Hùng`, ngày ISO `1958-03-12`, địa chỉ; `bà Trần thị hoa` chỉ che một phần.
- Dữ liệu hành chính (họ tên, ngày sinh, địa chỉ, SĐT, BHYT, CCCD, người liên hệ, mã hồ sơ/mã người bệnh) **có sẵn theo trường**: ở DB đọc qua `app/db/administrative.read_administrative([nguoi_benh_id])` (mô hình `s.AdministrativeRecord`, `app/api/schemas.py` ~241–270); ở chế độ tệp nằm trong khối `hanh_chinh` của `data/mock/**/<ca>.json`.
- Mã bản ghi gửi cho LLM có chứa mã hồ sơ/mã người bệnh (`SH-HS001-1-01`, `SH-{nguoi_benh_id}-CC`, `DB-HS-001-1-01`).

Người dùng chốt ba hướng **kết hợp**:
1. **Che theo trường:** lấy giá trị thật từ các trường hành chính của đúng người bệnh, dò và thay trong mọi văn bản gửi LLM bằng mã tạm; khi LLM trả về thì thay lại.
2. **Chỉ gửi thứ cần thiết:** prompt chỉ chứa dữ liệu lâm sàng cần cho thẩm định (tuổi, giới, cân nặng, chiều cao, chẩn đoán, xét nghiệm, thuốc...), không bao giờ chứa trường định danh.
3. **Văn bản tự do** (diễn biến, ghi chú bác sĩ, cách dùng, câu hỏi của dược sĩ): sau lớp 1 vẫn chạy bộ mẫu (lớp 2) để bắt tên người nhà, bác sĩ, ngày, địa chỉ không nằm trong trường nào.

## Phạm vi file
Được sửa/tạo: `app/deid/**`, `app/llm/case_context.py`, `app/llm/synthesizer.py`, `app/orchestration/ask.py`, `tests/deid/**`, `tests/llm/**`, `tests/orchestration/test_ask*.py`, test mới bất kỳ trong `tests/`, `plan/reports/T48.md`.
Cấm đụng (task khác đang sửa song song): `app/api/service.py`, `app/db/read_pool.py`, `app/orchestration/ai_review.py`, `app/orchestration/graph*`, `app/container.py`, `pyproject.toml`, `uv.lock`, `web/`, `config/prompts/` (trừ khi bắt buộc; nếu sửa prompt thì nêu lý do), `.env`, `data/`.

## Yêu cầu
1. **Nguồn định danh đã biết** (`app/deid/known.py` hoặc tương tự): hàm `known_identifiers(ca: CaBenh) -> list[GiaTriDinhDanh]` (loại + giá trị). Chế độ DB gọi `read_administrative` (không cache, không log giá trị); chế độ tệp đọc `hanh_chinh` của tệp ca (tìm theo `ca_id` trong `app.case_dir` của settings, không tạo đường dẫn từ dữ liệu người dùng ngoài mã ca đã có). Lỗi đọc thì **đóng an toàn**: vẫn chạy lớp 2 và thêm cảnh báo "không lấy được định danh để che", không làm hỏng bước AI. Luôn thêm `nguoi_benh_id`, `ca_id`, mã hồ sơ.
2. **Lớp 1, che theo giá trị:** thay mọi lần xuất hiện của từng giá trị, kể cả biến thể: không phân biệt hoa thường, không dấu, tên gọi (từ cuối của họ tên khi đứng sau danh xưng ông/bà/anh/chị/BN/cháu), ngày sinh ở các dạng `dd/mm/yyyy`, `d/m/yyyy`, `yyyy-mm-dd`, SĐT có/không dấu cách. Ưu tiên chuỗi dài trước. Mã tạm cùng dạng hiện có (`[TEN_1]`, `[NGAY_1]`, `[SDT_1]`, `[DIACHI_1]`, `[MA_1]`...), một giá trị một mã trong một lần gọi.
3. **Lớp 2, mẫu:** bổ sung vào `scrubber.py`: ngày ISO, tên không có danh xưng **khi có từ khóa ngữ cảnh** (người nhà, vợ, chồng, con, BS, ĐD...), địa chỉ sau "địa chỉ/ĐC/trú tại/số nhà", danh xưng viết thường (`bà Trần thị hoa`). Không che tên thuốc, hoạt chất, đơn vị, tên khoa (giữ toàn bộ test cũ của scrubber; thêm ca âm tính: "Paracetamol", "Vancomycin", "Khoa Nội tim mạch").
4. **Mã bản ghi thành mã tạm:** trong `build_case_context`, đổi `ban_ghi_id` (sinh hiệu, xét nghiệm, diễn biến, chẩn đoán, dị ứng, dòng y lệnh...) thành `R1, R2...` theo thứ tự xuất hiện; `GoiCanCu.ban_ghi_ids`, `dong_y_lenh_ids` dùng mã tạm để kiểm chứng chạy trên mã tạm; trong `synthesizer.py`, **sau** kiểm chứng và **trước** `merge`, đổi mã tạm về mã thật trong mọi trường của nhận định AI (`can_cu`, dòng y lệnh, văn bản). Kết quả cuối giống hệt cách làm cũ về mã bản ghi.
5. **Khôi phục định danh:** chỉ trong kết quả trả về giao diện (văn bản diễn giải, câu trả lời hỏi thêm) bằng bảng ánh xạ của chính lần gọi; bảng ánh xạ chỉ sống trong bộ nhớ của lần gọi, không ghi log, không lưu tệp, không đưa vào cảnh báo. Mã tạm lạ (LLM bịa) giữ nguyên.
6. **Gửi tối thiểu (hướng 2):** ghi trong docstring của `build_case_context` danh sách trường được gửi; thêm test khẳng định prompt chỉ chứa tuổi/giới chứ không chứa họ tên, ngày sinh, địa chỉ, SĐT, BHYT, CCCD, mã người bệnh, mã hồ sơ.
7. **Hỏi thêm (`ask.py`):** câu hỏi, lịch sử, ghi chú, ngữ cảnh ca đều qua lớp 1 (định danh của ca đang mở; câu hỏi chung `__global__` thì chỉ lớp 2) rồi lớp 2; khôi phục ở câu trả lời như trên.
8. **Test trên toàn bộ dữ liệu:** chạy `build_case_context` cho tất cả ca trong `data/mock/demo` và `data/mock/hoso_gia_lap` (chế độ tệp, không cần DB) và khẳng định không giá trị hành chính nào (và không biến thể không dấu) xuất hiện trong văn bản gửi LLM; thêm vài ca chèn tên người bệnh vào diễn biến/câu hỏi bằng chuỗi giả để chứng minh lớp 1 che được.
9. Không đổi kết luận luật, không đổi hợp đồng API.

## Nghiệm thu (dán kết quả)
- `uv run ruff check .`, `uv run ruff format --check` (tệp đã sửa), `uv run pytest -q --basetemp=.pytest_t48` đều qua.
- Bảng trước/sau cho các câu Claude đã thử ở phần bối cảnh.
- Báo cáo `plan/reports/T48.md` (kèm mục "Giới hạn còn lại").

## Cấm làm
Không commit/push, không thêm thư viện (không dùng mô hình NER), không gọi LLM thật trong test, không in giá trị bí mật, không dùng `&`, xóa `.pytest_t48*`.
