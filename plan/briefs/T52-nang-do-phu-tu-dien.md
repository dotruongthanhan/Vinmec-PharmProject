# T52 – Nâng độ phủ từ điển thuốc: quy tắc chắc chắn, ứng viên ngữ nghĩa (offline), hàng duyệt, bộ tra cuối

Mô hình: Codex `gpt-6.2-sol`, effort `high`. Chạy nền, không dừng để hỏi. Điểm chưa rõ thì chọn cách ít rủi ro nhất và ghi vào báo cáo, mục "Lựa chọn đã làm".

**Task này không có mạng.** Không gọi RxNav, OpenRouter hay Supabase. Mọi thứ cần gọi mạng phải có chế độ giả lập và chế độ `--dry-run`; Claude sẽ tự chạy phần thật sau khi review.

Đọc trước:
- `AGENTS.md`
- `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md`: mục 3.2 (đồng bộ, chống bản ghi ma), 4.1
- `plan/reports/T50.md`: cả mục "T50-fix-1 (sub Sonnet)"
- Mã T50: `app/kb/dictionary/**`, `app/kb/sources/rxnav.py`
- Giao diện nhúng sẵn có: `app/core/interfaces.py` (`Embedder`), `app/providers/cached_embedder.py`, `app/providers/fakes.py` (`HashEmbedder`), `app/providers/openrouter_embed.py`, `config/settings.yaml` mục `embedding`

## Bối cảnh (số liệu thật ngày 19/11)

- Từ điển T50 có 54.910 chế phẩm, trong đó **36.099 (65,7%) có đủ thành phần**. Phần chưa đủ:
  - 6.986 chế phẩm không tách được câu chữ.
  - 11.825 chế phẩm tách được nhưng có ít nhất một thành phần chưa nối vào trục.
- Hàng chờ (`data/kb_curated/tu_dien/cho_duyet.jsonl`) có **3.436 tên khác nhau / 21.755 lượt**. Phân bố dồn về đầu:

  | Số tên đầu | Phủ được |
  |--:|--:|
  | 100 | 39% |
  | 200 | 54% |
  | 500 | 74% |
  | 1.000 | 85% |

  1.763 tên chỉ gặp một lần.
- Tên gặp nhiều nhất trong hàng chờ:
  - Vitamin viết tắt: B6, B2, PP, B1, C, E, B5, B12, "Vitamin B6", "Vitamin D3".
  - Dược liệu: Cam thảo, Đương quy, Thục địa, Bạch truật, Đảng sâm, Xuyên khung…
  - Tên Việt bỏ chữ "e" cuối: Hydrochlorothiazid, Glibenclamid, Cinnarizin.
  - Chất cũ: Terpin hydrat.
- Claude đã tải sẵn **danh sách hoạt chất RxNorm** làm kho ứng viên: `data/kb_sources/rxnav/danh_muc/allconcepts_IN_PIN.json` (18.406 mục: 14.718 IN, 3.688 PIN; có `manifest.json`). Chỉ đọc.
- Người dùng chốt (19/11):
  - Tìm ngữ nghĩa chỉ chạy **offline**, sinh **ứng viên**.
  - Kết quả là một bảng tra. Chỉ dòng chắc chắn hoặc đã được người duyệt mới vào **bộ cuối**; bộ cuối sẽ được đẩy lên Supabase dưới dạng bảng thường.
  - Dòng chỉ có gợi ý ngữ nghĩa vào **hàng duyệt**, **không** vào bộ cuối.
  - Lúc thẩm định, app chỉ tra bảng.

## Rủi ro chính phải chặn: thuốc tên gần nhau

Ví dụ cefotaxim / ceftriaxon / cefuroxim / ceftazidim; hydroxyzin / hydralazin; clonidin / clonazepam. Ghép sai một cặp loại này làm thẩm định tra sai dị ứng và tương tác mà không ai thấy. **Mọi quy tắc tự nhận phải chứng minh bằng test là không ghép nhầm các cặp này.**

## Phạm vi file

**Được tạo / sửa:**
- `app/kb/dictionary/**`: mô-đun mới gợi ý `rules_extra.py`, `candidates.py`, `accept.py`, `review.py`, `publish.py`; sửa `axis.py` / `build` để dùng kết quả mới
- `config/kb/tu_dien.yaml` (mới: ngưỡng, cờ, bảng vitamin)
- `db/tu_dien.sql` (mới: DDL bảng của bộ cuối và hàng duyệt; **không chạy**)
- `tests/kb/test_dictionary_*.py`, `tests/kb/fixtures/tu_dien/**`
- Dữ liệu: `data/kb_curated/tu_dien/**` (dựng lại), `data/kb_reports/T52_*`, `data/cache/embeddings_tu_dien.sqlite` (chỉ khi chạy thật; task này không tạo)
- Báo cáo `plan/reports/T52.md`

**Cấm đụng:**
- `db/schema.sql`, `app/db/**`, `app/rules/**`, `app/api/**`, `app/llm/**`, `app/orchestration/**`, `web/**`
- `data/mock/**`, `data/kb/**`, `data/kb_sources/**` (chỉ đọc)
- Mã và dữ liệu DDInter (`app/kb/fetch/ddinter.py`, `app/kb/sources/ddinter_web.py`, `data/kb_*/ddinter*`)
- `config/settings.yaml` (chỉ đọc), `.env`, `pyproject.toml`, `uv.lock` (không thêm thư viện; so chuỗi bằng thư viện chuẩn)

## Yêu cầu

### 1. Quy tắc chắc chắn (chạy trước, không cần mạng)

1. **Thêm "e" cuối.**
   - Điều kiện: khoá chuẩn hoá kết thúc bằng phụ âm, và `khoa + "e"` **trùng khớp chính xác** một tên trong kho ứng viên (trục T50 + danh sách RxNorm).
   - Kết quả: ánh xạ, `cach_khop = "them_e_cuoi"`.
   - Nếu `khoa` (không thêm) cũng trùng một tên khác thì **không** áp dụng.
2. **Bảng vitamin** trong `config/kb/tu_dien.yaml`:
   - B1→thiamine, B2→riboflavin, B3 / PP→niacinamide (ghi rõ lựa chọn nicotinamide hay niacin theo cách RxNorm đặt tên), B5→pantothenic acid, B6→pyridoxine, B9→folic acid, B12→cyanocobalamin (ghi chú dạng hydroxocobalamin), C→ascorbic acid, D3→cholecalciferol, D2→ergocalciferol, E→tocopherol (ghi rõ dạng), K1→phytonadione.
   - Chỉ áp dụng khi tên đứng sau chữ "vitamin", **hoặc** chế phẩm có ít nhất hai thành phần đều là mã vitamin. "C" hay "E" đứng một mình trong chế phẩm khác thì **không** áp dụng.
   - `cach_khop = "bang_vitamin"`. Mọi mục trong bảng phải có `rxcui` lấy từ danh sách RxNorm đã tải. Mục nào không tìm thấy thì ghi báo cáo, không đoán.
3. **Dược liệu.**
   - Tên tiếng Việt không có dạng Latin khớp trong kho ứng viên, **và** chế phẩm đã được T50 gắn dấu hiệu dược liệu (hoặc có ≥ 3 thành phần đều là tên Việt không khớp) → `loai = "duoc_lieu"`, trạng thái `khong_co_du_lieu_tra`.
   - Không đưa vào hàng duyệt ưu tiên. Giao diện về sau sẽ hiện "dược liệu – không có dữ liệu tra", không phải "chưa kiểm".
   - Liệt kê 30 tên dược liệu nhiều nhất trong báo cáo.
4. **PIN → IN:** ứng viên là PIN (dạng muối) chỉ được nối về IN khi quan hệ đã có trong đệm RxNav của T50 (`data/kb_sources/rxnav/cache/`). Không có thì vào hàng duyệt.

### 2. Ứng viên ngữ nghĩa (offline, trong bộ nhớ)

- **Kho ứng viên:** 1.219 hoạt chất trên trục T50, cộng 18.406 mục RxNorm, cộng mọi `ten_viet` / đồng nghĩa đã có. Mỗi mục giữ `rxcui`, tên, `tty`.
- **Hai cách chấm điểm:**
  - (a) Nhúng qua giao diện `Embedder` có sẵn, bọc `CachedEmbedder` với tệp đệm riêng `data/cache/embeddings_tu_dien.sqlite`; mô hình lấy từ `settings.embedding.active`.
  - (b) Độ giống ký tự: Jaccard trigram trên khoá chuẩn hoá, cộng tỷ số độ dài; tự cài.
- Tính cosine trong bộ nhớ, không dùng cơ sở dữ liệu vector. Mỗi tên lấy **top 5** ứng viên, ghi đủ `diem_nhung`, `diem_ky_tu`, `diem_ket_hop`, `hang`.
- Cờ dòng lệnh `--embedder fake` (dùng `HashEmbedder`, cho test và chạy thử) và `--embedder that` (mặc định khi Claude chạy).
- Gọi nhúng **theo lô**, có đệm; chạy lại không gọi lại tên đã có.

### 3. Tự nhận (cực chặt) và chống thuốc tên gần nhau

- **Mặc định `tu_nhan_ngu_nghia: false`** trong `config/kb/tu_dien.yaml`. Khi tắt, mọi ứng viên ngữ nghĩa vào hàng duyệt.
- Khi bật, chỉ tự nhận nếu **đồng thời**:
  - Ứng viên hạng 1 vượt ngưỡng `nguong_nhung` và `nguong_ky_tu`.
  - Khoảng cách điểm với hạng 2 ≥ `chenh_toi_thieu`.
  - **Không** có ứng viên nào khác trong top 5 cùng tiền tố 4 ký tự (ví dụ `cefo`, `cefu`, `ceft`), hoặc cùng nhóm ATC mức 4 mà khác tên, nằm trong khoảng `chenh_toi_thieu`.
- **Lệnh hiệu chuẩn `calibrate`** dùng tập có nhãn sẵn là các tên đã khớp chắc chắn ở T50 (`ma_chuan`, `bang_viet_quoc_te`, `rxnav_chinh_xac`; ~1.700 tên):
  - Bỏ đáp án chính xác khỏi đường khớp chắc chắn, rồi cho bộ ứng viên chạy như tên lạ.
  - Đo độ đúng / độ phủ của luật tự nhận theo lưới ngưỡng.
  - Đề xuất bộ ngưỡng có **0 lỗi** trên tập này.
  - Ghi `data/kb_reports/T52_hieu_chuan.json`.
  - Claude sẽ chạy thật và quyết định bật cờ.
- **Test bắt buộc (dùng kho ứng viên thu nhỏ, thật):** không cặp nào sau bị tự nhận nhầm sang nhau ở bất kỳ ngưỡng mặc định nào:
  - cefotaxime / ceftriaxone / cefuroxime / ceftazidime / cefoxitin
  - hydroxyzine / hydralazine
  - clonidine / clonazepam
  - prednisone / prednisolone
  - glipizide / glyburide
  - amlodipine / amiloride
  - metformin / metronidazole

### 4. Hàng duyệt và nhập kết quả duyệt

- `data/kb_reports/T52_hang_duyet.csv` (UTF-8 có BOM để mở bằng Excel), **xếp theo số chế phẩm bị ảnh hưởng giảm dần**. Cột:
  - `khoa_chuan_hoa`, `ten_goc_vi_du`, `so_che_pham`, `so_luot`
  - `ung_vien_1..3` (tên + rxcui + điểm), `ly_do`
  - Cột trống để người duyệt điền: `quyet_dinh` (`chon_1` · `chon_2` · `chon_3` · `rxcui:<so>` · `duoc_lieu` · `bo_qua`), `nguoi_duyet`, `ghi_chu`
- Lệnh `nhap-duyet <tep.csv>`:
  - Đọc các dòng đã điền, kiểm hợp lệ (rxcui phải có trong kho ứng viên), ghi `data/kb_curated/tu_dien/duyet_tay.jsonl` với `cach_khop = "nguoi_duyet"`.
  - Lần `build` sau áp dụng tệp này **trước** mọi luật khác.
  - Dòng không hợp lệ thì báo lỗi, không nhập.

### 5. Bộ tra cuối và báo cáo trước / sau

- Dựng lại tầng 2 với các cách khớp mới. **Chỉ** các cách khớp sau được vào bộ cuối: `ma_chuan`, `bang_viet_quoc_te`, `rxnav_chinh_xac`, `them_e_cuoi`, `bang_vitamin`, `nguoi_duyet`, `ngu_nghia_tu_nhan` (chỉ khi cờ bật).
- Giữ nguyên bất biến của T50: không mồ côi, mọi dòng có `nguon_ban_ghi_ids`, không hoạt chất không neo. Hoạt chất mới thêm từ RxNorm có `nguon_ban_ghi_ids` trỏ tới danh sách RxNorm.
- `data/kb_reports/T52_do_phu_truoc_sau.json`:
  - Số chế phẩm đủ thành phần trước / sau, tách theo từng `cach_khop`.
  - Số tên còn trong hàng duyệt; số chế phẩm `duoc_lieu`.
  - **Hoạt chất ca giả lập chưa khớp: phải vẫn là 0.**
- `data/kb_reports/T52_mau_kiem.jsonl`: 40 dòng ngẫu nhiên (seed 52), 10 dòng cho mỗi cách khớp mới (`them_e_cuoi`, `bang_vitamin`, `duoc_lieu`, ứng viên hạng 1 của hàng duyệt), để Claude kiểm tay.

### 6. Chuẩn bị đẩy Supabase (không chạy)

- `db/tu_dien.sql`: DDL các bảng trong lược đồ `tri_thuc`, có khoá chính, khoá ngoại, `CHECK` cho `cach_khop` / `loai`, chỉ mục cho cột tra cứu, và bật RLS giống các bảng `tri_thuc` khác trong `db/schema.sql` (đọc để làm theo):
  - `tu_dien_hoat_chat`, `tu_dien_dong_nghia`, `tu_dien_thuoc`, `tu_dien_thanh_phan`, `tu_dien_anh_xa`, `tu_dien_hang_duyet`
  - **Không** sửa bảng `tri_thuc.hoat_chat` / `ten_thuoc` đang có.
- `python -m app.kb.dictionary publish`:
  - Mặc định `--dry-run`: in số dòng mỗi bảng và 3 dòng mẫu.
  - Chỉ ghi khi có `--yes`, đọc `DATABASE_URL` từ môi trường, nạp theo lô trong một giao dịch, có `phien_ban`.
  - Task này **chỉ chạy dry-run**.

## Nghiệm thu (dán kết quả vào báo cáo)

- `uv run python -m app.kb.dictionary build` với quy tắc mục 1 (không cần nhúng): dán độ phủ trước / sau.
- `uv run python -m app.kb.dictionary candidates --embedder fake`, `review`, `calibrate --embedder fake` chạy hết. Ghi rõ số đo bằng mô hình nhúng giả **không có ý nghĩa**, chỉ kiểm luồng.
- `nhap-duyet` với tệp mẫu 5 dòng trong fixture: áp dụng đúng; dòng sai bị từ chối.
- `publish` (dry-run): dán đầu ra.
- Test chống thuốc tên gần nhau qua. Test quy tắc vitamin: "C" đứng một mình trong chế phẩm không phải vitamin thì không ánh xạ.
- `uv run ruff check app/kb tests/kb`, `ruff format --check` các tệp đã sửa, `uv run pytest -q tests/kb --basetemp=.pytest_t52` qua.
- Báo cáo `plan/reports/T52.md`:
  - Có các mục "Lựa chọn đã làm", "Lệnh Claude cần chạy thật (nhúng, hiệu chuẩn, publish)", "Giới hạn còn lại".

## Cấm làm

- Không gọi mạng; không đặt khoá API trong code.
- Không commit. Không dùng `&`.
- Không ghép mờ vào bộ cuối khi cờ tắt.
- Không sửa dữ liệu nguồn.
- Xoá `.pytest_t52*` khi xong.
