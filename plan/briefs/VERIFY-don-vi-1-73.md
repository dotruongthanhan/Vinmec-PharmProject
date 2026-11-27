# VERIFY-don-vi-1-73 – Bộ kiểm chứng số coi "1,73 m²" trong đơn vị eGFR là số không có nguồn

Người làm: Codex `gpt-6.1-terra` high. Đọc `app/verify/number.py`, `app/verify/pipeline.py`, `app/orchestration/ask.py` (chỗ gọi kiểm chứng câu trả lời hỏi đáp), các test trong `tests/verify/**`, `tests/orchestration/**`.

## Lỗi thật (28/11 01:26, bản deploy, engine `co_dinh`, `gemini-3.5-flash-lite`, ca DEMO-02, câu "cho tôi bảng thống kê")

Vết `1cfcaab1`: LLM trả lời 2 lần, cả 2 lần `kiem_chung_tra_loi` đều `tu_choi` với `ma_ly_do: ["so_khong_co_nguon:1.73"]`. Dược sĩ chỉ nhận "Không có nguồn phù hợp". Số `1.73` gần như chắc chắn là một phần của **đơn vị** eGFR "mL/phút/1,73 m²" (hoặc `mL/min/1.73m2`), không phải số liệu.

## Yêu cầu (hẹp, không nới kiểm chứng số nói chung)

1. Trong bước tách số để kiểm chứng, nhận diện cụm **đơn vị chuẩn hoá theo diện tích da** và **không** coi số trong cụm là số cần nguồn. Các biến thể cần nhận:
   - `/1,73 m²`, `/1.73 m²`, `/1,73m²`, `/1.73m2`, `/1.73 m^2`;
   - có hoặc không có khoảng trắng, có `mL/phút` hoặc `mL/min` đứng trước.
2. **Chỉ** khi số 1,73 đứng ngay sau dấu `/` và ngay trước `m²`/`m2`/`m^2`. Số `1,73` đứng một mình (ví dụ "BSA 1,73 m²" không có `/` trước) vẫn phải có nguồn như cũ.
3. Áp dụng chung cho mọi đường dùng bộ kiểm số: `co_dinh`, agentic, tổng hợp nhận định. Không đổi các quy tắc khác. Không thêm danh sách số "luôn cho qua".
4. Test:
   - câu "eGFR 45 mL/phút/1,73 m² [1]" với nguồn có 45 → đạt;
   - cùng câu nhưng nguồn không có 45 → vẫn trượt vì 45;
   - "BSA 1,73 m²" không nguồn → trượt;
   - các biến thể ở mục 1 → đạt;
   - test cũ của `app/verify` không đổi kết quả.

## Tệp

`app/verify/number.py` (hoặc nơi tách số), `tests/verify/**`. Báo cáo: `plan/briefs/VERIFY-don-vi-1-73-bao-cao.md`.
**Cấm:** nới kiểm chứng ngoài đúng mẫu đơn vị trên; đọc `.env`; mạng; cài gói; commit.

## Nghiệm thu

```
uv run ruff check app tests && uv run pytest -q -p no:cacheprovider tests/verify tests/orchestration tests/agent
```
Claude hỏi lại câu trên ở web và chạy lại bộ chấm 90 câu nếu cần.
