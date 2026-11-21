# T97 – Tiến trình phân tích AI: backend

Đọc `AGENTS.md`, rồi `plan/plan-1.10-tien-trinh-ai-ui.md` (mục 4, 5, bảo mật). Bạn chỉ làm phần backend Python. KHÔNG gọi shell, KHÔNG gọi mạng, KHÔNG cài gói. Claude sẽ tự chạy pytest và ruff, nên hãy viết test cẩn thận và tự rà lại code bằng cách đọc.

## File được tạo hoặc sửa

- Tạo `app/orchestration/progress.py`
- Sửa `app/orchestration/jobs.py`, `app/orchestration/graph/nodes.py`, `app/orchestration/evidence.py` (chỉ nếu cần để lấy nhãn nguồn; ưu tiên làm trong nút), `app/llm/synthesizer.py`, `app/api/schemas.py`, `app/api/service.py`, `app/api/presenter.py` (nếu cần)
- Tạo test mới: `tests/orchestration/test_progress.py`, `tests/api/test_ai_progress.py` (đặt đúng thư mục test đang có)
- Cập nhật `plan/api-hop-dong-v1.1-bo-sung.md`: thêm mục ngắn "v1.10 – tiến trình" trỏ về plan 1.10.

CẤM đụng: `web/`, `app/verify/`, `app/rules/`, đồ thị (`builder.py`: thứ tự nút giữ nguyên), logic luật, chữ ký công khai của `AiRunner.run`, `Synthesizer.run`, `EvidenceCollector.collect`, `AiReviewer.run` (không đổi chữ ký; test cũ dùng bản giả).

## Yêu cầu

1. `progress.py` theo mục 5 của plan: `NguonTomTat(nhan, so_doan)`, `BuocTienTrinh(ma, ten, trang_thai, chi_tiet, nguon, thoi_gian_ms, ly_do, goi_y)` (pydantic, `extra="forbid"`, chuỗi cắt 160 ký tự), lớp `TienTrinh` an toàn đa luồng (`RLock`): `dang_ky(ma, ten)`, `bat_dau(ma, chi_tiet=None)`, `xong(ma, chi_tiet=None, nguon=None)`, `loi(ma, ly_do, goi_y=None)`, `them(ma, ten)` (nối bước mới, tối đa 40 bước, vượt thì bỏ qua im lặng), `chot(thanh_cong: bool)`, `chup(now=None) -> list[BuocTienTrinh]` (bước đang chạy có `thoi_gian_ms` = thời gian đã chạy; trả bản sao, không lộ tham chiếu nội bộ), `tong_ms(now)`. Dùng `time.perf_counter()`. `ContextVar` `tien_trinh_hien_tai` và hàm `ghi_buoc` an toàn khi không có bộ ghi (không ném lỗi).
2. `jobs.py`: mỗi tác vụ tạo `TienTrinh` với ba bước đăng ký sẵn (`thu_thap_nguon` "Lấy nguồn", `tong_hop_1` "Tổng hợp nhận định", `kiem_chung_1` "Kiểm chứng trích dẫn"), đặt vào ContextVar ngay trong `_run_job` (và reset bằng token khi xong) trước khi gọi `fn()`; lưu ở `AiJobState.tien_trinh` (trường `Any = None`, kèm `bat_dau`, `ket_thuc`); chốt khi kết thúc (`chot(True)` nếu trạng thái xong và kết quả AI không phải `loi_llm`, ngược lại `chot(False)`); ghi thời lượng các lượt xong vào danh sách tối đa 20 và cung cấp `thuong_le_ms()` (trung vị, `None` nếu dưới 3 mẫu). Giữ đúng hành vi cũ khác (thế hệ, hàng đợi, trần).
3. Điểm ghi sự kiện:
   - `ThuThapNguon.__call__`: bắt đầu bước `thu_thap_nguon`; xong thì `chi_tiet` "N đoạn từ M nguồn" và `nguon` nhóm theo `Chunk.nguon` (nhãn công khai, số đoạn, tối đa 8 nhóm, sắp theo số đoạn giảm dần); không có đoạn nào thì chi tiết "Không tìm thấy đoạn nguồn phù hợp" và vẫn xong. Nếu ném ngoại lệ thì `an_toan` đánh dấu `loi` với `ly_do` "Không lấy được nguồn" (không kèm thông điệp ngoại lệ) và `goi_y` "Thử lại; bảng luật vẫn dùng được".
   - `Synthesizer._run_with_llm`: mỗi lượt n: bước `tong_hop_n` bắt đầu (lượt 1 dùng bước đăng ký sẵn; lượt ≥2 gọi `them` với tên "Tổng hợp lại, lần n"), `chi_tiet` "Đang gọi mô hình"; nhận được đầu ra thì xong; sai lược đồ thì `chi_tiet` "Đầu ra sai định dạng, thử lại"; rồi bước `kiem_chung_n` ("Kiểm chứng trích dẫn" hoặc "Kiểm chứng lại, lần n"), xong với `chi_tiet` "x/y dòng đạt". Lỗi nhà cung cấp: bước `tong_hop_n` thành `loi`, `ly_do` theo mã (`het_han_muc_token` → "Vượt hạn mức độ dài", còn lại → "Nhà cung cấp mô hình báo lỗi"), `goi_y` "Bảng luật vẫn đúng; bấm Thử lại sau ít phút". Cả hai ghi qua `ghi_buoc`; khi không có bộ ghi thì không làm gì (test cũ phải xanh nguyên vẹn).
   - Đường tuần tự cũ `AiReviewer._run_sequential` KHÔNG cần ghi sự kiện (ghi chú trong docstring: engine mặc định là langgraph); nhưng nếu dễ thì bọc hai bước thu thập và tổng hợp.
4. `schemas.py`: `NguonTomTat`, `BuocAI` (theo bảng mục 4 plan, `ApiModel`), và `KetQuaAI` thêm `cac_buoc: list[BuocAI] = []`, `da_chay_ms: float | None = None`, `thuong_le_ms: float | None = None`.
5. `service.py`: `_present_job_state`, `start_ai`, `get_ai` gắn ba trường vào `KetQuaAI` (dùng `model_copy(update=...)`) cho cả `dang_chay`, `xong`, `loi`; trạng thái `tat` thì để mặc định. `da_chay_ms` = tổng thời gian tại lúc trả lời (đang chạy) hoặc tổng (đã kết thúc).

## Bảo mật (tiêu chí nghiệm thu)

- Không có chuỗi nào lấy từ hồ sơ, tên thuốc theo ca, nội dung prompt hay đầu ra mô hình, hay `str(exc)` đi vào `chi_tiet`, `ly_do`, `goi_y`, `nguon`. Mã lỗi nhà cung cấp chỉ dùng khi `isascii() and isidentifier()`.
- Test: tạo ca có tên người bệnh/chuỗi nhận diện, chạy tác vụ với bản giả, serialize `cac_buoc` thành JSON, khẳng định chuỗi đó không xuất hiện; khẳng định không quá 40 bước và mọi chuỗi ≤160 ký tự.
- Test hai tác vụ song song không lẫn bước (ContextVar không rò).
- Không ghi nội dung bước vào log.

## Nghiệm thu (Claude sẽ chạy)

`uv run pytest tests/orchestration tests/api tests/llm -q`, `uv run pytest -q` toàn bộ, `uv run ruff check .`. Test cũ giữ nguyên xanh; chỉ được sửa test cũ khi hợp đồng thật sự đổi (chỉ thêm trường). Cuối việc viết báo cáo ngắn vào `plan/briefs/T97-bao-cao.md`: file đã đổi, quyết định tự chọn, điều chưa chắc.
