"""Lệnh tạo báo cáo độ phủ đa nguồn hoàn toàn ngoại tuyến."""

import argparse
import sqlite3
from pathlib import Path

from app.kb.coverage.models import DEFAULT_REQUIRED, SOURCE_COLUMNS
from app.kb.coverage.storage import report


def main(argv: list[str] | None = None, *, root: Path | None = None) -> int:
    """Chạy từ gốc dự án; cho phép chọn bộ nguồn bắt buộc."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("report",))
    parser.add_argument(
        "--required-sources",
        nargs="+",
        choices=tuple(SOURCE_COLUMNS),
        default=DEFAULT_REQUIRED,
        help="Nguồn bắt buộc, mặc định: dav rxcui atc ddinter nhan_fda",
    )
    args = parser.parse_args(argv)
    try:
        summary = report(root or Path.cwd(), required_sources=args.required_sources)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"Khong tao duoc bao cao do phu: {exc}\n")
    print(summary.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
