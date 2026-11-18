# Dữ liệu hồ sơ giả lập

Toàn bộ họ tên, số thẻ BHYT, số điện thoại và địa chỉ trong 60 hồ sơ tại đây
và 6 hồ sơ `../demo/` là **giả lập**, không thuộc người bệnh thật. Địa danh
có thật chỉ làm bối cảnh mẫu; số nhà là giả. Số điện thoại dùng mẫu
`0900 000 0xx`, không dùng để liên hệ. Họ tên đánh số 1–66 theo brief T45.

Chạy `uv run python tools/sinh_hanh_chinh.py --dry-run` để kiểm trước khi bổ sung;
`uv run python tools/kiem_hanh_chinh.py` để kiểm các trường và bảo toàn nội dung gốc.
Bản gốc 66 hồ sơ tại `../_goc_truoc_T45/` chỉ dùng đối chiếu, không được sửa.

Cân nặng/chiều cao có sẵn được lấy từ số đo gần lần vào viện mới nhất. Chiều cao
còn thiếu được sinh cố định cho dữ liệu mẫu; cân nặng không được ghi nhận vẫn
là `null` (HS-040), tránh biến dữ liệu thiếu thành số liệu lâm sàng giả định.
Ngày sinh khớp tuổi đã có tại lần vào viện đầu; không thay đổi tuổi trong hồ sơ.
