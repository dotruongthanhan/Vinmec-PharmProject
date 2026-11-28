# VZ2-fix-5 – Build web hỏng trong Docker/Vercel vì test import tệp ngoài `web/`

Người làm: Codex `gpt-6.1-terra` high.

## Lỗi (Claude deploy EC2, 28/11 ~1h15)

`docker compose build api` chạy `npm run build` trong ảnh. Ảnh chỉ có thư mục `web/`, nên build dừng:

```
src/features/minh-hoa/__tests__/ui2.test.tsx(8,23): error TS2307: Cannot find module '../../../../../tests/fixtures/minh_hoa/doan.json'
```

Vercel cũng chỉ build `web/`, nên sẽ hỏng như vậy.

## Yêu cầu

- Chuyển tệp đặc tả dùng chung vào trong `web/`, ví dụ `web/src/features/minh-hoa/__tests__/fixtures/doan.json`. Các test web import từ đó.
- Test Python đang đọc `tests/fixtures/minh_hoa/doan.json` thì đổi sang đọc đường dẫn mới. Hai bên vẫn dùng **một** tệp. Xoá bản cũ trong `tests/fixtures/minh_hoa/`.
- Kiểm thêm: không còn import nào trong `web/src` trỏ ra ngoài `web/`. Thêm một test vitest quét nguồn tìm chuỗi `'../../../../../` (hoặc import có `tests/fixtures`) để chặn tái phát.
- Mô phỏng build như trong ảnh: sao `web/` ra thư mục tạm trong `%TEMP%`, chạy `npx tsc -b --noEmit` ở đó, phải đạt. Nếu không mô phỏng được (thiếu `node_modules`) thì ghi rõ trong báo cáo.

## Tệp

`web/src/features/minh-hoa/__tests__/**`, `tests/agent/**` (chỉ đường dẫn fixture), `tests/fixtures/minh_hoa/**`. Báo cáo: mục "fix-5" trong `plan/briefs/VZ2-bao-cao.md`.
**Cấm:** như brief VZ2; không đọc `.env`; không mạng.

## Nghiệm thu

```
uv run ruff check tests && uv run pytest -q -p no:cacheprovider tests/agent/test_minh_hoa_kiem.py
cd web && npx tsc -b --noEmit && npx vitest run && npx vite build
```
