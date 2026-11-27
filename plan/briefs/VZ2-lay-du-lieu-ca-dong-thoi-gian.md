# VZ2 – Tool `lay_du_lieu_ca` và dấu dòng thời gian (V2, V3, V5, V6, V8)

Người làm: Codex `gpt-6.1-terra` xhigh. Được chạy ruff, pytest, vitest, tsc; **không** cài gói, không mạng, không commit, không đọc `.env`.

Đọc trước: `AGENTS.md`; `plan/plan-1.11-tracer-va-visualizer.md` mục B.2, B.3 (V2, V3, V5, V6, V8), B.4 mục 1, B.7; `plan/api-hop-dong-v1.10-minh-hoa.md` (hợp đồng `KhoiMinhHoa`, `BoDuLieu`, ngữ pháp `mh-1`); `plan/plan-1.11-bo-sung-ngu-phap-minh-hoa.md`; báo cáo VZ1: `plan/briefs/VZ1a-bao-cao.md`, `VZ1a-2…5-bao-cao.md`, `VZ1b-bao-cao.md`, `VZ1-fix-1/2-bao-cao.md` (biết cái đã có, **không làm lại**).

Mã liên quan: `app/agent/tools/*.py` (mẫu: `tinh_chi_so.py`, `tra_tuong_tac.py` sinh `bo_du_lieu`; `ve_bieu_do.py`), `app/agent/tools/gateway.py`, `registry.py`, `policy.py`, `config/tool_policy.yaml`, `app/agent/minh_hoa/{models,kiem}.py`, `app/domain/models.py` (`CaBenh`: `sinh_hieu`, `xet_nghiem`, `vi_sinh`, `y_lenh[].chi_tiet[].lich_dung`, `thuoc.thanh_phan`, `la_khang_sinh`, `dien_bien`), `app/rules/d5_config.py` + `data/kb/lieu_toi_da.json` (liều tối đa ngày), `config/prompts/ky_nang_minh_hoa.v1.md`, `web/src/features/minh-hoa/{nguPhap.ts,dungMoHinh.ts,KhungMinhHoa.tsx}`.

## Mục tiêu

Ở chế độ ca, dược sĩ hỏi về **diễn tiến theo thời gian của ca đang mở** thì agent lấy được bộ dữ liệu thời gian do code dựng và vẽ được: V2 (tổng liều 24 giờ + lịch dùng theo giờ), V3 (diễn tiến xét nghiệm, có mốc kê y lệnh), V5 (sinh hiệu), V6 (dòng thời gian kháng sinh + vi sinh), V8 (dòng thời gian ca). Mọi số trên hình đến từ code. LLM không tính.

## Yêu cầu

### 1. Tool `lay_du_lieu_ca` (mới, chỉ đọc)

- **Chỉ chế độ ca.** Ca lấy từ ngữ cảnh lượt (giống cách các tool khác lấy ca hiện tại), **không nhận `ca_id` từ LLM**. Tham số pydantic `extra="forbid"`. Chế độ chung hoặc không có ca → `tu_choi` với lý do ngắn. Quyền xem ca: dùng đúng cơ chế kiểm phạm vi sẵn có; ca không được phép → kết quả giống "không tìm thấy" (không lộ ca có tồn tại).
- Tham số:
  - `phan`: danh sách con (1–5 phần tử, không trùng) của `xet_nghiem | sinh_hieu | lich_dung | khang_sinh | moc_ca`;
  - `ma_xet_nghiem`: tuỳ chọn, ≤ 10 mã, mỗi mã ≤ 32 ký tự, chỉ chữ/số/`_`/`-` (lọc phần xét nghiệm);
  - `loai_sinh_hieu`: tuỳ chọn, tương tự.
- Mỗi phần sinh **một bộ dữ liệu** (đi qua Gateway như VZ1: đánh mã `ds-n`, che PII ô chuỗi, tóm tắt ≤ 5 dòng mẫu cho LLM, trần 20 cột × 2.000 dòng; vượt trần thì **giữ các dòng mới nhất** tới 2.000 và ghi `vet_bi_cat`/lý do trong span, không bỏ cả bộ). Phần văn bản trả LLM: tóm tắt ngắn có số liệu chính (ví dụ "creatinin: 5 lần đo, 98 → 212 µmol/L") để câu trả lời chữ có căn cứ; mã căn cứ dạng `ca:<phan>` hoặc theo quy ước `du_lieu` hiện có của bộ kiểm chứng (đọc `app/verify` để chọn đúng, không đổi logic kiểm chứng).
- Cột của từng bộ (kiểu theo `CotDuLieu.kieu`):
  - **`xet_nghiem`**: `thoi_diem` (thoi_gian), `ma_xet_nghiem` (danh_muc), `ten_xet_nghiem` (danh_muc), `gia_tri` (dinh_luong, null nếu chỉ có chữ), `don_vi`, `nguong_duoi`, `nguong_tren` (dinh_luong), `ngoai_nguong` (logic, code so). Thêm cột `creatinin_tang_nhanh` (logic) cho dòng creatinin: tăng ≥ 26,5 µmol/L trong ≤ 48 giờ **hoặc** ≥ 1,5 lần giá trị thấp nhất trong 7 ngày trước (tiêu chuẩn KDIGO 2012 AKI). Nếu kho đã có hàm/luật tương đương (tìm `rg -n "26.5|tang_nhanh|AKI|KDIGO" app`) thì **dùng lại**, không viết bản thứ hai. Đổi đơn vị mg/dL ↔ µmol/L bằng hàm sẵn có.
  - **`sinh_hieu`**: `thoi_diem`, `loai` (danh_muc), `gia_tri`, `don_vi`.
  - **`lich_dung`** (hai bộ): (a) từng liều: `thoi_diem`, `thuoc` (tên thuốc), `hoat_chat` (danh_muc), `lieu` (dinh_luong, theo hoạt chất, đổi từ `lieu` × `thanh_phan` bằng code), `don_vi`; (b) tổng 24 giờ theo hoạt chất: `hoat_chat`, `tong_24h_lon_nhat` (tổng **cửa sổ 24 giờ trượt** lớn nhất trên lịch dùng), `cua_so_tu`, `cua_so_den` (thoi_gian), `lieu_toi_da_ngay` (từ `lieu_toi_da.json` qua `d5_config`, null nếu không có), `vuot` (logic), `so_che_pham` (dinh_luong). Thiếu `lich_dung` thì suy từ `lieu_moi_lan` × `so_lan_moi_ngay` **chỉ khi** có đủ dữ liệu và ghi cột `nguon_lich` = `lich_dung|suy_tu_tan_suat`. Nếu luật D5 đã có hàm tính tổng ngày theo hoạt chất thì dùng lại để số khớp với nhận định D5.
  - **`khang_sinh`** (hai bộ): (a) đợt kháng sinh: `thuoc`, `hoat_chat`, `bat_dau`, `ket_thuc` (thoi_gian; null nếu đang dùng thì dùng mốc tham chiếu của ca, ghi `dang_dung` logic), `ngay_thu` (dinh_luong, số ngày từ `bat_dau` đến mốc tham chiếu, ngày đầu = 1), `trang_thai_dong`; (b) vi sinh: `thoi_diem_lay_mau`, `benh_pham`, `vi_khuan`, `hoat_chat`, `ket_qua` (S/I/R), `mic` — một dòng mỗi kết quả kháng sinh đồ; mẫu không có kháng sinh đồ vẫn có một dòng với `hoat_chat`/`ket_qua` null. **Mốc tham chiếu của ca**: dùng mốc mà các luật hiện dùng (tìm trong `app/rules`/`app/pipeline`), không dùng giờ máy.
  - **`moc_ca`**: `thoi_diem`, `loai` (`vao_vien|y_lenh|xet_nghiem|vi_sinh|dien_bien`), `nhan` (≤ 80 ký tự: tên thuốc, mã xét nghiệm, loại hồ sơ). **Không** đưa `noi_dung` diễn biến, chẩn đoán tự do, hay ghi chú bác sĩ vào bộ dữ liệu.
- Đăng ký trong `registry`, `config/tool_policy.yaml` (cho `duoc_si_ls` và `admin`, **chỉ chế độ ca**), tính vào trần lời gọi tool của lượt. Span tracer: `phan`, số dòng mỗi bộ, có cắt hay không; không ghi giá trị.

### 2. Dấu dòng thời gian `doan` (ngữ pháp `mh-1`, máy chủ + web)

- Thêm dấu `doan`: đoạn ngang trên một làn. Kênh: `x_tu`, `x_den` (thoi_gian hoặc dinh_luong), `y` (danh_muc = làn), tuỳ chọn `mau`, `nhan`. Thiếu `x_den` (null trong dữ liệu) thì vẽ tới hết miền trục x và có mũi tên/nét "đang dùng".
- `diem` trên trục thời gian dùng làm **mốc** (V6 vi sinh, V8 mốc ca): kiểm `x` kiểu thoi_gian được.
- `quy_tac` dọc theo thời gian (mốc kê y lệnh trên V3) lấy giá trị từ ô, như quy tắc hiện có.
- Cập nhật **đồng thời** bộ kiểm máy chủ (`app/agent/minh_hoa/kiem.py`) và web (`nguPhap.ts`): cùng khoá, cùng ràng buộc. Có test chứng minh hai bên cùng nhận/cùng từ chối trên một tập đặc tả mẫu (ví dụ tệp JSON dùng chung trong `tests/fixtures/minh_hoa/` đọc từ cả pytest và vitest, nếu kho chưa có cách khác).
- Web (`dungMoHinh.ts`, `KhungMinhHoa.tsx`): trục x thời gian (nhãn ngày/giờ theo `vi-VN`, múi giờ Asia/Ho_Chi_Minh), vẽ `doan`, chú giải không chỉ bằng màu (nhãn làn + nét). "Xem dạng bảng" vẫn hiện đúng số. Không `innerHTML`, không gói mới. Nếu trục thời gian cho `duong` đã có thì dùng lại.

### 3. Kỹ năng prompt

Sửa `config/prompts/ky_nang_minh_hoa.v1.md` (giữ ≤ 1.500 từ; nếu kho có quy ước tăng phiên bản thì theo): khi câu hỏi về **diễn tiến, thời điểm, thứ tự trước/sau, ngày thứ mấy, tổng liều trong ngày** ở chế độ ca thì gọi `lay_du_lieu_ca` với đúng `phan` cần, rồi chọn dấu: xu hướng xét nghiệm/sinh hiệu → `duong` (+ `quy_tac` mốc kê y lệnh, + `diem` tô các dòng `ngoai_nguong`/`creatinin_tang_nhanh`); tổng liều 24 giờ → `cot` + `quy_tac` liều tối đa lấy từ ô `lieu_toi_da_ngay`; lịch theo giờ → `diem` theo thời gian, làn = hoạt chất; kháng sinh → `doan` + `diem` vi sinh; dòng thời gian ca → `diem` theo làn `loai`. Thêm **2 ví dụ đặc tả hoàn chỉnh** (V3 creatinin có mốc y lệnh; V6 kháng sinh + vi sinh). Câu một con số (ví dụ "creatinin hôm nay bao nhiêu?") thì **không vẽ**.

## Test

- `tests/agent/test_tool_lay_du_lieu_ca.py`:
  - DEMO-02 (`data/mock/demo/DEMO-02.json`): bộ `xet_nghiem` creatinin có đúng số dòng và giá trị như tệp; `ngoai_nguong` và `creatinin_tang_nhanh` khớp tính tay trong test (độc lập, không gọi hàm của tool).
  - Ca dựng trong test có paracetamol từ **3 chế phẩm**, tổng 6 g/24 giờ: `tong_24h_lon_nhat` = 6.000 mg, `lieu_toi_da_ngay` = giá trị trong `lieu_toi_da.json`, `vuot` = true, `so_che_pham` = 3; một trường hợp liều rải qua ranh giới ngày (cửa sổ trượt khác tổng theo ngày lịch) để chứng minh dùng cửa sổ trượt.
  - Kháng sinh: `ngay_thu` đúng theo mốc tham chiếu (ngày đầu = 1); vi sinh có và không có kháng sinh đồ.
  - `moc_ca`: không có chuỗi nào lấy từ `dien_bien.noi_dung` hay `chan_doan.noi_dung` (canary: đặt chuỗi lạ vào đó, khẳng định không xuất hiện trong bộ dữ liệu, văn bản tool và khối hình).
  - Canary PII: họ tên/SĐT đặt trong `ten_tu_do` của một dòng thuốc → bị che ở bộ dữ liệu.
  - Chế độ chung → `tu_choi`; tham số `ca_id` → bị từ chối (`extra="forbid"`); `phan` lạ, trùng, rỗng → từ chối; `ma_xet_nghiem` có ký tự lạ (`'; drop`, `<`) → từ chối.
  - Trần 2.000 dòng: bộ 2.500 dòng giữ 2.000 dòng mới nhất, span ghi bị cắt.
- `tests/agent/test_minh_hoa_kiem.py` (bổ sung): `doan` hợp lệ; `doan` thiếu `y`, `x_tu` sai kiểu, `y` kiểu dinh_luong → từ chối.
- Đồ thị agent với LLM giả: `lay_du_lieu_ca(phan=[xet_nghiem])` → `ve_bieu_do` (`duong` + `quy_tac`) → trả lời qua kiểm chứng → `TraLoi.minh_hoa` có 1 khối, số trong khối khớp bộ dữ liệu.
- Web (vitest): `nguPhap` nhận/từ chối giống máy chủ trên tập đặc tả dùng chung; `KhungMinhHoa` render `doan` với trục thời gian (có đoạn đang dùng), "Xem dạng bảng" khớp số.

## Tệp

Được tạo/sửa: `app/agent/tools/**` (thêm `lay_du_lieu_ca.py`), `app/agent/minh_hoa/**`, `app/agent/nodes.py`/`state.py` (chỉ nếu cần truyền ca vào tool), `app/tracing/models.py` (chỉ thêm khoá thuộc tính span cho phép), `config/tool_policy.yaml`, `config/prompts/ky_nang_minh_hoa.v1.md`, `web/src/features/minh-hoa/**`, `tests/agent/**`, `tests/fixtures/minh_hoa/**` (mới), `web/src/features/minh-hoa/__tests__/**`. Báo cáo: `plan/briefs/VZ2-bao-cao.md`.

**Cấm:** `app/eval/**`, `data/gold/**`, `tests/eval/**` (đợt VZ5 đang làm song song ở đó); `data/**` khác; `.env*`; `plan/**` (trừ báo cáo); đổi logic kiểm chứng số trong `app/verify`; đổi luật D1–D7; cài gói; mạng; commit. Ghi tệp bằng apply_patch (giữ UTF-8), không ghi bằng PowerShell `Set-Content`/`Out-File`/`>`.

**RAM:** máy dev ít RAM. Chỉ chạy test liên quan **từng tệp một** (`tests/agent/test_tool_lay_du_lieu_ca.py`, `test_minh_hoa_kiem.py`, `test_tool_ve_bieu_do.py`, `test_minh_hoa_do_thi.py`, `tests/tracing`), và vitest chỉ thư mục `web/src/features/minh-hoa`. Thư mục tạm pytest đặt trong `%TEMP%` (`--basetemp`).

## Nghiệm thu (Claude chạy)

```
uv run ruff check app tests && uv run ruff format --check app tests/agent
uv run pytest -q -p no:cacheprovider tests/agent tests/orchestration tests/tracing tests/api
cd web && npx tsc -b --noEmit && npx oxlint && npx vitest run && npx vite build
```

Claude kiểm độc lập trên 5173 với API thật, engine `agentic`:
- DEMO-02 "Creatinin của người bệnh diễn tiến thế nào, CrCl hôm nay còn tin được không?" → hình đường creatinin có mốc kê y lệnh; số trên hình khớp tệp ca.
- HS-019 "Paracetamol có vượt liều tối đa trong 24 giờ không, giờ nào dồn liều?" → hình tổng liều có đường liều tối đa; tổng khớp tự tính.
- một ca có kháng sinh + vi sinh "Kháng sinh đang dùng ngày thứ mấy, có kháng sinh đồ chưa?" → dòng thời gian kháng sinh.
- "Creatinin hôm nay bao nhiêu?" → **không** có hình.
- Quét khối hình: không có họ tên, mã người bệnh, nội dung diễn biến.

## Lượt 2 (27/11) – làm tiếp, không làm lại

Lượt 1 dừng sớm (báo cáo `plan/briefs/VZ2-bao-cao.md`): **đã có** dấu `doan` ở `kiem.py` + `nguPhap.ts`, bộ dựng SVG, trục thời gian, `tests/fixtures/minh_hoa/doan.json`. **Còn thiếu, làm hết trong lượt này:** yêu cầu 1 (tool `lay_du_lieu_ca` đủ 5 phần, đăng ký registry, `tool_policy.yaml`, Gateway: mã `ds-n`, che PII, cắt 2.000 dòng mới nhất, span), yêu cầu 3 (kỹ năng prompt + 2 ví dụ), toàn bộ mục Test còn thiếu (`test_tool_lay_du_lieu_ca.py`, đồ thị agent LLM giả, vitest render `KhungMinhHoa` với `doan` và "Xem dạng bảng").

- Không dừng giữa chừng để hỏi: chọn phương án hợp lý, ghi vào báo cáo.
- Lịch suy từ tần suất: chỉ dùng cho **tổng 24 giờ** (khi không có `lich_dung`, tổng ngày = `lieu_moi_lan × so_lan_moi_ngay`, ghi `nguon_lich=suy_tu_tan_suat`); **không** sinh giờ dùng giả cho bộ từng liều.
- `ruff format --check` báo `app/eval/hoi_dap.py`: bỏ qua, đó là tệp của agent khác.
- Ghi đè `plan/briefs/VZ2-bao-cao.md`, đối chiếu từng yêu cầu 1–3 và từng test: đạt / thiếu.

## Lượt 3 (27/11) – CHỈ làm yêu cầu 1 và test của nó

Hai lượt trước **chưa viết dòng nào** của tool `lay_du_lieu_ca`. Lượt này chỉ có một mục tiêu: tool chạy được, có test. Không sửa thêm web hay `doan` (đã xong).

- **Được sửa thêm `app/container.py`** (chỉ thêm một dòng import và `danh_muc.dang_ky(LayDuLieuCa())` cạnh `TraTuongTac`, `VeBieuDo` ở khoảng dòng 308–332).
- Làm theo đúng khuôn `app/agent/tools/tinh_chi_so.py`: lớp kế thừa như các tool khác, `che_do_cho_phep = frozenset({"ca"})`, lấy ca từ `ctx.ca` (None → `trang_thai="loi"`, `ma_loi="sai_tham_so"`), trả `KetQuaCongCu` có `bo_du_lieu` như `tra_tuong_tac.py`. Gateway hiện có đã đánh mã `ds-n`, che PII, tóm tắt: dùng lại; chỉ thêm việc **cắt giữ 2.000 dòng mới nhất** nếu Gateway đang bỏ cả bộ khi vượt trần (tool tự cắt trước khi trả cũng được, ghi số dòng bị cắt vào thuộc tính span).
- Thêm tool vào `config/tool_policy.yaml` giống `tinh_chi_so` (chế độ ca, `duoc_si_ls` + `admin`).
- Viết `tests/agent/test_tool_lay_du_lieu_ca.py` đủ các ý ở mục Test (DEMO-02, paracetamol 3 chế phẩm 6 g cửa sổ trượt, kháng sinh `ngay_thu`, vi sinh, canary `dien_bien`/`ten_tu_do`, chế độ chung, `extra="forbid"`, tham số lạ, trần 2.000) và test đồ thị agent LLM giả `lay_du_lieu_ca` → `ve_bieu_do` → `TraLoi.minh_hoa` 1 khối.
- Yêu cầu 3 (kỹ năng prompt): làm **sau cùng**, nếu còn thời gian; nếu không, ghi rõ "chưa làm" trong báo cáo.
- Không dừng để hỏi. Thiếu dữ kiện thì chọn phương án an toàn, ghi vào báo cáo.
