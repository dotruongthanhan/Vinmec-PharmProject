# CLAUDE.md – Vinmec-PharmProject

File này để bất kỳ phiên Claude nào (kể cả tài khoản khác) đọc là biết dự án đang ở đâu và mình được làm gì. Đọc xong file này thì đọc `plan/HANDOFF.md` (bàn giao giữa các phiên, việc phải làm ngay) rồi `plan/TRACKING.md`.

## 1. Dự án là gì

Hệ thống AI agent hỗ trợ dược sĩ lâm sàng (DSLS) thẩm định y lệnh, Khoa Dược Vinmec Times City, trong chương trình Vinmec AI Exploration Sprint 6 tuần (VinUni × Vinmec). Nhóm 2 người: Vũ Gia Khải (chủ kho này, nhánh `vukhai248`) và Đỗ Trương Thành Ân.

- Bản plan đầy đủ: `plan/plan-trien-khai-ai-agent-tham-dinh-y-lenh.md`
- **Plan 1.1 – kiến trúc chi tiết** (phân lớp, quy ước hướng đối tượng, cấu trúc thư mục, RAG, đồ thị điều phối, cấu hình, sổ tay thử): `plan/plan-1.1-kien-truc-chi-tiet.md`. Thay mục 4.4 và Phụ lục B của plan gốc. Brief cho T11 trở đi phải bám bản này.
- **Plan 1.2 – giao diện và trải nghiệm cho dược sĩ** (bố cục, thẻ nhận định, khung hỏi thêm, trạng thái, tổ chức code giao diện): `plan/plan-1.2-giao-dien-ui-ux.md`.
- **Plan 1.4 – hệ thống thiết kế cho bản web** (công nghệ giao diện, bảng màu theo nghĩa, thang chữ, đặc tả từng thành phần, danh sách kiểm): `plan/plan-1.4-he-thong-thiet-ke.md`. Mọi brief giao diện phải bám bản này; nó thay câu "CSS thuần, không thêm thư viện giao diện" của plan 1.2.
- **Plan 1.3 – dữ liệu** (sơ đồ nguồn, 4 tầng xử lý, chuẩn hoá tên thuốc, gộp nguồn và xử lý trùng theo tầng tin cậy, cổng chất lượng): `plan/plan-1.3-du-lieu-thu-thap-tong-hop-tien-xu-ly.md`.
- **Plan 1.5 – bảo mật** (xác thực JWT Supabase, refresh token, vai trò `duoc_si_ls` / `admin`, sở hữu hội thoại và phản hồi, kiểm thử, giới hạn tốc độ đang hoãn, bảng theo dõi): `plan/plan-1.5-bao-mat-xac-thuc-phan-quyen.md`; hợp đồng `plan/api-hop-dong-v1.3-xac-thuc.md`.
- **Plan 1.6 – dữ liệu lên Supabase và chuyển từ tệp mock sang SQL** (bản đồ dữ liệu, quy trình nạp, các đợt M0–M5, cổng dữ liệu thật, bảng theo dõi D1–D14): `plan/plan-1.6-du-lieu-tong-hop-len-supabase-va-chuyen-doi.md`. Đến hết demo 20/11 ứng dụng vẫn đọc tệp `data/mock/demo`.
- **Plan 1.7 – dữ liệu bệnh án giả lập (60 hồ sơ)** (cấu trúc bệnh án thật, so sánh với `CaBenh`, mô hình mở rộng, chiến lược tạo và kiểm; bản nháp chờ duyệt): `plan/plan-1.7-du-lieu-benh-an-gia-lap.md`.
- **Plan 1.8 – dữ liệu thật cho thẩm định 7 yếu tố** (từ điển thuốc, bộ phân giải tên → hoạt chất, cào Cục Quản lý Dược / DDInter / RxNav / openFDA, luật từng yếu tố, các đợt D0–D7 có cổng review): `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md`. Làm xong phần này mới sang plan 1.9.
- **Plan 1.9 – Agentic RAG, công cụ và phân quyền** (trước đây đánh số 1.8): `plan/plan-1.9-agentic-rag-cong-cu-va-phan-quyen.md`.
- Tệp nguồn tri thức đã tải (50 nhãn openFDA, DDInter) và tình trạng từng nguồn: `data/kb_sources/README.md`.
- **Hợp đồng API** giữa backend FastAPI (`app/api/`) và bản web React (`web/`): `plan/api-hop-dong-v1.md` và phần bổ sung `plan/api-hop-dong-v1.1-bo-sung.md` (bước AI chạy nền, mở đoạn nguồn). Muốn đổi tên trường thì sửa file này trước.
- Theo dõi tiến độ: `plan/TRACKING.md`
- Brief giao việc cho agent code: `plan/briefs/`
- Báo cáo, ghi chép khảo sát, ERD: `docs/`
- Ngữ cảnh ngoài kho: `D:\create\Khoa dược` (`phan-bien-DLS.md`, `Khảo sát\survay.md`, `Mau-du-lieu-DLS.pdf`)

## 2. Mốc sống còn

**MVP phải chạy trọn và demo được ngày 20/11/2026.** Demo không đạt thì nhóm có thể bị loại. Mọi quyết định ưu tiên theo mục 9.1 của plan: lát cắt dọc trước, mở rộng sau, đóng băng tính năng trưa 19/11.

## 3. Vai trò của Claude trong kho này (người dùng quy định ngày 16/11/2026)

Claude **không viết và không sửa code**, để tiết kiệm quota. Claude chỉ được:

1. Viết brief và giao task cho agent CLI.
2. Nghiên cứu khi cần để viết brief cho đúng.
3. Review code agent trả về (đọc, không sửa).
4. Chạy lệnh để xác nhận khi review: test, lint, script kiểm tra độc lập.
5. Ghi tiến độ vào `plan/TRACKING.md`.

Claude được viết tài liệu: plan, brief, tracking, `CLAUDE.md`, `AGENTS.md`. Thấy code sai thì viết brief sửa và giao lại, không tự sửa.

## 4. Agent code và cách gọi

| Agent | Mô hình | Trạng thái (16/11/2026) | Lệnh |
| :--- | :--- | :--- | :--- |
| Codex CLI 0.160.0 | `gpt-6.1-sol`, **luôn effort `xhigh`** (người dùng chốt 16/11 phiên 3) | Chạy được | `codex exec -m gpt-6.1-sol -c model_reasoning_effort=xhigh -s workspace-write -C <thư mục kho> -o <file báo cáo> "<prompt>"` |
| Gemini CLI 0.68.0 | "Gemini 4 Hydrogen", high – xhigh | Đã cài lại ngày 16/11 (bản cũ mất `bundle/gemini.js`). **Chưa đăng nhập**, người dùng phải tự đăng nhập. `gemini --list-models` chỉ báo `gemini-2.5-pro`, `gemini-3.5-flash`, `gemini-3.1-flash-lite`; chưa biết mã mô hình Gemini 4 | `gemini --skip-trust --approval-mode yolo -m <mã mô hình> -p "<prompt>"` |

| **agy CLI 1.5.9** (đường chạy Gemini 4) | `gemini-4-hydrogen-high`, `gemini-4-hydrogen-xhigh` | Chạy được ở chế độ mặc định (đã thử 16/11). Danh sách mô hình: `agy models` | `agy --model gemini-4-hydrogen-high --mode accept-edits --print-timeout 1200s -p "<prompt>"`; chỉ đọc: `--mode plan` |

**Gemini 4 Hydrogen gọi qua `agy`, không qua `gemini`.** Lệnh `gemini` chưa đăng nhập và không có Gemini 4.

**Giao song song (người dùng cho phép 16/11):** việc độc lập về file thì giao cùng lúc cho Codex và nhiều phiên agy; mỗi brief ghi rõ file được tạo và file cấm đụng để không giẫm nhau. Ưu tiên `gemini-4-hydrogen-xhigh` hơn Codex một chút; Codex luôn chạy `xhigh`. Prompt cho agy phải có câu cấm gọi công cụ shell.

**Quyền khi gọi agy:** `--dangerously-skip-permissions` bị lớp kiểm soát quyền của Claude Code chặn. Dùng `--mode accept-edits --print-timeout 1200s`: agent chỉ ghi file; Claude tự chạy `uv sync`, `ruff`, `pytest` khi review. Với Codex dùng `-s workspace-write`.

Lưu ý khi gọi Codex:

- Cấu hình máy này để `sandbox_mode = danger-full-access`, `approval_policy = never`: Codex tự chạy lệnh và ghi file không hỏi. Vì vậy brief phải nêu rõ phạm vi được đụng và việc cấm làm.
- Prompt dài thì để trong file brief và truyền kiểu: `"Đọc AGENTS.md và plan/briefs/Txx-....md rồi thực hiện đúng brief đó."`
- Task dài hơn 2 phút: chạy nền, đọc file `-o` khi xong.
- Quy tắc chung cho mọi agent nằm ở `AGENTS.md`.

## 5. Quy trình một task

1. Viết `plan/briefs/Txx-ten-task.md`: bối cảnh, phạm vi file, yêu cầu, tiêu chí nghiệm thu chạy được bằng lệnh, việc cấm làm.
2. Thêm dòng vào `plan/TRACKING.md` với trạng thái "đang giao".
3. Gọi agent.
4. Review: đọc diff, chạy `uv run pytest`, `uv run ruff check .`, và **kiểm chứng độc lập** (tự tính lại vài giá trị, không tin test của chính agent viết).
5. Đạt thì ghi "xong" kèm bằng chứng. Chưa đạt thì viết brief sửa `Txx-fix-n.md`, giao lại.

## 6. Những điều đã thống nhất về sản phẩm

- **Kiến trúc lai:** công thức và luật chạy bằng code; RAG lấy đoạn nguồn; LLM chỉ đọc văn bản tự do và viết diễn giải; mọi nhận định qua bước kiểm chứng trích dẫn mới được hiển thị. **LLM không bao giờ tự tính.**
- **Dược sĩ quyết định.** Hệ thống không duyệt thay, không ghi vào `OH` / `EMR`, không gửi tin.
- **Kết luận 4 trạng thái:** đạt · cần xem · không đủ dữ liệu · ngoài HDSD. Thiếu dữ liệu thì nói thiếu, không được ghi "đạt".
- **Dữ liệu:** 100% giả lập. Không có dữ liệu người bệnh thật trong kho, trong prompt, trong log.
- **Nguồn thuốc:** văn bản Bộ Y tế → Dược thư Quốc gia → nhãn FDA (openFDA, DailyMed) → DDInter (chỉ sàng lọc, giấy phép phi thương mại). Không sao chép nội dung UpToDate, MIMS, Micromedex.
- **Công thức:** tự cài bằng Python, có trích dẫn bài báo gốc; kiểm chéo với MedCalc-Bench và `open-medicine`.
- **Ngăn xếp:** Python (quản lý bằng `uv`), pydantic, pytest, ruff; **giao diện chính là bản web React + TypeScript (`web/`) gọi API FastAPI (`app/api/`)**, bản Streamlit (`app/ui/`) chỉ để tham khảo và làm đường lui; **một PostgreSQL có pgvector chạy trên Supabase** (người dùng chốt 16/11, tự cấu hình): dữ liệu thay đổi theo thời gian ở lược đồ `nghiep_vu`, tri thức ít đổi ở lược đồ `tri_thuc`; LangGraph ở lớp điều phối; LLM DeepSeek. Chi tiết ở plan 1.1.
- **Bảo mật:** agent chỉ có công cụ đọc; phát hiện của luật không bị LLM xoá hay hạ mức; có bộ ca tấn công chèn lệnh.

## 7. Khoá API của LLM

**Đã có từ 16/11:** `.env` chứa `OPENROUTER_API_KEY`, `OPENROUTER_API_KEY_2` (nhúng, xếp hạng lại), `DEEPSEEK_API_KEY` (LLM, gọi thẳng `api.deepseek.com`; tài khoản có `deepseek-flash` và `deepseek-v4-pro`), `DATABASE_URL`. Đã gọi thử cả ba dịch vụ, đều chạy. Khoá chỉ nằm trong `.env` (đã nằm trong `.gitignore`), không ghi vào brief, tracking, code, log hay câu trả lời.

## 8. Quy ước

- Viết tiếng Việt trong tài liệu và khi trả lời người dùng.
- Tài liệu ghi nhân sự viện theo **vai trò**, không ghi tên. Không ghi tên hay mã người bệnh.
- Tên trường dữ liệu theo ERD (tiếng Việt không dấu, `snake_case`); tên hàm, lớp, module bằng tiếng Anh.
- Không commit, không push khi người dùng chưa bảo. `docs/bao-cao-tuan-1.md` đang ở trạng thái xung đột hợp nhất, người dùng tự xử lý.
- Ảnh trong `D:\create\Khoa dược\.codex-attachments` và `.codex-remote-attachments` chưa rà PII; không đưa vào kho.

## 9. Câu hỏi còn mở cần người dùng hoặc dược sĩ trả lời

Xem mục 11 của plan (Q1–Q19). Ba câu chặn việc sớm nhất: Q10 (15 hoạt chất đầu), Q3 (dược sĩ duyệt đáp án), Q4 (nguồn được chấp nhận).
