# T94 – Job CI bảo mật (quét CVE, quét khoá) và bật luật bảo mật `S` của ruff (C5, mục 5.2 báo cáo)

Nguồn: `docs/bao-cao-bao-mat-2026-11-20.md` mục C5 và 5.2. Agent: agy `gemini-4-hydrogen-xhigh`. **Không gọi shell, không gọi mạng; chỉ đọc và ghi tệp.**

Không cài gói nào: hai công cụ quét chạy trong GitHub Actions; luật `S` có sẵn trong ruff.

## 1. Tạo `.github/workflows/security.yml`

Giá trị Claude đã tra ngày 20/11/2026 (`gh api`); chép đúng từng ký tự:

| Action | Ghim |
| :-- | :-- |
| OSV-Scanner (reusable workflow) | `google/osv-scanner-action/.github/workflows/osv-scanner-reusable.yml@32d3cd482bdadfb38b186c0ad1b031902d55d932 # v2.7.1` |
| Gitleaks | `gitleaks/gitleaks-action@e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e # v3.0.0` |
| Checkout (đã ghim ở T92) | `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7` |

Nội dung:

- `name: security`; `on`: `push`, `pull_request` (nhánh `main`, `vukhai248`), `schedule` hằng tuần (`cron: "17 2 * * 1"`), `workflow_dispatch`.
- `permissions: contents: read` ở cấp đầu.
- Job `osv` dùng reusable workflow trên (`uses:` ở cấp job), `with`:
  - `scan-args: |-` hai dòng `--lockfile=uv.lock` và `--lockfile=web/package-lock.json`;
  - `fail-on-vuln: true`.
  - `permissions` của job: `actions: read`, `contents: read`, `security-events: write` (workflow con cần để tải SARIF).
- Job `gitleaks` (`runs-on: ubuntu-latest`): checkout với `fetch-depth: 0`, rồi gitleaks-action, `env: GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}`. Kho thuộc tài khoản cá nhân nên không cần `GITLEAKS_LICENSE` (ghi chú một dòng trong tệp).
- Không `pull_request_target`, không tiêm `${{ github.event.* }}` vào `run:`.

Nếu có dương tính giả biết trước (chuỗi giả trong test như `db.invalid`, `mk-bi-mat`), tạo `.gitleaks.toml` với `[extend] useDefault = true` và `[allowlist]` theo **đường dẫn** `tests/` cụ thể; không tắt luật toàn cục.

## 2. Bật luật `S` của ruff

`pyproject.toml` mục `[tool.ruff.lint]`: thêm `"S"` vào `select` (giữ các nhóm hiện có). Thêm:

- `ignore`: `S101` (assert) – ghi chú lý do: 55 assert trong `app/` là bất biến nội bộ, xử lý ở đợt sau.
- `per-file-ignores`: `"tests/**" = ["S"]`, `"notebooks/**" = ["S"]` nếu thư mục có.

Sửa 16 lỗi còn lại trong `app/` và `tools/` (Claude đã đếm: S608×4, S311×4, S110×4, S324×2, S105×1, S112×1). Với mỗi lỗi:

- **S608** (SQL ghép chuỗi): nếu chỉ ghép tên bảng/cột là hằng trong mã → `# noqa: S608` kèm lý do ngắn trên cùng dòng; nếu ghép dữ liệu từ người dùng → **dừng, ghi báo cáo**, không tự sửa.
- **S311** (`random` không mật mã): nếu dùng cho jitter/thử lại/mẫu dữ liệu → `# noqa: S311` kèm lý do; nếu dùng tạo mã, token, id bí mật → đổi sang `secrets`.
- **S110/S112** (`except: pass/continue`): thêm `logger.debug(...)` hoặc thu hẹp ngoại lệ; giữ hành vi.
- **S324** (`md5/sha1`): nếu chỉ làm khoá bộ đệm/băm nội dung → thêm `usedforsecurity=False`; nếu dùng cho bảo mật → dừng, báo cáo.
- **S105**: nếu là tên trường/hằng không phải mật khẩu thật → `# noqa: S105` kèm lý do; nếu là bí mật thật → dừng, báo cáo **không chép giá trị**.

Liệt kê từng lỗi (tệp:dòng → cách xử lý) trong báo cáo.

## Phạm vi

Tạo: `.github/workflows/security.yml`, `.gitleaks.toml` (nếu cần). Sửa: `pyproject.toml` (chỉ mục ruff), các tệp `app/`, `tools/` có lỗi S (chỉ dòng liên quan). Cấm tệp khác.

## Nghiệm thu (Claude chạy)

```
uv run ruff check .
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider
grep -n "uses:" .github/workflows/security.yml     # mọi dòng ghim SHA 40 ký tự
```

Ghi `plan/reports/T94.md` theo mẫu `AGENTS.md`.
