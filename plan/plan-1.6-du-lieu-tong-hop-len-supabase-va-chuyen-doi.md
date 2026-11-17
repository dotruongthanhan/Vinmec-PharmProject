# Plan 1.6 – Dữ liệu: tổng hợp, đưa lên Supabase và chuyển ứng dụng từ tệp mock sang CSDL

Phiên bản 1 · 18/11/2026 · Người viết: Claude (theo thảo luận với chủ kho)

**Quan hệ với các plan khác.** Plan 1.3 nói dữ liệu đi từ nguồn tới kho tri thức như thế nào (4 tầng, chuẩn hoá, gộp nguồn). Plan 1.1 mục 10 là lược đồ `tri_thuc` / `nghiep_vu`. Plan 1.5 là bảo mật (người dùng, vai trò). **Plan này gom ba việc còn thiếu:** (1) bản đồ toàn bộ dữ liệu hiện có và bảng theo dõi, (2) quy trình đưa dữ liệu lên Supabase và giữ cho nó đúng, (3) lộ trình đổi ứng dụng từ đọc tệp mock sang đọc Supabase, **không phá bản demo 20/11**.

## 1. Câu hỏi gốc và kết luận ngắn

> "Giao diện đang hiện 6 y lệnh mock. Muốn không còn mock thì cần nạp y lệnh mới vào DB? DB hiện có chứa mock không?"

Kiểm ngày 18/11/2026:

- Ứng dụng đọc ca bệnh từ **tệp JSON** `data/mock/demo` (`config/settings.yaml`, `case_dir`), nằm trong Docker image trên EC2. **Không đọc Supabase.**
- Supabase **có** bản chép của đúng 6 ca giả lập đó, cùng toàn bộ kho tri thức. Nhưng **không có chỗ nào trong ứng dụng đọc nó** (T14 chỉ làm lược đồ và lệnh nạp).
- Vì vậy chỉ nạp thêm ca vào DB **không làm giao diện đổi**. Phải làm cả hai: (a) dạy ứng dụng đọc từ DB, (b) có dữ liệu ca mới để đọc. Cả hai nằm trong plan này.
- "Mock" ở đây là **đúng thiết kế**: CLAUDE.md quy định dữ liệu 100% giả lập. Chuyển sang Supabase **không có nghĩa là dùng dữ liệu người bệnh thật**; điều đó cần cổng riêng (mục 9).

## 2. Hiện trạng dữ liệu (18/11/2026)

Số liệu đếm trực tiếp trong Supabase (chỉ đọc) và đối chiếu với tệp cục bộ.

### 2.1 Dữ liệu ca (loại C, giả lập)

| Bảng `nghiep_vu` | Số dòng | Ghi chú |
| :--- | :-: | :--- |
| `nguoi_benh`, `dot_dieu_tri`, `y_lenh`, `chi_tiet_y_lenh`, `thuoc`, `chan_doan`, `dien_bien`, `lan_tham_dinh` | 6 mỗi bảng | Đúng 6 ca DEMO-01…06 |
| `thuoc_hoat_chat` | 7 | |
| `ket_qua_xet_nghiem` | 9 | |
| `sinh_hieu` | 13 | |
| `lich_dung` | 13 | |
| `di_ung`, `vi_sinh`, `khang_sinh_do` | 1 mỗi bảng | |
| `nhan_dinh`, `nhan_dinh_thuoc` | 5 | Từ đáp án mẫu |
| `can_cu` | 0 | Chưa nạp |
| `phan_hoi` | 0 | Phản hồi thật đang nằm ở `data/runtime/phan_hoi.jsonl` trên EC2, **không** ở DB |

### 2.2 Kho tri thức (loại A và B)

| Bảng `tri_thuc` | Số dòng | Ghi chú |
| :--- | :-: | :--- |
| `tai_lieu` | 50 | 50 nhãn openFDA |
| `doan_trich` | 3.730 | **Chưa có véc-tơ**: cột `embedding` có 0/3.730 giá trị. Truy xuất lúc chạy dùng tệp cục bộ `data/kb_curated/chunks.jsonl` (cũng 3.730 dòng) và bộ đệm nhúng |
| `hoat_chat` | 61 | |
| `ten_thuoc` | 187 | |
| `quy_tac_lieu_than` | 4 | Luật chỉnh liều thận chạy bằng tệp `data/kb/quy_tac_lieu_than.json`, không đọc từ DB |
| `tuong_tac_sang_loc` | 234.981 | DDInter, chỉ sàng lọc, giấy phép phi thương mại |

Dung lượng cơ sở dữ liệu: **128 MB** (gói miễn phí giới hạn 500 MB; véc-tơ 3.730 × 2.048 chiều ở dạng `halfvec` cộng chỉ mục HNSW sẽ thêm khoảng vài chục MB, cần đo lại sau khi nạp).

### 2.3 Dữ liệu sinh ra lúc chạy (không phải dữ liệu nguồn)

| Dữ liệu | Hiện ở đâu | Đích |
| :--- | :--- | :--- |
| Phản hồi của dược sĩ | `data/runtime/phan_hoi.jsonl` (volume Docker trên EC2) | `nghiep_vu.phan_hoi` (bảng đã có, **thiếu** cột `nguoi_dung_id`, `phien_id` của plan 1.5) |
| Nhật ký hỏi đáp | `data/runtime/hoi_thoai.jsonl` | Bảng mới `nghiep_vu.hoi_thoai` (chưa có) |
| Kết quả bước AI nền | Bộ nhớ tiến trình, mất khi khởi động lại | Bảng `lan_tham_dinh`, `nhan_dinh`, `can_cu` (đã có, chưa dùng) |

### 2.4 Khoảng trống cần đóng

1. Ứng dụng **chưa có lớp đọc SQL**. Giao diện `CaseRepository` đã có ở `app/core/interfaces.py`, bản `JsonCaseRepository` có ở `app/storage/case_repo.py`, nhưng `CaseService` đọc tệp trực tiếp, chưa đi qua giao diện đó.
2. Véc-tơ chưa nạp; luật liều thận chưa đọc từ DB.
3. Runtime chưa có chỗ ở trong DB.
4. Chưa có quy trình sao lưu, khôi phục, và chưa có cách phân biệt dữ liệu giả lập với thật.

## 3. Các quyết định

| Mã | Quyết định | Lý do |
| :-: | :--- | :--- |
| Q-D1 | **Trước demo 20/11, ứng dụng vẫn đọc tệp mock.** Không chuyển nguồn dữ liệu trước đóng băng trưa 19/11 | Mục 9.1 của plan 1: lát cắt dọc trước, không đổi móng sát hạn. Demo đang chạy được |
| Q-D2 | Chuyển theo **cờ cấu hình** `DATA_BACKEND` = `files` hoặc `sql` (mặc định `files` cho tới khi nghiệm thu), có thể quay về ngay bằng cách đổi cờ | Đường lui rẻ nhất |
| Q-D3 | Tệp trong kho (`data/mock/`, `data/gold/`, `data/kb_curated/`) vẫn là **nguồn gốc**; Supabase là **bản phát hành** dựng lại được bằng lệnh. Không sửa tay dữ liệu trong DB | Nguyên tắc 1 của plan 1.3: tầng sau luôn dựng lại được từ tầng trước |
| Q-D4 | Ứng dụng chỉ **đọc** dữ liệu ca và tri thức từ DB; chỉ **ghi** vào bảng runtime (`phan_hoi`, `hoi_thoai`, `lan_tham_dinh`…) | Tách rõ dữ liệu phát hành (lệnh nạp ghi) với dữ liệu phát sinh (ứng dụng ghi) |
| Q-D5 | Chuyển từng lớp, từng bước nghiệm thu bằng **so sánh kết quả hai đường** (tệp và SQL) trước khi đổi mặc định | Phát hiện lệch dữ liệu bằng máy, không bằng mắt |
| Q-D6 | **Không mở dữ liệu cho API công khai của Supabase.** Mọi bảng đã bật RLS không có chính sách nào; chỉ backend kết nối bằng `DATABASE_URL` (vai `postgres` qua session pooler) | Trình duyệt chỉ cầm khoá `anon`; khoá này không được đọc dữ liệu ca |
| Q-D7 | **Dữ liệu giả lập luôn đánh dấu được**: mã ca có tiền tố `DEMO-` và (khi chuyển sang SQL) cột `la_gia_lap` bắt buộc `true`. Bộ nạp mặc định **từ chối** ca không phải giả lập | Không để dữ liệu thật lẫn vào kho giả lập, và ngược lại |
| Q-D8 | Dữ liệu người bệnh thật **chưa được phép** vào kho, vào prompt, vào log. Mở ra chỉ khi qua cổng ở mục 9 | CLAUDE.md mục 6 và 8 |
| Q-D9 | Sao lưu có trước, đổi sau: không chạy `reset` trên Supabase nếu chưa có bản sao lưu mới nhất | Lệnh `reset` xoá sạch hai lược đồ |
| Q-D10 | Luật và truy xuất đọc tri thức từ DB **sau** khi dữ liệu ca đã ổn (thứ tự mục 6) | Rủi ro thấp trước, cao sau |

## 4. Bản đồ dữ liệu: từ nguồn đến Supabase

```text
data/kb_sources/            TẦNG 0 gốc: 50 nhãn openFDA, DDInter (không sửa)
      │  python -m app.kb.fetch / normalize / curate / build       (plan 1.3)
data/kb_curated/            TẦNG 2: chunks.jsonl 3.730 đoạn, bảng có cấu trúc
data/kb/quy_tac_lieu_than.json
data/mock/demo/*.json       CA GIẢ LẬP: 6 ca (mục tiêu 20–30)
data/gold/                  ĐÁP ÁN mẫu của dược sĩ (không nạp vào DB phục vụ chạy)
      │  python -m app.db load {cases|kb|ddinter|embeddings}   (T14, có sẵn)
Supabase PostgreSQL
  ├─ tri_thuc  : tai_lieu, doan_trich(+véc-tơ), hoat_chat, ten_thuoc,
  │              quy_tac_lieu_than, tuong_tac_sang_loc
  └─ nghiep_vu : nguoi_benh … y_lenh … (ca), + runtime (phan_hoi, hoi_thoai,
                 lan_tham_dinh, nhan_dinh, can_cu)
```

Mỗi hàng của bảng theo dõi ở mục 11 ứng với một mũi tên của sơ đồ này.

## 5. Quy trình tổng hợp và cập nhật dữ liệu

### 5.1 Thêm hoặc sửa ca giả lập

1. Viết ca mới ở `data/mock/demo/DEMO-xx.json` theo mô hình `app/domain/models.py`. Mã ca bắt đầu bằng `DEMO-`.
2. Viết **đáp án trước** ở `data/gold/` (plan 1.3 mục 8); dược sĩ duyệt (Q3).
3. `uv run pytest tests/domain` kiểm mô hình và bộ nạp.
4. `python -m app.db all --dry-run` xem số dòng sẽ nạp và các dòng bị loại (có lý do).
5. Nạp: `python -m app.db load cases --replace` (chỉ thay nhóm ca, giữ nguyên kho tri thức).
6. `python -m app.db verify` so số dòng trong DB với tệp.
7. Ghi vào bảng theo dõi.

Thuốc trong ca phải nằm trong danh mục đã có nguồn (plan 1.3 mục 8): ca mới và kho tri thức mở rộng cùng nhau.

### 5.2 Mở rộng kho tri thức

Theo plan 1.3: nguồn mới → tầng 0 (manifest) → chuẩn hoá → tổng hợp → cổng chất lượng Q1–Q10 → `build` → nạp. Phiên bản kho (`phien_ban_kho`) tăng mỗi lần phát hành.

### 5.3 Luật cứng của bộ nạp

- Mọi lệnh nạp **idempotent** (chạy lại không nhân đôi dòng); dùng upsert theo khoá.
- Dòng sai không biến mất âm thầm: ghi vào báo cáo kèm lý do; vượt ngưỡng loại thì dừng.
- Nạp thật chỉ do chủ kho hoặc Claude chạy theo yêu cầu, **không** để agent code chạy nạp thật (agent chỉ chạy `--dry-run` và `check`), theo quy ước từ T14.
- Không in `DATABASE_URL` hay bất kỳ phần nào của chuỗi kết nối.

## 6. Đưa dữ liệu lên Supabase

### 6.1 Việc còn thiếu so với T14

| # | Việc | Chi tiết |
| :-: | :--- | :--- |
| U1 | **Nạp véc-tơ** cho 3.730 đoạn | `python -m app.db load embeddings`; cần bộ đệm nhúng đủ 3.730 (hiện mới 134 trong lần kiểm trước; nhúng lại các đoạn mới sau T25) qua OpenRouter, tốn tiền nhỏ, cần khoá |
| U2 | **Bảng runtime** | Thêm `nguoi_dung_id`, `phien_id` cho `phan_hoi`; tạo `hoi_thoai`; khoá ngoại tới người dùng Supabase **không** tạo (người dùng ở `auth.users`, lược đồ khác): chỉ lưu `uuid` |
| U3 | **Di chuyển dữ liệu runtime cũ** | Đọc `phan_hoi.jsonl` và `hoi_thoai.jsonl` trên EC2 rồi nạp vào DB, dòng cũ không có chủ (plan 1.5 mục 3.3) |
| U4 | **Bảng `la_gia_lap`** (Q-D7) | Thêm cột có ràng buộc; bộ nạp từ chối ca không có tiền tố `DEMO-` |
| U5 | **Kiểm dung lượng sau khi nạp véc-tơ** | Phải còn dưới 70% hạn mức gói miễn phí; nếu vượt thì giảm chiều hoặc nâng gói |

### 6.2 Kiểm sau mỗi lần nạp

`python -m app.db verify` phải báo khớp số dòng từng bảng. Thêm hai kiểm:

1. **Băm đối chiếu:** với mỗi ca, tính băm chuẩn hoá của dữ liệu đọc từ tệp và từ DB; hai băm phải bằng nhau.
2. **Truy xuất mẫu:** với 5 câu hỏi vàng, kết quả top-k từ pgvector trùng ít nhất 4/5 với kết quả đang chạy bằng bộ nhớ.

### 6.3 Quyền truy cập

- Backend dùng `DATABASE_URL` (session pooler). Tài khoản kết nối chỉ nằm trong `.env` trên EC2 (quyền tệp `600`), không trong image, không trong git.
- Bảng đã bật RLS, không chính sách. Không thêm chính sách cho vai `anon` hay `authenticated` trên hai lược đồ này.
- Hai lược đồ `nghiep_vu`, `tri_thuc` **không được** thêm vào danh sách *Exposed schemas* của Data API.
- Trước khi có người dùng thật: tạo vai riêng cho ứng dụng (chỉ `SELECT` trên `tri_thuc`; `SELECT` trên ca; `INSERT/SELECT` trên bảng runtime), thay cho vai `postgres`.

## 7. Chuyển ứng dụng từ tệp mock sang Supabase

### 7.1 Đích kiến trúc

```text
        CaseService / luật / truy xuất / bước AI
                      │  chỉ biết các giao diện
        ┌─────────────┼───────────────────────────┐
  CaseRepository   KnowledgeRepository      RuntimeRepository
  (ca bệnh)        (quy tắc liều, tương tác,  (phản hồi, hội thoại,
                    đoạn trích + VectorStore)   kết quả AI)
        │                  │                       │
  Json…  │  Sql…     Json…/Memory │ Pg…        Jsonl │ Sql…
        └─────── chọn theo DATA_BACKEND ───────────────┘
```

`CaseRepository` và `VectorStore` đã có trong `app/core/interfaces.py`. Cần thêm `KnowledgeRepository` (quy tắc liều thận, tương tác sàng lọc) và `RuntimeRepository`. `CaseService` phải nhận chúng qua hàm dựng thay vì tự đọc tệp.

### 7.2 Các đợt chuyển

| Đợt | Nội dung | Điều kiện qua đợt | Khi nào |
| :-: | :--- | :--- | :-: |
| M0 | **Hiện tại.** Đọc tệp; DB là bản chép chưa dùng | — | Đang là thế |
| M1 | Rút lớp đọc ca thành `CaseRepository` dùng được cho cả hai. `CaseService` đi qua nó. Viết `SqlCaseRepository` (đọc 14 bảng ca, dựng lại `CaBenh`). Cờ `DATA_BACKEND` | **So sánh hai đường:** với 6 ca, `CaBenh` đọc từ tệp và từ SQL bằng nhau từng trường; kết quả `run_rules` giống hệt (so JSON chuẩn hoá). Toàn bộ test hiện có qua cả với `files` | Sau demo |
| M2 | Tri thức đọc từ DB: `quy_tac_lieu_than` và `tuong_tac_sang_loc` qua `KnowledgeRepository`; truy xuất qua `PgVectorStore` + chỉ mục từ khoá trong DB. Nạp véc-tơ (U1) | 5 câu hỏi vàng cho top-k trùng ≥ 4/5; thời gian truy xuất không tệ hơn 1,5 lần bản bộ nhớ; 6 ca cho cùng nhận định luật | Sau M1 |
| M3 | Ghi runtime vào DB: phản hồi, hội thoại, kết quả AI (cần plan 1.5 đã xong để có `nguoi_dung_id`) | Test sở hữu của plan 1.5 mục 7.3 vẫn qua; dữ liệu cũ đã di chuyển (U3); khởi động lại tiến trình không mất kết quả AI | Sau M2 |
| M4 | **Đổi mặc định** sang `sql` ở EC2; giữ `files` làm đường lui trong 2 tuần | Chạy thật 3 ngày không lỗi; so sánh định kỳ vẫn khớp | Sau M3 |
| M5 | Đường nạp dữ liệu thật (có cổng che định danh, phê duyệt, nhật ký truy cập) | Mục 9 đủ điều kiện | Chỉ khi được phép |

Mỗi đợt là một task giao cho agent (mục 11), có brief riêng, và **review bằng chạy hai đường**.

### 7.3 Đường lui

- Đặt `DATA_BACKEND=files` rồi khởi động lại container: về ngay trạng thái hiện tại, không cần dựng lại image (tệp mock vẫn nằm trong image đến hết M4).
- Dữ liệu runtime ghi vào DB ở M3 vẫn đọc được từ DB; khi quay về `files`, phần runtime mới phát sinh trong thời gian ở `sql` sẽ không hiện ở giao diện. Cần ghi rõ trong ghi chú vận hành và xuất ra JSONL trước khi quay về.

### 7.4 Hiệu năng và kết nối

- EC2 và Supabase phải **cùng khu vực** (hiện EC2 ở `ap-southeast-1`). Chủ kho kiểm khu vực dự án Supabase; nếu khác khu vực, đo độ trễ truy vấn thật trước M1. Đặt mục tiêu: đọc một ca dưới 100 ms.
- Dùng **session pooler** (đã dùng) hoặc transaction pooler; một tiến trình `uvicorn`, hạn mức kết nối nhỏ (2–5).
- Danh sách ca và chi tiết ca đệm trong bộ nhớ tiến trình vài giây; dữ liệu giả lập ít đổi.

## 8. Dữ liệu sinh ra lúc chạy

Quy ước bổ sung cho plan 1.5:

| Bảng | Khoá | Cột chính |
| :--- | :--- | :--- |
| `nghiep_vu.phan_hoi` (đã có) | id tự tăng | thêm `nguoi_dung_id uuid`, `phien_id uuid null`, `vai_tro text` |
| `nghiep_vu.hoi_thoai` (mới) | id tự tăng | `nguoi_dung_id uuid`, `phien_id uuid null`, `ca_id text`, `cau_hoi text` (đã che định danh), `tra_loi jsonb`, `thoi_diem timestamptz` |
| `nghiep_vu.lan_tham_dinh`, `nhan_dinh`, `can_cu` (đã có) | | Kết quả bước AI nền, kèm `phien_ban_kho`, `phien_ai` |

Chỉ mục: (`nguoi_dung_id`, `ca_id`, `thoi_diem`) cho hội thoại. Không lưu câu hỏi chưa qua cổng che định danh. Thời hạn lưu hội thoại: chốt với Khoa Dược; tạm 90 ngày, có lệnh xoá.

## 9. Cổng trước khi có dữ liệu người bệnh thật (chưa mở)

Dữ liệu sức khoẻ là dữ liệu nhạy cảm theo Nghị định 13/2023/NĐ-CP. **Không** nạp dữ liệu thật cho tới khi đủ **tất cả**:

1. Văn bản đồng ý của Khoa Dược và bộ phận công nghệ thông tin / pháp chế của viện về nơi lưu (Supabase nước ngoài hay hạ tầng của viện) và mục đích sử dụng.
2. Đánh giá tác động xử lý dữ liệu cá nhân nếu viện yêu cầu.
3. Cổng che định danh (T08) được đánh giá lại trên dữ liệu thật, không chỉ test giả lập.
4. Plan 1.5 xong, kèm xác thực hai bước cho `admin`, nhật ký truy cập, giới hạn tốc độ.
5. Gói Supabase trả phí (sao lưu theo ngày, không tự tạm dừng) hoặc chuyển sang hạ tầng của viện; mã hoá và vai riêng cho ứng dụng.
6. Quy tắc lưu và xoá (mục 8) được duyệt.
7. Cổng nạp (M5) bắt buộc cờ rõ ràng, ghi nhật ký người nạp, và không dùng chung bảng với ca giả lập (đánh dấu bằng `la_gia_lap = false` và vai trò nạp riêng).

Nếu viện yêu cầu dữ liệu nằm trong hạ tầng của họ thì Supabase chỉ giữ ca giả lập và kho tri thức; mô hình `Repository` ở mục 7 cho phép đổi nơi lưu mà không đổi luật.

## 10. Vận hành

| Việc | Cách làm | Khi nào |
| :--- | :--- | :-: |
| **Sao lưu** | `pg_dump` hai lược đồ qua session pooler, lưu ngoài kho git (ví dụ `D:\create\backups\supabase\<ngày>.sql.gz`, cạnh thư mục budget); chạy trước mỗi lần `reset` và mỗi tuần | Trước lần nạp tiếp theo |
| **Diễn tập khôi phục** | Khôi phục bản sao lưu vào một cơ sở dữ liệu thử, so số dòng | Một lần trước M4 |
| **Dự án Supabase gói miễn phí tự tạm dừng sau khoảng 7 ngày không hoạt động** | Gọi `check` định kỳ hoặc nâng gói trước demo; theo dõi thư báo từ Supabase | Trước 20/11 |
| **Dung lượng** | Giữ dưới 70% hạn mức; xem sau khi nạp véc-tơ | U5 |
| **Khoá và chuỗi kết nối** | Chỉ trong `.env`; xoay vòng mật khẩu CSDL nếu chuỗi từng lộ ra màn hình (T14 ghi nhận mật khẩu từng xuất hiện trong traceback) | Nên làm ngay |
| **Phiên bản kho và phiên bản dữ liệu ca** | Ghi `phien_ban_kho` và băm tệp ca vào bảng `lan_nap` (mới, một dòng mỗi lần nạp: ai, lúc nào, nhóm, số dòng, băm) | M1 |

## 11. Bảng theo dõi dữ liệu

Trạng thái: `xong` · `đang giao` · `chờ giao` · `chờ chủ kho` · `bị chặn` · `hoãn`. Cập nhật mỗi khi đổi; bản tóm tắt cũng ghi ở `plan/TRACKING.md`.

### 11.1 Tập dữ liệu

Cột "tệp" là số dòng tệp cục bộ, "DB" là số dòng đếm trong Supabase ngày 18/11/2026.

| Mã | Tập dữ liệu | Loại | Tầng | Tệp cục bộ | Bảng Supabase | Tệp | DB | Trạng thái | Ghi chú |
| :-: | :--- | :-: | :-: | :--- | :--- | :-: | :-: | :-: | :--- |
| D1 | Nhãn openFDA (50 hoạt chất) | A | 0→3 | `data/kb_sources/openfda/` | `tri_thuc.tai_lieu` | 50 | 50 | xong | Mở rộng theo `config/kb/hoat_chat_can_lay.yaml` |
| D2 | Đoạn trích nhãn | A | 2→3 | `data/kb_curated/chunks.jsonl` | `tri_thuc.doan_trich` | 3.730 | 3.730 | xong (chưa véc-tơ) | `over_max=0`, `under_50=0` |
| D3 | Véc-tơ nhúng (OpenRouter, 2.048 chiều) | A | 3 | bộ đệm nhúng | `doan_trich.embedding` | 3.730 | **0** | chờ giao (U1) | Cần khoá OpenRouter, đo dung lượng |
| D4 | Hoạt chất, tên thuốc | A | 1→3 | `data/kb_curated/` | `hoat_chat`, `ten_thuoc` | — | 61 / 187 | xong | Chuẩn hoá tên theo plan 1.3 mục 5 |
| D5 | Luật chỉnh liều thận (meropenem, 4 mức) | B | 2 | `data/kb/quy_tac_lieu_than.json` | `tri_thuc.quy_tac_lieu_than` | 4 | 4 | xong dữ liệu; **chưa đọc từ DB** | Dược sĩ chưa duyệt (Q3). Đã đối chiếu nhãn FDA 16/11 |
| D6 | Tương tác DDInter | B | 1→3 | `data/kb_sources/ddinter/` | `tri_thuc.tuong_tac_sang_loc` | 234.981 cặp | 234.981 | xong | Chỉ sàng lọc, phi thương mại; giấy phép chưa quyết (plan 1.3 mục 12.5) |
| D7 | Ca giả lập (6 ca) | C | — | `data/mock/demo/*.json` | 14 bảng `nghiep_vu` | 6 | 6 | xong; **chưa đọc từ DB** | Xem 2.1 |
| D8 | Đáp án mẫu | C | — | `data/gold/` | `nhan_dinh`, `nhan_dinh_thuoc` | — | 5 | xong | Không dùng để chạy, chỉ để chấm |
| D9 | Mở rộng ca lên 20–30 | C | — | `data/mock/demo/` | | 6 | 6 | chờ giao | Mục tiêu 18/11 trong mục 9.1 của plan 1 chưa đạt; cần dược sĩ duyệt đáp án |
| D10 | Phản hồi dược sĩ | runtime | — | `data/runtime/phan_hoi.jsonl` (EC2) | `nghiep_vu.phan_hoi` | ? | 0 | chờ giao (U2, U3, M3) | Cần cột người dùng (plan 1.5) |
| D11 | Nhật ký hỏi đáp | runtime | — | `data/runtime/hoi_thoai.jsonl` (EC2) | `nghiep_vu.hoi_thoai` | ? | bảng chưa có | chờ giao (U2, U3, M3) | |
| D12 | Kết quả bước AI nền | runtime | — | bộ nhớ tiến trình | `lan_tham_dinh`, `nhan_dinh`, `can_cu` | — | 0 (`can_cu`) | chờ giao (M3) | Mất khi khởi động lại |
| D13 | QĐ 5948/QĐ-BYT, Dược thư, danh mục thuốc viện | A, B | — | | | | | bị chặn | Chờ Khoa Dược (plan 1.3 mục 12) |
| D14 | Thực phẩm chức năng, LiverTox, LactMed | A | — | | | | | hoãn | Sau demo |

### 11.2 Việc cần làm

| Mã | Việc | Đợt | Giao cho | Trạng thái | Bằng chứng / ghi chú |
| :-: | :--- | :-: | :--- | :-: | :--- |
| T14 | Lược đồ + lệnh nạp (`python -m app.db`) | — | Codex xhigh | xong | 18/11: `check` đạt; đếm bảng khớp bảng 11.1 |
| T30 | M1: `CaseRepository` dùng chung, `SqlCaseRepository`, cờ `DATA_BACKEND`, kiểm so sánh hai đường, bảng `lan_nap` | M1 | Codex | chờ giao (sau demo) | Cần brief |
| T31 | U1, U4, U5: nạp véc-tơ, cột `la_gia_lap`, đo dung lượng | M1 | Claude (chạy nạp) + Codex (code) | chờ giao | Chờ khoá OpenRouter |
| T32 | M2: `KnowledgeRepository`, `PgVectorStore`, luật liều thận đọc từ DB | M2 | Codex | chờ giao | Phụ thuộc T30, T31 |
| T33 | U2, U3, M3: bảng runtime, di chuyển dữ liệu cũ, ghi runtime vào DB | M3 | Codex | chờ giao | Phụ thuộc plan 1.5 (T28) xong và T30 |
| T34 | Mở rộng ca giả lập 20–30, kèm đáp án viết trước | — | Agent + dược sĩ duyệt | chờ giao | Gắn với T09 của TRACKING |
| T35 | Sao lưu `pg_dump` + diễn tập khôi phục | — | Claude (lệnh) | chờ chủ kho | Cần chủ kho cho phép chạy `pg_dump` và chỗ lưu |
| T36 | M4: đổi mặc định sang `sql` trên EC2 | M4 | Claude + chủ kho | chờ | Sau T30–T33 |
| T37 | M5: đường nạp dữ liệu thật | M5 | — | bị chặn | Cổng mục 9 |
| V-1 | Xoay vòng mật khẩu CSDL Supabase (đã từng lộ trong traceback của T14); cập nhật `.env` trên máy và EC2 | — | Chủ kho | chờ chủ kho | Làm ngay, không phụ thuộc gì |
| V-2 | Kiểm khu vực dự án Supabase so với EC2 | — | Chủ kho | chờ chủ kho | Ảnh hưởng độ trễ (mục 7.4) |
| V-3 | Kiểm dự án Supabase còn hoạt động trước demo (gói miễn phí tự tạm dừng) | — | Chủ kho | chờ chủ kho | Có thể nâng gói trước demo |

### 11.3 Mốc

| Ngày | Mốc dữ liệu | Đạt? |
| :--- | :--- | :-: |
| 18/11 | 6 ca và kho tri thức đã nạp Supabase; plan 1.6 viết xong | đạt |
| 19/11 | Đóng băng trưa: **vẫn dùng tệp mock** (Q-D1); chỉ sửa lỗi | |
| 20/11 | Demo bằng dữ liệu giả lập đọc từ tệp | |
| Tuần sau demo | T30 (M1) rồi T31 | |
| Sau M3 | T36 đổi mặc định | |

## 12. Kiểm thử cho phần chuyển đổi

1. **Tương đương mô hình:** với mỗi ca, `JsonCaseRepository.get(id) == SqlCaseRepository.get(id)` (so `model_dump` chuẩn hoá).
2. **Tương đương luật:** `run_rules` trên hai đường cho cùng danh sách `PhatHien` (số lượng, mã luật, mức, căn cứ).
3. **Tương đương truy xuất:** 5 câu hỏi vàng, top-k trùng ≥ 4/5; con số và mã trích dẫn mở được qua `/api/cases/{id}/sources/...`.
4. **Bộ nạp:** idempotent (nạp hai lần giữ nguyên số dòng); loại ca không có tiền tố `DEMO-`; ca thiếu khoá ngoại bị loại có lý do.
5. **Đường lui:** đổi cờ về `files` thì toàn bộ test API cũ qua.
6. **Không lộ bí mật:** không có `DATABASE_URL` hay mật khẩu trong log, ngoại lệ, báo cáo nạp (có test hồi quy từ T14).
7. **Quyền:** khoá `anon` của dự án không đọc được bất kỳ bảng nào của hai lược đồ (Claude kiểm bằng một yêu cầu REST với khoá `anon` công khai: phải bị từ chối hoặc không thấy lược đồ).

## 13. Câu hỏi mở

| # | Câu hỏi | Ai trả lời | Chặn |
| :-: | :--- | :--- | :--- |
| P1 | Viện có yêu cầu dữ liệu thật phải nằm trong hạ tầng của viện không? | Khoa Dược, công nghệ thông tin viện | M5 |
| P2 | Thời hạn lưu hội thoại và phản hồi | Khoa Dược | T33 |
| P3 | Có đưa `data/kb_sources/ddinter/` (22 MB, phi thương mại) vào git không | Chủ kho | Bảng D6 |
| P4 | Khu vực dự án Supabase | Chủ kho | T30 (đo độ trễ) |
| P5 | Dược sĩ duyệt đáp án và luật liều thận (Q3) | Khoa Dược | D5, D9 |
