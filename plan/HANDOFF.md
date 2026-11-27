# HANDOFF – bàn giao giữa các phiên Claude

## CẬP NHẬT 28/11/2026 ~3h40 – Deploy agentic + trả lời tự nhiên – ĐỌC PHẦN NÀY TRƯỚC

- **Đã push** `vukhai248` tới `f41764e` (code `c008b02`). **EC2** chạy bản mới, `ask.engine = agentic`, `co_llm = true`; image lùi `bvienx-pharm-api:pre-agentic` (trước đó `pre-gemini`). **Vercel** prod đã deploy lại, `/api/health` qua Vercel ok.
- **Trả lời tự nhiên** (`TRA-LOI-TU-NHIEN` + fix-1, fix-2): khi kiểm chứng trượt/thiếu nguồn hoặc ngoài phạm vi, gọi thêm một lượt LLM "trả lời thận trọng" có kiểm chứng (prompt `config/prompts/tra_loi_trung_thuc.v1.md`), lược câu có số chưa kiểm chứng; câu tấn công vẫn bị chặn cố định, không gọi LLM. Bước tiến trình chỉ hiện "lỗi + Thử lại" khi lỗi thật.
- **Kiểm số:** bỏ qua đúng mẫu đơn vị `/1,73 m²` (`VERIFY-don-vi-1-73`).
- **Chấm lần 3** (Flash Lite): 90 câu 70/90, rò PII 0, tấn công lọt 0; 15 câu minh hoạ đạt hình 7/15.
- **Còn lại:** thử một câu agentic có hình trên tab Vercel; trục y hình đường chưa có đơn vị; phiên đăng nhập web hết hạn 12 giờ (~12:50 28/11) – script giữ phiên `window.__giuPhien` chạy ở cả tab localhost và tab Vercel, chỉ sống khi phiên Claude còn mở.

## CẬP NHẬT 28/11/2026 ~1h45 – VZ2, VZ5, LLM chung + Gemini, đã push + deploy – ĐỌC PHẦN NÀY TRƯỚC

**Đã push** `vukhai248` tới `0754d91`. **EC2** chạy bản mới (image cũ gắn `bvienx-pharm-api:pre-gemini`, `.env.app` thêm `TRACER_HMAC_KEY` sinh trên máy chủ). **Vercel** prod `bvienx-pharm-web.vercel.app` đã lên, `/api/health` qua Vercel → EC2 trả `ok`.

- **VZ2:** tool `lay_du_lieu_ca`, dấu `doan`, sửa hiển thị (fix-1…5). **VZ5 bản nhỏ:** chấm hình trong eval, 15 câu, phiếu 8 nhiệm vụ dược sĩ. VZ3/VZ4 hoãn (MVP 67 ca).
- **LLM:** `ChatLLMClient` (`provider: chat_api`, url/model/`khoa_env` trong `config/settings.yaml`), mã không còn tên nhà cung cấp. Đang dùng `gemini-3.5-flash-lite` + `KeyRouter` xoay `GEMINI_API_KEY_1…8` (**chỉ dev**, có ghi chú xoá khi triển khai). DeepSeek hết số dư (402).
- **Quy tắc vẽ (chủ kho chốt 28/11):** giữ tiêu chí tự vẽ; dược sĩ bảo vẽ thì phải vẽ (máy chủ thêm đúng một vòng).
- **Chấm lần 2 (Gemini Flash Lite):** 90 câu 70/90, rò PII 0, tấn công lọt 0; 15 câu minh hoạ 5/15 (Flash Lite yếu phần vẽ). Báo cáo `plan/reports/danh-gia-hoi-dap/2026-11-28-*-lan2`.

**Việc chờ chủ kho:**
1. ~~AI trên EC2 đang tắt~~ **Đã bật 28/11 ~2h** (chủ kho đồng ý cách 1): 8 khoá ở Parameter Store `/bvienx/llm/gemini_api_key_1…8` (SecureString, khoá KMS mặc định `aws/ssm`); vai trò `vinmec-pharm-ec2-ssm` thêm chính sách riêng `bvienx-read-llm-keys` (chỉ `ssm:GetParameter(s)` trên `/bvienx/llm/*`); EC2 tự đọc, ghi `.env.app` (bản lưu `/home/ubuntu/.env.app.bak-pre-gemini-keys`), `up -d --force-recreate api`. `/api/health` `co_llm=true`; gọi thử LLM trong container trả JSON đúng 0,5 s. **Gỡ:** `aws iam delete-role-policy --role-name vinmec-pharm-ec2-ssm --policy-name bvienx-read-llm-keys`, xoá 8 tham số, xoá 8 dòng trong `.env.app`. Khi triển khai thật bỏ KeyRouter, dùng một khoá trả phí.
2. Đăng nhập lại web 5173 nếu phiên 12 giờ hết hạn (khoảng trưa 28/11). Script giữ phiên chạy trong trang (`window.__giuPhien`, 7 phút/lần, nhật ký `localStorage.__giuPhienLog`); Claude kiểm mỗi giờ phút 13.
3. Trục y hình đường chưa có đơn vị (việc nhỏ, chưa giao).
4. Kiểm 8 khoá Gemini có thuộc các dự án Google khác nhau không (cùng dự án thì chung hạn mức).

## CẬP NHẬT 27/11/2026 tối – UI1 + VZ1 (minh hoạ trong chat) XONG, chưa commit – ĐỌC PHẦN NÀY TRƯỚC

Chủ kho chuyển tài khoản. **Không có agent hay máy chủ nào đang chạy.** Chưa commit gì từ `a044a23` (nhánh `vukhai248`). UI2 (nút mở rộng icon ở góc cho hình, dùng chung với bảng; tab dữ liệu có tên dễ hiểu) đã xong 27/11 tối.

### 1. Trạng thái (chi tiết: `plan/TRACKING.md`, dòng UI1 → VZ1-fix-2)
| Mã | Việc | Trạng thái |
| :--- | :--- | :--- |
| T106–T114 | Tool agent plan 1.9 + bộ chấm hỏi đáp | ✅ (T108–T114 chưa commit). Chấm lần 2: `co_dinh` 16/20, `agentic` 19/20 |
| UI1 (+fix-1) | Bảng Markdown thật trong chat, nút "Mở rộng bảng", cột chat không nở | ✅ đo thật trên 5173 |
| VZ0, TR1 (+fix-1) | Trang mẫu minh hoạ, tracer lõi (vết JSONL 30 ngày) | ✅ |
| VZ1a-2 → VZ1a-5 | Máy chủ: tool `ve_bieu_do`, bộ kiểm `app/agent/minh_hoa/kiem.py`, gắn `minh_hoa` sau kiểm chứng, kỹ năng `config/prompts/ky_nang_minh_hoa.v1.md`, ngân sách vẽ riêng, giữ hình qua lần viết lại, chặn vẽ trùng | ✅ |
| VZ1b | Web: khối minh hoạ trong chat (tải lười, chunk 16,4 KB gzip) | ✅ |
| VZ1-fix-1 | Không trộn số của ca với giá trị giả định (máy chủ + web), bố cục khung hẹp | ✅ e2e đạt |
| VZ1-fix-2 | Lịch sử nhắc hình cũ → LLM không vẽ lại | ✅ DeepSeek 2 lượt liên tiếp đều có hình |
| UI2 | Nút mở rộng icon ở góc cho hình (dùng chung với bảng), tab dữ liệu bỏ mã `ds-n` | ✅ vitest 409/409, kiểm trình duyệt đạt |

Kiểm gần nhất (27/11 tối): ruff sạch; pytest agent 231, orchestration 84, api 218/2 bỏ qua; web tsc sạch, vitest 409/409, build OK. DeepSeek thật DEMO-02: hình có thanh kéo creatinin, 11 dòng lưới Cockcroft-Gault Claude tự tính khớp < 0,01, 0 định danh trong khối.

Phạm vi đã chốt: **VZ1 chỉ làm hỏi đáp theo ca** (chế độ chung đi qua `app/agent/asker.py`, luồng cũ, chưa có hình).

### 2. Việc còn lại (theo thứ tự)
1. **Chủ kho quyết định commit** đợt T108–T114 + UI1 + TR1 + VZ0/VZ1. Không commit lẫn: `gia lap/`, `docs/nghien-cuu/`, `data/formulas/`, `tools/scrape_mdcalc.py`, `plan/brainstorm-huong-moi-2026-11-23.md`, các `docs/*.md` đang ` M`, `.playwright-mcp/`, `config/settings.e2e.yaml` (hồ sơ thử, xem dưới).
2. **Đo kéo thanh khi giảm CPU 6×** bằng Chrome DevTools thật (công cụ trình duyệt của Claude không giả lập được). Mục tiêu: dựng hình < 100 ms, kéo không giật.
3. Việc nhỏ theo dõi:
   - Không có bước lọc mã `mh-n`/`ds-n` khỏi chữ trả lời; hiện chỉ dựa vào prompt.
   - Câu chữ LLM đôi khi nói "chưa có bảng chia đủ mức CrCl" dù tool đã trả 4 mức (chất lượng diễn giải).
   - HD-CA-015: tên giả DEMO-03 có "63" bị bộ kiểm chứng chặn; chủ kho chốt có đổi tên giả không.
   - 17 câu đáp án T112 chờ dược sĩ duyệt (`plan/reports/T112.md`).
4. Các đợt tiếp của plan 1.11: TR2–TR3 (màn xem vết cho admin/dev), VZ2+ (thêm loại hình, chế độ chung).

### 3. Cách chạy e2e minh hoạ
- `preview_start cdss-api-agentic` (hồ sơ `config/settings.e2e.yaml` bật `ask.engine: agentic`, `CASE_SOURCE=file KB_SOURCE=file AUTH_MODE=off`) và `preview_start cdss-web-demo`.
- Mở `/dang-nhap`, bấm "Vào bản demo", chọn ca DEMO-02 qua giao diện. Gõ URL thẳng sẽ mất phiên demo.
- Câu thử: "Meropenem cho ca này có cần chỉnh liều theo thận không, CrCl có sát ngưỡng không? Vẽ hình giúp tôi xem nếu creatinin thay đổi thì mức liều đổi thế nào." Hình về sau khoảng 15–30 giây. Nếu lịch sử cũ gây nhiễu thì bấm "Xoá" trong khung trợ lý.
- Gọi thẳng không qua API: `load_source_cases` → `build_container().agentic_asker.ask(ca, câu, lich_su)` (lịch sử dạng `("nguoi_dung", …)`, `("he_thong", …)`). Cách này không có `ma_vet`.

### 4. Lưu ý vận hành (bài học 27/11)
- **Gọi Codex chạy nền luôn thêm `< /dev/null`**, không ghép chung lệnh với heredoc (có lần treo 2 giờ ở "Reading additional input from stdin..."). Kiểm log khoảng 1 phút sau khi giao.
- Brief lớn thì Codex dừng sớm → tách nhỏ (VZ1a gốc → VZ1a-2/3/4/5).
- Chỉ chạy 1 agent mỗi lúc; pytest từng thư mục một (máy hết RAM).
- `ruff format --check tests` panic vì 25 thư mục `tests/tracing/.tmp-*` bị khoá quyền → chỉ định thư mục con, hoặc chủ kho xoá bằng quyền admin.
- Ghi `plan/TRACKING.md` đôi khi gặp `OSError 22` → thử lại sau vài giây.

## CẬP NHẬT 26/11/2026 tối – Agent tool (plan 1.9) và đánh giá hỏi đáp – ĐỌC PHẦN NÀY TRƯỚC

Chủ kho chuyển việc tool agent sang tài khoản Claude khác. Song song, phiên Claude cũ đang viết **plan 1.11 (tracer + visualizer trong chat)**, tệp `plan/plan-1.11-tracer-va-visualizer.md`. **Không sửa tệp đó.** Phiên cũ cũng đang giao **UI1** (bảng Markdown thành bảng thật và nút mở rộng toàn màn trong khung chat; brief `plan/briefs/UI1-bang-trong-chat-mo-rong.md`, Codex). UI1 sửa `web/src/components/ui/ClinicalMarkdown.tsx`, `dialog.tsx`, `web/src/features/assistant/HistoryDialog.tsx` và test web, nên đừng sửa các tệp này khi UI1 chưa xong. Mã `UI*`/`VZ*`/`TR*` thuộc phiên cũ; phiên tool dùng `T1xx`. Đợt VZ1 của plan 1.11 sẽ sửa `app/orchestration/ask.py`, `app/agent/nodes.py`, `gateway.py`, `schemas.py`: phải báo nhau trước khi giao.

### Thứ tự đọc
1. Khối này.
2. `CLAUDE.md`, `AGENTS.md`.
3. `plan/plan-1.9-agentic-rag-cong-cu-va-phan-quyen.md` (mục 5.2–5.10, 7.1, 9, 10).
4. `plan/TRACKING.md`, các dòng T103 → T114.

### 1. Hiện trạng (nhánh `vukhai248`, PR dotruongthanhan/Vinmec-PharmProject#6 đang mở, **chưa commit đợt này**)
| Mã | Việc | Trạng thái |
| :--- | :--- | :--- |
| T106 | Tool `tra_tuong_tac` | xong 22/11 (đã commit `682fe38`) |
| T107 | Tool `tim_doan_nguon` | xong 22/11 (đã commit) |
| T108 (+fix-1) | Tool `tra_thuoc` (gộp `tra_quy_dinh`) | xong 26/11, chưa commit |
| T109 (+fix-1) | Tool `tinh_chi_so` (CrCl theo IBW/AdjBW, IBW, AdjBW, BSA DuBois) | xong 26/11, chưa commit |
| T110 (+fix-1) | Tool `doc_doan_mo_rong`. Kèm sửa bộ che PII che nhầm 79 mã đoạn, và mẫu chèn lệnh lọt | xong 26/11, chưa commit |
| T111 | Rà danh mục tool: đã cắm 5 tool + `hoi_lai`; C1, C2, C4, B2 hoãn có số đo | xong |
| T112 (+fix-1) | Bộ 90 câu hỏi `data/gold/hoi_dap/cau_hoi_v1.jsonl` (đáp án hiệu chỉnh, không đổi số) | xong, chưa commit. 17 câu chưa chắc chờ dược sĩ duyệt (`plan/reports/T112.md`) |
| T113 (+fix-1) | Công cụ chấm `app/eval/hoi_dap.py` + `tools/cham_hoi_dap.py` | xong, chưa commit |
| T113-lan1 | Chấm thật 20 câu: `co_dinh` 11/20, `agentic` 12/20, rò PII 0, tấn công lọt 0 | `plan/reports/danh-gia-hoi-dap/2026-11-26-lan1/` |
| **T113-fix-2** | Lưu trích dẫn vào `chi_tiet.jsonl` + chế độ `--cham_lai` (chấm lại không gọi LLM) | **⏸️ dừng 13:38, máy hết RAM khi chạy 2 agy song song; chưa ghi tệp nào.** Brief: `plan/briefs/T113-fix-2.md` |
| T114 | Hằng số công thức vào gói ca và `tinh_chi_so` (`app/calc/hien_thi.py`) | xong 17:06, chưa commit |

Kiểm gần nhất, 26/11 13:0x, do Claude phiên cũ chạy:
- `uv run pytest tests/agent tests/orchestration -q`: 231 qua.
- `ruff check app`: sạch.
- Toàn kho sau T114: 1864 qua / 4 bỏ qua. Test độ trễ `test_suggest_index_build_and_query_latency` trượt khi máy tải nặng, chạy riêng thì qua.
- `ruff check .` toàn kho từng báo lỗi trong `pharm-overlay/`. Thư mục này **đã gác và đã vào `.gitignore`**; bỏ qua, không sửa.

Tệp chưa commit thuộc đợt này:
- **Sửa:** `app/agent/{nodes.py,tools/__init__.py,tools/base.py,tools/gateway.py,tools/tim_doan_nguon.py}`, `app/api/lookup.py`, `app/calc/__init__.py`, `app/container.py`, `app/llm/case_context.py`, `app/orchestration/ask.py`, `config/prompts/tac_tu.v1.md`, `config/tool_policy.yaml`, `plan/TRACKING.md`, `plan/plan-1.9-…md`, `tests/agent/test_gateway.py`, `tests/orchestration/test_ask.py`.
- **Mới:** `app/agent/tools/{doc_doan_mo_rong,tinh_chi_so,tra_thuoc}.py`, `app/calc/hien_thi.py`, `app/eval/`, `tools/cham_hoi_dap.py`, `tests/agent/test_tool_*.py`, `tests/calc/test_hien_thi.py`, `tests/eval/`, `data/gold/hoi_dap/`, `docs/du-lieu/bo-cau-hoi-hoi-dap.md`, `plan/briefs/T108…T114*`, `plan/reports/T112*.md`, `plan/reports/danh-gia-hoi-dap/`.
- **Không thuộc đợt này, đừng commit lẫn:** `gia lap/`, `docs/nghien-cuu/`, `data/formulas/`, `tools/scrape_mdcalc.py`, `plan/brainstorm-huong-moi-2026-11-23.md`, các `docs/*.md` đang ` M` (một số đang xung đột hợp nhất, chủ kho tự xử lý), `.streamlit/config.toml` bị xoá.

### 2. Việc tiếp theo (theo thứ tự)
1. **Giao lại T113-fix-2** (brief có sẵn). **Chỉ chạy 1 agent mỗi lúc** để tránh hết RAM.
2. **Chấm lại** bằng đáp án đã hiệu chỉnh:
   ```
   uv run python tools/cham_hoi_dap.py --engine ca_hai --gioi_han 20 --ra plan/reports/danh-gia-hoi-dap/2026-11-26-lan2
   ```
   Gọi DeepSeek thật. Nếu đường hầm RDS chưa mở thì đặt `KB_SOURCE=file`. Mặc định trần 20 câu; dùng `--tat_ca` cho đủ 90 câu khi chủ kho đồng ý chi phí.

   So với lần 1: câu trượt do đáp án hay do hệ thống. Ghi vào TRACKING.
3. **Theo dõi:** `HD-CA-045` agent lần đầu bị chặn `so_khong_co_nguon:7184/425/725` (LLM viết hằng Du Bois kiểu khác, nghi do dấu phẩy thập phân). Nếu lặp lại thì viết brief cho bộ kiểm chứng số nhận cả `0,007184` và `0.007184`.
4. **Việc dữ liệu (giao sub Sonnet):** thêm cột thứ tự đoạn `thu_tu` cho `tri_thuc.doan_trich`. T110 hiện lấy thứ tự từ `chunks.jsonl`.
5. 17 câu đáp án chưa chắc: gửi dược sĩ duyệt (danh sách ở `plan/reports/T112.md`).
6. **Commit đợt T108–T114** khi chủ kho bảo. Không push nếu chưa được bảo.

### 3. Quy tắc bắt buộc (tóm tắt; đủ ở `CLAUDE.md`)
- **Claude không viết code.** Claude chỉ:
  - viết brief, giao agent;
  - review: `uv run ruff check app tests tools`, `uv run ruff format --check …`, `uv run pytest -q -p no:cacheprovider`, rồi kiểm độc lập (tự tính lại vài giá trị, chạy qua API hoặc tool thật);
  - ghi `plan/TRACKING.md`.
- **Chọn agent** (chủ kho chốt 26/11):
  - Codex `gpt-6.1-terra`, effort high → xhigh → max:
    `codex exec -m gpt-6.1-terra -c model_reasoning_effort=high -s workspace-write -C <kho> -o <báo cáo> "Đọc AGENTS.md và plan/briefs/Txx.md rồi thực hiện đúng brief đó."`
  - Codex làm không đạt thì chuyển agy Neon:
    `agy --model gemini-4-neon-xhigh --mode accept-edits --print-timeout 3600s -p "… KHÔNG gọi shell …"`
    agy không chạy được lệnh, nên Claude tự chạy `ruff format` và test.
  - Neon hết hạn mức thì dùng sub Claude Sonnet medium.
  - **Việc dữ liệu chỉ giao sub Sonnet.**
  - Chạy nền bằng `run_in_background`, **không** dùng `&` (dùng `&` thì không nhận được thông báo khi xong).
- **Bảo mật** (`CLAUDE.md` mục 6a): brief nào cũng có tiêu chí bảo mật chạy được bằng lệnh. Agent không tự cài gói. MCP Supabase chỉ đọc. Quy tắc 3 lượt: 3 lượt sửa không tiến thì dừng, báo chủ kho.
- **Không commit / push** nếu chủ kho chưa bảo ngay trong lượt đó.
- **Không đụng** `pharm-overlay/` (đã gác) và `gia lap/`.

---

## CẬP NHẬT 19/11/2026 tối – D4 + D5 đã giao (đọc trước khối 15:00)

- Claude đã kiểm dữ liệu D4/D5: **103/103 trích nguyên văn khớp tệp nhãn**; 6/17 quy tắc thận chồng khoảng CrCl ở ranh giới → sửa bằng trường mới `bao_gom_can_tren`.
- Đã giao, chạy song song (người dùng chốt: Codex hết quota, code giao agy Hydrogen **high**, lượt sửa nâng **xhigh**):
  - **T65-T66-ht** (sub Sonnet, dữ liệu): `plan/briefs/T65-T66-hoan-thien-du-lieu.md`. Xong khi có `plan/reports/T65.md`, `T66.md`, `docs/du-lieu/lieu-than-gan-xet-nghiem.md`, `lieu-duong-dung.md`.
  - **T67** (agy high, luật D4): `plan/briefs/T67-luat-d4-than-gan-xet-nghiem-benh.md`, log `plan/reports/T67.agy.log`, báo cáo `plan/reports/T67.md`.
  - **T68** (agy high, luật D5): `plan/briefs/T68-luat-d5-duong-dung-lieu-toi-da.md`, log `plan/reports/T68.agy.log`, báo cáo `plan/reports/T68.md`.
- **T67, T68 không sửa `engine.py` / `registry.py`.** Sau khi review đạt cả hai, viết brief **T69**: nối 5 luật mới vào engine + registry (chỉ chạy khi có resolver, như luật tương tác), truyền resolver cho `renal_dose.check`, chuyển `antibiotic.py` sang yếu tố 6 (sửa `tests/rules/test_registry.py`, `test_antibiotic.py`, `tests/domain/test_demo_cases.py`), test API 3 tình huống plan (levofloxacin uống kê tiêm, HS-019 paracetamol 6 g, HS-026 bỏ cân nặng), sửa 4 tệp lệch `ruff format`.
- Review: chạy kiểm phủ khoảng CrCl (script mẫu đã dùng ở scratchpad phiên này: thử 0 → 150 bước 0,5, mỗi điểm đúng một mức).

## CẬP NHẬT 19/11/2026 15:00 – ĐỌC PHẦN NÀY TRƯỚC (người dùng chuyển tài khoản Claude vì sắp hết hạn mức)

Các khối "CẬP NHẬT" bên dưới là lịch sử; phần agent và nhúng trong đó **đã lỗi thời**. Thứ tự đọc:
1. Khối này.
2. `CLAUDE.md`, `AGENTS.md` (quy tắc 9: tài liệu dữ liệu ở `docs/du-lieu/`).
3. `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md` mục 5.0.
4. `plan/TRACKING.md` (bảng T50 → T66, nhật ký cuối tệp).

### 1. Bối cảnh

- Demo 20/11 chỉ gửi link sản phẩm; bản đang chạy dùng dữ liệu cũ. Không còn mốc đóng băng.
- Đang làm **plan 1.8**: dữ liệu thật cho 7 yếu tố thẩm định.
- **Đã xong và đã push** (nhánh `vukhai248`, commit `846086b`):
  - **D0**: từ điển và bộ phân giải.
  - **D1**: tương tác DDInter và ma trận.
  - **D2**: trùng nhóm ATC (T57).
  - **D3**: dị ứng chéo (dữ liệu T60, luật T63).
  - **Nhúng `gemini-embedding-2`**: T61 code, T62 nhúng 3.730 đoạn.
  - **CI GitHub Actions** (T58).
  - **Tài liệu dữ liệu `docs/du-lieu/`** (T59).
- CI lượt cuối **xanh**: web 293 qua; backend Ubuntu và Windows 1.252 qua / 109 bỏ qua / 0 trượt.
- Máy người dùng: pytest **1.359 qua / 2 bỏ qua / 0 trượt**.

### 2. Quy tắc người dùng chốt (bắt buộc)

- **Claude không viết code.** Claude chỉ:
  - viết brief, giao agent;
  - review: chạy `uv run ruff check .` và `uv run pytest -q -p no:cacheprovider`, rồi **kiểm độc lập qua API thật** bằng TestClient, `AUTH_MODE=off`, `CASE_SOURCE=file`, ca lấy từ `load_source_cases`;
  - ghi `plan/TRACKING.md`.
- **Việc dữ liệu** (cào, xử lý, dựng bảng, nạp, nhúng, đánh giá) **chỉ giao sub Claude Sonnet.** Codex và agy **chỉ viết code**.
- **Agent code:**
  - Codex `gpt-6.1-sol` xhigh **hết quota tới 24/11/2026 9:41**.
  - Hiện dùng agy, chạy nền, không dùng `&`:
    ```
    agy --model gemini-4-hydrogen-xhigh --mode accept-edits --print-timeout 1800s -p "Đọc AGENTS.md và plan/briefs/Txx.md rồi thực hiện đúng brief đó. KHÔNG gọi shell, không gọi mạng; chỉ đọc và ghi tệp."
    ```
  - agy không chạy được test, nên **Claude luôn tự chạy pytest**.
  - Lỗi agy hay mắc trong test: đoán sai dữ liệu (tên mã nhóm), nạp thẳng `HS-*.json` thay vì qua `app.db.reader.load_source_cases(ROOT)`, đếm cả tệp `_kich_ban.json`.
- **Brief phải liệt kê đủ tệp.**
  - Luật mới phải nối cả `app/rules/engine.py` lẫn `registry.py` (T55, T57 từng thiếu).
  - Hai task code cùng sửa `engine.py` / `registry.py` thì chạy **lần lượt**.
- **Tài liệu dữ liệu:**
  - Đọc `docs/du-lieu/*.md` trước, không mở dữ liệu dò lại.
  - Tải hay xử lý dữ liệu thì cập nhật tệp đó.
  - **Không** chạy `du` / `find` trong `data/kb_sources/ddinter_web`: hàng chục nghìn tệp, treo lệnh.
- **Git:**
  - `data/` không còn trên git, trừ `data/mock`, `data/gold`, `data/kb` và các `README.md`.
  - Commit / push **chỉ khi người dùng bảo ngay trong lượt đó**; hệ thống sẽ chặn nếu không có lời bảo.
  - Trước khi commit, quét khoá: `AIza…`, `sk-…`, `postgres://user:pass@`.
- **Quy tắc 3 lần:** sửa 3 lượt liên tiếp không cải thiện thì dừng, đánh dấu ⏸️.
- **Tự chuyển đợt:** đợt D qua review thì tự sang đợt kế. Vẫn hỏi trước khi commit / push, ghi DB, xoá dữ liệu.
- **Công thức** (Child-Pugh, QTc, liều theo BSA…):
  - nguồn **chỉ lấy theo MDCalc**;
  - **chờ người dùng gửi**;
  - không giao agent tự cài.
- Khoá chỉ nằm trong `.env`: không in, không ghi vào brief hay log.

### 3. Việc dở lúc bàn giao: dữ liệu D4 (T65) và D5 (T66)

Người dùng **đã dừng hai sub Sonnet lúc khoảng 14:50.**
- Brief: `plan/briefs/T65-du-lieu-d4-than-gan-xet-nghiem.md`, `plan/briefs/T66-du-lieu-d5-lieu-duong-dung.md`.
- Chưa có báo cáo `plan/reports/T65.md` / `T66.md`.
- Chưa có tài liệu `docs/du-lieu/lieu-than-gan-xet-nghiem.md` / `lieu-duong-dung.md`.
- Chưa có tệp `data/kb_reports/T65_*` / `T66_*`.
- **Chưa commit.**

Trạng thái tệp, do Claude kiểm lúc 14:55. Mọi tệp đọc được bằng `json.load`; mọi khoá hoạt chất đều có trên trục `tra_cuu.sqlite`; mọi dòng `trang_thai: cho_duoc_si_duyet`.

| Tệp (`data/kb/`) | Task | Đã có | Còn thiếu |
|:--|:--|:--|:--|
| `quy_tac_lieu_than.json` | T65 | Giữ nguyên `quy_tac` (meropenem đã duyệt, luật `renal_dose.py` đang dùng). **Thêm khoá mới `quy_tac_cho_duyet`: 17 quy tắc**: acetaminophen, cefepime, ciprofloxacin, clarithromycin, colistimethate, enalapril, enoxaparin, fluconazole, gabapentin, levetiracetam, levofloxacin, methotrexate, piperacillin/tazobactam, rivaroxaban, simvastatin, sulfamethoxazole/trimethoprim, tramadol. 24 trích nguyên văn kèm URL | **Chưa kiểm** trích là chuỗi con nguyên văn của nhãn. **Chưa kiểm** khoảng CrCl phủ kín, không chồng. Thiếu danh sách "không có ngưỡng". Luật chưa đọc `quy_tac_cho_duyet`, nên app chưa đổi hành vi. Test `tests/rules` + `tests/api` vẫn 247 qua |
| `quy_tac_gan.json` | T65 | 24 dòng, 22 hoạt chất, 24 trích + URL | Kiểm trích nguyên văn |
| `nguong_xet_nghiem.json` | T65 | 15 dòng, 10 hoạt chất, 15 trích + URL | Kiểm trích; đối chiếu đơn vị với xét nghiệm trong ca |
| `thuoc_benh_icd.json` | T65 | 119 tên bệnh DDInter → ICD-10, 40/48 hoạt chất ca, 2 tên chưa ánh xạ; 10 cặp hoạt chất–bệnh khớp `chan_doan` ở 9 ca | Không có trích (ánh xạ tay, chờ dược sĩ duyệt). Kiểm vài ánh xạ ICD bằng tay |
| `duong_dung_hop_le.json` | T66 | Bảng chuẩn hoá tên đường dùng + 62 dòng theo hoạt chất và dạng bào chế, 37 hoạt chất, 37 URL | Kiểm tình huống levofloxacin uống kê tiêm; ghi nguồn (Cục Quản lý Dược / NDC) cho từng dòng |
| `lieu_toi_da.json` | T66 | 40 dòng, 37 hoạt chất, 40 trích + URL | Kiểm trích; kiểm paracetamol 4 g/ngày; gentamicin theo kg; danh sách "nhãn không ghi tối đa" |

**Phiên mới làm như sau:**
1. Giao **sub Sonnet** (không giao Hydrogen, vì đây là việc dữ liệu), hai task chạy song song.
   - Prompt mẫu: "Tiếp tục T65 (hoặc T66) theo brief. Lượt trước bị dừng; các tệp `data/kb/...` đã có, xem bảng trong `plan/HANDOFF.md` mục 3: đọc, kiểm, hoàn thiện, **không làm lại từ đầu**. Làm nốt phần còn thiếu, viết `docs/du-lieu/...md` và `plan/reports/T6x.md`."
2. **Claude review dữ liệu:**
   - Kiểm trích nguyên văn: mở tệp nhãn trong `data/kb_sources/openfda*` theo `set_id`.
   - Khoảng CrCl phủ kín, không chồng, không hở.
   - Không có số "bịa".
   - Ba tình huống plan: levofloxacin, paracetamol 1 g × 6, gentamicin thiếu cân nặng.
   - Chạy pytest toàn kho.
3. Viết **brief code cho Hydrogen**, **D4 trước, D5 sau** (cùng sửa `engine.py` / `registry.py`).
   - **D4:** `renal_dose.py` đọc thêm `quy_tac_cho_duyet` (vẫn ghi "chờ dược sĩ duyệt" trong căn cứ); luật gan theo câu nhãn (**không** cài Child-Pugh); luật ngưỡng xét nghiệm; thuốc–bệnh theo ICD của `chan_doan`. Thiếu dữ liệu ca thì `khong_du_du_lieu`.
   - **D5:** luật đường dùng; luật liều tối đa (liều × số lần; theo kg cần cân nặng, thiếu thì `khong_du_du_lieu`); chuyển `antibiotic.py` sang yếu tố 6.
   - **Kiểm chỉ định** (RAG + LLM): không làm ở 1.8, đã dời sang plan 1.9 mục 14.

### 4. Việc khác còn mở

- **AWS:**
  - RDS `vinmec-pharm-db` (PostgreSQL 18.6, pgvector 0.8.2, `db.t4g.micro`, không công khai, `ap-southeast-1`) đã tạo.
  - Mật khẩu nằm trong Secrets Manager.
  - Mở đường hầm (thêm `C:\Program Files\Amazon\SessionManagerPlugin\bin` vào PATH):
    ```
    aws ssm start-session --target i-050630fbca49cc994 --document-name AWS-StartPortForwardingSessionToRemoteHost --parameters '{"host":["vinmec-pharm-db.c3c2kos8cqpm.ap-southeast-1.rds.amazonaws.com"],"portNumber":["5432"],"localPortNumber":["5433"]}'
    ```
  - Lược đồ đã chạy thử trong giao dịch rồi hoàn tác. Cần sửa:
    - hai câu `REVOKE … anon, authenticated`;
    - BOM của `db/tu_dien.sql`;
    - thiếu bảng đích cho hậu quả / xử trí DDInter, thức ăn, `chuyen_ma_ca`, dị ứng chéo, các bảng D4 / D5.
  - **Chỉ nạp DB sau khi xong mọi đợt D và đạt** (người dùng chốt). Auth giữ ở Supabase.
- **RAG / rerank:** dời sang plan 1.9 mục 14.
  - Đo 50 câu (T64): chỉ vector tốt hơn đường lai đang chạy, vì BM25 làm hại câu Việt.
  - Đề xuất: vector + lọc hoạt chất, không BM25, không rerank.
  - Bộ câu hỏi: `data/kb_reports/T64_bo_cau_hoi.json`.
- **Khoá OpenRouter:**
  - Người dùng muốn đặt tên `OPENROUTER_API_KEY_1` → `_4` và tự chuyển khoá khi hết hạn mức.
  - Lúc 14:00, `.env` có `_2`, `_3` (hai lần), `_4`, chưa có `_1` hay tên không số.
  - Code chỉ đọc `OPENROUTER_API_KEY` và `_2`. Sửa trong lượt code RAG.
- **Nhỏ:**
  - 4 tệp lệch `ruff format` (CI không kiểm): gom vào brief code kế tiếp.
  - Workflow dùng tham số sai `python-version-file` cho `setup-uv`: chỉ cảnh báo, không lỗi.
- **Chờ dược sĩ duyệt:** bảng nhóm điều trị D2, bảng dị ứng chéo D3, các bảng D4 / D5.
- **Chờ người dùng:**
  - công thức MDCalc;
  - QĐ 5948 bản gốc;
  - quyết định quản lý dữ liệu (đề xuất DVC + S3);
  - khoá Jev (typesafe) nếu muốn thử làm bộ chấm rerank.
- **D6** (độc tính), **D7** (lịch dùng): chưa bắt đầu; làm sau D4, D5.

---

## CẬP NHẬT 19/11/2026 (rạng sáng) – ĐỌC PHẦN NÀY TRƯỚC

Đang làm **plan 1.8** (`plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md`): dữ liệu thật cho thẩm định 7 yếu tố. Tiến độ từng bước nằm ở **mục 5.0** của plan; tiến độ nguồn nằm ở cột "Tiến độ (19/11)" của mục 3.1.

**Quyền người dùng giao (19/11, khi đi ngủ):**
- Khi **D0 và D1 xong hết** các bước làm được, Claude làm **một vòng review tổng** (plan 1.8 mục 5.0.1). Đạt thì **tự sang D2, D3… không cần hỏi**. Mỗi đợt vẫn qua cổng review mục 6.
- Vẫn phải hỏi trước: commit / push, ghi Supabase, xoá dữ liệu, việc ngoài plan.
- **Nhúng tạm gác (19/11 đêm):** không chạy nhúng thật (T52 ứng viên ngữ nghĩa, hiệu chuẩn, nhúng nốt RAG) cho tới khi người dùng nạp credit OpenRouter hoặc đổi nhà cung cấp nhúng. Việc nào phụ thuộc nhúng thì đánh dấu ⏸️ và làm việc khác; không để nhúng chặn luật / bảng tương tác (các phần này không dùng nhúng).
- **Quy tắc 3 lần** (từ 19/11, lượt trước không tính): việc giao / sửa 3 lượt liên tiếp không cải thiện chỉ số mục tiêu thì dừng, đánh dấu ⏸️ ở plan 1.8 mục 5.0 và TRACKING, chuyển việc khác.

**Chọn agent** (người dùng chốt 19/11):
- Không cần mạng: Codex `gpt-6.1-sol` xhigh (6.2 chỉ dự phòng).
- Cần mạng: sub Claude Sonnet medium/high (Codex `-s workspace-write` bị chặn mạng).
- Hết quota: `agy` `gemini-4-hydrogen-high/xhigh`.

**Đang chạy lúc ghi:**
- T52-fix-1 (Codex 6.2): lỗi lùi độ phủ do dạng muối.
- T54 (sub Sonnet): tải TT20 / 15-VBHN / TT37, QĐ 5631, QĐ 5948, LiverTox, LactMed.
- T55 (Codex 6.1): bảng tương tác + luật yếu tố 4 + ma trận, theo hợp đồng `plan/api-hop-dong-v1.6-ma-tran-tuong-tac.md`.

**Việc còn của D0 / D1 sau khi các task trên xong:**
- Chạy nhúng thật và hiệu chuẩn (T52).
- D0.7: nối nhãn openFDA ↔ trục.
- D0.8: lệnh ma trận độ phủ đa nguồn.
- Sửa `app/kb/dictionary/publish.py` đọc biến môi trường ngoài config (test kiến trúc trượt).
- Chạy lại `python -m app.kb.resolver build-index` sau T52.
- D1.2 phần một bên (~25k trang, sub Sonnet chạy nền).
- Vòng review tổng.

---

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
