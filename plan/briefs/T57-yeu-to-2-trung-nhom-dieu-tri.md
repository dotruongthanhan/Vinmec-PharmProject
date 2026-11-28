# T57 – Yếu tố 2: trùng hoạt chất qua bộ phân giải và trùng nhóm điều trị theo ATC (plan 1.8 đợt D2)

Mô hình: Codex `gpt-6.1-sol`, effort `xhigh`. Không có mạng, không cần mạng.

Đọc trước:
- `AGENTS.md`
- `plan/plan-1.8-du-lieu-tham-dinh-7-yeu-to.md`: mục 2 (nguyên tắc), 5.0, **Đợt D2**, mục 6
- `app/rules/duplicate.py`, `app/rules/registry.py`, `app/rules/interaction.py` (mẫu dùng `ctx.resolver`, xử lý thiếu chỉ mục)
- `app/kb/resolver/resolver.py` (`resolve_line`, `KetQuaPhanGiai`, `ThanhPhanPhanGiai.ma_atc`)

## Bối cảnh

D0 + D1 đã qua review tổng ngày 19/11. Bộ phân giải `DrugResolver` trả hoạt chất trên trục RxNorm kèm `ma_atc` (danh sách mã ATC mức 4, lấy từ RxClass).

Luật yếu tố 2 hiện tại (`app/rules/duplicate.py`) chỉ so mã `HC-…` của danh mục ca. Vì vậy:
- Không bắt được "Augmentin" + "Amoxicillin" ghi khác mã.
- Không có trùng nhóm điều trị.
- Khi không thấy trùng thì luôn ghi `dat`, kể cả khi có dòng thuốc không phân giải được.

Claude đã chạy thử trên 66 ca. Đúng 4 ca có trùng nhóm, đều là ca thiết kế cho D2:

| Ca | Nhóm | Hoạt chất | ATC |
|:--|:--|:--|:--|
| HS-014 | ức chế hệ RAS | enalapril, losartan | C09AA, C09CA |
| HS-015 | PPI | omeprazole, esomeprazole | A02BC |
| HS-016 | chống đông | enoxaparin, rivaroxaban | B01AB, B01AF |
| HS-017 | NSAID | ketorolac, ibuprofen | M01AB, M01AE |

Chú ý: ibuprofen có 5 mã ATC (C01EB, G02CC, M01AE, M02AA, R02AX). heparin có B01AB, C05BA, S01XA. Vì vậy **không được** so "trùng mã ATC mức 4" một cách máy móc. Nhóm phải định nghĩa bằng danh sách tiền tố trong cấu hình.

## Phạm vi file

**Được tạo / sửa:**
- `app/rules/duplicate.py`, `app/rules/registry.py` (chỉ `DuplicateRule`)
- `config/kb/nhom_dieu_tri_trung.yaml` (mới), `config/kb/atc_bo_sung.yaml` (mới)
- Mã nạp cấu hình nếu cần: đặt trong `app/rules/` hoặc `app/kb/` (module mới); đọc qua lớp cấu hình hiện có, không đọc biến môi trường
- `tests/rules/test_duplicate*.py` và test mới; test API / kiến trúc chỉ khi kỳ vọng đổi vì hành vi mới (liệt kê từng thay đổi trong báo cáo)
- `web/src/api/mockData.ts` chỉ khi test web trượt vì chuỗi đổi
- `plan/reports/T57.md`

**Cấm đụng:**
- Luật khác (`interaction.py`, `allergy.py`, `antibiotic.py`, `renal_dose.py`, `schedule.py`)
- `app/kb/resolver/**`, `app/kb/dictionary/**`, `app/kb/interactions/**`, `app/llm/**`, `app/orchestration/**`
- `data/**` (chỉ đọc), `db/**`, `.env`, `pyproject.toml`, `uv.lock`
- Hợp đồng API: không đổi tên hay thêm trường; `ma_luat` là chuỗi tự do nên được thêm mã mới

## Yêu cầu

### 1. Trùng hoạt chất qua bộ phân giải

- Có `ctx.resolver` thì lấy hoạt chất của mỗi dòng đang hiệu lực qua `resolve_line` (khoá `hoat_chat_id` trên trục).
- Không có `ctx.resolver` (thiếu `tra_cuu.sqlite`) thì chạy đúng luật cũ, không lỗi.
- Giữ `ma_luat="trung_hoat_chat"`, kết luận, mức và điều kiện "có ít nhất một dòng chờ duyệt" như cũ.
- Test: "Augmentin" (amoxicillin + clavulanic acid) + "Amoxicillin 500 mg" ra trùng amoxicillin. Dựng ca trong bộ nhớ nếu dữ liệu ca không có.

### 2. Trùng nhóm điều trị

Cấu hình `config/kb/nhom_dieu_tri_trung.yaml`. Mỗi nhóm có:
- `ma_nhom`, `ten` (tiếng Việt)
- `tien_to_atc`: danh sách tiền tố
- `muc_do`: `nghiem_trong` hoặc `can_luu_y`
- `ly_do`: một câu tiếng Việt về nguy cơ
- `nguon`: ghi "phân loại ATC của WHO; mức do nhóm đề xuất, chờ dược sĩ duyệt"
- `ngoai_le`: danh sách cặp hoạt chất được phép, mặc định rỗng

Bộ ban đầu (đánh dấu cả tệp là **chờ dược sĩ duyệt**):

| `ma_nhom` | Tiền tố | Mức |
|:--|:--|:--|
| `ppi` | A02BC | can_luu_y |
| `khang_h2` | A02BA | can_luu_y |
| `nsaid` | M01A (trừ M01AX) | nghiem_trong |
| `chong_dong` | B01AA, B01AB, B01AE, B01AF, B01AX05 | nghiem_trong |
| `uc_che_ras` | C09 | nghiem_trong |
| `statin` | C10AA | can_luu_y |
| `benzodiazepin` | N05BA, N05CD | can_luu_y |
| `sulfonylure` | A10BB | can_luu_y |

Luật:
- Hai **hoạt chất khác nhau** (khác `hoat_chat_id`) trên **hai dòng khác nhau** đang hiệu lực, cùng thuộc một nhóm, có ít nhất một dòng chờ duyệt → một phát hiện `ma_luat="trung_nhom_dieu_tri"`, `ket_luan="can_xem"`, `muc_do` theo nhóm.
- Mô tả mẫu: `Trùng nhóm chống đông: Enoxaparin 40 mg (enoxaparin, B01AB) và Rivaroxaban 20 mg (rivaroxaban, B01AF). Nếu đang chuyển thuốc, kiểm lịch ngừng thuốc cũ.`
- Căn cứ có mã ATC từng bên, nguồn nhóm, và câu "chờ dược sĩ duyệt bảng nhóm".
- Cùng một hoạt chất thì thuộc trùng hoạt chất, không báo hai lần.
- Hai thành phần trong **cùng một thuốc phối hợp** không tính là trùng nhóm.
- Một mã ATC chỉ được xét với các tiền tố của nhóm, nên mã phụ không gây báo nhầm. Ví dụ ibuprofen C01EB hay M02AA (thuốc bôi) không tạo nhóm khác. Thêm test cho ibuprofen.
- Cặp nằm trong `ngoai_le` thì không báo, nhưng ghi vào căn cứ của kết quả "đạt".

### 3. Thiếu dữ liệu (bất biến an toàn, bắt buộc)

- Dòng đang hiệu lực mà `resolve_line` trả `khong_nhan_dien` hoặc `mot_phan`, hoặc hoạt chất `loai` thường mà **mọi** thành phần của dòng đều không có ATC: **không được ghi `dat`** cho yếu tố 2.
- Khi đó, nếu không có phát hiện `can_xem` nào, trả một phát hiện `ket_luan="khong_du_du_lieu"`, `muc_do="thong_tin"`, nêu đúng dòng hoặc hoạt chất thiếu và lý do. Ví dụ: `Chưa đủ dữ liệu để loại trừ trùng nhóm: Oresol chưa nhận diện được hoạt chất.`
- Dòng `khong_ap_dung` (dịch truyền, điện giải) và dược liệu: bỏ qua, có ghi "không áp dụng" trong căn cứ; **không** làm mất kết luận `dat`.
- Thành phần không có ATC nhưng cùng dòng có thành phần khác có ATC (ví dụ clavulanic acid trong Augmentin): dòng vẫn đủ dữ liệu; ghi chú trong căn cứ.

`config/kb/atc_bo_sung.yaml`: bảng bổ sung ATC cho hoạt chất trên trục thiếu ATC.
- Mục đầu tiên: `valproic_acid: [N03AG]`, nguồn "WHO ATC/DDD Index, N03AG01", **chờ Claude kiểm**.
- Luật dùng `ma_atc` từ bộ phân giải, cộng thêm bảng này.
- Không sửa `tra_cuu.sqlite`.

### 4. Kết quả "đạt"

Không có phát hiện và đủ dữ liệu thì giữ `ma_luat="trung_hoat_chat_khong_co"`, đổi mô tả thành:
`Đã đối chiếu N dòng thuốc đang hiệu lực (M hoạt chất) theo K nhóm điều trị: không có trùng hoạt chất hay trùng nhóm.`

## Nghiệm thu (dán vào `plan/reports/T57.md`)

- [L] `uv run ruff check .`, `uv run ruff format --check` các tệp sửa; `uv run pytest -q -p no:cacheprovider --basetemp=<thư mục tạm ngoài kho>` toàn kho **0 trượt**. Nếu có sửa `mockData.ts`: `npx vitest run`, `npx tsc -b` trong `web/`.
- [L] Bảng chạy trên cả 66 ca (dùng `load_source_cases` và container, như `tests/api/test_interaction_runtime.py`). Mỗi ca một dòng: kết luận yếu tố 2, các `ma_luat`, nhóm.
  - Kỳ vọng: HS-014/015/016/017 có `trung_nhom_dieu_tri` đúng nhóm, đúng mức; không ca nào khác có `trung_nhom_dieu_tri`.
  - Ca có dòng chưa nhận diện (Oxy, Oresol, Ringer) không còn `dat`. Ghi rõ số ca `dat` / `can_xem` / `khong_du_du_lieu` trước và sau.
- [L] Test đơn vị: bốn tình huống trong bảng trên; ibuprofen mã phụ; hai thành phần cùng thuốc phối hợp; ngoại lệ; dòng không nhận diện → `khong_du_du_lieu`; dòng dịch truyền → vẫn `dat`; không có resolver → luật cũ.
- [L] Dán nguyên văn mô tả và căn cứ yếu tố 2 của HS-016 (TestClient, `AUTH_MODE=off`, ghi ca ra thư mục tạm).

## Cấm làm

Không gọi mạng. Không commit. Không dùng `&`. Không xoá hay bỏ qua test. Không đổi kết luận các luật khác.
