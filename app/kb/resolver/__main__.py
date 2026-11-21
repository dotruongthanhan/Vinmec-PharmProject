"""Lệnh dựng chỉ mục và đo độ phủ ngoại tuyến."""

import argparse
import json
from pathlib import Path

from app.kb.resolver.build import build_index
from app.kb.resolver.report import report


def main() -> None:
    """Chạy lệnh từ thư mục gốc dự án."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build-index", "report"))
    command = parser.parse_args().command
    if command == "build-index":
        summary = build_index(Path.cwd())
    else:
        data = report(Path.cwd())
        summary = {
            key: data[key]
            for key in (
                "so_ca",
                "tong_so_dong",
                "theo_trang_thai",
                "theo_nguon_khop",
                "so_dong_du_ddinter_id",
                "so_hoat_chat_ca",
                "so_hoat_chat_ca_co_ddinter_id",
                "giay_nap_chi_muc",
                "giay_trung_binh_moi_dong",
            )
        }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
