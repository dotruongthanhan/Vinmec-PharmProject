# Plan 1.11 – Tracer (nhật ký lượt chạy AI) và minh hoạ tương tác trong khung chat

Bản 2, ngày 26/11/2026. Viết lại sau góp ý của chủ kho cùng ngày (mục 0.1). Đọc kèm:
- `CLAUDE.md` mục 6, 6a;
- plan 1.4 (hệ thống thiết kế), plan 1.5 (bảo mật), plan 1.9 (agent, Gateway, kiểm chứng), plan 1.10 (tiến trình bước);
- `api-hop-dong-v1.2-hoi-dap.md`.

## 0. Một đoạn

**Phần A – tracer.** Mỗi lượt AI chạy sinh một vết `ma_vet`, gồm cây các bước:
- node đồ thị;
- LLM (token, độ trễ);
- tool (tham số đã che, căn cứ, lỗi);
- kiểm chứng.

Vết mặc định chỉ có siêu dữ liệu, lưu trong viện **30 ngày**, chỉ quản trị viên (và dev) xem được.

**Phần B – minh hoạ.** Agent có tool riêng `ve_bieu_do`. LLM **tự quyết** khi nào cần hình, và tự chọn kiểu hình (cột, đường, tròn, ma trận nhiệt, dòng thời gian…), trục, bộ lọc, thanh điều khiển, chú thích. Có hai nguồn đầu vào:
- câu hỏi lâm sàng theo ca: thang liều thận, tổng liều 24 giờ, diễn tiến xét nghiệm, ma trận tương tác…;
- câu hỏi thống kê nhiều ca: "tháng này bao nhiêu y lệnh bị bỏ sót", "luật nào hay bị bác bỏ"…

Hình hiện trong một **khung tương tác** giống ví dụ chủ kho gửi: biểu đồ, thanh điều khiển, nút xem bảng và mở rộng. Ràng buộc giữ nguyên: **mọi con số do code lấy từ tool có căn cứ**. LLM thiết kế hình nhưng không tự đưa số vào và không viết code.

**Phần C – bảng trong chat.** Hiển thị bảng Markdown thành bảng thật, kèm nút mở rộng toàn màn. Phần này đã giao ngay (brief `UI1`).

### 0.1. Chủ kho chốt ngày 26/11
1. Minh hoạ dùng **tool riêng**, LLM tự quyết khi nào cần. (Bỏ phương án B1 "trường đầu ra" của bản 1.)
2. Danh mục cố định V1–V3 **chưa đủ**. Dược sĩ còn hỏi số liệu tổng hợp ("trong tháng này bao nhiêu đơn bị bỏ sót…"), nên cần biểu đồ cột, đường, tròn… **không cố định**, do AI tự dựng, hiện trong khung tương tác giống ví dụ.
3. **Ma trận tương tác** phải có: thừa hơn thiếu, phòng khi dược sĩ hỏi mà hệ thống không làm được.
4. Vết lưu khoảng **1 tháng**; chỉ **admin** (hoặc dev) được xem, ít nhất ở giai đoạn này.
5. Thêm tính năng **mở rộng bảng toàn màn** trong khung chat của dược sĩ.

## 1. Vì sao

**Tracer:**
1. **Pháp lý.** Luật Trí tuệ nhân tạo 134/2025/QH15 (hiệu lực 01/3/2026) xếp y tế vào nhóm rủi ro cao, phải lưu hồ sơ kỹ thuật và nhật ký. Hướng "chạy bóng" (brainstorm 23/11) cũng cần vết.
2. **Gỡ lỗi và đánh giá.** Hiện chưa xem được agent đã gọi tool gì, tham số gì, bộ kiểm chứng chặn số nào. Lượt chấm 26/11 phải đoán nguyên nhân `HD-CA-045`.
3. **Chi phí.** `DeepSeekLLM.last_usage` có ghi token nhưng không ai đọc; độ trễ từng lần gọi LLM không được đo.

**Minh hoạ:**
1. **Mentor 23/11:** sản phẩm phải chính xác và làm được điều dược sĩ không tự làm nhanh. Bảng liều 4 mức CrCl có điểm của người bệnh, hay tổng paracetamol gộp từ 3 biệt dược, nhìn hình thì thấy ngay, đọc chữ thì dễ sót.
2. **Khảo sát** (`docs/note_by_khai/Bao-cao-tuan-1-template.md` mục B4, B5): dược sĩ đối chiếu liều theo chức năng gan thận, kiểm thiếu liều hoặc lệch liều theo giờ, theo dõi xét nghiệm, rà phiếu hội chẩn kháng sinh. Họ còn làm **chỉ số tháng** từ tệp Excel xuất ra từ OH (mục B5, B6). Đây chính là nhu cầu thống kê chủ kho nêu.

## 2. Hiện trạng (Claude khảo sát mã 26/11)
| Hạng mục | Hiện có | Thiếu |
| :--- | :--- | :--- |
| Log | `logging` ra stdout. Logger `app.agent.audit` ghi mỗi lần gọi tool (không tham số, không nội dung). Nhật ký truy cập ghi JSONL theo ngày, giữ 90 ngày | Không có mã nối các dòng của một lượt; không có vết lâu dài |
| Tiến trình | `app/core/progress.py`: các bước chỉ nằm trong RAM, xoá sau 60 giây | Không lưu |
| LLM | `last_usage` có ghi token | Không ai đọc; không đo độ trễ |
| LangSmith | Tắt chủ động (T49) | – |
| DB | `y_lenh` (thời điểm kê, khoa, trạng thái), `ket_qua_tham_dinh`, `ket_qua_nhan_dinh` (yếu tố, kết luận, mức độ, luật), `phan_hoi` (đồng ý / bác bỏ / cần sửa), `sinh_hieu`, `ket_qua_xet_nghiem`, `khang_sinh_do`, `lich_dung` | Không có bảng vết; không có lớp thống kê |
| Chat web | `ClinicalMarkdown` tự viết (JSX thuần). **Không có bảng**: bảng Markdown hiện thành chữ có dấu `\|` | Không có khối hình; không mở rộng được |
| Biểu đồ web | `LabTrendChart.tsx` vẽ SVG tay. **Không có thư viện biểu đồ** | Chưa có bảng màu chuỗi dữ liệu |
| CSP | `script-src 'self'`, `object-src 'none'`, `frame-ancestors 'none'` | – |

---

# PHẦN A – TRACER

## A.1. Mục tiêu, không làm, phản mục tiêu

**Mục tiêu:**
1. Mỗi lượt AI (hỏi đáp, rà AI, eval) có một `ma_vet` (UUID v4). `TraLoi` trả kèm `ma_vet`; bảng phản hồi và dòng `chi_tiet.jsonl` của eval cũng lưu `ma_vet`.
2. Vết là cây span theo khái niệm OpenTelemetry (`trace_id`, `span_id`, `parent_id`), để sau này xuất sang OTel không phải đổi mô hình.
3. **Span LLM:** mô hình, phiên bản prompt, token vào/ra, độ trễ, số lần thử lại, lý do kết thúc, số ký tự prompt và băm prompt.
4. **Span tool:** tên, tham số **đã che PII** cùng băm tham số gốc, trạng thái, mã lỗi, kích thước kết quả, cờ bị cắt 8.000 ký tự, mã căn cứ, thời gian. Riêng `ve_bieu_do` thêm kiểu hình, số điểm, lý do bị bỏ nếu có.
5. **Span kiểm chứng:** số câu bị chặn, mã lý do (`so_khong_co_nguon:…`), trích dẫn bị loại. Thêm sự kiện bảo mật: phát hiện chèn lệnh, PII trong tham số.
6. **Tổng hợp theo lượt:** trạng thái cuối, thời gian, token, chi phí ước tính, số tool, số lần bị chặn.
7. **Trang quản trị:** danh sách vết có lọc; thác nước thời gian; bảng tổng hợp vẽ bằng chính bộ hình của phần B.
8. **Ghi không chặn lượt chạy:** dùng hàng đợi có trần; đầy thì bỏ vết và tăng bộ đếm, không làm chậm câu trả lời.

**Không làm:**
- dịch vụ SaaS ngoài (LangSmith, Langfuse cloud);
- gói OpenTelemetry (gói mới phải kiểm theo mục 6a; để sau);
- chạy bóng trên dữ liệu thật.

**Phản mục tiêu:** vết chứa PII hoặc khoá API; tracer làm tăng độ trễ p95 quá 20 ms; dược sĩ xem được vết; vết rời khỏi viện.

## A.2. Phương án (chọn A1)
| | **A1. Tracer tự viết, không thêm gói** | A2. OpenTelemetry SDK + Jaeger tự host | A3. Langfuse tự host |
| :--- | :--- | :--- | :--- |
| Gói mới | 0 | nhiều gói `opentelemetry-*` | thêm dịch vụ và CSDL riêng |
| Kiểm soát PII | toàn quyền | phải tự lọc trong span processor | dữ liệu nằm ngoài `nghiep_vu` |
| Giao diện xem | tự làm (TR3) | có sẵn | có sẵn |

Lý do chọn A1:
- Đã có sẵn `ghi_buoc`, `_audit` và `access_log` để móc vào.
- Quy tắc cấm agent tự cài gói khiến A2, A3 chậm.
- Dữ liệu y tế nên ở trong lược đồ của mình.

Mô hình span giữ tương thích OTel, nên sau này đổi sang A2 vẫn được.

## A.3. Mô hình dữ liệu

**Vết** – bảng `nghiep_vu.vet_chay`:

| Trường | Ghi chú |
| :--- | :--- |
| `ma_vet` | UUID v4 |
| `bat_dau`, `ket_thuc`, `thoi_gian_ms` | |
| `loai` | `hoi_dap` \| `ai_review` \| `danh_gia` |
| `engine` | `co_dinh` \| `agentic` |
| `nguoi_dung_id`, `vai_tro`, `phien_id` | |
| `ca_bam` | HMAC của mã ca, khoá nằm trong `.env` |
| `phien_ban` | JSON: prompt, `tool_policy`, mô hình, nguồn KB, commit |
| `trang_thai_cuoi` | |
| `tong_token_vao`, `tong_token_ra`, `chi_phi_uoc_tinh` | |
| `so_tool`, `so_bi_chan` | |
| `ma_loi`, `muc_noi_dung` | |

**Span** – bảng `nghiep_vu.vet_buoc`:

| Trường | Ghi chú |
| :--- | :--- |
| `ma_vet`, `ma_buoc`, `ma_buoc_cha` | |
| `loai` | `node` \| `llm` \| `tool` \| `kiem_chung` \| `che_pii` \| `chan_dau_vao` \| `su_kien_bao_mat` |
| `ten` | |
| `bat_dau`, `thoi_gian_ms`, `trang_thai` | |
| `thuoc_tinh` | JSONB, chỉ chứa khoá trong danh sách cho phép của từng loại span; tối đa 4 KB |
| `noi_dung` | chỉ có khi mức nội dung cho phép (A.4) |

Mỗi vết tối đa 200 span và 256 KB; vượt thì gắn cờ `vet_bi_cat`.

## A.4. Mức nội dung (`tracer.muc_noi_dung`)
| Mức | Ghi gì | Dùng khi |
| :--- | :--- | :--- |
| `sieu_du_lieu` (**mặc định**) | Không có văn bản; chỉ số đếm, thời gian, mã, băm | Mọi môi trường có thể có dữ liệu thật (plan gốc dòng 408) |
| `noi_dung_da_che` | Thêm prompt, câu trả lời, tham số tool đã che PII, mỗi trường tối đa 2.000 ký tự | Dev, demo, eval trên dữ liệu 100% giả lập |
| `day_du` | Như trên, không cắt | Chỉ chạy cục bộ. App từ chối khởi động nếu đặt mức này khi `APP_ENV=production` |

## A.5. Ghi, lưu và thời hạn
- **Module `app/tracing/`:**
  - ContextVar giữ vết hiện tại, giống `tien_trinh_hien_tai`;
  - span dùng dạng `with span(loai, ten) as s:`;
  - lớp bọc `LLMClient` để đo độ trễ và đọc `last_usage`.
- **Điểm móc:** `ghi_buoc` (node), `ToolGateway.goi` (ngay sau bước che PII), nút kiểm chứng, `ChanDauVao`.
- **Đích ghi:**
  1. tệp JSONL theo ngày `data/runtime/vet/vet-YYYY-MM-DD.jsonl`;
  2. Postgres, ghi lô bất đồng bộ.

  Đích lỗi thì cảnh báo và đếm, không làm hỏng lượt chạy.
- **Thời hạn lưu (chủ kho chốt 26/11):** **30 ngày** (cấu hình `tracer.so_ngay_luu`, mặc định 30). Job dọn hằng ngày xoá cả tệp JSONL lẫn bản ghi DB quá hạn. Tệp JSONL tối đa 200 MB mỗi ngày.
- `ma_vet` đi kèm header `X-Ma-Vet` và trường `TraLoi.ma_vet`. Phản hồi của dược sĩ lưu kèm `ma_vet`.

## A.6. Ai được xem (chủ kho chốt 26/11: admin hoặc dev)
- **API**, chỉ vai trò `admin`:
  - `GET /api/quan-tri/vet` (lọc, phân trang tối đa 50);
  - `GET /api/quan-tri/vet/{ma_vet}`;
  - `GET /api/quan-tri/vet/tong-hop`.

  `duoc_si_ls` gọi thì nhận 403; mã vết không tồn tại thì 404.
- **"Dev"** = tài khoản `admin` trên môi trường dev, hoặc đọc trực tiếp tệp JSONL trên máy dev. **Không tạo vai trò mới** ở đợt này.
- **Web `/app/quan-tri/vet`:**
  - danh sách vết;
  - thác nước span;
  - nút sao chép mã vết;
  - bảng tổng hợp: p50/p90 độ trễ theo engine, token và chi phí theo ngày, tỉ lệ lỗi tool, tỉ lệ bị chặn và 10 lý do hàng đầu.
- Mỗi lần xem vết ghi vào nhật ký truy cập.

## A.7. Bảo mật (bắt buộc)
- Tracer chỉ nhận chuỗi **sau** khi Gateway đã che PII.
- Test canary:
  - họ tên, HN, số điện thoại, CCCD giả đặt trong câu hỏi và trong tham số tool, rồi quét JSONL và DB: phải bằng 0;
  - khoá `sk-…` giả: phải bằng 0.
- Mọi chuỗi ghi qua `json.dumps`, chống giả mạo dòng log.
- Giới hạn span và dung lượng ở A.3, A.5.
- LangSmith giữ tắt; có test khẳng định `tracing_context(enabled=False)` còn nguyên.
- Không có API xoá vết.

## A.8. Nghiệm thu
- `pytest tests/tracing`:
  - cây span đúng cho một lượt agent giả lập;
  - token lấy đúng;
  - hàng đợi đầy vẫn không chặn lượt chạy;
  - mức `day_du` ở production thì từ chối khởi động;
  - canary bằng 0;
  - 403/404 đúng;
  - dọn vết quá 30 ngày (đồng hồ giả).
- **Hiệu năng:** 50 lượt agent, chênh lệch p95 khi bật tracer < 20 ms.
- **Eval:** `chi_tiet.jsonl` có `ma_vet`; mở vết `HD-CA-045` thấy được lý do chặn và span LLM tương ứng.

## A.9. Còn hỏi
Bản demo (dữ liệu giả lập) có đặt `noi_dung_da_che` để xem được nội dung khi gỡ lỗi không?

---

# PHẦN B – MINH HOẠ TƯƠNG TÁC DO AI DỰNG

## B.1. "AI tự làm ra hình" nghĩa là gì: hai cách và cách chọn
| | **C1. AI viết đặc tả hình (đề xuất)** | C2. AI viết code HTML/JS, chạy trong khung cách ly (kiểu ChatGPT/Claude artifact) |
| :--- | :--- | :--- |
| AI tự quyết | Kiểu hình (cột, đường, tròn, nhiệt, dòng thời gian…), cột nào lên trục nào, tô màu theo gì, bộ lọc, thanh điều khiển, đường ngưỡng, tiêu đề, chú thích | Mọi thứ, kể cả cách tính và cách vẽ |
| Con số trên hình | **Do code chép từ bộ dữ liệu của tool**; LLM chỉ trỏ tới tên cột | LLM tự viết số hoặc tự tính trong JS; **không kiểm chứng được** |
| Bảo mật | Không chạy code lạ; React tự escape; CSP giữ nguyên | Phải mở `iframe` sandbox, đổi CSP, lo thoát sandbox, rò dữ liệu qua mạng |
| Phù hợp nguyên tắc dự án ("LLM không bao giờ tự tính", "mọi nhận định qua kiểm chứng") | Có | **Không** |

Chọn **C1**. Với dược sĩ, trải nghiệm vẫn là "AI tự dựng hình theo câu hỏi": mỗi câu một hình khác, không có danh mục cố định. Nhưng hình đúng tới từng con số, và bấm "Xem dạng bảng" là đối chiếu được.

## B.2. Kiến trúc

```
câu hỏi ──► TacTu (LLM)
              │ 1) gọi tool lấy dữ liệu: tinh_chi_so / tra_thuoc / tra_tuong_tac / lay_du_lieu_ca / thong_ke …
              │    → mỗi tool trả thêm "bộ dữ liệu" ds-n (cột có kiểu + đơn vị, dòng, mã căn cứ)
              │ 2) gọi ve_bieu_do(dac_ta) – qua Gateway
              │    → Gateway kiểm đặc tả, bộ dựng (code) chép số từ ds-n → KhoiMinhHoa mh-n
              │    → trả LLM xác nhận ngắn "mh-1: cột, 12 nhóm, 3 điều khiển"
              │ 3) viết câu trả lời có nhắc mh-1, số trong lời vẫn qua kiểm chứng
              ▼
TraLoi { noi_dung, trich_dan, minh_hoa: [KhoiMinhHoa…], ma_vet }
              ▼
Web: KhungMinhHoa (giống ảnh mẫu) – vẽ bằng bộ component, điều khiển chạy phía máy khách trên dữ liệu đã gửi
```

**Bộ dữ liệu (`BoDuLieu`):**
- mỗi tool lấy dữ liệu trả thêm `bo_du_lieu: [{ma: "ds-1", cot: [{ten, kieu: so|chu|thoi_gian|muc, don_vi}], dong: [...], can_cu: {...}}]`;
- tối đa 2.000 dòng × 20 cột mỗi bộ;
- giữ trong trạng thái lượt chạy, **không** đưa toàn bộ vào prompt: LLM chỉ thấy tên cột, số dòng và 5 dòng mẫu.

**Tool `ve_bieu_do` (qua Gateway):**
- Tham số là đặc tả:

  | Trường | Nội dung |
  | :--- | :--- |
  | `kieu` | `cot` \| `cot_chong` \| `cot_ngang` \| `duong` \| `vung` \| `tron` \| `vanh` \| `phan_tan` \| `nhiet` (ma trận) \| `dong_thoi_gian` (Gantt) \| `thang_nguong` (dải mức) \| `bang` |
  | `bo_du_lieu` | mã `ds-n` |
  | `truc` | `{x, y, mau, kich_thuoc}`, mỗi trục là tên cột |
  | `gop` | `tong` \| `dem` \| `trung_binh` \| `trung_vi`; **code** gộp khi cần |
  | `chu_thich_duong` | đường ngưỡng, vùng, mốc; giá trị phải trỏ tới **ô dữ liệu**, không nhận số tự do |
  | `dieu_khien` | tối đa 6, mô tả ở B.5 |
  | `tieu_de`, `phu_de`, `chu_thich` | văn bản, mỗi trường ≤ 300 ký tự |

- Gateway bỏ đặc tả (và ghi lý do vào vết) khi:
  - `ds-n` không thuộc lượt này;
  - cột không tồn tại hoặc sai kiểu (ví dụ hình tròn với cột âm);
  - có số tự do ở chỗ phải là ô dữ liệu;
  - quá 3 hình mỗi câu trả lời, quá 2.000 điểm, hoặc khối kết quả quá 64 KB.
- Ngân sách: `ve_bieu_do` tính vào trần tool của lượt.

**Kỹ năng (skill), tệp `config/prompts/ky_nang_minh_hoa.v1.md`:** hướng dẫn LLM:
- **Khi nào nên vẽ:** so sánh nhiều nhóm, xu hướng theo thời gian, vị trí so với ngưỡng, nhiều cặp tương tác, câu hỏi thống kê.
- **Khi nào không vẽ:** câu hỏi một con số, thiếu dữ liệu, hỏi định nghĩa.
- **Chọn kiểu hình:**
  - thời gian → đường;
  - so sánh nhóm → cột;
  - tỉ trọng ≤ 6 phần → tròn hoặc vành; nhiều hơn → cột;
  - cặp × cặp → nhiệt;
  - ngưỡng liều → thang ngưỡng;
  - lịch dùng → dòng thời gian.
- **Không vẽ thay lời:** câu trả lời bằng chữ phải tự đứng được.
- **Chú thích** không chứa số ngoài bộ dữ liệu.

## B.3. Danh mục gợi ý (không cố định; LLM được dựng hình khác nếu dữ liệu cho phép)

**Nhóm 1 – lâm sàng theo ca:**

| # | Hình | Dược sĩ hỏi | Tương tác | Dữ liệu |
| :--- | :--- | :--- | :--- | :--- |
| V1 | **Thang liều theo chức năng thận** (và gan khi có Child-Pugh): các mức CrCl theo bảng nhãn, điểm của người bệnh, khoảng chênh khi đổi cách tính cân nặng | "Meropenem cho CrCl này mức nào, có sát ngưỡng?" | Đổi cân nặng thực / IBW / AdjBW; thanh giả định (B.5); di chuột vào mức thì hiện trích nguyên văn | `tinh_chi_so`, `tra_thuoc`, `doc_doan_mo_rong` |
| V2 | **Tổng liều 24 giờ theo hoạt chất** so với liều tối đa, kèm **lịch dùng theo giờ** | "Paracetamol từ 3 biệt dược có vượt 4 g? Giờ nào dồn hay hổng liều?" | Di chuột từng liều; bật/tắt chế phẩm; khung 24/48/72 giờ | Y lệnh, `lich_dung`, quy tắc liều tối đa (D5) |
| V3 | **Diễn tiến xét nghiệm**: creatinin, kali, natri, INR, bạch cầu, CRP, AST/ALT…, có mốc kê y lệnh và cờ "creatinin tăng nhanh, CrCl kém tin cậy" | "Creatinin đang lên? CrCl hôm nay dùng chỉnh liều được không?" | Bật/tắt chỉ số, chọn khoảng thời gian | `ket_qua_xet_nghiem` |
| **V4** | **Ma trận tương tác** các thuốc đang dùng (thuốc–thuốc), thêm lớp trùng nhóm ATC và dị ứng chéo | "8 thuốc này cặp nào nặng nhất?" | Bấm ô xem cơ chế và trích dẫn; lọc theo mức; bật/tắt lớp ATC và dị ứng | `tra_tuong_tac`, D2, D3 |
| V5 | **Sinh hiệu theo thời gian**: nhiệt độ, huyết áp, mạch, SpO₂ | "Sốt đã hết chưa từ khi đổi kháng sinh?" | Bật/tắt, khoảng thời gian | `sinh_hieu` |
| V6 | **Dòng thời gian kháng sinh**: ngày dùng thứ mấy, đổi hoặc ngưng, kết quả vi sinh và kháng sinh đồ | "Kháng sinh này dùng ngày thứ mấy, có kháng sinh đồ chưa?" (phục vụ hội chẩn kháng sinh, khảo sát B4) | Bấm mốc xem chi tiết | `y_lenh`, `vi_sinh`, `khang_sinh_do` |
| V7 | **So sánh cách tính chức năng thận**: CG thực / IBW / AdjBW / eGFR, kèm ranh giới mức liều | "Sao CrCl và eGFR khác nhau, dùng cái nào?" | Di chuột | `tinh_chi_so` |
| V8 | **Dòng thời gian ca**: vào viện, y lệnh, xét nghiệm, diễn biến | "Thuốc kê trước hay sau kết quả xét nghiệm?" | Thu phóng, bấm mốc | dữ liệu ca |

**Nhóm 2 – thống kê nhiều ca (chế độ chung):**

| # | Hình | Dược sĩ hỏi |
| :--- | :--- | :--- |
| S1 | Số y lệnh cần thẩm định theo ngày, tuần, tháng (đường); theo khoa (cột) | "Tháng này bao nhiêu y lệnh, khoa nào nhiều nhất?" |
| S2 | Nhận định theo 7 yếu tố và mức độ (cột chồng hoặc tròn) | "Lỗi hay gặp nhất là gì?" |
| **S3** | **"Bỏ sót"**. Ba định nghĩa **cần dược sĩ chốt**, mỗi định nghĩa là một chỉ số riêng: (a) y lệnh đã duyệt mà còn nhận định `nghiem_trong` chưa có phản hồi; (b) nhận định bị dược sĩ `bac_bo` (hệ thống báo sai); (c) y lệnh chờ thẩm định quá N giờ | "Tháng này bao nhiêu đơn bị bỏ sót?" |
| S4 | Hoạt chất hoặc thuốc có nhiều cảnh báo nhất (cột ngang) | "Thuốc nào hay bị cảnh báo?" |
| S5 | Tỉ lệ đồng ý / bác bỏ / cần sửa theo luật. Đây là thước đo **độ chính xác của luật**, đúng góp ý mentor | "Luật nào hay báo sai?" |
| S6 | Tương tác nghiêm trọng và kháng sinh nhóm hạn chế theo khoa, theo tháng | "Khoa nào dùng kháng sinh nhóm hạn chế nhiều?" |
| S7 | Thời gian từ kê đến thẩm định (nếu dữ liệu có thời điểm duyệt) | "Trung bình bao lâu thì thẩm định xong?" |
| S8 (admin) | Chỉ số vận hành AI lấy từ tracer | – |

**Đã loại:** hình khái niệm thống kê thuần (như phân phối Gauss), vì không phục vụ quyết định. Mô phỏng nồng độ vancomycin/aminoglycosid **hoãn**, vì cần mô hình dược động học có dược sĩ duyệt.

## B.4. Tool dữ liệu mới
1. **`lay_du_lieu_ca`** (chế độ ca): trả chuỗi thời gian và bảng của ca đang mở, gồm xét nghiệm, sinh hiệu, lịch dùng, kháng sinh và vi sinh. Bộ dữ liệu này phục vụ V2, V3, V5, V6, V8. Chỉ đọc ca mà người dùng được phép xem (kiểm phạm vi `ca_id` như các tool khác).
2. **`thong_ke`** (chế độ chung): **lớp ngữ nghĩa đóng**.
   - LLM chọn `chi_so`, `chieu` (tối đa 2), `loc` và `khoang_thoi_gian` (tối đa 366 ngày) từ danh mục khai báo trong code (`config/thong_ke.yaml`). Code dựng SQL **có tham số**; **không bao giờ nhận SQL hay tên bảng từ LLM**.
   - **Chỉ số khởi đầu:** `so_y_lenh`, `so_nhan_dinh`, `ty_le_dong_y`, `ty_le_bac_bo`, `bo_sot_a/b/c` (sau khi dược sĩ chốt định nghĩa), `so_tuong_tac_nghiem_trong`, `so_khang_sinh_han_che`, `thoi_gian_tham_dinh_trung_vi`.
   - **Chiều:** `ngay|tuan|thang`, `khoa`, `yeu_to`, `muc_do`, `ket_luan`, `hoat_chat`, `ma_luat`.
   - Mỗi chỉ số có **định nghĩa bằng chữ** và mã căn cứ `tk:<chi_so>@<khoang>`. Câu trả lời nêu số thì phải trích mã này. Bộ kiểm chứng số mở rộng để nhận nguồn `tk:`.
   - **Ô nhỏ:** khi chia từ 2 chiều trở lên, ô có số đếm dưới 5 hiện "<5" để tránh nhận diện ngược.
   - **Trả về số tổng hợp**, không trả danh sách người bệnh. Nút "xem danh sách ca" để đợt sau, và chỉ trả mã ca trong phạm vi được phép.
3. **Các tool có sẵn** (`tinh_chi_so`, `tra_thuoc`, `doc_doan_mo_rong`, `tra_tuong_tac`) trả thêm `bo_du_lieu`. Phần văn bản giữ nguyên.

**Thực tế dữ liệu:** hiện chỉ có 66 ca giả lập và rất ít phản hồi, nên hình thống kê sẽ nghèo. Cần sinh dữ liệu giả lập quy mô một tháng (khoảng 1.000–2.000 y lệnh có nhận định và phản hồi; giao sub Sonnet theo plan 1.7) trước khi demo nhóm S.

## B.5. "Thanh giả định" là gì (giải thích theo câu hỏi của chủ kho)

**Ví dụ:** DEMO-02, nữ 75 tuổi, 50 kg, creatinin 212 µmol/L, nên CrCl ≈ 16 ml/phút. Hình V1 đặt điểm người bệnh ở mức "10–25" của bảng liều meropenem.
- Dưới hình có thanh kéo **"Giả định: creatinin"**, mặc định 212.
- Dược sĩ kéo xuống 150 (ví dụ chờ xét nghiệm ngày mai): máy chủ tính lại bằng đúng công thức Cockcroft-Gault, ra CrCl ≈ 22,6. Điểm **giả định** (màu khác, nét đứt) vẫn nằm trong mức 10–25.
- Kéo tiếp xuống 120: CrCl ≈ 28. Điểm giả định sang mức "26–50", tức là **liều sẽ phải đổi** nếu creatinin về mức đó.
- Nút "Về số liệu của ca" đưa thanh về 212.

**Tác dụng:** dược sĩ thấy ngay người bệnh **sát ngưỡng đổi liều** đến đâu, và CrCl "nhạy" thế nào với cân nặng hoặc creatinin. Với người bệnh béo phì, chọn cân nặng nào cũng làm đổi mức liều.

**Ràng buộc:**
- Số giả định do **API công thức có sẵn** tính (`POST /api/cong-thuc/{ma}`, debounce 300 ms, chịu giới hạn tần suất). Không chép công thức sang web.
- Luôn ghi nhãn "giả định, không phải dữ liệu của ca".
- Không lưu, không ghi vào ca, không gửi cho LLM.

**Rủi ro:** dược sĩ có thể hiểu nhầm thành khuyến cáo. Nếu chủ kho hoặc dược sĩ thấy không cần, bỏ thanh này; hình vẫn dùng được.

**Các điều khiển khác** (đều chạy phía máy khách trên dữ liệu đã gửi, không gọi LLM):
- bật/tắt chuỗi;
- lọc theo một cột (khoa, yếu tố…);
- chọn khoảng thời gian;
- đổi kiểu hình giữa các kiểu hợp lệ (cột ↔ đường ↔ bảng);
- di chuột xem giá trị và căn cứ.

## B.6. Khung minh hoạ (giống ảnh mẫu chủ kho gửi)
```
┌──────────────────────────────────────────────────────────────┐
│ Liều meropenem theo chức năng thận            [⤢] [▦ bảng]  │  ← tiêu đề, mở rộng toàn màn, xem dạng bảng
│ DEMO-02 · CrCl 16,0 ml/phút (CG, cân nặng thực)              │  ← phụ đề (số từ dữ liệu)
│                                                              │
│   <10   │  10–25  ●người bệnh  │   26–50   │   >50            │  ← hình
│                                                              │
│ Cân nặng:  (•) thực  ( ) IBW  ( ) AdjBW                      │  ← điều khiển
│ Giả định creatinin: 212 ━━━━━●━━━━━ (giả định)  [Về số ca]   │
│ Nguồn: [tinh:crcl_cg] [bang:merrem_2.3]  · Minh hoạ, không phải khuyến cáo │
└──────────────────────────────────────────────────────────────┘
```
- Nền và viền theo plan 1.4, chạy được cả sáng và tối.
- Màu chuỗi dữ liệu là bảng màu mới. Phải kiểm tương phản và **không chỉ phân biệt bằng màu** (thêm nét, hoa văn, nhãn).
- Nút **mở rộng toàn màn** dùng chung hộp thoại `fullscreen` của UI1.
- "Xem dạng bảng" hiện đúng số và căn cứ. Đây vừa là đường kiểm chứng, vừa phục vụ trợ năng.
- Bàn phím: Tab qua các điều khiển; thanh kéo dùng phím mũi tên.

**Thư viện vẽ:** cần quyết ở VZ1.
- (a) **Tự vẽ SVG** như `LabTrendChart`: 0 gói mới, nhưng tốn công cho 12 kiểu hình.
- (b) **Thẩm định Recharts** (hoặc visx) theo `CLAUDE.md` mục 6a: tồn tại và chủ sở hữu trên npm, ngày phát hành, OSV, thử trong Docker, rồi chủ kho cài.

Claude đề xuất (b) vì danh sách kiểu hình giờ đã rộng. Nếu thẩm định không đạt thì quay về (a).

## B.7. Bảo mật (bắt buộc)
- **Không có HTML hay code từ LLM:** không `iframe`/`srcdoc`, không `dangerouslySetInnerHTML`; React tự escape. `safety.test.ts` vẫn qua; CSP giữ nguyên.
- **`thong_ke`:**
  - SQL có tham số, danh mục chỉ số và chiều đóng;
  - không nhận tên bảng hay biểu thức từ LLM;
  - khoảng thời gian tối đa 366 ngày, tối đa 5 lần gọi mỗi lượt, có hạn giờ truy vấn;
  - quy tắc ô nhỏ;
  - test chèn SQL qua mọi tham số chữ.
- **Phạm vi:**
  - `lay_du_lieu_ca` kiểm quyền xem `ca_id`; ca không có quyền thì 404, giống API ca;
  - `thong_ke` cho `duoc_si_ls` giới hạn khoa ra sao: **câu hỏi mở**;
  - admin xem tất cả.
- **PII:** bộ dữ liệu và khối hình không chứa họ tên, HN, số điện thoại; trục thời gian dùng thời điểm có trong ca. Test canary quét khối hình.
- **Chèn lệnh:** tiêu đề và chú thích qua bộ quét chèn lệnh. Ca thử: đặc tả chứa link hoặc script thì phải bị bỏ.
- **Giới hạn:** 3 hình, 2.000 điểm, 64 KB mỗi câu trả lời; thanh giả định chịu giới hạn tần suất API.
- **Tải CSV:** chưa làm. Nếu làm thì chỉ số tổng hợp, chỉ admin.

## B.8. Nghiệm thu
- **Backend:**
  - bộ dựng: test so **từng điểm** trên hình với bộ dữ liệu của tool, gồm DEMO-02 (V1, V3), HS-019 (V2 paracetamol 6 g/ngày), một ca nhiều thuốc (V4), và dữ liệu tháng giả lập (S1–S5);
  - 8 kiểu đặc tả độc hại hoặc sai phải bị bỏ;
  - `thong_ke` đúng số khi đối chiếu với SQL viết tay độc lập; ca chèn SQL bị chặn; ô nhỏ hiện "<5".
- **Web:**
  - render từng kiểu hình;
  - "Xem dạng bảng" khớp số;
  - điều khiển lọc và bật/tắt đúng;
  - thanh giả định gọi API có debounce và hiện nhãn;
  - mở rộng toàn màn;
  - tương phản sáng/tối đạt.
- **Eval:** thêm 20 câu vào bộ hỏi đáp: 10 câu kỳ vọng có hình đúng kiểu (5 ca, 5 thống kê), 5 câu kỳ vọng **không** có hình, 5 câu thống kê kiểm số.
- **Dược sĩ:** 8 nhiệm vụ (liều thận, tổng liều, tương tác, thống kê tháng), làm có hình và không hình. Đo tỉ lệ đúng và mức tin tưởng.

## B.9. Đợt việc
| Đợt | Việc | Agent | Phụ thuộc |
| :--- | :--- | :--- | :--- |
| **UI1** | Bảng Markdown thành bảng thật, nút mở rộng toàn màn, lịch sử hiện Markdown | Codex terra high | **đã giao 26/11** |
| VZ0 | Mẫu tĩnh khung minh hoạ (V1, V4, S1, S3) cho dược sĩ góp ý; chốt định nghĩa "bỏ sót"; thẩm định thư viện vẽ | Claude + dược sĩ + chủ kho | – |
| TR1 | `app/tracing/`, bọc LLM, móc node / Gateway / kiểm chứng, đích JSONL, `ma_vet` | Codex terra xhigh | – |
| TR2 | Bảng `vet_*`, ghi lô, dọn 30 ngày, API admin | Codex terra xhigh | TR1 |
| VZ1 | `BoDuLieu` trong kết quả tool, tool `ve_bieu_do` + Gateway kiểm đặc tả, bộ dựng, kỹ năng prompt, hợp đồng `minh_hoa`, khung minh hoạ web với 4 kiểu đầu (thang ngưỡng, cột, đường, nhiệt) → V1, V3, V4 | Codex (backend) → Codex/Neon (web) | VZ0, TR1 (chung `ask.py`, `nodes.py`) |
| VZ2 | `lay_du_lieu_ca`, kiểu dòng thời gian → V2, V5, V6, V8 | Codex | VZ1 |
| VZ3 | Dữ liệu giả lập một tháng | sub Sonnet | VZ0 (định nghĩa) |
| VZ4 | `thong_ke` + kiểu tròn, vành, cột chồng → S1–S7 | Codex | VZ1, VZ3 |
| TR3 | Trang quản trị vết (dùng chung khung minh hoạ) | Codex/Neon | TR2, VZ1 |
| VZ5 | 20 câu eval có hình; nhiệm vụ đo với dược sĩ | sub Sonnet + Claude | VZ1–VZ4 |

Các đợt cùng sửa `ask.py`, `nodes.py`, `schemas.py`, `gateway.py` thì chạy **lần lượt**. Phiên làm tool agent (tài khoản Claude khác) cũng sửa những tệp này, nên **phải báo trước khi giao VZ1**.

## B.10. Rủi ro
| Rủi ro | Cách giảm |
| :--- | :--- |
| Dược sĩ hiểu thanh giả định là khuyến cáo | Nhãn và màu riêng; hỏi dược sĩ ở VZ0; bỏ thanh nếu cần |
| AI chọn hình sai kiểu hoặc gây hiểu nhầm (ví dụ hình tròn nhiều phần) | Kỹ năng prompt, Gateway kiểm kiểu và cột, eval có câu kỳ vọng kiểu hình |
| Hình đẹp nhưng sai số | Số chỉ từ bộ dữ liệu của tool, test so từng điểm, có "Xem dạng bảng" |
| Thống kê trên dữ liệu ít, không có ý nghĩa | Dữ liệu giả lập một tháng (VZ3); hình ghi rõ "dữ liệu giả lập" |
| `thong_ke` lộ thông tin qua ô nhỏ | Quy tắc "<5"; không trả danh sách người bệnh |
| Đụng tệp với phiên làm tool agent | Báo trước, làm lần lượt |

## B.11. Còn hỏi chủ kho và dược sĩ
1. Định nghĩa "đơn bị bỏ sót": (a), (b), (c) ở S3, hay định nghĩa khác?
2. `duoc_si_ls` xem thống kê của **mọi khoa** hay chỉ khoa mình phụ trách? (Hiện chưa có dữ liệu "dược sĩ phụ trách khoa nào".)
3. Giữ thanh giả định không (xem ví dụ B.5)?
4. Thư viện vẽ: thẩm định Recharts hay tự vẽ SVG?
5. Bản demo bật `noi_dung_da_che` cho vết không (A.9)?

---

# PHẦN C – BẢNG TRONG KHUNG CHAT (UI1, đã giao 26/11)
- `ClinicalMarkdown` chưa hiểu bảng Markdown, nên bảng hiện thành chữ có dấu `|`.
- UI1 sửa như sau:
  - phân tích bảng kiểu GFM (căn lề, `\|`, giới hạn 200 dòng × 20 cột);
  - bảng nằm trong khung cuộn ngang riêng, tiêu đề cột dính;
  - nút **"Mở rộng bảng"** mở hộp thoại toàn màn **chỉ chứa bảng**, Esc để đóng; bấm trích dẫn trong đó thì đóng hộp thoại và mở nguồn;
  - lịch sử hội thoại cũng hiện Markdown.

  Không thêm gói, không `innerHTML`, có test XSS. Brief: `plan/briefs/UI1-bang-trong-chat-mo-rong.md`.
- Khung minh hoạ của phần B dùng lại hộp thoại `fullscreen` này.
