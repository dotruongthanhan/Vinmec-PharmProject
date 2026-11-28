# Báo cáo VZ1-fix-1

TRẠNG THÁI: CHƯA XONG — kiểm thử vitest bổ sung chưa được chạy bằng vitest; chưa đo bố cục trên trình duyệt.

- Máy chủ và web từ chối trộn ô của ca với ô cùng cột theo tham số trong một mảng; phép tra khoảng theo tham số phải có ô hiển thị cùng bộ dữ liệu và cột. Lý do từ chối máy chủ có hướng dẫn sửa.
- Kỹ năng minh hoạ và mẫu demo đã chỉnh dùng cùng giá trị CrCl cho phụ đề và mức liều. Số của ca có dòng riêng; mẫu vi phạm được giữ riêng để kiểm thử. Mock dùng mẫu đã chỉnh.
- Giá trị phụ thuộc tham số được ghi rõ giả định khi điều khiển khác mặc định. Khung hẹp dùng toàn chiều ngang cho phụ đề và từng ô số.

## Lệnh và kết quả

- `uv run --offline --frozen ruff check app tests`: đạt.
- `uv run --offline --frozen ruff format --check app tests/agent`: đạt, 236 tệp.
- `uv run --offline --frozen pytest -q -p no:cacheprovider tests/agent/test_minh_hoa_kiem.py --basetemp <thư mục mới trong %TEMP%>`: 40 đạt.
- `uv run --offline --frozen pytest -q -p no:cacheprovider tests/agent/test_minh_hoa_do_thi.py --basetemp <thư mục mới trong %TEMP%>`: 19 đạt. Lần đầu có 10 lỗi và 9 đạt vì ví dụ prompt chưa được sửa do mã hoá; sau khi sửa đã chạy lại thành công.
- Tại `web`, chạy các tệp thực thi đã cài trong `node_modules/.bin`: `tsc -b` đạt; `oxlint` đạt với một cảnh báo có sẵn ở `src/features/lookup/InteractionLookupPage.tsx:111`; `vitest run` đạt 49 tệp, 406 kiểm thử; `vite build` đạt.
- Kiểm tra độc lập bằng Node: ba ví dụ prompt được bộ kiểm web chấp nhận; tại creatinin 121, CrCl lưới là 28.030876951331493 và phụ đề cùng ô mức liều khớp phép tra; có điểm riêng cho giá trị ca.

## Giới hạn và điểm lệch

- Theo giới hạn RAM, không chạy toàn bộ `tests/agent`; chỉ chạy lần lượt hai tệp pytest được brief cho phép, mỗi lần dùng `--basetemp` riêng trong `%TEMP%`.
- Kiểm thử vitest cho ba ví dụ prompt được bổ sung sau lượt `vitest run` duy nhất; cùng các ví dụ và bộ kiểm web đã được kiểm độc lập bằng Node như trên, nhưng kiểm thử vitest mới chưa được chạy bởi vitest.
- Bố cục 320 và 399 px được kiểm tĩnh qua lớp CSS; chưa đo số ký tự mỗi dòng hay tràn ngang trên trình duyệt. Brief giao Claude chạy lại e2e.
- Hai lệnh `uv run` đầu tiên không khởi tạo được cache mặc định do quyền truy cập; các lệnh sau dùng `UV_CACHE_DIR` trong `%TEMP%` và chế độ offline.
- Hướng dẫn `modern-web-guidance` yêu cầu tải gói qua mạng; không thực hiện vì brief cấm mạng và cài gói.
