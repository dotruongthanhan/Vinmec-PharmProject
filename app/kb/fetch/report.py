"""Báo cáo độ phủ sinh hoàn toàn từ nguồn trên đĩa."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.kb.fetch.labels import (
    SECTION_FIELDS,
    DrugSpec,
    dosage_tables,
    field_text,
    label_matches,
    section_counts,
)
from app.kb.fetch.runner import json_bytes

_RENAL_SECTION = re.compile(
    r"(?:renal|kidney)\s+(?:impairment|insufficiency|dysfunction)|"
    r"(?:dose|dosage|dosing)\s+.{0,100}(?:renal|kidney)|"
    r"creatinine\s+clearance|\b(?:CrCl|CLcr|eGFR)\b",
    re.IGNORECASE,
)
_TITLES = {
    "chi_dinh": "Chỉ định",
    "lieu_va_cach_dung": "Liều và cách dùng",
    "chong_chi_dinh": "Chống chỉ định",
    "canh_bao": "Cảnh báo",
    "tuong_tac": "Tương tác",
    "nhom_dac_biet": "Nhóm đặc biệt",
    "bang_lieu": "Bảng liều",
}
_FAILURE_STATUSES = frozenset(
    {
        "loi_ket_noi",
        "phan_hoi_sai_cau_truc",
        "khong_co_ung_vien_hop_le",
        "khong_tim_thay",
        "that_bai",
    }
)


def label_coverage(entry: dict[str, Any]) -> dict[str, Any]:
    """Đo sự hiện diện mục và ký tự; không suy ra khuyến cáo liều."""
    counts = section_counts(entry)
    renal_text = "\n".join(
        field_text(entry, field)
        for field in (
            "dosage_and_administration",
            "use_in_specific_populations",
        )
    )
    return {
        "set_id": entry.get("set_id"),
        "effective_time": entry.get("effective_time"),
        "duong_dung": entry.get("openfda", {}).get("route", []),
        "muc": {name: {"co": count > 0, "so_ky_tu": count} for name, count in counts.items()},
        "so_bang_lieu": len(dosage_tables(entry)),
        "co_muc_chinh_lieu_than": bool(_RENAL_SECTION.search(renal_text)),
        "co_muc_tuong_tac": counts["tuong_tac"] > 0,
        "muc_thieu": [name for name, count in counts.items() if not count],
    }


def _render(report: dict[str, Any]) -> str:
    lines = [
        "# Báo cáo độ phủ nhãn openFDA",
        "",
        f"Số nhãn trên đĩa: {report['so_nhan']}. "
        "Sinh lại bằng `uv run python -m app.kb.fetch report`.",
        "Không gọi mạng; không sửa, dịch hoặc tóm tắt nhãn. Ô mục ghi có/không và số ký tự.",
        "Bảng liều tính ký tự bản phẳng của bảng tách được, bỏ bảng trùng nguyên văn.",
        "Chỉnh liều thận là chỉ dấu văn bản trong mục liều/nhóm đặc biệt; cần dược sĩ đối chiếu.",
        "",
        "| Nhãn | "
        + " | ".join(_TITLES.values())
        + " | Số bảng liều | Thận | Tương tác | Đường dùng | effective_time |",
        "| " + " | ".join(["---"] * 13) + " |",
    ]
    for row in report["nhan"]:
        cells = [f"`{row['duong_dan']}`"]
        cells.extend(
            f"{'có' if row['muc'][key]['co'] else 'không'} ({row['muc'][key]['so_ky_tu']})"
            for key in SECTION_FIELDS
        )
        cells.extend(
            [
                str(row["so_bang_lieu"]),
                "có" if row["co_muc_chinh_lieu_than"] else "không",
                "có" if row["co_muc_tuong_tac"] else "không",
                ", ".join(row["duong_dung"]),
                str(row["effective_time"] or "thiếu"),
            ]
        )
        lines.append("| " + " | ".join(cells) + " |")
    lines.extend(["", "## Thiếu nhãn cho đường dùng cần có", ""])
    lines.extend(f"- `{row['ma']}`: {row['duong_dung']}" for row in report["thieu_nhan"])
    if not report["thieu_nhan"]:
        lines.append("Không có.")
    lines.extend(["", "## Nhãn thiếu từ 2 mục trở lên", ""])
    lines.extend(
        f"- `{row['duong_dan']}`: {', '.join(_TITLES[key] for key in row['muc_thieu'])}"
        for row in report["nhan_thieu_tu_2_muc"]
    )
    if not report["nhan_thieu_tu_2_muc"]:
        lines.append("Không có.")
    lines.extend(["", "## Ghi chú danh mục và lỗi nguồn", ""])
    lines.extend(f"- `{row['ma']}`: {row['ghi_chu']}" for row in report["ghi_chu"])
    lines.extend(f"- `{row['duong_dan']}`: {row['ly_do']}" for row in report["loi_tep"])
    lines.extend(["", "## Kết quả tải gần nhất", ""])
    for kind, rows in report["ket_qua_tai"].items():
        counts: dict[str, int] = {}
        for row in rows:
            status = row["trang_thai"]
            counts[status] = counts.get(status, 0) + 1
        lines.append(
            f"- {kind}: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        )
        lines.extend(
            f"  - `{row['ma']}` ({row.get('duong_dung') or 'NDC'}): "
            f"{row['trang_thai']} {row.get('ly_do', '')}".rstrip()
            for row in rows
            if row["trang_thai"] in _FAILURE_STATUSES
        )
    if report.get("dung_kho"):
        build = report["dung_kho"]
        lines.extend(
            [
                "",
                "## Đối chiếu dựng lại kho",
                "",
                f"- Nhãn trước / sau: {build.get('so_nhan_truoc', 'thiếu')} / "
                f"{build['so_nhan_da_xu_ly']}.",
                f"- Đoạn trước / sau: {build.get('so_doan_truoc', 'thiếu')} / "
                f"{build['tong_doan']}.",
                f"- Mã đoạn cũ không còn trong kho: {build.get('so_ma_doan_bi_doi', 'thiếu')} "
                "(bao gồm đoạn có nội dung hoặc nhãn được thay thế).",
                "- Mã bị đổi dù nội dung và đường dẫn không đổi: "
                f"{build.get('so_ma_doan_khong_doi_noi_dung_bi_doi', 'thiếu')}.",
                "",
                "Dòng tóm tắt nghiệm thu của `uv run python -m app.kb.build`:",
                "",
                "```text",
                build["tom_tat"],
                "```",
            ]
        )
    return "\n".join(lines) + "\n"


def write_coverage_report(
    sources_dir: Path,
    reports_dir: Path,
    specs: list[DrugSpec],
) -> dict[str, Any]:
    """Quét mọi nhãn trên đĩa, kể cả nhãn thiếu hoặc không có manifest."""
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    entries: list[dict[str, Any]] = []
    for path in sorted((sources_dir / "openfda").glob("*.json")):
        relative = path.relative_to(sources_dir).as_posix()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            entry = payload["results"][0]
            row = {"duong_dan": relative, **label_coverage(entry)}
            rows.append(row)
            entries.append(entry)
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            errors.append({"duong_dan": relative, "ly_do": "Nhãn thiếu results[0] hợp lệ"})
    missing = [
        {"ma": spec.ma, "duong_dung": route}
        for spec in specs
        for route in spec.duong_dung
        if not any(label_matches(entry, spec, route) for entry in entries)
    ]
    downloads = {}
    for kind in ("openfda", "ndc"):
        path = reports_dir / f"openfda_fetch_{kind}.json"
        if path.is_file():
            downloads[kind] = json.loads(path.read_text(encoding="utf-8"))
    report: dict[str, Any] = {
        "so_nhan": len(rows),
        "nhan": rows,
        "thieu_nhan": missing,
        "nhan_thieu_tu_2_muc": [row for row in rows if len(row["muc_thieu"]) >= 2],
        "loi_tep": errors,
        "ghi_chu": [spec.model_dump(include={"ma", "ghi_chu"}) for spec in specs if spec.ghi_chu],
        "ket_qua_tai": downloads,
    }
    old_path = reports_dir / "openfda_do_phu.json"
    if old_path.is_file():
        previous = json.loads(old_path.read_text(encoding="utf-8"))
        if "dung_kho" in previous:
            report["dung_kho"] = previous["dung_kho"]
    _write(reports_dir, report)
    return report


def _write(reports_dir: Path, report: dict[str, Any]) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "openfda_do_phu.json").write_bytes(json_bytes(report))
    (reports_dir / "openfda_do_phu.md").write_text(_render(report), encoding="utf-8", newline="\n")


def record_build(reports_dir: Path, build: dict[str, Any], summary: str) -> None:
    """Gắn số liệu và dòng nghiệm thu vào cuối báo cáo độ phủ đã có."""
    path = reports_dir / "openfda_do_phu.json"
    if path.is_file():
        report = json.loads(path.read_text(encoding="utf-8"))
        report["dung_kho"] = {**build, "tom_tat": summary}
        _write(reports_dir, report)
