"""Xuất hàng duyệt và kiểm tra quyết định trước khi lưu."""

import csv
import io
from collections import Counter
from pathlib import Path
from random import Random

from pydantic import BaseModel

from app.kb.dictionary.accept import Ranking, candidate_path
from app.kb.dictionary.catalog import Catalog, baseline
from app.kb.dictionary.storage import Row, read_jsonl, store, write_jsonl
from app.kb.names import normalize_key

FIELDS = (
    "khoa_chuan_hoa",
    "ten_goc_vi_du",
    "so_che_pham",
    "so_luot",
    "ung_vien_1",
    "ung_vien_2",
    "ung_vien_3",
    "ly_do",
    "quyet_dinh",
    "nguoi_duyet",
    "ghi_chu",
)


class Decision(BaseModel):
    khoa_chuan_hoa: str
    quyet_dinh: str
    rxcui: str | None
    nguoi_duyet: str
    ghi_chu: str
    cach_khop: str = "nguoi_duyet"


def _decision_file(root: Path) -> Path:
    return root / "kb_curated/tu_dien/duyet_tay.jsonl"


def _validate_decision(row: Decision, catalog: Catalog) -> None:
    key = row.khoa_chuan_hoa
    if not key or normalize_key(key) != key:
        raise ValueError("khoa_chuan_hoa khong hop le")
    if not row.nguoi_duyet.strip():
        raise ValueError("thieu nguoi_duyet")
    if row.cach_khop != "nguoi_duyet":
        raise ValueError("cach_khop khong hop le")
    if row.quyet_dinh in {"duoc_lieu", "bo_qua"} and row.rxcui is None:
        return
    if row.quyet_dinh not in {"chon_1", "chon_2", "chon_3", f"rxcui:{row.rxcui}"}:
        raise ValueError("quyet_dinh khong hop le")
    entry = catalog.by_code(row.rxcui) if row.rxcui else None
    if not entry:
        raise ValueError("RxCUI khong co trong kho ung vien")
    match = catalog.match(entry, "nguoi_duyet", catalog.baseline.copy())
    if not match.hoat_chat_id:
        raise ValueError(match.ly_do)


def read_decisions(root: Path, catalog: Catalog) -> dict[str, Row]:
    path = _decision_file(root)
    decisions = {}
    if path.is_file():
        for data in read_jsonl(path):
            row = Decision.model_validate(data)
            _validate_decision(row, catalog)
            if row.khoa_chuan_hoa in decisions:
                raise ValueError(f"Khoa duyet bi lap: {row.khoa_chuan_hoa}")
            decisions[row.khoa_chuan_hoa] = row.model_dump()
    return decisions


def queue(root: Path, *, rows: list[Row] | None = None) -> dict[str, Row]:
    if rows is None:
        rows = read_jsonl(root / "kb_curated/tu_dien/cho_duyet.jsonl")
    grouped = {}
    for row in rows:
        if row["loai_ban_ghi"] != "ten":
            continue
        key = row["khoa_chuan_hoa"]
        if key not in grouped:
            grouped[key] = {
                "khoa_chuan_hoa": key,
                "ten_goc_vi_du": row["ten_goc"],
                "so_luot": 0,
                "ma_dav": set(),
                "ly_do": Counter(),
                "nguon_ban_ghi_ids": set(),
            }
        group = grouped[key]
        group["so_luot"] += 1
        group["ly_do"][row["ly_do"] or "chua_khop"] += 1
        group["nguon_ban_ghi_ids"].update(row["nguon_ban_ghi_ids"])
        if row["nguon"] == "dav":
            group["ma_dav"].add(row["ma_ban_ghi_nguon"])
    for group in grouped.values():
        group["so_che_pham"] = len(group.pop("ma_dav"))
        group["ly_do"] = ", ".join(sorted(group["ly_do"]))
        group["nguon_ban_ghi_ids"] = sorted(group["nguon_ban_ghi_ids"])
    return grouped


def _rankings(root: Path, mode: str | None = None) -> dict[str, Ranking]:
    path = candidate_path(root, mode or "that")
    if not mode and not path.is_file():
        path = candidate_path(root, "fake")
    if mode is None and not path.is_file():
        return {}
    return {row["khoa_chuan_hoa"]: Ranking.model_validate(row) for row in read_jsonl(path)}


def _csv_cell(value: str) -> str:
    """Giữ chuỗi nguồn ở dạng văn bản khi mở bằng bảng tính."""
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def export_review(root: Path, mode: str | None = None) -> Row:
    grouped = queue(root)
    rankings = _rankings(root, mode)
    out = root / "kb_reports"
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, FIELDS)
    writer.writeheader()
    with_candidates = []
    for key, group in sorted(grouped.items(), key=lambda pair: (-pair[1]["so_che_pham"], pair[0])):
        row = {k: v for k, v in group.items() if k in FIELDS}
        row["ten_goc_vi_du"] = _csv_cell(row["ten_goc_vi_du"])
        if ranking := rankings.get(key):
            for pick in ranking.ung_vien[:3]:
                row[f"ung_vien_{pick.hang}"] = _csv_cell(
                    f"{pick.ten} | {pick.rxcui or ''} | {pick.diem_ket_hop:.6f}"
                )
            if ranking.ung_vien:
                with_candidates.append(
                    {
                        "nhom_mau": "ung_vien_hang_1",
                        **group,
                        "mo_hinh": ranking.mo_hinh,
                        "ung_vien": ranking.ung_vien[0].model_dump(),
                    }
                )
        writer.writerow(row)
    store(out / "T52_hang_duyet.csv", csv_buffer.getvalue().encode("utf-8-sig"))
    path = out / "T52_mau_kiem.jsonl"
    samples = read_jsonl(path) if path.is_file() else []
    samples = [row for row in samples if row["nhom_mau"] != "ung_vien_hang_1"]
    rng = Random(52)  # noqa: S311  # mẫu kiểm dữ liệu tất định
    sample_rows = rng.sample(with_candidates, min(10, len(with_candidates)))
    write_jsonl(path, [*samples, *sample_rows])
    return {"so_ten_cho_duyet": len(grouped), "so_ten_co_ung_vien": len(with_candidates)}


def import_review(root: Path, path: Path) -> Row:
    """Kiểm tra trọn tệp trước khi cập nhật các quyết định theo khóa."""
    _, _, _, catalog = baseline(root)
    decisions = read_decisions(root, catalog)
    grouped = queue(root)
    # Đối chiếu cột ứng viên với kết quả xếp hạng cục bộ của lượt xuất tương ứng.
    options: dict[str, list[Ranking]] = {}
    for mode in ("that", "fake"):
        if candidate_path(root, mode).is_file():
            for key, ranking in _rankings(root, mode).items():
                options.setdefault(key, []).append(ranking)
    changes: dict[str, Row] = {}
    errors = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not set(FIELDS) <= set(reader.fieldnames or []):
            raise ValueError("Tep duyet thieu cot")
        for row in reader:
            decision = (row["quyet_dinh"] or "").strip()
            if not decision:
                continue
            try:
                key = (row["khoa_chuan_hoa"] or "").strip()
                if key not in grouped and key not in decisions:
                    raise ValueError("khoa khong co trong hang duyet")
                if key in changes:
                    raise ValueError("khoa bi lap trong tep")
                code = None
                if decision in {"chon_1", "chon_2", "chon_3"}:
                    rank = int(decision[-1])
                    col = row[f"ung_vien_{rank}"] or ""
                    codes = {
                        pick.rxcui
                        for ranking in options.get(key, [])
                        for pick in ranking.ung_vien
                        if pick.hang == rank
                        and _csv_cell(f"{pick.ten} | {pick.rxcui or ''} | {pick.diem_ket_hop:.6f}")
                        == col
                    }
                    if len(codes) != 1 or None in codes:
                        raise ValueError("ung vien khong khop ket qua xep hang da luu")
                    code = next(iter(codes))
                elif decision.startswith("rxcui:"):
                    code = decision.partition(":")[2]
                entry = Decision(
                    khoa_chuan_hoa=key,
                    quyet_dinh=decision,
                    rxcui=code,
                    nguoi_duyet=(row["nguoi_duyet"] or "").strip(),
                    ghi_chu=(row["ghi_chu"] or "").strip(),
                )
                _validate_decision(entry, catalog)
                changes[key] = entry.model_dump()
            except ValueError as exc:
                errors.append(f"dong {reader.line_num}: {exc}")
    if errors:
        raise ValueError("\n".join(errors))
    if changes:
        decisions.update(changes)
        write_jsonl(_decision_file(root), (decisions[key] for key in sorted(decisions)))
    return {"so_dong_da_nhap": len(changes)}
