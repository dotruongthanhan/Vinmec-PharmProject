# T55-fix-1 – Nối luật tương tác (yếu tố 4) vào đường chạy thật và cập nhật test

Mô hình: Codex `gpt-6.1-sol`, effort `xhigh`. Không có mạng, không cần mạng.

Đọc: `AGENTS.md`, `plan/api-hop-dong-v1.6-ma-tran-tuong-tac.md`, `plan/briefs/T55-luat-tuong-tac-va-ma-tran.md`, `plan/reports/T55.md` (đặc biệt mục "Giới hạn còn lại", "Test đã đổi kỳ vọng").

## Bối cảnh

T55 đã viết xong:
- Bảng tương tác: 291.876 cặp.
- `InteractionStore`, luật `app/rules/interaction.py`, ma trận, `ChiTietCa.ma_tran_tuong_tac`, component web.
- Trên 66 ca: 162 cặp, 0 cặp chưa kiểm.

Nhưng **brief T55 thiếu phạm vi**, nên:
- `app/pipeline.py:run_case` vẫn gọi `app/rules/engine.py:run_rules` với 5 luật cứng.
- Endpoint thật chạy 5 luật và trả `ma_tran_tuong_tac = null`.
- `OrderDetailView.tsx` chưa truyền `detail.ma_tran_tuong_tac` vào `InteractionMatrix`.
- 10 test cũ trượt vì đổi số luật / tập trường hợp đồng.

Lượt này mở phạm vi để nối hết.

## Phạm vi file

**Được sửa:**
- `app/pipeline.py`, `app/rules/engine.py`, `app/rules/registry.py`, `app/rules/interaction.py`
- `app/api/service.py`, `app/api/presenter.py`
- `app/db/reader.py` (chỉ chỗ gọi `run_case` trong `DbReviewService`), `app/ui/services.py` (chỉ chỗ gọi `run_case`)
- `app/container.py`, `app/kb/interactions/**`
- `web/src/features/order-detail/OrderDetailView.tsx` và test web liên quan
- **Test được đổi kỳ vọng (chỉ đúng các chỗ sau):**
  - `tests/architecture/test_notebook.py` (số luật 5 → 6)
  - `tests/rules/test_registry.py` (thêm `('interaction', 4)`, giữ thứ tự)
  - `tests/test_container.py`
  - `tests/api/test_contract.py` (thêm v1.6 vào tập hợp đồng đối chiếu)
- Test mới bất kỳ
- Mục "## T55-fix-1" cuối `plan/reports/T55.md`

**Cấm đụng:**
- `app/kb/resolver/**`, `app/kb/dictionary/**`, `app/llm/**`, `app/deid/**`, `app/orchestration/**`
- `data/**` (trừ đọc), `db/**`, `.env`, `pyproject.toml`, `uv.lock`
- `plan/` (trừ báo cáo)

## Yêu cầu

1. **Đường chạy:**
   - `run_case` (và mọi nơi gọi nó: dịch vụ API ở cả chế độ tệp và DB, Streamlit) chạy **6 luật** gồm luật tương tác, khi phụ thuộc có sẵn.
   - Phụ thuộc (bộ phân giải + kho tương tác) lấy từ container, **nạp một lần**, không nạp lại mỗi ca.
   - Nếu chỉ mục `tra_cuu.sqlite` hoặc `ddinter.sqlite` không có thì chạy 5 luật như cũ và ghi một cảnh báo; ứng dụng **không được lỗi**.
   - Giữ tương thích chữ ký: tham số mới là tuỳ chọn có mặc định.
   - Thứ tự phát hiện theo `_priority_key`.
2. **Presenter:** truyền `ma_tran_tuong_tac` thật vào `present_case` ở mọi đường trả `ChiTietCa`. Dùng lại ma trận đã tính khi chạy luật (không tính hai lần). `nhan_dinh_id` của cặp trỏ đúng nhận định.
3. **AI:** kiểm luồng thẩm định AI (`app/orchestration`, chỉ đọc) vẫn nhận đủ phát hiện luật kể cả yếu tố 4. Không sửa orchestration; nếu thấy cần sửa thì ghi vào báo cáo.
4. **Web:** `OrderDetailView.tsx` truyền `detail.ma_tran_tuong_tac`; khi `null` giữ cách cũ.
5. **Test:**
   - Cập nhật đúng các kỳ vọng nêu trên; liệt kê từng thay đổi trong báo cáo.
   - Thêm test endpoint `GET /api/cases/{ca_id}` cho một ca có tương tác (HS-024: amiodaron × digoxin) trả `ma_tran_tuong_tac` khác `null`, có cặp `nghiem_trong` và `nhan_dinh_id` khớp một nhận định yếu tố 4.
   - Thêm test khi thiếu chỉ mục: 5 luật, `ma_tran_tuong_tac` là `null`, không lỗi.
6. **Đo:** thời gian `GET /api/cases/{ca_id}` trước và sau (DEMO-02 và HS-024), trung vị 20 lần sau khi nạp nóng, dùng TestClient. Ghi cả thời gian nạp chỉ mục lần đầu.

## Nghiệm thu (dán kết quả vào báo cáo)

- `uv run ruff check .`, `uv run ruff format --check` (các tệp đã sửa), `uv run pytest -q --basetemp=.pytest_t55f1`: **toàn kho 0 trượt**.
- Web, trong `web/`: `npx vitest run`, `npx oxlint`, `npx tsc -b`, `npm run build` đều qua.
- Dán đầu ra rút gọn của endpoint HS-024: danh sách cặp với mức.

## Cấm làm

- Không gọi mạng. Không commit. Không dùng `&`.
- Không đổi kết luận các luật cũ.
- Không xoá test để làm xanh.
