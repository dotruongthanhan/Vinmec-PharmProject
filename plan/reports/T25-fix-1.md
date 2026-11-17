```text
TRẠNG THÁI: XONG
FILE ĐÃ TẠO / SỬA:
- app/kb/fetch/labels.py
- app/kb/fetch/runner.py
- app/kb/fetch/report.py
- app/kb/fetch/client.py
- app/kb/fetch/__main__.py
- tests/kb/conftest.py
- tests/kb/test_openfda_fetch.py
- data/kb_sources/README.md
LỆNH ĐÃ CHẠY VÀ KẾT QUẢ: Chưa chạy lệnh nào (tuân thủ yêu cầu tuyệt đối không gọi công cụ shell và không gọi mạng; người review sẽ chạy các lệnh nghiệm thu ở mục 5 của plan/briefs/T25-fix-1.md).
ĐIỂM LỆCH SO VỚI BRIEF (nếu có) VÀ LÝ DO:
- Không sửa config/kb/hoat_chat_can_lay.yaml vì tên hoạt chất hiện tại (như warfarin sodium, valproate sodium, ketorolac tromethamine, metoprolol tartrate, enoxaparin sodium, insulin glargine) đã xử lý được bằng chiến lược 4 bậc và quy tắc so khớp tên chung mới mà vẫn giữ đủ 50 mã và tránh nhận nhầm metoprolol succinate hoặc bản tương tự sinh học.
- Thay đổi quy ước tên trạng thái lỗi tải từ "that_bai" sang "loi_ket_noi" và mã thoát phân biệt 3 kết cục (0=đạt, 1=loi_ket_noi, 2=khong_co_ung_vien_hop_le, 3=khong_tim_thay) theo mục 3 của brief; đã cập nhật 4 kiểm thử hiện có trong tests/kb/test_openfda_fetch.py tương ứng với quy tắc mới.
VIỆC CHƯA LÀM / CÂU HỎI:
- Người review chạy bộ nghiệm thu: ruff check/format, pytest -q tests/kb -p no:cacheprovider --ignore=tests/kb/.tmp, python -m app.kb.fetch openfda|ndc|report và python -m app.kb.build trên máy có mạng.
- Thư mục khóa quyền tests/kb/.tmp cũ (nếu còn trên đĩa) cần người dùng/người review xóa thủ công vì agent không dùng shell.
```

Chi tiết thay đổi:
- [labels.py](file:///D:/create/Vinmec-PharmProject/app/kb/fetch/labels.py): bổ sung `build_queries` 4 bậc cho cả `drug/label` và `drug/ndc` (`generic_name.exact` viết hoa -> `substance_name.exact` / `active_ingredients.name.exact` viết hoa -> `generic_name` không `.exact` -> `generic_name` không `.exact` đã bỏ muối khi khác bậc 3); bỏ `.exact` ở `product_type` và `route`; tách `label_rejection_reason` và `ndc_rejection_reason` để lọc chặt đơn chất/phối hợp, từ chối hậu tố tương tự sinh học (`-[a-z]{4}`), tránh nhầm muối khác loại (`metoprolol succinate` với `metoprolol tartrate`), đồng thời chấp nhận `generic_name` dài hơn ở nhãn tiêm/tiêm dưới da (ví dụ dung môi hoặc `INJECTION,USP`).
- [runner.py](file:///D:/create/Vinmec-PharmProject/app/kb/fetch/runner.py): thực thi tải nhiều bậc `_fetch_label_tiered` và `_fetch_ndc_tiered`, dừng ở bậc đầu tiên có ứng viên đạt chuẩn; ghi `bac_truy_van` và `truy_van` vào `manifest.json` và kết quả tải; phân tách `khong_tim_thay` (404 ở mọi bậc), `khong_co_ung_vien_hop_le` (kèm `ly_do_loai` tối đa 3 ứng viên đầu), và `loi_ket_noi`.
- [report.py](file:///D:/create/Vinmec-PharmProject/app/kb/fetch/report.py) và [__main__.py](file:///D:/create/Vinmec-PharmProject/app/kb/fetch/__main__.py): cập nhật hiển thị 3 kết cục trong báo cáo độ phủ và mã thoát `_exit_code` (`0`, `1`, `2`, `3`).
- [client.py](file:///D:/create/Vinmec-PharmProject/app/kb/fetch/client.py): kiểm tra an toàn hơn khi trường `error` của phản hồi 404 là `null`.
- [conftest.py](file:///D:/create/Vinmec-PharmProject/tests/kb/conftest.py): bỏ cấu hình `basetemp` trỏ vào `tests/kb/.tmp/t25-pytest`, dùng `tmp_path` mặc định của pytest.
- [test_openfda_fetch.py](file:///D:/create/Vinmec-PharmProject/tests/kb/test_openfda_fetch.py): bổ sung kiểm thử dùng mẫu thật [mero_label_rx_iv.json](file:///D:/create/Vinmec-PharmProject/data/kb_sources/openfda_api_mau/mero_label_rx_iv.json), [mero_ndc.json](file:///D:/create/Vinmec-PharmProject/data/kb_sources/openfda_api_mau/mero_ndc.json), [err_404.json](file:///D:/create/Vinmec-PharmProject/data/kb_sources/openfda_api_mau/err_404.json) và dữ liệu dựng tay tối thiểu cho truy vấn nhiều bậc, tên dài hơn, loại dạng phối hợp ở bậc lỏng, lý do loại 3 ứng viên đầu, 3 mã thoát, thay nhãn sai đường dùng kèm đếm `so_ma_doan_bi_doi`, và kiểm tra `tmp_path` ngoài `tests/kb/.tmp`.
- [README.md](file:///D:/create/Vinmec-PharmProject/data/kb_sources/README.md): cập nhật mục 1 (`Đã có`) và mục 6 (`Tải lại openFDA và lập báo cáo`) theo chiến lược nhiều bậc và mã thoát mới.
