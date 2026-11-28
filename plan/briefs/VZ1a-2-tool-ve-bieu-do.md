# VZ1a-2 – Tool `ve_bieu_do` và bộ kiểm đặc tả `mh-1` (tách từ VZ1a)

Người làm: Codex gpt-6.1-terra xhigh. Không cài gói, không mạng, không commit, không đọc `.env`, không đọc `~/.codex`.

VZ1a gốc (`plan/briefs/VZ1a-minh-hoa-backend.md`) quá rộng cho một lượt; ba lượt trước đều dừng sớm. Brief này **chỉ** làm yêu cầu 3 của VZ1a. Phần gắn hình vào câu trả lời, kỹ năng prompt và đồ thị agent để VZ1a-3.

## Đã có (không làm lại)
- `app/agent/minh_hoa/models.py`: `CotDuLieu`, `BoDuLieu`, `KhoiMinhHoa`.
- `ToolGateway.bo_du_lieu` (`app/agent/tools/gateway.py`): bộ dữ liệu của lượt, mã `ds-n`, ô chuỗi đã che PII, đã kiểm trần.
- Ba tool `tinh_chi_so`, `tra_thuoc`, `tra_tuong_tac` đã sinh bộ dữ liệu.

## Đọc trước
`AGENTS.md`; `plan/api-hop-dong-v1.10-minh-hoa.md` (hợp đồng, mục 2–5); `plan/plan-1.11-bo-sung-ngu-phap-minh-hoa.md` mục 2; `web/src/features/minh-hoa/nguPhap.ts` (bộ kiểm phía web – **ngữ pháp máy chủ phải khớp khoá và trần**); 3 mẫu `web/src/features/minh-hoa/mau/*.json`; `app/agent/tools/gateway.py`, `base.py`, một tool có sẵn làm mẫu; `config/tool_policy.yaml`; `app/calc/hien_thi.py` (`CONG_THUC_HIEN_THI`); bộ quét chèn lệnh sẵn có (tìm trong `app/deid` / `app/agent`).

## Việc phải làm
1. `app/agent/minh_hoa/kiem.py` (mới): mô hình pydantic `DacTaMinhHoa` (`extra="forbid"`, ngữ pháp `mh-1` = `mh-0` + `o_theo_khoang`) và hàm `kiem_dac_ta(dac_ta: dict, bo_du_lieu: Mapping[str, BoDuLieu], ma_can_cu_hop_le: set[str]) -> KhoiMinhHoa | LoiDacTa`. Kiểm:
   - `ds-n` phải có trong `bo_du_lieu` của lượt; cột tồn tại; kiểu cột hợp với kênh mã hoá (trục định lượng cần cột `dinh_luong`/`thoi_gian`…, khớp `nguPhap.ts`);
   - mọi chỗ cần số (phụ đề, chú thích, ngưỡng, `mac_dinh` của thanh) chỉ nhận tham chiếu ô/khoảng – số tự do bị từ chối;
   - chữ ≤ 120 ký tự, không `<`, `>`, `http`, `javascript:`, ký tự rộng 0, mẫu chèn lệnh (tiếng Anh + tiếng Việt, dùng bộ quét sẵn có);
   - `cong_thuc` ∈ `CONG_THUC_HIEN_THI`; `nguon` ⊆ `ma_can_cu_hop_le`;
   - ≤ 6 lớp, ≤ 6 điều khiển, ≤ 2.000 phần tử vẽ (ước theo số dòng các bộ được vẽ), đặc tả ≤ 16 KB, khối ≤ 100 KB sau `json.dumps`.
   - Đạt → `KhoiMinhHoa` có đúng các bộ được trỏ tới và `cong_thuc_hien_thi` lấy từ `hien_thi.py`. Hỏng → lý do ngắn, máy đọc được (ví dụ `ds_khong_ton_tai:ds-9`, `so_tu_do:phu_de[1]`).
2. Tool `ve_bieu_do` (`app/agent/tools/ve_bieu_do.py`), đăng ký như tool khác, đi qua Gateway:
   - tham số `dac_ta` (object); Gateway truyền vào bộ dữ liệu và mã căn cứ của lượt;
   - đạt: lưu khối vào Gateway (`ToolGateway.minh_hoa: list[KhoiMinhHoa]`, mã `mh-1`, `mh-2`…), trả LLM câu xác nhận ngắn, ví dụ `mh-1: 2 lớp, 3 điều khiển, 216 dòng`;
   - hỏng: `tu_choi` với lý do để LLM sửa; tính vào trần lời gọi như mọi tool;
   - tối đa 3 khối mỗi lượt; khối thứ 4 bị từ chối;
   - span tracer: kiểu dấu, số lớp, số phần tử, kích thước byte, lý do từ chối. **Không** ghi chữ của đặc tả. Thêm khoá cần thiết vào danh sách cho phép trong `app/tracing/models.py`.
3. `config/tool_policy.yaml`: `ve_bieu_do` cho `duoc_si_ls` và `admin`, chế độ ca (chế độ chung để sau, xem dưới).

## Ngoài phạm vi
- Chế độ hỏi đáp chung hiện đi qua `app/agent/asker.py` sang luồng cũ, không có đồ thị agent. **Quyết định 27/11: VZ1 chỉ làm chế độ ca.** Không sửa `asker.py`.
- Không gắn `minh_hoa` vào `AskResult`/`TraLoi` (VZ1a-3), không viết kỹ năng prompt (VZ1a-3).

## Test (`tests/agent/test_tool_ve_bieu_do.py`, `tests/agent/test_minh_hoa_kiem.py`)
- 3 mẫu VZ0 (đổi `ds-n` và dữ liệu cho khớp bộ dữ liệu dựng trong test) → đạt, khối đúng hợp đồng.
- **Ít nhất 12** đặc tả hỏng bị từ chối đúng lý do: khoá lạ; `ds-9`; cột không có; cột sai kiểu; số tự do ở `phu_de`; `<script`; `javascript:`; chèn lệnh tiếng Anh; chèn lệnh tiếng Việt; ký tự rộng 0; > 2.000 phần tử; khối > 100 KB; khối thứ 4; `nguon` lạ; `cong_thuc` lạ.
- Canary PII: bộ dữ liệu có ô chứa họ tên/SĐT giả đi qua Gateway → khối trả về không chứa chúng.
- Dựng khối cho lưới 300 dòng < 50 ms (đo 5 lần lấy trung vị; ngưỡng nới ×3 khi biến môi trường `CI` có).

## Tệp
Được tạo/sửa: `app/agent/minh_hoa/**`, `app/agent/tools/ve_bieu_do.py`, `app/agent/tools/__init__.py`, `app/agent/tools/gateway.py` (chỉ thêm phần lưu khối và truyền ngữ cảnh), `app/tracing/models.py` (chỉ khoá cho phép), `config/tool_policy.yaml`, `tests/agent/test_tool_ve_bieu_do.py`, `tests/agent/test_minh_hoa_kiem.py`, `tests/agent/test_gateway.py` (nếu cần). Báo cáo `plan/briefs/VZ1a-2-bao-cao.md`.
Cấm: `web/**`, `data/**`, `plan/**` (trừ báo cáo), `app/agent/asker.py`, `app/orchestration/**`, `app/api/**`, đổi logic kiểm chứng số.

**RAM:** chạy pytest **từng tệp một**, `--basetemp` trong `%TEMP%`. Không chạy cả thư mục.

## Nghiệm thu (Claude chạy)
```
uv run ruff check app tests tools && uv run ruff format --check app tests/agent tools
uv run pytest -q -p no:cacheprovider tests/agent/test_tool_ve_bieu_do.py tests/agent/test_minh_hoa_kiem.py tests/agent/test_gateway.py tests/tracing
```
Báo cáo phải ghi: tệp sửa, danh sách lý do từ chối đã có, các điểm khác `nguPhap.ts` (nếu có) và vì sao.
