# T55-fix-3 – Sửa diễn đạt yếu tố 4 và cập nhật hai test tích hợp

Mô hình: Codex `gpt-6.1-sol`, effort `xhigh`. Không có mạng.

Đọc: `AGENTS.md`, `plan/api-hop-dong-v1.6-ma-tran-tuong-tac.md`, `plan/reports/T55.md` (mục T55-fix-1, T55-fix-2).

## Bối cảnh (Claude gọi thật `GET /api/cases/HS-024` và DEMO-02 ngày 19/11)

Luật đúng về kết luận, nhưng diễn đạt có ba lỗi.

1. **Nhận xét lặp và khó đọc.**
   - Hiện tại: `Amiodaron 200 mg + Digoxin 0,25 mg: (amiodarone × digoxin – Major – Distribution): DDInter. Sàng lọc, cần đối chiếu nhãn.`
   - Với cặp thiếu dữ liệu thì tên thuốc bị lặp hai lần: `Amiodaron 200 mg + Paracetamol 500 mg: (amiodarone × paracetamol): Amiodaron 200 mg + Paracetamol 500 mg (amiodarone × paracetamol…`.
2. **Mức `Unknown` của DDInter hiện nguyên tiếng Anh** trong `tom_tat`, `ly_do`, nhận xét.
3. **Ca chỉ một thuốc** (DEMO-02) ghi `ket_luan=dat` với mô tả "Không có cặp cần báo ở dòng chờ duyệt. Sàng lọc, cần đối chiếu nhãn.", dễ hiểu nhầm là đã đối chiếu tương tác.

Ngoài ra còn hai test trượt vì kỳ vọng cũ: `tests/api/test_routes.py::test_demo02_detail`, `tests/db/test_reader.py::test_cache_refresh_and_review`.

## Phạm vi

**Được sửa:**
- `app/rules/interaction.py`, `app/kb/interactions/**`
- `app/api/presenter.py` (chỉ phần dựng nhận xét yếu tố 4, nếu lặp do presenter)
- `tests/rules/test_interaction*.py`, `tests/kb/test_interactions*.py`
- `tests/api/test_routes.py`, `tests/db/test_reader.py`, test API khác liên quan yếu tố 4
- Test web nếu chuỗi hiển thị đổi
- Mục "## T55-fix-3" trong `plan/reports/T55.md`

**Cấm đụng:** luật khác, `app/kb/resolver/**`, `app/kb/dictionary/**`, `app/llm/**`, `app/orchestration/**`, `data/**`, hợp đồng API (không đổi tên trường).

## Yêu cầu

1. **Mẫu nhận xét (tiếng Việt, một câu chính và một câu nguồn), không lặp tên.**
   - Có tương tác: `Amiodaron 200 mg × Digoxin 0,25 mg: tương tác mức nặng (DDInter: Major, cơ chế Distribution). Nguồn sàng lọc, cần đối chiếu nhãn.` Moderate → "mức trung bình", Minor → "mức nhẹ".
   - Thiếu dữ liệu: `Amiodaron 200 mg × Paracetamol 500 mg: chưa đủ dữ liệu tương tác (DDInter ghi mức chưa rõ).` Thiếu `ddinter_id` hoặc không phân giải: nêu đúng lý do, ví dụ "chưa có dữ liệu DDInter cho sulbactam".
   - Giữ nguyên tên mức gốc của DDInter **trong ngoặc** để truy vết, nhưng phần tiếng Việt phải là chính.
2. **`Unknown`:** trong mọi chuỗi hiển thị (`tom_tat`, `ly_do`, nhận xét) đổi thành "chưa rõ (DDInter: Unknown)". Giá trị dữ liệu nội bộ (`muc_do` trong bảng) giữ nguyên.
3. **Một thuốc / không có cặp nào có dòng chờ duyệt:**
   - Phát hiện yếu tố 4 phải nói rõ: `Y lệnh chỉ có một thuốc đang hiệu lực, không có cặp để đối chiếu tương tác.`
   - Chọn `ket_luan`: giữ `dat` (yếu tố đã xét, không có nguy cơ tương tác vì không có cặp) **hoặc** đổi sang mức thông tin, theo cách ít gây hiểu nhầm nhất mà không đổi hợp đồng; ghi lý do vào báo cáo.
   - **Không** được để câu "sàng lọc, cần đối chiếu nhãn" ở trường hợp này, vì không có gì để đối chiếu.
4. Khi có cặp nhưng không cặp nào cần báo: `Đã đối chiếu N cặp thuốc, không phát hiện tương tác trong dữ liệu DDInter.` Kèm câu nguồn sàng lọc.
5. Cập nhật hai test tích hợp theo hành vi mới. Thêm test cho ba mẫu câu (có tương tác, thiếu dữ liệu, một thuốc) và cho việc không còn lặp tên thuốc.

## Nghiệm thu

- `uv run pytest -q --basetemp=.pytest_t55f3` toàn kho **0 trượt**; `uv run ruff check .`, `ruff format --check` các tệp sửa.
- Nếu đổi chuỗi web: chạy `npx vitest run`, `npx tsc -b` trong `web/`.
- Dán nhận xét thật của HS-024 (mọi cặp) và DEMO-02 vào báo cáo. Dùng TestClient; chế độ tệp dùng DEMO-02, các ca HS chỉ có ở chế độ DB nên nếu không có thì dùng ca giả lập trong bộ nhớ.

## Cấm làm

Không gọi mạng. Không commit. Không dùng `&`. Không đổi kết luận / mức của cặp.
