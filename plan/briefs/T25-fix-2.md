# T25-fix-2 – dọn 8 test trượt sau T25-fix-1 và lần tải openFDA thật

## 1. Bối cảnh

T25-fix-1 (truy vấn openFDA nhiều bậc, ba kết cục) đã đạt phần dữ liệu khi người review chạy thật ngày 17/11: 50/50 nhãn đúng đường dùng, NDC 50/50, `python -m app.kb.build` ra `labels=50/50 chunks=3730 over_max=0 under_50=0 empty_act=0`. Nhưng toàn kho còn **8 test trượt, 696 qua**. Cả 8 đều do test chưa theo kịp hành vi mới hoặc gắn cứng số liệu; code sản phẩm được coi là đúng.

Lệnh tái hiện:

```bash
uv run pytest -q -p no:cacheprovider --ignore tests/db/.tmp --ignore tests/kb/.tmp --ignore tests/architecture/.tmp --ignore tests/api/.tmp
```

## 2. Tám test và hướng sửa

| # | Test | Nguyên nhân | Hướng sửa |
| :-: | :--- | :--- | :--- |
| 1 | `tests/kb/test_fetch.py::test_query_encodes_spaces_and_special_characters_without_injection` | Truy vấn bậc 1 nay viết hoa tên hoạt chất và bỏ `.exact` ở `product_type`, `route` | Cập nhật chuỗi mong đợi theo hành vi mới; **giữ nguyên ý kiểm chống chèn**: dấu `"` vẫn phải được thoát, ký tự đặc biệt vẫn được mã hoá |
| 2 | `…::test_retry_and_failure_continue_with_next_drug` | Kết cục `that_bai` nay tách thành `loi_ket_noi` / `khong_co_ung_vien_hop_le` / `khong_tim_thay` | Đổi giá trị mong đợi sang kết cục đúng theo tình huống của test |
| 3, 4 | `…::test_malformed_results_are_reported_and_next_drug_continues[openfda]`, `[ndc]` | Như trên | Như trên. Nếu phản hồi sai định dạng mà code xếp vào `loi_ket_noi` là **không hợp lý về nghĩa** thì dừng lại, nêu trong báo cáo, không tự đổi code |
| 5 | `…::test_ndc_requires_all_pages_before_writing[True]` | Như trên | Như trên |
| 6 | `tests/kb/test_names.py::test_hoat_chat_json_unique_and_covers_all_manifest_labels` | Hàm đọc manifest của test chỉ xem phần tử đầu của danh sách; nay phần tử đầu là tệp DDInter (không có `ten_goi`) | Sửa hàm trợ giúp trong test: lấy danh sách `tep`, lọc theo `nguon == "openfda_drug_label"`, không phụ thuộc thứ tự |
| 7 | `tests/kb/test_openfda_source.py::test_load_real_meropenem_label` | Cùng nguyên nhân với #6 (`StopIteration`) | Cùng cách sửa |
| 8 | `tests/db/test_mapping.py::test_kb_preserves_every_chunk_field_and_renal_values` | Gắn cứng `3738` đoạn; kho nay có 3730 | Không gắn cứng: so với số dòng không rỗng của `data/kb_curated/chunks.jsonl` và số tài liệu phân biệt đọc từ chính tệp đó |

## 3. Phạm vi file

Được sửa: `tests/kb/test_fetch.py`, `tests/kb/test_names.py`, `tests/kb/test_openfda_source.py`, `tests/db/test_mapping.py`.

Cấm đụng: mọi thứ trong `app/`, `web/`, `data/`, `config/`, `db/`, `plan/` (trừ tệp báo cáo được chỉ định khi gọi). Một phiên agent khác đang sửa `web/`. Không xoá, không tạo thư mục `.tmp` trong kho; test dùng `tmp_path` của pytest.

## 4. Yêu cầu

- Không xoá test, không đánh dấu `skip` / `xfail`, không nới điều kiện kiểm để cho qua.
- Thấy lỗi thật trong code sản phẩm thì ghi vào báo cáo kèm bằng chứng, không sửa.
- Không cần mạng. Không gọi openFDA, không gọi LLM.

## 5. Nghiệm thu

```bash
uv run ruff check tests/kb tests/db --exclude tests/kb/.tmp --exclude tests/db/.tmp
uv run ruff format --check tests/kb tests/db --exclude tests/kb/.tmp --exclude tests/db/.tmp
uv run pytest -q -p no:cacheprovider --ignore tests/db/.tmp --ignore tests/kb/.tmp --ignore tests/architecture/.tmp --ignore tests/api/.tmp
```

Đích: 0 test trượt, số test không giảm so với 704.

## 6. Cấm làm

Không commit, không push. Không in giá trị trong `.env`. Trả lời theo mẫu trong `AGENTS.md`.
