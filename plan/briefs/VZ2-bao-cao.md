# Báo cáo VZ2 – Lượt 3 (27/11/2026)

## fix-2 (27/11/2026) – CHƯA XONG nghiệm thu đầy đủ

- Gateway tạo bản dữ liệu cho hình có thời gian gốc, sau khi kiểm tra từng ô thời gian là ngày hoặc thời điểm ISO 8601 hợp lệ. Bản mẫu gửi LLM vẫn được che; mọi ô chữ khác và siêu dữ liệu vẫn qua che định danh. Cách này áp dụng cho mọi tool. Quét PII cuối bỏ riêng các ô thời gian ISO hợp lệ khỏi bản sao dùng để quét, còn các phần khác của khối vẫn được quét. Ô thời gian chứa văn bản không hợp lệ làm bộ dữ liệu bị loại.
- `lay_du_lieu_ca` cấp căn cứ tính toán `tinh:lich_dung` cho cả hai bộ lịch/tổng; tổng, số lần và từng mức liều trong cửa sổ tính được ghi vào căn cứ. Không tính lại số trong LLM. Bộ kiểm chứng nhận `ca:lich_dung` nếu trích loại `bang`, nhưng không nhận mã đó với loại `tinh_toan` vì nhánh tính toán của tool yêu cầu tiền tố `tinh:`. Tóm tắt cũ có `3000.0` nhưng thiếu số lần và mức liều; giờ `06:00` được bộ kiểm chứng bỏ qua, còn `3.000 mg` được nhận là 3000. Không sửa `app/verify` hoặc `app/deid`.
- Test LLM giả tái hiện chính xác câu tổng 24 giờ với 3 liều 1.000 mg, qua kiểm chứng và có hình; số không có nguồn bị từ chối. Test hình creatinin so sánh ISO với ca, test mẫu LLM che ngày và canary họ tên/SĐT, cùng test bộ dữ liệu từ tool khác và ô thời gian giả mạo đều đạt.
- Lỗi `loi` sau 3 giây trước khi gọi tool: chưa tái hiện được offline nên chưa xác định được nguyên nhân. Prompt và ví dụ hiện tại cùng lời gọi tool hợp lệ đã chạy thành công với LLM giả; phần dựng prompt thay placeholder chọn lọc bằng regex, không dùng `str.format` trên ví dụ JSON, vì thế không thấy lỗi do dấu ngoặc JSON trong trường hợp này. Đường đi vẫn có thể trả `loi` khi provider ném lỗi, phản hồi sai lược đồ hai lần, hoặc có ngoại lệ ở nút/đồ thị; không đủ trace để chọn một nguyên nhân. Không gọi DeepSeek hay mạng.
- Lệnh ruff toàn bộ `app tests` và format check `app tests/agent`: đạt. Pytest ngoại tuyến từng tệp: `test_tool_lay_du_lieu_ca.py` 31 đạt; `test_gateway.py` 33 đạt; `test_minh_hoa_do_thi.py` 20 đạt, 1 không chạy. Đã dùng `UV_NO_SYNC=1`, `UV_OFFLINE=1`, `KB_SOURCE=file`, cache và basetemp ở `%TEMP%`.
- Ba test tái hiện chạy trước sửa đều trượt: hai lỗi thời gian `[NGAY_n]` không parse được và test tổng liều trả `loi`; sau sửa đều đạt. Lần gọi `uv` đầu bị từ chối quyền cache mặc định, khắc phục bằng cache tại `%TEMP%`. `git diff --check` toàn workspace báo trailing whitespace trong các tài liệu thay đổi sẵn, ngoài phạm vi; kiểm tra riêng các tệp theo dõi đã sửa của fix-2 đạt.
- Không chạy nguyên lệnh pytest ba tệp của brief vì test `test_api_case_returns_block_without_saving_it` import `app.api.main`, tệp này gọi `load_env_file()` ngay khi import, trái yêu cầu trực tiếp của người dùng. Đã chạy các test còn lại bằng `--deselect` test đó; cần người dùng/Claude kiểm thử API khi có cách chạy phù hợp. Bốn câu thật để Claude chạy lại như brief; chưa chạy trong lượt này.
- `docs/du-lieu/ca-gia-lap.md` được bổ sung mô tả xử lý dữ liệu theo quy tắc 9 AGENTS.md; không đổi tệp nguồn hay số dòng. Giới hạn phân quyền từng ca được nêu ở báo cáo trước vẫn chưa giải quyết trong phạm vi fix-2.

## fix-1 (27/11/2026) – CHƯA XONG

- Đã thêm cột logic `chua_bat_dau`, phân biệt tóm tắt chưa bắt đầu, đang dùng và đã ngưng; thêm test cho ba trường hợp. Test web kiểm tất cả ví dụ JSON trong kỹ năng, tối thiểu năm ví dụ, với bộ cột tương ứng.
- **Còn thiếu:** lớp che định danh hiện có che ngày dạng `dd/mm` trong văn bản thành `[NGAY_1]`, nên LLM chưa nhận nguyên ngày như brief yêu cầu. Thời điểm vẫn có trong cột dữ liệu gốc. Không bỏ qua hoặc sửa lớp che định danh ngoài phạm vi brief; cần xử lý an toàn cơ chế này ở lượt sau.
- Nghiệm thu ngoại tuyến: `uv run ruff check app tests` đạt; `uv run pytest -q -p no:cacheprovider tests/agent/test_tool_lay_du_lieu_ca.py` đạt 29 test (thư mục pytest tạm ở `%TEMP%`); `npx.cmd vitest run src/features/minh-hoa` đạt 35 test. Dùng `npx.cmd` vì `npx.ps1` bị chính sách PowerShell chặn. Lần chạy pytest ban đầu với đường dẫn tạm qua `PYTEST_ADDOPTS` sai định dạng gây lỗi quyền; đã sửa đường dẫn và chạy lại thành công. Lần đầu `uv` không truy cập được cache mặc định, đã chuyển cache sang `%TEMP%` và chạy ngoại tuyến.

## Trạng thái: CHƯA XONG

Tool, đăng ký, policy, dữ liệu thời gian, prompt và các test liên quan đã được bổ sung. **Chưa thể xác nhận yêu cầu phân quyền theo từng ca:** hệ thống hiện kiểm vai trò nhưng chưa có kiểm tra người dùng được xem ca cụ thể; yêu cầu trả 404 khi truy cập ca ngoài phạm vi vì vậy chưa đạt. Việc này không thể khắc phục đúng trong phạm vi tệp được phép và khi chưa có quy tắc phân công ca.

## Đối chiếu yêu cầu

1. **Tool `lay_du_lieu_ca`: đạt chức năng, thiếu kiểm quyền theo từng ca.** Lấy `ctx.ca`, không nhận `ca_id`; chế độ chung bị Gateway từ chối, không có ca trả `sai_tham_so`. Sinh xét nghiệm, sinh hiệu, hai bộ lịch/tổng liều, hai bộ kháng sinh/vi sinh và mốc ca. Gateway hiện hữu đánh mã, che PII, quét chèn lệnh và tóm tắt. Tool giữ 2.000 dòng mới nhất trước khi tạo `BoDuLieu`, ghi số dòng gốc, số dòng cắt và lý do trong span. Đã đăng ký ở `app/container.py` và policy cho `duoc_si_ls`, `admin` ở chế độ ca.
   - Tính cờ creatinin theo công thức trong brief; không tìm thấy luật KDIGO tương đương trong `app`. Dùng lại phép đổi đơn vị hiện có. Khi không đủ kết quả trước đó hoặc đơn vị không hỗ trợ, cờ để `null`.
   - Dùng lại quy đổi liều, chọn đối tượng và đơn vị của D5; dùng bảng ánh xạ tên hoạt chất sẵn có. Cửa sổ lịch là `(từ, đến]`. Liều chỉ có tần suất được ghi `suy_tu_tan_suat`, không tạo giờ; nhiều dòng chỉ cộng khi xác định được chúng chồng lấp tại mốc ca. Khi lịch thực và lịch suy từ tần suất trộn lẫn, hoặc thiếu hàm lượng/đường dùng/đối tượng, phần chưa xác định để `null` và nêu trường thiếu. Ngày kháng sinh dựa trên thời điểm kê y lệnh, không dùng giờ máy.
   - **Giới hạn quyền:** `app/api/routes.py` yêu cầu vai trò; `CaseService.ask` trong `app/api/service.py` gọi `_get_case(case_id)` mà không kiểm quyền đối tượng của `principal`; `ToolContext` không mang thông tin phân công. `plan/TRACKING.md` ghi T86 phân quyền theo ca đã hoãn. Test mới chỉ chứng minh tool không nhận mã ca do LLM đưa và không dùng ca khác trong `ctx.cac_ca`; chưa có test A bị từ chối 404 với ca của B, vì hệ thống chưa có khái niệm phân công đó. Không coi đây là kiểm quyền theo ca.
2. **Dấu `doan`, web và test giao diện:** giữ kết quả các lượt trước; không sửa web hay bộ kiểm dấu trong lượt này. Lượt 2 báo 44 test máy chủ và 35 test thư mục web đạt, test giao diện ở mức render/giả lập hook; chưa kiểm bằng trình duyệt thật/API thật trong lượt này.
3. **Kỹ năng prompt: đạt trong phạm vi chỉnh sửa.** Đã bổ sung quy tắc chọn phần dữ liệu/dấu, không vẽ cho câu hỏi một số, không tự dựng giờ; thêm ví dụ V3/V6. Prompt 943 từ theo đếm tách khoảng trắng; hai ví dụ mới qua bộ kiểm máy chủ.

## Đối chiếu kiểm thử

- DEMO-02: 2 dòng creatinin, đối chiếu giá trị, ngưỡng và cờ tăng nhanh; thêm kiểm đổi đơn vị và cửa sổ KDIGO – **đạt**.
- Ba chế phẩm paracetamol: 6.000 mg, trần D5, vượt liều, ba chế phẩm và cửa sổ qua nửa đêm; ranh giới đúng 24 giờ; thiếu lịch/thành phần và mã hoạt chất tương đương – **đạt**.
- Kháng sinh theo mốc ca, mẫu vi sinh có/không có kháng sinh đồ, ngày trong tương lai – **đạt**.
- Canary nội dung diễn biến/chẩn đoán và PII trong bộ dữ liệu, căn cứ và khối hình – **đạt**.
- Chế độ chung, tham số lạ/trùng/rỗng, `ca_id`, trần bộ lọc, ngân sách, 2.500 dòng giữ 2.000 dòng mới nhất và span ghi 500 dòng bị cắt – **đạt**.
- Test cô lập dữ liệu giữa các ca trong ngữ cảnh – **đạt**; test phân quyền người A với ca B trả 404 – **chưa thực hiện được/thiếu cơ chế phân quyền ca**.
- Đồ thị LLM giả `lay_du_lieu_ca` → `ve_bieu_do` đường và mốc y lệnh → câu trả lời đã kiểm chứng chứa một khối minh hoạ – **đạt**.
- Hai ví dụ prompt mới được kiểm bằng `kiem_dac_ta` – **đạt**. Không chạy lại vitest/tsc vì không sửa web trong lượt này.

## Tệp đã tạo hoặc sửa

- `app/agent/tools/lay_du_lieu_ca.py`, `tests/agent/test_tool_lay_du_lieu_ca.py` – tạo mới.
- `app/container.py`, `app/tracing/models.py`, `config/tool_policy.yaml` – đăng ký, policy, khóa span.
- `config/prompts/ky_nang_minh_hoa.v1.md`, `tests/agent/test_minh_hoa_do_thi.py` – hướng dẫn và kiểm hai ví dụ.
- `docs/du-lieu/ca-gia-lap.md` – bổ sung mô tả cách xử lý dữ liệu ca, các trường, số dòng, lệnh và ngày theo quy tắc tài liệu dữ liệu.
- `plan/briefs/VZ2-bao-cao.md` – báo cáo này.

## Lệnh và kết quả

Các lệnh `uv` dùng `--offline --no-sync`, `UV_CACHE_DIR` trong `%TEMP%`; pytest dùng `-p no:cacheprovider` và `--basetemp` mới trong `%TEMP%`. Chạy tuần tự từng tệp:

- `tests/agent/test_tool_lay_du_lieu_ca.py`: **28 đạt**.
- `tests/agent/test_gateway.py`: **31 đạt**; `test_policy.py`: **9 đạt**; `test_tool_tinh_chi_so.py`: **18 đạt**.
- `tests/agent/test_minh_hoa_kiem.py`: **44 đạt**; `test_tool_ve_bieu_do.py`: **11 đạt**; `test_minh_hoa_do_thi.py`: **21 đạt**.
- `tests/tracing/test_tracing.py`: **14 đạt**; `test_sink_db.py`: **12 đạt**.
- `uv run --offline --no-sync ruff check app tests --exclude app/eval,tests/eval --output-format concise`: **đạt**.
- `uv run --offline --no-sync ruff format --check app tests/agent --exclude app/eval --output-format concise`: **đạt**, 237 tệp đúng định dạng.
- `git diff --check` toàn kho: **không đạt** do khoảng trắng cuối dòng đã có trong các tệp tài liệu ngoài phạm vi; `git diff --check` giới hạn các tệp được sửa trong lượt: **đạt**.
- Bộ nghiệm thu pytest toàn thư mục và web là phần Claude chạy theo brief; không chạy toàn bộ vì giới hạn RAM và không sửa web.

## Sự cố khi kiểm tra thủ công

Một lệnh Python kiểm tra quyền đã nhập `tests.auth.support` ngoài pytest mà không đặt `PYTHON_DOTENV_DISABLED=1`. Mã khởi tạo `app.api.main` đã gọi `load_env_file()`, nên **có thể đã đọc `.env` nếu tệp tồn tại**; không có giá trị bí mật nào được in ra. Cấu hình nguồn tự động cũng đã **thử kết nối DB**, trái quy tắc không dùng mạng; hai yêu cầu giả đều trả HTTP 503 do `ConnectionTimeout`, không thu được kết quả kiểm quyền. Đã dừng lệnh, không dùng kết nối đó nữa.

Lần kiểm lại được đặt `PYTHON_DOTENV_DISABLED=1`, `KB_SOURCE=file`, `CASE_SOURCE=file` và chặn `socket.connect`; test thủ công không chạy được vì Windows `asyncio` cần `socketpair` nội bộ cũng bị chặn (`RuntimeError: network disabled for test`). Không coi hai lần này là bằng chứng kiểm quyền. Nhận định thiếu kiểm quyền dựa trên mã nguồn và trạng thái T86 ở trên.

## Việc còn lại

Cần chủ kho chốt mô hình phân công/phạm vi ca, triển khai kiểm quyền đối tượng ở đường nạp ca trước khi tạo `ToolContext`, và thêm test A gọi ca B nhận 404 giống ca không tồn tại. Sau đó nghiệm thu API thật theo các kịch bản Claude trong brief.
