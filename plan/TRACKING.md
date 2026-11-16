# TRACKING – nhật ký tiến độ

Cập nhật mỗi khi giao, review hoặc đóng một task. Mốc: **MVP demo 20/11/2026** (mục 9.1 của plan).

Trạng thái: `chờ giao` · `đang giao` · `chờ review` · `cần sửa` · `xong` · `bị chặn`

## 1. Bảng task

| Mã | Việc | Bước | Giao cho | Trạng thái | Bằng chứng / ghi chú |
| :-: | :--- | :-: | :--- | :-: | :--- |
| T00 | Plan, `CLAUDE.md`, `AGENTS.md`, tracking | — | Claude | xong | 16/11: plan chuyển vào `plan/` |
| T01 | Khung dự án + công thức (CrCl, eGFR, BSA, BMI, IBW, AdjBW) | B3 | agy `gemini-4-hydrogen-high` | xong | 16/11: `ruff check` sạch; `pytest tests/calc` 27 qua; Claude tự tính lại 14 giá trị, khớp sai số < 1e-5; kiểm tay thiếu đầu vào và 3 ca `ValueError`. Tồn đọng nhỏ: `ruff format --check .` quét cả khối code trong `plan/*.md` → cần thêm `extend-exclude` (gộp vào task sau) |
| T02 | Mô hình dữ liệu ca bệnh (pydantic theo ERD phần MVP) + 6 ca demo JSON + bộ nạp | B1 | agy `gemini-4-hydrogen-xhigh` | xong | 16/11: `ruff check` sạch; `pytest tests/domain` qua (49 test cùng `tests/calc`); Claude in ra và so tay 6 ca với bảng mục 5 của brief, 6 đáp án khớp. Còn 1 dòng lệch `ruff format` trong `models.py`, gộp vào T03 mục 9b |
| T03 | Luật v0: dị ứng, trùng hoạt chất, kháng sinh – vi sinh, chỉnh liều theo thận, lịch dùng | B4 | agy `gemini-4-hydrogen-xhigh` | xong | 16/11: `ruff check` sạch; `pytest` 218 qua; Claude chạy `python -m app.rules` trên 6 ca demo, cả 6 đúng bảng mục 6 của brief (DEMO-02: CrCl 16.0, 3 căn cứ đúng thứ tự, trỏ `XN-DEMO02-01`); bảng luật thận chỉ có meropenem đúng brief. Phiên 2 (16/11) đóng 2 tồn đọng: (1) 2 file lệch định dạng là `app/rules/renal_dose.py`, `tests/rules/test_engine_demo.py`, đã định dạng trong T08-fix-1; (2) Claude tự chạy `select_renal_tier` với CrCl 50 / 50.01 / 25 / 25.01 / 10 / 9.99 → mức 2 / 1 / 3 / 2 / 3 / 4, đúng cả 6. Bảng liều meropenem đã đối chiếu nhãn gốc FDA ngày 16/11 (khớp 4 mức, xem T15). **Còn nợ:** dược sĩ duyệt |
| T04 | Kho tri thức + truy xuất lai. Tách T04a (nguồn, cắt đoạn, dựng kho) và T04b (nhúng, xếp hạng lại, Chroma, BM25, truy xuất) theo plan 1.1 mục 5–6 | B5 | — | chờ T11 | Chưa có Q10 thì dùng 6 hoạt chất của ca demo. T04b cần khoá OpenRouter |
| T05 | Bước LLM tổng hợp (DeepSeek) + lược đồ đầu ra + **kiểm chứng** (gộp T06) | B6, B7 | agy `gemini-4-hydrogen-xhigh`; sửa: Codex xhigh | cần sửa (đang giao fix) | 16/11 phiên 3: Claude chạy thật với DeepSeek. DEMO-06 đạt: phát hiện dị ứng chéo của luật còn nguyên, AI thêm diễn giải có trích nguyên văn khớp nhãn, và tự báo "Bệnh án có đoạn văn bản bất thường, giống chỉ thị cho hệ thống" (câu chèn lệnh không có tác dụng). **DEMO-02 trượt cả 3 lần:** `finish_reason=length`, `reasoning_tokens=4096` = toàn bộ `max_tokens`, nội dung rỗng → rơi về chỉ có luật, mã lỗi `dau_ra_khong_hop_le` không nói rõ nguyên nhân. Mỗi lần gọi 20–23 giây. Brief `briefs/T05-fix-1.md`, giao Codex xhigh |
| T06 | Bước kiểm chứng trích dẫn, con số | B7 | — | gộp vào T05 | Xem T05 |
| T07 | Pipeline + giao diện Streamlit: danh sách ca → màn hình ca, phản hồi | B8 | agy `gemini-4-hydrogen-high`; chỉnh nhỏ: Codex | xong | 16/11 phiên 2: lần gọi agy đầu ra rỗng (agent tự gọi lệnh shell, bị từ chối quyền) → giao lại kèm câu cấm gọi shell, đạt. `ruff check` sạch; 11 test mới qua; Claude tự tính tay CrCl 16,0 và eGFR 20,57 của DEMO-02, khớp; mở giao diện thật ở `localhost:8501`, xem DEMO-01 và DEMO-02, bấm "Đồng ý" → có dòng trong `data/runtime/phan_hoi.jsonl` (đã nằm trong `.gitignore`). 5 điểm chỉnh nhỏ ở `briefs/T07-fix-1.md` (định dạng 2 file, BSA 2 số lẻ, nhãn nút thanh bên bị diễn giải markdown, chuỗi khuyến cáo không dấu, mã nội bộ hiện thô): Codex làm xong, `ruff check` và `ruff format --check .` sạch toàn kho, 344 test qua, Claude thử tay `metric_text` và `plain_label`. Chưa mở lại giao diện để nhìn sau lần chỉnh này |
| T08 | Cổng che định danh bản tối giản (regex, đóng khi lỗi) | B2 | Codex `gpt-6.1-sol` high | xong | 16/11: bản đầu có 4 lỗi (ngày trước dấu phẩy không che; tên một từ sau danh xưng không che; phân số liều `1/2 viên` bị che thành ngày; số 9 chữ số kèm đơn vị bị che thành HN). Sửa bằng `briefs/T08-fix-1.md` (Codex; lần chạy 1 dừng đúng quy định vì test cũ `BS An` mâu thuẫn quy tắc mới, Claude duyệt đổi đúng kỳ vọng đó rồi giao lại). Sau sửa: lint và định dạng sạch, toàn kho 332 test qua; Claude thử 19 câu tự đặt ngoài bộ test, đúng cả 19, khứ hồi `restore_text` đúng. Biết trước: che thừa địa danh sau danh xưng (`Bà Rịa`), chấp nhận |
| T09 | 12–15 ca tấn công + trang số đo | — | — | chờ viết brief | |
| T11 | Khung kiến trúc theo plan 1.1: `config/`, `app/config`, `app/core`, `app/container.py`, nhà cung cấp giả, lớp bọc `Rule`, test kiến trúc, khung `notebooks/` | — | Codex `gpt-6.1-sol` high | xong | 16/11: 29 file mới, không đổi hành vi cũ; toàn kho **418 test qua**; lint và định dạng của phần T11 sạch. Claude kiểm độc lập: `load_settings()` đúng giá trị plan 1.1; `build_container("test")` ra 5 luật, 6 ca; `build_container("dev").llm` ném `ConfigError` đúng câu; `run_registered` bằng đúng `run_rules` trên 6 ca; BM25 truy vấn không dấu trúng đoạn có dấu và lọc theo hoạt chất đúng; kho trong bộ nhớ ghi đè theo mã, lọc trước khi xếp hạng; sổ tay `00_cau_hinh` 5 ô, không có đầu ra; khoá chỉ có trong `.env`. **Tồn đọng:** Codex để lại thư mục `tests/architecture/.tmp` bị khoá quyền (không đọc, không xoá được từ phiên Claude; `ruff` phải thêm `--exclude tests/architecture/.tmp`). Người dùng cần xoá bằng quyền quản trị |
| T13 | Giao diện đợt 1 theo plan 1.2 | B8 | agy `gemini-4-hydrogen-xhigh`; sửa: Codex | xong | 16/11: 2.113 dòng ở `app/ui/`, 9 thành phần; 50 test giao diện qua. Claude mở giao diện thật (1366 × 768), xem DEMO-02: hàng đợi xếp theo ưu tiên, dải định danh có CrCl và dị ứng, thẻ nhận định 3 cột có nhãn `Luật`, căn cứ 3 dòng đúng thứ tự, trạng thái "Đã phản hồi", khung hỏi thêm ở trạng thái chưa nối, dòng "Chưa có luật kiểm tra cho yếu tố 3, 4, 5". 6 điểm phải sửa ở `briefs/T13-fix-1.md`: 2 lỗi lint + 1 file lệch định dạng; số ngày nằm viện lấy sai mốc (ra 10, đúng là 3); creatinin trong 6 ca demo không có khoảng tham chiếu nên DEMO-02 hiện "không có xét nghiệm ngoài ngưỡng" (agent phát hiện đúng, brief gốc của Claude sai kỳ vọng); không được nói "không bất thường" khi thiếu khoảng tham chiếu; dòng yếu tố chưa kiểm phải luôn hiện; thêm test chạy thử cả ứng dụng bằng `AppTest`. **T13-fix-1 (Codex) xong:** lint và định dạng sạch, toàn kho **430 test qua** (có test chạy thử cả ứng dụng trên 6 ca); Claude đối chiếu 6 ca: khoảng tham chiếu creatinin đúng theo giới, DEMO-02 nằm viện 3 ngày, dòng creatinin `212,0 ▲ (từ 150,0, sau 3 ngày)`; mở lại giao diện thật xác nhận. Lưu ý: máy chủ Streamlit chạy từ trước không nạp lại module đã đổi, phải khởi động lại mới thấy bản mới |
| T14 | PostgreSQL + pgvector trên **Supabase**: `schema.sql` hai lược đồ, kho ca SQL, kho véc-tơ, lệnh nạp | — | — | chờ viết brief | Chờ người dùng cấu hình xong Supabase và đặt `DATABASE_URL` vào `.env` |
| T19 | API backend FastAPI theo `api-hop-dong-v1.md` | B8 | Codex `gpt-6.1-sol` high | xong | 16/11 phiên 3: toàn kho 565 test qua (1 trượt thuộc T04a). Claude chạy `uvicorn` thật và gọi: `/api/health`, `/api/cases` (6 ca), `/api/cases/DEMO-02` (CrCl 16,0; 1 nghiêm trọng; nằm viện 3 ngày; creatinin 212,0 ▲), bản ghi đúng ca → 200, bản ghi ca khác → 404, ca lạ → 404, phản hồi `bac_bo` thiếu lý do → 422, lý do ngoài danh sách → 422, mã nhận định lạ → 404; `/` phục vụ `web/dist`. Tồn đọng chung: câu căn cứ do luật sinh còn thô (`212.0 umol/L lúc 2026-11-10T05:30:00+07:00`, `thuc_te`) → T03-fix-1 |
| T20 | Bản web chính React + TypeScript theo plan 1.2 | B8 | agy `gemini-4-hydrogen-xhigh` | xong | 16/11 phiên 3: `npm run build` đạt (JS 311 kB), `vitest` 22 test qua, `npm run lint` còn 3 cảnh báo (đưa vào T21). Claude mở bản đóng gói ở `localhost:8000` với API thật (1366 × 768): hàng đợi 6 ca xếp theo ưu tiên, dải định danh, 4 chỉ số, thẻ nhận định 3 cột, căn cứ 3 dòng, bấm "Mở bản ghi" ra hộp thoại creatinin 212,0 (khoảng 44,0 – 80,0), trạng thái đã phản hồi, không lỗi console. Không có chèn HTML thô trong mã nguồn |
| T04a | Tiền xử lý 50 nhãn openFDA, chuẩn hoá tên thuốc, cắt đoạn theo cấu trúc, lệnh `python -m app.kb.build` | B5 | agy `gemini-4-hydrogen-xhigh`; sửa: Codex xhigh | cần sửa (đang giao fix) | 16/11 phiên 3: lệnh dựng kho chạy trọn `labels=50/50 chunks=3738 table=232 over_max=0 under_50=0 empty_act=0`; Claude mở đoạn bảng liều thận meropenem: đúng 4 mức, khớp bảng luật. Lỗi: 1 test trượt (gán bảng trong tệp mẫu), 2 lỗi lint, 6 file lệch định dạng, tên tiểu mục dính chữ đầu thân bài (`… Renal Impairment Dosage`), `url_goc` rỗng. Brief `briefs/T04a-fix-1.md`, giao Codex xhigh |
| T04b | Nhúng và xếp hạng lại qua OpenRouter, bộ đệm, RRF, truy xuất lai, bộ dựng truy vấn | B5 | Codex `gpt-6.1-sol` high | xong ở mức test | 16/11 phiên 3: test của phần này qua trong lần chạy toàn kho. **Chưa chạy thật** truy xuất trên kho 3.738 đoạn: `build_retriever` nhúng cả kho khi dựng, quá chậm cho lần đầu → T12 dựng lười theo hoạt chất; sẽ đo thật khi review T12 |
| T15 | Dữ liệu nguồn: tải, lập manifest, kiểm | — | Claude (chạy lệnh, tài liệu) | xong đợt 1 | 16/11: 50 nhãn openFDA + 14 tệp DDInter (234.981 cặp) ở `data/kb_sources/`, có `manifest.json` và `README.md`. Đã đối chiếu bảng liều thận meropenem với nhãn gốc: khớp 4 mức. Chưa lấy được QĐ 5948 bản chính thức, Dược thư, nguồn thực phẩm chức năng |
| T12 | Điều phối: nối truy xuất + LLM + kiểm chứng vào API, chạy nền theo hợp đồng v1.1 | — | agy `gemini-4-hydrogen-xhigh` | đang giao | Brief `briefs/T12-dieu-phoi-va-noi-ai-vao-api.md`. Giao 16/11 phiên 3. **Lệch plan 1.1:** bản này điều phối tuần tự bằng code thường, chưa dùng LangGraph (chưa cài, để sau demo) |
| T21 | Web: dải trạng thái AI, diễn giải và đề xuất trên thẻ, thẻ do AI thêm, mở đoạn nguồn; dọn 3 cảnh báo lint | B8 | agy `gemini-4-hydrogen-xhigh` | xong ở chế độ giả lập | 16/11 phiên 3: `npm run build` đạt, `npm run lint` 0 cảnh báo, `vitest` 33 test qua (thêm 11). Claude mở bản chạy `VITE_USE_MOCK=1` và đọc nội dung trang DEMO-02: dải "AI đã phân tích xong (3 giây). 1 nhận định có diễn giải, 1 nhận định do AI thêm", khối "AI · đã kiểm chứng" có Diễn giải và Đề xuất trên thẻ của luật, nhóm căn cứ tăng lên 4. Chưa chụp được ảnh (khung trình duyệt bị ẩn) và **chưa thử với backend thật** (chờ T12) |
| T22 | Làm lại giao diện web theo hệ thống thiết kế (plan 1.4): Tailwind v4, Radix kiểu shadcn, lucide, Inter | B8 | Gemini 4 Hydrogen xhigh (người dùng tự chạy) | chờ giao | Brief dài: `briefs/T22-lam-lai-giao-dien-theo-he-thong-thiet-ke.md`. **Chỉ bắt đầu sau khi T21 xong** (cùng sửa `web/src/`). Bước 0.2 của brief có lệnh `npm install`; Claude chạy lệnh này bị lớp kiểm soát quyền chặn nên người dùng hoặc agent phải chạy |
| T05-fix-1 | Hạn mức token, thử lại khi bị cắt, mã lỗi riêng, giảm suy luận | B6 | Codex `gpt-6.1-sol` xhigh | xong | 16/11 phiên 3: lint và định dạng sạch, 84 test của phần này qua (Codex báo toàn kho 584). Cấu hình: `max_tokens 16000`, `max_tokens_retry 32000`, `reasoning_effort: low` (Codex đo: suy luận 3118 → 1159 token). Claude chạy thật DEMO-02 kèm 3 đoạn nguồn, 3 lần: **cả 3 có phần AI** (4–5 dòng), 23–30 giây mỗi lần. Hai lần có cảnh báo `ai_ha_muc_bi_loai`: AI định hạ mức một phát hiện của luật và bị loại đúng thiết kế. **Tồn đọng:** mã cảnh báo này hiện thô, cần câu tiếng Việt; thời gian vẫn 20–30 giây (thử `thinking: disabled` Codex đo được 3,9 giây, chưa bật vì chưa đánh giá chất lượng) |
| T04a-fix-1 | 6 tồn đọng tiền xử lý nhãn | B5 | Codex `gpt-6.1-sol` xhigh | đang giao | Giao 16/11 phiên 3 |
| T10 | Sửa `docs/erd.md` theo A1–A4, A7, A5 tối thiểu | — | Claude (tài liệu) | chờ làm | |

## 2. Mốc theo ngày (mục 9.1)

| Ngày | Mốc | Đạt? |
| :--- | :--- | :-: |
| 16/11 | Một ca chạy trọn từ JSON đến bảng nhận định ở dòng lệnh | đạt |
| 17/11 | Lát cắt dọc trên giao diện | đạt sớm 16/11 (chưa có LLM) |
| 18/11 | 20 ca chạy không lỗi | chưa |
| 19/11 | Đóng băng trưa; diễn tập 2 lần; video dự phòng | chưa |
| 20/11 | Demo | chưa |

## 3. Tình trạng agent

| Agent | Tình trạng | Ngày kiểm |
| :--- | :--- | :-: |
| Codex CLI 0.160.0, `gpt-6.1-sol`, effort high | Chạy được, đã thử lệnh `codex exec` trả lời đúng | 16/11 |
| Gemini CLI 0.68.0 | Đã cài lại (bản cũ mất `bundle/gemini.js`). **Chưa đăng nhập:** thiếu phương thức xác thực. Danh sách mô hình CLI báo: `gemini-2.5-pro`, `gemini-3.5-flash`, `gemini-3.1-flash-lite`; không thấy Gemini 4 | 16/11 |

| agy CLI 1.5.9 | Chạy được; có `gemini-4-hydrogen-high` và `gemini-4-hydrogen-xhigh`. Đây là đường gọi Gemini 4 Hydrogen | 16/11 |

## 4. Nhật ký

- **16/11** – Viết plan; thêm cột giải thích chi tiết ở 3.2; viết lại 9.1 thành mốc MVP.
- **16/11** – Người dùng quy định: Claude chỉ giao task, review, nghiên cứu, chạy kiểm chứng, tracking; không sửa code. Code giao cho Gemini CLI hoặc Codex CLI.
- **16/11** – Chuyển plan vào `plan/`; tạo `CLAUDE.md`, `AGENTS.md`, `plan/TRACKING.md`, brief T01.
- **16/11** – Thử Codex: đạt. Gemini CLI hỏng cài đặt → cài lại bằng `npm install -g @google/gemini-cli@latest` → chạy được `--version` nhưng chưa có xác thực.
- **16/11** – Tính lại độc lập 15 giá trị kỳ vọng của T01; sửa 5 giá trị trong brief (3 giá trị eGFR CKD-EPI lệch quá sai số cho phép).

- **16/11** – `agy` 1.5.9 chạy được với Gemini 4 Hydrogen. Cờ `--dangerously-skip-permissions` bị lớp kiểm soát quyền của Claude Code chặn → dùng `--mode accept-edits` (agent chỉ ghi file), Claude tự chạy lệnh nghiệm thu.
- **16/11** – Người dùng cho phép giao song song cho Codex và nhiều phiên agy; việc khó ưu tiên `gemini-4-hydrogen-xhigh`.
- **16/11** – T01 xong (agy high). Giao T02 (agy xhigh) và T08 (Codex) song song.

- **16/11** – T02 xong (agy xhigh). Giao T03 (agy xhigh). Viết sẵn brief T07.
- **16/11** – Review T08 (Codex): cần sửa 3 lỗi. Viết `plan/HANDOFF.md` để đổi tài khoản.

- **16/11** – T03 về, review đạt trên 6 ca demo. Phiên Claude thứ nhất hết quota tại đây; T07 chưa giao.

- **16/11 (phiên 2, tài khoản thứ hai)** – Nhận bàn giao. Đóng 2 tồn đọng T03. Giao T07 (agy high) và T08-fix-1 (Codex) song song; cả hai đạt sau 2 lần gọi. Giao T07-fix-1 (Codex).
- **16/11 (phiên 2)** – Người dùng hỏi về trang `doctorabad.com/uptodate/d/di.htm`. Kết luận: là bản sao trái phép Lexicomp Drug Interactions (Wolters Kluwer), dữ liệu tĩnh đóng băng tháng 4/2018, không có API. **Không dùng**: vi phạm bản quyền và trái mục 6 của `CLAUDE.md` (không sao chép UpToDate). Nguồn thay thế cho yếu tố 4: Quyết định 5948/QĐ-BYT (danh mục tương tác chống chỉ định), mục tương tác trong nhãn FDA, DDInter (sàng lọc).
- **Lưu ý gọi agy:** thêm vào prompt câu cấm gọi công cụ shell; nếu agent gọi shell thì cả phiên ra rỗng, không ghi file nào.

- **16/11 (phiên 2)** – T07-fix-1 xong. Viết **plan 1.1** (`plan-1.1-kien-truc-chi-tiet.md`) theo yêu cầu người dùng: phân lớp và quy ước hướng đối tượng, thư mục `config/` và `notebooks/`, chiến lược cắt đoạn theo cấu trúc, truy xuất lai, đồ thị LangGraph ở lớp điều phối, ChromaDB cho MVP, nhúng và xếp hạng lại qua OpenRouter, LLM DeepSeek. Chờ người dùng duyệt D1–D8.

- **16/11 (phiên 2)** – Người dùng duyệt hướng plan 1.1, chỉnh: dùng PostgreSQL + pgvector (không ChromaDB), tách lược đồ theo tần suất thay đổi; đưa khoá OpenRouter và DeepSeek (đã ghi `.env`, gọi thử ba dịch vụ đều chạy: nhúng 2048 chiều, cosine Việt – Anh 0,60; xếp hạng lại 0,994 so với 0,0005; DeepSeek có `deepseek-flash`, `deepseek-v4-pro`). Viết **plan 1.2** (giao diện). Giao T11 (Codex) và T13 (agy xhigh) song song. Tải dữ liệu nguồn đợt 1 (T15).
- **16/11 (phiên 2)** – Người dùng đề nghị kéo dữ liệu từ `doctorabad.com`. Claude **không làm**: trang ghi rõ là Lexicomp của Wolters Kluwer, đây là sao chép cơ sở dữ liệu thương mại có bản quyền chứ không phải dữ liệu giả lập. Thay bằng DDInter (đã tải) và QĐ 5948 (chờ bản chính thức).

- **16/11 (phiên 2)** – Viết **plan 1.3** (`plan-1.3-du-lieu-thu-thap-tong-hop-tien-xu-ly.md`): 3 loại dữ liệu, 4 tầng xử lý, chuẩn hoá tên thuốc, quy tắc gộp nguồn theo tầng tin cậy, cổng chất lượng Q1–Q10. Review T11: đạt. Review T13: chạy được, giao T13-fix-1 (Codex).
- **Việc phát sinh chưa giao (chờ người dùng cho phép):** (a) `T03-fix-1`: câu mô tả và căn cứ do luật sinh ra còn thô (`212.0 umol/L lúc 2026-11-10T05:30:00+07:00`, `cân nặng thuc_te`, `CrCl = 16.0`), cần định dạng kiểu Việt; đụng `app/rules` và test so chuỗi. (b) T04a, T04b, T05, T06 theo plan 1.1 mục 11. (c) T14 PostgreSQL khi Docker Desktop bật. (d) T16 bảng tương tác theo plan 1.3.

- **16/11 (phiên 2)** – Người dùng chốt: cơ sở dữ liệu chạy trên **Supabase** (tự cấu hình); giao diện chính là **bản web thật**, Streamlit để tham khảo; backend cũng có thể giao cho Gemini 4 Hydrogen xhigh; việc nào song song được thì giao ngay. Claude cài `fastapi`, `uvicorn`, `httpx` bằng `uv add`, dựng khung `web/` bằng `npm create vite` (React + TypeScript) và cài gói, viết `plan/api-hop-dong-v1.md`, rồi giao 5 task song song: T19 (Codex), T20 (agy xhigh), T04a (agy xhigh), T04b (Codex), T05 gộp T06 (agy xhigh). Các task không đụng file của nhau; không task nào sửa `pyproject.toml` hay `app/container.py`.
- **Việc sau đợt này:** T12 (đồ thị điều phối + nối `ReviewService` / API với tổng hợp và truy xuất), T03-fix-1 (câu căn cứ của luật), T14 (Supabase), T16 (bảng tương tác).

- **16/11 (phiên 3, tài khoản thứ nhất quay lại)** – Đọc lại ngữ cảnh phiên 2. Review 5 task: T19 và T20 đạt (chạy thật API và mở web thật); T04b đạt ở mức test; T04a và T05 chạy được nhưng cần sửa. Viết `plan/api-hop-dong-v1.1-bo-sung.md` (AI chạy nền, mở đoạn nguồn). Giao 4 task song song: T12 và T21 (agy xhigh), T05-fix-1 và T04a-fix-1 (Codex xhigh).
- **Người dùng quy định thêm (phiên 3):** ưu tiên Gemini 4 Hydrogen xhigh hơn GPT một chút; GPT 6.1 luôn dùng effort **xhigh**, không dùng high nữa.
- **Việc sau đợt này:** T14 (Supabase: lược đồ, kho ca, kho véc-tơ), T03-fix-1 (câu căn cứ của luật), T09 (ca tấn công + trang số đo), thêm ca giả lập cho đủ 20, ô hỏi thêm.

- **16/11 (phiên 3)** – Người dùng chê bản web xấu, hỏi về Next.js. Claude viết **plan 1.4** (`plan-1.4-he-thong-thiet-ke.md`): giữ Vite + React, thêm Tailwind v4 + Radix kiểu shadcn + lucide + Inter; bảng màu theo nghĩa, thang chữ, khoảng cách, đặc tả từng thành phần, danh sách kiểm. Đề xuất chưa chuyển Next (lý do ở mục 1.1 của plan 1.4). Viết brief T22.

## 5. Việc chờ người dùng

0. Xoá thư mục `tests/architecture/.tmp` bằng quyền quản trị. Cấu hình xong Supabase (bật phần mở rộng `vector`) và đặt `DATABASE_URL` vào `.env` (cho T14). Xin Khoa Dược bản chính thức QĐ 5948/QĐ-BYT và quyền dùng Dược thư.
1. Khoá API LLM khi tới T05.
2. Q10: 15 hoạt chất đầu tiên; Q3: dược sĩ duyệt đáp án; Q4: nguồn được chấp nhận.
3. Xử lý xung đột hợp nhất ở `docs/bao-cao-tuan-1.md`.
