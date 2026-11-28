# FIX-CI-VA-HINH-TRUNG – CI đỏ trên `vukhai248`; hình vẽ trùng; lỗi định dạng làm mất câu trả lời; tool gọi lặp; hiển thị số và đơn vị

Người làm: Codex `gpt-6.1-terra` xhigh. Được chạy ruff, pytest, vitest, tsc, git (chỉ `git worktree add` vào thư mục tạm để tái hiện CI). **Không** đọc `.env`, không mạng ngoài, không cài gói, không commit, không push.

## A. CI đỏ (GitHub Actions `CI`, cả ubuntu và windows)

CI đỏ từ `0ce1f2f`. Lần xanh cuối là `5883a8a`. Mọi lần chạy cùng 11 test trượt:

```
FAILED tests/agent/test_minh_hoa_do_thi.py::test_drawing_rounds_preserve_successful_block - assert 0 == 1
FAILED tests/agent/test_minh_hoa_do_thi.py::test_drawing_rejection_list_is_not_recorded_in_llm_trace - assert 'nguon_khong_hop_le' in '...'
FAILED tests/agent/test_minh_hoa_do_thi.py::test_fourth_drawing_round_prompts_for_answer - assert 0 == 1
FAILED tests/agent/test_minh_hoa_do_thi.py::test_duplicate_drawing_then_different_layer - assert [] == ['mh-1', 'mh-2']
FAILED tests/agent/test_minh_hoa_do_thi.py::test_graph_returns_verified_block_and_grid - assert 0 == 1
FAILED tests/agent/test_minh_hoa_do_thi.py::test_retry_preserves_previous_block - assert 0 == 1
FAILED tests/agent/test_minh_hoa_do_thi.py::test_retry_keeps_only_new_block - assert 0 == 1
FAILED tests/agent/test_minh_hoa_do_thi.py::test_api_case_returns_block_without_saving_it - assert 0 == 1
FAILED tests/agent/test_minh_hoa_do_thi.py::test_duplicate_drawing_and_forced_answer_are_traced - assert 0 == 1
FAILED tests/agent/test_minh_hoa_do_thi.py::test_missing_figure_filter_in_verified_answer - assert []
FAILED tests/db/test_roles_sql.py::test_roles_sql_has_rls_policies_matching_grants - {('DELETE','...m_dinh'),...} == {('DELETE','...vu.phan_hoi')}
```

1. **10 test minh hoạ:** chạy ở máy dev thì qua, trên CI thì trượt. Trên CI `cong_cu_da_goi=['tinh_chi_so','tra_thuoc']`, không có hình. Nghi test phụ thuộc tệp dữ liệu chỉ có ở máy dev (bị `.gitignore`, ví dụ `data/kb_curated/**`, `data/cache/**`).
   - **Tái hiện như CI:** `git worktree add %TEMP%\ci-repro HEAD`, tạo venv trong đó (`uv sync` dùng cache sẵn có, không tải mạng nếu được; không được thì báo), chạy `uv run pytest tests/agent/test_minh_hoa_do_thi.py tests/db/test_roles_sql.py` **trong worktree đó**.
   - **Sửa test** cho tự đủ: dựng dữ liệu tool bằng fixture/stub trong test, không phụ thuộc tệp ngoài Git. Không giảm ý test. Nếu mã sản phẩm thật sự sai khi thiếu dữ liệu (ví dụ ném ngoại lệ) thì sửa mã cho an toàn và ghi rõ.
2. **`test_roles_sql`:** đợt TR2a thêm `GRANT INSERT, SELECT, DELETE` trên `nghiep_vu.vet_chay`, `vet_buoc` cho `bvienx_app` ở `db/roles.sql`, nhưng không có chính sách RLS tương ứng. Test yêu cầu mỗi grant có chính sách khớp.
   - Đọc cách kho xử lý các bảng ghi bởi dịch vụ (không theo người dùng) và chọn **một** cách:
     - (a) thêm `ENABLE ROW LEVEL SECURITY` + chính sách cho `bvienx_app` trên hai bảng vết, đúng mẫu hiện có;
     - (b) nếu kho có cơ chế miễn trừ rõ ràng cho bảng hệ thống, dùng cơ chế đó, kèm lý do.
   - Nếu chọn (a): ghi trong báo cáo **câu SQL Claude phải chạy trên RDS** (Claude chạy bằng tài khoản chủ), và bảo đảm ghi vết từ app vẫn chạy (`sink_db.py` insert/delete).
3. Sau khi sửa: chạy lại toàn bộ `uv run pytest -q` **trong worktree tái hiện**. Phải xanh. Xoá worktree tạm khi xong (`git worktree remove`).

## B. Hình vẽ trùng (vết `c0163f8e` trên bản deploy, DEMO-02 "Vẽ biểu đồ creatinin theo thời gian")

Mô hình (`gemini-3.5-flash-lite`) gọi `lay_du_lieu_ca` 3 lần cùng tham số, rồi `ve_bieu_do` 2 lần với **đặc tả y hệt**, cả hai `ok`, giao diện hiện 2 hình giống nhau. Lần thứ 3 `tu_choi`. Mô hình lặp là lỗi của mô hình, nhưng mã phải chặn:

4. **Chốt hình trùng** (`ve_bieu_do`/Gateway): đặc tả mới, sau khi chuẩn hoá (bỏ khác biệt thứ tự khoá), trùng một khối đã nhận trong lượt (cùng bộ dữ liệu theo nội dung, không chỉ theo mã `ds-n`) thì **không thêm khối**. Trả LLM `ok` ngắn "đã vẽ ở mh-1, không vẽ lại", không tính là lỗi. Test với đúng chuỗi trên.
5. **Tool gọi lặp:** trong một lượt, gọi lại cùng tool với tham số giống hệt (đã chuẩn hoá) thì trả **kết quả cũ** (cùng `ds-n`, không tạo bộ dữ liệu mới), kèm ghi chú ngắn cho LLM "kết quả đã có ở lần gọi trước". Có tính vào trần lời gọi hay không: chọn và ghi lý do. Áp dụng cho các tool chỉ đọc. Test.

## C. Lỗi định dạng làm mất câu trả lời (vết `28919045`)

Đã vẽ 1 hình, rồi các vòng sau LLM trả JSON sai lược đồ 2 lần, dẫn tới `loi` "Đầu ra sai định dạng" và dược sĩ mất cả câu trả lời.

6. Khi hết số lần sai lược đồ cho phép, **không** trả `ERROR_MESSAGE`. Chuyển sang lượt "trả lời thận trọng" (`tra_loi_trung_thuc`, đã có), dùng kết quả tool và hình đã có. Câu trả lời thận trọng qua kiểm chứng thì gắn kèm `minh_hoa` đã dựng. Chỉ khi chính lượt thận trọng cũng lỗi mới trả `ERROR_MESSAGE`. Bước tiến trình: "Đầu ra sai định dạng, chuyển sang trả lời thận trọng" ở trạng thái `xong`. Test cho cả hai nhánh.

## D. Hiển thị

7. Số trong câu trả lời hiện "150.0 umol/L". Định dạng số do code đưa vào văn bản tool hoặc tóm tắt cho LLM: bỏ `.0` thừa, dùng dấu thập phân kiểu Việt khi có phần lẻ (`16,0` → `16`; `2,5` giữ). Không đổi giá trị trong `bo_du_lieu`. Bộ kiểm chứng số vẫn khớp (đã nhận cả `,` và `.`; kiểm lại bằng test).
8. Trục y hình đường chưa có đơn vị (VZ2-fix-4 còn sót). Trong `lay_du_lieu_ca`, khi mọi dòng của một chỉ số cùng đơn vị, gán `don_vi` cho cột `gia_tri` của bộ dữ liệu. Web hiện "Giá trị (umol/L)". Test pytest + vitest.

## Tệp

`tests/agent/**`, `tests/db/**`, `db/roles.sql`, `db/vet.sql` (nếu chọn RLS), `app/agent/tools/**`, `app/agent/nodes.py`, `app/agent/minh_hoa/**`, `app/orchestration/ask.py`, `web/src/features/minh-hoa/**`, `tests/orchestration/**`. Báo cáo: `plan/briefs/FIX-CI-VA-HINH-TRUNG-bao-cao.md` (kèm câu SQL cho RDS nếu có).
**Cấm:** đọc `.env`, mạng (trừ khi `uv sync` buộc tải; khi đó dừng và báo), cài gói, commit, push, sửa `app/verify` (trừ khi mục 7 bắt buộc, phải ghi lý do), chạy SQL trên DB thật.

## Nghiệm thu (Claude chạy)

```
uv run ruff check app tests && uv run ruff format --check app tests/agent tests/db tests/orchestration
PYTHON_DOTENV_DISABLED=1 uv run pytest -q -p no:cacheprovider tests
cd web && npx tsc -b --noEmit && npx oxlint && npx vitest run && npx vite build
```
Rồi push để CI chạy. CI phải xanh cả hai hệ điều hành.
