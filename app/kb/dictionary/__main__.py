"""Điểm vào các thao tác dựng, duyệt và xuất bản từ điển."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.errors import ConfigError, ProviderError
from app.kb.dictionary.build import build_dictionary
from app.kb.dictionary.candidates import calibrate, find_candidates
from app.kb.dictionary.publish import publish
from app.kb.dictionary.report import report_dictionary
from app.kb.dictionary.review import export_review, import_review
from app.kb.fetch.client import FetchError


def main(argv: list[str] | None = None, *, root: Path = Path("data")) -> int:
    parser = argparse.ArgumentParser(description="Dựng và báo cáo từ điển thuốc")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build")
    commands.add_parser("report")
    for name in ("candidates", "calibrate"):
        command = commands.add_parser(name)
        command.add_argument("--embedder", choices=("fake", "that"), default="that")
        command.add_argument("--dry-run", action="store_true")
    review = commands.add_parser("review")
    review.add_argument("--embedder", choices=("fake", "that"))
    load_review = commands.add_parser("nhap-duyet")
    load_review.add_argument("tep", type=Path)
    options = commands.add_parser("publish").add_mutually_exclusive_group()
    options.add_argument("--dry-run", action="store_true")
    options.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    try:
        match args.command:
            case "build":
                result = build_dictionary(root)
            case "report":
                result = report_dictionary(root)
            case "candidates":
                result = find_candidates(root, args.embedder, dry_run=args.dry_run)
            case "calibrate":
                result = calibrate(root, args.embedder, dry_run=args.dry_run)
            case "review":
                result = export_review(root, args.embedder)
            case "nhap-duyet":
                result = import_review(root, args.tep)
            case "publish":
                result = publish(root, yes=args.yes)
    except (FetchError, ConfigError, ProviderError, OSError, ValueError) as exc:
        print(f"[tu dien {args.command}] {ascii(str(exc))}")
        return 1
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
