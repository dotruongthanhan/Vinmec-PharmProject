# VZ1a-4 – Vẽ hỏng làm mất câu trả lời: tách ngân sách vẽ, thông báo lỗi rõ hơn, kỹ năng gọi đúng tool

Người làm: Codex gpt-6.1-terra xhigh. Không cài gói, không mạng, không commit, không đọc `.env`, không đọc `~/.codex`.

## Claude chạy thật (27/11, DeepSeek, agentic, `CASE_SOURCE=file KB_SOURCE=file`, DEMO-02)

| Câu | Kết quả |
| :--- | :--- |
| "Creatinin máu gần nhất bao nhiêu?" | ok, không hình (đúng) |
| "Có cặp tương tác nào không?" | ok, không hình (đúng: ca chỉ có 1 thuốc) |
| "Meropenem có cần chỉnh liều theo thận không, CrCl có sát ngưỡng không? Vẽ hình xem nếu creatinin thay đổi thì mức liều đổi thế nào." | **`khong_co_nguon` sau 75 s, 0 hình** |

Chuỗi lời gọi của câu 3:
1. `tra_thuoc` (ok);
2. `tim_doan_nguon` (ok);
3. `ve_bieu_do` → `tu_choi nguon_khong_hop_le`. LLM tự bịa mã `tinh:cockcroft_gault:thuc_te`, vì chưa hề gọi `tinh_chi_so`;
4. `ve_bieu_do` → **ok** (`mh-1: 1 lớp, 0 điều khiển, 4 dòng`);
5. `ve_bieu_do` (vẽ lại) → `tu_choi so_tu_do:phu_de[0]` ("CrCl hiện tại: 16.0 mL/min"); bộ kiểm làm đúng.

Kết quả: 5 vòng = `max_turns` (config `settings.yaml` dòng 40), nên `nodes.py` trả `het_luot`, rơi vào dự phòng, mất cả câu trả lời chữ lẫn hình đã hợp lệ.

Ngoài ra:
- LLM không gọi `tinh_chi_so`, nên không có lưới Cockcroft-Gault và không có thanh kéo creatinin.
- Lời từ chối không cho LLM biết mã nguồn hợp lệ là gì.

## Việc phải làm

1. **Ngân sách vẽ riêng** (`app/agent/nodes.py`, `gateway.py`):
   - Vòng mà **mọi** lời gọi đều là `ve_bieu_do` không tính vào `max_turns`. Các vòng đó có trần riêng: tối đa **3 vòng vẽ** mỗi lượt.
   - Sau **2 lần bị từ chối** trong lượt, Gateway từ chối mọi lời gọi `ve_bieu_do` tiếp theo với lời nhắn: `het_luot_ve: không vẽ thêm, hãy trả lời bằng chữ`.
   - Hết ngân sách vẽ thì agent vẫn phải đi tới bước trả lời. Không được rơi vào dự phòng chỉ vì vẽ.
   - Trần thời gian tổng của lượt giữ nguyên.
   - Không đổi hành vi `het_luot` cho các tool khác.
2. **Lời từ chối có ích cho LLM** (`ve_bieu_do.py` / `kiem.py`), ngắn, không lộ dữ liệu:
   - `nguon_khong_hop_le` → kèm danh sách mã căn cứ hợp lệ của lượt (tối đa 10 mã);
   - `ds_khong_ton_tai` / `cot_khong_ton_tai` → kèm danh sách `ds-n` và tên cột hiện có;
   - `so_tu_do:<vị trí>` → kèm gợi ý "dùng tham chiếu `o` hoặc `o_theo_khoang`".
   - Vết vẫn chỉ ghi mã lý do, không ghi danh sách.
3. **Kỹ năng** (`config/prompts/ky_nang_minh_hoa.v1.md`):
   - Muốn vẽ liều thận theo CrCl kèm thanh kéo creatinin: gọi `tinh_chi_so` (Cockcroft-Gault) **trước** để có lưới, rồi mới `tra_thuoc`, rồi mới `ve_bieu_do`. Ví dụ 1 phải dùng cả hai bộ dữ liệu.
   - `nguon` chỉ chép **nguyên văn** mã căn cứ có trong kết quả tool, không tự đặt mã.
   - Số của ca (CrCl 16,0) phải lấy bằng tham chiếu ô từ bộ "giá trị của ca", không viết vào chữ.
   - Một lần vẽ là đủ. Không vẽ lại nếu lần trước đã `ok`.
4. **Gợi ý trong tóm tắt bộ dữ liệu** (Gateway, phần nối vào kết quả tool): mỗi bộ ghi kèm mã căn cứ dùng cho `nguon`.

## Test
- Đồ thị với LLM giả:
  - (a) gọi 2 tool thường, rồi `ve_bieu_do` từ chối, ok, từ chối, rồi trả lời: `trang_thai == "ok"` và có 1 khối (khối ok được giữ);
  - (b) 4 tool thường + 3 lần `ve_bieu_do` từ chối + trả lời: vẫn ok, không có khối, không `het_luot`;
  - (c) lời gọi `ve_bieu_do` thứ 3 sau 2 lần từ chối bị chặn `het_luot_ve`;
  - (d) 5 vòng tool thường vẫn `het_luot` như cũ.
- Lời từ chối `nguon_khong_hop_le` chứa mã hợp lệ của lượt; vết không chứa danh sách đó.
- Ví dụ 1 trong kỹ năng (2 bộ dữ liệu) qua `kiem_dac_ta`.

## Tệp
Được sửa:
- `app/agent/nodes.py`, `app/agent/state.py`, `app/agent/graph.py` (nếu cần);
- `app/agent/tools/gateway.py`, `app/agent/tools/ve_bieu_do.py`, `app/agent/minh_hoa/kiem.py`;
- `config/prompts/ky_nang_minh_hoa.v1.md`;
- `tests/agent/**`.

Báo cáo ghi vào `plan/briefs/VZ1a-4-bao-cao.md`.

Cấm:
- `web/**`, `data/**`, `plan/**` (trừ báo cáo), `app/agent/asker.py`, `config/settings*.yaml`;
- đổi logic kiểm chứng số, đổi `max_turns`;
- cài gói, dùng mạng, commit.

**RAM:** pytest **từng tệp một**, `--basetemp` trong `%TEMP%`.

## Nghiệm thu (Claude chạy)
```
uv run ruff check app tests && uv run ruff format --check app tools tests/agent tests/api tests/orchestration
uv run pytest -q -p no:cacheprovider tests/agent tests/orchestration tests/api
```
Sau đó Claude chạy lại câu 3 với DeepSeek thật. Đạt khi có câu trả lời `ok` kèm 1 khối, có thanh kéo creatinin, và số trên lưới khớp với số Claude tự tính.
