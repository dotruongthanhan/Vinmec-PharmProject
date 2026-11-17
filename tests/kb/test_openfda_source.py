"""Kiem thu bo doc va tien xu ly nhan openFDA."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.kb.names import DrugNameIndex
from app.kb.sources.openfda import LabelDocument, _extract_subsection_title, load_label

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_HOAT_CHAT_PATH = _ROOT / "data" / "kb" / "hoat_chat.json"
_MANIFEST_PATH = _ROOT / "data" / "kb_sources" / "manifest.json"


def _find_manifest_entry(ten_goi: str) -> dict:
    raw = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else raw["tep"]
    for item in items:
        if item.get("nguon") == "openfda_drug_label" and item.get("ten_goi") == ten_goi:
            return item
    raise AssertionError(f"Khong tim thay {ten_goi} trong manifest")


def test_load_new_format_fixture_strips_highlights_and_parses_tables() -> None:
    index = DrugNameIndex.load(_HOAT_CHAT_PATH)
    manifest_entry = {
        "ten_goi": "meropenem",
        "set_id": "11111111-2222-3333-4444-555555555555",
        "effective_time": "20250610",
        "url": "https://api.fda.gov/drug/label.json?search=set_id:11111111",
    }
    doc = load_label(_FIXTURES / "openfda_new_format.json", manifest_entry, index)
    assert isinstance(doc, LabelDocument)
    assert doc.tai_lieu_id == "openfda:11111111-2222-3333-4444-555555555555"
    assert doc.url_goc == (
        "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
        "setid=11111111-2222-3333-4444-555555555555"
    )
    assert doc.hoat_chat_ids == ["meropenem"]
    assert "meropenem" in doc.ten_hoat_chat
    assert "(10/06/2025)" in doc.ten_hien_thi
    assert doc.canh_bao == ["custom_unmapped_section"]

    paths = [sec.duong_dan_muc for sec in doc.sections]
    assert len(paths) == len(set(paths))
    mucs = {sec.muc for sec in doc.sections}
    assert {"chi_dinh", "chong_chi_dinh", "lieu", "lieu_than", "tuong_tac", "khac"} <= mucs
    assert "thai_ky_cho_bu" in mucs
    assert "nhi_cao_tuoi" in mucs

    # Kiem tra cat bo phan Highlights va khong giu bang tom tat cua Highlights.
    for sec in doc.sections:
        assert "HIGHLIGHTS INDICATIONS" not in sec.van_ban
        assert "HIGHLIGHTS WARNINGS" not in sec.van_ban
        assert "----------DOSAGE" not in sec.van_ban

    # Bang o tieu muc 2.2: bang chuan voi tfoot truoc tbody va bang gop o colspan=2.
    renal_secs = [s for s in doc.sections if s.muc == "lieu_than"]
    assert len(renal_secs) == 1
    renal_tables = renal_secs[0].bang
    assert len(renal_tables) == 2

    t2, t3 = renal_tables
    assert t2.tieu_de == "Table 2. Recommended Synthopenem Dosage Schedule in Renal Impairment"
    assert t2.cot == ["CrCl mL/min", "Dose", "Dosing Interval"]
    assert t2.dong == [[">50", "100%", "Every 8 hours"], ["26-50", "100%", "Every 12 hours"]]
    assert "Footnote: Based on adult renal clearance studies." in t2.van_ban_phang

    # Bang co colspan=2 -> cot va dong rong, van giu van_ban_phang.
    assert t3.cot == []
    assert t3.dong == []
    assert "Under 50 kg | 20 mg/kg every 8 hours" in t3.van_ban_phang

    # Truong 12.3 khong bi cat nham o "6.4-12.1 Myocardium".
    pk_secs = [s for s in doc.sections if "12.3" in s.duong_dan_muc]
    assert len(pk_secs) == 1
    assert "6.4-12.1 Myocardium" in pk_secs[0].van_ban

    # Truong pregnancy trung lap hoan toan voi 8.1 phai duoc loai bo.
    preg_secs = [s for s in doc.sections if s.muc == "thai_ky_cho_bu"]
    assert len(preg_secs) == 1


@pytest.mark.parametrize(
    ("segment", "major", "minor", "expected"),
    [
        (
            "2.2 Use in Adult Patients with Renal Impairment "
            "Dosage should be reduced in patients with creatinine clearance of 50 mL/min or less.",
            2,
            2,
            "2.2 Use in Adult Patients with Renal Impairment",
        ),
        (
            "8.6 Patients with Renal Impairment Dosage adjustment is necessary in patients "
            "with creatinine clearance 50 mL/min or less",
            8,
            6,
            "8.6 Patients with Renal Impairment",
        ),
        (
            "2.1 Recommended Dosage for Adult Patients The recommended dosage",
            2,
            1,
            "2.1 Recommended Dosage for Adult Patients",
        ),
        ("2.1 Dosage and Administration", 2, 1, "2.1 Dosage and Administration"),
    ],
)
def test_subsection_title_excludes_first_body_word(
    segment: str, major: int, minor: int, expected: str
) -> None:
    assert _extract_subsection_title(segment, major, minor) == expected


@pytest.mark.parametrize("set_id_source", ["entry", "openfda", "manifest", "missing"])
def test_source_url_uses_available_set_id(tmp_path: Path, set_id_source: str) -> None:
    payload = json.loads((_FIXTURES / "openfda_new_format.json").read_text(encoding="utf-8"))
    entry = payload["results"][0]
    entry.pop("set_id", None)
    entry["openfda"].pop("spl_set_id", None)
    manifest_entry = {"ten_goi": "meropenem", "url": "https://example.invalid/label"}
    set_id = "11111111-2222-3333-4444-555555555555"
    if set_id_source == "entry":
        entry["set_id"] = set_id
        entry["openfda"]["spl_set_id"] = ["other-meta-set"]
        manifest_entry["set_id"] = "other-manifest-set"
    elif set_id_source == "openfda":
        entry["openfda"]["spl_set_id"] = [set_id]
        manifest_entry["set_id"] = "other-manifest-set"
    elif set_id_source == "manifest":
        manifest_entry["set_id"] = set_id
    path = tmp_path / "label.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    doc = load_label(path, manifest_entry, DrugNameIndex.load(_HOAT_CHAT_PATH))
    if set_id_source == "missing":
        assert doc.set_id == ""
        assert doc.url_goc == ""
        assert doc.tai_lieu_id == "openfda:meropenem"
    else:
        assert doc.set_id == set_id
        assert doc.url_goc == f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}"


def test_load_old_format_fixture_maps_sections_and_dedupes_subfields() -> None:
    index = DrugNameIndex.load(_HOAT_CHAT_PATH)
    manifest_entry = {
        "ten_goi": "amoxicillin_and_clavulanate_potassium",
        "set_id": "aaaa1111-bbbb-2222-cccc-333333333333",
        "effective_time": "20230415",
        "url": "https://api.fda.gov/drug/label.json?search=set_id:aaaa1111",
    }
    doc = load_label(_FIXTURES / "openfda_old_format.json", manifest_entry, index)

    assert doc.hoat_chat_ids == ["amoxicillin", "clavulanic_acid"]
    assert doc.canh_bao == []
    mucs = {sec.muc for sec in doc.sections}
    assert {
        "chi_dinh",
        "lieu",
        "chong_chi_dinh",
        "canh_bao",
        "tuong_tac",
        "thai_ky_cho_bu",
        "nhi_cao_tuoi",
        "tac_dung_phu",
        "qua_lieu",
        "duoc_ly",
    } <= mucs

    # Ky tu an \u200b phai duoc loai bo.
    dosage_sec = next(s for s in doc.sections if s.muc == "lieu")
    assert "\u200b" not in dosage_sec.van_ban

    # Truong teratogenic_effects (< 50 ky tu) bi lap lai trong precautions khong tao muc rieng.
    assert not any(s.truong_goc == "teratogenic_effects" for s in doc.sections)

    # Khong tach nham 10.7 / 13.3 trong clinical_pharmacology cu.
    pk_secs = [s for s in doc.sections if s.muc == "duoc_ly"]
    assert len(pk_secs) == 1
    assert "10.7 Patients With Renal Impairment" in pk_secs[0].van_ban


def test_load_real_meropenem_label() -> None:
    index = DrugNameIndex.load(_HOAT_CHAT_PATH)
    entry = _find_manifest_entry("meropenem")
    doc = load_label(_ROOT / "data" / "kb_sources" / entry["duong_dan"], entry, index)

    assert doc.hoat_chat_ids == ["meropenem"]
    assert doc.tai_lieu_id == f"openfda:{entry['set_id']}"
    mucs = {sec.muc for sec in doc.sections}
    assert {"chi_dinh", "chong_chi_dinh", "tuong_tac", "tac_dung_phu"} <= mucs
    assert "lieu" in mucs or "lieu_than" in mucs
    tables = [tbl for sec in doc.sections for tbl in sec.bang]
    assert tables, "Nhan meropenem that phai trich duoc bang lieu"
    assert all(len(sec.van_ban) >= 50 for sec in doc.sections)
    for parent, title in [
        ("Dosage and Administration", "2.2 Use in Adult Patients with Renal Impairment"),
        ("Use in Specific Populations", "8.6 Patients with Renal Impairment"),
    ]:
        section = next(sec for sec in doc.sections if sec.duong_dan_muc == f"{parent} > {title}")
        assert section.van_ban.startswith(f"{title} Dosage ")
