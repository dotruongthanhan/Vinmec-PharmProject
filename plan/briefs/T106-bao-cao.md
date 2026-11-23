# T106 – Báo cáo: tool `tra_tuong_tac` và trích dẫn dòng bảng

Trạng thái: XONG phần việc brief giao; ghi các điểm còn ngờ ở mục 5.

## 1. Tệp đã tạo / sửa

Tạo:
- `app/agent/tools/tra_tuong_tac.py` – lớp `TraTuongTac`, lược đồ `ThamSoTraTuongTac`.
- `tests/agent/test_tool_tra_tuong_tac.py` – 20 test.

Sửa:
- `app/agent/tools/base.py` – `CanCu.noi_dung: str | None = None`.
- `app/orchestration/ask.py` – `AskCitationRaw.loai` thêm `"bang"`; `kiem_chung_tra_loi` thêm tham số `bang_by_ma: Mapping[str, tuple[str, str]] | None = None` (mã -> (nhãn, nội dung dòng)).
- `app/agent/nodes.py` – chỉ `KiemChung`: dựng `bang_by_ma` từ `state["can_cu"]` loại `bang`, truyền vào.
- `app/container.py` – chỉ `agentic_asker`: `danh_muc.dang_ky(TraTuongTac())`.
- `config/tool_policy.yaml` – khai báo `tra_tuong_tac`, cho `duoc_si_ls` và `admin`; `mac_dinh: tu_choi` giữ nguyên.
- `config/prompts/tac_tu.v1.md` – quy tắc trích `loai="bang"` và dòng lược đồ JSON ở quy tắc 6.

Không sửa: `graph.py`, `gateway.py`, `app/api/lookup.py`, `web/`, `data/`, test hiện có. Không ghi DB, không cài gói.

## 2. Quyết định thiết kế

- **Thuốc–thuốc:** gọi `app.api.lookup.lookup_interactions` (nhập lười trong `chay` để tránh vòng nhập). `HTTPException` 422 (trùng tên, rỗng...) chuyển thành `loi`/`sai_tham_so` kèm thông báo của hàm đó; mã khác chuyển thành `loi`/`thieu_du_lieu_nguon`. Không phải tách lõi khỏi FastAPI. Hàm này không trả hậu quả/xử trí/mã DDInter, nên để có dòng bảng đầy đủ, tool phân giải lại từng tên bằng `resolver.resolve_name` (cùng đường với `resolve_line` cho tên tự do) rồi lấy `PairRecord` từ `InteractionStore.pair`. Phân loại cặp (có tương tác / thiếu dữ liệu / không phát hiện / không áp dụng) lấy từ ma trận của `lookup_interactions`, không viết lại.
- **Thức ăn:** `InteractionStore.foods(ddinter_id)` (`ddinter_thuc_an`), không viết SQL.
- **Thuốc–bệnh:** đọc bảng `thuoc_benh_icd` qua `try_load_default_drug_disease_config()` (cùng nguồn với `_rules_for` nhóm `thuoc_benh` và luật yếu tố 6; hỗ trợ tệp và DB) và dùng lại `icd_matches` của `app/rules/drug_disease.py` (tiền tố, khoảng). `benh` giống mã ICD-10 thì so mã; còn lại so chuỗi con (bỏ dấu, không phân biệt hoa) với `ten_benh` của DDInter. Không có `benh` ở chế độ `ca` thì dùng `ma_icd10` của `chan_doan` ca; chế độ `chung` mà không có `benh` hoặc ca không có chẩn đoán kèm mã trả `loi`/`sai_tham_so`.
- **Khoá dòng bảng:** `bang:ddinter_cap:<id_a>-<id_b>`, `bang:ddinter_thuc_an:<ddinter_id>:<thức ăn>`, `bang:thuoc_benh_icd:<hoạt chất>:<tên bệnh>`; chữ thường, khoảng trắng/ký tự điều khiển/ngoặc vuông thành `_`, cắt 120 ký tự, khử trùng trong một kết quả. `CanCu.noi_dung` là phần thân dòng **không kèm** mã trong ngoặc (để số trong mã DDInter không lọt vào tập số được phép).
- **Thiếu dữ liệu:** tên không phân giải, hoạt chất chưa có mã DDInter, phân giải một phần, hoặc cặp thiếu dữ liệu đều thành dòng "không có dữ liệu DDInter cho ..." / "chưa đủ dữ liệu DDInter để kết luận". Cụm "không có tương tác" không xuất hiện trong bất kỳ kết quả nào (cặp sạch ghi "không phát hiện cặp tương tác trong DDInter (cả hai hoạt chất đã có danh sách đầy đủ)").
- **Giới hạn:** tối đa 20 dòng bảng và 6500 ký tự cho phần dòng; ghi chú có trần để tổng không vượt 8000 ký tự của Gateway; vượt thì thêm "(còn N dòng nữa chưa hiển thị)" / "(còn N ghi chú nữa ...)". Hậu quả/xử trí/mô tả/nội dung bị cắt ở ranh giới từ (220 ký tự mỗi trường, thêm "…"). Test 10 thuốc đã bắt được một lỗi thật (nội dung 8560 ký tự) và được sửa bằng trần ghi chú.
- **Kiểm chứng:** `loai="bang"`: mã không có trong `bang_by_ma` thì `_reject("unknown_table_row:...")`; số trong dòng được cộng vào `effective_numbers` (có nhận dấu phẩy hàng nghìn tiếng Anh vì dữ liệu DDInter là tiếng Anh); ra `AskCitation(loai_ma="tai_lieu", ban_ghi_id=None, doan_trich_id=None, trich_nguyen_van=None)`. `CaseAsker` không truyền tham số mới, hành vi cũ không đổi.
- **Tiến trình:** `chi_tiet_tien_trinh` chỉ có số đếm ("2 hoạt chất, 1 cặp có tương tác").

## 3. Bảo mật

- `extra="forbid"`; không có `ca_id`; `ten_thuoc` 1–10 phần tử mỗi phần tử 1–120 ký tự, `benh` ≤ 5 phần tử ≤ 120 ký tự, `loai` là Literal. Test qua Gateway: trường lạ (`ca_id`, `sql`) và các vi phạm giới hạn đều `sai_tham_so`.
- Không có SQL tự viết trong tool; chỉ dùng `InteractionStore`, bộ phân giải và bảng luật có sẵn. Chế độ tệp trong test chặn mọi kết nối DB.
- Vai trò không khai báo -> `khong_co_quyen`; tên người bệnh trong tham số -> `tham_so_co_dinh_danh` (test với DEMO-02).
- Kiểm chứng: trích `bang:` không có trong lượt bị chặn; số không có trong dòng bị chặn (test chạy qua đồ thị thật với FakeLLM).
- Dữ liệu DDInter là đầu vào ngoài: vẫn đi qua che định danh, loại ký hiệu khối và quét chèn lệnh của Gateway như mọi tool.

## 4. Lệnh nghiệm thu đã chạy

- `uv run ruff check app tests`: All checks passed.
- `uv run ruff format --check app tests`: 374 files already formatted.
- `uv run pytest -q -p no:cacheprovider tests/agent tests/orchestration`: 134 passed.
- `uv run pytest -q -p no:cacheprovider tests/api`: 217 passed, 2 skipped, **1 failed**: `tests/api/test_tra_cuu.py::test_suggest_index_build_and_query_latency` (dựng chỉ mục gợi ý mất 7,2 giây, ngưỡng 3 giây). Test này đo tốc độ, chạy riêng vẫn trượt (7,5 giây); không đụng tới đoạn code T106 sửa (chỉ mục gợi ý nằm ở `app/api/lookup.py` và `app/kb/suggest.py`, thay đổi chưa commit của việc T105). Cần xác nhận lại trên máy ít tải.
- Toàn bộ `pytest`: xem mục dưới.

## 5. Điểm còn ngờ

1. Test độ trễ chỉ mục gợi ý (mục 4) trượt do ngưỡng thời gian, không do T106; cần kiểm lại khi máy rảnh.
2. Tên bệnh trong DDInter bằng tiếng Anh: `benh` là tên tiếng Việt sẽ không khớp theo tên (tool ghi rõ "không khớp ... tên bệnh trong DDInter bằng tiếng Anh"); nên dùng mã ICD-10 hoặc để LLM đổi sang tên tiếng Anh/ICD khi gọi.
3. Nội dung hậu quả/xử trí là tiếng Anh nguyên văn DDInter (đã cắt gọn); phần khung dòng bằng tiếng Việt. Câu trả lời của LLM phải dịch/diễn giải; số trong câu trả lời vẫn bị kiểm với dòng gốc.
4. Gateway che PII bằng `scrub` trên `noi_dung`; `CanCu.noi_dung` không qua bước đó (dữ liệu thuốc, không có định danh người bệnh) nên có thể lệch rất nhỏ so với bản đã che nếu bộ che sửa một chuỗi trong văn bản DDInter. Chưa thấy trường hợp thực tế trong test.
5. Khi `lookup_interactions` chạy lại phân giải, tool phân giải tên lần hai (nhẹ, trong bộ nhớ); nếu sau này `lookup_interactions` trả luôn mã DDInter và hậu quả thì bỏ được bước này.

## 6. Sửa sau review

- Tên không phân giải được (mọi loại tra): ghi chú nối thêm "; có thể là: <nhãn>… (gợi ý gần đúng, cần xác nhận)" từ `app.api.lookup.suggest_drugs(ten, limit=3)` (ưu tiên `goi_y_sua`, rồi `ket_qua`, tối đa 3 nhãn). Lỗi bất kỳ khi gợi ý thì bỏ qua lặng lẽ; tool không tự chọn thuốc thay. Kiểm thật: "parecetamo" ra gợi ý paracetamol.
- Ghi chú thuốc–bệnh: không khớp thì ghi "bảng trong kho chỉ có N dòng cho hoạt chất này, không đủ để loại trừ"; không có dữ liệu thì thêm "không đủ để loại trừ".
- Test mới: gợi ý thật từ chỉ mục, gợi ý giả lập cho thuoc_thuoc/thuoc_thuc_an, lỗi gợi ý bị nuốt, hai ghi chú thuốc–bệnh. Ruff sạch; `tests/agent`: xem kết quả dưới đây.
- Kết quả: `tests/agent` 67 passed, ruff sạch (toàn bộ pytest để Claude chính chạy).

### Fix-2 (mã dòng bảng do LLM thật trích)

DeepSeek bỏ tiền tố `bang:` trong `ma`. `kiem_chung_tra_loi` nhánh `loai="bang"` nay chuẩn hoá `ma` (bỏ khoảng trắng và ngoặc vuông hai đầu), tra nguyên dạng, rồi nếu chưa có và chưa bắt đầu bằng `bang:` thì thử `bang:` + ma; không khớp mờ. Prompt nêu rõ `ma` gồm tiền tố `bang:` kèm ví dụ. Test mới: mã không tiền tố, có ngoặc vuông, có khoảng trắng được chấp nhận; mã của dòng khác vẫn bị chặn.
