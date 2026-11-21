# T99 – Tiến trình hỏi đáp: backend

Đọc `AGENTS.md`, `plan/plan-1.10-tien-trinh-ai-ui.md` (mục 4, 5 và đặc biệt mục 10), và code đã có của T97: `app/core/progress.py` (`TienTrinh`, `ghi_buoc`, `tien_trinh_hien_tai`), `app/orchestration/jobs.py`. KHÔNG gọi shell, KHÔNG gọi mạng, KHÔNG cài gói. Claude sẽ tự chạy pytest và ruff.

## File được tạo hoặc sửa

- `app/core/progress.py`: thêm `AskProgressRegistry` (và hằng số giới hạn).
- `app/orchestration/ask.py`: chỉ thêm các lời gọi `ghi_buoc` / cập nhật bước trong `CaseAsker.ask` và `ask_global`; KHÔNG đổi chữ ký, logic che định danh, truy xuất, kiểm chứng hay nội dung trả về.
- `app/api/service.py`: bọc `ask` (cả nhánh ca và `__global__`) để tạo mục sổ đăng ký, đặt ContextVar `tien_trinh_hien_tai`, chốt khi xong (`chot(True/False)` theo `result.trang_thai == "ok"`), reset ContextVar trong `finally`; thêm `get_ask_progress(case_id, principal)`.
- `app/api/schemas.py`: `TienTrinhHoiDap` theo mục 10 (dùng lại `BuocAI`).
- `app/api/routes.py`: `GET /cases/{ca_id}/ask/tien-trinh` và `GET /ask/tien-trinh` (quyền `Caller`, response_model `TienTrinhHoiDap`). Đặt route tĩnh `/ask/tien-trinh` trước mọi route có tham số nếu cần để không bị nuốt.
- `plan/api-hop-dong-v1.2-hoi-dap.md`: thêm mục ngắn "v1.10 – tiến trình hỏi đáp" trỏ về plan 1.10 mục 10.
- Test mới: `tests/api/test_ask_progress.py`, bổ sung `tests/orchestration/test_progress.py` cho sổ đăng ký (đặt đúng thư mục test đang có).

CẤM đụng: `web/`, `app/verify/`, `app/rules/`, các chữ ký công khai (`CaseAsker.ask`, `ask_global`, `AskRunner`, `AiRunner`), logic giới hạn tốc độ/ngân sách, lịch sử hội thoại (`_server_history_pairs`, `_save_chat_log`), `app/orchestration/graph/`.

## Yêu cầu

1. `AskProgressRegistry` (an toàn đa luồng, `RLock`): khoá `(ca_id, nguoi_dung_id)`; `bat_dau(khoa, cac_buoc_dang_ky) -> (token, TienTrinh)` (mục mới thay mục cũ cùng khoá, ghi `token` để mục cũ chốt muộn không xoá mục mới); `ket_thuc(khoa, token, thanh_cong)` (chốt bước, ghi thời điểm xong, giữ 60 giây); `doc(khoa) -> (dang_chay, list[BuocTienTrinh], tong_ms) | None` (dọn mục quá 60 giây sau khi xong); tối đa 200 mục (đẩy mục tạo sớm nhất). Dùng `time.monotonic()` cho hạn 60 giây.
2. `service.ask`: tạo mục ở đầu (ngay sau khi biết `case_id` và `principal`, trước các thao tác chậm), đăng ký bước theo mục 10 (theo ca: `chuan_bi`, `truy_xuat`, `goi_mo_hinh`, `kiem_chung`; chung: `chuan_bi` tên "Tổng hợp danh sách y lệnh", `goi_mo_hinh`, `kiem_chung`; bỏ `truy_xuat` nếu nhánh chung không truy xuất, tự chọn). Mọi đường thoát (return sớm, ngoại lệ HTTPException 429 do giới hạn, lỗi) phải kết thúc mục trong `finally`. Với 429: chốt thất bại với `ly_do` "Vượt giới hạn lượt hỏi", `goi_y` "Chờ ít giây rồi hỏi lại" (không đưa thông điệp ngoại lệ).
3. `CaseAsker.ask`: ghi bước theo diễn biến thật: `chuan_bi` (bắt đầu ngay đầu hàm; xong sau khi dựng `bundle`/ngữ cảnh), `truy_xuat` (bắt đầu trước `_retrieve_chunks`; xong với chi tiết "N đoạn từ M nguồn" theo `Chunk.nguon` công khai, hoặc "Không dùng tra cứu nguồn" khi `used_retrieval` sai), `goi_mo_hinh` (mỗi lượt của vòng `for attempt`; lượt 2 dùng `them` với tên "Soạn lại, lần 2"), `kiem_chung` (mỗi lượt; xong với "Đạt" hoặc lỗi nhẹ "Không đạt, thử lại" khi `_AskVerificationError` và còn lượt). Lỗi cuối cùng (`except Exception`, `ProviderError`): đánh dấu bước đang chạy là `loi` với `ly_do` theo mã đã lọc (`het_han_muc_token` → "Vượt hạn mức độ dài", lỗi kết nối → "Không kết nối được nhà cung cấp mô hình", còn lại → "Không soạn được câu trả lời") và `goi_y` "Bấm Thử lại sau ít phút". Gọi `ghi_buoc` ngoài mọi lambda chạy ở luồng khác (`_run_with_deadline` chạy `llm.complete_json` có thể ở luồng khác nên ContextVar không đi theo; đặt lời gọi `ghi_buoc` ở luồng gọi).
4. `ask_global` tương tự nhưng gọn.
5. `get_ask_progress`: lấy `principal.nguoi_dung_id` (nếu `None` thì dùng khoá "__anonymous__" như `_enforce_llm_limits`), trả `TienTrinhHoiDap`; không có mục → `dang_chay=False, cac_buoc=[], da_chay_ms=None`. Không kiểm `case_id` tồn tại (không 404). Giới hạn độ dài `ca_id` path ≤ 128 (nếu cách kiểm chung của kho đã có thì dùng nó).

## Bảo mật (tiêu chí nghiệm thu)

- Không chuỗi nào lấy từ câu hỏi, câu trả lời, hồ sơ, tên thuốc theo ca, prompt, hay `str(exc)` đi vào `chi_tiet`/`ly_do`/`goi_y`/`nguon`. Test: đưa chuỗi nhận diện (ví dụ "BENHNHAN-XYZ") vào câu hỏi và vào ca giả, serialize `TienTrinhHoiDap` thành JSON, khẳng định không xuất hiện.
- Test cách ly: người dùng B gọi điểm cuối không thấy bước của người dùng A (cùng `ca_id`).
- Test: mục xong được đọc lại đúng một lần trong 60 giây với `dang_chay=False`; sau hạn thì rỗng (giả lập đồng hồ).
- Test: 429 do giới hạn vẫn chốt mục (không treo "đang chạy").
- Test: hai câu hỏi liên tiếp cùng khoá không để mục cũ xoá mục mới (token).
- ≤ 40 bước, chuỗi ≤ 160 ký tự, không ghi nội dung bước vào log.
- Test cũ của `ask` giữ nguyên xanh; `TraLoi` và hành vi POST không đổi.

## Nghiệm thu (Claude sẽ chạy)

`uv run pytest tests/orchestration tests/api tests/llm -q`, `uv run pytest -q` toàn bộ, `uv run ruff check .`, `uv run ruff format --check app tests`. Cuối việc viết `plan/briefs/T99-bao-cao.md`: file đổi, quyết định tự chọn, điều chưa chắc.
