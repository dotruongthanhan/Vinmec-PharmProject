"""Điểm vào dòng lệnh chạy bộ luật v0 trên một tệp JSON ca bệnh."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.domain.loader import load_case
from app.rules.engine import run_rules
from app.rules.renal_dose import load_renal_rules

_DEFAULT_RENAL_RULES_PATH = Path("data/kb/quy_tac_lieu_than.json")


def _build_parser() -> argparse.ArgumentParser:
    """Khởi tạo bộ phân tích tham số dòng lệnh cho bộ luật."""
    parser = argparse.ArgumentParser(
        prog="python -m app.rules",
        description="Chạy bộ luật v0 kiểm tra một ca bệnh từ tệp JSON.",
    )
    parser.add_argument("case_path", type=Path, help="Đường dẫn tới tệp JSON ca bệnh")
    parser.add_argument(
        "--renal-rules",
        type=Path,
        default=_DEFAULT_RENAL_RULES_PATH,
        help="Đường dẫn bảng quy tắc chỉnh liều theo thận",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Nạp ca bệnh, chạy bộ luật và in danh sách phát hiện dưới dạng JSON UTF-8."""
    current_encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
    if hasattr(sys.stdout, "reconfigure") and current_encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    args = _build_parser().parse_args(argv)
    ca = load_case(args.case_path)
    renal_rules = load_renal_rules(args.renal_rules)
    findings = run_rules(ca, renal_rules)
    payload = [item.model_dump(mode="json") for item in findings]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
