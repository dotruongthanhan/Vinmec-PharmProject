# Plan 1.9 – Chuyển RAG cố định sang Agentic RAG: công cụ, phân quyền, chốt an toàn

Ngày lập: 18/11/2026. Trạng thái: **bản nháp, chờ nhóm duyệt.** Bám plan 1.1 (kiến trúc), 1.5 (bảo mật), mục 7.5 của plan 1.1 (đồ thị LangGraph, T49).

## 1. Mục tiêu

1. **Agent tự tra cứu qua công cụ** thay cho một bước truy xuất cố định: LLM chọn công cụ nào, với truy vấn gì, và tra lại khi thiếu.
2. **Không để LLM "lộng hành":** mọi việc LLM làm đều đi qua công cụ có lược đồ, có quyền, có giới hạn; kết quả vẫn qua các chốt kiểm chứng như hiện nay. Mở đường cho **phân quyền theo công cụ**: vai trò A không được gọi công cụ X, hoặc chỉ được gọi với phạm vi hẹp.
3. **Mỗi nguồn dữ liệu một công cụ riêng:** hồ sơ bệnh án, y lệnh, phiếu điều trị, phác đồ, kho tri thức thuốc... lưu ở nơi khác nhau, có quy tắc truy cập khác nhau.
4. **Hai chế độ làm việc:** theo một ca/y lệnh đang mở, và **không chọn ca** (dược sĩ hỏi chung, ví dụ "tra bệnh X", "phác đồ viêm phổi cộng đồng", "liều vancomycin theo thận").

## 2. Hiện trạng (đã kiểm mã ngày 18/11)

| Thành phần | Hiện tại |
| :--- | :--- |
| Truy xuất | Bước cố định `EvidenceCollector.collect` (`app/orchestration/evidence.py`): code dựng truy vấn theo phát hiện luật, chạy BM25 + vector + RRF + rerank trong bộ nhớ từ `data/kb_curated/chunks.jsonl`. LLM không chọn gì. |
| Điều phối | LangGraph luồng thẳng (T49): `thu_thap_nguon → tong_hop → hoan_tat`, cờ `orchestration.engine`. |
| Hỏi thêm | `app/orchestration/ask.py` có chế độ theo ca và chế độ chung (`ask_global`, mã `__global__`). Trường `cong_cu_da_goi` chỉ là **nhãn bước**, không có tool calling. |
| Gọi LLM | `complete_json(messages, schema)` (`app/providers/deepseek_llm.py`), chưa truyền danh sách công cụ. |
| Che PII | T48: che theo trường + mẫu, mã tạm `R1..`, `[TEN_1]`, khôi phục sau kiểm chứng. |
| Vai trò | `duoc_si_ls`, `admin` (`app/auth/roles.py`); `Principal` truyền xuống dịch vụ. |
| Cấu hình sẵn | `max_turns: 5` (chưa dùng như vòng lặp công cụ thật). |

Kết luận: hệ thống là **RAG cố định**, chưa phải agentic RAG; chưa có lớp công cụ, chưa có phân quyền theo công cụ.

## 3. Nguyên tắc bất biến (không được nới khi chuyển)

1. **LLM không tự tính.** Mọi con số lâm sàng do công cụ tính (`app/calc`), LLM chỉ đọc kết quả.
2. **LLM không sửa kết quả luật.** Phát hiện của bộ luật không bị xóa hay hạ mức; `merge` giữ nguyên ở cuối luồng.
3. **Mọi nhận định qua kiểm chứng** trích dẫn nguyên văn và kiểm số trước khi hiển thị, bất kể nguồn đến từ công cụ nào.
4. **Chỉ đọc.** Không công cụ nào ghi DB, duyệt đơn, gửi tin, ghi OH/EMR.
5. **PII không ra khỏi hệ thống:** công cụ trả dữ liệu ca **đã che**; tham số công cụ do LLM sinh được quét PII trước khi chạy (đặc biệt công cụ gọi ra ngoài).
6. **Đầu ra công cụ là dữ liệu, không phải chỉ thị:** bọc trong dấu đánh dấu như `<<<DU_LIEU_BENH_AN`, quét chèn lệnh, không bao giờ nối thẳng vào system prompt.
7. **Có đường lui:** cờ cấu hình quay về luồng thẳng hiện tại; AI lỗi thì vẫn còn kết quả luật.

## 4. Kiến trúc đề xuất

### 4.1 Ba lớp

```
LLM (chỉ thấy tên + mô tả + lược đồ của các công cụ được phép)
   │  đề xuất gọi công cụ (tên, tham số JSON)
   ▼
Cổng công cụ (ToolGateway)  ← chốt an toàn duy nhất
   • có trong danh mục? vai trò được phép? đúng phạm vi ca?
   • tham số đúng lược đồ (pydantic), quét PII, quét chèn lệnh
   • ngân sách: số lượt, thời gian, số đoạn trả về
   • ghi nhật ký kiểm toán (tên công cụ, vai trò, mã ca băm, thời gian; KHÔNG ghi nội dung)
   ▼
Công cụ (Tool) – lớp mỏng bọc dịch vụ hiện có, chỉ đọc
```

### 4.2 Đồ thị LangGraph

```
START → chuan_bi (luật + công thức chạy bằng code, như hiện nay)
      → tac_tu (LLM chọn công cụ hoặc kết thúc)
            ⇄ goi_cong_cu (qua ToolGateway)        [tối đa N vòng, hạn T giây]
      → tong_hop (LLM viết nhận định từ các đoạn đã thu)
      → kiem_chung (trích dẫn, số, mã bản ghi)  → (thử lại tổng hợp nếu trượt)
      → ghep_luat → khoi_phuc_PII → hoan_tat → END
```
- Hết lượt/hết giờ/lỗi công cụ → đi thẳng `tong_hop` với những gì đã có, hoặc trả kết quả chỉ-luật.
- Đường thẳng T49 giữ làm chế độ `tuan_tu`/`langgraph_thang`; chế độ mới tên `agentic`.

### 4.3 Bối cảnh chạy (ToolContext)
Mỗi lượt có một `ToolContext` bất biến: `principal` (vai trò), `pham_vi` (`ca` + `ca_id` hoặc `chung`), `deid_session` (T48), ngân sách còn lại, danh sách đoạn nguồn đã cấp (để kiểm chứng). Công cụ **không nhận `ca_id` từ LLM**: phạm vi ca lấy từ `ToolContext`, nên LLM không thể tự nhảy sang hồ sơ người bệnh khác.

## 5. Danh mục công cụ

| Nhóm | Công cụ | Nguồn | Chế độ | Ghi chú |
| :--- | :--- | :--- | :--- | :--- |
| Kho tri thức | `tra_kho_tri_thuc(hoat_chat?, yeu_to?, cau_hoi)` | RAG hiện có (hybrid + rerank) | ca, chung | Tầng 1, ưu tiên cao nhất |
| Kho tri thức | `tra_tuong_tac(hoat_chat_a, hoat_chat_b)` | DDInter (chỉ sàng lọc) | ca, chung | Giấy phép phi thương mại |
| Phác đồ | `tra_phac_do(benh_hoac_icd10, cau_hoi)` | Phác đồ BYT/bệnh viện (kho riêng, chưa có) | ca, chung | Cần nguồn được Khoa Dược duyệt |
| Bệnh | `tra_benh(ten_hoac_icd10)` | ICD-10 + văn bản BYT | chung | Phục vụ "tra bệnh X" khi chưa chọn ca |
| Hồ sơ bệnh án | `doc_ho_so(muc)` – mục: chẩn đoán, dị ứng, cơ địa, sinh hiệu, xét nghiệm, vi sinh, diễn biến | `nghiep_vu` (đã che PII) | chỉ ca | Không nhận mã ca từ LLM |
| Y lệnh | `doc_y_lenh(loai)` – chờ duyệt, đang dùng, lịch sử các lần vào viện | `nghiep_vu.y_lenh` | chỉ ca | |
| Phiếu điều trị | `doc_phieu_dieu_tri(ngay?)` | `nghiep_vu.phieu_dieu_tri` | chỉ ca | Văn bản tự do → che PII + quét chèn lệnh |
| Luật | `xem_ket_qua_luat()` | `app/rules` | chỉ ca | Chỉ đọc |
| Tính toán | `tinh_chi_so(cong_thuc)` – CrCl, eGFR, BMI, BSA | `app/calc` | chỉ ca | Đầu vào lấy từ hồ sơ, không nhận số từ LLM |
| Nguồn ngoài (tầng 2) | `tra_openfda(hoat_chat, muc)` | openFDA/DailyMed API | ca, chung | Sau demo; nhãn Mỹ, ghi rõ |
| Nguồn ngoài (tầng 3) | `tim_web(cau_hoi)` | TinyFish | ca, chung | **Chờ nhóm quyết**; mặc định tắt |

Mỗi công cụ là một lớp có: `ten`, `mo_ta` (cho LLM), `LuocDoThamSo` (pydantic, `extra="forbid"`), `LuocDoKetQua`, `pham_vi_cho_phep`, `muc_nhay_cam`, `chi_doc=True`, `goi_ra_ngoai: bool`, `thoi_gian_toi_da`.

## 6. Phân quyền theo công cụ

### 6.1 Chính sách khai báo (một tệp, ví dụ `config/tool_policy.yaml`)
```yaml
vai_tro:
  duoc_si_ls:
    cho_phep: [tra_kho_tri_thuc, tra_tuong_tac, tra_phac_do, tra_benh,
               doc_ho_so, doc_y_lenh, doc_phieu_dieu_tri, xem_ket_qua_luat, tinh_chi_so]
    gioi_han:
      doc_ho_so: { muc: [chan_doan, di_ung, co_dia, sinh_hieu, xet_nghiem, vi_sinh, dien_bien] }
  admin:
    cho_phep: [tra_kho_tri_thuc, tra_benh]      # quản trị không cần đọc hồ sơ lâm sàng
  # vai_tro_tuong_lai (ví dụ hoc_vien): chỉ kho tri thức, không hồ sơ
mac_dinh: tu_choi                              # không khai báo = không được gọi
cong_cu_ra_ngoai:
  tra_openfda: { bat: false }
  tim_web:     { bat: false, can_duoc_si_bam: true }
```

### 6.2 Cách áp dụng (hai lần chặn)
1. **Trước khi gọi LLM:** chỉ đưa vào prompt các công cụ vai trò được phép, nên LLM không biết công cụ bị cấm tồn tại.
2. **Tại ToolGateway:** kiểm lại vai trò, phạm vi, giới hạn tham số; từ chối thì trả lỗi có cấu trúc ("không có quyền") cho LLM và ghi nhật ký kiểm toán. Không tin vào việc LLM "tự giác".

Mặc định **từ chối**; thêm vai trò mới chỉ cần sửa chính sách, không sửa mã công cụ. Về sau có thể chuyển chính sách vào bảng DB có RLS (đồng bộ plan 1.5).

## 7. Chống LLM lộng hành (tóm tắt các chốt)

| Rủi ro | Chốt |
| :--- | :--- |
| Gọi công cụ không được phép | Danh mục theo vai trò + kiểm tại Gateway, mặc định từ chối |
| Đọc hồ sơ người bệnh khác | Phạm vi ca lấy từ `ToolContext`, không nhận mã ca từ LLM |
| Vòng lặp vô hạn, tốn chi phí | `max_turns` (mặc định 5), hạn thời gian mỗi lượt, giới hạn số đoạn |
| Chèn lệnh qua đầu ra công cụ (hồ sơ, web) | Bọc dữ liệu, quét chèn lệnh, đầu ra công cụ không bao giờ thành system prompt |
| Rò PII ra ngoài | Dữ liệu ca đã che; tham số công cụ gọi ra ngoài phải qua bộ che, có định danh thì từ chối |
| Bịa nguồn, bịa số | Kiểm chứng trích dẫn nguyên văn và kiểm số như hiện nay; chỉ đoạn công cụ đã trả trong lượt mới được trích |
| Hạ mức cảnh báo luật | `merge` giữ nguyên ở cuối, ngoài tầm LLM |
| Kết luận "đạt" từ nguồn yếu | Nguồn tầng 3 không bao giờ cho kết luận "đạt"; gắn nhãn hạng nguồn |
| Khó truy vết | Nhật ký kiểm toán: công cụ, vai trò, mã ca băm, thời gian, kết quả cho phép/từ chối; không ghi nội dung |

## 8. Chế độ "không chọn ca"

- Phạm vi `chung`: chỉ có công cụ tri thức (`tra_kho_tri_thuc`, `tra_tuong_tac`, `tra_phac_do`, `tra_benh`, sau này `tra_openfda`); **không có** công cụ đọc hồ sơ/y lệnh.
- Câu hỏi như "tra bệnh X", "phác đồ Y", "liều Z" đi theo phạm vi này; nếu dược sĩ nhắc tên người bệnh, câu hỏi vẫn qua bộ che PII và agent không có công cụ nào để tìm người bệnh đó.
- Giao diện: ô hỏi thêm khi chưa chọn y lệnh dùng phạm vi `chung` (đã có `__global__`), hiển thị rõ "đang hỏi chung, không gắn ca".

## 9. Lộ trình

| Giai đoạn | Nội dung | Đầu ra | Thời điểm |
| :--- | :--- | :--- | :--- |
| P0 – thử | Kiểm `deepseek-flash` (và `deepseek-v4-pro`) có tool calling ổn định không (định dạng, nhiều công cụ, tham số JSON); đo độ trễ | Báo cáo ngắn, chọn mô hình | Trước khi viết mã |
| P1 – đóng gói | `app/tools/`: lớp `Tool`, danh mục, `ToolGateway`, `ToolContext`, chính sách vai trò, nhật ký kiểm toán; bọc các dịch vụ hiện có thành công cụ. **Luồng thẳng hiện tại gọi qua Gateway** theo thứ tự cố định (chưa có LLM chọn) | Hành vi không đổi, 66 ca giống hệt; test quyền | Có thể trước demo nếu kịp (rủi ro thấp) |
| P2 – agent ở hỏi thêm | Vòng `tac_tu ⇄ goi_cong_cu` cho ô hỏi thêm (cả theo ca và chung), cờ `ask.engine: agentic`, mặc định tắt | Đối chiếu chất lượng với bản cũ trên bộ câu hỏi mẫu | Sau demo |
| P3 – agent ở thẩm định | Vòng tương tự cho thẩm định ca; giữ nguyên kiểm chứng và ghép luật | Đối chiếu trên 66 ca + bộ đáp án | Sau P2 |
| P4 – phác đồ, bệnh | Kho phác đồ và ICD-10 đã duyệt, công cụ `tra_phac_do`, `tra_benh` | | Khi có nguồn được Khoa Dược duyệt |
| P5 – nguồn ngoài | `tra_openfda` (tầng 2), sau đó `tim_web` (tầng 3) theo quyết định nhóm | | Sau P3 |

## 10. Kiểm thử và đánh giá

- **Quyền:** mỗi vai trò × mỗi công cụ (cho phép/từ chối), công cụ bị cấm không xuất hiện trong prompt, gọi mã ca khác bị từ chối.
- **Chèn lệnh:** HS-056..060 và ca tấn công qua đầu ra công cụ (diễn biến, phiếu, trang web giả) – agent không đổi hành vi, vẫn báo "đoạn văn bất thường".
- **PII:** tham số công cụ ra ngoài không bao giờ chứa định danh (chạy trên 66 ca).
- **Ngân sách:** dừng đúng ở `max_turns`, đúng hạn thời gian.
- **Chất lượng:** so bản cố định và bản agentic trên 66 ca + bộ câu hỏi mẫu: độ phủ phát hiện, số nhận định qua kiểm chứng, số trích dẫn, thời gian, số lần gọi LLM.
- **Bất biến:** kết quả luật giống hệt; không nhận định AI nào hiển thị mà chưa qua kiểm chứng.

## 11. Rủi ro

| Rủi ro | Mức | Giảm thiểu |
| :--- | :--- | :--- |
| DeepSeek tool calling không ổn định | Cao | P0 thử trước; dự phòng: LLM trả JSON "kế hoạch tra cứu" theo lược đồ, code thực thi (agent có cấu trúc, không cần tool calling gốc) |
| Chậm hơn (hiện 45–48 s/ca) | Trung bình | Giới hạn lượt, chạy song song công cụ độc lập, cache kết quả tra kho |
| Kết quả kém ổn định | Trung bình | Nhiệt độ 0, cờ quay về luồng thẳng, đánh giá trên bộ cố định trước khi bật |
| Chính sách quyền sai | Trung bình | Mặc định từ chối, test ma trận quyền, chính sách nằm một chỗ |
| Nguồn phác đồ chưa có | Cao cho P4 | Không làm P4 đến khi có nguồn được duyệt |

## 12. Câu hỏi mở cho nhóm

1. Ngoài `duoc_si_ls` và `admin`, sẽ có vai trò nào (bác sĩ, học viên, dược sĩ trưởng)? Mỗi vai trò được tra gì?
2. Phác đồ lấy từ đâu (BYT, phác đồ nội viện) và ai duyệt?
3. Tầng 3 (TinyFish): có dùng không, điều khoản lưu dữ liệu, danh sách hạng nguồn.
4. Nhật ký kiểm toán lưu bao lâu, ai được xem?
5. Có cho dược sĩ thấy "agent đã gọi công cụ nào" trên giao diện không (khuyến nghị: có, dạng tóm tắt)?

## 13. Hướng phát triển thêm

1. **Mô hình lai.** 7 yếu tố thẩm định chạy luồng cố định (ổn định, tái lập được); agent tự chọn công cụ chỉ ở ô hỏi thêm, hoặc khi luồng cố định không tìm đủ nguồn.
2. **Bộ đánh giá cố định trước khi bật agent.** 66 ca + bộ câu hỏi mẫu có đáp án dược sĩ duyệt; đo độ phủ phát hiện, số nhận định qua kiểm chứng, độ trễ, chi phí. Chỉ bật agent khi không kém luồng cố định.
3. **Dược sĩ xác nhận giữa chừng.** Trước khi gọi công cụ ra ngoài (openFDA, web), đồ thị dừng chờ dược sĩ đồng ý (cơ chế ngắt của LangGraph).
4. **Hiển thị vết công cụ trên giao diện.** Ví dụ "Agent đã tra: kho tri thức (meropenem, thận); xét nghiệm creatinin", để dược sĩ biết căn cứ đến từ đâu.
5. **Bộ nhớ đệm kết quả tra cứu** theo hoạt chất và yếu tố, giảm độ trễ và chi phí.
6. **Kho phác đồ và ICD-10 đã duyệt**, có phiên bản và ngày hiệu lực, làm nguồn cho `tra_phac_do` và `tra_benh`.
7. **Chuyển chính sách quyền vào DB có RLS** khi có thêm vai trò (bác sĩ, học viên, dược sĩ trưởng).
8. **Bộ ca tấn công riêng cho agent:** chèn lệnh trong đầu ra công cụ, yêu cầu gọi công cụ bị cấm, cố đọc hồ sơ người bệnh khác.
9. **Theo dõi khi vận hành:** tỷ lệ bị từ chối quyền, số vòng trung bình, tỷ lệ trượt kiểm chứng, chi phí mỗi ca; chỉ ghi số liệu, không ghi nội dung.
