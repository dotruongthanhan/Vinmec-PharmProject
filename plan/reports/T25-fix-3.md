TRẠNG THÁI: XONG

Đã thêm `phan_hoi_sai_cau_truc`, dùng mã thoát 1, có lý do và dòng riêng trong báo cáo; giữ nguyên tệp nguồn cũ và tiếp tục hoạt chất kế.

FILE ĐÃ TẠO / SỬA: Sửa đúng 10 tệp được phép:

- `app/kb/fetch/`: `client.py`, `runner.py`, `report.py`, `__main__.py`.
- `tests/kb/`: `test_fetch.py`, `test_openfda_fetch.py`, `test_names.py`, `test_openfda_source.py`.
- `tests/db/test_mapping.py`.
- `data/kb_sources/README.md`: chỉ thêm một dòng.

LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:

- `uv run ruff check app/kb tests/kb tests/db --exclude tests/kb/.tmp --exclude tests/db/.tmp` → đạt.
- `uv run ruff format --check app/kb tests/kb tests/db --exclude tests/kb/.tmp --exclude tests/db/.tmp` → 27 tệp đúng định dạng.
- `uv run pytest -q -p no:cacheprovider --ignore tests/db/.tmp --ignore tests/kb/.tmp --ignore tests/architecture/.tmp --ignore tests/api/.tmp` → **723 passed**, 1 cảnh báo deprecation sẵn có từ FastAPI/Starlette. Test dựng kho được brief lưu ý cũng qua.

ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO: Không. Pytest dùng thư mục tạm ngoài kho.

VIỆC CHƯA LÀM / CÂU HỎI: Không. Không commit, không push, không gọi openFDA thật.