# Báo cáo độ phủ nhãn openFDA

Số nhãn trên đĩa: 50. Sinh lại bằng `uv run python -m app.kb.fetch report`.
Không gọi mạng; không sửa, dịch hoặc tóm tắt nhãn. Ô mục ghi có/không và số ký tự.
Bảng liều tính ký tự bản phẳng của bảng tách được, bỏ bảng trùng nguyên văn.
Chỉnh liều thận là chỉ dấu văn bản trong mục liều/nhóm đặc biệt; cần dược sĩ đối chiếu.

| Nhãn | Chỉ định | Liều và cách dùng | Chống chỉ định | Cảnh báo | Tương tác | Nhóm đặc biệt | Bảng liều | Số bảng liều | Thận | Tương tác | Đường dùng | effective_time |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `openfda/acetaminophen.json` | có (334) | có (4774) | có (282) | có (2401) | có (894) | có (8222) | không (0) | 0 | có | có | INTRAVENOUS | 20260924 |
| `openfda/acyclovir.json` | có (854) | có (3816) | có (129) | có (6651) | có (300) | có (3658) | có (155) | 1 | có | có | INTRAVENOUS | 20241113 |
| `openfda/allopurinol.json` | có (1602) | có (9588) | có (274) | có (7282) | có (5764) | có (9300) | có (411) | 2 | có | có | ORAL | 20261105 |
| `openfda/amikacin.json` | có (3173) | có (7912) | có (302) | có (12692) | không (0) | có (664) | có (516) | 1 | có | không | INTRAMUSCULAR, INTRAVENOUS | 20260727 |
| `openfda/amiodarone.json` | có (1166) | có (5171) | có (851) | có (11555) | có (9774) | có (4249) | không (0) | 0 | có | có | INTRAVENOUS | 20261026 |
| `openfda/amlodipine.json` | có (4062) | có (1676) | có (155) | có (1146) | có (1335) | có (7903) | không (0) | 0 | có | có | ORAL | 20261109 |
| `openfda/amoxicillin_and_clavulanate_potassium.json` | có (3427) | có (9324) | có (880) | có (7365) | có (2251) | có (7384) | có (3777) | 5 | có | có | ORAL | 20261105 |
| `openfda/apixaban.json` | có (1258) | có (8985) | có (362) | có (10861) | có (4755) | có (13072) | không (0) | 0 | có | có | ORAL | 20260924 |
| `openfda/atorvastatin.json` | có (2198) | có (2898) | có (533) | có (7828) | có (8028) | có (20653) | không (0) | 0 | có | có | ORAL | 20261106 |
| `openfda/cefepime.json` | có (3190) | có (9546) | có (513) | có (4656) | có (2176) | có (9633) | có (3128) | 4 | có | có | INTRAVENOUS | 20260625 |
| `openfda/ceftriaxone.json` | có (5265) | có (5487) | có (1913) | có (13677) | không (0) | có (2472) | có (271) | 2 | có | không | INTRAMUSCULAR, INTRAVENOUS | 20260930 |
| `openfda/ciprofloxacin.json` | có (8136) | có (7069) | có (508) | có (19810) | có (5381) | có (23201) | có (3630) | 7 | có | có | INTRAVENOUS | 20260804 |
| `openfda/clarithromycin.json` | có (4899) | có (5814) | có (2674) | có (11234) | có (17280) | có (18078) | có (1313) | 2 | có | có | ORAL | 20261109 |
| `openfda/clopidogrel.json` | có (1605) | có (994) | có (528) | có (4799) | có (4324) | có (6635) | không (0) | 0 | có | có | ORAL | 20261105 |
| `openfda/colistimethate.json` | có (1374) | có (3321) | có (157) | có (9252) | có (779) | có (2277) | có (1963) | 2 | có | có | INTRAMUSCULAR, INTRAVENOUS | 20261104 |
| `openfda/dabigatran.json` | có (2686) | có (14005) | có (640) | có (11288) | có (2984) | có (12901) | có (1718) | 2 | có | có | ORAL | 20261106 |
| `openfda/digoxin.json` | có (896) | có (5799) | có (480) | có (6312) | có (3456) | có (5839) | không (0) | 0 | có | có | INTRAMUSCULAR, INTRAVENOUS | 20261106 |
| `openfda/enalapril.json` | có (1953) | có (6179) | có (668) | có (20593) | có (1791) | có (1520) | có (405) | 1 | có | có | ORAL | 20261009 |
| `openfda/enoxaparin.json` | có (3013) | có (11016) | có (712) | có (11781) | có (655) | có (9579) | có (1342) | 1 | có | có | SUBCUTANEOUS | 20261015 |
| `openfda/esomeprazole.json` | có (3762) | có (6979) | có (1151) | có (10598) | có (7876) | có (23570) | có (2453) | 3 | có | có | ORAL | 20261102 |
| `openfda/fentanyl.json` | có (1328) | có (5053) | có (194) | có (21756) | có (7431) | có (13694) | có (1655) | 1 | có | có | INTRAMUSCULAR, INTRAVENOUS | 20261023 |
| `openfda/fluconazole.json` | có (1226) | có (17266) | có (635) | có (35106) | có (17797) | có (12426) | có (714) | 4 | có | có | INTRAVENOUS | 20260817 |
| `openfda/furosemide.json` | có (899) | có (3495) | có (137) | có (15235) | có (3689) | có (3445) | không (0) | 0 | không | có | INTRAMUSCULAR, INTRAVENOUS | 20261102 |
| `openfda/gentamicin.json` | có (3657) | có (6647) | có (277) | có (9666) | không (0) | không (0) | không (0) | 0 | có | không | INTRAMUSCULAR, INTRAVENOUS | 20261102 |
| `openfda/heparin.json` | có (1399) | có (7786) | có (1140) | có (7419) | có (1841) | có (9358) | có (1865) | 2 | không | có | INTRAVENOUS, SUBCUTANEOUS | 20261103 |
| `openfda/ibuprofen.json` | có (669) | có (2471) | có (557) | có (29486) | có (3766) | có (5687) | không (0) | 0 | không | có | ORAL | 20261109 |
| `openfda/imipenem_and_cilastatin.json` | có (6375) | có (9339) | có (241) | có (6499) | có (2254) | có (10596) | có (2217) | 4 | có | có | INTRAVENOUS | 20250116 |
| `openfda/insulin_glargine.json` | có (554) | có (3745) | có (353) | có (6871) | có (2729) | có (10675) | không (0) | 0 | có | có | SUBCUTANEOUS | 20260616 |
| `openfda/ketorolac.json` | có (1175) | có (3715) | có (2153) | có (40141) | có (240) | có (7238) | không (0) | 0 | có | có | INTRAMUSCULAR, INTRAVENOUS | 20260213 |
| `openfda/levetiracetam.json` | có (1054) | có (7280) | có (298) | có (16923) | không (0) | có (15601) | không (0) | 0 | có | không | ORAL | 20261106 |
| `openfda/levofloxacin.json` | có (9140) | có (12043) | có (252) | có (18142) | có (5208) | có (19117) | có (6418) | 4 | có | có | INTRAVENOUS | 20260721 |
| `openfda/linezolid.json` | có (3424) | có (5176) | có (612) | có (10918) | có (522) | có (13735) | có (2444) | 2 | không | có | ORAL, INTRAVENOUS | 20261103 |
| `openfda/losartan.json` | có (4176) | có (3508) | có (305) | có (2818) | có (2972) | có (13427) | không (0) | 0 | có | có | ORAL | 20261109 |
| `openfda/meropenem.json` | có (2583) | có (8841) | có (329) | có (7287) | có (1456) | có (14788) | có (3030) | 7 | có | có | INTRAVENOUS | 20261102 |
| `openfda/metformin.json` | có (438) | có (3299) | có (514) | có (10015) | có (2793) | có (11468) | không (0) | 0 | có | có | ORAL | 20261109 |
| `openfda/methotrexate.json` | có (1425) | có (5836) | có (445) | có (13034) | có (2053) | có (9902) | không (0) | 0 | có | có | ORAL | 20261105 |
| `openfda/metoprolol_succinate.json` | có (3444) | có (3807) | có (545) | có (5350) | có (1997) | có (8169) | không (0) | 0 | có | có | ORAL | 20261104 |
| `openfda/metoprolol_tartrate.json` | có (567) | có (1311) | có (747) | có (2558) | có (2728) | có (10589) | không (0) | 0 | không | có | INTRAVENOUS | 20261008 |
| `openfda/morphine.json` | có (1238) | có (6450) | có (1012) | có (19272) | có (5102) | có (24685) | không (0) | 0 | có | có | INTRAVENOUS | 20261014 |
| `openfda/omeprazole.json` | có (3984) | có (6709) | có (1162) | có (10670) | có (8843) | có (27388) | có (5256) | 3 | không | có | ORAL | 20261027 |
| `openfda/phenytoin.json` | có (841) | có (10834) | có (992) | có (13880) | có (1789) | có (5618) | không (0) | 0 | có | có | INTRAMUSCULAR, INTRAVENOUS | 20261106 |
| `openfda/piperacillin_and_tazobactam.json` | có (3243) | có (14581) | có (327) | có (8243) | có (5278) | có (13576) | có (2401) | 5 | có | có | INTRAVENOUS | 20261022 |
| `openfda/rivaroxaban.json` | có (1268) | có (5188) | có (359) | có (11873) | có (2495) | có (12265) | có (681) | 1 | có | có | ORAL | 20261021 |
| `openfda/simvastatin.json` | có (1818) | có (3484) | có (999) | có (7668) | có (7190) | có (15138) | không (0) | 0 | có | có | ORAL | 20261103 |
| `openfda/spironolactone.json` | có (4934) | có (2403) | có (262) | có (2310) | có (2978) | có (9857) | không (0) | 0 | có | có | ORAL | 20261109 |
| `openfda/sulfamethoxazole_and_trimethoprim.json` | có (2496) | có (3121) | có (517) | có (24660) | có (5225) | có (8281) | có (553) | 4 | có | có | ORAL | 20261014 |
| `openfda/tramadol.json` | có (1271) | có (13323) | có (1544) | có (38980) | có (9405) | có (10548) | không (0) | 0 | có | có | ORAL | 20261103 |
| `openfda/valproate.json` | có (2376) | có (9872) | có (1504) | có (26816) | có (13840) | có (31398) | không (0) | 0 | không | có | INTRAVENOUS | 20260312 |
| `openfda/vancomycin.json` | có (2963) | có (9624) | có (135) | có (10705) | có (503) | có (1878) | có (370) | 2 | có | có | INTRAVENOUS | 20261008 |
| `openfda/warfarin.json` | có (1406) | có (11332) | có (2533) | có (8871) | có (6473) | có (11717) | có (246) | 1 | có | có | ORAL | 20261109 |

## Thiếu nhãn cho đường dùng cần có

Không có.

## Nhãn thiếu từ 2 mục trở lên

- `openfda/gentamicin.json`: Tương tác, Nhóm đặc biệt, Bảng liều
- `openfda/levetiracetam.json`: Tương tác, Bảng liều

## Ghi chú danh mục và lỗi nguồn

- `acetaminophen`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `acyclovir`: Bổ sung đúng dạng tiêm theo README; thay nhãn uống khi tìm được nhãn phù hợp.
- `allopurinol`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `amikacin`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `amiodarone`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `amlodipine`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `amoxicillin_and_clavulanate_potassium`: Phối hợp đã có trong danh mục; chỉ nhận đúng các thành phần ghi rõ dưới đây.
- `apixaban`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `atorvastatin`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `cefepime`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `ceftriaxone`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `ciprofloxacin`: Bổ sung đúng dạng tiêm theo README; thay nhãn uống khi tìm được nhãn phù hợp.
- `clarithromycin`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `clopidogrel`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `colistimethate`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `dabigatran`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `digoxin`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `enalapril`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `enoxaparin`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `esomeprazole`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `fentanyl`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `fluconazole`: Bổ sung đúng dạng tiêm theo README; thay nhãn uống khi tìm được nhãn phù hợp.
- `furosemide`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `gentamicin`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `heparin`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `ibuprofen`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `imipenem_and_cilastatin`: Phối hợp đã có trong danh mục; chỉ nhận đúng các thành phần ghi rõ dưới đây.
- `insulin_glargine`: Truy vấn đúng tên insulin glargine, không dùng tên có hậu tố của bản tương tự sinh học.
- `ketorolac`: Bổ sung đúng dạng tiêm theo README; thay nhãn uống khi tìm được nhãn phù hợp.
- `levetiracetam`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `levofloxacin`: Bổ sung đúng dạng tiêm theo README; thay nhãn uống khi tìm được nhãn phù hợp.
- `linezolid`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `losartan`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `meropenem`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `metformin`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `methotrexate`: README chỉ xác định nhãn hiện tại là dung dịch uống, chưa xác định đường dùng cần thay; giữ ORAL, cần dược sĩ chốt.
- `metoprolol_succinate`: Giữ ORAL của dạng succinate; yêu cầu bổ sung nhãn tiêm áp dụng mục metoprolol_tartrate, không suy ra succinate có dạng tiêm.
- `metoprolol_tartrate`: Bổ sung đúng dạng tiêm theo README; thay nhãn uống khi tìm được nhãn phù hợp.
- `morphine`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `omeprazole`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `phenytoin`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `piperacillin_and_tazobactam`: Phối hợp đã có trong danh mục; chỉ nhận đúng các thành phần ghi rõ dưới đây.
- `rivaroxaban`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `simvastatin`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `spironolactone`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `sulfamethoxazole_and_trimethoprim`: Phối hợp đã có trong danh mục; chỉ nhận đúng các thành phần ghi rõ dưới đây.
- `tramadol`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `valproate`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `vancomycin`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.
- `warfarin`: Giữ đường dùng đã có trong nguồn; danh mục chờ dược sĩ chốt.

## Kết quả tải gần nhất

- openfda: bo_qua=43, da_lay=7
- ndc: bo_qua=46, da_lay=4

## Đối chiếu dựng lại kho

- Nhãn trước / sau: 50 / 50.
- Đoạn trước / sau: 3738 / 3730.
- Mã đoạn cũ không còn trong kho: 633 (bao gồm đoạn có nội dung hoặc nhãn được thay thế).
- Mã bị đổi dù nội dung và đường dẫn không đổi: 0.

Dòng tóm tắt nghiệm thu của `uv run python -m app.kb.build`:

```text
[openfda] status=OK labels=50/50 chunks=3730 text=3483 table=247 over_max=0 under_50=0 empty_act=0 q3_warn=16 missing_set_id=0
```
