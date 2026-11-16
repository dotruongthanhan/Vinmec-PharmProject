"""Kiem thu pipeline CLI build KB, xac minh SHA-256 va cong chat luong."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from app.kb import build as build_module
from app.kb.build import BuildReport, load_chunks, main
from app.kb.names import DrugNameIndex
from app.kb.sources.openfda import LabelDocument

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_REAL_SOURCES = _ROOT / "data" / "kb_sources"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prepare_synthetic_sources(base_dir: Path) -> Path:
    sources_dir = base_dir / "kb_sources"
    openfda_dir = sources_dir / "openfda"
    openfda_dir.mkdir(parents=True, exist_ok=True)

    new_dst = openfda_dir / "meropenem.json"
    old_dst = openfda_dir / "amoxicillin_and_clavulanate_potassium.json"
    shutil.copyfile(_FIXTURES / "openfda_new_format.json", new_dst)
    shutil.copyfile(_FIXTURES / "openfda_old_format.json", old_dst)

    manifest = [
        {
            "nguon": "openfda_drug_label",
            "ten_goi": "meropenem",
            "duong_dan": "openfda/meropenem.json",
            "sha256": _sha256(new_dst),
            "set_id": "11111111-2222-3333-4444-555555555555",
            "effective_time": "20250610",
            "url": "https://api.fda.gov/drug/label.json?search=set_id:11111111",
        },
        {
            "nguon": "openfda_drug_label",
            "ten_goi": "amoxicillin_and_clavulanate_potassium",
            "duong_dan": "openfda/amoxicillin_and_clavulanate_potassium.json",
            "sha256": _sha256(old_dst),
            "set_id": "aaaa1111-bbbb-2222-cccc-333333333333",
            "effective_time": "20230415",
            "url": "https://api.fda.gov/drug/label.json?search=set_id:aaaa1111",
        },
    ]
    (sources_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return sources_dir


def test_build_synthetic_sources_deterministic_and_passes_gates(tmp_path: Path) -> None:
    sources_dir = _prepare_synthetic_sources(tmp_path)
    out_1 = tmp_path / "out_1"
    rep_1 = tmp_path / "rep_1"
    out_2 = tmp_path / "out_2"
    rep_2 = tmp_path / "rep_2"

    code_1 = main(
        [
            "--sources",
            str(sources_dir),
            "--out",
            str(out_1),
            "--reports",
            str(rep_1),
        ]
    )
    code_2 = main(
        [
            "--sources",
            str(sources_dir),
            "--out",
            str(out_2),
            "--reports",
            str(rep_2),
        ]
    )

    assert code_1 == 0
    assert code_2 == 0

    chunks_bytes_1 = (out_1 / "chunks.jsonl").read_bytes()
    chunks_bytes_2 = (out_2 / "chunks.jsonl").read_bytes()
    assert chunks_bytes_1 == chunks_bytes_2

    chunks = load_chunks(out_1 / "chunks.jsonl")
    assert len(chunks) > 10
    ids = [c.doan_trich_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert all(c.hoat_chat_ids for c in chunks)
    assert all(len(c.noi_dung_goc) >= 50 for c in chunks if c.loai_noi_dung != "bang")

    report_files = list(rep_1.glob("openfda_build_*.json"))
    assert len(report_files) == 1
    report = BuildReport.model_validate_json(report_files[0].read_text(encoding="utf-8"))
    assert report.dat_chat_luong is True
    assert report.so_nhan_da_xu_ly == 2
    assert report.so_nhan_thieu_set_id == 0
    assert report.so_doan_vuot_max_chars == 0
    assert report.so_doan_duoi_50_ky_tu == 0
    assert report.so_doan_hoat_chat_rong == 0
    assert all(
        c.url_goc
        == (
            "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
            f"setid={c.tai_lieu_id.removeprefix('openfda:')}"
        )
        for c in chunks
    )


def test_build_reports_missing_set_id(tmp_path: Path) -> None:
    sources_dir = _prepare_synthetic_sources(tmp_path)
    source_path = sources_dir / "openfda" / "meropenem.json"
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    payload["results"][0].pop("set_id", None)
    payload["results"][0]["openfda"].pop("spl_set_id", None)
    source_path.write_text(json.dumps(payload), encoding="utf-8")
    manifest_path = sources_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[0].pop("set_id", None)
    manifest[0]["sha256"] = _sha256(source_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    out_dir = tmp_path / "out"
    rep_dir = tmp_path / "rep"
    code = main(["--sources", str(sources_dir), "--out", str(out_dir), "--reports", str(rep_dir)])
    assert code == 0
    report_path = next(rep_dir.glob("openfda_build_*.json"))
    report = BuildReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    assert report.so_nhan_da_xu_ly == 2
    assert report.so_nhan_thieu_set_id == 1
    chunks = load_chunks(out_dir / "chunks.jsonl")
    missing_id_chunks = [c for c in chunks if c.tai_lieu_id == "openfda:meropenem"]
    assert missing_id_chunks
    assert all(c.url_goc == "" for c in missing_id_chunks)
    assert all(c.url_goc for c in chunks if c.tai_lieu_id != "openfda:meropenem")


def test_rebuild_preserves_ids_when_other_table_moves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources_dir = _prepare_synthetic_sources(tmp_path)
    out_dir = tmp_path / "out"
    args = [
        "--sources",
        str(sources_dir),
        "--out",
        str(out_dir),
        "--reports",
        str(tmp_path / "reports"),
        "--only",
        "meropenem",
    ]
    original_load = build_module.load_label

    def load_with_misassigned_table(
        path: Path, manifest_entry: dict, names: DrugNameIndex
    ) -> LabelDocument:
        doc = original_load(path, manifest_entry, names)
        dosage = next(s for s in doc.sections if s.truong_goc == "dosage_and_administration")
        renal = next(s for s in doc.sections if s.muc == "lieu_than")
        dosage.bang.append(renal.bang.pop(0))
        return doc

    monkeypatch.setattr(build_module, "load_label", load_with_misassigned_table)
    assert main(args) == 0
    before = load_chunks(out_dir / "chunks.jsonl")
    monkeypatch.setattr(build_module, "load_label", original_load)
    assert main(args) == 0
    after = load_chunks(out_dir / "chunks.jsonl")
    before_by_content = {c.noi_dung_goc: c for c in before}
    assert {c.noi_dung_goc for c in before} == {c.noi_dung_goc for c in after}
    for chunk in after:
        previous = before_by_content[chunk.noi_dung_goc]
        if chunk.duong_dan_muc == previous.duong_dan_muc:
            assert chunk.doan_trich_id == previous.doan_trich_id
        else:
            assert chunk.loai_noi_dung == "bang"
            assert chunk.muc == "lieu_than"
            assert chunk.doan_trich_id != previous.doan_trich_id
    assert main(args) == 0
    assert load_chunks(out_dir / "chunks.jsonl") == after


def test_build_only_flag_filters_labels(tmp_path: Path) -> None:
    sources_dir = _prepare_synthetic_sources(tmp_path)
    out_dir = tmp_path / "out"
    rep_dir = tmp_path / "rep"

    code = main(
        [
            "--sources",
            str(sources_dir),
            "--out",
            str(out_dir),
            "--reports",
            str(rep_dir),
            "--only",
            "meropenem",
        ]
    )
    assert code == 0
    chunks = load_chunks(out_dir / "chunks.jsonl")
    assert all(c.hoat_chat_ids == ["meropenem"] for c in chunks)


def test_build_fails_loudly_on_sha256_mismatch(tmp_path: Path) -> None:
    sources_dir = _prepare_synthetic_sources(tmp_path)
    manifest_path = sources_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    out_dir = tmp_path / "out"
    rep_dir = tmp_path / "rep"
    code = main(
        [
            "--sources",
            str(sources_dir),
            "--out",
            str(out_dir),
            "--reports",
            str(rep_dir),
        ]
    )
    assert code != 0
    assert not (out_dir / "chunks.jsonl").exists()


def test_build_fails_on_missing_file_and_q4_empty_actives(tmp_path: Path) -> None:
    sources_dir = _prepare_synthetic_sources(tmp_path)
    (sources_dir / "openfda" / "meropenem.json").unlink()
    code_missing = main(
        [
            "--sources",
            str(sources_dir),
            "--out",
            str(tmp_path / "out_m"),
            "--reports",
            str(tmp_path / "rep_m"),
        ]
    )
    assert code_missing != 0

    # Kiem tra cong Q4 bat hoat_chat_ids rong voi nhan khong co trong hoat_chat.json.
    unknown_src = tmp_path / "src_q4"
    (unknown_src / "openfda").mkdir(parents=True)
    unknown_json = unknown_src / "openfda" / "mystery_drug.json"
    payload = json.loads((_FIXTURES / "openfda_old_format.json").read_text(encoding="utf-8"))
    payload["results"][0]["openfda"]["generic_name"] = ["MYSTERY SUBSTANCE XYZ"]
    payload["results"][0]["openfda"]["brand_name"] = ["MYSTERYBRAND"]
    unknown_json.write_text(json.dumps(payload), encoding="utf-8")
    (unknown_src / "manifest.json").write_text(
        json.dumps(
            [
                {
                    "nguon": "openfda_drug_label",
                    "ten_goi": "mystery_drug",
                    "duong_dan": "openfda/mystery_drug.json",
                    "sha256": _sha256(unknown_json),
                    "set_id": "99999999-0000-0000-0000-000000000000",
                    "effective_time": "20240101",
                    "url": "https://api.fda.gov/drug/label.json?search=set_id:99999999",
                }
            ]
        ),
        encoding="utf-8",
    )
    out_q4 = tmp_path / "out_q4"
    rep_q4 = tmp_path / "rep_q4"
    code_q4 = main(
        [
            "--sources",
            str(unknown_src),
            "--out",
            str(out_q4),
            "--reports",
            str(rep_q4),
        ]
    )
    assert code_q4 != 0
    rep_file = next(rep_q4.glob("openfda_build_*.json"))
    rep_data = BuildReport.model_validate_json(rep_file.read_text(encoding="utf-8"))
    assert rep_data.dat_chat_luong is False
    assert rep_data.so_doan_hoat_chat_rong > 0


def test_build_real_meropenem_smoke(tmp_path: Path) -> None:
    out_dir = tmp_path / "real_out"
    rep_dir = tmp_path / "real_rep"
    code = main(
        [
            "--sources",
            str(_REAL_SOURCES),
            "--out",
            str(out_dir),
            "--reports",
            str(rep_dir),
            "--only",
            "meropenem",
        ]
    )
    assert code == 0
    chunks = load_chunks(out_dir / "chunks.jsonl")
    assert chunks
    assert all(c.hoat_chat_ids == ["meropenem"] for c in chunks)
    assert any(c.loai_noi_dung == "bang" for c in chunks)
