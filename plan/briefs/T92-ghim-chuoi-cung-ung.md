# T92 – Ghim chuỗi cung ứng: GitHub Actions theo SHA, image Docker theo digest, bỏ `requirements.txt` (T3)

Nguồn: `docs/bao-cao-bao-mat-2026-11-20.md` mục T3. Agent: agy `gemini-4-hydrogen-high`. **Không gọi shell, không gọi mạng; chỉ đọc và ghi tệp.**

Song song: T89, T90, T91. Không đụng `app/`, `web/src`, `tests/`.

## Phạm vi tệp

Sửa: `.github/workflows/*.yml`, `Dockerfile`, `docker-compose.yml` (chỉ dòng `image:` của `caddy`). Tạo: `.github/dependabot.yml`. Xoá: `requirements.txt` (không tệp nào tham chiếu; Claude đã grep).

## Giá trị đã tra (Claude tra ngày 20/11/2026 bằng `gh api` và `docker buildx imagetools inspect`)

| Hiện tại | Ghim thành |
| :-- | :-- |
| `actions/checkout@v7` | `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7` |
| `actions/setup-node@v7` | `actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7` |
| `astral-sh/setup-uv@v10.3.3` | `astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3` |
| `FROM node:24-alpine` | `FROM node:24-alpine@sha256:116b800c3754b440ee0aa3ed2f20f5bf3d99a554bfd9adeea09ea8017f6e85f5` |
| `FROM python:3.13-slim` | `FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90` |
| `COPY --from=ghcr.io/astral-sh/uv:0.12.15` | `COPY --from=ghcr.io/astral-sh/uv:0.12.15@sha256:62f8c047d0a0e9ece6b53fc63df902585a67a47a7f318ddec4a37db586edc8e3` |
| `image: caddy:2` | `image: caddy:2@sha256:4851e54a46b206517c574821bb5cc67f170d2156041e9fbc4c9193b45e84a75b` |

Thay **mọi** chỗ xuất hiện (mọi workflow, mọi job). Chép đúng từng ký tự giá trị trên; không tự đoán SHA khác.

## Thêm

- `Dockerfile`, giai đoạn `app`: thêm `CDSS_RUNTIME=container` vào khối `ENV` hiện có (T89 dùng biến này để cấm `AUTH_MODE=off` trong container).
- `.github/dependabot.yml` (`version: 2`): `github-actions` (`/`), `pip` (`/`, uv dùng `pyproject.toml`), `npm` (`/web`), `docker` (`/`); lịch `weekly`; `open-pull-requests-limit: 5`.
- Workflow: mỗi workflow có `permissions: contents: read` ở cấp đầu (đã có thì giữ).

## Nghiệm thu (Claude chạy)

```
grep -rn "uses:" .github/workflows   # mọi dòng có @<40 hex>
docker compose config -q             # với .env.app tạm
docker build --target app -t vinmec-pin-check .   # build được với digest
uv run pytest -q -p no:cacheprovider tests/architecture
```

## Cấm

Không cài gói, không đổi phiên bản (chỉ ghim đúng bản đang dùng). Ghi `plan/reports/T92.md` theo mẫu `AGENTS.md`.
