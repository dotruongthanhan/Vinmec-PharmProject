# T55 – Bảng tương tác từ DDInter, luật yếu tố 4, nối ma trận giao diện (plan 1.8 D1.6–D1.8)

Mô hình: Codex `gpt-6.1-sol`, effort `xhigh`. Không có mạng, không cần mạng. Chạy nền, không dừng để hỏi. Điểm chưa rõ thì chọn cách ít rủi ro nhất và ghi vào báo cáo, mục "Lựa chọn đã làm".

**Ưu tiên: kịp demo. Đóng băng tính năng trưa 19/11/2026.**

Đọc trước:
- `AGENTS.md`
- **`plan/api-hop-dong-v1.6-ma-tran-tuong-tac.md`** (hợp đồng, bám đúng tên trường)
- `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md` mục D1, 3.2
- `plan/reports/T51.md`, `plan/reports/T53.md`
- `app/rules/registry.py`, `app/rules/types.py`, `app/rules/engine.py`, `app/rules/duplicate.py` (mẫu luật)
- `app/kb/resolver/**` (bộ phân giải, chỉ dùng, không sửa)
- `app/api/presenter.py`, `app/api/schemas.py`, `app/container.py`
- `web/src/lib/detailTables.ts`, `web/src/features/order-detail/InteractionMatrix.tsx`

## Dữ liệu sẵn có (chỉ đọc)

DDInter tầng 1 (`data/kb_staging/ddinter/`):
- `thuoc.jsonl`: 1.971 thuốc, có `tong_tuong_tac_tren_trang`.
- `tuong_tac_thuoc.jsonl`: 553.657 dòng, 291.877 cặp; có `muc_do`, `muc_do_so`, `co_che[]`, `ma_trang_cap`, `tu_trang_cua`.
- `tuong_tac_chi_tiet.jsonl`: 861 trang cặp; có `hau_qua`, `xu_tri`, `tai_lieu[]`, `thay_the_a/b`.
- `tuong_tac_thuc_an.jsonl`: 805 dòng.
- `tuong_tac_benh.jsonl`.

Lưu ý:
- 274 cặp có nhiều `ma_trang_cap` với mức khác nhau.
- `xu_tri` có khi là chuỗi `"-"`, nghĩa là không có.

Bộ phân giải T53:
- `DrugResolver.from_index(Path("data/kb_curated/tra_cuu/tra_cuu.sqlite"))` → `resolve_line(ca, line)` trả `KetQuaPhanGiai` (thành phần có `hoat_chat_id`, `ddinter_id`, `loai`; `trang_thai`).
- Đã kiểm: 49/51 hoạt chất của ca giả lập có `ddinter_id` (thiếu `penicillin_g` vì xung đột 3 bản ghi benzylpenicillin, và `sulbactam` không có trong DDInter).

## Phạm vi file

**Được tạo / sửa:**
- `app/kb/interactions/**` (mới: dựng bảng và kho đọc)
- `data/kb_curated/tuong_tac/**` (mới)
- `app/rules/interaction.py` (mới), `app/rules/registry.py` (thêm luật vào `default_rules`, thêm phụ thuộc vào `RuleContext` dạng tuỳ chọn)
- `app/container.py` (nối đường dẫn chỉ mục)
- `app/config/settings.py` + `config/settings.yaml` + `config/settings.test.yaml` (chỉ thêm đường dẫn `tra_cuu` và `tuong_tac`)
- `app/api/schemas.py`, `app/api/presenter.py`, `app/api/view_models*.py` nếu có (chỉ thêm `ma_tran_tuong_tac`)
- `web/src/api/types.ts`, `web/src/lib/detailTables.ts`, `web/src/features/order-detail/InteractionMatrix.tsx`, test web liên quan
- `tests/rules/test_interaction*.py`, `tests/kb/test_interactions*.py`, `tests/api/**` (thêm test và sửa kỳ vọng **chỉ** nơi số luật / số nhận định đổi vì thêm luật)
- `plan/reports/T55.md`

**Cấm đụng:**
- `app/kb/resolver/**`, `app/kb/dictionary/**` (T52-fix-1 đang chạy song song)
- `data/kb_curated/tu_dien/**`, `data/kb_curated/tra_cuu/**`, `data/kb_staging/**`, `data/kb_sources/**`, `data/mock/**`, `data/gold/**`
- `app/llm/**`, `app/deid/**`, `app/orchestration/**`, `app/db/**`, `db/**`, `.env`, `pyproject.toml`, `uv.lock`, `plan/` (trừ báo cáo)
- Không thêm thư viện, không đổi trường API cũ.

## Yêu cầu

### 1. Bảng tương tác (D1.6): `python -m app.kb.interactions build`

Ghi `data/kb_curated/tuong_tac/ddinter.sqlite` (ghi tệp mới rồi thay thế nguyên tử; chạy lại cho cùng SHA-256).

Bảng `cap`:

```text
ddinter_id_a < ddinter_id_b (PK), muc_do (Major|Moderate|Minor|Unknown), muc_do_so, co_che_json,
co_lech_muc (bool), cac_muc_nguon_json, ma_trang_cap_json, hau_qua, xu_tri, tai_lieu_json, url_goc
```

- Gộp mọi dòng của cùng cặp (cả hai chiều). Mức lấy **cao nhất** (Major > Moderate > Minor > Unknown); khác mức thì `co_lech_muc = true` và giữ mọi mức nguồn.
- Chi tiết (hậu quả, xử trí, tài liệu) lấy từ trang cặp nếu đã cào, ưu tiên trang có mức trùng mức đã chọn. `"-"` / rỗng → `NULL`.

Bảng `thuoc`:
- `ddinter_id`, `ten`, `da_cao_du`.
- `da_cao_du = true` khi số dòng thuốc–thuốc đã có bằng `tong_tuong_tac_tren_trang.tuong_tac_thuoc`.

Bảng `thuc_an`: `ddinter_id`, `thuc_an`, `muc_do`, `mo_ta`, `xu_tri`, `co_che_json`.

Báo cáo `data/kb_reports/T55_bang_tuong_tac.json`: số cặp theo mức, số cặp lệch mức, số cặp có chi tiết, số thuốc `da_cao_du`.

### 2. Kho đọc

`InteractionStore.from_path(...)` có:
- `pair(id_a, id_b)`
- `drug_complete(id)`
- `foods(id)`

Đọc SQLite chỉ đọc, nạp một lần.

### 3. Luật yếu tố 4 (D1.7): `app/rules/interaction.py`

- Dòng xét: `effective_lines(ca)`. Phân giải từng dòng bằng bộ phân giải.
- Tính `CapMaTran` cho **mọi cặp dòng** theo đúng bảng mức trong hợp đồng v1.6:
  - Mức nặng nhất qua mọi cặp hoạt chất.
  - Hai dòng cùng hoạt chất → `khong_ap_dung` kèm lý do "trùng hoạt chất – xem yếu tố 2".
  - `khong_phat_hien` chỉ khi cả hai `ddinter_id` có `da_cao_du`.
- Sinh `PhatHien` (`yeu_to=4`) cho cặp có ít nhất một dòng chờ duyệt:

  | Mức của cặp | `ket_luan` | `muc_do` | Ghi chú |
  |:--|:--|:--|:--|
  | Major | `can_xem` | `nghiem_trong` | |
  | Moderate | `can_xem` | `can_luu_y` | |
  | Minor | `can_xem` | `thong_tin` | Ma trận hiện `can_luu_y`, `tom_tat` ghi Minor |
  | Thiếu dữ liệu | `khong_du_du_lieu` | `None` | `thong_tin_con_thieu` nêu tên thuốc / hoạt chất thiếu dữ liệu |

  - `mo_ta` có tên hai thuốc (đúng `line_label`) và hai hoạt chất. Ví dụ: "Warfarin 5 mg + Amiodaron 200 mg (warfarin × amiodarone): DDInter Major – Metabolism. Sàng lọc, cần đối chiếu nhãn."
  - `can_cu`: `tai_lieu` gồm nguồn, mức, cơ chế, hậu quả, xử trí, URL trang gốc. Văn bản DDInter giữ nguyên tiếng Anh, không dịch.
- Không có cặp nào cần báo và mọi cặp đều đã xét → một `PhatHien` `dat` cho yếu tố 4 với `chi_tiet_y_lenh_id` của dòng chờ duyệt, để yếu tố 4 không bị coi là chưa kiểm.
- Chỉ mục tra cứu hoặc bảng tương tác không có → luật không sinh gì, ghi một cảnh báo; yếu tố 4 vẫn "chưa có luật" như cũ. **Không làm hỏng các luật khác.**
- Thứ tự sắp phát hiện theo `_priority_key` sẵn có.
- Luật trả thêm dữ liệu ma trận cho presenter. Cách gợi ý: hàm thuần `build_interaction_matrix(ca, resolver, store) -> MaTranTuongTac`, dùng chung cho luật và presenter, có cache theo `ca_id` + mốc làm mới nếu cần. **Không** nhét ma trận vào `PhatHien`.

### 4. API (D1.8 phần backend)

`ChiTietCa.ma_tran_tuong_tac` đúng lược đồ v1.6:
- `ten` của thuốc phải trùng tên trong bảng y lệnh đang hiển thị.
- `nhan_dinh_id` trỏ đúng nhận định yếu tố 4 của cặp đó. Theo cách presenter đang sinh `nhan_dinh_id`; ghi rõ cách nối trong báo cáo.
- `nguon` = "DDInter 2.0 (sàng lọc, CC BY-NC-SA 4.0)".

### 5. Giao diện (D1.8 phần web)

- `buildInteractionMatrix` dùng `ma_tran_tuong_tac` khi có (khoá theo `chi_tiet_y_lenh_id`, không dò chuỗi); `null` thì giữ cách cũ.
- Thêm mức `khong_ap_dung` vào `InteractionLevel` và `INTERACTION_LEVEL_META` (mã "–", nhãn "Không áp dụng", gợi ý "Dịch truyền, điện giải hoặc dược liệu"); ô hiển thị theo hệ thống thiết kế hiện có (plan 1.4).
- Bấm ô có `nhan_dinh_id` thì mở nhận định như hiện nay. Ô `thieu_du_lieu` / `khong_ap_dung` hiện `ly_do` khi rê chuột hoặc lấy tiêu điểm.
- Dưới ma trận: danh sách ngắn tương tác thuốc–thức ăn (nếu có) và dòng nguồn `nguon` + `ghi_chu`.

### 6. Test và kiểm trên ca thật

Test luật dùng chỉ mục thu nhỏ (fixture) hoặc chỉ mục thật, đọc chỉ đọc. Các tình huống:
- Cặp Major tạo `nghiem_trong`.
- Phối hợp lấy mức nặng nhất.
- Thiếu `ddinter_id` → `thieu_du_lieu`.
- Dịch truyền → `khong_ap_dung`.
- Cùng hoạt chất → `khong_ap_dung`.
- Không phát hiện chỉ khi `da_cao_du`.
- Đối xứng (A, B) = (B, A).
- Thiếu chỉ mục → luật im lặng, không lỗi.

Lệnh `python -m app.kb.interactions report-ca` chạy ma trận cho mọi ca `data/mock/demo` + `data/mock/hoso_gia_lap` (dùng bộ nạp ca như `app.kb.resolver.build._load_cases(Path("."))`). Ghi `data/kb_reports/T55_ma_tran_ca.json`:
- Đếm cặp theo mức.
- Liệt kê mọi cặp `nghiem_trong` / `can_luu_y`.
- Liệt kê `thieu_du_lieu` kèm lý do.
- **Không còn cặp `chua_kiem`.**

Kiểm cụ thể:
- Ca có amiodarone + digoxin (ví dụ HS-024) phải ra `nghiem_trong`.
- Ca có clarithromycin + simvastatin, meropenem + valproate (nếu có trong dữ liệu) phải ra `nghiem_trong`.
- Ca Levetiracetam + Natri clorid + Paracetamol: cặp có natri clorid là `khong_ap_dung`; cặp levetiracetam × paracetamol theo đúng dữ liệu DDInter.

## Nghiệm thu (dán kết quả vào báo cáo)

- `uv run python -m app.kb.interactions build` và `report-ca`: dán số liệu.
- `uv run ruff check .` (toàn kho; nếu còn lỗi của task khác thì ghi rõ tệp), `uv run ruff format --check` các tệp đã sửa, `uv run pytest -q --basetemp=.pytest_t55` (toàn kho).
  - Liệt kê **mọi** test cũ phải đổi kỳ vọng, kèm lý do; chỉ chấp nhận lý do "thêm luật yếu tố 4".
  - Đã biết sẵn một lỗi không phải của task này: `tests/architecture/test_import_boundaries.py::test_environment_access_only_in_config` (do `app/kb/dictionary/publish.py` của T52). Ghi nhận, không sửa.
- Web, trong `web/`: `npx vitest run`, `npx oxlint`, `npx tsc -b`, `npm run build` qua.
- Đo thời gian thêm vào `GET /api/cases/{ca_id}` khi bật luật mới (trước / sau, ca DEMO-02).
- Báo cáo `plan/reports/T55.md`: có các mục "Lựa chọn đã làm", "Test đã đổi kỳ vọng", "Giới hạn còn lại".

## Cấm làm

- Không gọi mạng hay LLM.
- Không commit. Không dùng `&`.
- Không dịch hay sửa nội dung DDInter.
- Không dùng chữ "chống chỉ định" cho kết luận từ DDInter.
- Xoá `.pytest_t55*` khi xong (nếu bị chặn quyền thì ghi lại).
