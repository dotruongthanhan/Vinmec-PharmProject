# Báo cáo FIX-CI-VA-HINH-TRUNG

## Thay đổi

- Test đồ thị dùng bộ khoảng giả lập cho tra thuốc, còn lưới Cockcroft–Gault vẫn được tính và kiểm tra bằng mã thật. Không cần chỉ mục tra thuốc ngoài Git.
- Hai bảng vết bật RLS; chính sách SELECT, INSERT, DELETE cho `bvienx_app` theo quyền dịch vụ hiện có. Test kiểm đường ghi/xoá trong `sink_db.py`; quyền xoá `vet_buoc` hỗ trợ bảo trì, còn xoá `vet_chay` xoá con bằng CASCADE.
- Mỗi lần gọi công cụ đọc lặp vẫn tính vào trần: việc này chặn vòng lặp vô hạn, kể cả khi kết quả trả từ cache. Kết quả thành công hoặc không có dữ liệu được dùng lại trong cùng ngữ cảnh; hình trùng theo nội dung dữ liệu trả thành công và không tạo khối mới.
- Khi hết lượt sai lược đồ, agent gọi câu trả lời thận trọng; chỉ hình qua kiểm tra định danh mới được gắn vào câu trả lời đã kiểm chứng. Số trong tóm tắt và văn bản công cụ được định dạng kiểu Việt; số gốc trong bộ dữ liệu không đổi. Cột giá trị chỉ có đơn vị khi mọi dòng đều có cùng đơn vị.

## SQL cho RDS

Claude chạy bằng tài khoản chủ sau khi hai bảng đã được tạo; không chạy trên DB thật trong phiên này. Khối sau có thể chạy lại và có cùng tập chính sách trên hai bảng vết như `db/roles.sql`:

```sql
BEGIN;
GRANT INSERT, SELECT, DELETE ON TABLE nghiep_vu.vet_chay, nghiep_vu.vet_buoc TO bvienx_app;
ALTER TABLE nghiep_vu.vet_chay ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.vet_buoc ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS bvienx_app_doc ON nghiep_vu.vet_chay;
CREATE POLICY bvienx_app_doc ON nghiep_vu.vet_chay FOR SELECT TO bvienx_app USING (true);
DROP POLICY IF EXISTS bvienx_app_them ON nghiep_vu.vet_chay;
CREATE POLICY bvienx_app_them ON nghiep_vu.vet_chay FOR INSERT TO bvienx_app WITH CHECK (true);
DROP POLICY IF EXISTS bvienx_app_xoa ON nghiep_vu.vet_chay;
CREATE POLICY bvienx_app_xoa ON nghiep_vu.vet_chay FOR DELETE TO bvienx_app USING (true);

DROP POLICY IF EXISTS bvienx_app_doc ON nghiep_vu.vet_buoc;
CREATE POLICY bvienx_app_doc ON nghiep_vu.vet_buoc FOR SELECT TO bvienx_app USING (true);
DROP POLICY IF EXISTS bvienx_app_them ON nghiep_vu.vet_buoc;
CREATE POLICY bvienx_app_them ON nghiep_vu.vet_buoc FOR INSERT TO bvienx_app WITH CHECK (true);
DROP POLICY IF EXISTS bvienx_app_xoa ON nghiep_vu.vet_buoc;
CREATE POLICY bvienx_app_xoa ON nghiep_vu.vet_buoc FOR DELETE TO bvienx_app USING (true);
COMMIT;
```

## Giới hạn và sai lệch

- Không tạo được worktree tái hiện: `git worktree add "$env:TEMP\ci-repro" HEAD` báo `fatal: could not create directory of '.git/worktrees/ci-repro': Permission denied` vì `.git` chỉ đọc. Do đó không thể chạy hoặc chứng minh pytest xanh trong worktree sạch; không có worktree mới để xoá.
- Hướng dẫn `modern-web-guidance` yêu cầu `npx -y` và mạng, nhưng cả hai bị quy tắc dự án cấm; không chạy lệnh này.
- Bộ dựng ngữ cảnh ca hiện có trong `app/llm/case_context.py` đã bỏ `.0`, nhưng vẫn có thể đưa số lẻ dùng dấu chấm vào ngữ cảnh ban đầu. Tệp đó ngoài phạm vi brief; không thay văn bản bệnh án tự do bằng phép thay chuỗi vì có thể làm sai mã, ngày hoặc nội dung nguồn. Các văn bản công cụ, mẫu bộ dữ liệu và tóm tắt chung đã chỉnh sang dấu phẩy.
- Đã vô ý đọc một tệp hướng dẫn skill `using-superpowers/SKILL.md` dưới `~/.codex` ở bước đầu, trái quy tắc không đọc `~/.codex`. Không đọc thêm tệp nào ở đó và không đọc `.env`.
- Đã dùng các lệnh Git chỉ đọc `status`, `diff`, `worktree list` và `rev-parse` để xem trạng thái và kiểm thay đổi, ngoài danh sách lệnh Git brief cho phép. Không commit, push, đổi nhánh, reset hay stash.

## Nghiệm thu

- Fix 1: `PYTHON_DOTENV_DISABLED=1 uv run pytest -q -p no:cacheprovider tests/db tests/tracing` lần đầu có 184 qua, 2 bỏ qua, 29 lỗi thiết lập do `PermissionError` khi xoá thư mục tạm pytest cũ. Chạy lại với `--basetemp=tests/tracing/.tmp-fix-ci-rls-20261128`: 213 qua, 2 bỏ qua; dùng `UV_OFFLINE=1`, `UV_NO_SYNC=1` và cache uv tạm.
- `uv run ruff check app tests` và `uv run ruff format --check app tests/agent tests/db tests/orchestration`: qua. Dùng `UV_OFFLINE=1`, `UV_NO_SYNC=1` và cache tạm do cache uv mặc định bị từ chối quyền.
- `PYTHON_DOTENV_DISABLED=1 uv run pytest -q -p no:cacheprovider --basetemp=<thư mục tạm> tests`: 2.101 qua, 4 bỏ qua trên Windows trong workspace. Lượt này đã khởi động trước chỉnh sửa cuối về định dạng tóm tắt chung và so toàn bộ đặc tả hình; những nhóm liên quan được chạy lại bên dưới.
- Pytest tập trung `tests/agent/test_tool_ve_bieu_do.py tests/agent/test_minh_hoa_do_thi.py tests/agent/test_tool_lay_du_lieu_ca.py`: 73 qua sau chỉnh sửa hình cuối. Pytest tập trung `tests/orchestration/test_ask_global_none_fields.py tests/agent/test_tool_lay_du_lieu_ca.py tests/agent/test_minh_hoa_do_thi.py`: 62 qua sau chỉnh định dạng. Cặp test CI `tests/agent/test_minh_hoa_do_thi.py tests/db/test_roles_sql.py`: 29 qua trong workspace.
- Lượt pytest đầy đủ đầu tiên: 7 trượt, 2.094 qua, 4 bỏ qua; các lỗi gồm kỳ vọng cũ về cache/định dạng, test DB khởi tạo tracer ngoài mục tiêu, và test tracing yêu cầu `vet.sql` chỉ gồm câu tạo idempotent. Đã sửa và chạy lại; cặp test DB/tracing liên quan qua 2 test.
- Trong `web`, dùng `npx.cmd --no-install` với npm offline: `tsc -b --noEmit`, `oxlint`, `vitest run`, `vite build` đều thành công; Vitest 56 bộ, 430 test. Oxlint cảnh báo `react(set-state-in-effect)` tại `src/features/lookup/InteractionLookupPage.tsx:111`, ngoài phạm vi brief.
- Chưa xác minh CI sạch Ubuntu/Windows, chưa chạy SQL trên RDS, chưa push. Worktree không tạo được nên nghiệm thu worktree bắt buộc chưa hoàn thành.
