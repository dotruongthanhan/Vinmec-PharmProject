"""Pipeline xay dung KB openFDA: xac minh SHA-256, cat doan, kiem tra chat luong."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from app.config.settings import Settings, load_settings
from app.core.types import Chunk
from app.kb.chunking.label_chunker import LabelChunker
from app.kb.names import DrugNameIndex
from app.kb.sources.openfda import LabelDocument, load_label

_CRITICAL_SECTIONS: tuple[str, ...] = (
    "chi_dinh",
    "lieu",
    "chong_chi_dinh",
    "canh_bao",
    "tuong_tac",
    "tac_dung_phu",
)


class BuildReport(BaseModel):
    """Bao cao ket qua chay tien xu ly va cat doan nguon openFDA."""

    thoi_gian_utc: str
    tong_nhan_manifest: int
    so_nhan_da_xu_ly: int
    so_nhan_thieu_set_id: int = 0
    tong_doan: int
    so_doan_van_ban: int
    so_doan_bang: int
    ty_le_trong_max_chars: float
    do_dai_trung_binh: float
    do_dai_trung_vi: float
    do_dai_nho_nhat: int
    do_dai_lon_nhat: int
    so_doan_vuot_max_chars: int
    so_doan_duoi_50_ky_tu: int
    so_doan_hoat_chat_rong: int
    so_doan_trung_id: int
    phan_bo_theo_muc: dict[str, int]
    nhan_thieu_muc_quan_trong: dict[str, list[str]] = Field(default_factory=dict)
    nhan_co_canh_bao: dict[str, list[str]] = Field(default_factory=dict)
    canh_bao_q3: list[str] = Field(default_factory=list)
    vi_pham_q2: list[str] = Field(default_factory=list)
    vi_pham_q4: list[str] = Field(default_factory=list)
    dat_chat_luong: bool


def load_chunks(path: Path) -> list[Chunk]:
    """Doc danh sach Chunk tu tep JSONL (chunks.jsonl)."""
    chunks: list[Chunk] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            chunks.append(Chunk.model_validate_json(stripped))
    return chunks


def _extract_manifest_entries(data: object) -> list[dict]:
    """Trich danh sach muc tai lieu tu manifest.json (ho tro ca list lan dict)."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for val in data.values():
            if isinstance(val, list) and val and all(isinstance(x, dict) for x in val):
                if any("duong_dan" in x and "ten_goi" in x for x in val):
                    return list(val)
    raise ValueError("Khong tim thay danh sach tai lieu hop le trong manifest.json")


def _sha256_file(path: Path) -> str:
    """Tinh SHA-256 hexdigest cua mot tep."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest().lower()


def _verify_manifest_entries(sources_dir: Path, entries: list[dict]) -> list[str]:
    """Kiem tra ton tai va ma SHA-256 cho tat ca tep openFDA duoc chon."""
    errors: list[str] = []
    for entry in entries:
        ten_goi = str(entry.get("ten_goi") or "unknown")
        rel_path = entry.get("duong_dan")
        if not rel_path:
            errors.append(f"thieu_duong_dan:{ten_goi}")
            continue
        file_path = sources_dir / str(rel_path)
        if not file_path.is_file():
            errors.append(f"khong_tim_thay_tep:{ten_goi}:{file_path}")
            continue
        expected = str(entry.get("sha256") or "").strip().lower()
        actual = _sha256_file(file_path)
        if not expected or actual != expected:
            errors.append(f"sai_sha256:{ten_goi}:expected={expected}:actual={actual}")
    return errors


def _collect_q3_warnings(chunks: list[Chunk]) -> list[str]:
    """Thu thap canh bao chat luong muc Q3 (khong lam that bai build)."""
    warnings: list[str] = []
    for chunk in chunks:
        if chunk.loai_noi_dung == "bang":
            continue
        text = chunk.noi_dung_goc
        if text and text[0].islower():
            warnings.append(f"q3_bat_dau_chu_thuong:{chunk.doan_trich_id}")
        if text.endswith(("e.g.", "i.e.", "vs.", "No.")):
            warnings.append(f"q3_ket_thuc_viet_tat:{chunk.doan_trich_id}")
    return warnings


def build_kb(
    sources_dir: Path,
    out_dir: Path,
    reports_dir: Path,
    names_path: Path | None = None,
    only: list[str] | None = None,
    settings: Settings | None = None,
) -> tuple[BuildReport, int]:
    """Chay pipeline tao chunks.jsonl va bao cao chat luong, tra ve (BuildReport, exit_code)."""
    resolved_settings = settings if settings is not None else load_settings()
    resolved_names_path = names_path if names_path is not None else Path("data/kb/hoat_chat.json")
    manifest_path = sources_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Khong tim thay manifest.json tai {manifest_path}")

    manifest_raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    all_entries = _extract_manifest_entries(manifest_raw)
    openfda_entries = [e for e in all_entries if e.get("nguon") == "openfda_drug_label"]
    if not openfda_entries:
        openfda_entries = all_entries

    if only:
        wanted = {name.strip() for name in only if name.strip()}
        available = {str(e.get("ten_goi")) for e in openfda_entries}
        missing = sorted(wanted - available)
        if missing:
            raise ValueError(f"Khong tim thay ten_goi trong manifest: {', '.join(missing)}")
        selected_entries = [e for e in openfda_entries if str(e.get("ten_goi")) in wanted]
    else:
        selected_entries = list(openfda_entries)

    selected_entries.sort(key=lambda e: (str(e.get("ten_goi", "")), str(e.get("set_id", ""))))

    verify_errors = _verify_manifest_entries(sources_dir, selected_entries)
    if verify_errors:
        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        empty_report = BuildReport(
            thoi_gian_utc=now_iso,
            tong_nhan_manifest=len(openfda_entries),
            so_nhan_da_xu_ly=0,
            tong_doan=0,
            so_doan_van_ban=0,
            so_doan_bang=0,
            ty_le_trong_max_chars=0.0,
            do_dai_trung_binh=0.0,
            do_dai_trung_vi=0.0,
            do_dai_nho_nhat=0,
            do_dai_lon_nhat=0,
            so_doan_vuot_max_chars=0,
            so_doan_duoi_50_ky_tu=0,
            so_doan_hoat_chat_rong=0,
            so_doan_trung_id=0,
            phan_bo_theo_muc={},
            vi_pham_q4=verify_errors,
            dat_chat_luong=False,
        )
        _write_report(reports_dir, empty_report)
        return empty_report, 1

    names = DrugNameIndex.load(resolved_names_path)
    chunker = LabelChunker(resolved_settings.chunking, names=names)

    docs: list[LabelDocument] = []
    chunks: list[Chunk] = []
    for entry in selected_entries:
        doc = load_label(sources_dir / str(entry["duong_dan"]), entry, names)
        docs.append(doc)
        chunks.extend(chunker.split(doc))

    chunks_path = out_dir / "chunks.jsonl"
    if chunks_path.is_file():
        # Giu ma cu khi noi dung va duong dan khong doi, du thu tu bang thay doi.
        previous_ids = {
            (c.tai_lieu_id, c.duong_dan_muc, c.noi_dung_goc): c.doan_trich_id
            for c in load_chunks(chunks_path)
        }
        chunks = [
            c.model_copy(
                update={
                    "doan_trich_id": previous_ids.get(
                        (c.tai_lieu_id, c.duong_dan_muc, c.noi_dung_goc), c.doan_trich_id
                    )
                }
            )
            for c in chunks
        ]

    text_chunks = [c for c in chunks if c.loai_noi_dung != "bang"]
    table_chunks = [c for c in chunks if c.loai_noi_dung == "bang"]
    text_lengths = [len(c.noi_dung_goc) for c in text_chunks]
    max_chars = resolved_settings.chunking.max_chars

    over_max = [
        f"{c.doan_trich_id}({len(c.noi_dung_goc)})"
        for c in text_chunks
        if len(c.noi_dung_goc) > max_chars
    ]
    too_short = [
        f"{c.doan_trich_id}({len(c.noi_dung_goc)})" for c in text_chunks if len(c.noi_dung_goc) < 50
    ]
    empty_actives = [c.doan_trich_id for c in chunks if not c.hoat_chat_ids]

    id_counts = Counter(c.doan_trich_id for c in chunks)
    dup_ids = [cid for cid, cnt in id_counts.items() if cnt > 1]

    missing_sections: dict[str, list[str]] = {}
    label_warnings: dict[str, list[str]] = {}
    for doc in docs:
        present = {sec.muc for sec in doc.sections}
        if "lieu_than" in present:
            present.add("lieu")
        missing = [m for m in _CRITICAL_SECTIONS if m not in present]
        if missing:
            missing_sections[doc.ten_goi] = missing
        if doc.canh_bao:
            label_warnings[doc.ten_goi] = list(doc.canh_bao)

    q3_warnings = _collect_q3_warnings(chunks)
    if missing_sections:
        for ten_goi, missed in missing_sections.items():
            q3_warnings.append(f"q3_thieu_muc:{ten_goi}:{','.join(missed)}")

    vi_pham_q2 = list(over_max)
    vi_pham_q4: list[str] = []
    if empty_actives:
        vi_pham_q4.extend(f"hoat_chat_rong:{cid}" for cid in empty_actives)
    if too_short:
        vi_pham_q4.extend(f"duoi_50_ky_tu:{item}" for item in too_short)
    if dup_ids:
        vi_pham_q4.extend(f"trung_id:{cid}" for cid in dup_ids)
    if not chunks:
        vi_pham_q4.append("khong_tao_duoc_chunk_nao")

    passed = not vi_pham_q2 and not vi_pham_q4
    within_ratio = (
        round(sum(1 for n in text_lengths if n <= max_chars) / len(text_lengths), 4)
        if text_lengths
        else 1.0
    )

    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = BuildReport(
        thoi_gian_utc=now_iso,
        tong_nhan_manifest=len(openfda_entries),
        so_nhan_da_xu_ly=len(docs),
        so_nhan_thieu_set_id=sum(not doc.set_id for doc in docs),
        tong_doan=len(chunks),
        so_doan_van_ban=len(text_chunks),
        so_doan_bang=len(table_chunks),
        ty_le_trong_max_chars=within_ratio,
        do_dai_trung_binh=round(statistics.mean(text_lengths), 1) if text_lengths else 0.0,
        do_dai_trung_vi=float(statistics.median(text_lengths)) if text_lengths else 0.0,
        do_dai_nho_nhat=min(text_lengths) if text_lengths else 0,
        do_dai_lon_nhat=max(text_lengths) if text_lengths else 0,
        so_doan_vuot_max_chars=len(over_max),
        so_doan_duoi_50_ky_tu=len(too_short),
        so_doan_hoat_chat_rong=len(empty_actives),
        so_doan_trung_id=len(dup_ids),
        phan_bo_theo_muc=dict(sorted(Counter(c.muc for c in chunks).items())),
        nhan_thieu_muc_quan_trong=missing_sections,
        nhan_co_canh_bao=label_warnings,
        canh_bao_q3=q3_warnings,
        vi_pham_q2=vi_pham_q2,
        vi_pham_q4=vi_pham_q4,
        dat_chat_luong=passed,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    with chunks_path.open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in chunks:
            line = json.dumps(chunk.model_dump(mode="json"), ensure_ascii=False)
            handle.write(line + "\n")

    _write_report(reports_dir, report)
    return report, (0 if passed else 1)


def _write_report(reports_dir: Path, report: BuildReport) -> Path:
    """Ghi bao cao JSON vao thu muc reports."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"openfda_build_{stamp}.json"
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build curated chunks.jsonl from openFDA drug labels."
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=Path("data/kb_sources"),
        help="Thu muc chua manifest.json va nhan openFDA.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/kb_curated"),
        help="Thu muc dau ra chua chunks.jsonl.",
    )
    parser.add_argument(
        "--reports",
        type=Path,
        default=Path("data/kb_reports"),
        help="Thu muc luu bao cao JSON.",
    )
    parser.add_argument(
        "--names",
        type=Path,
        default=Path("data/kb/hoat_chat.json"),
        help="Duong dan tep hoat_chat.json.",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Danh sach ten_goi cach nhau boi dau phay.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Diem vao CLI cho python -m app.kb.build."""
    args = _parse_args(argv)
    only_list = (
        [item.strip() for item in args.only.split(",") if item.strip()] if args.only else None
    )
    try:
        report, exit_code = build_kb(
            sources_dir=args.sources,
            out_dir=args.out,
            reports_dir=args.reports,
            names_path=args.names,
            only=only_list,
        )
    except Exception as exc:
        print(f"[openfda] ERROR: {exc}")
        return 1

    print(
        f"[openfda] status={'OK' if exit_code == 0 else 'FAIL'} "
        f"labels={report.so_nhan_da_xu_ly}/{report.tong_nhan_manifest} "
        f"chunks={report.tong_doan} text={report.so_doan_van_ban} "
        f"table={report.so_doan_bang} over_max={report.so_doan_vuot_max_chars} "
        f"under_50={report.so_doan_duoi_50_ky_tu} empty_act={report.so_doan_hoat_chat_rong} "
        f"q3_warn={len(report.canh_bao_q3)} missing_set_id={report.so_nhan_thieu_set_id}"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
