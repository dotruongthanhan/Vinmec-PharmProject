"""Điểm vào python -m app.kb.fetch openfda|ndc|report."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

from app.kb.fetch.client import FDAClient
from app.kb.fetch.report import write_coverage_report
from app.kb.fetch.runner import fetch_sources, json_bytes, load_config


def _exit_code(rows: list[dict[str, Any]]) -> int:
    """Mã thoát: 0=đạt, 1=lỗi kết nối/cấu trúc, 2=không hợp lệ, 3=404."""
    statuses = {row["trang_thai"] for row in rows}
    if statuses & {"loi_ket_noi", "phan_hoi_sai_cau_truc"}:
        return 1
    if "khong_co_ung_vien_hop_le" in statuses:
        return 2
    if "khong_tim_thay" in statuses:
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    """Tải nguồn theo cấu hình và ghi báo cáo mà không lộ khóa API."""
    parser = argparse.ArgumentParser(description="Tải nhãn/NDC openFDA và báo cáo độ phủ")
    parser.add_argument("command", choices=["openfda", "ndc", "report"])
    parser.add_argument("--only", help="Các mã cách nhau bằng dấu phẩy")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    config_path = Path("config/kb/hoat_chat_can_lay.yaml")
    sources_dir = Path("data/kb_sources")
    reports_dir = Path("data/kb_reports")
    try:
        specs = load_config(config_path)
        if args.command == "report":
            report = write_coverage_report(sources_dir, reports_dir, specs)
            print(
                f"[openfda report] labels={report['so_nhan']} "
                f"missing_routes={len(report['thieu_nhan'])}"
            )
            return 0
        if args.only is not None:
            wanted = {code.strip() for code in args.only.split(",") if code.strip()}
            missing = wanted - {spec.ma for spec in specs}
            if not wanted or missing:
                parser.error(f"Mã không hợp lệ: {', '.join(sorted(missing))}")
            specs = [spec for spec in specs if spec.ma in wanted]
        with httpx.Client(timeout=30.0, follow_redirects=False) as http:
            rows = fetch_sources(
                args.command,
                specs,
                sources_dir,
                FDAClient(http),
                refresh=args.refresh,
                dry_run=args.dry_run,
            )
        for row in rows:
            print(f"[{row['trang_thai']}] {row['duong_dan']} {row.get('ly_do', '')}".rstrip())
            if args.dry_run:
                print(f"  {row['truy_van']}")
        print(
            f"[openfda {args.command}] "
            + " ".join(
                f"{status}={count}"
                for status, count in sorted(Counter(row["trang_thai"] for row in rows).items())
            )
        )
        if not args.dry_run:
            reports_dir.mkdir(parents=True, exist_ok=True)
            (reports_dir / f"openfda_fetch_{args.command}.json").write_bytes(json_bytes(rows))
            write_coverage_report(sources_dir, reports_dir, load_config(config_path))
        return _exit_code(rows)
    except (OSError, ValueError) as exc:
        print(f"[openfda] ERROR: {type(exc).__name__}: không đọc/ghi được cấu hình hoặc nguồn")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
