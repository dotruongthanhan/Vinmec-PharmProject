# T55-fix-4 – Bỏ chuỗi "None" của DDInter và ngoặc lồng nhau ở yếu tố 4

Mô hình: Codex `gpt-6.1-sol`, effort `xhigh`. Không có mạng, không cần mạng.

Đọc: `AGENTS.md`, `plan/reports/T55.md` (các mục fix-1 → fix-3).

## Bối cảnh (Claude review tổng D0 + D1 ngày 19/11, sau khi cào đủ 27.936 trang chi tiết cặp)

Bảng `data/kb_curated/tuong_tac/ddinter.sqlite` đã dựng lại. Mọi cặp nặng / trung bình trong 66 ca đều có hậu quả và xử trí. Còn hai lỗi diễn đạt:

1. **"Hậu quả: None".** Trang DDInter của cặp mức `Unknown` ghi đúng chữ `None` ở ô mô tả. Bộ dựng (`app/kb/interactions/build.py:_text`) giữ nguyên chuỗi đó, nên 10.751 cặp (toàn bộ là `Unknown`) có `hau_qua = 'None'`, và căn cứ hiện `Hậu quả: None`. Đúng ra phải là `Hậu quả: thiếu`.
   Ví dụ: HS-024, amiodarone × paracetamol; HS-031, spironolactone × furosemide.
2. **Ngoặc lồng nhau:** `app/rules/interaction.py:125` sinh `DDInter ghi mức chưa rõ (DDInter: Unknown)`. Khi đặt trong ngoặc của câu nhận xét thì thành `(DDInter ghi mức chưa rõ (DDInter: Unknown))`.

## Phạm vi

**Được sửa:**
- `app/kb/interactions/build.py`
- `app/rules/interaction.py`
- `tests/kb/test_interactions*.py`, `tests/rules/test_interaction*.py`, test API yếu tố 4 nếu chuỗi đổi
- Mục "## T55-fix-4" cuối `plan/reports/T55.md`
- Được chạy lại `uv run python -m app.kb.interactions build` và `report-ca` (ghi đè `data/kb_curated/tuong_tac/ddinter.sqlite`, `data/kb_reports/T55_*`)

**Cấm đụng:** mọi thứ khác, gồm `data/kb_staging/**`, `data/kb_sources/**` (dữ liệu gốc giữ nguyên chữ "None"), `app/kb/resolver/**`, `app/kb/dictionary/**`, `app/llm/**`, `app/orchestration/**`, hợp đồng API.

## Yêu cầu

1. `_text` (và mọi chỗ đọc mô tả hoặc xử trí, kể cả thức ăn) coi `None` / `none` / `N/A` sau khi bỏ khoảng trắng là thiếu (`NULL`). Sau khi dựng lại: `SELECT count(*) FROM cap WHERE hau_qua IN ('None','none')` ra 0; số cặp và số theo mức **không đổi** (291.876; Major 50.402; Moderate 186.830; Minor 12.229; Unknown 42.415).
2. Lý do thiếu dữ liệu không lồng ngoặc. Ví dụ: `chưa đủ dữ liệu tương tác: DDInter ghi mức chưa rõ (Unknown)`. Chỉ giữ một cặp ngoặc trong mọi chuỗi hiển thị (`tom_tat`, `ly_do`, mô tả nhận định).
3. Không đổi kết luận hay mức của bất kỳ cặp nào. So `data/kb_reports/T55_ma_tran_ca.json` trước và sau: `so_cap_theo_muc` phải y hệt (nghiem_trong 10, can_luu_y 10, thieu_du_lieu 30, khong_phat_hien 14, khong_ap_dung 98, chua_kiem 0).
4. Thêm test: mô tả `"None"` → thiếu; chuỗi lý do Unknown không có ngoặc lồng.

## Nghiệm thu (dán vào báo cáo)

- `uv run ruff check .`, `uv run ruff format --check` các tệp sửa.
- `uv run pytest -q -p no:cacheprovider --basetemp=<thư mục tạm ngoài kho>` toàn kho **0 trượt**.
- Kết quả hai câu SQL ở mục 1 và tóm tắt `report-ca`.
- Căn cứ và `ly_do` thật của HS-024 cặp amiodarone × paracetamol (dùng TestClient, `AUTH_MODE=off`, ca ghi ra thư mục tạm như `tests/api/test_interaction_runtime.py`).

## Cấm làm

Không gọi mạng. Không commit. Không dùng `&`. Không xoá test.
