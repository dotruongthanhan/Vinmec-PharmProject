# VZ1-fix-2 – LLM tưởng hình của lượt trước vẫn còn nên không vẽ lại

Người làm: Codex gpt-6.1-terra high. Không cài gói, không mạng, không commit, không đọc `.env`, không đọc `~/.codex`.

## Lỗi (Claude chạy e2e, 27/11 tối, DeepSeek thật, DEMO-02)

Lịch sử hội thoại do máy chủ dựng có câu trả lời cũ nhắc tới hình ("Hình `mh-1` đã thể hiện…"). Theo hợp đồng v1.10 mục 1, **hình không được lưu vào lịch sử**.

Khi hỏi lại cùng câu, agent chỉ gọi `tinh_chi_so`, `tra_thuoc`, `tim_doan_nguon` rồi trả lời:

> "Hình `mh-1` ở lượt trước đã thể hiện lưới CrCl…, nên không vẽ lại."

API trả `minh_hoa: []`, nên dược sĩ không thấy hình nào. Câu trả lời còn lộ mã nội bộ `mh-1` ra cho người đọc.

Xoá lịch sử rồi hỏi lại thì agent vẽ bình thường.

## Việc phải làm
1. `config/prompts/ky_nang_minh_hoa.v1.md`:
   - **Hình chỉ tồn tại trong lượt vừa tạo; lịch sử không có hình.** Câu hỏi hiện tại cần hình thì vẽ trong lượt này, kể cả khi lịch sử nhắc tới hình.
   - Quy tắc "không vẽ lại" chỉ áp dụng **trong cùng một lượt**.
   - **Không nhắc mã `mh-n`, `ds-n`** trong chữ trả lời; muốn nói tới hình thì viết "hình bên dưới".
2. `app/agent/nodes.py` (phần dựng ngữ cảnh lịch sử, nếu có chỗ phù hợp): khi đưa câu trả lời cũ của trợ lý vào prompt, thay các cụm `mh-\d+` bằng `hình (không còn hiển thị)` để LLM không bị lừa. Chỉ sửa chuỗi đưa vào prompt, không sửa dữ liệu lưu.
3. Bộ kiểm chứng chữ trả lời **không đổi**. Nếu kho có sẵn bước làm sạch chữ trả lời thì thêm luật thay `mh-\d+` / `ds-\d+` trong `noi_dung` bằng "hình bên dưới" / "bảng dữ liệu của hình". Chỉ thay khi `minh_hoa` không rỗng; nếu `minh_hoa` rỗng thì bỏ câu có chứa mã đó. Nếu phải thêm bước mới vào luồng kiểm chứng thì **không làm**; ghi lại trong báo cáo.

## Test
- LLM giả, lịch sử có câu "Hình mh-1 đã thể hiện…". Kiểm prompt gửi LLM không còn chuỗi `mh-1`.
- Kỹ năng có câu về hình không nằm trong lịch sử (test đọc tệp).
- Nếu làm mục 3: `noi_dung` chứa `mh-1` khi `minh_hoa == []` thì câu đó bị bỏ.

## Tệp
Được sửa:
- `config/prompts/ky_nang_minh_hoa.v1.md`;
- `app/agent/nodes.py` (chỉ phần dựng lịch sử / làm sạch chữ);
- `tests/agent/test_minh_hoa_do_thi.py`.

Báo cáo ghi vào `plan/briefs/VZ1-fix-2-bao-cao.md`.

Cấm:
- `web/**`, `app/verify/**`, `app/api/**`, `data/**`, `plan/**` (trừ báo cáo);
- thêm gói, dùng mạng, commit.

**RAM:** pytest từng tệp, `--basetemp` trong `%TEMP%`.

## Nghiệm thu (Claude chạy)
```
uv run ruff check app tests && uv run ruff format --check app tests/agent
uv run pytest -q -p no:cacheprovider tests/agent tests/orchestration
```
Sau đó Claude chạy DeepSeek thật hai lượt liên tiếp, cùng câu, **không** xoá lịch sử. Đạt khi lượt 2 vẫn có hình và chữ trả lời không chứa `mh-`.
