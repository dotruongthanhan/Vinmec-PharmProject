# Sổ tay thử

| Tệp | Thử gì | Cần mạng / khoá |
| :--- | :--- | :-: |
| `00_cau_hinh.ipynb` | Nạp `settings.yaml`, in cấu hình hiệu lực, kiểm biến môi trường có mặt (không in giá trị) | Không |
| `01_test_db.ipynb` | Nạp ca qua `CaseRepository`; mở kho véc-tơ, đếm đoạn theo nguồn, theo hoạt chất, theo mục; đọc phản hồi và nhật ký | Không |
| `02_test_chunking.ipynb` | Cắt 1–2 nhãn thuốc; phân bố độ dài; in vài đoạn kèm siêu dữ liệu; kiểm bảng không bị cắt, mảnh nhỏ đã gộp | Không |
| `03_test_embedding.ipynb` | Nhúng vài câu; số chiều; cặp Việt – Anh cùng nghĩa; tỉ lệ trúng bộ đệm; tốc độ | Có |
| `04_test_retriever.ipynb` | Một truy vấn qua từng tầng: BM25 · véc-tơ · RRF · xếp hạng lại, xem hạng thay đổi thế nào | Có |
| `05_test_tools.ipynb` | Gọi tay 4 công cụ chỉ đọc trên một ca; thử đầu vào sai, thử đọc ca khác (phải bị từ chối) | Không |
| `06_test_llm.ipynb` | Một lời gọi tổng hợp với gói căn cứ cố định; kiểm JSON theo lược đồ; đo thời gian và số token | Có |
| `07_test_verify.ipynb` | Cho nhận định đúng và nhận định cố ý sai (mã lạ, câu trích bịa, con số bịa) qua bộ kiểm chứng | Không |
| `08_test_agent.ipynb` | Lắp ráp: chạy cả đồ thị trên 6 ca demo; xem `vet` từng nút; so với đáp án ở `data/gold` | Có |
| `09_eval.ipynb` | Số đo truy xuất (mục 6.7) và số đo cả luồng (plan 1 mục 8.2) | Có |

Quy tắc:

- Sổ tay **không chứa logic**: chỉ import từ `app/`, lấy đối tượng từ `build_container()`. Thấy mình viết hàm trong sổ tay thì hàm đó phải chuyển vào `app/` kèm test.
- Sổ tay là chỗ **nhìn bằng mắt và thử nhanh**; `pytest` vẫn là cổng nghiệm thu. Điều gì sổ tay cho thấy là đúng thì phải có test tương ứng.
- Xoá đầu ra trước khi đưa vào git (dùng `nbstripout`); không in khoá, không in dữ liệu ngoài dữ liệu giả lập.
- Sổ tay không cần mạng phải chạy được với `profile="test"`.


## Cách chạy

Chạy `uv run jupyter lab` hoặc mở sổ tay bằng VS Code với nhân Python của `.venv`.
