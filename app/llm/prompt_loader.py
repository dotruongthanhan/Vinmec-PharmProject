"""Bộ nạp tệp prompt có phiên bản và thay thế chỗ điền đơn giản."""

from pathlib import Path


def load_prompt(path: Path | str) -> tuple[str, str]:
    """Đọc tệp prompt UTF-8, trả về cặp (phien_ban, noi_dung)."""
    prompt_path = Path(path)
    phien_ban = prompt_path.stem
    noi_dung = prompt_path.read_text(encoding="utf-8")
    return phien_ban, noi_dung


def render_prompt(
    template: str,
    *,
    van_ban_ca: str,
    doan_nguon: str,
    loi_lan_truoc: str,
) -> str:
    """Thay thế ba chỗ điền cố định trong nội dung prompt bằng thay chuỗi đơn giản."""
    return (
        template.replace("{{van_ban_ca}}", van_ban_ca)
        .replace("{{doan_nguon}}", doan_nguon)
        .replace("{{loi_lan_truoc}}", loi_lan_truoc)
    )
