# VZ1a – Minh hoạ do agent tự dựng: bộ dữ liệu trong tool, tool `ve_bieu_do`, khối `minh_hoa` trong `TraLoi`

Người làm: Codex gpt-6.1-terra (high → xhigh nếu lượt đầu không đạt). Được chạy ruff, pytest; không cài gói, không mạng, không commit, không đọc `.env`.
Đọc trước: `AGENTS.md`; `plan/api-hop-dong-v1.10-minh-hoa.md` (**hợp đồng, bắt buộc**); `plan/plan-1.11-bo-sung-ngu-phap-minh-hoa.md`; `plan/plan-1.11-tracer-va-visualizer.md` mục B.2, B.7; `web/src/features/minh-hoa/nguPhap.ts` (bộ kiểm phía web – ngữ pháp phía máy chủ phải khớp); `tools/xuat_mau_minh_hoa.py` (cách dựng lưới và biên vẽ đã được duyệt); `app/agent/nodes.py`, `app/agent/state.py`, `app/agent/tools/*.py`, `config/tool_policy.yaml`, `config/prompts/tac_tu.v1.md`, `app/orchestration/ask.py` (`AskResult`), `app/api/schemas.py` (`TraLoi`), `app/api/service.py`, `app/tracing/`.

## Mục tiêu

Dược sĩ hỏi trong khung chat (engine `agentic`), agent **tự quyết** có vẽ hay không và vẽ gì; máy chủ trả `TraLoi.minh_hoa` đúng hợp đồng v1.10. Mọi số trên hình đến từ bộ dữ liệu do tool (code) sinh.

## Yêu cầu

1. **`BoDuLieu` trong kết quả tool.** `KetQuaCongCu` thêm `bo_du_lieu: list[BoDuLieu]` (mặc định rỗng). Gateway:
   - đánh mã `ds-1`, `ds-2`… theo thứ tự trong lượt, giữ trong đối tượng Gateway của lượt (không vào prompt toàn bộ);
   - **che PII mọi ô chuỗi** bằng cùng cơ chế che nội dung tool;
   - nối vào văn bản kết quả tool một tóm tắt ngắn cho LLM: mã, tên + kiểu + đơn vị cột, số dòng, ≤ 5 dòng mẫu;
   - kiểm trần (20 cột, 2.000 dòng, chuỗi ≤ 200 ký tự); vượt thì bỏ bộ đó, ghi lý do vào span tool.
2. **Tool sinh bộ dữ liệu:**
   - `tinh_chi_so`: mỗi chỉ số có kết quả → 1 bộ một dòng (giá trị, đơn vị, biến đầu vào). Riêng Cockcroft-Gault: thêm **lưới tính sẵn** creatinin từ max(30, ½ giá trị ca) đến min(800, 2× giá trị ca) bước 5 µmol/L (đổi theo đơn vị của ca nếu khác), **cộng đúng giá trị của ca**, × `loai_can_nang` ∈ {thực tế, lý tưởng, hiệu chỉnh} (bỏ loại không tính được), mỗi dòng gọi `app.calc.renal.cockcroft_gault` – **không tự viết công thức**. Kèm bộ "giá trị của ca" một dòng để làm `mac_dinh`.
   - `tra_thuoc`: hoạt chất có quy tắc liều thận đã duyệt (`quy_tac` trong `data/kb/quy_tac_lieu_than.json`, hiện chỉ meropenem) → bộ các mức: `crcl_tu`, `crcl_den` (nhãn), `bien_ve_tu`, `bien_ve_den`, `bao_gom_tu`, `bao_gom_den` (suy theo **đúng** `select_renal_tier`, tái dùng hàm của `tools/xuat_mau_minh_hoa.py` bằng cách chuyển nó vào `app/` rồi để script import lại), `can_chinh`, `khuyen_cao`.
   - `tra_tuong_tac`: bộ các cặp `thuoc_a`, `thuoc_b`, `muc_do`, `co_che` (≤ 200 ký tự), `ma_can_cu`.
3. **Tool `ve_bieu_do`** (mới, qua Gateway, có trong `tool_policy.yaml` cho `duoc_si_ls` và `admin`, cả chế độ ca và chung):
   - tham số: `dac_ta` (đối tượng ngữ pháp `mh-1`);
   - kiểm bằng mô hình pydantic `extra="forbid"` + kiểm tham chiếu: `ds-n` phải thuộc lượt; cột tồn tại, đúng kiểu; mọi chỗ cần số là tham chiếu ô/khoảng; chữ ≤ 120 ký tự, không `<`, `>`, `http`, `javascript:`, ký tự rộng 0, mẫu chèn lệnh (dùng bộ quét chèn lệnh sẵn có); `cong_thuc` ∈ `CONG_THUC_HIEN_THI`; `nguon` ⊆ mã căn cứ đã có trong lượt; ≤ 6 lớp, ≤ 6 điều khiển, ≤ 2.000 phần tử vẽ; đặc tả ≤ 16 KB; khối ≤ 100 KB; ≤ 3 hình mỗi lượt;
   - đạt → dựng `KhoiMinhHoa` (kèm đúng các bộ dữ liệu được trỏ tới và `cong_thuc_hien_thi`), lưu trong Gateway, trả LLM câu xác nhận ngắn (`mh-1: 2 lớp, 3 điều khiển, 216 dòng`); hỏng → `tu_choi` với lý do ngắn để LLM sửa (tính vào trần lời gọi tool như mọi tool).
4. **Gắn vào câu trả lời:** `AskResult` và `TraLoi` thêm `minh_hoa: list[KhoiMinhHoa] = []`; chỉ gắn khi `KiemChung` đạt và `trang_thai == "ok"`; dự phòng/bị chặn → `[]`; `co_dinh` → `[]`. API hỏi đáp (cả ca và chung) trả trường này. Tracer: span tool `ve_bieu_do` ghi kiểu dấu, số phần tử, kích thước, lý do bỏ (không ghi chữ).
5. **Kỹ năng** `config/prompts/ky_nang_minh_hoa.v1.md` (≤ 1.200 từ) và nạp vào prompt `tac_tu` khi tool `ve_bieu_do` được phép: khi nào vẽ (so sánh nhiều nhóm, xu hướng thời gian, vị trí so với ngưỡng, nhiều cặp tương tác, câu "nếu… thì…"), khi nào không (một con số, thiếu dữ liệu, định nghĩa); chọn dấu theo câu hỏi; trung thực (cột từ 0, không phân biệt chỉ bằng màu, tỉ trọng ≤ 6 phần); thanh kéo khi người bệnh sát ngưỡng; chữ trả lời tự đứng được, không viết "xem hình" thay câu trả lời; **3 ví dụ đặc tả hoàn chỉnh** (liều thận + lưới CrCl, ma trận tương tác, xét nghiệm theo thời gian dạng đường – ví dụ cuối chỉ minh hoạ cú pháp). Cập nhật phiên bản prompt nếu kho có quy ước.
6. Ngân sách hiệu năng phía máy chủ: dựng khối < 50 ms cho lưới 300 dòng (test đo, ngưỡng nới khi CI chậm).

## Test

- `tests/agent/test_tool_ve_bieu_do.py`: đặc tả hợp lệ (lấy từ 3 tệp mẫu VZ0, đổi `ds-n` cho khớp lượt) → khối đúng hợp đồng; **ít nhất 10** đặc tả hỏng bị từ chối đúng lý do (khoá lạ, `ds-9`, cột sai kiểu, số tự do ở `phu_de`, `<script`, `javascript:`, chèn lệnh tiếng Anh + tiếng Việt, ký tự rộng 0, quá 2.000 phần tử, khối > 100 KB, hình thứ 4, `nguon` lạ, `cong_thuc` lạ).
- Lưới CG: tự tính lại ≥ 5 dòng bằng công thức viết tay trong test (độc lập với `app/calc`) khớp ±0,01; có đúng dòng giá trị của ca.
- Biên vẽ meropenem: mọi dòng lưới rơi đúng một mức theo `select_renal_tier`.
- Đồ thị agent với LLM giả: gọi `tinh_chi_so` → `tra_thuoc` → `ve_bieu_do` → trả lời → `TraLoi.minh_hoa` có 1 khối; LLM giả trả lời không qua kiểm chứng → `minh_hoa == []`; engine `co_dinh` → `[]`.
- **Canary PII:** ca giả có họ tên/SĐT trong một ô chuỗi của bộ dữ liệu → khối trả về không chứa chúng.
- Hợp đồng API: test bộ trường `TraLoi` cập nhật `minh_hoa`.

## Tệp

Được tạo/sửa: `app/tracing/models.py` (chỉ thêm khoá thuộc tính cho span `ve_bieu_do`/bộ dữ liệu vào danh sách cho phép), `app/agent/tools/**`, `app/agent/nodes.py`, `app/agent/state.py`, `app/agent/minh_hoa/**` (mới, nếu tách mô hình/bộ kiểm), `app/orchestration/ask.py` (chỉ `AskResult.minh_hoa` và chuyền qua), `app/api/schemas.py`, `app/api/service.py`, `app/rules/renal_dose.py` (chỉ thêm hàm biên vẽ nếu đặt ở đây), `tools/xuat_mau_minh_hoa.py` (chỉ đổi sang import hàm dùng chung), `config/tool_policy.yaml`, `config/prompts/**`, `tests/agent/**`, `tests/api/**` (chỉ hợp đồng). Báo cáo `plan/briefs/VZ1a-bao-cao.md`.
Cấm: `web/**`, `data/**`, `.env`, `plan/**` (trừ báo cáo); đổi logic kiểm chứng số; cài gói; mạng; commit. Thư mục tạm pytest đặt trong `%TEMP%` (`--basetemp`), **không** trong `tests/`.

**Giới hạn RAM (máy dev hay hết bộ nhớ, Claude Code tự dừng tiến trình):** agent chỉ chạy test liên quan (`tests/agent/test_tool_ve_bieu_do.py`, các test tool đã sửa, `tests/api/test_contract.py`, `tests/tracing`), **không** chạy cả `tests/api` hay `tests/agent` đầy đủ; Claude chạy bộ đầy đủ khi review.

## Nghiệm thu (Claude chạy)

```
uv run ruff check app tests tools && uv run ruff format --check app tests/agent tests/api tests/orchestration tools
uv run pytest -q -p no:cacheprovider tests/agent tests/orchestration tests/tracing tests/eval tests/api
```
Claude kiểm độc lập: chạy thật DeepSeek (agentic) DEMO-02 "Meropenem cho ca này có cần chỉnh liều theo thận không, có sát ngưỡng không?" và một câu tương tác nhiều thuốc → có khối hợp lệ, số trên lưới khớp tự tính; một câu một con số → không có hình; quét khối không có định danh.

## Lượt 3 (27/11) – làm tiếp, không làm lại

Hai lượt trước dừng giữa chừng (lượt xhigh bị dừng vì máy hết RAM). Trong cây làm việc **đã có**: `app/agent/minh_hoa/models.py` (`CotDuLieu`, `BoDuLieu`, `KhoiMinhHoa`), `KetQuaCongCu.bo_du_lieu`, `AskResult.minh_hoa`/`TraLoi.minh_hoa` (rỗng), một phần sinh bộ dữ liệu trong `tinh_chi_so.py`, `tra_thuoc.py`, `tra_tuong_tac.py`, `gateway.py`, hàm biên vẽ trong `app/rules/renal_dose.py`, `tools/xuat_mau_minh_hoa.py` import lại, cùng test trong `tests/agent/test_gateway.py`, `test_tool_*.py`.

Việc đầu tiên: `git diff` các tệp trên, đối chiếu từng yêu cầu 1–6, ghi vào báo cáo cái nào đạt/thiếu. Rồi làm phần **còn thiếu** (dự kiến: hoàn thiện yêu cầu 1–2 nếu thiếu, tool `ve_bieu_do` + bộ kiểm `mh-1`, gắn `minh_hoa` sau kiểm chứng, tracer, chính sách tool, kỹ năng prompt, toàn bộ test mới). Không viết lại phần đã đạt.

Chạy test **từng tệp một**, không chạy cả thư mục `tests/api` hay `tests/agent`. Ghi đè `plan/briefs/VZ1a-bao-cao.md` bằng báo cáo mới.
