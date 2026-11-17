# T04a-fix-1 – Sửa tồn đọng của bước tiền xử lý nhãn

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort xhigh) · **Ngày:** 16/11/2026 (phiên 3)
**Đọc trước:** `AGENTS.md`; `plan/briefs/T04a-tien-xu-ly-va-cat-doan.md`; `app/kb/`, `tests/kb/`.

## 1. Hiện trạng (người review đã chạy)

`python -m app.kb.build` chạy trọn: `labels=50/50 chunks=3738 text=3506 table=232 over_max=0 under_50=0 empty_act=0 q3_warn=18`. Đoạn bảng liều thận của meropenem đúng 4 mức. Còn 6 việc:

| # | Việc | Bằng chứng và yêu cầu |
| :-: | :--- | :--- |
| 1 | 1 test trượt | `tests/kb/test_openfda_source.py::test_load_new_format_fixture_strips_highlights_and_parses_tables`: `assert len(renal_tables) == 2` nhưng ra 0. Trên dữ liệu thật, bảng mục 2.2 của meropenem vẫn được gán đúng. Xác định lỗi nằm ở code gán bảng hay ở tệp mẫu `tests/kb/fixtures/openfda_new_format.json`. Lỗi ở code thì sửa code; tệp mẫu sai thì sửa tệp mẫu và nêu rõ sai chỗ nào. **Không** nới câu `assert`. |
| 2 | Lint | `uv run ruff check app/kb tests/kb` báo 2 lỗi |
| 3 | Định dạng | `uv run ruff format --check app/kb tests/kb` báo 6 file |
| 4 | Tên tiểu mục dính chữ đầu của thân bài | `duong_dan_muc` đang là `... > 2.2 Use in Adult Patients with Renal Impairment Dosage`: chữ `Dosage` là từ đầu câu thân bài ("Dosage should be reduced…"). Tương tự `8.6 Patients with Renal Impairment Dosage`. Sửa cách cắt ranh giới tiêu đề – thân bài; thêm test với đúng hai chuỗi này, kỳ vọng `2.2 Use in Adult Patients with Renal Impairment` và `8.6 Patients with Renal Impairment`. Sau khi sửa, đưa vào báo cáo 30 `duong_dan_muc` lấy ngẫu nhiên (hạt giống cố định) từ 5 nhãn khác nhau để người review soát. |
| 5 | `url_goc` rỗng | Mọi đoạn có `url_goc == ""`. Điền `https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=<set_id>` khi nhãn có `set_id` trong dữ liệu (không gọi mạng). Không có thì để rỗng, và báo cáo dựng kho đếm số nhãn như vậy. |
| 6 | Import trong sổ tay | `uv run ruff check . --exclude tests/architecture/.tmp` báo 4 lỗi `I001` ở `notebooks/04_test_database.ipynb` và một sổ tay khác. Chỉ sắp lại import trong các ô đó; không đổi nội dung khác, không lưu đầu ra ô. |

## 2. Phạm vi file

`app/kb/**`, `tests/kb/**`, `notebooks/*.ipynb` (chỉ việc 6). Sau khi sửa, chạy lại `uv run python -m app.kb.build` để sinh lại `data/kb_curated/chunks.jsonl` và báo cáo trong `data/kb_reports/`. Không đụng `app/retrieval`, `app/llm`, `app/api`, `app/orchestration`, `web/`, `data/kb_sources/`.

**Giữ ổn định mã đoạn:** `doan_trich_id` của các đoạn không đổi nội dung cần giữ nguyên sau khi sửa (bộ đệm nhúng dùng mã này). Nếu việc 4 buộc mã đổi vì mã tính từ `duong_dan_muc`, ghi rõ trong báo cáo bao nhiêu mã đổi.

## 3. Nghiệm thu

```bash
uv run ruff check . --exclude tests/architecture/.tmp
uv run ruff format --check app/kb tests/kb
uv run pytest -q tests/kb tests/architecture -p no:cacheprovider
uv run python -m app.kb.build
```

Dòng tóm tắt của lệnh cuối phải còn `labels=50/50`, `over_max=0`, `under_50=0`, `empty_act=0`.

## 4. Cấm làm

Không sửa, dịch, tóm tắt nội dung y khoa. Không gọi mạng. Không thêm thư viện. Không commit, không push. Trả lời theo mẫu trong `AGENTS.md`.
