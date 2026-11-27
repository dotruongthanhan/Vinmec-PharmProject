# VZ1a-3-fix-1 – Số dính đơn vị lọt qua bộ kiểm chữ

Người làm: Codex gpt-6.1-terra high. Không cài gói, không mạng, không commit, không đọc `.env`, không đọc `~/.codex`.

## Lỗi (Claude thử lách sau VZ1a-3)

`kiem_dac_ta` trong `app/agent/minh_hoa/kiem.py` cho qua `tieu_de: "25mL/phút"`. Lý do là token lẫn chữ và số được miễn để giữ `CYP2C9`, `HbA1c`.

Kết quả thử lách hiện tại:

| Ví dụ | Kết quả hiện tại |
| :--- | :--- |
| `CYP2C9`, `CKD-EPI`, `Nhóm IV` | đạt (đúng) |
| `ngưỡng 0,5`, `liều ２ g`, `CrCl 25 mL/phút` | từ chối (đúng) |
| `25mL/phút` | **đạt (sai)** |

## Sửa

Token lẫn chữ và số chỉ được miễn khi **không bắt đầu bằng chữ số**. Tức là:
- `25mL`, `2g`, `0.5mg/kg`, `12h` → `so_tu_do`;
- `CYP2C9`, `HbA1c`, `CKD-EPI`, `CYP3A4` → vẫn đạt.

Chuẩn hoá NFKC như hiện nay, để chữ số toàn độ rộng cũng bị chặn.

## Test

Thêm các ca trên vào `tests/agent/test_minh_hoa_kiem.py`. Ba mẫu VZ0 và các ví dụ trong `config/prompts/ky_nang_minh_hoa.v1.md` vẫn phải đạt.

## Tệp

Chỉ sửa `app/agent/minh_hoa/kiem.py` và `tests/agent/test_minh_hoa_kiem.py`. Báo cáo ngắn vào `plan/briefs/VZ1a-3-fix-1-bao-cao.md`.

**RAM:** chỉ chạy:
- `tests/agent/test_minh_hoa_kiem.py`
- `tests/agent/test_minh_hoa_do_thi.py`

## Nghiệm thu

```
uv run ruff check app tests/agent && uv run ruff format --check app tests/agent
uv run pytest -q -p no:cacheprovider tests/agent/test_minh_hoa_kiem.py tests/agent/test_minh_hoa_do_thi.py
```
