# T114 – Hằng số công thức bị bộ kiểm chứng chặn ("so_khong_co_nguon:3600")

Người làm: agy Neon xhigh (không gọi shell; Claude chạy nghiệm thu). Song song với T113-fix-2 và T112-fix-1, không đụng tệp của nhau.
Đọc trước: `AGENTS.md`; `app/llm/case_context.py` (`_format_calc_line`, `_add_number`, nơi dựng danh sách số được phép); `app/agent/tools/tinh_chi_so.py`; `app/calc/` (mọi công thức); `app/orchestration/ask.py` (`kiem_chung_tra_loi`, nhánh số).

## Lỗi (Claude tái hiện 26/11 bằng bộ chấm T113)

`HD-CA-011` (DEMO, "BSA Mosteller của người bệnh là bao nhiêu"): agent trả `khong_co_nguon` hai lần liền. Log: `ask rejected step=verification reason=so_khong_co_nguon:3600`. LLM giải thích công thức `√(chiều cao × cân nặng / 3600)`; số 3600 không nằm trong số được phép nên câu trả lời đúng bị chặn. Cùng rủi ro với hằng số của Cockcroft–Gault (140, 72, 0,85…), IBW Devine, AdjBW, Du Bois, CKD-EPI 2021.

## Sửa

1. Thêm vào `app/calc/` một bảng hằng `CONG_THUC_HIEN_THI: dict[str, str]`, mỗi công thức một chuỗi công thức dạng người đọc, **chép đúng từ code tính hiện có** (đọc thân hàm, không tự nhớ). Đặt trong tệp mới `app/calc/hien_thi.py`; không sửa hàm tính nào.
2. `app/llm/case_context.py`, `_format_calc_line`: thêm "· công thức: <chuỗi>" sau đầu vào; mọi số trong chuỗi công thức được thêm vào danh sách số được phép theo đúng cơ chế hiện có (`_add_number` hoặc tương đương). Dòng "không tính được" không thêm gì.
3. `app/agent/tools/tinh_chi_so.py`: nội dung tool thêm "công thức: <chuỗi>" (cùng bảng), nằm trong `noi_dung` của `CanCu` để số hằng được chấp nhận khi trích `tinh:`.
4. **Không** nới bộ kiểm chứng theo kiểu cho mọi số; chỉ số xuất hiện trong văn bản công thức của chỉ số **có trong ca / có trong kết quả tool lượt này**.

## Tệp

Tạo: `app/calc/hien_thi.py`, test trong `tests/calc/test_hien_thi.py`.
Sửa: `app/llm/case_context.py` (chỉ `_format_calc_line` và chỗ thêm số), `app/agent/tools/tinh_chi_so.py` (chỉ chuỗi nội dung), `app/calc/__init__.py` (xuất hằng), test liên quan trong `tests/llm/`, `tests/agent/test_tool_tinh_chi_so.py`, `tests/orchestration/`.
Báo cáo: `plan/briefs/T114-bao-cao.md`.
Cấm: sửa hàm tính trong `app/calc/`, `app/orchestration/ask.py`, `app/agent/tools/gateway.py`, `app/eval/`, `data/`, `web/`, cài gói, gọi mạng, commit.

## Test

- Mỗi khoá trong `CONG_THUC_HIEN_THI` khớp đúng một `cong_thuc` mà `app/calc` trả; đủ 7 công thức (`cockcroft_gault`, `egfr_ckd_epi_2021`, `bmi`, `bsa_mosteller`, `bsa_dubois`, `ibw_devine`, `adjusted_body_weight`).
- Tính lại kết quả bằng cách thế số vào hằng trong chuỗi (test tự viết biểu thức tương ứng) cho 1 bộ đầu vào mỗi công thức, khớp hàm tính tới 0,01: đảm bảo chuỗi không sai hằng.
- `kiem_chung_tra_loi` với gói ca DEMO-02 và câu trả lời có "3600" + kết quả BSA đúng, trích `tinh_toan` `bsa_mosteller` → qua. Câu trả lời có số lạ (vd 3700) → vẫn bị chặn.
- Gói ca vẫn không chứa PII (test cũ phải còn qua).

## Nghiệm thu (Claude chạy)

```
uv run ruff check app tests
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider tests/calc tests/llm tests/agent tests/orchestration
```
Claude chạy lại `HD-CA-011` bằng `tools/cham_hoi_dap.py` với LLM thật.
