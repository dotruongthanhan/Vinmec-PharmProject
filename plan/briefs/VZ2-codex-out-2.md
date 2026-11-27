TRẠNG THÁI: **CHƯA XONG**

FILE ĐÃ TẠO / SỬA:

- [ui2.test.tsx](D:/create/Vinmec-PharmProject/web/src/features/minh-hoa/__tests__/ui2.test.tsx) và [doan-tuong-tac.test.tsx](D:/create/Vinmec-PharmProject/web/src/features/minh-hoa/__tests__/doan-tuong-tac.test.tsx): bổ sung kiểm thử render đoạn đang dùng và chuyển trạng thái xem bảng.
- [VZ2-bao-cao.md](D:/create/Vinmec-PharmProject/plan/briefs/VZ2-bao-cao.md): ghi đối chiếu từng yêu cầu và test.

LỆNH ĐÃ CHẠY VÀ KẾT QUẢ: Vitest phần minh hoạ **35 test đạt**; TypeScript và oxlint trên hai tệp test đạt. Các test Python liên quan đã chạy riêng từng tệp: **102 test đạt**. Ruff toàn kho không đạt vì lỗi trong `tests/eval/test_cham_minh_hoa.py` và định dạng trong `app/eval/hoi_dap.py`; tôi không sửa các tệp của agent khác. Chi tiết lệnh và đầu ra nằm trong báo cáo.

ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO: Chưa triển khai tool `lay_du_lieu_ca`, tích hợp Gateway, policy, prompt và các test liên quan. Nơi đăng ký tool thực tế là `app/container.py`, nhưng tệp này không nằm trong danh sách brief cho phép sửa. Kiểm thử chuyển bảng hiện dùng hook giả lập, chưa kiểm tra thao tác trên trình duyệt thật.

VIỆC CHƯA LÀM / CÂU HỎI: Cần hoàn thành toàn bộ yêu cầu 1 và 3, kiểm thử luồng agent mới, cùng nghiệm thu trên trình duyệt và API thật.