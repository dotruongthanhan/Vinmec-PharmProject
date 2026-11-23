# Báo cáo thực hiện T102 – Đồ thị agent hỏi đáp (LangGraph), `AgenticAsker`, nối dịch vụ theo cờ

## 1. Tệp đã tạo hoặc sửa

**Đã tạo:**
- `app/agent/state.py`
- `app/agent/nodes.py`
- `app/agent/graph.py`
- `app/agent/asker.py`
- `config/prompts/tac_tu.v1.md`
- `tests/agent/test_graph.py`
- `tests/agent/test_asker.py`
- `tests/agent/test_service_engine.py`

**Đã sửa:**
- `app/orchestration/ask.py`
- `app/container.py`
- `app/api/service.py`
- `app/config/settings.py`
- `config/settings.yaml`

Không sửa `app/agent/tools/*`, `web/*`, `app/api/routes.py`, `app/api/schemas.py`, hợp đồng API hay bất kỳ tệp nào ngoài phạm vi brief (ngoài tệp báo cáo này).

## 2. Các hàm và kiểu dữ liệu đã tách khỏi `app/orchestration/ask.py`

- `NguCanhCa`: dataclass `frozen=True` chứa `active_result`, `van_ban_ca`, `ids`, `anh_xa`, `allowed_record_ids`, `allowed_calc_ids`, `allowed_numbers`, `priority_chunk_ids`.
- `chuan_bi_ngu_canh_ca(ca, ket_qua, ai_result, nhan_dinh_id, session, case_settings, renal_rules_getter) -> NguCanhCa`: tách phần chạy luật (nếu chưa có), `build_case_bundle`, `_collect_case_numbers`, `_format_priority_finding`, `_format_ai_section` và `_sanitize_markers`. `CaseAsker.ask` gọi lại hàm này.
- `AskVerificationError`: đổi tên công khai từ `_AskVerificationError` và giữ bí danh `_AskVerificationError = AskVerificationError`.
- `kiem_chung_tra_loi(...) -> AskResult`: tách phần thân `CaseAsker._verify_and_build_reply` thành hàm công khai cấp module; `CaseAsker._verify_and_build_reply` chỉ còn ủy quyền sang `kiem_chung_tra_loi`.

## 3. Quyết định khi brief chưa rõ

- **Truyền `ToolGateway` mỗi lượt cho đồ thị biên dịch một lần:** vì đồ thị `dung_do_thi_hoi_dap` biên dịch một lần trong `AgenticAsker.__init__` còn `ToolGateway` khởi tạo mới mỗi lượt hỏi (`so_lan_goi_toi_da = max_turns * 3`), `HoiDapState` giữ trường `gateway` do `AgenticAsker.ask` tạo và truyền vào lúc `invoke`; nếu gọi đồ thị trực tiếp không truyền `gateway`, `GoiCongCu` tự khởi tạo một `ToolGateway` cho lượt đó.
- **Cập nhật `ctx.deid_session` tại nút `che_pii`:** nút `che_pii` mở `DeidSession` bằng `open_deid_session` và gắn lại vào `ctx` qua `dataclasses.replace(ctx, deid_session=session)` để `ToolGateway` dùng chung đúng `DeidSession` khi quét PII tham số và che kết quả công cụ.
- **Bắt ngoại lệ ở mọi nút bằng `@an_toan`:** ngoài `tac_tu` và `kiem_chung`, các nút `che_pii`, `chan_dau_vao`, `chuan_bi_ngu_canh` và `goi_cong_cu` cũng có cạnh điều kiện kiểm tra `can_du_phong` trước khi đi tiếp, bảo đảm ngoại lệ ở bất kỳ nút nào đều rẽ ngay sang `du_phong_luong_cu` mà không chạy qua nút sau hay làm lộ thông tin ngoại lệ. `du_phong_luong_cu` và `hoan_tat` tự bọc `try/except` an toàn.
- **Đếm lượt `agent_tac_tu_<n>` và lỗi lược đồ:** dùng bộ đếm riêng `luot_tac_tu` tăng mỗi lần gọi `TacTu` để mã bước `agent_tac_tu_<n>` luôn duy nhất trong `TienTrinh` ngay cả khi lặp lại do `kiem_chung` trượt lần 1 hoặc sai lược đồ lần 1. Sai lược đồ tăng `so_vong` và `so_lan_sai_luoc_do`; sai 2 lần liên tiếp (hoặc hết `max_turns`) chuyển sang `du_phong_luong_cu` với `ly_do_du_phong="loi"`.
- **Dùng lại kết quả khi `luong_cu_cung` đã chạy `ok` trong lượt:** không sửa `app/agent/tools/*` nên `GoiCongCu` dựng lại `AskResult` từ `KetQuaCongCu` (gỡ khung `<<<KET_QUA_CONG_CU ...>>>`, khôi phục PII/mã bản ghi, giữ danh sách `doan`) và lưu vào `state["ket_qua_luong_cu"]`; khi vào `du_phong_luong_cu` trả ngay kết quả này mà không gọi lại `CaseAsker`.
- **Trạng thái khi tắt `luong_cu_cung` ở `ask_global`:** trả `AskResult(trang_thai="chua_san_sang", noi_dung=...)` kèm thông báo chưa hỗ trợ.
- **Rẽ nhánh `du_phong_luong_cu` khi `luong_cu_cung` tắt:** `ly_do_du_phong == "loi"` trả `AskResult(trang_thai="loi", noi_dung=ERROR_MESSAGE)`, các lý do còn lại (`khong_du_can_cu`, `het_luot`, `het_gio`, `truot_kiem_chung`) trả `AskResult(trang_thai="khong_co_nguon", noi_dung=NO_SOURCE_MESSAGE)`.
- **Lược đồ `LoiGoiCongCu` và `KeHoachTacTu`:** đặt trong `app/agent/state.py` và tái xuất ở `app/agent/nodes.py` để tránh vòng lặp import.
- **Kiểm tra `ask.engine=co_dinh` với `luong_cu_cung` tắt trong `CaseService`:** kiểm tra ngay trong `CaseService.__init__` khi dịch vụ có AI và có `Container` (`self._ai_enabled and self._container is not None`), báo `ConfigError("ask.engine=co_dinh nhưng luong_cu_cung đang tắt")`.

## 4. Điều chưa làm

- **Chưa chạy lệnh kiểm thử và lint (`pytest`, `ruff`)**: tuân thủ tuyệt đối quy định không gọi công cụ shell của brief và yêu cầu người dùng; người review cần chạy các lệnh nghiệm thu ở mục 4 của brief.
