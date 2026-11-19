"""Lệnh dựng bảng và kiểm ma trận hoàn toàn ngoại tuyến."""

import argparse
import json

from app.kb.interactions.build import build_index
from app.kb.interactions.report import report_cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Bảng tương tác DDInter cục bộ")
    parser.add_argument("command", choices=("build", "report-ca"))
    args = parser.parse_args()
    result = build_index() if args.command == "build" else report_cases()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
