# T40-fix-1 – Cập nhật hai test sau khi danh mục thuốc của 60 hồ sơ đã được chuẩn hóa

Đọc `AGENTS.md`, `plan/briefs/T40-luoc-do-nhieu-lan-vao-vien-va-nap-tu-dau.md`, `plan/reports/T40.md`.

## Bối cảnh
Báo cáo T40 ghi `all --dry-run` thất bại vì 9 bản thuốc trùng mã nhưng khác nội dung. Nguyên nhân là dữ liệu sinh ra lệch nhẹ giữa các hồ sơ (viết "uong"/"uống", "1 g"/"1000 mg", "Ceftriaxone"/"Ceftriaxon"), **không phải lỗi bộ nạp**. Claude đã chuẩn hóa danh mục thuốc trong `data/mock/hoso_gia_lap/*` và căn `T-MEROPENEM-1G` theo `data/mock/demo/DEMO-02.json`. Kết quả hiện tại: `uv run python -m app.db all --dry-run` báo **0 dòng bị loại**, 66 người bệnh, 93 đợt, 228 y lệnh, 233 dòng thuốc.

Hai test đang khẳng định trạng thái lỗi cũ nên trượt:
1. `tests/db/test_cli.py::test_dry_run_never_connects[cases]` mong mã thoát 1 cho nhóm `cases`.
2. `tests/db/test_multi_encounter.py::test_source_conflicts_are_explicit_and_no_other_rows_are_rejected` mong đúng 9 dòng bị loại từ dữ liệu thật.

## Yêu cầu
1. Sửa test (1): `load cases --dry-run` phải trả **0** như các nhóm khác (bỏ nhánh `1 if group == "cases"`).
2. Sửa test (2): **không dựa vào dữ liệu thật để có xung đột.** Tạo trong `tmp_path` một bộ hồ sơ giả gồm hai hồ sơ cùng `thuoc_id` nhưng khác `ten_thuoc` (và một cặp chỉ khác đơn vị nhưng cùng lượng, ví dụ 1 g so với 1000 mg: quyết định theo cách bộ nạp hiện xử lý, ghi rõ trong báo cáo), rồi kiểm: xung đột được báo rõ, bản đầu được giữ, bản sau bị loại và ghi vào nhật ký, không dòng nào khác bị loại.
3. Thêm một test mới trên **dữ liệu thật** của kho: nạp thử trong bộ nhớ cả `data/mock/demo` và `data/mock/hoso_gia_lap`, khẳng định **0 dòng bị loại** và các số đếm: `nguoi_benh` 66, `dot_dieu_tri` 93, `y_lenh` 228, `chi_tiet_y_lenh` 233, `thuoc` 67, `lan_tham_dinh` 66.
4. Không sửa `app/`, `data/`, `tools/`, `db/`, tài liệu `plan/` trừ báo cáo `plan/reports/T40-fix-1.md`. Không chạy lệnh ghi Supabase (chỉ `--dry-run`). Không đọc `.env`.

## Nghiệm thu
```
uv run ruff check app/db tests/db
uv run pytest -q -p no:cacheprovider --basetemp=.pytest_tmp tests/db
uv run pytest -q -p no:cacheprovider --basetemp=.pytest_tmp
uv run python -m app.db all --dry-run
```
Pytest dùng `--basetemp` trong thư mục làm việc vì thư mục tạm của hệ thống bị từ chối quyền trên máy này (xóa `.pytest_tmp` sau khi chạy). Báo cáo ngắn: kết quả bốn lệnh và mọi lệch brief.
