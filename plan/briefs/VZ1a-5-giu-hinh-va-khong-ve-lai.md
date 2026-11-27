# VZ1a-5 – Giữ hình hợp lệ qua lần viết lại, không vẽ trùng, hết lượt vẽ thì buộc trả lời chữ

Người làm: Codex gpt-6.1-terra xhigh. Không cài gói, không mạng, không commit, không đọc `.env`, không đọc `~/.codex`.

## Claude chạy thật sau VZ1a-4 (27/11 tối, DeepSeek, agentic, DEMO-02, `CASE_SOURCE=file KB_SOURCE=file`)

Câu hỏi: "Meropenem cho ca này có cần chỉnh liều theo thận không, CrCl có sát ngưỡng không? Vẽ hình giúp tôi xem nếu creatinin thay đổi thì mức liều đổi thế nào."

VZ1a-4 có tác dụng: agent gọi đúng thứ tự `tinh_chi_so` → `tra_thuoc` → `ve_bieu_do`, dùng tham chiếu ô và `o_theo_khoang`, và hình hợp lệ ngay lần đầu.

**Lần 2 (có log từng nút):**

| Bước | Kết quả |
| :--- | :--- |
| `tinh_chi_so`, `tra_thuoc` | ok |
| `ve_bieu_do` | ok `mh-1: 2 lớp, 3 điều khiển, 199 dòng` |
| `ve_bieu_do` | ok `mh-2`, cùng đặc tả |
| `ve_bieu_do` | ok `mh-3`, cùng đặc tả |
| Trả lời | `KiemChung` trượt `so_khong_co_nguon:106` |
| Viết lại | qua |
| **Kết quả** | **`ok`, `minh_hoa == []`** |

Lý do mất hình: VZ1a-3 bỏ mọi hình tạo trước lần kiểm chứng trượt. Ba lần vẽ trùng tốn khoảng 28 giây.

**Lần 1:** vẽ 2 lần đều ok, sau đó `trang_thai == "loi"`. Nhiều khả năng LLM tiếp tục đòi vẽ sau lời nhắc `het_luot_ve`, rơi vào nhánh `ly_do_du_phong: "loi"` trong `TacTu` (`nodes.py`, đoạn `da_nhac_het_luot_ve`).

## Việc phải làm

1. **Giữ hình qua lần viết lại.** Khối đã qua `kiem_dac_ta` chỉ phụ thuộc bộ dữ liệu của tool, không phụ thuộc chữ trả lời.
   - Khi `KiemChung` trượt lần 1 rồi agent viết lại và qua: giữ các khối đã hợp lệ.
   - Chỉ bỏ khối khi câu trả lời cuối không đạt: dự phòng, bị chặn, hoặc hỏi lại.
   - Vẫn quét PII toàn khối trước khi gắn, như hiện nay.
2. **Không vẽ trùng.**
   - Gateway so đặc tả mới với các khối đã lưu, sau khi chuẩn hoá JSON (sắp khoá, bỏ khoảng trắng; coi như trùng nếu chỉ khác `tieu_de`/`phu_de` mà cùng `lop` và `dieu_khien`). Trùng thì từ chối `trung_hinh:mh-n`. Lần từ chối này **không** tính vào 2 lần từ chối của ngân sách vẽ.
   - Lời xác nhận khi vẽ ok thêm câu: `Đã có hình mh-n. Không cần vẽ lại; hãy trả lời bằng chữ.`
   - Kỹ năng: nhắc lại "mỗi ý chỉ một hình; vẽ xong thì trả lời ngay".
3. **Hết lượt vẽ thì buộc trả lời chữ, không `loi`.** Thay nhánh `da_nhac_het_luot_ve` → `"loi"` bằng hai bước:
   - Gọi LLM thêm **một lần** với danh sách tool rỗng và lời nhắc chỉ được trả lời. Nếu lược đồ cho phép thì chỉ nhận `tra_loi` hoặc `hoi_lai`.
   - Vẫn đòi tool → dự phòng `khong_du_can_cu` (`khong_co_nguon`), **không** `loi`. `loi` chỉ dành cho lỗi thật: ngoại lệ, sai lược đồ 2 lần.
   - Trần thời gian giữ nguyên.
4. **Vết:** ghi số lần từ chối `trung_hinh` và việc buộc trả lời chữ, dưới dạng thuộc tính span, không ghi nội dung.

## Test (LLM giả, `tests/agent/test_minh_hoa_do_thi.py`)
- Vẽ ok, rồi trả lời trượt kiểm chứng, rồi viết lại qua → `ok` và đúng 1 khối.
- Vẽ ok, rồi gọi lại đúng đặc tả đó → `trung_hinh`, chỉ 1 khối được lưu. Sau đó vẫn vẽ được một hình khác (khác `lop`).
- Vẽ hết ngân sách, LLM vẫn đòi vẽ → có lần gọi LLM không tool. Lần đó trả lời → `ok`; lần đó vẫn đòi tool → `khong_co_nguon`, không `loi`.
- Trả lời cuối bị chặn → `minh_hoa == []`.
- Các test VZ1a-4 hiện có vẫn qua. Test nào khẳng định hành vi cũ "bỏ hình trước lần trượt" thì sửa theo yêu cầu 1 và ghi rõ trong báo cáo.

## Tệp
Được sửa:
- `app/agent/nodes.py`, `app/agent/state.py`;
- `app/agent/tools/gateway.py`, `app/agent/tools/ve_bieu_do.py`;
- `app/tracing/models.py` (chỉ khoá cho phép);
- `config/prompts/ky_nang_minh_hoa.v1.md`, `config/prompts/tac_tu.v1.md` (chỉ lời nhắc trả lời khi hết tool, nếu cần);
- `tests/agent/**`.

Báo cáo ghi vào `plan/briefs/VZ1a-5-bao-cao.md`.

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
Sau đó Claude chạy lại câu trên với DeepSeek thật 2 lần. Đạt khi:
- cả 2 lần đều `ok` và có 1 khối có thanh kéo;
- không vẽ trùng quá 1 lần;
- số trên lưới khớp với Cockcroft-Gault do Claude tự tính.
