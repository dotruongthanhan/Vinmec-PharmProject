# T52-fix-1 – Không để độ phủ lùi vì dạng muối (PIN), làm sạch kho ứng viên

Mô hình: Codex `gpt-6.2-sol`, effort `high`. Không có mạng, không cần mạng.

Đọc: `AGENTS.md`, `plan/briefs/T52-nang-do-phu-tu-dien.md`, `plan/reports/T52.md`, `app/kb/dictionary/catalog.py`, `app/kb/names.py`.

## Vấn đề Claude thấy khi review

`data/kb_reports/T52_do_phu_truoc_sau.json`:
- Thêm mới 3.102 chế phẩm đủ thành phần.
- **2.360 chế phẩm trước đã đủ thì lùi về chưa đủ**: lý do `pin_thieu_quan_he_in` 2.330, `pin_trung_nhieu_ma` 30.
- Kết quả: độ phủ chỉ tăng từ 36.099 lên 36.841.

Nguyên nhân:
- Từ khi có danh sách RxNorm (`allconcepts_IN_PIN.json`), tên có muối khớp thẳng vào mục **PIN** (`losartan potassium`, `metformin hydrochloride`, `bisoprolol fumarate`, `enalapril maleate`, `atorvastatin calcium`, `ceftriaxone sodium`…; 272 khoá).
- `pin_base()` cần quan hệ PIN → IN trong đệm RxNav, nhưng đệm không có.
- Ở T50 các tên này khớp đúng IN qua đường khác.

Thêm một điểm đáng ngờ: ứng viên trong `T52_mau_kiem.jsonl` có tên kiểu biệt dược hoặc kèm hàm lượng (`akudinir 50`, `telovyl 10`, `gardenal 100mg`, `bio taksym`) với `tty: "IN"`. Kiểm nguồn của các mục này.

## Phạm vi file

- **Được sửa:** `app/kb/dictionary/**`, `config/kb/tu_dien.yaml`, `tests/kb/test_dictionary_*.py`, `tests/kb/fixtures/tu_dien/**`, dữ liệu `data/kb_curated/tu_dien/**`, `data/kb_reports/T52_*`; thêm mục "## T52-fix-1" cuối `plan/reports/T52.md`.
- **Cấm đụng:** như brief T52, cộng `app/kb/resolver/**`, `data/kb_curated/tra_cuu/**`, `tests/kb/test_resolver*` (T53 đang chạy song song).

## Yêu cầu

1. **PIN → IN bằng quy tắc đặt tên RxNorm**, chạy khi không có quan hệ trong đệm:
   - Tên PIN của RxNorm có dạng `<tên IN> <phần muối/este>`.
   - Bỏ phần muối bằng danh sách muối dùng chung (`app/kb/names.py` + phần mở rộng của dictionary).
   - Nhận khi và chỉ khi **phần còn lại trùng chính xác đúng một IN** trong danh sách RxNorm, và tên PIN **bắt đầu bằng** tên IN đó.
   - Ghi `cach_khop` giữ nguyên cách khớp gốc, cộng thêm trường `pin_ve_in = "bo_muoi"` (hoặc tương đương), có `nguon_ban_ghi_ids` trỏ tới cả mục PIN và mục IN trong danh sách RxNorm.
   - Không trùng hoặc trùng nhiều thì giữ hành vi cũ (vào hàng duyệt).
2. **Không được lùi:**
   - Thêm kiểm bằng code trong `build`: mọi chế phẩm đủ thành phần ở bản T50 (lưu sẵn danh sách `thuoc_id` từ bản dựng trước, hoặc so với `T50_do_phu.csv` / tệp đã có) phải vẫn đủ, **với cùng tập `hoat_chat_id`**.
   - Có ca lệch thì liệt kê trong `data/kb_reports/T52_lui.jsonl` kèm lý do. `build` trả mã khác 0 nếu có ca lùi không thuộc danh sách lý do được phép.
   - Danh sách lý do được phép (ghi trong cấu hình) **ban đầu rỗng**.
3. **Kho ứng viên sạch:**
   - Tìm vì sao có mục như `gardenal 100mg`, `akudinir 50` mang `tty: "IN"`: từ đồng nghĩa biệt dược của trục, từ tệp RxNorm, hay do gộp nhầm.
   - Chỉ dùng tên IN/PIN thật của RxNorm, cùng tên và đồng nghĩa loại `inn` / `viet` / `muoi` của trục, làm ứng viên. **Bỏ** đồng nghĩa `biet_duoc` và tên có hàm lượng khỏi kho ứng viên.
   - Ghi kết quả điều tra vào báo cáo.
4. Dựng lại bằng `build`, `candidates --embedder fake`, `review`.

## Nghiệm thu (dán vào báo cáo)

- `T52_do_phu_truoc_sau.json` mới:
  - `so_che_pham_chuyen_ve_chua_du` = 0 (hoặc từng ca có lý do được phép, mà danh sách được phép đang rỗng nên phải = 0).
  - Dán số đủ thành phần trước / sau.
- Ví dụ trong báo cáo: `losartan potassium` → `losartan`; `metformin hydrochloride` → `metformin`; `ceftriaxone sodium` → `ceftriaxone`; `tenofovir disoproxil fumarate` → ghi rõ kết quả (IN của RxNorm có thể là `tenofovir disoproxil`; không ép).
- Test mới:
  - PIN → IN bằng bỏ muối, ca nhận và ca từ chối (trùng nhiều IN).
  - Kiểm không lùi phát hiện ca lùi.
  - Kho ứng viên không còn tên có hàm lượng.
  - Test chống thuốc tên gần nhau vẫn qua.
- `uv run ruff check app/kb tests/kb`, `ruff format --check` các tệp sửa, `uv run pytest -q tests/kb --basetemp=.pytest_t52f1` qua. Hoạt chất ca giả lập chưa khớp vẫn = 0.

## Cấm làm

- Không gọi mạng. Không commit. Không dùng `&`.
- Không ghép mờ vào bộ cuối.
- Không sửa tệp của T53.
