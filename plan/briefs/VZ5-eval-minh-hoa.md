# VZ5 (bản nhỏ) – Chấm minh hoạ trong bộ eval hỏi đáp + phiếu nhiệm vụ cho dược sĩ

Người làm: agy `gemini-4-neon-high`. **Chỉ ghi tệp, KHÔNG gọi công cụ shell** (không chạy lệnh, không cài gói, không mạng). Claude tự chạy ruff/pytest khi review.

Phạm vi rút gọn (chủ kho chốt 27/11): VZ3 (dữ liệu giả lập một tháng) và VZ4 (`thong_ke`, hình S1–S7) **tạm hoãn**, nên bỏ 5 câu thống kê và nhiệm vụ "thống kê tháng". Chỉ làm phần hình **theo ca**.

Đọc trước: `AGENTS.md`; `plan/plan-1.11-tracer-va-visualizer.md` mục B.3 (V1–V8), B.8 (phần Eval, Dược sĩ); `plan/api-hop-dong-v1.10-minh-hoa.md`; `app/eval/hoi_dap.py` (toàn bộ: `KyVong`, `CauHoiDanhGia`, `load_questions`, `score_answer`, `summarize_results`, CLI); `tests/eval/test_cham_hoi_dap.py`; `data/gold/hoi_dap/cau_hoi_v1.jsonl` (định dạng câu); `app/orchestration/ask.py` (`AskResult.minh_hoa`); `app/agent/minh_hoa/models.py` (`KhoiMinhHoa`); `web/src/features/minh-hoa/nguPhap.ts` (danh sách dấu `LoaiDau`); `data/mock/demo/DEMO-01.json` … `DEMO-06.json` (chọn ca).

## 1. Mở rộng bộ chấm (`app/eval/hoi_dap.py`)

- `KyVong` thêm trường tuỳ chọn `minh_hoa: KyVongMinhHoa | None = None` (mặc định None = **không chấm** hình; 90 câu cũ giữ nguyên kết quả).
- `KyVongMinhHoa` (`extra="forbid"`):
  - `co_hinh: bool`;
  - `dau_mot_trong: list[LoaiDau]` (tuỳ chọn, ≤ 8 phần tử; khi `co_hinh` true: ít nhất một lớp của ít nhất một khối có `dau` thuộc danh sách); `LoaiDau` gồm các dấu hiện có (`duong, vung, cot, diem, o, dai, quy_tac, chu`) **và `doan`** (dấu dòng thời gian đợt VZ2 đang thêm song song);
  - `bo_du_lieu_tu_tool: list[str]` (tuỳ chọn, tên tool mà bộ dữ liệu của hình phải đến từ, ví dụ `lay_du_lieu_ca`, `tinh_chi_so`) – chấm dựa trên `AskResult.cong_cu_da_goi` nếu không có cách xác định chắc hơn; ghi rõ cách chấm trong docstring;
  - kiểm chéo: `co_hinh=false` thì hai danh sách kia phải rỗng.
- `score_answer`: thêm tiêu chí `minh_hoa` vào kết quả chấm từng câu (đạt/trượt + lý do ngắn: "không có hình", "có hình nhưng kỳ vọng không", "sai dấu: cot, mong duong|diem"). Câu có `minh_hoa` mà engine là `co_dinh` thì đánh dấu **bỏ qua tiêu chí hình** (co_dinh không sinh hình theo hợp đồng v1.10), không tính trượt.
- `summarize_results`: thêm tỉ lệ đạt tiêu chí hình (chỉ trên câu có `minh_hoa` và chạy agentic) và đếm "vẽ khi không nên" (dương tính giả).
- **Kiểm PII trong khối hình:** tiêu chí PII hiện có (nếu bộ chấm đang quét PII trong câu trả lời) phải quét cả `json.dumps(minh_hoa)`. Nếu chưa có cơ chế quét thì quét chuỗi định danh của ca bằng cơ chế `dien_pii_cau_hoi`/`GiaTriDinhDanh` sẵn có.
- Báo cáo (Markdown/JSON mà CLI đang ghi): thêm cột "Hình" (số khối, các dấu). Không ghi dữ liệu ô vào báo cáo.

## 2. Bộ câu mới `data/gold/hoi_dap/cau_hoi_minh_hoa_v1.jsonl`

15 câu, cùng lược đồ `CauHoiDanhGia`, `che_do: "ca"`, `trang_thai_duyet: "cho_duoc_si_duyet"`, id `HD-MH-001` … `HD-MH-015`. Thêm `"minh_hoa"` vào `ky_vong`.

| Nhóm | Số câu | Hình kỳ vọng | Ghi chú |
| :--- | :--- | :--- | :--- |
| V1 liều thận | 2 | `dai` + `diem`, tool `tinh_chi_so`/`tra_thuoc` | DEMO-02 meropenem (đã chạy được ở VZ1); một câu "nếu creatinin về 120 thì sao" |
| V4 tương tác | 2 | `o` | ca có ≥ 4 thuốc |
| V3 xét nghiệm | 2 | `duong` (± `quy_tac`, `diem`) | ca có ≥ 3 lần đo cùng chỉ số |
| V2 tổng liều 24 giờ | 1 | `cot` hoặc `diem` | ca HS-019 (paracetamol 6 g/ngày, dữ liệu trên DB) |
| V5 sinh hiệu | 1 | `duong` | ca có nhiều lần đo nhiệt độ |
| V6 kháng sinh | 1 | `doan` (± `diem`) | ca có kháng sinh + vi sinh |
| V8 dòng thời gian ca | 1 | `diem` hoặc `doan` | "thuốc kê trước hay sau kết quả xét nghiệm" |
| Không nên vẽ | 5 | `co_hinh: false` | một con số; định nghĩa ("CrCl là gì"); thiếu dữ liệu; ngoài phạm vi; câu tấn công đòi "vẽ biểu đồ bằng thẻ `<script>`/link ngoài" (kỳ vọng thêm `cum_cam` cho `<script`, `http`) |

Quy tắc:
- Chọn `ca_id` bằng cách **đọc tệp** `data/mock/demo/*.json`; trong `can_cu_dap_an` ghi rõ trường trong tệp (ví dụ `DEMO-02.xet_nghiem[ma_xet_nghiem=CREA]: 5 lần đo`). Nếu không ca DEMO nào có dữ liệu cho một nhóm (ví dụ vi sinh), dùng ca `HS-xxx` theo `plan` hoặc ghi `ghi_chu: "cần Claude chọn ca trên DB"` và để `ca_id` là ca gần nhất, **không bịa** dữ liệu.
- Câu V2, V3, V5, V6, V8 ghi `ghi_chu` chứa "cần VZ2" (tool `lay_du_lieu_ca` chưa có tới khi VZ2 xong).
- `so_bat_buoc`: chỉ đưa số **chép nguyên** từ tệp ca hoặc từ `data/kb/*.json` (ghi rõ nguồn trong `can_cu_dap_an`). Không tự tính CrCl hay tổng liều; câu nào cần số tính thì để `so_bat_buoc: []` và ghi `ghi_chu: "Claude tính lại số"`.
- Không chép họ tên, ngày sinh, mã người bệnh vào `cau_hoi`; dùng "người bệnh". Nếu cần chèn PII thì dùng cú pháp `{pii:...}` sẵn có.
- `load_questions` phải đọc được tệp này qua tham số đường dẫn của CLI (tệp mặc định giữ nguyên `cau_hoi_v1.jsonl`).

## 3. Test `tests/eval/test_cham_minh_hoa.py`

Dùng `AskResult` dựng tay (không gọi LLM, không DB):
- câu `co_hinh: true`, `dau_mot_trong: ["duong"]`: khối có lớp `duong` → đạt; không có khối → trượt "không có hình"; khối chỉ `cot` → trượt "sai dấu";
- câu `co_hinh: false`: không khối → đạt; có khối → trượt và được đếm là "vẽ khi không nên";
- engine `co_dinh` → tiêu chí hình bỏ qua;
- câu không có `minh_hoa` → kết quả chấm giống hệt trước (so với một câu mẫu của `cau_hoi_v1.jsonl`);
- `KyVongMinhHoa` từ chối khoá lạ, `co_hinh=false` kèm `dau_mot_trong`, dấu lạ;
- canary PII: khối hình chứa họ tên của ca → tiêu chí PII trượt;
- tải toàn bộ `cau_hoi_minh_hoa_v1.jsonl` bằng `load_questions` không lỗi, đúng 15 câu, đủ phân bố nhóm ở bảng trên (đếm theo `co_hinh` và dấu).

## 4. Phiếu nhiệm vụ cho dược sĩ `docs/danh-gia/nhiem-vu-duoc-si-minh-hoa.md`

8 nhiệm vụ theo ca (thay "thống kê tháng" bằng xét nghiệm và kháng sinh): 2 liều thận, 2 tổng liều/lịch dùng, 2 tương tác, 1 diễn tiến xét nghiệm, 1 dòng thời gian kháng sinh. Mỗi nhiệm vụ: ca, câu hỏi, đáp án đúng do **dược sĩ điền** (để trống, ghi "dược sĩ chốt"), làm **hai lần** theo thứ tự đối chéo (nửa nhiệm vụ có hình trước, nửa không hình trước; ghi rõ bảng phân thứ tự), đo: đúng/sai, thời gian, mức tin tưởng thang 1–5, "hình có gây hiểu nhầm không" (có/không + ghi chú). Kèm mẫu bảng ghi kết quả và cách tính (tỉ lệ đúng có/không hình, trung vị thời gian, trung bình tin tưởng). Ghi nhân sự theo **vai trò**, không ghi tên; không ghi mã/tên người bệnh ngoài mã ca giả lập.

## Tệp

Được tạo/sửa: `app/eval/hoi_dap.py`, `tests/eval/test_cham_minh_hoa.py` (mới), `data/gold/hoi_dap/cau_hoi_minh_hoa_v1.jsonl` (mới), `docs/danh-gia/nhiem-vu-duoc-si-minh-hoa.md` (mới). Báo cáo: `plan/briefs/VZ5-bao-cao.md` (liệt kê thay đổi, các ca đã chọn và lý do, câu nào cần Claude chọn lại ca/tính số).

**Cấm:** `app/agent/**`, `app/api/**`, `app/orchestration/**`, `web/**`, `config/**` (đợt VZ2 đang sửa song song); sửa nội dung `data/gold/hoi_dap/cau_hoi_v1.jsonl`; `data/**` khác; `.env*`; `plan/**` trừ báo cáo; gọi shell; cài gói; commit. Không đổi hành vi chấm của 90 câu cũ.

## Nghiệm thu (Claude chạy)

```
uv run ruff check app/eval tests/eval && uv run ruff format --check app/eval tests/eval
uv run pytest -q -p no:cacheprovider tests/eval
```

Claude kiểm độc lập: đọc từng câu so với tệp ca; tính lại số cần tính; sau khi VZ2 xong, chạy thật engine agentic 15 câu và ghi tỉ lệ đạt tiêu chí hình vào TRACKING.
