# VZ2-fix-2 – Cột thời gian bị che trong khối hình; câu tổng liều trượt kiểm chứng

Người làm: Codex `gpt-6.1-terra` xhigh. Đọc `plan/briefs/VZ2-lay-du-lieu-ca-dong-thoi-gian.md`, `plan/briefs/VZ2-bao-cao.md`, `plan/api-hop-dong-v1.10-minh-hoa.md`, `app/agent/tools/gateway.py`, `app/agent/nodes.py`, `app/verify/**` (chỉ đọc), `app/deid/**` (chỉ đọc).

## Claude chạy thật (27/11, DeepSeek, engine agentic, `CDSS_PROFILE=e2e`, gọi thẳng `container.agentic_asker.ask`)

| Ca | Câu | Kết quả |
| :--- | :--- | :--- |
| DEMO-02 | Creatinin diễn tiến thế nào, CrCl hôm nay còn tin được không? | `ok`, 28 s, tool `lay_du_lieu_ca` → `ve_bieu_do`, 1 hình `duong`+`diem`+`quy_tac`. Câu chữ đúng (150 → 212). **Nhưng** ô thời gian trong khối: `'thoi_diem': '[NGAY_1]T05:30:00+07:00'` |
| DEMO-02 | Tổng liều meropenem trong 24 giờ là bao nhiêu, lịch dùng theo giờ thế nào? | lần 1: `loi` sau 3 s, không tool nào; lần 2: `khong_co_nguon` sau 23 s, đã gọi `lay_du_lieu_ca` → `ve_bieu_do` nhưng câu trả lời bị bỏ |
| DEMO-04 | Kháng sinh ngày thứ mấy, có kháng sinh đồ chưa? | `ok`, trả lời đúng (ceftriaxon chưa bắt đầu; E. coli S với ceftriaxon), không vẽ (chấp nhận được) |
| DEMO-02 | Creatinin hôm nay bao nhiêu? | `ok`, không hình (đúng) |
| | Quét khối | Không có mã người bệnh |

## Phải sửa

1. **Ô thời gian bị che trong khối hình gửi web.** Gateway che PII mọi ô chuỗi nên cột `kieu = thoi_gian` thành `[NGAY_n]T…`. Web không đọc được trục thời gian, nên hình V3/V5/V6/V8 hỏng.
   - **Nguyên tắc:** văn bản và tóm tắt gửi LLM vẫn che như cũ. **Khối hình gửi web** (không đi qua LLM) phải có giá trị thời gian gốc. Plan 1.11 B.7: "trục thời gian dùng thời điểm có trong ca".
   - Cách làm do bạn chọn, ghi trong báo cáo. Gợi ý: Gateway giữ hai bản cho mỗi bộ (bản gốc cho khối, bản che cho LLM); hoặc khi dựng khối thì khôi phục bằng `deid_session` cho **riêng cột `thoi_gian`**.
   - Họ tên, SĐT, mã người bệnh trong ô chữ vẫn phải bị che trong **cả hai** bản.
   - Kiểm mọi bộ dữ liệu, không chỉ của `lay_du_lieu_ca`.
   - **Test:**
     - khối của `lay_du_lieu_ca` có `thoi_diem` parse được ISO 8601, khớp giá trị trong ca;
     - tóm tắt gửi LLM vẫn không có ngày gốc nếu bộ che đang che ngày;
     - canary tên/SĐT trong ô chữ không xuất hiện trong khối.
2. **Câu tổng liều 24 giờ bị bộ kiểm chứng bỏ.**
   - Tái hiện bằng LLM giả trả một câu kiểu: "Tổng liều meropenem trong 24 giờ là **3.000 mg** (3 liều 1.000 mg lúc 06:00, 14:00, 22:00) [n]", trích căn cứ của `lay_du_lieu_ca`.
   - Tìm vì sao bị bỏ: số `3000.0` vs "3.000", giờ "06:00", mã căn cứ `ca:lich_dung` không được bộ kiểm chứng nhận, hay lý do khác.
   - Sửa **phía tool**: văn bản tóm tắt có đủ con số, định dạng mà bộ kiểm chứng đối chiếu được, kiểu và mã căn cứ đúng loại `du_lieu`/`tinh_toan` mà bộ kiểm chứng đang chấp nhận. Tổng 24 giờ là số **code tính**, nên căn cứ nên là loại tính toán nếu bộ kiểm chứng phân biệt.
   - **Không** nới logic kiểm chứng số trong `app/verify`. Nếu thật sự không thể sửa phía tool thì dừng và ghi rõ lý do, đề xuất cách sửa bộ kiểm chứng trong báo cáo, không tự sửa.
   - Test đồ thị agent LLM giả: câu trên qua kiểm chứng, `trang_thai == "ok"`, có `minh_hoa`.
3. **Lần chạy lỗi sau 3 giây** (`loi`, chưa gọi tool): đọc mã đường lỗi trong `AgenticAsker`/đồ thị và tìm nguyên nhân có thể (ví dụ lỗi dựng prompt khi kỹ năng có ví dụ mới, lỗi phân tích lời gọi tool). Nếu tìm ra lỗi tái hiện được thì sửa và thêm test. Nếu không tái hiện được thì ghi trong báo cáo các khả năng đã loại trừ. Không gọi mạng.

## Tệp

Được sửa: `app/agent/tools/**`, `app/agent/nodes.py`, `app/agent/state.py`, `app/agent/minh_hoa/**`, `tests/agent/**`. Báo cáo: ghi tiếp mục "fix-2" vào `plan/briefs/VZ2-bao-cao.md`.

**Cấm:** như brief VZ2. Không sửa `app/verify/**`, `app/deid/**`. Không gọi `load_env_file()`, không đọc `.env`, không kết nối DB, không mạng.

## Nghiệm thu

```
uv run ruff check app tests && uv run ruff format --check app tests/agent
uv run pytest -q -p no:cacheprovider tests/agent/test_tool_lay_du_lieu_ca.py tests/agent/test_minh_hoa_do_thi.py tests/agent/test_gateway.py
```
Claude chạy lại 4 câu thật ở trên.
