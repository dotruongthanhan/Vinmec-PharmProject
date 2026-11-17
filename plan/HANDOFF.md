# HANDOFF – bàn giao giữa các phiên Claude

## CẬP NHẬT PHIÊN 5 (17/11/2026, khoảng 10:35) – ĐỌC PHẦN NÀY TRƯỚC

Khối "PHIÊN 4" bên dưới vẫn đúng về quyết định của người dùng, bẫy đã gặp và danh sách việc kế; riêng mục 2 và 3 của nó (bốn việc chạy nền) **đã xử lý xong**:

- T14: code đạt. Người dùng đã đặt `DATABASE_URL` Supabase (session pooler); `python -m app.db check` kết nối được, cơ sở dữ liệu còn trống. **Chưa chạy lần nạp thật**, đang chờ người dùng cho phép (`uv run python -m app.db all`). Bộ đệm nhúng mới có ít đoạn; kho vừa dựng lại (3.730 đoạn) nên phải nhúng lại trước khi nạp véc-tơ đầy đủ.
- T24-fix-1: đạt khi gọi thật (câu hỏi demo `ok` 6/6).
- T25-fix-1 + T25-fix-3: đạt; đã tải lại openFDA thật (50/50 nhãn, NDC 50/50). T25-fix-2 bị dừng và thay bằng fix-3.
- T23-fix-1: đạt theo lệnh và theo DOM; **chưa ai xem bằng mắt** (chụp màn hình hết giờ). Nhờ người dùng xem qua hoặc thử chụp lại.
- Toàn kho: 723 test qua, 0 trượt; web 141 test qua. Commit mới nhất là `d042d0c`; mọi thay đổi của phiên 4 và 5 chưa commit.
- Người dùng chốt phiên 5: code chính giao **Codex `gpt-6.1-sol` xhigh trước**, agy `gemini-4-hydrogen-xhigh` dự phòng.
- Cổng 8000 đang bị một tiến trình `uvicorn` cũ giữ (code cũ); khi kiểm dùng cổng khác hoặc nhờ người dùng tắt.

Việc kế: mục 5 của khối phiên 4, bắt đầu từ bước 2 (chạy trọn kịch bản demo) và các brief chưa viết ở bước 3.

---

## CẬP NHẬT PHIÊN 4 (17/11/2026, khoảng 10:30) – ĐỌC PHẦN NÀY TRƯỚC

Các khối "CẬP NHẬT PHIÊN 2/3" bên dưới đã cũ; chỉ dùng để tra lệnh. Vai trò của Claude không đổi: **không viết, không sửa code**; chỉ viết brief, giao agent, review bằng lệnh, ghi `plan/TRACKING.md`.

### 1. Người dùng đã chốt trong phiên này

- Giao diện: **không chuyển Next.js**, giữ Vite + React + Tailwind v4 + Radix, thêm `react-router-dom`, `motion`, `@supabase/supabase-js` (4 gói đã cài trong `web/`).
- Bố cục: trang chủ → đăng nhập → bàn làm việc ba cột (thanh bên tính năng nền tối · danh sách y lệnh mỗi dòng một y lệnh · trợ lý AI gõ câu hỏi). Phải "fancy", tránh dấu hiệu giao diện do AI sinh (danh sách cấm ở `briefs/T23-…md` mục 3.2). Có **chế độ sáng / tối**.
- Supabase đã kết nối; cần lệnh nạp chạy lại được từ đầu khi sửa trường.
- openFDA: dùng API của họ; kết quả khảo sát ở `data/kb_sources/openfda_api.md`.
- Được giao song song Codex `gpt-6.1-sol` **xhigh** và agy `gemini-4-hydrogen-xhigh`, cái nào làm chính cũng được. Được chạy `npm install` trong `web/`.

### 2. Việc đang chạy nền lúc bàn giao (phiên mới không nhận được thông báo hoàn tất, phải tự kiểm)

| Task | Agent | Brief | Tệp báo cáo | Cách biết đã xong |
| :--- | :--- | :--- | :--- | :--- |
| T14 nạp Supabase | Codex xhigh | `briefs/T14-nap-du-lieu-supabase.md` | `plan/reports/T14.md` | Tệp báo cáo có nội dung; có `db/schema.sql`, `app/db/` |
| T23-fix-1 sửa giao diện + sáng/tối | Codex xhigh | `briefs/T23-fix-1.md` (+ `T23-bo-sung-1-che-do-sang-toi.md`) | `plan/reports/T23-fix-1.md` | Tệp báo cáo có nội dung |
| T24-fix-1 chatbot | Codex xhigh | `briefs/T24-fix-1.md` | `plan/reports/T24-fix-1.md` | Tệp báo cáo có nội dung |
| T25-fix-1 truy vấn openFDA | agy xhigh | `briefs/T25-fix-1.md` | `plan/reports/T25-fix-1.md` | Tệp kết thúc bằng mẫu báo cáo `TRẠNG THÁI…` |

Tệp báo cáo rỗng hoặc tệp `.log` kết thúc bằng `Selected model is at capacity` nghĩa là phiên agent đã chết: kiểm `git status` xem đã ghi gì, rồi giao lại đúng brief đó (Codex quá tải thì chuyển agy, thêm câu "không gọi công cụ shell" và tự chạy phần nghiệm thu).

### 3. Review từng việc khi về

Chạy đúng mục "Nghiệm thu" của brief, cộng các kiểm độc lập sau:

- **T24-fix-1:** `uv run uvicorn app.api.main:app --port 8010`, rồi gọi `POST /api/cases/DEMO-02/ask` bằng Python `httpx` (gọi bằng `curl` từ Git Bash làm hỏng tiếng Việt, ra 400). Câu `Vì sao cần xem lại liều meropenem ở ca này?` phải ra `ok` có trích dẫn (trước khi sửa ra `khong_co_nguon`); câu chèn lệnh phải ra `ngoai_pham_vi`. Mở một `doan_trich_id` trong câu trả lời qua `/sources/…`. `GET /api/cases` phải có `ma_y_lenh`, `thoi_diem_ke`, `nguoi_benh_tom_tat`, `thuoc`. Đọc diff `app/verify/` để chắc bước kiểm con số không bị nới.
- **T23-fix-1:** trong `web/`: `npm run build`, `npm run lint` (0 cảnh báo), `npx vitest run`. Mở trình duyệt (`.claude/launch.json` có `cdss-web` cổng 5173, backend cổng 8000 phải **khởi động lại** để nạp code mới): trang chủ `/`, `/dang-nhap` → nút `Vào bản demo`, `/app`, `/app/y-lenh/DEMO-02`. Soát: dấu tiếng Việt ở tiêu đề chữ có chân (trước đó vỡ: "Tấ t cả y lệnh"), F5 không bị đá về đăng nhập, bảng không tràn ngang, đủ cột y lệnh, chuyển sáng / tối ở cả năm màn, gõ một câu hỏi vào trợ lý với backend thật.
- **T14:** `uv run pytest -q tests/db`, `uv run python -m app.db all --dry-run`, `uv run python -m app.db check`. Lúc phiên này kết thúc còn 1 test trượt (`tests/db/test_cli.py::test_sql_schema_only_targets_allowed_namespaces`) do agent đang làm dở. Đọc `db/schema.sql`: chỉ đụng lược đồ `nghiep_vu`, `tri_thuc`; `embedding halfvec(2048)`. **Không chạy lệnh ghi vào cơ sở dữ liệu thật**; hướng dẫn người dùng tự chạy `uv run python -m app.db all` lần đầu.
- **T25-fix-1:** agy không chạy lệnh, Claude tự chạy: `PYTHONIOENCODING=utf-8 uv run python -m app.kb.fetch openfda`, `… ndc`, `… report`, `uv run python -m app.kb.build`. Đích: 8 hoạt chất có nhãn đúng đường dùng (kiểm `openfda.route` của `levofloxacin`, `ciprofloxacin`), NDC đủ 50 hoặc có lý do, dòng dựng kho còn `over_max=0 under_50=0 empty_act=0`. Sau khi kho đổi, bộ đệm nhúng phải nhúng lại các đoạn mới.

### 4. Hiện trạng đã kiểm trong phiên này

- T22 (giao diện theo plan 1.4) đã xong và đã commit `ee0912d`. Mọi thứ sau đó **chưa commit**.
- T23 (Hydrogen): dựng được cả năm màn, chạy với backend thật; 10 lỗi A1–A10 ở `briefs/T23-fix-1.md`.
- T24 (Hydrogen): toàn kho 656 test qua; phần an toàn đúng; câu hỏi chính của demo ra `khong_co_nguon`.
- T25 (Codex): code xong; Codex không tải được vì hộp cát chặn mạng; Claude chạy tải thật: NDC 46/50, 8 nhãn đường tiêm báo "không tìm thấy" sai.
- Bước AI nền (T12) chạy thật trên DEMO-02: xong sau 30,3 giây, 4 nhận định có diễn giải. Lỗi treo nhúng OpenRouter hôm 16/11 không còn tái hiện.
- Hợp đồng API mới: `plan/api-hop-dong-v1.2-hoi-dap.md` (hỏi đáp, và mục 4 thêm 4 trường cho danh sách).

### 5. Việc kế tiếp theo thứ tự ưu tiên (demo 20/11, đóng băng trưa 19/11)

1. Review bốn việc ở mục 2, giao sửa tiếp nếu chưa đạt.
2. Chạy trọn kịch bản demo trên bản đóng gói: `npm run build` trong `web/` rồi `uv run uvicorn app.api.main:app --port 8000`, mở `http://localhost:8000/`.
3. Brief chưa viết: backend kiểm mã phiên Supabase (API đang mở, đăng nhập chỉ chặn ở trình duyệt); T03-fix-1 (câu căn cứ của luật còn thô); câu cảnh báo `ai_ha_muc_bi_loai` thành tiếng Việt; T09 (12–15 ca tấn công, thêm ca giả lập); bảng nhóm dược lý từ `drug/ndc` cho luật dị ứng cùng nhóm; chuyển ứng dụng sang đọc ca từ Supabase (sau T14).
4. T10: sửa `docs/erd.md` (Claude tự làm, là tài liệu).

### 6. Việc chờ người dùng

- Xoá bằng quyền quản trị: `tests/architecture/.tmp`, `tests/kb/.tmp` (Codex để lại, bị khoá quyền; làm 24 test `tests/kb` báo lỗi dọn dẹp; khi chạy lệnh phải thêm `--exclude` / `--ignore` hai thư mục này).
- Tạo `web/.env.local` với `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` và một tài khoản thử trong Supabase Auth; chưa có thì web chạy "chế độ demo".
- Chạy lần nạp Supabase thật sau khi T14 đạt.
- Xin khoá openFDA miễn phí (`OPENFDA_API_KEY` trong `.env`) nếu mở rộng danh mục hoạt chất; chốt danh mục ở `config/kb/hoat_chat_can_lay.yaml`.
- Các câu Q10, Q3, Q4; xung đột hợp nhất `docs/bao-cao-tuan-1.md`.

### 7. Bẫy đã gặp

- agy gọi công cụ shell thì cả phiên ra rỗng: prompt luôn có câu cấm; Claude tự chạy lệnh nghiệm thu.
- Codex với `-s workspace-write` **không ra được mạng**: việc cần mạng (tải openFDA, gọi LLM thật) Claude tự chạy khi review.
- Codex chạy 3 phiên cùng lúc từng báo `model is at capacity` sau khi đọc xong ngữ cảnh.
- Máy chủ `uvicorn` / Vite chạy từ trước không nạp code mới; cổng 8000 có thể đang bị một tiến trình cũ giữ.
- Windows: đặt `PYTHONIOENCODING=utf-8` khi lệnh in tiếng Việt.
- Không đọc, không in giá trị trong `.env`.

---

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
