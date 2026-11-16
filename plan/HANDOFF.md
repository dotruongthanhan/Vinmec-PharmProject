# HANDOFF – bàn giao giữa các phiên Claude

> **CẬP NHẬT PHIÊN 3 (16/11, khoảng 14:30):** đã review 5 task của phiên 2: T19, T20 đạt; T04b đạt ở mức test; T04a, T05 cần sửa. **Đang chạy nền 4 task:** T12 (agy xhigh, nối AI vào API theo `plan/api-hop-dong-v1.1-bo-sung.md`), T21 (agy xhigh, web hiển thị kết quả AI), T05-fix-1 và T04a-fix-1 (Codex xhigh). Nếu phiên này chết trước khi chúng về: kiểm `app/orchestration/`, `web/src/state/useAiReview.ts`, `config/settings.yaml` (mục `llm` phải có `max_tokens: 16000`), `uv run pytest -q tests/kb`; thiếu thì giao lại bằng đúng brief. Cách review từng task nằm ở mục "Nghiệm thu" của brief. Kiểm thật bước AI: script đo ở mục 1 của `briefs/T05-fix-1.md` (DEMO-02 phải có phần AI cả 3 lần). Quy định mới của người dùng: Codex luôn `model_reasoning_effort=xhigh`; ưu tiên agy xhigh. Backend và web chạy một tiến trình: `npm run build` trong `web/` rồi `uv run uvicorn app.api.main:app --port 8000`, mở `http://localhost:8000/`.

> **CẬP NHẬT PHIÊN 2, LẦN 3 (16/11):** T11 và T13 (kèm T13-fix-1) đã xong, 430 test qua. Người dùng chốt thêm: cơ sở dữ liệu trên **Supabase** (tự cấu hình), giao diện chính là **bản web React** ở `web/` gọi API FastAPI (`plan/api-hop-dong-v1.md`), Streamlit chỉ để tham khảo. **Đang giao song song 5 task:** T19, T20, T04a, T04b, T05 (gộp T06); xem `TRACKING.md` để biết task nào đã review. Khi review: agy không chạy được lệnh nên Claude phải tự chạy `uv run pytest`, `ruff`, và trong `web/` chạy `npm run build`, `npm run lint`, `npx vitest run`; `ruff` thêm `--exclude tests/architecture/.tmp`; máy chủ Streamlit / uvicorn phải khởi động lại mới nạp code mới. Sau đợt này: T12 (đồ thị + nối các phần), T03-fix-1, T14, T16. Còn 3 plan con: 1.1 kiến trúc, 1.2 giao diện, 1.3 dữ liệu.
>
> **CẬP NHẬT PHIÊN 2, LẦN 2 (16/11):** người dùng đã duyệt plan 1.1 (đổi sang PostgreSQL + pgvector, DeepSeek gọi thẳng) và đưa khoá (đã ở `.env`). Đã viết plan 1.2 (giao diện). **Đang giao:** T11 (Codex, khung kiến trúc) và T13 (agy xhigh, giao diện); xem `TRACKING.md` để biết đã review chưa. Dữ liệu nguồn đợt 1 ở `data/kb_sources/` (đọc `README.md` ở đó). Sau khi T11 đạt: viết brief T04a (cắt đoạn nhãn openFDA, dựng kho), T04b (nhúng, xếp hạng lại, truy xuất lai), T05 (DeepSeek + tổng hợp), T06 (kiểm chứng), giao song song; T14 (PostgreSQL) cần người dùng bật Docker Desktop. Người dùng yêu cầu: review xong thì báo và **xin phép trước khi giao việc kế**. Không kéo dữ liệu từ `doctorabad.com`.
>
> **CẬP NHẬT PHIÊN 2 (16/11):** T07, T07-fix-1, T08-fix-1 đều xong và đã review; toàn kho 344 test qua, lint và định dạng sạch; hai tồn đọng của T03 đã đóng. Đã viết `plan/plan-1.1-kien-truc-chi-tiet.md` và **đang chờ người dùng duyệt D1–D8** (mục 1 của bản đó), khoá OpenRouter, mã mô hình DeepSeek. Duyệt xong thì việc kế tiếp là viết brief T11 (khung kiến trúc), rồi T04a / T04b song song. Khi gọi `agy` phải thêm câu cấm gọi công cụ shell vào prompt (lần gọi đầu của T07 ra rỗng vì agent tự gọi shell). Mọi dòng bên dưới nói T07 chưa giao, T08 cần sửa là đã cũ; xem `TRACKING.md`.
>
> **CẬP NHẬT CUỐI PHIÊN 1 (16/11, sau khi viết các mục dưới):** T03 đã về và review đạt trên 6 ca demo (218 test qua). Không còn task nào chạy nền. **Việc đầu tiên của phiên kế:** (a) chạy `uv run ruff format --check .` xem 2 file nào lệch định dạng; (b) tự kiểm 6 giá trị biên của `select_renal_tier` (mục 3); (c) giao T07 bằng lệnh ở mục 4; (d) viết và giao `T08-fix-1` (mục 5, thêm ca `123456789 mmHg` bị che nhầm thành HN). Các dòng nói "T03 đang chạy" bên dưới đã cũ.

**Viết lúc:** 16/11/2026, cuối phiên của tài khoản thứ nhất (sắp hết quota).
**Người đọc:** phiên Claude kế tiếp. Đọc `CLAUDE.md` trước, rồi file này, rồi `plan/TRACKING.md`.

## 1. Việc đầu tiên phải làm khi nhận bàn giao

1. Chạy kiểm tra hiện trạng (không sửa gì):

   ```bash
   git status --short
   uv sync
   uv run ruff check app tests
   uv run ruff format --check app tests
   uv run pytest -q
   ```

2. Xem T03 đã ghi file chưa: `ls app/rules data/kb tests/rules`. Nếu có đủ file ở mục 2 của `plan/briefs/T03-bo-luat-v0.md` thì review theo mục 3 dưới đây. Nếu thiếu hoặc dở dang (phiên agy có thể đã chết cùng phiên Claude cũ) thì **giao lại T03 từ đầu** bằng lệnh ở mục 4; brief đã đủ để làm lại, agent ghi đè file dở.
3. Sau khi T03 đạt: giao T07 (brief đã viết sẵn).

## 2. Hiện trạng từng task

| Task | Agent | Trạng thái lúc bàn giao | Việc của phiên kế |
| :-: | :--- | :--- | :--- |
| T01 khung + công thức | agy high | **Xong, đã review** | Không |
| T02 mô hình dữ liệu + 6 ca demo | agy xhigh | **Xong, đã review.** 49 test qua; 6 ca đúng bảng mục 5 của brief; đáp án khớp. Còn 1 chỗ lệch định dạng trong `app/domain/models.py`, đã gộp vào T03 (mục 9b của brief T03) | Không |
| T08 che định danh | Codex high | **Code có, 125 test qua, lint sạch, nhưng cần sửa** (3 lỗi ở mục 5). Tiến trình Codex đã kết thúc; kết quả kiểm lại sau khi kết thúc vẫn như trên | Viết và giao `T08-fix-1` |
| T03 bộ luật v0 | agy xhigh | **Đang chạy nền lúc bàn giao**, chưa có file nào trong `app/rules/` | Review hoặc giao lại |
| T07 pipeline + giao diện | — | **Brief viết xong, chưa giao** (chờ T03 vì cùng sửa `pyproject.toml` và dùng `app/rules`) | Giao sau khi T03 đạt |
| T05 bước LLM | — | **Bị chặn: chưa có khoá API.** Người dùng sẽ đưa khoá trong chat khi được hỏi | Khi T03 và T07 đạt thì hỏi người dùng khoá, viết brief |
| T04, T06, T09, T10 | — | Chưa viết brief | Xem mục 6 |

## 3. Cách review T03 (mong muốn cụ thể)

Chạy 4 lệnh ở mục 8 của brief T03. Sau đó **tự kiểm độc lập**, không dựa vào test của agent:

- Chạy `uv run python -m app.rules data/mock/demo/DEMO-0x.json` cho cả 6 ca và so tay với bảng mục 6 của brief:
  - DEMO-01: không có mục nào khác "đạt".
  - DEMO-02: đúng một mục yếu tố 6, cần xem, nghiêm trọng; mô tả có `16.0`; 3 căn cứ theo thứ tự dữ liệu → tính toán → tài liệu; căn cứ dữ liệu trỏ `XN-DEMO02-01` (creatinin 212), không phải kết quả cũ 150.
  - DEMO-03: yếu tố 1, không đủ dữ liệu.
  - DEMO-04: không có mục cần chú ý; có mục đạt `khang_sinh_vi_sinh_nhay`.
  - DEMO-05: yếu tố 7, cần xem.
  - DEMO-06: yếu tố 1, cần xem, nghiêm trọng, `di_ung_cung_nhom`.
- Kiểm biên chọn mức liều thận: CrCl 50 → mức 2; 50.01 → mức 1; 25 → mức 3; 25.01 → mức 2; 10 → mức 3; 9.99 → mức 4.
- Mở `data/kb/quy_tac_lieu_than.json`: chỉ được có meropenem, đúng nội dung mục 4.4 của brief. Agent thêm hoạt chất hay ngưỡng khác là lỗi.
- Xác nhận agent không sửa `app/calc`, `data/mock`, `data/gold`; trong `app/domain` chỉ có đúng một dòng gộp theo mục 9b.
- Đạt thì ghi "xong" kèm bằng chứng vào `TRACKING.md`. Chưa đạt thì viết `plan/briefs/T03-fix-1.md` nêu đúng chỗ sai, giao lại.

**Lưu ý y khoa:** bảng chỉnh liều meropenem trong brief T03 do Claude ghi theo trí nhớ về nhãn FDA MERREM IV, **chưa đối chiếu nhãn gốc**. Trước demo cần mở nhãn trên DailyMed để đối chiếu và nhờ dược sĩ xem.

## 4. Lệnh giao việc (đã thử, chạy được)

T03, hoặc task khó khác (đổi tên brief):

```bash
agy --model gemini-4-hydrogen-xhigh --mode accept-edits --print-timeout 1500s -p "Doc file AGENTS.md va plan/briefs/T03-bo-luat-v0.md trong thu muc hien tai, roi thuc hien dung brief T03. Chi tao va sua cac file brief cho phep. Khong commit, khong push. Ban khong can chay lenh shell: nguoi review se tu chay lenh nghiem thu. Xong thi tra loi theo mau bao cao trong AGENTS.md."
```

T07:

```bash
agy --model gemini-4-hydrogen-high --mode accept-edits --print-timeout 1500s -p "Doc file AGENTS.md va plan/briefs/T07-pipeline-va-giao-dien.md trong thu muc hien tai, roi thuc hien dung brief T07. Chi tao va sua cac file brief cho phep. Khong commit, khong push. Ban khong can chay lenh shell: nguoi review se tu chay lenh nghiem thu. Xong thi tra loi theo mau bao cao trong AGENTS.md."
```

Codex:

```bash
codex exec -m gpt-6.1-sol -c model_reasoning_effort=high -s workspace-write "Read AGENTS.md and plan/briefs/<ten brief>.md in the current directory, then carry out that brief exactly. Create only the files the brief lists. Do not commit or push. When done, answer using the report template in AGENTS.md."
```

Ghi nhớ khi giao:

- Chạy nền (task mất 5–20 phút); đợi thông báo xong rồi mới review.
- `agy` chỉ ghi file, không chạy lệnh: Claude phải tự chạy `uv sync`, `ruff`, `pytest`.
- Cờ `--dangerously-skip-permissions` của `agy` bị lớp kiểm soát quyền của Claude Code chặn; đừng thử lại.
- Prompt dòng lệnh viết không dấu để tránh lỗi mã hoá trên Windows; nội dung thật nằm trong file brief.
- Hai task chạy song song không được cùng sửa một file. `pyproject.toml` là điểm dễ giẫm nhau nhất.
- In tiếng Việt ra terminal từ Python cần `PYTHONIOENCODING=utf-8`, nếu không sẽ gặp `UnicodeEncodeError` (lỗi của terminal, không phải lỗi code).

## 5. T08 – ba lỗi cần đưa vào brief sửa `T08-fix-1`

Claude đã thử bằng câu tự đặt, ngoài bộ test của agent:

| # | Đầu vào | Kết quả hiện tại | Mong muốn |
| :-: | :--- | :--- | :--- |
| 1 | `báo BS lúc 5/11, CCCD …` | `5/11,` **không bị che** | Phải che. Nguyên nhân: brief gốc cấm dấu `,` và `.` dính ngay sau ngày, trong khi ngày đứng trước dấu câu là chuyện thường. Sửa quy tắc: dấu `,` `.` `;` `:` `)` ngay sau mà **không** kèm chữ số tiếp theo thì vẫn là ngày |
| 2 | `chị Hoa nhà ở Hà Nội` | `Hoa` **không bị che** | Tên một từ sau danh xưng phải che (`chị Hoa`, `anh Nam`, `BS Đức`). Cho phép 1–4 từ viết hoa. Chấp nhận che thừa trong trường hợp như `Bà Rịa` |
| 3 | `liều 1/2 viên; tỉ lệ 3/4` | Thành `[NGAY_1] viên`, `[NGAY_2]` | Không che phân số liều. Không coi là ngày khi ngay sau là đơn vị liều (`viên`, `ống`, `lọ`, `gói`, `liều`, `mg`, `ml`, `g`) hoặc ngay trước là từ `liều`, `tỉ lệ`, `tỷ lệ`. Trường hợp không có dấu hiệu nào thì vẫn che |

Brief sửa cần: nêu 3 ca trên thành test bắt buộc, giữ nguyên 125 test đang qua, giữ khứ hồi `restore_text`, phạm vi chỉ `app/deid/scrubber.py` và `tests/deid/test_scrubber.py`. Đã chạy đúng: `120/80`, `212 umol/L`, `K 4.5`, CCCD, BHYT viết thường, `+84 912 345 678`, đầu vào `None` và đầu vào chứa sẵn `[TEN_1]` đều ném `DeidError`.

## 6. Thứ tự việc sau T03 và T07 (theo mục 9.1 của plan)

1. **T05 – bước LLM (B6):** hỏi người dùng khoá API trong chat; ghi vào `.env` (không ghi ở đâu khác). Brief cần có: lớp trừu tượng nhà cung cấp, prompt có phiên bản, đầu ra JSON theo lược đồ nhận định ở mục 4.3 của plan, văn bản ca đi qua `scrub_text` trước khi gửi, phát hiện của luật luôn được giữ nguyên, chạy được ở chế độ "không có LLM".
2. **T06 – kiểm chứng (B7):** mã căn cứ phải thuộc tập đã cấp; câu trích khớp chuỗi; con số khớp `chi_so`; không đạt thì gắn "chưa kiểm chứng".
3. **T04 – kho tri thức:** chờ câu Q10 (15 hoạt chất). Chưa có câu trả lời thì dùng các hoạt chất trong 6 ca demo: amlodipin, meropenem, amoxicillin, acid clavulanic, ceftriaxon, metoprolol.
4. **T09 – ca tấn công và trang số đo:** 12–15 ca; DEMO-06 là ca mẫu; cần luật phát hiện "đoạn văn bản bất thường" (đáp án DEMO-06 có `van_ban_bat_thuong: true` nhưng chưa có code nào sinh ra cờ này).
5. **T10 – sửa `docs/erd.md`** theo mục 3.2 của plan (Claude tự làm, là tài liệu).
6. Thêm 14–24 ca giả lập để đủ 20–30 ca.

Mốc: hết 17/11 phải có lát cắt dọc trên giao diện (T07). Nếu trễ: bỏ đường cơ sở P2 và ca tấn công, dồn vào đường chạy chính.

## 7. Điều người dùng đã quyết, đừng hỏi lại

- Claude không viết, không sửa code; chỉ giao task, review, nghiên cứu, chạy kiểm chứng, tracking.
- Code giao cho `agy` (Gemini 4 Hydrogen high / xhigh; việc khó dùng xhigh) và Codex (`gpt-6.1-sol` high / xhigh). Được giao song song nhiều phiên.
- Demo 20/11 là mốc sống còn; tuần 3 phải ra MVP chạy trọn.
- Khoá API LLM: người dùng đưa trong chat khi tới T05.
- Không commit khi chưa được bảo. Chưa có gì được commit trong phiên này.

## 8. Việc chờ người dùng

- Khoá API LLM (khi tới T05) và chọn nhà cung cấp.
- Q10: 15 hoạt chất đầu; Q3: dược sĩ duyệt đáp án; Q4: nguồn được chấp nhận.
- Xử lý xung đột hợp nhất ở `docs/bao-cao-tuan-1.md`.
- Lệnh `gemini` (khác `agy`) vẫn chưa đăng nhập; không cần nếu tiếp tục dùng `agy`.
