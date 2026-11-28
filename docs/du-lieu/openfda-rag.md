# openFDA – nhãn, NDC, đoạn RAG và cache nhúng

Cập nhật: 19/11/2026. Đọc dữ liệu thực và code hiện có, không tải nguồn hoặc gọi nhà cung cấp nhúng.

| Mục | Giá trị |
|:--|:--|
| Trang gốc | https://api.fda.gov/drug/label.json và https://api.fda.gov/drug/ndc.json; đường dẫn trích dẫn nhãn được dựng sang DailyMed theo set_id |
| Giấy phép | Manifest ghi `Public domain (FDA)`; phản hồi nhãn còn giữ `meta.license`, `meta.terms` và `meta.disclaimer`. Chỉ ghi nhận bằng chứng cục bộ, không xác minh điều khoản trực tuyến trong T59. |
| Tầng tin cậy | 3 theo manifest và `LabelChunker`; nhãn Mỹ không thay cho quyết định của dược sĩ tại Việt Nam. |
| Cách lấy | Lần đầu `curl` theo header manifest; sau T25 dùng API có lọc tên/thành phần/loại sản phẩm/đường dùng và chọn ứng viên nhiều bậc. NDC phân trang rồi lưu bản rút gọn, không giữ nguyên phản hồi đầy đủ. |
| Ngày lấy | Header manifest 16/11/2026; 43 nhãn không có ngày riêng, 7 nhãn ghi 17/11; cả 50 mục NDC ghi 17/11. Không coi ngày header là ngày tải lại của mọi tệp. |
| Lệnh tải / xử lý | Đã có trong README T25: `uv run python -m app.kb.fetch openfda --dry-run`, `... openfda`, `... ndc`, `... report`, `uv run python -m app.kb.build`. Đây là lệnh pipeline, **không chạy trong T59** vì ghi dữ liệu/có thể gọi mạng. Lệnh đo chỉ đọc đã chạy nằm cuối tài liệu. |

## 1. Đơn vị dữ liệu

Một `openfda/<ma>.json` hiện chứa một nhãn được chọn trong `results[0]`, gắn một `set_id` của nhà sản xuất; không đại diện mọi nhãn hay mọi dạng dùng của hoạt chất. Có thể là thuốc phối hợp.

Một `openfda_ndc/<ma>.json` chứa nhiều sản phẩm rút gọn trong `san_pham`. Toàn bộ bản lưu hiện có **429 sản phẩm**, không phải 429 hoạt chất; tên NDC không phải số đăng ký thuốc Việt Nam.

Một dòng `chunks.jsonl` là một đoạn văn hoặc một bảng phẳng kèm metadata căn cứ. Kho có **3.730 dòng**, gồm **3.483 văn bản + 247 bảng**, thuộc **50 tài liệu**. Một đoạn có thể liên kết nhiều hoạt chất.

Một dòng SQLite `embeddings` là một véc-tơ cho khóa băm mô hình + loại văn bản + nguyên văn; không phải khóa đoạn. Cache có thể chứa tài liệu, truy vấn, nội dung cũ hoặc mô hình khác. Không thể coi tổng hàng cache là số đoạn hiện đã nhúng.

## 2. Ba tầng tệp

Kích thước byte đo bằng `stat().st_size`, tổng các tệp thường khi là thư mục. Manifest dùng chung nên không cộng toàn bộ byte manifest vào từng nhóm nguồn.

| Tầng | Đường dẫn | Số lượng / kích thước byte | Giữ lâu dài? |
|:--|:--|--:|:--|
| Thô: nhãn | `data/kb_sources/openfda/*.json` | 50 tệp; 6.164.671 | Có, nguồn và mã băm |
| Thô đã rút gọn: NDC | `data/kb_sources/openfda_ndc/*.json` | 50 tệp; 139.242 | Có; không còn toàn bộ trường phản hồi API |
| Siêu dữ liệu chung | `data/kb_sources/manifest.json` | 81.847 | Có; gồm cả mục nguồn khác |
| Trung gian | `LabelDocument`, `LabelSection`, `LabelTable` trong bộ nhớ khi build | Không có tệp nhãn trung gian được pipeline này xuất ra `kb_staging`; không gán byte 0 | Dựng lại từ nguồn |
| Bộ tra RAG | `data/kb_curated/chunks.jsonl` | 3.730 dòng; 9.246.537 | Có, app nạp trực tiếp |
| Bộ đệm nhúng RAG | `data/cache/embeddings.sqlite` | Đo trước T61: 1.022 hàng (mô hình cũ `nvidia/nemotron-3.5-embed-1b:free`); sau T61 dùng `gemini-embedding-2` | Có thể dựng lại; tái dùng phụ thuộc đúng mô hình/nội dung |
| Cache từ điển riêng | `data/cache/embeddings_tu_dien.sqlite` | 0 hàng; 12.288 | Đường riêng của `dictionary/candidates.py`, dùng cùng `build_embedder` |

`data/kb_sources/openfda_api_mau/` là các phản hồi mẫu thăm dò API/fixture kiểm thử, không phải đầu vào build nhãn hoặc corpus đang chạy; không nhập các endpoint sự kiện, thu hồi, thiếu thuốc từ thư mục này vào RAG.

## 3. Trường của từng tệp

✅ ghi rõ đường dùng khi tải/build, báo cáo hoặc runtime. ❌ là chưa có consumer tương ứng sau lưu nguồn; không có nghĩa trường đó không quan trọng về y khoa.

### 3.1. `openfda/*.json`

Hợp khóa dưới đây được quét trên mọi nhãn, kể cả metadata nested và trường bảng; không phải nhãn nào cũng có đủ. Trường nội dung FDA là mảng chuỗi tiếng Anh; trường hậu tố `_table` chứa HTML. `load_label` bỏ các mục trong `_SKIP_FIELDS`; bảng chỉ được xử lý nếu mục văn bản tương ứng được giữ. Mục chưa có bản đồ được giữ ở `khac`, kèm cảnh báo chất lượng.

| Trường | Ý nghĩa | App dùng ở đâu? |
|:--|:--|:--|
| `meta` | Siêu dữ liệu phản hồi API | ❌ load_label không dùng; giữ để kiểm nguồn |
| `meta.disclaimer` | Tuyên bố lưu ý của FDA | ❌ Chỉ lưu nguồn |
| `meta.last_updated` | Ngày cập nhật kho API, khác ngày tải và effective_time nhãn | ❌ Chỉ lưu nguồn |
| `meta.license` | URL giấy phép do API trả | ❌ App không xử lý quyền dùng |
| `meta.results` | Thông tin phân trang phản hồi | ❌ Build nhãn không đọc |
| `meta.results.limit` | Giới hạn bản ghi truy vấn | ❌ Chỉ lưu phản hồi |
| `meta.results.skip` | Vị trí bắt đầu truy vấn | ❌ Chỉ lưu phản hồi |
| `meta.results.total` | Tổng ứng viên API báo cho truy vấn | ❌ Build nhãn không dùng; không phải số nhãn đã lưu |
| `meta.terms` | URL điều khoản API | ❌ Chỉ lưu nguồn |
| `results` | Danh sách nhãn; bản lưu hiện có một nhãn được chọn trong mỗi tệp | ✅ sources/openfda.py:load_label đọc results[0] |
| `results[].abuse` | Lạm dụng thuốc | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].adverse_reactions` | Phản ứng có hại | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].adverse_reactions_table` | Bảng HTML của mục Phản ứng có hại | ✅ load_label phân tích bảng khi mục văn bản tương ứng được giữ |
| `results[].animal_pharmacology_and_or_toxicology` | Dược lý/độc tính trên động vật | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].boxed_warning` | Cảnh báo đóng khung | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].carcinogenesis_and_mutagenesis_and_impairment_of_fertility` | Sinh ung thư, đột biến và ảnh hưởng sinh sản | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].clinical_pharmacology` | Dược lý lâm sàng | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].clinical_pharmacology_table` | Bảng HTML của mục Dược lý lâm sàng | ✅ load_label phân tích bảng khi mục văn bản tương ứng được giữ |
| `results[].clinical_studies` | Nghiên cứu lâm sàng | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].clinical_studies_table` | Bảng HTML của mục Nghiên cứu lâm sàng | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].contraindications` | Chống chỉ định | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].controlled_substance` | Phân loại chất bị kiểm soát | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].dependence` | Lệ thuộc thuốc | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].description` | Mô tả chế phẩm | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].description_table` | Bảng HTML của mục Mô tả chế phẩm | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].dosage_and_administration` | Liều và cách dùng | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].dosage_and_administration_table` | Bảng HTML của mục Liều và cách dùng | ✅ load_label phân tích bảng khi mục văn bản tương ứng được giữ |
| `results[].dosage_forms_and_strengths` | Dạng bào chế và hàm lượng | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].dosage_forms_and_strengths_table` | Bảng HTML của mục Dạng bào chế và hàm lượng | ✅ load_label phân tích bảng khi mục văn bản tương ứng được giữ |
| `results[].drug_abuse_and_dependence` | Lạm dụng và lệ thuộc thuốc | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].drug_and_or_laboratory_test_interactions` | Tương tác thuốc/xét nghiệm | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].drug_interactions` | Tương tác thuốc | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].drug_interactions_table` | Bảng HTML của mục Tương tác thuốc | ✅ load_label phân tích bảng khi mục văn bản tương ứng được giữ |
| `results[].effective_time` | Ngày hiệu lực nhãn dạng YYYYMMDD | ✅ Chọn phiên bản mới nhất; build phiên bản/tiêu đề nguồn |
| `results[].general_precautions` | Thận trọng chung | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].geriatric_use` | Dùng ở người cao tuổi | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].how_supplied` | Quy cách cung cấp | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].how_supplied_table` | Bảng HTML của mục Quy cách cung cấp | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].id` | Định danh bản nhãn SPL | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].indications_and_usage` | Chỉ định và sử dụng | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].information_for_patients` | Thông tin cho người dùng thuốc | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].information_for_patients_table` | Bảng HTML của mục Thông tin cho người dùng thuốc | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].instructions_for_use` | Hướng dẫn sử dụng | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].instructions_for_use_table` | Bảng HTML của mục Hướng dẫn sử dụng | ✅ load_label phân tích bảng khi mục văn bản tương ứng được giữ |
| `results[].labor_and_delivery` | Chuyển dạ và sinh | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].laboratory_tests` | Xét nghiệm cần lưu ý | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].mechanism_of_action` | Cơ chế tác dụng | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].microbiology` | Vi sinh học | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].microbiology_table` | Bảng HTML của mục Vi sinh học | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].nonclinical_toxicology` | Độc tính tiền lâm sàng | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].nonteratogenic_effects` | Ảnh hưởng thai ngoài gây dị tật | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].nursing_mothers` | Dùng khi cho con bú | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].openfda` | Khối định danh/siêu dữ liệu nhãn | ✅ Tải và build đọc các trường con nêu dưới |
| `results[].openfda.application_number` | Số hồ sơ phê duyệt | ❌ Chưa có đường đọc trường này trong app |
| `results[].openfda.brand_name` | Tên thương mại | ✅ Build tiêu đề nhãn/embedding trong load_label; không đọc nhãn thô khi truy xuất |
| `results[].openfda.generic_name` | Tên chung | ✅ Lọc ứng viên, dự phòng phân giải hoạt chất và tiêu đề lúc tải/build |
| `results[].openfda.is_original_packager` | Cờ đóng gói gốc | ❌ Chưa có đường đọc trường này trong app |
| `results[].openfda.manufacturer_name` | Tên nhà sản xuất | ❌ Chưa có đường đọc trường này trong app |
| `results[].openfda.nui` | Định danh NUI | ❌ Chưa có đường đọc trường này trong app |
| `results[].openfda.original_packager_product_ndc` | NDC của đơn vị đóng gói gốc | ❌ Chưa có đường đọc trường này trong app |
| `results[].openfda.package_ndc` | Mã NDC bao gói | ❌ Chưa có đường đọc trường này trong app |
| `results[].openfda.pharm_class_cs` | Nhóm cấu trúc hóa học | ❌ Chưa có đường đọc trường này trong app |
| `results[].openfda.pharm_class_epc` | Nhóm dược lý đã thiết lập | ❌ Chưa có đường đọc trường này trong app |
| `results[].openfda.pharm_class_moa` | Nhóm cơ chế tác dụng | ❌ Chưa có đường đọc trường này trong app |
| `results[].openfda.pharm_class_pe` | Nhóm tác dụng sinh lý | ❌ Chưa có đường đọc trường này trong app |
| `results[].openfda.product_ndc` | NDC sản phẩm | ❌ Chưa có đường đọc trường này trong app |
| `results[].openfda.product_type` | Loại sản phẩm | ✅ fetch/labels.py kiểm loại sản phẩm |
| `results[].openfda.route` | Đường dùng | ✅ fetch/labels.py so đường dùng cấu hình; fetch/report.py báo độ phủ |
| `results[].openfda.rxcui` | Mã RxCUI nguồn gắn | ❌ Chưa có đường đọc trường này trong app |
| `results[].openfda.spl_id` | Định danh SPL | ❌ Chưa có đường đọc trường này trong app |
| `results[].openfda.spl_set_id` | Định danh tập SPL | ✅ load_label dùng dự phòng nếu set_id cấp nhãn thiếu |
| `results[].openfda.substance_name` | Tên chất | ✅ Lọc thành phần và dự phòng phân giải hoạt chất lúc tải/build |
| `results[].openfda.unii` | Định danh UNII | ❌ Chưa có đường đọc trường này trong app |
| `results[].openfda.upc` | Mã UPC | ❌ Chưa có đường đọc trường này trong app |
| `results[].overdosage` | Quá liều | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].package_label_principal_display_panel` | Nhãn chính trên bao bì | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].pediatric_use` | Dùng ở trẻ em | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].pediatric_use_table` | Bảng HTML của mục Dùng ở trẻ em | ✅ load_label phân tích bảng khi mục văn bản tương ứng được giữ |
| `results[].pharmacodynamics` | Dược lực học | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].pharmacodynamics_table` | Bảng HTML của mục Dược lực học | ✅ load_label phân tích bảng khi mục văn bản tương ứng được giữ |
| `results[].pharmacogenomics` | Dược học di truyền | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].pharmacokinetics` | Dược động học | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].pharmacokinetics_table` | Bảng HTML của mục Dược động học | ✅ load_label phân tích bảng khi mục văn bản tương ứng được giữ |
| `results[].precautions` | Thận trọng | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].precautions_table` | Bảng HTML của mục Thận trọng | ✅ load_label phân tích bảng khi mục văn bản tương ứng được giữ |
| `results[].pregnancy` | Thai kỳ | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].recent_major_changes` | Thay đổi chính gần đây | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].recent_major_changes_table` | Bảng HTML của mục Thay đổi chính gần đây | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].references` | Tài liệu tham khảo | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].risks` | Nguy cơ theo mục nguồn | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].set_id` | Định danh tập nhãn để nối phiên bản | ✅ Định danh tài liệu, chọn nhãn, build và nối trích dẫn |
| `results[].spl_medguide` | Hướng dẫn thuốc cho người dùng | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].spl_medguide_table` | Bảng HTML của mục Hướng dẫn thuốc cho người dùng | ✅ load_label phân tích bảng khi mục văn bản tương ứng được giữ |
| `results[].spl_patient_package_insert` | Tờ hướng dẫn trong bao gói | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].spl_patient_package_insert_table` | Bảng HTML của mục Tờ hướng dẫn trong bao gói | ✅ load_label phân tích bảng khi mục văn bản tương ứng được giữ |
| `results[].spl_product_data_elements` | Các thành phần dữ liệu sản phẩm SPL | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].spl_unclassified_section` | Mục SPL chưa phân loại | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].spl_unclassified_section_table` | Bảng HTML của mục Mục SPL chưa phân loại | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].storage_and_handling` | Bảo quản và xử lý | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].storage_and_handling_table` | Bảng HTML của mục Bảo quản và xử lý | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].teratogenic_effects` | Ảnh hưởng gây dị tật | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].use_in_specific_populations` | Dùng ở nhóm đặc biệt | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].use_in_specific_populations_table` | Bảng HTML của mục Dùng ở nhóm đặc biệt | ✅ load_label phân tích bảng khi mục văn bản tương ứng được giữ |
| `results[].version` | Số phiên bản SPL của nguồn | ❌ load_label bỏ mục này; giữ bản nguồn |
| `results[].warnings` | Cảnh báo | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].warnings_and_cautions` | Cảnh báo và thận trọng | ✅ load_label làm sạch/cắt mục; trường ngoài bản đồ được giữ ở mục khac và báo cảnh báo |
| `results[].warnings_and_cautions_table` | Bảng HTML của mục Cảnh báo và thận trọng | ✅ load_label phân tích bảng khi mục văn bản tương ứng được giữ |

Không dùng các mã RxCUI/UNII/ATC suy đoán từ nhãn để thay trục RxNav hiện tại. Nhóm dược lý `pharm_class_*` vẫn được giữ ở nguồn nhưng chưa có consumer trong app; dòng README cũ nói dùng NDC cho “nhóm dược lý” không mô tả bản NDC rút gọn hiện tại.

### 3.2. `openfda_ndc/*.json`

| Trường | Ý nghĩa | App dùng ở đâu? |
|:--|:--|:--|
| `san_pham` | Danh sách sản phẩm đã lọc/bỏ trùng | ✅ coverage/storage.py:_read_ndc duyệt |
| `san_pham[].ten_biet_duoc` | Tên thương mại hoặc null | ❌ Sau khi tải, app chưa dùng cột này để phân giải tên |
| `san_pham[].ten_chung` | Tên chung hoặc null | ❌ Bộ đọc coverage hiện không dùng cột này |
| `san_pham[].ham_luong` | Danh sách thành phần/hàm lượng nguồn ghi | ✅ _read_ndc duyệt để lấy tên chất |
| `san_pham[].ham_luong[].hoat_chat` | Tên chất thành phần | ✅ Coverage khớp hoạt chất sau chuẩn hóa/bỏ muối |
| `san_pham[].ham_luong[].ham_luong` | Chuỗi hàm lượng hoặc null, không suy diễn | ❌ Chưa dùng kiểm liều hoặc chuẩn hóa đơn vị |
| `san_pham[].dang_bao_che` | Dạng bào chế | ❌ Chưa có consumer sau tải |
| `san_pham[].duong_dung` | Danh sách đường dùng | ✅ fetch/runner.py tổng hợp metadata đường dùng lúc ghi; ❌ chưa dùng khi thẩm định |

`fetch/runner.py:_ndc_products` tạo các trường này từ `brand_name`, `generic_name`, `active_ingredients[].name/strength`, `dosage_form` và `route` của API, lọc rồi bỏ trùng theo toàn bộ bản ghi rút gọn. Bản trên đĩa **không có** `results`, `active_ingredients`, `product_ndc` hoặc các trường nhóm dược lý. `coverage/storage.py:_read_ndc` hỗ trợ cả phản hồi gốc và dạng rút gọn; dữ liệu thực hiện dùng dạng thứ hai.

### 3.3. `manifest.json`

| Trường | Ý nghĩa | App dùng ở đâu? |
|:--|:--|:--|
| `ngay_lay` | Ngày lấy chung của lần khởi tạo manifest | ❌ Lưu vết; không tự coi mọi mục đã tải lại ngày này |
| `cach_lay` | Mô tả cách lấy lúc khởi tạo | ❌ Lưu vết |
| `tep` | Danh sách tệp; dùng chung với DDInter cũ | ✅ build lọc nguon; db/sources.py:prepare_kb nạp metadata |
| `tep[].duong_dan` | Đường dẫn tương đối với data/kb_sources | ✅ Fetch kiểm tệp cũ, build mở tệp và kiểm SHA |
| `tep[].nguon` | Mã nguồn openfda_drug_label/openfda_ndc | ✅ Build chọn nhãn; nạp tri_thuc.tai_lieu |
| `tep[].tang_tin_cay` | Tầng 3 của nguồn | ✅ Nạp metadata tài liệu; chunker gán tầng nhãn |
| `tep[].giay_phep` | Ghi chú Public domain (FDA) | ✅ Nạp metadata tài liệu |
| `tep[].ten_goi` | Mã danh mục dùng lấy nhãn/NDC | ✅ Build chọn/sắp xếp tài liệu và giải hoạt chất |
| `tep[].hoat_chat` | Tên hoạt chất khai báo khi lấy | ❌ Lưu vết; build nối theo ten_goi và DrugNameIndex |
| `tep[].generic_name` | Tên chung ghi khi lấy | ❌ Lưu vết; load_label đọc lại tên trong nhãn |
| `tep[].brand_name` | Tên thương mại ghi khi lấy | ❌ Lưu vết; load_label đọc nhãn |
| `tep[].set_id` | Mã tập nhãn; NDC có thể null | ✅ Build dự phòng định danh; prepare_kb nạp tài liệu khi có set_id |
| `tep[].effective_time` | Ngày hiệu lực nhãn | ✅ load_label dùng khi trường nhãn thiếu |
| `tep[].phien_ban_nguon` | Chuỗi phiên bản nguồn đã ghi | ✅ Nạp tri_thuc.tai_lieu |
| `tep[].duong_dung` | Đường dùng lưu vết truy vấn | ❌ Lưu vết; kiểm nhãn dựa vào openfda.route |
| `tep[].bac_truy_van` | Bậc truy vấn thành công, chỉ có ở một số mục | ❌ Lưu vết tải |
| `tep[].truy_van` | Truy vấn không chứa khóa API | ❌ Lưu vết tải |
| `tep[].so_ung_vien` | Số ứng viên lúc tải | ❌ Lưu vết, không phải số sản phẩm sau bỏ trùng |
| `tep[].ngay_lay` | Ngày riêng mục đã tải lại; có thể không có | ❌ Lưu vết |
| `tep[].url_goc` | URL nguồn lưu ở manifest | ✅ Nạp metadata tài liệu; URL chunk được load_label dựng sang DailyMed theo set_id |
| `tep[].sha256` | SHA-256 nội dung tệp đã lưu | ✅ Build xác minh nguồn; fetch quyết định bỏ qua |
| `tep[].kich_thuoc` | Kích thước tệp đã lưu | ❌ Lưu vết; số trong tài liệu đo lại bằng stat |

Các trường ngày/bậc truy vấn/số ứng viên riêng mục có thể thiếu ở nguồn tải trước T25; không tự điền. NDC không phải tài liệu nhãn nên `set_id` và ngày hiệu lực có thể null. Mục DDInter dùng chung manifest được mô tả trong `ddinter.md`.

### 3.4. Trung gian chỉ trong bộ nhớ

Đây là mô hình ở `app/kb/sources/openfda.py`, không phải schema của một tệp staging tồn tại.

| Trường | Ý nghĩa | App dùng ở đâu? |
|:--|:--|:--|
| `tai_lieu_id` | Định danh nhãn | ✅ Build: chunker truyền sang Chunk |
| `ten_goi` | Mã mục cấu hình | ✅ Build: load_label/đối chiếu build |
| `hoat_chat_ids` | Mã hoạt chất đã giải | ✅ Build: chunker gắn metadata |
| `ten_hoat_chat` | Tên INN hiển thị | ✅ Build: chunker dựng văn bản nhúng |
| `set_id` | Mã tập nhãn | ✅ Build: build theo dõi nhãn thiếu ID |
| `phien_ban_nguon` | Ngày hiệu lực nhãn | ✅ Build: build chọn bản mới và chunker lưu nguồn |
| `url_goc` | URL DailyMed | ✅ Build: chunker lưu vào đoạn |
| `ten_hien_thi` | Tên nhãn kèm ngày nguồn | ✅ Build: chunker dựng văn bản nhúng |
| `sections` | Danh sách mục đã xử lý | ✅ Build: chunker duyệt |
| `canh_bao` | Tên trường chưa có bản đồ phân loại | ✅ Build: build ghi báo cáo |
| `sections[].muc` | Nhóm mục chuẩn | ✅ Build: chunker gắn metadata |
| `sections[].duong_dan_muc` | Đường mục/tiểu mục | ✅ Build: chunker tạo mã và ngữ cảnh |
| `sections[].truong_goc` | Tên trường FDA gốc | ❌ Được mô hình giữ; chưa có consumer sau load_label đọc trường này |
| `sections[].van_ban` | Văn bản đã sạch, bớt lặp/Highlights | ✅ Build: chunker chia đoạn |
| `sections[].bang` | Danh sách bảng HTML đã phân tích | ✅ Build: chunker tạo đoạn bảng riêng |
| `sections[].bang[].tieu_de` | Tiêu đề bảng nếu có | ✅ Build: chunker thêm tiêu đề |
| `sections[].bang[].cot` | Tên cột khi bảng đều và không ô gộp | ✅ Build: chunker định dạng bảng |
| `sections[].bang[].dong` | Các dòng khi nhận diện được bảng đều | ✅ Build: chunker định dạng bảng |
| `sections[].bang[].van_ban_phang` | Dạng văn bản của bảng | ✅ Build: chunker dùng khi bảng không cấu trúc được |

### 3.5. `data/kb_curated/chunks.jsonl`

| Trường | Ý nghĩa | App dùng ở đâu? |
|:--|:--|:--|
| `doan_trich_id` | Mã đoạn ổn định từ tài liệu, đường mục, thứ tự và nội dung | ✅ memory_store/hybrid nhận diện đoạn; API dẫn căn cứ; khóa nạp DB |
| `tai_lieu_id` | openfda:<set_id> | ✅ Liên kết tài liệu, báo cáo độ phủ và khóa ngoại DB |
| `muc_cha_id` | Mã mục cha, có thể null theo schema | ✅ Được load_corpus nạp và prepare_kb xuất DB; chưa thấy bước mở rộng cha trong truy xuất hiện tại |
| `nhom_nguon` | Nhóm nhan_thuoc | ✅ core/types.py:matches lọc nguồn và query_builder xây truy vấn |
| `nguon` | Mã openfda | ✅ Coverage chọn nhãn; presenter hiển thị nguồn |
| `tang_tin_cay` | Tầng 3 | ✅ hybrid ưu tiên tầng; presenter công bố nguồn |
| `hoat_chat_ids` | Danh sách mã hoạt chất, một đoạn phối hợp có nhiều mã | ✅ Bộ lọc truy xuất và coverage; không nối chỉ bằng tên tệp |
| `muc` | Nhóm mục lâm sàng như lieu, canh_bao | ✅ query_builder và matches lọc mục; build báo chất lượng |
| `duong_dan_muc` | Đường tiêu đề mục/tiểu mục nguồn | ✅ Tạo mã/embedding khi build và presenter hiển thị vị trí |
| `loai_noi_dung` | van_ban hoặc bang ở kho hiện tại | ✅ Build kiểm chất lượng; load_corpus/DB giữ loại; bảng hiện được lưu phẳng |
| `ngon_ngu` | en ở nhãn nguồn | ✅ Nạp và kiểm kiểu Chunk, xuất DB; chưa có bước dịch nội dung |
| `phien_ban_nguon` | Ngày hiệu lực nhãn dạng chuỗi | ✅ presenter hiển thị phiên bản; xuất DB |
| `url_goc` | Liên kết DailyMed theo set_id | ✅ presenter hiển thị đích căn cứ |
| `noi_dung_goc` | Nguyên văn đã làm sạch hoặc bảng phẳng | ✅ API presenter hiển thị căn cứ; kiểm độ dài/chất lượng |
| `noi_dung_nhung` | Tiêu đề hoạt chất + tài liệu + đường mục + nội dung | ✅ Corpus nhúng, BM25 lập chỉ mục, rerank chấm; khóa cache phụ thuộc nguyên văn |

Không có trường bảng lồng riêng trong JSONL hiện tại: bảng đã được định dạng vào `noi_dung_goc` và `noi_dung_nhung`; không coi đây là bảng liều có cấu trúc hoặc quy tắc đã duyệt.

## 4. Bộ tra và cache SQLite

### 4.1. Nạp corpus khi chạy

`app/retrieval/setup.py:build_retriever` gọi `corpus.load_corpus`, lập BM25 từ `noi_dung_nhung`, dùng `CachedEmbedder` cho véc-tơ tài liệu/truy vấn và `InMemoryVectorStore` cho truy xuất. Khi nhúng thất bại theo `ProviderError`, `index_corpus` vẫn giữ chỉ mục từ khóa. Không có SQLite nội dung nhãn riêng.

Đường nạp DB `app/db/sources.py:prepare_kb` đọc metadata manifest vào `tri_thuc.tai_lieu`, các dòng JSONL vào `tri_thuc.doan_trich`. `read_embeddings` mở cache chỉ đọc và kiểm kiểu/số chiều/giá trị trước nạp véc-tơ. Đây là đường nhập DB, không chứng minh DB ngoài đã được nạp; T59 không kết nối DB.

### 4.2. Schema thực đo

Cả hai SQLite trên đều có bảng `embeddings`; đã chạy `PRAGMA table_info(embeddings)` và `SELECT count(*) FROM embeddings` ở chế độ `mode=ro`.

| Cột | Kiểu / khóa | Ý nghĩa | App dùng ở đâu? |
|:--|:--|:--|:--|
| `key` | TEXT, khóa chính | SHA-256 của chuỗi `model_id\nkind\ntext`; `kind` là `doc` hoặc `query` | ✅ `providers/cached_embedder.py:_key/_embed` đọc/ghi; `db/sources.py:read_embeddings` tái tạo khóa doc |
| `dims` | INTEGER | Số chiều véc-tơ | ✅ Cache kiểm khớp nhà cung cấp; DB loader kiểm chiều |
| `vec` | BLOB | Mảng float32 lưu byte | ✅ Cache đọc bằng NumPy, DB loader kiểm trước xuất DB |

| Tệp | Số hàng | Chiều thực | Số byte BLOB mỗi hàng |
|:--|--:|--:|--:|
| `embeddings.sqlite` | 1.022 | 2.048 | 8.192 |
| `embeddings_tu_dien.sqlite` | 0 | Không có hàng | Không có hàng |

Với mô hình cũ `nvidia/nemotron-3.5-embed-1b:free` (đo trước T61), khóa `doc` theo `noi_dung_nhung` khớp **819/3.730 đoạn**, còn **2.911 đoạn không có khóa tương ứng**. Đây chỉ là kiểm hiện diện khóa, chưa xác minh chất lượng ngữ nghĩa hoặc tính hữu hạn của từng véc-tơ. Các hàng cache còn lại chưa được phân loại theo nguồn/mô hình; không kết luận toàn corpus đã nhúng.

### 4.2b. Kết quả nhúng thật (T62, 19/11/2026)

- Đã xoá 1.042 hàng nemotron (cache cũ, 2048 chiều) trong `data/cache/embeddings.sqlite`. Lệnh `--xoa-cache-cu` báo số dòng nhưng không xoá được tệp (WinError 32: tiến trình uvicorn của người dùng đang giữ tệp), nên dùng `DELETE` SQL rồi `VACUUM`.
- Nhúng `data/kb_curated/chunks.jsonl` bằng `gemini-embedding-2`: **3.730/3.730 đoạn có vector, 0 lỗi**. Cache sau nhúng: 3.730 hàng, tất cả `dims = 2048`, `vec` đúng 8.192 byte.
- `embeddings_tu_dien.sqlite` cũ (0 hàng) chuyển sang `data/_luu_tru/embeddings_tu_dien_nemotron_2026-11-19.sqlite`; cache từ điển mới do `dictionary candidates --embedder that` tạo: 22.058 hàng.
- Rerank qua OpenRouter đang lỗi HTTP 402 (hết credit); RAG lùi về thứ tự RRF. Xem plan/reports/T62.md.

### 4.3. Mô hình nhúng hiện hành và lệnh nhúng cache (T61, 19/11/2026)

Từ T61, cấu hình `config/settings.yaml` chuyển `embedding.provider` từ `openrouter` (`nvidia/nemotron-3.5-embed-1b:free`) sang **`gemini`** với mô hình **`gemini-embedding-2`** (`dimensions: 2048`, `batch_size: 100`, giữ nguyên `cache_path: "data/cache/embeddings.sqlite"`).

- Giao diện gọi API: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents` với header `x-goog-api-key` đọc qua `get_secret("GEMINI_API_KEY")`. Tài liệu dùng `taskType: "RETRIEVAL_DOCUMENT"`, truy vấn dùng `taskType: "RETRIEVAL_QUERY"`.
- Khoá băm trong `CachedEmbedder` gắn theo `model_id` (`sha256("{model_id}\n{kind}\n{text}")`), nên khoá của `gemini-embedding-2` tách biệt hoàn toàn với `nvidia/nemotron-3.5-embed-1b:free`. Thiếu `GEMINI_API_KEY` khi chạy RAG vẫn lùi về tìm theo từ khoá BM25 mà không lỗi.
- **Lệnh nhúng kho đoạn và dọn cache cũ** (`app/retrieval/embed_corpus.py`, T61 chưa chạy nhúng thật nên chưa ghi số hàng mới trên đĩa):
  - Xoá tệp cache cũ khi các khoá cũ không thuộc mô hình hiện tại (chỉ xoá khi có cờ này, in số dòng trước khi xoá):
    `uv run python -m app.retrieval.embed_corpus --xoa-cache-cu`
  - Nhúng thử ít đoạn (ví dụ 20 đoạn đầu):
    `uv run python -m app.retrieval.embed_corpus --limit 20`
  - Nhúng toàn bộ `data/kb_curated/chunks.jsonl` qua `CachedEmbedder` (chạy tiếp được sau khi dừng vì đoạn đã có trong cache sẽ được bỏ qua; in tiến độ và tổng số đoạn / số đoạn đã có vector / số đoạn lỗi):
    `uv run python -m app.retrieval.embed_corpus`

### 4.4. Kết quả đo tìm kiếm (T64, 19/11/2026)

Bộ 50 câu hỏi dược sĩ (Việt và Anh, 41 hoạt chất, 9 mục, 9 câu khó) ở `data/kb_reports/T64_bo_cau_hoi.json`; báo cáo đầy đủ `plan/reports/T64.md`. Đo trên 3.730 đoạn, không lọc, véc-tơ `gemini-embedding-2` (RETRIEVAL_QUERY, 2048 chiều).

| Cấu hình | recall@5 Việt / Anh | top-1 Việt / Anh | MRR Việt / Anh |
|:--|:-:|:-:|:-:|
| Chỉ vector (cosine) | 0,96 / 1,00 | 0,68 / 0,76 | 0,81 / 0,86 |
| Đường lai của app (BM25 + vector + RRF; rerank app lỗi 402 nên chỉ là RRF) | 0,86 / 0,92 | 0,28 / 0,62 | 0,52 / 0,74 |
| Lai, BM25 chỉ chạy với câu Anh | 0,96 / 0,92 | 0,68 / 0,62 | 0,81 / 0,74 |
| Vector + rerank nemotron (chỉ 29 câu đầu: hết hạn mức ngày) | 1,00 / 1,00 | 0,83 / 0,79 | 0,90 / 0,88 |
| Lai + rerank nemotron (chỉ 29 câu đầu) | 1,00 / 1,00 | 0,83 / 0,79 | 0,91 / 0,88 |

Kết luận: vector một mình tốt hơn đường lai hiện tại, nhất là câu Việt (BM25 kéo đoạn của thuốc/mục khác lên); rerank chỉ nâng hạng đầu nhẹ trên mẫu nhỏ và chạm hạn mức ngày của gói miễn phí OpenRouter. Đề xuất mặc định: vector trong bộ lọc hoạt chất, BM25 chỉ làm đường lui khi nhúng lỗi. Nhãn `muc` còn nhiễu (362 đoạn `khac`) nên nhiều câu sai là "đúng thuốc, sai mục".

## 5. Kết quả kiểm đã có

- Lệnh đo chỉ đọc ngày 19/11: số SHA-256 lệch manifest bằng 0 ở cả nhãn và NDC; 50 `set_id` khác nhau; JSONL không có mã đoạn trùng hoặc danh sách hoạt chất rỗng.
- `openfda_fetch_openfda.json`: 43 `bo_qua`, 7 `da_lay`; `openfda_fetch_ndc.json`: 46 `bo_qua`, 4 `da_lay`. Đây là kết quả tải đã lưu, không phải T59 vừa tải.
- `openfda_build_20261117_030156.json`: chất lượng đạt; 3.730 đoạn; số vượt giới hạn, dưới 50 ký tự, hoạt chất rỗng và ID trùng đều 0. Có 16 cảnh báo Q3; nhãn amikacin, ceftriaxone, gentamicin, levetiracetam thiếu mục tương tác. Đạt kỹ thuật không đồng nghĩa nội dung đủ căn cứ cho mọi ca.
- Báo cáo build cuối ghi mốc trước 3.738 đoạn, 633 mã cũ bị thay và 0 mã đổi khi nội dung/đường mục không đổi. Kho hiện tại khớp 3.730, nên không dùng số 3.738 của `plan/reports/T25.md` làm số hiện hành.
- T25 ban đầu bị lỗi mạng; T25-fix-3 báo kiểm thử/lint qua sau phân loại phản hồi sai cấu trúc. Không chạy lại test phần mềm trong task chỉ viết mô tả dữ liệu.
- `data/kb_sources/README.md` còn đúng về nguồn nhãn Mỹ, một nhãn theo nhà sản xuất, quy tắc không suy diễn và pipeline T25; các dòng “46 NDC”, “còn 4 NDC thiếu”, “42 nhãn đúng/cần tải lại 8” là lịch sử đã thay đổi theo artifact tải và dữ liệu hiện có.

## 6. Việc còn mở

- Dược sĩ chốt danh mục và đường dùng, đặc biệt methotrexate trong cấu hình vẫn cần quyết định; không biến chỉ dấu văn bản thận/gan thành quy tắc liều tự động.
- Đánh giá/duyệt các mục tương tác còn thiếu và cảnh báo Q3, chất lượng bảng phẳng, độ phù hợp nhãn Mỹ với chế phẩm Việt Nam.
- Khi có brief cho phép nhúng, bổ sung cache còn thiếu cho đúng mô hình và văn bản; không suy ra cache đầy từ tổng số hàng.
- Giữ phân biệt NDC rút gọn với phản hồi API gốc; nếu đổi schema, cập nhật tài liệu và các consumer cùng lúc.
- Không suy ra phạm vi lâm sàng chỉ từ việc có đoạn hoặc metadata; dược sĩ vẫn quyết định.

## Cách kiểm lại

Chạy từ gốc dự án bằng PowerShell. Đây là **nguyên lệnh đã chạy** để đo byte, số dòng, hợp trường, mã băm, schema SQLite và độ khớp khóa nhúng. Chỉ mở SQLite `mode=ro`, không gọi mạng hoặc build/embed.

```powershell
$env:PYTHONIOENCODING='utf-8'
@'
import collections, hashlib, json, sqlite3
from pathlib import Path
def fields(value, prefix='', result=None):
    result = set() if result is None else result
    if isinstance(value, dict):
        for key, child in value.items():
            path = f'{prefix}.{key}' if prefix else key
            result.add(path)
            fields(child, path, result)
    elif isinstance(value, list):
        for child in value:
            fields(child, prefix + '[]', result)
    return result
root = Path('.')
manifest_path = root / 'data/kb_sources/manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
print('manifest_bytes_header', manifest_path.stat().st_size, {k: v for k, v in manifest.items() if k != 'tep'})
for name, source in (('openfda', 'openfda_drug_label'), ('openfda_ndc', 'openfda_ndc')):
    paths = sorted((root / 'data/kb_sources' / name).glob('*.json'))
    payloads = [json.loads(p.read_text(encoding='utf-8-sig')) for p in paths]
    entries = [e for e in manifest['tep'] if e.get('nguon') == source]
    print(name, 'files_bytes', len(paths), sum(p.stat().st_size for p in paths))
    print('json_fields', sorted(set().union(*(fields(x) for x in payloads))))
    print('manifest_entries_fields_dates', len(entries), sorted(set().union(*(fields(x) for x in entries))), dict(collections.Counter(e.get('ngay_lay', 'header:' + manifest['ngay_lay']) for e in entries)))
    print('manifest_sha_mismatches', sum(hashlib.file_digest((root / 'data/kb_sources' / e['duong_dan']).open('rb'), 'sha256').hexdigest() != e['sha256'] for e in entries))
    if name == 'openfda':
        print('labels_set_ids', sum(len(x.get('results', [])) for x in payloads), len({y.get('set_id') for x in payloads for y in x.get('results', [])}))
    else:
        print('products', sum(len(x.get('san_pham', [])) for x in payloads))
path = root / 'data/kb_curated/chunks.jsonl'
chunks = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
print('chunks_bytes_rows_labels', path.stat().st_size, len(chunks), len({x['tai_lieu_id'] for x in chunks}))
print('chunk_fields', sorted(set().union(*(fields(x) for x in chunks))))
print('chunk_types_sections', dict(collections.Counter(x['loai_noi_dung'] for x in chunks)), dict(collections.Counter(x['muc'] for x in chunks)))
print('chunk_duplicate_ids_empty_actives', len(chunks) - len({x['doan_trich_id'] for x in chunks}), sum(not x['hoat_chat_ids'] for x in chunks))
for name in ('embeddings.sqlite', 'embeddings_tu_dien.sqlite'):
    path = root / 'data/cache' / name
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        print(name, 'bytes', path.stat().st_size, 'pragma', db.execute('PRAGMA table_info(embeddings)').fetchall(), 'count', db.execute('SELECT count(*) FROM embeddings').fetchone()[0])
        print('dims_vector_bytes', db.execute('SELECT dims,count(*),min(length(vec)),max(length(vec)) FROM embeddings GROUP BY dims').fetchall())
        if name == 'embeddings.sqlite':
            model = 'nvidia/nemotron-3.5-embed-1b:free'
            matched = sum(db.execute('SELECT EXISTS(SELECT 1 FROM embeddings WHERE key=?)', (hashlib.sha256(f'{model}\ndoc\n{x["noi_dung_nhung"]}'.encode()).hexdigest(),)).fetchone()[0] for x in chunks)
            print('matching_current_document_keys', model, matched, 'missing', len(chunks) - matched)
for name in ('openfda_fetch_openfda.json', 'openfda_fetch_ndc.json', 'openfda_build_20261117_030156.json'):
    payload = json.loads((root / 'data/kb_reports' / name).read_text(encoding='utf-8-sig'))
    print('report', name, dict(collections.Counter(x['trang_thai'] for x in payload)) if isinstance(payload, list) else payload)
'@ | .venv/Scripts/python.exe -
```


## Phụ lục: nhãn bổ sung cho dị ứng chéo (T60, 19/11/2026)

26 nhãn được tải thêm vào `data/kb_sources/openfda_d3/` (kèm `manifest.json`: truy vấn, `set_id`, `effective_time`, sha256, kích thước, ngày lấy), gồm penicillin, cephalosporin, carbapenem, aztreonam, NSAID, thuốc chống động kinh, sulfasalazine. Khác nhãn trong `openfda/`: **không** đưa vào `chunks.jsonl`, không nhúng; chỉ dùng làm câu trích nguyên văn cho `data/kb/di_ung_cheo.json`. Chi tiết và danh sách ở [di-ung-cheo.md](di-ung-cheo.md).
